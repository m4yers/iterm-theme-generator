"""Color extraction and shared color utilities.

This module is the foundation of the theme generator. It provides:

  1. ANSI color slot constants (COLOR_BLACK .. COLOR_WHITE)
  2. Low-level color math: clamping, format conversion, luminance, contrast
  3. The main extract_colors() pipeline that turns an image into an 8-color
     ANSI palette via KMeans clustering in perceptual LAB color space.

Both iterm.py and vim.py depend on this module for palette extraction and
color manipulation — nothing here depends on either output format.

Color representation throughout this module:
  - RGB tuples are float triples in the range [0.0, 1.0]
  - HSV tuples follow Python's colorsys convention: H in [0.0, 1.0]
  - LAB values follow CIE L*a*b* (D65 illuminant)
"""

import colorsys
import os

from PIL import Image
from sklearn.cluster import KMeans

# ---------------------------------------------------------------------------
# ANSI color slot indices.  These map to the standard 8-color terminal
# palette positions and are used as dictionary keys throughout the codebase.
# ---------------------------------------------------------------------------
COLOR_BLACK = 0
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_YELLOW = 3
COLOR_BLUE = 4
COLOR_MAGENTA = 5
COLOR_CYAN = 6
COLOR_WHITE = 7


# ---------------------------------------------------------------------------
# Low-level color math
# ---------------------------------------------------------------------------

def clamp(value, minv, maxv):
  """Restrict *value* to the closed interval [minv, maxv]."""
  return max(minv, min(maxv, value))


def clamp_hsv(rgb, minh=0.0, maxh=1.0, mins=0.0, maxs=1.0, minv=0.0, maxv=1.0):
  """Clamp each HSV component of an RGB color independently.

  Converts *rgb* to HSV, clamps hue/saturation/value to the given ranges,
  and converts back.  Useful for forcing colors into safe brightness or
  saturation bands (e.g. ensuring BLACK stays dark, WHITE stays light).

  Args:
    rgb:  Float RGB tuple (0.0–1.0).
    minh/maxh: Hue clamp range.
    mins/maxs: Saturation clamp range.
    minv/maxv: Value (brightness) clamp range.

  Returns:
    Clamped float RGB tuple.
  """
  hue, sat, val = colorsys.rgb_to_hsv(*rgb)
  hue = clamp(hue, minh, maxh)
  sat = clamp(sat, mins, maxs)
  val = clamp(val, minv, maxv)
  return colorsys.hsv_to_rgb(hue, sat, val)


def to_hex(rgb):
  """Convert a float RGB tuple to a CSS hex string.

  Example: (0.3, 0.6, 0.9) → "#4d99e6"
  """
  return "#{:02x}{:02x}{:02x}".format(*(int(x * 255) for x in rgb))


def to_256(rgb):
  """Map a float RGB tuple to the nearest xterm-256 color index.

  The 256-color palette is laid out as:
    0–15:    standard + bright ANSI (not used here)
    16–231:  6×6×6 color cube
    232–255: 24-step grayscale ramp

  For grays (r == g == b) we use the grayscale ramp; otherwise we snap
  to the nearest point in the 6×6×6 cube.
  """
  r, g, b = (int(x * 255) for x in rgb)
  # Grayscale shortcut: if all channels are equal, use the gray ramp
  if r == g == b:
    if r < 8: return 16
    if r > 248: return 231
    return round((r - 8) / 247 * 24) + 232
  # Otherwise snap to the 6×6×6 color cube (indices 16–231)
  return 16 + 36 * round(r / 255 * 5) + 6 * round(g / 255 * 5) + round(b / 255 * 5)


def _srgb_linearize(c):
  """Linearize a single sRGB channel value (inverse gamma).

  Used by relative_luminance() and rgb_to_lab() to convert from the
  perceptual sRGB encoding to linear light values.
  """
  return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
  """WCAG 2.x relative luminance of a float RGB color.

  Applies the sRGB inverse-gamma transfer function to linearize each
  channel, then weights by the standard luminance coefficients.
  Returns a value in [0.0, 1.0] where 0 is black and 1 is white.
  """
  r, g, b = (_srgb_linearize(x) for x in rgb)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
  """WCAG contrast ratio between two RGB colors.

  Returns a value in [1.0, 21.0].  A ratio ≥ 3.0 is the minimum for
  large text; ≥ 4.5 for normal text.
  """
  la, lb = relative_luminance(a), relative_luminance(b)
  bright, dark = max(la, lb), min(la, lb)
  return (bright + 0.05) / (dark + 0.05)


def ensure_contrast(fg, bg, min_ratio=3.0):
  """Nudge *fg* until it meets *min_ratio* contrast against *bg*.

  Strategy:
    - On a dark background (luminance < 0.5): increase brightness (V).
    - On a light background: decrease brightness.
    - In both cases, slightly reduce saturation (S) each step to avoid
      washing out the color with brightness alone.
    - Iterates up to 100 steps of 0.01; if the ratio still isn't met
      the best attempt so far is returned.

  Args:
    fg:        Foreground float RGB.
    bg:        Background float RGB.
    min_ratio: Target WCAG contrast ratio (default 3.0).

  Returns:
    Adjusted float RGB tuple for *fg*.
  """
  # Already good — return unchanged
  if contrast_ratio(fg, bg) >= min_ratio:
    return fg
  h, s, v = colorsys.rgb_to_hsv(*fg)
  # Step direction: brighten on dark bg, darken on light bg
  step = 0.01 if relative_luminance(bg) < 0.5 else -0.01
  for _ in range(100):
    v = clamp(v + step, 0.0, 1.0)
    # Reduce saturation at 1/10th the rate to keep color identity
    s = clamp(s - abs(step) * 0.1, 0.0, 1.0)
    fg = colorsys.hsv_to_rgb(h, s, v)
    if contrast_ratio(fg, bg) >= min_ratio:
      break
  return fg


def _lab_transfer(t):
  """CIE L*a*b* forward transfer function (cube-root with linear segment).

  Used by rgb_to_lab() for the XYZ → L*a*b* conversion.
  """
  return t ** (1/3) if t > 0.008856 else 7.787 * t + 16/116


def rgb_to_lab(rgb):
  """Convert sRGB (0.0–1.0) to CIE L*a*b* via XYZ (D65 illuminant).

  Pipeline: sRGB → linearize → XYZ (D65 matrix) → normalize → L*a*b*.

  LAB is used for KMeans clustering because Euclidean distance in LAB
  correlates with perceived color difference, unlike RGB where
  perceptually distinct colors (e.g. dark blue vs dark green) can have
  small Euclidean distances.
  """
  # Linearize sRGB (inverse gamma)
  r, g, b = _srgb_linearize(rgb[0]), _srgb_linearize(rgb[1]), _srgb_linearize(rgb[2])
  # Linear RGB → XYZ (sRGB D65 matrix), normalized to D65 white point
  x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
  y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.00000
  z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883
  # XYZ → L*a*b*
  return [116 * _lab_transfer(y) - 16,
          500 * (_lab_transfer(x) - _lab_transfer(y)),
          200 * (_lab_transfer(y) - _lab_transfer(z))]


def _lab_inverse_transfer(t):
  """CIE L*a*b* inverse transfer function.

  Used by lab_to_rgb() for the L*a*b* → XYZ conversion.
  """
  return t**3 if t**3 > 0.008856 else (t - 16/116) / 7.787


def _srgb_gamma(c):
  """Apply sRGB gamma and clamp to [0, 1].

  Used by lab_to_rgb() to convert linear RGB back to sRGB encoding.
  """
  return max(0, min(1, 1.055 * c**(1/2.4) - 0.055 if c > 0.0031308 else 12.92 * c))


def lab_to_rgb(lab):
  """Convert CIE L*a*b* back to sRGB (0.0–1.0).

  Inverse of rgb_to_lab(): L*a*b* → XYZ → linear RGB → sRGB gamma.
  """
  L, a, b = lab
  # L*a*b* → XYZ
  fy = (L + 16) / 116
  fx = a / 500 + fy
  fz = fy - b / 200
  x, y, z = _lab_inverse_transfer(fx) * 0.95047, _lab_inverse_transfer(fy), _lab_inverse_transfer(fz) * 1.08883
  # XYZ → linear RGB (inverse of sRGB D65 matrix)
  r =  x * 3.2406 + y * -1.5372 + z * -0.4986
  g =  x * -0.9689 + y * 1.8758 + z * 0.0415
  b =  x * 0.0557 + y * -0.2040 + z * 1.0570
  # Apply sRGB gamma and clamp to [0, 1]
  return [_srgb_gamma(r), _srgb_gamma(g), _srgb_gamma(b)]


def hue_distance(a, b):
  """Circular distance between two hue values on [0, 1].

  Hue wraps around (0.0 and 1.0 are the same), so we take the
  minimum of the direct and wrap-around distances.
  """
  d = abs(a - b)
  return min(d, 1 - d)


def assign_colors(candidates, targets):
  """Assign candidates to ANSI slots: red/green by hue, rest by max contrast.

  Red and green have strong semantic meaning (error/success), so they're
  assigned by hue proximity.  The remaining 4 slots are filled by
  greedily picking the candidate most distant in LAB space from all
  already-chosen colors, producing maximum visual separation.

  Args:
    candidates: List of float-RGB colors (non-black/white cluster centers).
    targets:    Dict mapping ANSI slot → target hue (0.0–1.0).

  Returns:
    Dict mapping ANSI slot → assigned float-RGB color.
  """
  if not candidates:
    return {}

  labs = [rgb_to_lab(c) for c in candidates]
  remaining = set(range(len(candidates)))
  assigned = {}

  def _lab_dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

  # -- Phase 1: assign red and green by hue proximity ------------------
  for slot in (COLOR_RED, COLOR_GREEN):
    target_hue = targets[slot]
    best = min(remaining, key=lambda i: hue_distance(
        colorsys.rgb_to_hsv(*candidates[i])[0], target_hue))
    assigned[slot] = best
    remaining.remove(best)

  # -- Phase 2: fill remaining 4 slots by max LAB distance + hue diversity
  free_slots = [s for s in sorted(targets) if s not in assigned]
  chosen_labs = [labs[i] for i in assigned.values()]
  chosen_hues = [colorsys.rgb_to_hsv(*candidates[i])[0] for i in assigned.values()]

  for slot in free_slots:
    best = max(remaining, key=lambda i: (
        min(_lab_dist(labs[i], cl) for cl in chosen_labs) *
        min((hue_distance(colorsys.rgb_to_hsv(*candidates[i])[0], ch) for ch in chosen_hues), default=1.0)
    ))
    assigned[slot] = best
    remaining.remove(best)
    chosen_labs.append(labs[best])
    chosen_hues.append(colorsys.rgb_to_hsv(*candidates[best])[0])

  return {slot: candidates[i] for slot, i in assigned.items()}


def vivify(c, options):
  """Boost saturation/value/hue of a chromatic color within user min/max.

  For each HSV component: clamp to [min, max] first, then add the
  user-specified boost.  This makes extracted colors more vivid while
  keeping them within controllable bounds.

  Args:
    c:       Float RGB tuple.
    options: argparse namespace with .hue_min, .hue_max, .hue_boost,
             .sat_min, .sat_max, .sat_boost, .val_min, .val_max, .val_boost.

  Returns:
    Vivified float RGB tuple.
  """
  h, s, v = colorsys.rgb_to_hsv(*c)
  return colorsys.hsv_to_rgb(
      clamp(clamp(h, options.hue_min, options.hue_max) + options.hue_boost, 0.0, 1.0),
      clamp(clamp(s, options.sat_min, options.sat_max) + options.sat_boost, 0.0, 1.0),
      clamp(clamp(v, options.val_min, options.val_max) + options.val_boost, 0.0, 1.0))


def make_bright(c, options):
  """Derive a "bright" ANSI variant: less saturated, more luminous.

  Terminal emulators use bright variants for bold text and ANSI colors
  8–15.  Reducing saturation while boosting value gives a lighter,
  slightly washed-out version of the base color.

  Args:
    c:       Float RGB tuple.
    options: argparse namespace with .bright_sat_drop, .bright_val_boost.

  Returns:
    Bright-variant float RGB tuple.
  """
  h, s, v = colorsys.rgb_to_hsv(*c)
  return colorsys.hsv_to_rgb(h, max(0, s - options.bright_sat_drop), min(1, v + options.bright_val_boost))


# ---------------------------------------------------------------------------
# Target hues on the HSV color wheel (0.0–1.0) for each chromatic ANSI slot.
# These correspond to: red=0°, yellow=60°, green=120°, cyan=180°,
# blue=240°, magenta=300° — divided by 360.
# ---------------------------------------------------------------------------
TARGET_HUES = {
  COLOR_RED:     0.0,
  COLOR_YELLOW:  1/6,
  COLOR_GREEN:   1/3,
  COLOR_CYAN:    0.5,
  COLOR_BLUE:    2/3,
  COLOR_MAGENTA: 5/6,
}


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract_colors(options):
  """Extract an 8-color ANSI palette from an image.

  High-level pipeline:
    1. Load & thumbnail the image to 200×200 for speed.
    2. Convert every pixel to LAB color space.
    3. Run KMeans (k=30) in LAB space to find 30 dominant colors.
    4. Split centers into achromatic (sat < 0.15) and chromatic pools.
    5. Darkest achromatic → BLACK, brightest → WHITE.
    6. Assign 6 chromatic ANSI slots from the chromatic pool only,
       so desaturated grays can't steal chromatic slots.
    7. Apply vivify() boost/cap and derive bright variants.
    8. Clamp BLACK/WHITE into safe HSV ranges.

  Args:
    options: argparse namespace with at least:
      .image, .hue_cap, .hue_boost, .sat_cap, .sat_boost,
      .val_cap, .val_boost, .bright_sat_drop, .bright_val_boost,
      .inverted

  Returns:
    Tuple of (palette, semantic, raw) where:
      palette:  List of 8 (normal, bright) float-RGB tuples in ANSI order.
      semantic: Dict with transformed UI colors: 'bg', 'bg2', 'fg',
                'comment', 'sel_text', chromatic colors, accents.
      raw:      Dict with the same keys as semantic but before any
                contrast/clamp transformations were applied.
  """
  # -- Step 1: Load image and downsample --------------------------------
  img = Image.open(os.path.abspath(options.image)).convert("RGB")
  img.thumbnail((200, 200))
  # Normalize pixel values from 0–255 int to 0.0–1.0 float
  pixels = [[r/255, g/255, b/255] for r, g, b in img.getdata()]

  # -- Step 2: Convert to LAB for perceptual clustering -----------------
  lab_pixels = [rgb_to_lab(p) for p in pixels]

  # -- Step 3: KMeans clustering (30 clusters, LAB space) ---------------
  # 30 clusters gives a rich candidate pool; assign_colors picks red/green
  # by hue proximity and fills the rest by maximizing LAB contrast.
  km = KMeans(n_clusters=30, n_init=10, random_state=0)
  km.fit(lab_pixels)

  # Find the dominant color (largest cluster) for background hue tinting
  from collections import Counter
  dominant_idx = Counter(km.labels_).most_common(1)[0][0]
  dominant_rgb = lab_to_rgb(km.cluster_centers_[dominant_idx])
  dominant_hue = colorsys.rgb_to_hsv(*dominant_rgb)[0]

  # -- Step 4: Convert centers back to sRGB, split into pools -----------
  centers = [lab_to_rgb(c) for c in km.cluster_centers_]

  # Separate into achromatic (low saturation) and chromatic pools.
  # This prevents desaturated grays from stealing chromatic ANSI slots.
  CHROMA_THRESHOLD = 0.15
  achromatic = []
  chromatic  = []
  for c in centers:
    _, s, _ = colorsys.rgb_to_hsv(*c)
    (chromatic if s >= CHROMA_THRESHOLD else achromatic).append(c)

  # -- Step 5: Darkest achromatic → BLACK, brightest → WHITE -----------
  # Fall back to overall darkest/brightest if achromatic pool is too small
  by_lum = sorted(achromatic or centers, key=lambda c: relative_luminance(c))
  black = by_lum[0]
  white = by_lum[-1]

  # -- Step 6: Assign chromatic slots from the chromatic pool ----------
  # If the image has fewer than 6 chromatic candidates, backfill from
  # the achromatic pool (excluding black/white) sorted by saturation desc.
  if len(chromatic) < 6:
    backfill = sorted(
      [c for c in achromatic if c is not black and c is not white],
      key=lambda c: colorsys.rgb_to_hsv(*c)[1], reverse=True)
    chromatic.extend(backfill[:6 - len(chromatic)])

  assigned = assign_colors(chromatic, TARGET_HUES)

  # -- Step 7: Vivify + bright variants ---------------------------------
  # Build the result map: slot → (normal, bright)
  # BLACK and WHITE don't go through vivify() — they're achromatic.
  result_map = {
    COLOR_BLACK: (black, make_bright(black, options)),
    COLOR_WHITE: (white, make_bright(white, options)),
  }
  # Chromatic slots get vivified before bright derivation
  for slot, color in assigned.items():
    color = vivify(color, options)
    result_map[slot] = (color, make_bright(color, options))

  # -- Step 8: Final assembly with inversion and clamping ---------------
  result = []
  for i in range(8):
    # Fall back to black if a slot wasn't assigned (shouldn't happen with
    # 14 candidates for 6 slots, but defensive)
    normal, bright = result_map.get(i, (black, make_bright(black, options)))

    # Optional color inversion: flip each channel around 0.5
    if options.inverted:
      normal = [1 - x for x in normal]
      bright = [1 - x for x in bright]

    # Clamp WHITE to ensure it reads as a light, near-white color
    if i == COLOR_WHITE:
      normal = clamp_hsv(normal, mins=0.0, maxs=0.12, minv=0.78, maxv=0.86)
      bright = clamp_hsv(bright, mins=0.0, maxs=0.19, minv=0.86, maxv=1.00)

    # Clamp BLACK to ensure it reads as a dark, near-black color
    if i == COLOR_BLACK:
      normal = clamp_hsv(normal, mins=0.0, maxs=0.08, minv=0.08, maxv=0.12)
      bright = clamp_hsv(bright, mins=0.0, maxs=0.16, minv=0.08, maxv=0.23)

    result.append((normal, bright))

  # -- Derive semantic UI colors from the clamped palette ---------------
  # These are shared by both iterm.py and vim.py so they're computed once
  # here rather than re-derived in each generator.
  #
  # --vibrancy (0.0–1.0) controls how vivid the output is:
  #   - Raises the minimum contrast ratio (3.0 → up to 5.5)
  #   - Boosts fg and comment brightness ceilings
  v = getattr(options, 'vibrancy', 0.0)

  black_n, black_b = result[COLOR_BLACK]
  white_n, _       = result[COLOR_WHITE]

  # Contrast target: 3.0 at vibrancy=0, 5.5 at vibrancy=1
  min_ratio = 3.0 + v * 2.5

  # Snapshot raw palette colors before semantic transformations
  raw = {
    'bg': black_n, 'bg2': black_n, 'fg': white_n,
    'comment': black_b, 'sel_text': black_n,
    'sel': result[COLOR_BLUE][0], 'bold': result[COLOR_MAGENTA][0],
    'err_bg': result[COLOR_RED][0],
    'red': result[COLOR_RED][0], 'red_b': result[COLOR_RED][1],
    'green': result[COLOR_GREEN][0], 'green_b': result[COLOR_GREEN][1],
    'yellow': result[COLOR_YELLOW][0], 'yellow_b': result[COLOR_YELLOW][1],
    'blue': result[COLOR_BLUE][0], 'blue_b': result[COLOR_BLUE][1],
    'magenta': result[COLOR_MAGENTA][0], 'magenta_b': result[COLOR_MAGENTA][1],
    'cyan': result[COLOR_CYAN][0], 'cyan_b': result[COLOR_CYAN][1],
  }

  bg       = clamp_hsv(black_n, minh=dominant_hue, maxh=dominant_hue, mins=0.05, maxs=0.15, minv=0.08, maxv=0.06)
  bg2      = clamp_hsv(black_n, minh=dominant_hue, maxh=dominant_hue, mins=0.05, maxs=0.15, minv=0.17, maxv=0.2)
  # fg brightness ceiling: 0.63 at v=0, 0.82 at v=1
  fg       = ensure_contrast(
               clamp_hsv(white_n, mins=0.12, maxs=0.16,
                         minv=0.5, maxv=0.63 + v * 0.19), bg, min_ratio)
  # comment: derived from bright-black, low saturation and low hue
  # to keep it neutral/desaturated like fg and bg
  # brightness ceiling: 0.38 at v=0, 0.50 at v=1
  comment  = ensure_contrast(
               clamp_hsv(black_b, minh=dominant_hue, maxh=dominant_hue,
                         mins=0.1, maxs=0.1,
                         minv=0.0, maxv=v * 0.12), bg, min_ratio*0.6)

  # Contrast-check every chromatic color (normal + bright) against bg,
  # then re-apply the user's saturation cap since ensure_contrast may
  # have altered saturation while nudging brightness.
  def contrast_and_cap(color):
    c = ensure_contrast(color, bg, min_ratio)
    return clamp_hsv(c, mins=options.sat_min, maxs=options.sat_max) if options.sat_max < 1.0 else c

  sel       = result[COLOR_BLUE][0]  # selection bg — not contrast-checked
  red       = contrast_and_cap(result[COLOR_RED][0])
  red_b     = contrast_and_cap(result[COLOR_RED][1])
  green     = contrast_and_cap(result[COLOR_GREEN][0])
  green_b   = contrast_and_cap(result[COLOR_GREEN][1])
  yellow    = contrast_and_cap(result[COLOR_YELLOW][0])
  yellow_b  = contrast_and_cap(result[COLOR_YELLOW][1])
  blue      = contrast_and_cap(result[COLOR_BLUE][0])
  blue_b    = contrast_and_cap(result[COLOR_BLUE][1])
  magenta   = contrast_and_cap(result[COLOR_MAGENTA][0])
  magenta_b = contrast_and_cap(result[COLOR_MAGENTA][1])
  cyan      = contrast_and_cap(result[COLOR_CYAN][0])
  cyan_b    = contrast_and_cap(result[COLOR_CYAN][1])

  # Derived accent colors
  if getattr(options, 'bold_as_bright', False):
    bold   = clamp_hsv(magenta, mins=0.60, minv=0.80, maxv=0.90)
  else:
    bold   = fg
  err_bg   = clamp_hsv(red, mins=0.10, maxs=0.25, minv=0.18, maxv=0.26)

  # Write the contrast-checked/capped colors back into the palette so
  # that ANSI color entries (0–15) in the output match the semantic colors.
  result[COLOR_RED]     = (red, red_b)
  result[COLOR_GREEN]   = (green, green_b)
  result[COLOR_YELLOW]  = (yellow, yellow_b)
  result[COLOR_BLUE]    = (sel, blue_b)  # normal stays as selection color
  result[COLOR_MAGENTA] = (magenta, magenta_b)
  result[COLOR_CYAN]    = (cyan, cyan_b)

  semantic = {
    'bg': bg, 'bg2': bg2, 'fg': fg, 'comment': comment,
    'sel_text': clamp_hsv(black_n, mins=0.0, maxs=0.1, minv=0.06, maxv=0.10),
    'sel': sel, 'bold': bold, 'err_bg': err_bg,
    'red': red, 'red_b': red_b,
    'green': green, 'green_b': green_b,
    'yellow': yellow, 'yellow_b': yellow_b,
    'blue': blue, 'blue_b': blue_b,
    'magenta': magenta, 'magenta_b': magenta_b,
    'cyan': cyan, 'cyan_b': cyan_b,
  }

  return result, semantic, raw
