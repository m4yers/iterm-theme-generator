======================
iTerm2 Theme Generator
======================

.. image:: https://img.shields.io/pypi/status/iterm-theme-generator.svg
   :target: https://pypi.python.org/pypi/iterm-theme-generator
   :alt: PyPi Status

.. image:: https://img.shields.io/pypi/v/iterm-theme-generator.svg
   :target: https://pypi.python.org/pypi/iterm-theme-generator
   :alt: PyPi Version

.. image:: https://img.shields.io/pypi/pyversions/iterm-theme-generator.svg
   :target: https://pypi.python.org/pypi/iterm-theme-generator
   :alt: Python Versions

This theme generator will produce a color set for iTerm2 from an image.

.. image:: https://i.imgur.com/iQWsYmG.png

Check out the gallery_

.. contents::

Installation
============

From pip::

  $pip install --upgrade iterm-theme-generator


Usage
=====

To generate a color set from an image::

  $ iterm_theme_generator <path-to-image> --parent <your-profile>


This will generate colors and create iTerm2 profile in its DynamicProfiles
directory. This theme profile will inherit profile you mention with `--parent`
option. Go to the profiles tab and select this new profile as default and
restart iTerm. Now, when you change theme again iTerm will load it dynamically,
so no need to restart again.

Options::

  usage: iTerm2 Theme Generator [-h] [--parent PROFILE] [--out FILE]
                                [--tiled TILED] [--blend BLEND]
                                [--transparency VALUE] [--contrast CONTRAST]
                                [--saturation-min MIN] [--saturation-max MAX]
                                [--brightness-min MIN] [--brightness-max MAX]
                                [--rotate TIMES] [--inverted] [--reversed]
                                [--no-background]
                                IMAGE

  Generate iTerm2 color scheme based on an image

  positional arguments:
    IMAGE                 Image to process

  optional arguments:
    -h, --help            show this help message and exit
    --parent PROFILE      Profile this theme will inherit. Default:
                          'Default.Profile'
    --out FILE            Output file. Default:
                          /Users/m4yers/Library/Application
                          Support/iTerm2/DynamicProfiles/theme.json
    --tiled TILED         Tile the image. Default: False
    --blend BLEND         Blend(0.0-1.0). Default: 0.10
    --transparency VALUE  Transparency(0.0-1.0). Default: 0.0
    --contrast CONTRAST   Contrast(0.0-1.0). Default: 0.0
    --saturation-min MIN  Minimal saturation(0.0-1.0). Default: 0.0
    --saturation-max MAX  Maximal saturation(0.0-1.0). Default: 1.0
    --brightness-min MIN  Minimal brightness(0.0-1.0). Default: 0.0
    --brightness-max MAX  Maximal brightness(0.0-1.0). Default: 1.0
    --rotate TIMES        Rotate colors order N times(0-7). Default: 0
    --inverted            Invert colors. Default: No
    --reversed            Reverse colors order. Default: No
    --no-background       Disable background image. Useful if using
                          transparency.

Features
========

Some iTerm features are exposed through the generator such as `tiling`,
`blending`, `contrast`.

The generator provides rudimentary color control, including:

* saturation min/max bound
* brightness min/max bound
* rotation and reversion of the generated color set
* color inversion

Using these features will allow you to capture an awesome color set that will
fit your background image neatly.


Thanks To
=========

* radiosilence_ for the original script
* metakirby5_ for colorz util


Links
=====

* PyPI_
* GitHub_

.. _PyPI: https://pypi.python.org/pypi/iterm-theme-generator/
.. _GitHub: https://github.com/m4yers/iterm-theme-generator
.. _radiosilence: https://gist.github.com/radiosilence/3946121
.. _metakirby5: https://github.com/metakirby5/colorz
.. _gallery: https://imgur.com/a/DCoDU
