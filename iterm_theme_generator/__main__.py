#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""CLI entry point for iterm-theme-generator.

Parses command-line arguments and dispatches to the two output generators:

  1. iterm.generate()      — always runs, produces an iTerm2 DynamicProfile
  2. vim.generate_vim()    — runs only if --vim-out is specified

Architecture:
  __main__.py  (this file)  — CLI parsing, orchestration
  colors.py                 — image → 8-color palette extraction, color math
  iterm.py                  — palette → iTerm2 DynamicProfile JSON
  vim.py                    — palette → Vim colorscheme (.vim file)

Original Script: https://gist.github.com/radiosilence/3946121
"""

import argparse

from .iterm import generate, THEME
from .vim import generate_vim


def main():
  """Parse CLI arguments and run the theme generators.

  The argument namespace is passed directly to generate() and
  generate_vim(), which forward it to extract_colors().  This means
  every color-tuning flag (--sat-boost, --val-cap, etc.) flows through
  to the extraction pipeline without any intermediate translation.
  """
  parser = argparse.ArgumentParser(
      prog='iTerm2 Theme Generator',
      description='Generate iTerm2 color scheme based on an image')

  # -- Positional: source image -----------------------------------------
  parser.add_argument('image', metavar='IMAGE', help="Image to process")

  # -- Output options ---------------------------------------------------
  parser.add_argument(
      '--parent', dest='parent', metavar='PROFILE', default="Default.Profile",
      help="Profile this theme will inherit. Default: 'Default.Profile'")

  parser.add_argument(
      '--out', dest='out', metavar='FILE', default=THEME,
      help="Output file. Default: {}".format(THEME))

  parser.add_argument(
      '--vim-out', dest='vim_out', metavar='FILE', default=None,
      help="If set, also generate a Vim colorscheme at this path (e.g. ~/.vim/colors/terminal.vim)")

  parser.add_argument(
      '--vim-plugins', dest='vim_plugins', metavar='PLUGIN', nargs='*', default=['airline', 'nerdtree', 'vim-markdown'],
      help="Vim plugins to generate theme files for (e.g. airline nerdtree vim-markdown). Default: airline nerdtree vim-markdown")

  # -- iTerm2 display settings ------------------------------------------
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
      '--no-background', dest='no_background', action='store_true', default=False,
      help="Disable background image. Useful if using transparency.")

  parser.add_argument(
      '--vim-no-bg', dest='vim_no_bg', action='store_true', default=False,
      help="Disable background color in Vim theme (use terminal background instead)")

  # -- Color tuning: chromatic boost/cap --------------------------------
  # These control how extracted colors are "vivified" before use.
  # Min/max clamp the HSV component, then boost is added on top.
  parser.add_argument(
      '--vibrancy', dest='vibrancy', metavar='VALUE', type=float, default=0.0,
      help="Overall color vibrancy (0.0-1.0). Raises contrast and brightness of all colors. Default: 0.0")

  parser.add_argument(
      '--sat-min', dest='sat_min', metavar='VALUE', type=float, default=0.0,
      help="Saturation floor for chromatic colors (0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--sat-max', dest='sat_max', metavar='VALUE', type=float, default=1.0,
      help="Saturation ceiling for chromatic colors (0.0-1.0). Default: 1.0")

  parser.add_argument(
      '--sat-boost', dest='sat_boost', metavar='VALUE', type=float, default=0.08,
      help="Saturation boost applied after min/max clamp (0.0-1.0). Default: 0.08")

  parser.add_argument(
      '--val-min', dest='val_min', metavar='VALUE', type=float, default=0.0,
      help="Brightness floor for chromatic colors (0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--val-max', dest='val_max', metavar='VALUE', type=float, default=0.65,
      help="Brightness ceiling for chromatic colors, prevents neon (0.0-1.0). Default: 0.65")

  parser.add_argument(
      '--val-boost', dest='val_boost', metavar='VALUE', type=float, default=0.2,
      help="Brightness boost applied after min/max clamp (0.0-1.0). Default: 0.2")

  parser.add_argument(
      '--hue-min', dest='hue_min', metavar='VALUE', type=float, default=0.0,
      help="Hue floor for chromatic colors (0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--hue-max', dest='hue_max', metavar='VALUE', type=float, default=1.0,
      help="Hue ceiling for chromatic colors (0.0-1.0). Default: 1.0")

  parser.add_argument(
      '--hue-boost', dest='hue_boost', metavar='VALUE', type=float, default=0.0,
      help="Hue rotation applied after min/max clamp (0.0-1.0). Default: 0.0")

  # -- Color tuning: bright variant derivation --------------------------
  # Bright variants (ANSI 8–15) are derived from normal colors by
  # reducing saturation and boosting brightness.
  parser.add_argument(
      '--bold-as-bright', dest='bold_as_bright', action='store_true', default=False,
      help="Use a distinct bright color for bold text instead of the normal foreground color. Default: No")

  parser.add_argument(
      '--bright-sat-drop', dest='bright_sat_drop', metavar='VALUE', type=float, default=0.1,
      help="Saturation reduction for bright variants (0.0-1.0). Default: 0.1")

  parser.add_argument(
      '--bright-val-boost', dest='bright_val_boost', metavar='VALUE', type=float, default=0.15,
      help="Brightness boost for bright variants (0.0-1.0). Default: 0.15")

  # -- Palette manipulation ---------------------------------------------
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
      '--print-colors', dest='print_colors', action='store_true', default=False,
      help="Print semantic color values and exit.")

  options = parser.parse_args()

  if options.print_colors:
    import colorsys
    from .colors import extract_colors, to_hex
    _, sem, raw = extract_colors(options)
    print(f"  {'name':12s}  {'hex':8s}  {'H':>5s}  {'S':>5s}  {'V':>5s}  before  after")
    print(f"  {'─'*12}  {'─'*8}  {'─'*5}  {'─'*5}  {'─'*5}  {'─'*6}  {'─'*5}")
    for name, rgb in sorted(sem.items()):
      h, s, v = colorsys.rgb_to_hsv(*rgb)
      r, g, b = (int(x * 255) for x in rgb)
      after = f"\033[48;2;{r};{g};{b}m      \033[0m"
      rb = raw[name]
      rr, rg, rbv = (int(x * 255) for x in rb)
      before = f"\033[48;2;{rr};{rg};{rbv}m      \033[0m"
      print(f"  {name:12s}  {to_hex(rgb)}  {h:5.2f}  {s:5.2f}  {v:5.2f}  {before}  {after}")

  # Always generate the iTerm2 profile
  generate(options)

  # Optionally generate a Vim colorscheme if --vim-out was provided
  if options.vim_out:
    generate_vim(options)

if __name__ == "__main__":
  main()
