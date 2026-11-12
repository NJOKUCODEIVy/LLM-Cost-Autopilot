"""
Shared look for the web app: colors, base styles, the logo, and the tier meter.

Used by both the landing page (landing.py) and the chat (app.py).
"""

WINE_950 = "#150A0E"   # Dark hero background
WINE_700 = "#7B1E34"   # Brand burgundy
BRASS = "#E3B261"      # Accent on dark backgrounds
IVORY = "#F7F2EC"      # Text on dark backgrounds
INK = "#262524"
MUTED = "#66625F"
BORDER = "#DCD8D4"
METER_OFF = "#CFCAC6"

# Note: Streamlit removes any style block that contains a "<" character, so none appear below.
BASE_CSS = """
<style>
header[data-testid="stHeader"] { background: transparent; }
.ca { font-family: 'IBM Plex Sans', system-ui, sans-serif; color: #262524; }
.ca-mono { font-family: 'IBM Plex Mono', ui-monospace, monospace; }
.ca-muted { color: #66625F; }
.ca-logo { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 18px; }
.ca-meter { display: inline-flex; align-items: flex-end; gap: 2px; height: 12px; }
.ca-meter span { width: 3px; border-radius: 1px; }
</style>
"""


def logo_img(stroke: str = INK, dot: str = WINE_700) -> str:
    """The route mark as an image (Streamlit strips inline SVG, but keeps images)."""
    s, d = stroke.replace("#", "%23"), dot.replace("#", "%23")
    svg = (
        "%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 28 28%27 fill=%27none%27%3E"
        f"%3Ccircle cx=%276%27 cy=%2714%27 r=%273.5%27 stroke=%27{s}%27 stroke-width=%272%27/%3E"
        f"%3Cpath d=%27M9.5 14h4c2 0 3-1 4-3l1.5-3H24M13.5 14c2 0 3 1 4 3l1.5 3H24%27 stroke=%27{s}%27 "
        "stroke-width=%272%27 stroke-linecap=%27round%27/%3E"
        f"%3Ccircle cx=%2724%27 cy=%278%27 r=%272%27 fill=%27{d}%27/%3E"
        f"%3Ccircle cx=%2724%27 cy=%2720%27 r=%272%27 fill=%27{s}%27/%3E%3C/svg%3E"
    )
    return f'<img alt="" width="24" height="24" src="data:image/svg+xml;utf8,{svg}">'


def tier_meter(tier: int, on: str = WINE_700, off: str = METER_OFF) -> str:
    """Three small bars; the number filled in shows the tier."""
    bars = "".join(
        f'<span style="height:{h}px;background:{on if tier >= level else off}"></span>'
        for level, h in ((1, 5), (2, 8), (3, 12))
    )
    return f'<span class="ca-meter" aria-hidden="true">{bars}</span>'
