#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Generate iTerm2 colors from an image.

Original Script: https://gist.github.com/radiosilence/3946121
"""

import collections
import colorsys
import argparse
import os

from colorz import colorz


HOME = os.path.expanduser("~")
THEME = HOME + "/Library/Application Support/iTerm2/DynamicProfiles/theme.json"

JSON_BEFORE = """
{{
  "Profiles": [{{
    "Name": "Default.Profile.Theme",
    "Guid": "Default.Profile.Theme",
    "Dynamic Profile Parent Name": "{}",

    "Only The Default BG Color Uses Transparency" : false,
    "Transparency" : {},

    "Background Image Location": "{}",
    "Background Image Is Tiled": {},
    "Minimum Contrast": {},
    "Blend": {},
"""
JSON_AFTER = """
  }]
}
"""
JSON_COLOR_ANSI = """
    "Ansi {} Color": {{
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""
JSON_COLOR_NAMED = """
    "{} Color": {{
      "Color Space" : "Calibrated",
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""

COLOR_BLACK = 0
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_YELLOW = 3
COLOR_BLUE = 4
COLOR_MAGENTA = 5
COLOR_CYAN = 6
COLOR_WHITE = 7

def clamp(value, minv, maxv):
  if value < minv:
    return minv
  if value > maxv:
    return maxv
  return value

def clamp_hsv(rgb, minh=0.0, maxh=1.0, mins=0.0, maxs=1.0, minv=0.0, maxv=1.0):
  hue, sat, val = colorsys.rgb_to_hsv(*rgb)

  hue = clamp(hue, minh, maxh)
  sat = clamp(sat, mins, maxs)
  val = clamp(val, minv, maxv)

  return colorsys.hsv_to_rgb(hue, sat, val)

def to_json_bool(value):
  return 'true' if value else 'false'


def generate(options):

  image = os.path.abspath(options.image)

  json_before = JSON_BEFORE.format(
      options.parent, options.transparency,
      "" if options.no_background else image,
      to_json_bool(options.tiled),
      options.contrast, options.blend)

  json = ""

  colors = collections.deque(colorz(image, n=8))

  colors.rotate(options.rotate)

  if options.reversed:
    colors = reversed(colors)

  for i, (normal, bright) in zip(range(8), colors):
    if options.inverted:
      normal = [256 - x for x in normal]
      bright = [256 - x for x in bright]

    normal = [x / 256.0 for x in normal]
    bright = [x / 256.0 for x in bright]

    if i == COLOR_WHITE:
      normal = clamp_hsv(normal, mins=0.0, maxs=0.12, minv=0.78, maxv=0.86)
      bright = clamp_hsv(bright, mins=0.0, maxs=0.19, minv=0.86, maxv=1.00)

    if i == COLOR_BLACK:
      normal = clamp_hsv(normal, mins=0.0, maxs=0.08, minv=0.08, maxv=0.12)
      bright = clamp_hsv(bright, mins=0.0, maxs=0.16, minv=0.08, maxv=0.23)

    normal = clamp_hsv(
        normal,
        mins=options.saturation_min, maxs=options.saturation_max,
        minv=options.brightness_min, maxv=options.brightness_max)
    bright = clamp_hsv(
        bright,
        mins=options.saturation_min, maxs=options.saturation_max,
        minv=options.brightness_min, maxv=options.brightness_max)

    if i == COLOR_WHITE:
      colors = clamp_hsv(normal, mins=0.12, maxs=0.16, minv=0.58, maxv=0.63)
      json += JSON_COLOR_NAMED.format("Foreground", *colors)

    if i == COLOR_BLACK:
      colors = clamp_hsv(normal, mins=0.0, maxs=0.1, minv=0.04, maxv=0.06)
      json += JSON_COLOR_NAMED.format("Background", *colors)

      colors = clamp_hsv(normal, mins=0.0, maxs=0.1, minv=0.06, maxv=0.10)
      json += JSON_COLOR_NAMED.format("Selected Text", *colors)

    if i == COLOR_BLUE:
      json += JSON_COLOR_NAMED.format("Selection", *normal)

    if i == COLOR_CYAN:
      json += JSON_COLOR_NAMED.format("Link", *normal)

    if i == COLOR_MAGENTA:
      colors = clamp_hsv(normal, mins=0.60, minv=0.80, maxv=0.90)
      json += JSON_COLOR_NAMED.format("Bold", *colors)

    json += JSON_COLOR_ANSI.format(i, *normal)
    json += JSON_COLOR_ANSI.format(i + 8, *bright)

  with open(options.out, 'w') as theme:
    theme.write(json_before)
    theme.write(json[:-2])
    theme.write(JSON_AFTER)

def main():
  parser = argparse.ArgumentParser(
      prog='iTerm2 Theme Generator',
      description='Generate iTerm2 color scheme based on an image')

  parser.add_argument('image', metavar='IMAGE', help="Image to process")

  parser.add_argument(
      '--parent', dest='parent', metavar='PROFILE', default="Default.Profile",
      help="Profile this theme will inherit. Default: 'Default.Profile'")

  parser.add_argument(
      '--out', dest='out', metavar='FILE', default=THEME,
      help="Output file. Default: {}".format(THEME))

  parser.add_argument(
      '--tiled', dest='tiled', metavar='TILED', type=bool, default=False,
      help="Tile the image. Default: False")

  parser.add_argument(
      '--blend', dest='blend', metavar='BLEND', type=float, default=0.10,
      help="Blend(0.0-1.0). Default: 0.10")

  parser.add_argument(
      '--transparency', dest='transparency', metavar='VALUE',
      type=float, default=0.0, help="Transparency(0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--contrast', dest='contrast', metavar='CONTRAST', type=float,
      default=0.0, help="Contrast(0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--saturation-min', dest='saturation_min', metavar='MIN', type=float,
      default=0.0, help="Minimal saturation(0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--saturation-max', dest='saturation_max', metavar='MAX', type=float,
      default=1.0, help="Maximal saturation(0.0-1.0). Default: 1.0")

  parser.add_argument(
      '--brightness-min', dest='brightness_min', metavar='MIN', type=float,
      default=0.0, help="Minimal brightness(0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--brightness-max', dest='brightness_max', metavar='MAX', type=float,
      default=1.0, help="Maximal brightness(0.0-1.0). Default: 1.0")

  parser.add_argument(
      '--rotate', dest='rotate', metavar='TIMES', type=int, default=0,
      choices=[0, 1, 2, 3, 4, 5, 6, 7],
      help="Rotate colors order N times(0-7). Default: 0")

  parser.add_argument(
      '--inverted', dest='inverted', action='store_true', default=False,
      help="Invert colors. Default: No")

  parser.add_argument(
      '--reversed', dest='reversed', action='store_true', default=False,
      help="Reverse colors order. Default: No")

  parser.add_argument(
      '--no-background', dest='no_background', action='store_true', default=False,
      help="Disable background image. Useful if using transparency.")

  generate(parser.parse_args())

if __name__ == "__main__":
  main()
