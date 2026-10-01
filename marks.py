"""Club marks: a faint line drawing of each club's mascot for the right of its
band (Scout, and the opposition end of the Match band), where the club site
puts its crests. They are our own plain drawings of the animal or idea behind
the nickname (a cat for Geelong, a crow for Adelaide), never a club's logo,
crest or other mark. Fremantle (and any club without one) gets the anchor.

Each mark is SVG markup on a 64 x 64 grid, drawn in white lines; `uri(club)`
wraps it as a CSS url() for the band's ::after background.
"""

import math
from urllib.parse import quote


def _ring(cx, cy, r_out, r_in, points, start=-90):
    """A zigzag ring (a lion's mane) or star outline: alternating radii."""
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(start + i * 180 / points)
        pts.append(f"{cx + r * math.cos(a):.1f} {cy + r * math.sin(a):.1f}")
    return "M" + " L".join(pts) + " Z"


def _rays(cx, cy, r1, r2, n):
    return " ".join(
        f"M{cx + r1 * math.cos(math.radians(i * 360 / n)):.1f} "
        f"{cy + r1 * math.sin(math.radians(i * 360 / n)):.1f} "
        f"L{cx + r2 * math.cos(math.radians(i * 360 / n)):.1f} "
        f"{cy + r2 * math.sin(math.radians(i * 360 / n)):.1f}" for i in range(n))


_CROW = ('<path d="M8 25 L20 21 C23 15 31 13 37 17 C45 22 52 32 60 46 L47 43 C40 47 30 46 25 40 '
         'C21 35 20 31 20 29 Z"/><path d="M28 30 C34 36 42 38 50 41"/>'
         '<path d="M32 46 L30 56 M38 45 L38 56 M27 56 L33 56 M35 56 L41 56"/>'
         '<circle cx="26" cy="21" r="1.6" fill="white"/>')

MARKS = {
    "Fremantle": ('<circle cx="32" cy="12" r="6"/>'
                  '<path d="M32 18v38M20 28h24M10 38c2 12 12 18 22 18s20-6 22-18"/>'),
    "Adelaide": _CROW,                                       # Crows
    "Collingwood": (                                         # Magpies: facing the other way, wing patch
        '<g transform="translate(64 0) scale(-1 1)">' + _CROW + '</g>'
        '<path d="M26 30 L38 35" stroke-width="6"/>'),
    "Geelong": (                                             # Cats
        '<path d="M14 54 C10 44 10 30 14 22 L12 8 L24 16 C29 14 35 14 40 16 L52 8 L50 22 '
        'C54 30 54 44 50 54 C44 60 20 60 14 54 Z"/>'
        '<ellipse cx="25" cy="34" rx="3.5" ry="2.2"/><ellipse cx="39" cy="34" rx="3.5" ry="2.2"/>'
        '<path d="M30 42 L34 42 L32 45 Z M6 41 L21 44 M6 48 L21 46 M58 41 L43 44 M58 48 L43 46"/>'),
    "Brisbane Lions": (                                      # Lions: face in a zigzag mane
        f'<path d="{_ring(32, 32, 28, 20, 14)}"/><circle cx="32" cy="33" r="13"/>'
        '<circle cx="27" cy="30" r="1.6" fill="white"/><circle cx="37" cy="30" r="1.6" fill="white"/>'
        '<path d="M29 36 L35 36 L32 39 Z M32 39 L32 42 M28 43 C30 44 34 44 36 43"/>'),
    "Richmond": ('<g stroke-width="5">'                      # Tigers: claw marks
                 '<path d="M18 10 C23 25 23 40 16 55"/><path d="M32 8 C37 25 37 40 30 57"/>'
                 '<path d="M46 10 C51 25 51 40 44 55"/></g>'),
    "Hawthorn": (                                            # Hawks: head with a hooked beak
        '<path d="M46 58 C50 46 52 34 48 22 C44 12 32 8 24 11 C17 14 12 19 10 26 C8 31 10 35 14 35 '
        'L18 33 C18 37 21 39 25 39 C23 45 25 52 31 58"/>'
        '<circle cx="29" cy="21" r="2.4"/><path d="M21 17 L36 17"/>'),
    "West Coast": (                                          # Eagles: soaring, fingered wing tips
        '<path d="M28 26 C21 21 12 18 3 19 L10 22 L4 25 L11 27 L6 31 C14 32 21 32 28 31"/>'
        '<path d="M36 26 C43 21 52 18 61 19 L54 22 L60 25 L53 27 L58 31 C50 32 43 32 36 31"/>'
        '<path d="M28 24 C28 21 36 21 36 24 L36 37 L32 40 L28 37 Z"/>'
        '<circle cx="32" cy="17" r="4"/><path d="M32 20 L32 22"/>'
        '<path d="M29 39 L26 50 L32 46 L38 50 L35 39"/>'),
    "Sydney": (                                              # Swans: curved neck, raised wing
        '<path d="M6 40 C10 52 48 54 58 38 C52 40 46 38 42 32 C40 38 34 42 26 40 '
        'C20 38 19 31 23 25 C27 19 30 15 28 11 C26 7 20 7 18 11 L12 13 L18 15 '
        'C20 13 22 13 22.5 15 C23 18 19 23 16 29 C12 36 13 42 20 44"/>'
        '<path d="M42 32 C46 26 52 24 58 24 C56 30 52 34 46 36"/>'
        '<circle cx="23" cy="10.5" r="1.3" fill="white"/>'),
    "Western Bulldogs": (                                    # Bulldogs: face, floppy ears, jowls
        '<path d="M14 26 C14 14 24 10 32 10 C40 10 50 14 50 26 C54 32 54 44 48 50 '
        'C42 56 22 56 16 50 C10 44 10 32 14 26 Z"/>'
        '<path d="M15 22 L6 18 L9 36 M49 22 L58 18 L55 36"/>'
        '<circle cx="24" cy="29" r="2" fill="white"/><circle cx="40" cy="29" r="2" fill="white"/>'
        '<ellipse cx="32" cy="38" rx="5" ry="3.5"/>'
        '<path d="M22 46 C26 50 30 48 32 42 C34 48 38 50 42 46"/>'),
    "North Melbourne": (                                     # Kangaroos
        '<path d="M6 58 C18 54 26 48 30 40 C28 34 30 26 36 22 L39 12 L42 20 L46 11 L46 22 '
        'C50 24 54 26 56 30 L50 31 C46 31 44 35 44 40 C46 46 49 52 56 58 L43 58 '
        'C41 53 37 49 34 47 C29 53 20 57 6 58 Z"/><path d="M44 36 L51 41"/>'
        '<circle cx="47" cy="25" r="1.4" fill="white"/>'),
    "Melbourne": (                                           # Demons: a trident
        '<path d="M32 58 L32 14 M20 24 L20 11 M44 24 L44 11 M20 24 C20 31 44 31 44 24"/>'
        '<path d="M27 15 L32 6 L37 15 M16 13 L20 7 L24 13 M40 13 L44 7 L48 13"/>'),
    "Essendon": (                                            # Bombers: a plane from above
        '<path d="M32 6 C35 6 36 10 36 16 L36 26 L58 36 L58 40 L36 36 L35 50 L42 56 L42 58 '
        'L32 55 L22 58 L22 56 L29 50 L28 36 L6 40 L6 36 L28 26 L28 16 C28 10 29 6 32 6 Z"/>'),
    "Gold Coast": (                                          # Suns
        f'<circle cx="32" cy="32" r="12"/><path d="{_rays(32, 32, 18, 27, 12)}"/>'),
    "Greater Western Sydney": (                              # Giants: a giant's footprint
        '<path d="M24 58 C15 58 13 48 15 40 C17 32 21 27 29 27 C39 27 43 35 41 45 C39 53 33 58 24 58 Z"/>'
        '<circle cx="14" cy="21" r="3"/><circle cx="21" cy="15" r="3.4"/><circle cx="30" cy="12" r="3.8"/>'
        '<circle cx="39" cy="14" r="3.4"/><circle cx="45" cy="20" r="3"/>'),
    "Port Adelaide": (                                       # Power: a lightning bolt
        '<path d="M38 4 L14 36 L30 36 L24 60 L50 26 L34 26 Z"/>'),
    "St Kilda": (                                            # Saints: a halo over a sparkle
        '<ellipse cx="32" cy="20" rx="19" ry="6"/>'
        '<path d="M32 32 L35 43 L46 46 L35 49 L32 60 L29 49 L18 46 L29 43 Z"/>'),
    "Carlton": (                                             # Blues: Captain Carlton's mask
        '<path d="M6 26 C14 20 24 22 32 28 C40 22 50 20 58 26 C58 36 52 42 44 42 C38 42 34 38 32 34 '
        'C30 38 26 42 20 42 C12 42 6 36 6 26 Z"/>'
        '<ellipse cx="20" cy="32" rx="5" ry="3.5"/><ellipse cx="44" cy="32" rx="5" ry="3.5"/>'),
}


def svg(club):
    body = MARKS.get(club, MARKS["Fremantle"])
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="white" '
            f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


def uri(club):
    """The club's mark as a CSS url(), for a style attribute."""
    # Single quotes: it goes inside double-quoted style attributes.
    return "url('data:image/svg+xml," + quote(svg(club), safe="") + "')"
