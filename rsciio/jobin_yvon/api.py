# -*- coding: utf-8 -*-
# Copyright 2007-2022 The HyperSpy developers
#
# This file is part of HyperSpy.
#
# HyperSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HyperSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HyperSpy. If not, see <https://www.gnu.org/licenses/#GPL>.

from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import logging
from copy import deepcopy
import importlib.util

_logger = logging.getLogger(__name__)

lumispy_installed = True
if importlib.util.find_spec("lumispy") is None:
    lumispy_installed = False
    _logger.warning("Cannot find package lumispy, using '' as signal_type.")


class JobinYvonXMLReader:
    def __init__(self, file_path, use_uniform_wavelength_axis=True, **kwargs):
        self.use_uniform_wavelength_axis = use_uniform_wavelength_axis
        self.file_path = file_path
        self.metadata = dict()

    ## each element of the xml-tree has the attributes attrib, tag, text
    ## jobin-yvon-xml only has the tags LSX_DATA,
    ## attrib contains the format, id and size (in the tag in the original xml-file)
    ## the actual content between the tags is stored in the attribute text
    ## format specifies the datatype of the text
    @staticmethod
    def get_id(xml_element):
        return xml_element.attrib["ID"]

    @staticmethod
    def get_size(xml_element):
        return int(xml_element.attrib["Size"])

    def parse_file(self):
        """First parse through file to extract data/metadata positions."""
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        lsx_tree_list = root.findall("LSX_Tree")
        assert len(lsx_tree_list) == 1
        self.lsx_tree = lsx_tree_list[0]

        lsx_matrix_list = root.findall("LSX_Matrix")
        assert len(lsx_matrix_list) == 1
        self.lsx_matrix = lsx_matrix_list[0]

        self.original_metadata = {}

        for child in self.lsx_tree:
            id = self.get_id(child)
            if id == "0x6C62D4D9":
                self.metadata_head = child
            if id == "0x6C7469D9":
                self.title = child.text
            if id == "0x6D707974":
                self.measurement_type = child.text
            if id == "0x7A74D9D6":
                for child2 in child:
                    if self.get_id(child2) == "0x7B697861":
                        self.nav_tree = child2

    def _get_metadata_values(self, xml_element, tag):
        """Helper method to extract information from metadata xml-element.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            head level metadata element
        tag: Str
            is used as key in original_metadata dictionary

        Example
        -------
        <LSX Format="9" ID="0x6D7361DE" Size="5">
                        <LSX Format="7" ID="0x6D6D616E">Laser (nm)</LSX>
                        <LSX Format="7" ID="0x7D6C61DB">633 </LSX>
                        <LSX Format="5" ID="0x8736F70">632.817</LSX>
                        <LSX Format="4" ID="0x6A6DE7D3">0</LSX>
        </LSX>

        This corresponds to child-level (xml-element would be multiple of those elements).
        ID="0x6D6D616E" -> key name for original metadata
        ID="0x7D6C61DB" -> first value
        ID="0x8736F70" -> second value

        Which value is used is decided in _clean_up_metadata (in this case the second value is used).
        """
        metadata_xml_element = dict()
        for child in xml_element:
            values = {}
            for child2 in child:
                if self.get_id(child2) == "0x6D6D616E":
                    key = child2.text
                if self.get_id(child2) == "0x7D6C61DB":
                    values["1"] = child2.text
                if self.get_id(child2) == "0x8736F70":
                    values["2"] = child2.text
            metadata_xml_element[key] = values
        self.original_metadata[tag] = metadata_xml_element

    def _clean_up_metadata(self):
        """Cleans up original metadata to meet standardized format.

        This means converting numbers from strings to floats,
        deciding which value shall be used (when 2 values are extracted,
        see _get_metadata_values() for more information).
        Moreover, some names are slightly modified.
        """
        convert_to_numeric = [
            "Acq. time (s)",
            "Accumulations",
            "Delay time (s)",
            "Binning",
            "Detector temperature (°C)",
            "Objective",
            "Grating",
            "ND Filter",
            "Laser (nm)",
            "Spectro (nm)",
            "Hole",
            "Laser Pol. (°)",
            "Raman Pol. (°)",
            "X (µm)",
            "Y (µm)",
            "Z (µm)",
            "Full time(s)",
        ]

        change_to_second_value = [
            "Objective",
            "Grating",
            "ND Filter",
            "Laser (nm)",
            "Spectro (nm)",
        ]

        ## use second extracted value
        for key in change_to_second_value:
            try:
                self.original_metadata["experimental setup"][
                    key
                ] = self.original_metadata["experimental setup"][key]["2"]
            except KeyError:
                pass

        ## use first extracted value
        for key, value in self.original_metadata["experimental setup"].items():
            if isinstance(value, dict):
                self.original_metadata["experimental setup"][
                    key
                ] = self.original_metadata["experimental setup"][key]["1"]

        for key, value in self.original_metadata["date"].items():
            if isinstance(value, dict):
                self.original_metadata["date"][key] = self.original_metadata["date"][
                    key
                ]["1"]

        for key, value in self.original_metadata["file information"].items():
            if isinstance(value, dict):
                self.original_metadata["file information"][
                    key
                ] = self.original_metadata["file information"][key]["1"]

        ## convert strings to float
        for key in convert_to_numeric:
            try:
                self.original_metadata["experimental setup"][key] = float(
                    self.original_metadata["experimental setup"][key]
                )
            except KeyError:
                pass

        ## move the unit from grating to the key name
        new_grating_key_name = "Grating (gr/mm)"
        try:
            self.original_metadata["experimental setup"][
                new_grating_key_name
            ] = self.original_metadata["experimental setup"]["Grating"]
            del self.original_metadata["experimental setup"]["Grating"]
        except KeyError:
            pass

        ## add percentage for filter key name
        new_filter_key_name = "ND Filter (%)"
        try:
            self.original_metadata["experimental setup"][
                new_filter_key_name
            ] = self.original_metadata["experimental setup"]["ND Filter"]
            del self.original_metadata["experimental setup"]["ND Filter"]
        except KeyError:
            pass

    def get_original_metadata(self):
        """Extracts metadata from file."""
        assert hasattr(self, "metadata_head")
        for child in self.metadata_head:
            id = self.get_id(child)
            if id == "0x7CECDBD7":
                date = child
            if id == "0x8716361":
                metadata = child
            if id == "0x7C73E2D2":
                file_specs = child

        ## setup tree structure original_metadata -> date{...}, experimental setup{...}, file information{...}
        ## based on structure in file
        self._get_metadata_values(date, "date")
        self._get_metadata_values(metadata, "experimental setup")
        self._get_metadata_values(file_specs, "file information")
        self.original_metadata["experimental setup"][
            "measurement_type"
        ] = self.measurement_type
        self.original_metadata["experimental setup"]["title"] = self.title
        self._clean_up_metadata()

    def get_scale(self, array, name):
        """Get scale for navigation/signal axes.

        Furthermore, checks whether the axis is uniform. Throws warning when this not the case.

        Parameters
        ----------
        array: np.ndarray
            contains the axes data points
        name: Str
            name of the axis
        """
        assert isinstance(array, np.ndarray)
        assert hasattr(array, "size")
        assert array.size >= 2
        if array.size >= 3:
            abs_diff_begin = np.abs(array[0] - array[1])
            abs_diff_end = np.abs(array[-1] - array[-2])
            abs_diff_compare = np.abs(abs_diff_begin - abs_diff_end)
            min_array = np.amin(array)
            if not np.isclose(min_array, 0):
                rel_diff_begin = abs_diff_begin / min_array
                rel_diff_end = abs_diff_end / min_array
                rel_diff_compare = np.abs(rel_diff_begin - rel_diff_end)
                if rel_diff_compare > 0.01 and self.use_uniform_wavelength_axis:
                    _logger.warning(
                        f"The relative variation of the {name}-axis-scale ({rel_diff_compare}) is greater than 1%. Using a non-uniform-axis is recommended."
                    )
            if not np.isclose(abs_diff_compare, 0) and self.use_uniform_wavelength_axis:
                _logger.warning(
                    f"The difference between consecutive entrys of the {name}-axis-scale varies ({abs_diff_compare} between first 2 and last 2). Consider using a non-uniform-axis."
                )
        return np.abs(array[0] - array[-1]) / (array.size - 1)

    def _set_nav_axis(self, xml_element, tag):
        """Helper method set navigation axes.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            head level metadata element
        tag: Str
            axis name
        """
        # assert measurement_type == "SpIm"
        has_nav = True
        nav_dict = dict()
        for child in xml_element:
            id = self.get_id(child)
            if id == "0x6D707974":
                nav_dict["name"] = child.text
            if id == "0x7C696E75":
                nav_dict["units"] = child.text
            if id == "0x7D6CD4DB":
                nav_array = np.fromstring(child.text.strip(), sep=" ")
                nav_size = nav_array.size
                if nav_size < 2:
                    has_nav = False
                else:
                    nav_dict["scale"] = self.get_scale(nav_array, tag)
                    nav_dict["offset"] = np.amin(nav_array)
                    nav_dict["size"] = nav_size
                    nav_dict["navigate"] = True
        if has_nav:
            self.axes[tag] = nav_dict
        return has_nav, nav_size

    def _set_signal_type(self, xml_element):
        """Sets signal type and units based on metadata from file.

        Extra method, because this information is stored seperate from the rest of the metadata.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            head level metadata element
        """
        for child in xml_element:
            id = self.get_id(child)
            ## contains also intensity-minima/maxima-values for each data-row (ignored by this reader)
            if id == "0x6D707974":
                self.original_metadata["experimental setup"]["signal type"] = child.text
            if id == "0x7C696E75":
                self.original_metadata["experimental setup"][
                    "signal units"
                ] = child.text

    def _set_signal_axis(self, xml_element):
        """Helper method set signal axes.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            head level metadata element
        tag: Str
            axis name
        """
        wavelength_dict = dict()
        for child in xml_element:
            id = self.get_id(child)
            if id == "0x7D6CD4DB":
                wavelength_array = np.fromstring(child.text.strip(), sep=" ")
                wavelength_dict["scale"] = self.get_scale(
                    wavelength_array, "wavelength"
                )
                wavelength_dict["offset"] = wavelength_array[0]
                wavelength_dict["size"] = wavelength_array.size
                if wavelength_array[0] > wavelength_array[1]:
                    wavelength_dict["scale"] *= -1
            if id == "0x6D707974":
                wavelength_dict["name"] = child.text
            if id == "0x7C696E75":
                wavelength_dict["units"] = child.text
        if wavelength_dict["name"] == "Spectr":
            if wavelength_dict["units"][:2] == "1/":
                wavelength_dict["name"] = "Wavenumber"
                wavelength_dict["units"] = wavelength_dict["units"][:4]
            elif wavelength_dict["units"] == "nm":
                wavelength_dict["name"] = "Wavelength"
            elif wavelength_dict["units"] == "eV":
                wavelength_dict["name"] = "Energy"
            else:
                _logger.warning(
                    "Cannot extract type of signal axis, using wavelength as name. Check on axis units (nm, eV, 1/cm can be read)"
                )
                wavelength_dict["name"] = "Wavelength"
        wavelength_dict["navigate"] = False
        if not self.use_uniform_wavelength_axis:
            del wavelength_dict["offset"]
            del wavelength_dict["scale"]
            del wavelength_dict["size"]
            wavelength_dict["axis"] = wavelength_array
        self.axes["wavelength_dict"] = wavelength_dict

    def _sort_nav_axes(self):
        """sort the navigation axis, such that (X, Y, Spectrum) = (1, 0, 2) (for map)
        or (X/Y, Spectrum) = (0, 1) or (Spectrum) = (0) (for linescan/spectrum).
        """
        self.axes["wavelength_dict"]["index_in_array"] = len(self.axes) - 1
        if self.has_nav2:
            self.axes["nav2_dict"]["index_in_array"] = 0
            if self.has_nav1:
                self.axes["nav1_dict"]["index_in_array"] = 1
        elif self.has_nav1 and not self.has_nav2:
            self.axes["nav1_dict"]["index_in_array"] = 0
        self.axes = sorted(self.axes.values(), key=lambda item: item["index_in_array"])

    def get_axes(self):
        """Extract navigation/signal axes data from file."""
        assert hasattr(self, "nav_tree")

        self.axes = dict()
        self.has_nav1 = False
        self.has_nav2 = False
        for child in self.nav_tree:
            if self.get_id(child) == "0x0":
                self._set_signal_type(child)
            if self.get_id(child) == "0x1":
                self._set_signal_axis(child)
            if self.get_id(child) == "0x2":
                self.has_nav1, self.nav1_size = self._set_nav_axis(child, "nav1_dict")
            if self.get_id(child) == "0x3":
                self.has_nav2, self.nav2_size = self._set_nav_axis(child, "nav2_dict")

        self._sort_nav_axes()

    def get_data(self):
        """Extract data from file."""
        assert hasattr(self, "lsx_matrix")

        sig_raw = self.lsx_matrix.findall("LSX_Row")
        ## lexicographical ordering -> 3x3 map -> 9 rows
        num_rows = len(sig_raw)
        if num_rows == 1:
            ## Spectrum
            self.sig_array = np.fromstring(sig_raw[0].text.strip(), sep=" ")
        else:
            ## linescan or map
            num_cols = self.get_size(sig_raw[0])
            self.sig_array = np.empty((num_rows, num_cols))
            for i, row in enumerate(sig_raw):
                row_array = np.fromstring(row.text.strip(), sep=" ")
                self.sig_array[i, :] = row_array
            ## reshape the array (lexicographic -> cartesian)
            ## reshape depends on available axes
            if self.has_nav2:
                if self.has_nav1:
                    self.sig_array = np.reshape(
                        self.sig_array, (self.nav2_size, self.nav1_size, num_cols)
                    )
                else:
                    self.sig_array = np.reshape(
                        self.sig_array, (self.nav2_size, num_cols)
                    )
            elif self.has_nav1 and not self.has_nav2:
                self.sig_array = np.reshape(self.sig_array, (self.nav1_size, num_cols))

    @property
    def record_by(self):
        if self.measurement_type == "Spectrum":
            return "spectrum"
        if self.measurement_type == "SpIm":
            return "image"

    @property
    def signal_type(self):
        if lumispy_installed:
            return "Luminescence"
        else:
            return ""

    @staticmethod
    def _set_metadata(dict_out, key_out, dict_in, key_in):
        """Sets key in dict_out, when key_in exists in dict_in."""
        try:
            dict_out[key_out] = dict_in[key_in]
        except KeyError:
            pass

    ## account for missing keys in original metadata (try/except)
    def map_metadata(self):
        """Maps original_metadata to metadata dictionary."""
        if "General" not in self.metadata:
            self.metadata["General"] = {}
        if "Signal" not in self.metadata:
            self.metadata["Signal"] = {}
        if "Sample" not in self.metadata:
            self.metadata["Sample"] = {}
        if "Acquisition_instrument" not in self.metadata:
            self.metadata["Acquisition_instrument"] = {
                "Laser": {"Filter": {}, "Polarizer": {}},
                "Spectrometer": {"Grating": {}, "Polarizer": {}},
                "Detector": {"processing": {}},
                "Spectral_image": {},
            }

        self.metadata["General"]["title"] = self.title
        self.metadata["General"]["original_filename"] = self.file_path.name
        self._set_metadata(
            self.metadata["General"],
            "notes",
            self.original_metadata["file information"],
            "Remark",
        )
        try:
            date, time = self.original_metadata["date"]["Acquired"].split(" ")
            self.metadata["General"]["date"] = date
            self.metadata["General"]["time"] = time
        except KeyError:
            pass

        self.metadata["Signal"]["record_by"] = self.record_by
        try:
            intensity_axis = self.original_metadata["experimental setup"]["signal type"]
            intensity_units = self.original_metadata["experimental setup"][
                "signal units"
            ]
        except KeyError:
            pass
        else:
            if intensity_axis == "Intens":
                intensity_axis = "Intensity"
            if intensity_units == "Cnt/sec":
                intensity_units = "Counts/s"
            self.metadata["Signal"][
                "quantity"
            ] = f"{intensity_axis} ({intensity_units})"
            self.metadata["Signal"]["signal_type"] = self.signal_type

        self._set_metadata(
            self.metadata["Sample"],
            "description",
            self.original_metadata["file information"],
            "Sample",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"],
            "wavelength",
            self.original_metadata["experimental setup"],
            "Laser (nm)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"],
            "objective_magnification",
            self.original_metadata["experimental setup"],
            "Objective",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"]["Filter"],
            "optical_density",
            self.original_metadata["experimental setup"],
            "ND Filter (%)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "central_wavelength",
            self.original_metadata["experimental setup"],
            "Spectro (nm)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "model",
            self.original_metadata["experimental setup"],
            "Instrument",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"]["Grating"],
            "groove_density",
            self.original_metadata["experimental setup"],
            "Grating (gr/mm)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "entrance_slit_width",
            self.original_metadata["experimental setup"],
            "Hole",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "spectral_range",
            self.original_metadata["experimental setup"],
            "Range",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "model",
            self.original_metadata["experimental setup"],
            "Detector",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "delay_time",
            self.original_metadata["experimental setup"],
            "Delay time (s)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "binning",
            self.original_metadata["experimental setup"],
            "Binning",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "temperature",
            self.original_metadata["experimental setup"],
            "Detector temperature (°C)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "exposure_per_frame",
            self.original_metadata["experimental setup"],
            "Acq. time (s)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "frames",
            self.original_metadata["experimental setup"],
            "Accumulations",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "autofocus",
            self.original_metadata["experimental setup"],
            "Autofocus",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "swift",
            self.original_metadata["experimental setup"],
            "SWIFT",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "auto_exposure",
            self.original_metadata["experimental setup"],
            "AutoExposure",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "spike_filter",
            self.original_metadata["experimental setup"],
            "Spike filter",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "de_noise",
            self.original_metadata["experimental setup"],
            "DeNoise",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "ics_correction",
            self.original_metadata["experimental setup"],
            "ICS correction",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "dark_correction",
            self.original_metadata["experimental setup"],
            "Dark correction",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "inst_process",
            self.original_metadata["experimental setup"],
            "Inst. Process",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"]["Polarizer"],
            "polarizer_type",
            self.original_metadata["experimental setup"],
            "Laser. Pol.",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"]["Polarizer"],
            "polarizer_type",
            self.original_metadata["experimental setup"],
            "Raman. Pol.",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"]["Polarizer"],
            "angle",
            self.original_metadata["experimental setup"],
            "Laser Pol. (°)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"]["Polarizer"],
            "angle",
            self.original_metadata["experimental setup"],
            "Raman Pol. (°)",
        )

        ## calculate and set integration time
        try:
            integration_time = (
                self.original_metadata["experimental setup"]["Accumulations"]
                * self.original_metadata["experimental setup"]["Acq. time (s)"]
            )
        except KeyError:
            pass
        else:
            self.metadata["Acquisition_instrument"]["Detector"][
                "integration_time"
            ] = integration_time

        ## convert filter range from percentage (0-100) to (0-1)
        try:
            self.metadata["Acquisition_instrument"]["Laser"]["Filter"][
                "optical_density"
            ] /= 100
        except KeyError:
            pass

        ## convert entrance_hole_width to mm
        try:
            self.metadata["Acquisition_instrument"]["Spectrometer"][
                "entrance_slit_width"
            ] /= 100
            self.metadata["Acquisition_instrument"]["Spectrometer"][
                "pinhole"
            ] = self.metadata["Acquisition_instrument"]["Spectrometer"][
                "entrance_slit_width"
            ]
        except KeyError:
            pass


def file_reader(file_path, lazy=False, use_uniform_wavelength_axis=True, **kwds):
    """Reads a file with jobin-yvon-xml-format.

    Parameters
    ----------
    use_uniform_wavelength_axis: bool
        can be specified to choose between non-uniform or uniform navigation axes
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    jy = JobinYvonXMLReader(
        file_path, use_uniform_wavelength_axis=use_uniform_wavelength_axis
    )
    jy.parse_file()
    jy.get_original_metadata()
    jy.get_axes()
    jy.get_data()
    jy.map_metadata()
    dictionary = {
        "data": jy.sig_array,
        "axes": jy.axes,
        "metadata": deepcopy(jy.metadata),
        "original_metadata": deepcopy(jy.original_metadata),
    }
    return [
        dictionary,
    ]
