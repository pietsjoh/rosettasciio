# -*- coding: utf-8 -*-
# Copyright 2007-2023 The HyperSpy developers
#
# This file is part of RosettaSciIO.
#
# RosettaSciIO is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RosettaSciIO is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with RosettaSciIO. If not, see <https://www.gnu.org/licenses/#GPL>.

import logging
from packaging.version import Version
from pathlib import Path

import dask.array as da
import h5py

from rsciio._docstrings import (
    CHUNKS_DOC,
    COMPRESSION_HDF5_DOC,
    COMPRESSION_HDF5_NOTES_DOC,
    FILENAME_DOC,
    LAZY_DOC,
    RETURNS_DOC,
    SIGNAL_DOC,
)
from rsciio._hierarchical import HierarchicalWriter, HierarchicalReader, version
from rsciio.utils.tools import get_file_handle


_logger = logging.getLogger(__name__)

not_valid_format = "The file is not a valid HyperSpy hdf5 file"

current_file_version = None  # Format version of the file being read
default_version = Version(version)


class HyperspyReader(HierarchicalReader):
    _file_type = "hspy"

    def __init__(self, file):
        super().__init__(file)
        self.Dataset = h5py.Dataset
        self.Group = h5py.Group
        self.unicode_kwds = {"dtype": h5py.special_dtype(vlen=str)}


class HyperspyWriter(HierarchicalWriter):
    """
    An object used to simplify and organize the process for
    writing a hyperspy signal.  (.hspy format)
    """

    target_size = 1e6

    def __init__(self, file, signal, expg, **kwds):
        super().__init__(file, signal, expg, **kwds)
        self.Dataset = h5py.Dataset
        self.Group = h5py.Group
        self.unicode_kwds = {"dtype": h5py.special_dtype(vlen=str)}
        self.ragged_kwds = {"dtype": h5py.special_dtype(vlen=signal["data"][0].dtype)}

    @staticmethod
    def _store_data(data, dset, group, key, chunks):
        if isinstance(data, da.Array):
            if data.chunks != dset.chunks:
                data = data.rechunk(dset.chunks)
            da.store(data, dset)
        elif data.flags.c_contiguous:
            dset.write_direct(data)
        else:
            dset[:] = data

    @staticmethod
    def _get_object_dset(group, data, key, chunks, **kwds):
        """Creates a h5py dataset object for saving ragged data"""
        # For saving ragged array
        if chunks is None:
            chunks = 1
        dset = group.require_dataset(
            key, chunks, dtype=h5py.special_dtype(vlen=data[0].dtype), **kwds
        )
        return dset


def file_reader(filename, lazy=False, **kwds):
    """
    Read data from hdf5-files saved with the HyperSpy hdf5-format
    specification (``.hspy``).

    Parameters
    ----------
    %s
    %s
    **kwds : dict, optional
        The keyword arguments are passed to :py:class:`h5py.File`.

    %s
    """
    try:
        # in case blosc compression is used
        import hdf5plugin
    except ImportError:
        pass
    mode = kwds.pop("mode", "r")
    f = h5py.File(filename, mode=mode, **kwds)

    reader = HyperspyReader(f)
    exp_dict_list = reader.read(lazy=lazy)
    if not lazy:
        f.close()

    return exp_dict_list


file_reader.__doc__ %= (FILENAME_DOC, LAZY_DOC, RETURNS_DOC)


def file_writer(
    filename,
    signal,
    chunks=None,
    compression="gzip",
    close_file=True,
    write_dataset=True,
    **kwds,
):
    """
    Write data to HyperSpy's hdf5-format (``.hspy``).

    Parameters
    ----------
    %s
    %s
    %s
    %s
    close_file : bool, default=True
        Close the file after writing.  The file should not be closed if the data
        needs to be accessed lazily after saving.
    write_dataset : bool, default=True
        If True, write the dataset, otherwise, don't write it. Useful to
        overwrite attributes (for example ``axes_manager``) only without having
        to write the whole dataset.
    **kwds
        The keyword argument are passed to the
        :external+h5py:meth:`h5py.Group.require_dataset` function.

    Notes
    -----
    %s
    """
    if not isinstance(write_dataset, bool):
        raise ValueError("`write_dataset` argument has to be a boolean.")

    if "shuffle" not in kwds:
        # Use shuffle by default to improve compression
        kwds["shuffle"] = True

    folder = signal["tmp_parameters"].get("original_folder", "")
    fname = signal["tmp_parameters"].get("original_filename", "")
    ext = signal["tmp_parameters"].get("original_extension", "")
    original_path = Path(folder, f"{fname}.{ext}")

    f = None
    if signal["attributes"]["_lazy"] and Path(filename).absolute() == original_path:
        f = get_file_handle(signal["data"], warn=False)
        if f is not None and f.mode == "r":
            # when the file is read only, force to reopen it in writing mode
            raise OSError(
                "File opened in read only mode. To overwrite file "
                "with lazy signal, use `mode='a'` when loading the "
                "signal."
            )

    if f is None:
        # with "write_dataset=False", we need mode='a', otherwise the dataset
        # will be flushed with using 'w' mode
        mode = kwds.get("mode", "w" if write_dataset else "a")
        if mode != "a" and not write_dataset:
            raise ValueError("`mode='a'` is required to use " "`write_dataset=False`.")
        f = h5py.File(filename, mode=mode)

    f.attrs["file_format"] = "HyperSpy"
    f.attrs["file_format_version"] = version
    exps = f.require_group("Experiments")
    title = signal["metadata"]["General"]["title"]
    group_name = title if title else "__unnamed__"
    # / is a invalid character, see https://github.com/hyperspy/hyperspy/issues/942
    if "/" in group_name:
        group_name = group_name.replace("/", "-")
    expg = exps.require_group(group_name)

    writer = HyperspyWriter(
        f,
        signal,
        expg,
        chunks=chunks,
        compression=compression,
        write_dataset=write_dataset,
        **kwds,
    )
    writer.write()

    if close_file:
        f.close()


file_writer.__doc__ %= (
    FILENAME_DOC.replace("read", "write to"),
    SIGNAL_DOC,
    CHUNKS_DOC,
    COMPRESSION_HDF5_DOC,
    COMPRESSION_HDF5_NOTES_DOC,
)


overwrite_dataset = HyperspyWriter.overwrite_dataset
