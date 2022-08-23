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

import gc
import numpy as np
import pytest
from pathlib import Path
from copy import deepcopy

hs = pytest.importorskip("hyperspy.api", reason="hyperspy not installed")

testfile_dir = (Path(__file__).parent / "jobin_yvon_data").resolve()

testfile_spec_path = (testfile_dir / "jobinyvon_test_spec.xml").resolve()
testfile_linescan_path = (testfile_dir / "jobinyvon_test_linescan.xml").resolve()
testfile_map_path = (testfile_dir / "jobinyvon_test_map.xml").resolve()



class TestSpec:

    @classmethod
    def setup_class(cls):
        cls.s = hs.load(testfile_spec_path, reader="Jobin Yvon", use_uniform_wavelength_axis=True)
        cls.s_non_uniform = hs.load(testfile_spec_path, reader="Jobin Yvon", use_uniform_wavelength_axis=False)

    @classmethod
    def teardown_class(cls):
        del cls.s
        del cls.s_non_uniform
        gc.collect()

    def test_data(self):
        spec_data = [1496, 1242, 1094, 986, 948, 900, 858, 855, 840, 822, 824, 820, 810, 809, 791,
		    781, 771, 782, 795, 790, 777, 771, 769, 767, 756, 755, 759, 740, 743, 763,
		    759, 727, 764, 760]
        assert (spec_data == self.s.data.tolist())
        np.testing.assert_allclose(self.s.data, self.s_non_uniform.data)

    def test_axes(self):
        spec_axes = {'axis-0': {'_type': 'UniformDataAxis',
                                'name': 'Wavelength',
                                'units': 'nm',
                                'navigate': False,
                                'is_binned': False,
                                'size': 34,
                                'scale': 0.44809090909091015,
                                'offset': 522.574}}

        spec_axes_non_uniform = {'axis-0': {'_type': 'DataAxis',
                                            'name': 'Wavelength',
                                            'units': 'nm',
                                            'navigate': False,
                                            'is_binned': False}}

        non_uniform_axis_values = np.array([
            537.361, 536.918, 536.474, 536.031, 535.586, 535.142, 534.697,
            534.252, 533.807, 533.361, 532.915, 532.468, 532.022, 531.575,
            531.128, 530.68 , 530.232, 529.784, 529.336, 528.887, 528.438,
            527.988, 527.539, 527.089, 526.639, 526.188, 525.737, 525.286,
            524.835, 524.383, 523.931, 523.479, 523.027, 522.574])

        non_uniform_axis_manager = deepcopy(self.s_non_uniform.axes_manager.as_dictionary())

        np.testing.assert_allclose(non_uniform_axis_values, non_uniform_axis_manager["axis-0"].pop("axis"))
        assert (spec_axes == self.s.axes_manager.as_dictionary())
        assert (spec_axes_non_uniform == non_uniform_axis_manager)

    def test_original_metadata(self):
        spec_original_metadata = {'date': {
                'Acquired': '27.06.2022 16:26:24'
                },
            'experimental setup': {
                'Acq. time (s)': 1.0,
                'Accumulations': 2.0,
                'Range': 'Visible',
                'Autofocus': 'Off',
                'AutoExposure': 'Off',
                'Spike filter': 'Multiple accum.',
                'Delay time (s)': 0.0,
                'Binning': 30.0,
                'Readout mode': 'Signal',
                'DeNoise': 'Off',
                'ICS correction': 'Off',
                'Dark correction': 'Off',
                'Inst. Process': 'Off',
                'Detector temperature (°C)': -118.94,
                'Instrument': 'LabRAM HR Evol',
                'Detector': 'Symphony VIS',
                'Objective': 100.0,
                'Grating (gr/mm)': 1800.0,
                'ND Filter (%)': 10.0,
                'Laser (nm)': 632.817,
                'Spectro (nm)': 530.0006245,
                'Hole': 100.02125,
                'Laser Pol. (°)': 0.0,
                'Raman Pol. (°)': 0.0,
                'StageXY': 'Marzhauser',
                'StageZ': 'Marzhauser',
                'X (µm)': 0.0,
                'Y (µm)': 0.0,
                'Z (µm)': 0.0,
                'Full time(s)': 3.0,
                'measurement_type': 'Spectrum',
                'title': 'jobinyvon_test_spec',
                'signal type': 'Intens',
                'signal units': 'Cnt/sec'
                },
            'file information': {
                'Project': 'A',
                'Sample': 'test',
                'Site': 'C',
                'Title': 'ev21738_1',
                'Remark': 'PL',
                'Date': '27.06.2022 16:26'}}
        assert (spec_original_metadata == self.s.original_metadata.as_dictionary())
        assert (spec_original_metadata == self.s_non_uniform.original_metadata.as_dictionary())

    def test_metadata(self):
        metadata = deepcopy(self.s.metadata.as_dictionary())
        metadata_non_uniform = deepcopy(self.s_non_uniform.metadata.as_dictionary())
        assert metadata_non_uniform["General"]["FileIO"]["0"]["io_plugin"] == "rsciio.jobin_yvon.api"
        assert metadata["General"]["FileIO"]["0"]["io_plugin"] == "rsciio.jobin_yvon.api"
        assert metadata["General"]["date"] == "27.06.2022"
        assert metadata["General"]["original_filename"] == str(testfile_spec_path.name)
        assert metadata["General"]["time"] == "16:26:24"
        assert metadata["Signal"]["quantity"] == "Intensity (Counts/s)"
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Detector"]["binning"], 30)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Detector"]["exposure_per_frame (s)"], 1)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Detector"]["frames"], 2)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Detector"]["integration_time (s)"], 2)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Detector"]["temperature (°C)"], -118.94)
        assert metadata["Acquisition_instrument"]["Detector"]["model"] == "Symphony VIS"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["AutoExposure"] == "Off"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["Autofocus"] == "Off"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["Dark correction"] == "Off"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["DeNoise"] == "Off"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["ICS correction"] == "Off"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["Inst. Process"] == "Off"
        assert metadata["Acquisition_instrument"]["Detector"]["processing"]["Spike filter"] == "Multiple accum."
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Laser"]["objective_magnification"], 100)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Laser"]["wavelength (nm)"], 632.817)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Laser"]["Filter"]["optical_density"], 0.1)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Spectrometer"]["Grating"]["groove_density"], 1800)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Spectrometer"]["central_wavelength (nm)"], 530.0006245)
        np.testing.assert_allclose(metadata["Acquisition_instrument"]["Spectrometer"]["entrance_slit_width"], 100.02125)
        assert metadata["Acquisition_instrument"]["Spectrometer"]["model"] == "LabRAM HR Evol"
        assert metadata["Acquisition_instrument"]["Spectrometer"]["spectral_range"] == "Visible"

        ## remove FileIO for comparison (timestamp varies)
        ## plugin is already tested for both (above)
        del metadata["General"]["FileIO"]
        del metadata_non_uniform["General"]["FileIO"]

        assert (metadata == metadata_non_uniform)

class TestLinescan:

    @classmethod
    def setup_class(cls):
        cls.s = hs.load(testfile_linescan_path, reader="Jobin Yvon", use_uniform_wavelength_axis=True)
        cls.s_non_uniform = hs.load(testfile_linescan_path, reader="Jobin Yvon", use_uniform_wavelength_axis=False)

    @classmethod
    def teardown_class(cls):
        del cls.s
        del cls.s_non_uniform
        gc.collect()

    def test_data(self):
        linescan_row0 = [1614, 1317, 1140, 1035, 970, 931, 901, 868, 864, 845, 843, 847, 831, 834, 813,
		810, 807, 817, 807, 798, 800, 797, 788, 804, 767, 778, 778, 787, 775, 790,
		769, 778, 780, 783]
        linescan_row1 = [1509, 1251, 1087, 1002, 934, 896, 866, 830, 837, 831, 815, 792, 784, 811, 796,
		799, 794, 784, 788, 773, 780, 787, 797, 779, 780, 765, 770, 757, 758, 758,
		741, 769, 765, 775]
        linescan_row2 = [1546, 1292, 1124, 1020, 950, 901, 890, 865, 865, 847, 837, 824, 827, 808, 818,
		809, 810, 814, 798, 784, 790, 785, 771, 790, 786, 786, 773, 771, 772, 768,
		782, 762, 757, 781]
        assert (linescan_row0 == self.s.data.tolist()[0])
        assert (linescan_row1 == self.s.data.tolist()[1])
        assert (linescan_row2 == self.s.data.tolist()[2])
        np.testing.assert_allclose(self.s.data, self.s_non_uniform.data)

    def test_axes(self):
        linescan_axes = {'axis-0': {
                '_type': 'UniformDataAxis',
                'name': 'Y',
                'units': 'µm',
                'navigate': True,
                'is_binned': False,
                'size': 3,
                'scale': 0.5,
                'offset': 0.0
                },
            'axis-1': {
                '_type': 'UniformDataAxis',
                'name': 'Wavelength',
                'units': 'nm',
                'navigate': False,
                'is_binned': False,
                'size': 34,
                'scale': 0.44809090909091015,
                'offset': 522.574}}

        linescan_axes_non_uniform = {'axis-0': {
                '_type': 'UniformDataAxis',
                'name': 'Y',
                'units': 'µm',
                'navigate': True,
                'is_binned': False,
                'size': 3,
                'scale': 0.5,
                'offset': 0.0
            }, 
            'axis-1': {
                '_type': 'DataAxis',
                'name': 'Wavelength',
                'units': 'nm',
                'navigate': False,
                'is_binned': False,
            }}

        non_uniform_axis_values = np.array([
            537.361, 536.918, 536.474, 536.031, 535.586, 535.142, 534.697,
            534.252, 533.807, 533.361, 532.915, 532.468, 532.022, 531.575,
            531.128, 530.68 , 530.232, 529.784, 529.336, 528.887, 528.438,
            527.988, 527.539, 527.089, 526.639, 526.188, 525.737, 525.286,
            524.835, 524.383, 523.931, 523.479, 523.027, 522.574])

        non_uniform_axis_manager = deepcopy(self.s_non_uniform.axes_manager.as_dictionary())

        np.testing.assert_allclose(non_uniform_axis_values, non_uniform_axis_manager["axis-1"].pop("axis"))
        assert (linescan_axes_non_uniform == non_uniform_axis_manager)
        assert (linescan_axes == self.s.axes_manager.as_dictionary())

class TestMap:

    @classmethod
    def setup_class(cls):
        cls.s = hs.load(testfile_map_path, reader="Jobin Yvon", use_uniform_wavelength_axis=True)
        cls.s_non_uniform = hs.load(testfile_map_path, reader="Jobin Yvon", use_uniform_wavelength_axis=False)

    @classmethod
    def teardown_class(cls):
        del cls.s
        del cls.s_non_uniform
        gc.collect()

    def test_data(self):
        map_row0 = [1570, 1287, 1145, 1020, 987, 921, 905, 866, 871, 847, 866, 841, 859, 838, 832,
		834, 817, 832, 808, 807, 798, 824, 814, 817, 797, 812, 804, 802, 798, 803,
		788, 814, 801, 798]
        map_row1 = [1645, 1342, 1180, 1067, 996, 936, 916, 884, 859, 878, 855, 869, 820, 852, 827,
		829, 823, 814, 823, 814, 813, 795, 786, 799, 790, 793, 794, 788, 808, 780,
		800, 777, 776, 787]
        map_row2 = [1626, 1351, 1166, 1049, 988, 969, 892, 883, 873, 856, 841, 852, 842, 839, 849,
		820, 800, 832, 817, 819, 825, 796, 828, 799, 820, 818, 799, 807, 787, 790,
		797, 768, 791, 784]
        map_row3 = [1655, 1380, 1194, 1090, 1019, 982, 948, 932, 911, 900, 883, 878, 851, 866, 852,
		875, 860, 849, 858, 829, 840, 856, 861, 844, 838, 794, 797, 771, 791, 783,
		788, 795, 777, 775]
        map_row4 = [1555, 1314, 1146, 1039, 959, 911, 898, 886, 870, 855, 848, 844, 841, 829, 824,
		821, 816, 826, 792, 800, 805, 819, 814, 798, 787, 800, 789, 789, 786, 789,
		795, 781, 783, 776]
        map_row5 = [1640, 1343, 1181, 1052, 984, 948, 917, 896, 892, 862, 853, 858, 843, 839, 834,
		831, 819, 811, 816, 828, 807, 809, 810, 806, 806, 818, 800, 799, 780, 781,
		775, 795, 781, 788]
        map_row6 = [1620, 1296, 1143, 1064, 974, 947, 905, 899, 866, 849, 836, 844, 839, 843, 831,
		844, 835, 835, 833, 812, 804, 814, 813, 801, 823, 786, 796, 797, 794, 784,
		809, 777, 768, 797]
        map_row7 = [1614, 1324, 1162, 1057, 981, 956, 906, 894, 858, 875, 857, 860, 846, 841, 847,
		822, 843, 835, 829, 815, 812, 804, 814, 812, 809, 807, 804, 792, 801, 789,
		793, 790, 777, 788]
        map_row8 = [1629, 1362, 1171, 1069, 1008, 947, 931, 896, 877, 872, 866, 867, 873, 844, 853,
		847, 847, 822, 837, 817, 823, 818, 809, 827, 823, 792, 817, 818, 801, 801,
		794, 787, 783, 796]
        assert (map_row0 == self.s.data.tolist()[0][0])
        assert (map_row1 == self.s.data.tolist()[0][1])
        assert (map_row2 == self.s.data.tolist()[0][2])
        assert (map_row3 == self.s.data.tolist()[1][0])
        assert (map_row4 == self.s.data.tolist()[1][1])
        assert (map_row5 == self.s.data.tolist()[1][2])
        assert (map_row6 == self.s.data.tolist()[2][0])
        assert (map_row7 == self.s.data.tolist()[2][1])
        assert (map_row8 == self.s.data.tolist()[2][2])
        np.testing.assert_allclose(self.s.data, self.s_non_uniform.data)

    def test_axes(self):
        map_axes = {'axis-0': {
                '_type': 'UniformDataAxis',
                'name': 'Y',
                'units': 'µm',
                'navigate': True,
                'is_binned': False,
                'size': 3,
                'scale': 0.5,
                'offset': 0.0
                },
            'axis-1': {
                '_type': 'UniformDataAxis',
                'name': 'X',
                'units': 'µm',
                'navigate': True,
                'is_binned': False,
                'size': 3,
                'scale': 0.5,
                'offset': 0.0
                },
            'axis-2': {
                '_type': 'UniformDataAxis',
                'name': 'Wavelength',
                'units': 'nm',
                'navigate': False,
                'is_binned': False,
                'size': 34,
                'scale': 0.44809090909091015,
                'offset': 522.574}}

        map_axes_non_uniform = {'axis-0': {
                '_type': 'UniformDataAxis',
                'name': 'Y',
                'units': 'µm',
                'navigate': True,
                'is_binned': False,
                'size': 3,
                'scale': 0.5,
                'offset': 0.0
                },
            'axis-1': {
                '_type': 'UniformDataAxis',
                'name': 'X',
                'units': 'µm',
                'navigate': True,
                'is_binned': False,
                'size': 3,
                'scale': 0.5,
                'offset': 0.0
                },
            'axis-2': {
                '_type': 'DataAxis',
                'name': 'Wavelength',
                'units': 'nm',
                'navigate': False,
                'is_binned': False,
            }}

        non_uniform_axis_values = np.array([
            537.361, 536.918, 536.474, 536.031, 535.586, 535.142, 534.697,
            534.252, 533.807, 533.361, 532.915, 532.468, 532.022, 531.575,
            531.128, 530.68 , 530.232, 529.784, 529.336, 528.887, 528.438,
            527.988, 527.539, 527.089, 526.639, 526.188, 525.737, 525.286,
            524.835, 524.383, 523.931, 523.479, 523.027, 522.574])

        non_uniform_axis_manager = deepcopy(self.s_non_uniform.axes_manager.as_dictionary())

        np.testing.assert_allclose(non_uniform_axis_values, non_uniform_axis_manager["axis-2"].pop("axis"))
        assert (map_axes_non_uniform == non_uniform_axis_manager)
        assert (map_axes == self.s.axes_manager.as_dictionary())