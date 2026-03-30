"""Generate an iTerm2 DynamicProfile JSON from an extracted palette.

iTerm2 supports "Dynamic Profiles" — JSON files dropped into
  ~/Library/Application Support/iTerm2/DynamicProfiles/
that are loaded at runtime without restarting.  Each profile can inherit
from a parent profile, so we only need to override color settings.

This module:
  1. Extracts the palette via colors.extract_colors().
  2. Maps ANSI slots 0–15 (normal + bright) into the JSON color format.
  3. Derives named semantic colors (Foreground, Background, Selection, etc.)
     from specific ANSI slots with additional HSV clamping.
  4. Writes the complete DynamicProfile JSON to disk.

Output structure (simplified):
  { "Profiles": [{
      "Name": "Default.Profile.Theme",
      "Dynamic Profile Parent Name": "<parent>",
      "Background Image Location": "<image>",
      "Ansi 0 Color": { R, G, B },   ← BLACK normal
      "Ansi 8 Color": { R, G, B },   ← BLACK bright
      ...
      "Foreground Color": { R, G, B },
      "Background Color": { R, G, B },
      ...
  }]}
"""

import os

from .colors import (
  extract_colors,
  COLOR_BLACK, COLOR_WHITE, COLOR_BLUE, COLOR_CYAN, COLOR_MAGENTA,
)

# Default output path — iTerm2's DynamicProfiles directory
HOME = os.path.expanduser("~")
THEME = HOME + "/Library/Application Support/iTerm2/DynamicProfiles/theme.json"

# ---------------------------------------------------------------------------
# JSON templates.  Double braces {{ }} are literal braces in str.format();
# single braces {} are substitution points.
# ---------------------------------------------------------------------------

# Profile header: inherits from parent, sets transparency and background image
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

# Profile footer: closes the JSON array and object
JSON_AFTER = """
  }]
}
"""

# Template for ANSI color slots 0–15 (index, R, G, B)
JSON_COLOR_ANSI = """
    "Ansi {} Color": {{
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""

# Template for named colors (name, R, G, B) — includes Color Space
JSON_COLOR_NAMED = """
    "{} Color": {{
      "Color Space" : "Calibrated",
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""


def to_json_bool(value):
  """Convert a Python bool to a JSON-compatible lowercase string."""
  return 'true' if value else 'false'


def generate(options):
  """Generate the iTerm2 DynamicProfile JSON and write it to disk.

  Args:
    options: argparse namespace with:
      .image          — path to the source image
      .parent         — name of the iTerm2 parent profile to inherit
      .out            — output file path (default: THEME)
      .transparency   — window transparency (0.0–1.0)
      .tiled          — whether to tile the background image
      .blend          — background image blend amount (0.0–1.0)
      .no_background  — if True, omit the background image path
      (plus all color-tuning options forwarded to extract_colors)
  """
  image = os.path.abspath(options.image)

  # Build the profile header with metadata and display settings
  json_before = JSON_BEFORE.format(
      options.parent, options.transparency,
      "" if options.no_background else image,
      to_json_bool(options.tiled),
      0.0, options.blend)

  json = ""
  palette, sem, _ = extract_colors(options)

  # Iterate over all 8 ANSI color slots.  For each slot we emit:
  #   - The normal color (Ansi {i})
  #   - The bright color (Ansi {i+8})
  #   - Any named semantic colors derived from this slot
  for i, (normal, bright) in enumerate(palette):

    # WHITE slot → Foreground from pre-computed semantic color
    if i == COLOR_WHITE:
      json += JSON_COLOR_NAMED.format("Foreground", *sem['fg'])

    # BLACK slot → Background and Selected Text from pre-computed semantic colors
    if i == COLOR_BLACK:
      json += JSON_COLOR_NAMED.format("Background", *sem['bg'])
      json += JSON_COLOR_NAMED.format("Selected Text", *sem['sel_text'])

    # BLUE slot → Selection highlight color
    if i == COLOR_BLUE:
      json += JSON_COLOR_NAMED.format("Selection", *sem['sel'])

    # CYAN slot → Clickable link color (used as-is)
    if i == COLOR_CYAN:
      json += JSON_COLOR_NAMED.format("Link", *normal)

    # MAGENTA slot → Bold text color
    if i == COLOR_MAGENTA:
      json += JSON_COLOR_NAMED.format("Bold", *sem['bold'])

    # Always emit the ANSI normal (0–7) and bright (8–15) entries
    json += JSON_COLOR_ANSI.format(i, *normal)
    json += JSON_COLOR_ANSI.format(i + 8, *bright)

  # Write the complete JSON file.
  # json[:-2] strips the trailing comma+newline from the last color entry
  # to produce valid JSON.
  with open(options.out, 'w') as theme:
    theme.write(json_before)
    theme.write(json[:-2])
    theme.write(JSON_AFTER)
