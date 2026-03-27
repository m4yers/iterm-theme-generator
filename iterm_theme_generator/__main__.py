#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate iTerm2 colors from an image.

Original Script: https://gist.github.com/radiosilence/3946121
"""

import collections
import colorsys
import argparse
import os

from PIL import Image
from sklearn.cluster import KMeans


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
  """Clamp value to [minv, maxv]."""
  return max(minv, min(maxv, value))

def clamp_hsv(rgb, minh=0.0, maxh=1.0, mins=0.0, maxs=1.0, minv=0.0, maxv=1.0):
  """Clamp each HSV component of an RGB color to the given ranges."""
  hue, sat, val = colorsys.rgb_to_hsv(*rgb)
  hue = clamp(hue, minh, maxh)
  sat = clamp(sat, mins, maxs)
  val = clamp(val, minv, maxv)
  return colorsys.hsv_to_rgb(hue, sat, val)

def to_json_bool(value):
  return 'true' if value else 'false'

def to_hex(rgb):
  """Convert an RGB tuple (0.0-1.0) to a CSS hex string."""
  return "#{:02x}{:02x}{:02x}".format(*(int(x * 255) for x in rgb))

def to_256(rgb):
  """Map an RGB tuple (0.0-1.0) to the nearest xterm-256 color index."""
  r, g, b = (int(x * 255) for x in rgb)
  if r == g == b:
    if r < 8: return 16
    if r > 248: return 231
    return round((r - 8) / 247 * 24) + 232
  return 16 + 36 * round(r / 255 * 5) + 6 * round(g / 255 * 5) + round(b / 255 * 5)

def relative_luminance(rgb):
  """Return WCAG relative luminance of an RGB tuple (0.0-1.0)."""
  def f(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
  r, g, b = (f(x) for x in rgb)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(a, b):
  """Return WCAG contrast ratio between two RGB colors (1.0-21.0)."""
  la, lb = relative_luminance(a), relative_luminance(b)
  bright, dark = max(la, lb), min(la, lb)
  return (bright + 0.05) / (dark + 0.05)

def ensure_contrast(fg, bg, min_ratio=3.0):
  """Nudge fg brightness up (and saturation slightly down) until contrast ratio is met.

  Adjusting both v and s keeps the color vivid rather than washing it out
  with brightness alone.
  """
  if contrast_ratio(fg, bg) >= min_ratio:
    return fg
  h, s, v = colorsys.rgb_to_hsv(*fg)
  step = 0.01 if relative_luminance(bg) < 0.5 else -0.01
  for _ in range(100):
    v = clamp(v + step, 0.0, 1.0)
    s = clamp(s - abs(step) * 0.1, 0.0, 1.0)
    fg = colorsys.hsv_to_rgb(h, s, v)
    if contrast_ratio(fg, bg) >= min_ratio:
      break
  return fg


def rgb_to_lab(rgb):
  """Convert sRGB (0.0-1.0) to CIE L*a*b* via XYZ D65."""
  def f(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
  r, g, b = f(rgb[0]), f(rgb[1]), f(rgb[2])
  x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
  y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.00000
  z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883
  def ft(t): return t ** (1/3) if t > 0.008856 else 7.787 * t + 16/116
  return [116 * ft(y) - 16, 500 * (ft(x) - ft(y)), 200 * (ft(y) - ft(z))]

def extract_colors(options):
  """Extract an 8-color palette from the wallpaper image.

  Uses k-means clustering in perceptual LAB color space (16 clusters) for
  better color separation than RGB-space clustering. Clusters are then
  assigned to ANSI color roles by hue proximity rather than extraction order,
  so red always maps to the reddest cluster, blue to the bluest, etc.

  Returns a list of 8 (normal, bright) RGB tuples in ANSI order:
    [BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE]
  """
  img = Image.open(os.path.abspath(options.image)).convert("RGB")
  img.thumbnail((200, 200))
  pixels = [[r/255, g/255, b/255] for r, g, b in img.getdata()]
  lab_pixels = [rgb_to_lab(p) for p in pixels]

  km = KMeans(n_clusters=16, n_init=10, random_state=0)
  km.fit(lab_pixels)

  def lab_to_rgb(lab):
    """Convert CIE L*a*b* back to sRGB (0.0-1.0)."""
    L, a, b = lab
    fy = (L + 16) / 116
    fx = a / 500 + fy
    fz = fy - b / 200
    def ft(t): return t**3 if t**3 > 0.008856 else (t - 16/116) / 7.787
    x, y, z = ft(fx) * 0.95047, ft(fy), ft(fz) * 1.08883
    r =  x * 3.2406 + y * -1.5372 + z * -0.4986
    g =  x * -0.9689 + y * 1.8758 + z * 0.0415
    b =  x * 0.0557 + y * -0.2040 + z * 1.0570
    def gc(c): return max(0, min(1, 1.055 * c**(1/2.4) - 0.055 if c > 0.0031308 else 12.92 * c))
    return [gc(r), gc(g), gc(b)]

  centers = sorted([lab_to_rgb(c) for c in km.cluster_centers_],
                   key=lambda c: relative_luminance(c))

  # Darkest cluster → BLACK, brightest → WHITE, rest assigned by hue
  black  = centers[0]
  white  = centers[-1]
  others = centers[1:-1]

  # Target hues (HSV 0.0-1.0) for each chromatic ANSI slot
  TARGET_HUES = {
    COLOR_RED:     0.0,
    COLOR_YELLOW:  1/6,
    COLOR_GREEN:   1/3,
    COLOR_CYAN:    0.5,
    COLOR_BLUE:    2/3,
    COLOR_MAGENTA: 5/6,
  }

  def hue_distance(a, b):
    """Circular distance between two hue values (0.0-1.0)."""
    d = abs(a - b)
    return min(d, 1 - d)

  def assign_by_hue(candidates, targets):
    """Greedy assignment: match each target hue to its nearest unused candidate."""
    remaining = list(candidates)
    assigned = {}
    for slot, target_hue in sorted(targets.items(), key=lambda x: x[0]):
      if not remaining:
        break
      best = min(remaining, key=lambda c: hue_distance(colorsys.rgb_to_hsv(*c)[0], target_hue))
      assigned[slot] = best
      remaining.remove(best)
    return assigned

  assigned = assign_by_hue(others, TARGET_HUES)

  def vivify(c):
    """Apply hue/sat/val boost+cap to a chromatic color."""
    h, s, v = colorsys.rgb_to_hsv(*c)
    return colorsys.hsv_to_rgb(
        clamp(min(h, options.hue_cap) + options.hue_boost, 0.0, 1.0),
        clamp(min(s, options.sat_cap) + options.sat_boost, 0.0, 1.0),
        clamp(min(v, options.val_cap) + options.val_boost, 0.0, 1.0))

  def make_bright(c):
    """Derive a bright variant by applying bright_sat_drop and bright_val_boost."""
    h, s, v = colorsys.rgb_to_hsv(*c)
    return colorsys.hsv_to_rgb(h, max(0, s - options.bright_sat_drop), min(1, v + options.bright_val_boost))

  result_map = {
    COLOR_BLACK: (black, make_bright(black)),
    COLOR_WHITE: (white, make_bright(white)),
  }
  for slot, color in assigned.items():
    color = vivify(color)
    result_map[slot] = (color, make_bright(color))

  result = []
  for i in range(8):
    normal, bright = result_map.get(i, (black, make_bright(black)))

    if options.inverted:
      normal = [1 - x for x in normal]
      bright = [1 - x for x in bright]

    if i == COLOR_WHITE:
      normal = clamp_hsv(normal, mins=0.0, maxs=0.12, minv=0.78, maxv=0.86)
      bright = clamp_hsv(bright, mins=0.0, maxs=0.19, minv=0.86, maxv=1.00)

    if i == COLOR_BLACK:
      normal = clamp_hsv(normal, mins=0.0, maxs=0.08, minv=0.08, maxv=0.12)
      bright = clamp_hsv(bright, mins=0.0, maxs=0.16, minv=0.08, maxv=0.23)

    result.append((normal, bright))
  return result


def generate(options):
  """Generate the iTerm2 DynamicProfile JSON with ANSI + named colors."""
  image = os.path.abspath(options.image)

  json_before = JSON_BEFORE.format(
      options.parent, options.transparency,
      "" if options.no_background else image,
      to_json_bool(options.tiled),
      0.0, options.blend)

  json = ""
  palette = extract_colors(options)

  for i, (normal, bright) in enumerate(palette):
    if i == COLOR_WHITE:
      fg = clamp_hsv(normal, mins=0.12, maxs=0.16, minv=0.58, maxv=0.63)
      json += JSON_COLOR_NAMED.format("Foreground", *fg)

    if i == COLOR_BLACK:
      bg = clamp_hsv(normal, mins=0.0, maxs=0.1, minv=0.04, maxv=0.06)
      json += JSON_COLOR_NAMED.format("Background", *bg)

      sel_text = clamp_hsv(normal, mins=0.0, maxs=0.1, minv=0.06, maxv=0.10)
      json += JSON_COLOR_NAMED.format("Selected Text", *sel_text)

    if i == COLOR_BLUE:
      json += JSON_COLOR_NAMED.format("Selection", *normal)

    if i == COLOR_CYAN:
      json += JSON_COLOR_NAMED.format("Link", *normal)

    if i == COLOR_MAGENTA:
      bold = clamp_hsv(normal, mins=0.60, minv=0.80, maxv=0.90)
      json += JSON_COLOR_NAMED.format("Bold", *bold)

    json += JSON_COLOR_ANSI.format(i, *normal)
    json += JSON_COLOR_ANSI.format(i + 8, *bright)

  with open(options.out, 'w') as theme:
    theme.write(json_before)
    theme.write(json[:-2])
    theme.write(JSON_AFTER)


def generate_vim(options):
  """Generate a Vim colorscheme file from the extracted palette.

  Colors are contrast-checked against the background and nudged if needed.
  The hi() helper emits both gui (hex) and cterm (256-color) attributes so
  the theme works in both terminal vim and gvim.
  """
  palette = extract_colors(options)

  bg       = clamp_hsv(palette[COLOR_BLACK][0], mins=0.0, maxs=0.1,  minv=0.04, maxv=0.06)
  bg2      = clamp_hsv(palette[COLOR_BLACK][0], mins=0.0, maxs=0.1,  minv=0.08, maxv=0.14)
  fg       = clamp_hsv(palette[COLOR_WHITE][0], mins=0.12, maxs=0.16, minv=0.58, maxv=0.63)
  comment  = clamp_hsv(palette[COLOR_BLACK][1], mins=0.0,  maxs=0.16, minv=0.28, maxv=0.38)

  fg      = ensure_contrast(fg, bg)
  comment = ensure_contrast(comment, bg)
  sel      = palette[COLOR_BLUE][0]
  red      = ensure_contrast(palette[COLOR_RED][0], bg)
  red_b    = ensure_contrast(palette[COLOR_RED][1], bg)
  green    = ensure_contrast(palette[COLOR_GREEN][0], bg)
  green_b  = ensure_contrast(palette[COLOR_GREEN][1], bg)
  yellow   = ensure_contrast(palette[COLOR_YELLOW][0], bg)
  yellow_b = ensure_contrast(palette[COLOR_YELLOW][1], bg)
  blue     = ensure_contrast(palette[COLOR_BLUE][0], bg)
  blue_b   = ensure_contrast(palette[COLOR_BLUE][1], bg)
  magenta  = ensure_contrast(palette[COLOR_MAGENTA][0], bg)
  magenta_b= ensure_contrast(palette[COLOR_MAGENTA][1], bg)
  cyan     = ensure_contrast(palette[COLOR_CYAN][0], bg)
  cyan_b   = ensure_contrast(palette[COLOR_CYAN][1], bg)
  bold_col = clamp_hsv(magenta, mins=0.60, minv=0.80, maxv=0.90)
  err_bg   = clamp_hsv(red, mins=0.10, maxs=0.25, minv=0.18, maxv=0.26)

  name = os.path.splitext(os.path.basename(options.vim_out))[0]

  def hi(group, fg=None, bg=None, attr=None, sp=None):
    """Emit a :hi command for the given group with gui and cterm colors."""
    gfg = to_hex(fg) if fg else "NONE"
    gbg = to_hex(bg) if bg else "NONE"
    cfg = str(to_256(fg)) if fg else "NONE"
    cbg = "NONE"
    a   = attr or "NONE"
    line = "hi {} term=NONE guifg={} guibg={} ctermfg={} ctermbg={} gui={} cterm={}".format(
        group, gfg, gbg, cfg, cbg, a, a)
    if sp:
      line += " guisp={}".format(to_hex(sp))
    return line

  def link(group, target):
    return "hi! link {} {}".format(group, target)

  lines = [
    '" Generated by iterm-theme-generator',
    "set background=dark",
    "hi clear",
    "if exists('syntax_on') | syntax reset | endif",
    "let g:colors_name = '{}'".format(name),
    "",
    '" ── UI ──────────────────────────────────────────────────────────────',
    hi("Normal",          fg=fg,      bg=bg),
    hi("NormalFloat",     fg=fg,      bg=bg2),
    hi("NonText",         fg=comment),
    hi("EndOfBuffer",     fg=comment),
    hi("SpecialKey",      fg=comment),
    hi("Conceal",         fg=comment),
    hi("Visual",          fg=fg,      bg=sel),
    hi("VisualNOS",       fg=fg,      bg=sel),
    hi("Search",          fg=bg,      bg=yellow),
    hi("IncSearch",       fg=bg,      bg=yellow_b),
    hi("CurSearch",       fg=bg,      bg=yellow_b),
    hi("MatchParen",      fg=bg,      bg=bold_col, attr="bold"),
    hi("Cursor",          fg=bg,      bg=fg),
    hi("CursorLine",                               attr="NONE"),
    hi("CursorColumn",                             attr="NONE"),
    hi("CursorLineNr",    fg=yellow),
    hi("ColorColumn"),
    hi("LineNr",          fg=comment),
    hi("SignColumn",      fg=green),
    hi("FoldColumn",      fg=comment),
    hi("Folded",          fg=comment),
    hi("VertSplit",       fg=blue),
    hi("WinSeparator",    fg=blue),
    hi("StatusLine",      fg=fg,      bg=blue),
    hi("StatusLineNC",    fg=comment),
    hi("StatusLineTerm",  fg=fg,      bg=blue),
    hi("StatusLineTermNC",fg=comment),
    hi("TabLine",         fg=comment,              attr="NONE"),
    hi("TabLineSel",      fg=fg,      bg=blue, attr="NONE"),
    hi("TabLineFill",                              attr="NONE"),
    hi("WildMenu",        fg=bg,      bg=cyan, attr="bold"),
    hi("PMenu",           fg=fg,      bg=bg2),
    hi("PMenuSel",        fg=fg,      bg=sel),
    hi("PMenuSbar"),
    hi("PMenuThumb"),
    hi("Directory",       fg=blue),
    hi("Title",           fg=comment, attr="bold"),
    hi("ModeMsg",         fg=yellow),
    hi("MoreMsg",         fg=yellow),
    hi("Question",        fg=yellow),
    hi("WarningMsg",      fg=magenta_b),
    hi("Error",           fg=red_b,   bg=err_bg),
    hi("ErrorMsg",        fg=red_b,   bg=err_bg),
    hi("Todo",            fg=yellow,               attr="bold"),
    hi("DiffAdd",         fg=green),
    hi("DiffChange",      fg=yellow),
    hi("DiffDelete",      fg=red),
    hi("DiffText",        fg=bg,      bg=yellow, attr="bold"),
    hi("SpellBad",        sp=red,     attr="undercurl"),
    hi("SpellCap",        sp=blue,    attr="undercurl"),
    hi("SpellLocal",      sp=cyan,    attr="undercurl"),
    hi("SpellRare",       sp=magenta, attr="undercurl"),
    hi("IndentGuidesOdd"),
    hi("IndentGuidesEven"),
    "",
    '" ── Syntax ──────────────────────────────────────────────────────────',
    hi("Comment",         fg=comment),
    hi("SpecialComment",  fg=comment,              attr="bold"),
    hi("Constant",        fg=cyan),
    hi("String",          fg=green),
    hi("Character",       fg=green),
    hi("Number",          fg=cyan),
    hi("Boolean",         fg=green,   attr="bold"),
    hi("Float",           fg=cyan),
    hi("Identifier",      fg=blue),
    hi("Function",        fg=fg),
    hi("Statement",       fg=magenta_b, attr="NONE"),
    hi("Conditional",     fg=magenta,   attr="bold"),
    hi("Repeat",          fg=magenta,   attr="bold"),
    hi("Label",           fg=blue),
    hi("Operator",        fg=cyan,    attr="NONE"),
    hi("Keyword",         fg=blue),
    hi("Exception",       fg=red),
    hi("PreProc",         fg=blue),
    hi("Include",         fg=red),
    hi("Define",          fg=blue),
    hi("Macro",           fg=blue),
    hi("PreCondit",       fg=cyan),
    hi("Type",            fg=magenta_b, attr="bold"),
    hi("StorageClass",    fg=blue,    attr="bold"),
    hi("Structure",       fg=blue,    attr="bold"),
    hi("Typedef",         fg=magenta_b, attr="bold"),
    hi("Special",         fg=fg),
    hi("SpecialChar",     fg=fg),
    hi("Tag",             fg=green),
    hi("Delimiter",       fg=cyan),
    hi("Debug",           fg=cyan),
    hi("Underlined",      fg=blue,    attr="underline"),
    hi("Ignore",          fg=comment),
    hi("Global",          fg=blue),
    "",
    '" ── Diff ────────────────────────────────────────────────────────────',
    hi("diffAdded",       fg=green),
    hi("diffRemoved",     fg=red),
    hi("diffFile",        fg=yellow,  attr="bold"),
    hi("diffNewFile",     fg=yellow),
    hi("diffLine",        fg=blue,    attr="bold"),
    hi("diffIndexLine",   fg=blue),
    hi("diffSubname",     fg=fg),
    hi("diffBDiffer",     fg=magenta),
    "",
    '" ── LSP / Diagnostics ───────────────────────────────────────────────',
    hi("DiagnosticError",            fg=red_b),
    hi("DiagnosticWarn",             fg=yellow),
    hi("DiagnosticInfo",             fg=blue),
    hi("DiagnosticHint",             fg=cyan),
    hi("DiagnosticUnderlineError",   sp=red_b,   attr="undercurl"),
    hi("DiagnosticUnderlineWarn",    sp=yellow,  attr="undercurl"),
    hi("DiagnosticUnderlineInfo",    sp=blue,    attr="undercurl"),
    hi("DiagnosticUnderlineHint",    sp=cyan,    attr="undercurl"),
    link("LspDiagnosticsDefaultError",       "DiagnosticError"),
    link("LspDiagnosticsDefaultWarning",     "DiagnosticWarn"),
    link("LspDiagnosticsDefaultInformation", "DiagnosticInfo"),
    link("LspDiagnosticsDefaultHint",        "DiagnosticHint"),
    link("LspDiagnosticsUnderlineError",     "DiagnosticUnderlineError"),
    link("LspDiagnosticsUnderlineWarning",   "DiagnosticUnderlineWarn"),
    link("LspDiagnosticsUnderlineInformation","DiagnosticUnderlineInfo"),
    link("LspDiagnosticsUnderlineHint",      "DiagnosticUnderlineHint"),
    "",
    '" ── Git ─────────────────────────────────────────────────────────────',
    hi("gitcommitSummary",      fg=fg,      attr="bold"),
    hi("gitcommitHeader",       fg=comment),
    hi("gitcommitBranch",       fg=magenta_b, attr="bold"),
    hi("gitcommitSelectedType", fg=green),
    hi("gitcommitDiscardedType",fg=red),
    hi("gitcommitSelectedFile", fg=green),
    hi("gitcommitUntrackedFile",fg=cyan),
    hi("gitcommitDiff",         fg=comment),
    link("gitcommitNoBranch",   "gitcommitBranch"),
    hi("SignifySignAdd",    fg=green),
    hi("SignifySignChange", fg=yellow),
    hi("SignifySignDelete", fg=red),
    link("SignifyLineAdd",    "DiffAdd"),
    link("SignifyLineChange", "DiffChange"),
    link("SignifyLineDelete", "DiffDelete"),
    "",
    '" ── NERDTree ────────────────────────────────────────────────────────',
    hi("NERDTreeDir",         fg=blue),
    hi("NERDTreeDirSlash",    fg=blue),
    hi("NERDTreeFile",        fg=fg),
    hi("NERDTreeExecFile",    fg=green),
    hi("NERDTreeHelp",        fg=comment),
    hi("NERDTreeHelpTitle",   fg=magenta_b, attr="bold"),
    hi("NERDTreeHelpKey",     fg=cyan),
    hi("NERDTreeHelpCommand", fg=yellow),
    hi("NERDTreeUp",          fg=comment),
    hi("NERDTreeOpenable",    fg=yellow),
    hi("NERDTreeClosable",    fg=yellow),
    hi("NERDTreeToggleOn",    fg=green,  attr="bold"),
    hi("NERDTreeToggleOff",   fg=red,    attr="bold"),
    "",
    '" ── Startify ────────────────────────────────────────────────────────',
    hi("StartifyHeader",  fg=blue,    attr="bold"),
    hi("StartifySection", fg=magenta_b, attr="bold"),
    hi("StartifyFile",    fg=fg),
    hi("StartifyPath",    fg=comment),
    hi("StartifySlash",   fg=comment),
    hi("StartifyNumber",  fg=yellow),
    hi("StartifyBracket", fg=comment),
    hi("StartifySpecial", fg=cyan),
    "",
    '" ── Tagbar ──────────────────────────────────────────────────────────',
    hi("TagbarKind",       fg=blue,    attr="bold"),
    hi("TagbarSignature",  fg=comment),
    hi("TagbarHelp",       fg=comment),
    hi("TagbarHelpTitle",  fg=magenta_b, attr="bold"),
    "",
    '" ── CoC ─────────────────────────────────────────────────────────────',
    hi("CocErrorSign",    fg=red_b),
    hi("CocWarningSign",  fg=yellow),
    hi("CocInfoSign",     fg=blue),
    hi("CocHintSign",     fg=cyan),
    hi("CocErrorHighlight",   sp=red_b,  attr="undercurl"),
    hi("CocWarningHighlight", sp=yellow, attr="undercurl"),
    hi("CocInfoHighlight",    sp=blue,   attr="undercurl"),
    hi("CocHintHighlight",    sp=cyan,   attr="undercurl"),
    hi("CocFloating",     fg=fg,  bg=bg2),
    hi("CocErrorFloat",   fg=red_b,  bg=bg2),
    hi("CocWarningFloat", fg=yellow, bg=bg2),
    hi("CocInfoFloat",    fg=blue,   bg=bg2),
    hi("CocHintFloat",    fg=cyan,   bg=bg2),
    "",
    '" ── netrw ───────────────────────────────────────────────────────────',
    hi("netrwDir",        fg=blue),
    hi("netrwClassify",   fg=blue),
    hi("netrwExe",        fg=green),
    hi("netrwSuffixes",   fg=comment),
    hi("netrwTreeBar",    fg=comment),
    hi("netrwList",       fg=fg),
    hi("netrwHelpCmd",    fg=cyan),
    hi("netrwQuickHelp",  fg=comment),
    hi("netrwHidePat",    fg=comment),
    hi("netrwVersion",    fg=comment),
    "",
    '" ── BufTabLine ──────────────────────────────────────────────────────',
    hi("BufTabLineCurrent", fg=fg,      bg=blue, attr="NONE"),
    hi("BufTabLineActive",  fg=fg,                attr="NONE"),
    hi("BufTabLineHidden",  fg=comment,           attr="NONE"),
    hi("BufTabLineFill",                          attr="NONE"),
    "",
    '" ── Terminal colors (Vim 8+ / Neovim) ───────────────────────────────',
  ]

  for i, (normal, bright) in enumerate(palette):
    lines.append("let g:terminal_color_{} = '{}'".format(i, to_hex(normal)))
    lines.append("let g:terminal_color_{} = '{}'".format(i + 8, to_hex(bright)))

  with open(options.vim_out, 'w') as f:
    f.write("\n".join(lines) + "\n")

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
      '--sat-boost', dest='sat_boost', metavar='VALUE', type=float, default=0.08,
      help="Saturation boost applied to chromatic colors (0.0-1.0). Default: 0.08")

  parser.add_argument(
      '--sat-cap', dest='sat_cap', metavar='VALUE', type=float, default=1.0,
      help="Saturation cap before boost (0.0-1.0). Default: 1.0")

  parser.add_argument(
      '--val-boost', dest='val_boost', metavar='VALUE', type=float, default=0.2,
      help="Brightness boost applied to chromatic colors (0.0-1.0). Default: 0.2")

  parser.add_argument(
      '--val-cap', dest='val_cap', metavar='VALUE', type=float, default=0.65,
      help="Brightness cap before boost, prevents neon colors (0.0-1.0). Default: 0.65")

  parser.add_argument(
      '--hue-boost', dest='hue_boost', metavar='VALUE', type=float, default=0.0,
      help="Hue rotation applied to chromatic colors (0.0-1.0). Default: 0.0")

  parser.add_argument(
      '--hue-cap', dest='hue_cap', metavar='VALUE', type=float, default=1.0,
      help="Hue cap before boost (0.0-1.0). Default: 1.0")

  parser.add_argument(
      '--bright-sat-drop', dest='bright_sat_drop', metavar='VALUE', type=float, default=0.1,
      help="Saturation reduction for bright variants (0.0-1.0). Default: 0.1")

  parser.add_argument(
      '--bright-val-boost', dest='bright_val_boost', metavar='VALUE', type=float, default=0.15,
      help="Brightness boost for bright variants (0.0-1.0). Default: 0.15")

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

  parser.add_argument(
      '--vim-out', dest='vim_out', metavar='FILE', default=None,
      help="If set, also generate a Vim colorscheme at this path (e.g. ~/.vim/colors/terminal.vim)")

  options = parser.parse_args()
  generate(options)
  if options.vim_out:
    generate_vim(options)

if __name__ == "__main__":
  main()
