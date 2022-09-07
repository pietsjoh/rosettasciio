.. _jobin-yvon-format:

Jobin Yvon
----------

Currently, RosettaSciIO can only read ``.xml`` format from Jobin-Yvon.
If lumispy is installed, then LumiSpectrum will be used as the signal_type.


.. code-block:: python

    >>> sig = hs.load("file.xml", reader="JobinYvon")

Specifying the reader is necessary as :ref:`EMPAD <empad-format>`
also uses the .xml file-extension.

Extra loading arguments
^^^^^^^^^^^^^^^^^^^^^^^

- ``use_uniform_wavelength_axis``: bool, default is True. This option decides whether to use an
  uniform or non-uniform data axis for the signal. In the former case, only offset and scale are saved.
  Otherwise all data points from this axis are used.
  A warning message is printed when the difference between the first 2
  and last 2 wavelengths differ (when set to True).
