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

import logging
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path
from copy import deepcopy

import numpy as np

_logger = logging.getLogger(__name__)


class JobinYvonXMLReader:
    """Class to read Jobin Yvon .xml-files.

    The file is read using xml.etree.ElementTree.
    Each element can have the following attributes: attrib, tag, text.
    Moreover, non-leaf-elements are iterable (iterate over child-nodes).
    In this specific format, the tags do not contain useful information.
    Instead, the "ID"-entry in attrib is used to identify the sort of information.
    The IDs are consistent for the tested files.

    Parameters
    ----------
    file_path: pathlib.Path
        Path to the to be read file.

    use_uniform_signal_axis: bool, default=True
        Decides whether to use uniform or non-uniform data axis.

    Attributes
    ----------
    data, metadata, original_metadata, axes

    Methods
    -------
    parse_file, get_original_metadata, get_axes, get_data, map_metadata
    """

    def __init__(self, file_path, use_uniform_signal_axis=True):
        self._file_path = file_path
        self._use_uniform_signal_axis = use_uniform_signal_axis
        self._reverse_wavelength = False

        if importlib.util.find_spec("lumispy") is None:
            self._lumispy_installed = False
            _logger.warning("Cannot find package lumispy, using '' as signal_type.")
        else:
            self._lumispy_installed = True

    @staticmethod
    def _get_id(xml_element):
        return xml_element.attrib["ID"]

    @staticmethod
    def _get_size(xml_element):
        return int(xml_element.attrib["Size"])

    def parse_file(self):
        """First parse through file to extract data/metadata positions."""
        tree = ET.parse(self._file_path)
        root = tree.getroot()

        lsx_tree_list = root.findall("LSX_Tree")
        assert len(lsx_tree_list) == 1
        lsx_tree = lsx_tree_list[0]

        lsx_matrix_list = root.findall("LSX_Matrix")
        assert len(lsx_matrix_list) == 1
        self._lsx_matrix = lsx_matrix_list[0]

        for child in lsx_tree:
            id = self._get_id(child)
            if id == "0x6C62D4D9":
                self._metadata_head = child
            if id == "0x6C7469D9":
                self._title = child.text
            if id == "0x6D707974":
                self._measurement_type = child.text
            if id == "0x6C676EC6":
                for child2 in child:
                    if self._get_id(child2) == "0x0":
                        self._angle = child2.text
            if id == "0x7A74D9D6":
                for child2 in child:
                    if self._get_id(child2) == "0x7B697861":
                        self._nav_tree = child2

    def _get_metadata_values(self, xml_element, tag):
        """Helper method to extract information from metadata xml-element.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            Head level metadata element.
        tag: Str
            Used as the corresponding key in the original_metadata dictionary.

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
                if self._get_id(child2) == "0x6D6D616E":
                    key = child2.text
                if self._get_id(child2) == "0x7D6C61DB":
                    values["1"] = child2.text
                if self._get_id(child2) == "0x8736F70":
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
            "angle (rad)",
            "Windows",
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
                self.original_metadata["experimental_setup"][
                    key
                ] = self.original_metadata["experimental_setup"][key]["2"]
            except KeyError:
                pass

        ## use first extracted value
        for key, value in self.original_metadata["experimental_setup"].items():
            if isinstance(value, dict):
                # only if there is an entry/value
                if bool(value):
                    self.original_metadata["experimental_setup"][
                        key
                    ] = self.original_metadata["experimental_setup"][key]["1"]

        for key, value in self.original_metadata["date"].items():
            if isinstance(value, dict):
                if bool(value):
                    self.original_metadata["date"][key] = self.original_metadata[
                        "date"
                    ][key]["1"]

        for key, value in self.original_metadata["file_information"].items():
            if isinstance(value, dict):
                if bool(value):
                    self.original_metadata["file_information"][
                        key
                    ] = self.original_metadata["file_information"][key]["1"]

        ## convert strings to float
        for key in convert_to_numeric:
            try:
                self.original_metadata["experimental_setup"][key] = float(
                    self.original_metadata["experimental_setup"][key]
                )
            except KeyError:
                pass

        ## move the unit from grating to the key name
        new_grating_key_name = "Grating (gr/mm)"
        try:
            self.original_metadata["experimental_setup"][
                new_grating_key_name
            ] = self.original_metadata["experimental_setup"]["Grating"]
            del self.original_metadata["experimental_setup"]["Grating"]
        except KeyError: # pragma: no cover
            pass # pragma: no cover

        ## add percentage for filter key name
        new_filter_key_name = "ND Filter (%)"
        try:
            self.original_metadata["experimental_setup"][
                new_filter_key_name
            ] = self.original_metadata["experimental_setup"]["ND Filter"]
            del self.original_metadata["experimental_setup"]["ND Filter"]
        except KeyError: # pragma: no cover
            pass # pragma: no cover

    def get_original_metadata(self):
        """Extracts metadata from file."""
        assert hasattr(self, "_metadata_head")
        self.original_metadata = {}
        for child in self._metadata_head:
            id = self._get_id(child)
            if id == "0x7CECDBD7":
                date = child
            if id == "0x8716361":
                metadata = child
            if id == "0x7C73E2D2":
                file_specs = child

        ## setup tree structure original_metadata -> date{...}, experimental_setup{...}, file_information{...}
        ## based on structure in file
        self._get_metadata_values(date, "date")
        self._get_metadata_values(metadata, "experimental_setup")
        self._get_metadata_values(file_specs, "file_information")
        try:
            self.original_metadata["experimental_setup"][
                "measurement_type"
            ] = self._measurement_type
        except AttributeError: # pragma: no cover
            pass # pragma: no cover
        try:
            self.original_metadata["experimental_setup"]["title"] = self._title
        except AttributeError: # pragma: no cover
            pass # pragma: no cover
        try:
            self.original_metadata["experimental_setup"]["angle (rad)"] = self._angle
        except AttributeError:
            pass
        self._clean_up_metadata()

    def _get_scale(self, array, name):
        """Get scale for navigation/signal axes.

        Furthermore, checks whether the axis is uniform. Throws warning when this not the case.
        This check is performed by comparing the difference between the first 2 and last 2 values.
        The decision to use a non-uniform/uniform data-axis is left to the user
        (use_uniform_wavelength_axis).

        Parameters
        ----------
        array: np.ndarray
            Contains the axes data points.
        name: Str
            Name of the axis.
        """
        assert isinstance(array, np.ndarray)
        assert hasattr(array, "size")
        assert array.size >= 2
        scale = np.abs(array[0] - array[-1]) / (array.size - 1)
        if array.size >= 3:
            abs_diff_begin = np.abs(array[0] - array[1])
            abs_diff_end = np.abs(array[-1] - array[-2])
            abs_diff_compare = np.abs(abs_diff_begin - abs_diff_end)
            min_array = np.amin(array)
            if not np.isclose(min_array, 0):
                rel_diff_compare = abs_diff_compare / min_array
                if rel_diff_compare > 0.01 and self._use_uniform_signal_axis: # pragma: no cover
                    _logger.warning(
                        f"The relative variation of the {name}-axis-scale ({rel_diff_compare}) is greater than 1%. Using a non-uniform-axis is recommended."
                    ) # pragma: no cover
            if not np.isclose(abs_diff_compare, 0) and self._use_uniform_signal_axis:
                _logger.warning(
                    f"The difference between consecutive entrys (scale) of the {name}-axis varies (from {abs_diff_begin} to {abs_diff_end} between the first 2 and last 2 entrys, difference: {abs_diff_compare}). {scale} will be used for scale. Consider using a non-uniform-axis."
                )
        return scale

    def _set_nav_axis(self, xml_element, tag):
        """Helper method for setting navigation axes.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            Head level metadata element.
        tag: Str
            Axis name.
        """
        # assert measurement_type == "SpIm"
        has_nav = True
        nav_dict = dict()
        for child in xml_element:
            id = self._get_id(child)
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
                    nav_dict["scale"] = self._get_scale(nav_array, tag)
                    nav_dict["offset"] = nav_array[0]
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
            Head level metadata element.
        """
        for child in xml_element:
            id = self._get_id(child)
            ## contains also intensity-minima/maxima-values for each data-row (ignored by this reader)
            if id == "0x6D707974":
                self.original_metadata["experimental_setup"]["signal type"] = child.text
            if id == "0x7C696E75":
                self.original_metadata["experimental_setup"][
                    "signal units"
                ] = child.text

    def _set_signal_axis(self, xml_element):
        """Helper method to extract signal-axis information.

        Parameters
        ----------
        xml_element: xml.etree.ElementTree.Element
            Head level metadata element.
        tag: Str
            Axis name.
        """
        wavelength_dict = dict()
        wavelength_dict["navigate"] = False
        for child in xml_element:
            id = self._get_id(child)
            if id == "0x7D6CD4DB":
                wavelength_array = np.fromstring(child.text.strip(), sep=" ")
                if wavelength_array[0] > wavelength_array[1]:
                    wavelength_array = wavelength_array[::-1]
                    self._reverse_wavelength = True
                if self._use_uniform_signal_axis:
                    wavelength_dict["scale"] = self._get_scale(
                        wavelength_array, "wavelength"
                    )
                    wavelength_dict["offset"] = wavelength_array[0]
                    wavelength_dict["size"] = wavelength_array.size
                else:
                    wavelength_dict["axis"] = wavelength_array
            if id == "0x7C696E75":
                units = child.text
                if "/" in units and units[-3:] == "abs":
                    wavelength_dict["name"] = "Wavenumber"
                    wavelength_dict["units"] = units[:-4]
                elif "/" in units and units[-1] == "m":
                    wavelength_dict["name"] = "Raman Shift"
                    wavelength_dict["units"] = units
                elif units[-2:] == "eV":
                    wavelength_dict["name"] = "Energy"
                    wavelength_dict["units"] = units
                elif "/" not in units and units[-1] == "m":
                    wavelength_dict["name"] = "Wavelength"
                    wavelength_dict["units"] = units
                else: # pragma: no cover
                    _logger.warning(
                        "Cannot extract type of signal axis from units, using wavelength as name."
                    ) # pragma: no cover
                    wavelength_dict["name"] = "Wavelength" # pragma: no cover
                    wavelength_dict["units"] = units # pragma: no cover
        self.axes["wavelength_dict"] = wavelength_dict

    def _sort_nav_axes(self):
        """Sort the navigation axis, such that (X, Y, Spectrum) = (1, 0, 2) (for map)
        or (X/Y, Spectrum) = (0, 1) or (Spectrum) = (0) (for linescan/spectrum).
        """
        self.axes["wavelength_dict"]["index_in_array"] = len(self.axes) - 1
        if self._has_nav2:
            self.axes["nav2_dict"]["index_in_array"] = 0
            if self._has_nav1:
                self.axes["nav1_dict"]["index_in_array"] = 1
        elif self._has_nav1 and not self._has_nav2:
            self.axes["nav1_dict"]["index_in_array"] = 0
        self.axes = sorted(self.axes.values(), key=lambda item: item["index_in_array"])

    def get_axes(self):
        """Extract navigation/signal axes data from file."""
        assert hasattr(self, "_nav_tree")

        self.axes = dict()
        self._has_nav1 = False
        self._has_nav2 = False
        for child in self._nav_tree:
            if self._get_id(child) == "0x0":
                self._set_signal_type(child)
            if self._get_id(child) == "0x1":
                self._set_signal_axis(child)
            if self._get_id(child) == "0x2":
                self._has_nav1, self._nav1_size = self._set_nav_axis(child, "nav1_dict")
            if self._get_id(child) == "0x3":
                self._has_nav2, self._nav2_size = self._set_nav_axis(child, "nav2_dict")

        self._sort_nav_axes()

    def get_data(self):
        """Extract data from file."""
        assert hasattr(self, "_lsx_matrix")

        data_raw = self._lsx_matrix.findall("LSX_Row")
        ## lexicographical ordering -> 3x3 map -> 9 rows
        num_rows = len(data_raw)
        if num_rows == 1:
            ## Spectrum
            self.data = np.fromstring(data_raw[0].text.strip(), sep=" ")
            if self._reverse_wavelength:
                self.data = self.data[::-1]
        else:
            ## linescan or map
            num_cols = self._get_size(data_raw[0])
            self.data = np.empty((num_rows, num_cols))
            for i, row in enumerate(data_raw):
                row_array = np.fromstring(row.text.strip(), sep=" ")
                if self._reverse_wavelength:
                    row_array = row_array[::-1]
                self.data[i, :] = row_array
            ## reshape the array (lexicographic -> cartesian)
            ## reshape depends on available axes
            if self._has_nav2:
                if self._has_nav1:
                    self.data = np.reshape(
                        self.data, (self._nav2_size, self._nav1_size, num_cols)
                    )
                else:
                    self.data = np.reshape(self.data, (self._nav2_size, num_cols))
            elif self._has_nav1 and not self._has_nav2: # pragma: no cover
                self.data = np.reshape(self.data, (self._nav1_size, num_cols)) # pragma: no cover

    @property
    def _signal_type(self):
        if self._lumispy_installed:
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
        self.metadata = dict()
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

        self.metadata["General"]["title"] = self._title
        self.metadata["General"]["original_filename"] = self._file_path.name
        self._set_metadata(
            self.metadata["General"],
            "notes",
            self.original_metadata["file_information"],
            "Remark",
        )
        try:
            date, time = self.original_metadata["date"]["Acquired"].split(" ")
            self.metadata["General"]["date"] = date
            self.metadata["General"]["time"] = time
        except KeyError: # pragma: no cover
            pass # pragma: no cover

        try:
            intensity_axis = self.original_metadata["experimental_setup"]["signal type"]
            intensity_units = self.original_metadata["experimental_setup"][
                "signal units"
            ]
        except KeyError: # pragma: no cover
            pass # pragma: no cover
        else:
            if intensity_axis == "Intens":
                intensity_axis = "Intensity"
            if intensity_units == "Cnt/sec":
                intensity_units = "Counts/s"
            if intensity_units == "Cnt":
                intensity_units = "Counts"
            self.metadata["Signal"][
                "quantity"
            ] = f"{intensity_axis} ({intensity_units})"

        self.metadata["Signal"]["signal_type"] = self._signal_type
        self.metadata["Signal"]["signal_dimension"] = 1

        self._set_metadata(
            self.metadata["Sample"],
            "description",
            self.original_metadata["file_information"],
            "Sample",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"],
            "wavelength",
            self.original_metadata["experimental_setup"],
            "Laser (nm)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"],
            "objective_magnification",
            self.original_metadata["experimental_setup"],
            "Objective",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"]["Filter"],
            "optical_density",
            self.original_metadata["experimental_setup"],
            "ND Filter (%)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "central_wavelength",
            self.original_metadata["experimental_setup"],
            "Spectro (nm)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "model",
            self.original_metadata["experimental_setup"],
            "Instrument",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"]["Grating"],
            "groove_density",
            self.original_metadata["experimental_setup"],
            "Grating (gr/mm)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "entrance_slit_width",
            self.original_metadata["experimental_setup"],
            "Hole",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"],
            "spectral_range",
            self.original_metadata["experimental_setup"],
            "Range",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "model",
            self.original_metadata["experimental_setup"],
            "Detector",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "delay_time",
            self.original_metadata["experimental_setup"],
            "Delay time (s)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "binning",
            self.original_metadata["experimental_setup"],
            "Binning",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "temperature",
            self.original_metadata["experimental_setup"],
            "Detector temperature (°C)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "exposure_per_frame",
            self.original_metadata["experimental_setup"],
            "Acq. time (s)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"],
            "frames",
            self.original_metadata["experimental_setup"],
            "Accumulations",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "autofocus",
            self.original_metadata["experimental_setup"],
            "Autofocus",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "swift",
            self.original_metadata["experimental_setup"],
            "SWIFT",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "auto_exposure",
            self.original_metadata["experimental_setup"],
            "AutoExposure",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "spike_filter",
            self.original_metadata["experimental_setup"],
            "Spike filter",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "de_noise",
            self.original_metadata["experimental_setup"],
            "DeNoise",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "ics_correction",
            self.original_metadata["experimental_setup"],
            "ICS correction",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "dark_correction",
            self.original_metadata["experimental_setup"],
            "Dark correction",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Detector"]["processing"],
            "inst_process",
            self.original_metadata["experimental_setup"],
            "Inst. Process",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"]["Polarizer"],
            "polarizer_type",
            self.original_metadata["experimental_setup"],
            "Laser. Pol.",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"]["Polarizer"],
            "polarizer_type",
            self.original_metadata["experimental_setup"],
            "Raman. Pol.",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Laser"]["Polarizer"],
            "angle",
            self.original_metadata["experimental_setup"],
            "Laser Pol. (°)",
        )
        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectrometer"]["Polarizer"],
            "angle",
            self.original_metadata["experimental_setup"],
            "Raman Pol. (°)",
        )

        self._set_metadata(
            self.metadata["Acquisition_instrument"]["Spectral_image"],
            "angle",
            self.original_metadata["experimental_setup"],
            "angle (rad)",
        )

        ## extra units here, because rad vs. deg
        if "angle (rad)" in self.original_metadata["experimental_setup"]:
            self.metadata["Acquisition_instrument"]["Spectral_image"][
                "angle_units"
            ] = "rad"

        if "Windows" in self.original_metadata["experimental_setup"]:
            self.metadata["Acquisition_instrument"]["Detector"]["glued_spectrum"] = True
            self.metadata["Acquisition_instrument"]["Detector"][
                "glued_spectrum_windows"
            ] = self.original_metadata["experimental_setup"]["Windows"]
        else:
            self.metadata["Acquisition_instrument"]["Detector"][
                "glued_spectrum"
            ] = False

        ## calculate and set integration time
        try:
            integration_time = (
                self.original_metadata["experimental_setup"]["Accumulations"]
                * self.original_metadata["experimental_setup"]["Acq. time (s)"]
            )
        except KeyError: # pragma: no cover
            pass # pragma: no cover
        else:
            self.metadata["Acquisition_instrument"]["Detector"][
                "integration_time"
            ] = integration_time

        ## convert filter range from percentage (0-100) to (0-1)
        try:
            self.metadata["Acquisition_instrument"]["Laser"]["Filter"][
                "optical_density"
            ] /= 100
        except KeyError: # pragma: no cover
            pass # pragma: no cover

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
        except KeyError: # pragma: no cover
            pass # pragma: no cover


def file_reader(filename, use_uniform_signal_axis=True, **kwds):
    """Reads a file with Jobin Yvon .xml-format.

    Parameters
    ----------
    use_uniform_signal_axis: bool, default=True
        Can be specified to choose between non-uniform or uniform signal-axis.
    """
    if not isinstance(filename, Path):
        filename = Path(filename)
    jy = JobinYvonXMLReader(
        file_path=filename, use_uniform_signal_axis=use_uniform_signal_axis
    )
    jy.parse_file()
    jy.get_original_metadata()
    jy.get_axes()
    jy.get_data()
    jy.map_metadata()
    dictionary = {
        "data": jy.data,
        "axes": jy.axes,
        "metadata": deepcopy(jy.metadata),
        "original_metadata": deepcopy(jy.original_metadata),
    }
    return [
        dictionary,
    ]
