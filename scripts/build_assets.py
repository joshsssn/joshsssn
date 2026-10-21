"""Builds every SVG panel used in README.md, styled after a Bloomberg-type market terminal.

    python scripts/build_assets.py

Inputs:  data/contributions.json ({"YYYY-MM-DD": count}), data/stats.json ({"public_repos": n})
Outputs: assets/*.svg

Fonts (IBM Plex Mono / Plex Sans Condensed, SIL OFL) are subset per file and embedded as
base64 woff2, so the panels render the same on GitHub, in VS Code and in any browser.
Animations use CSS only (opacity, transform, stroke-dashoffset); every element is fully
visible when animations are off.
"""

import base64
import datetime as dt
import io
import json
import math
import random
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONT_DIR = Path(__file__).resolve().parent / "fonts"

# ------------------------------------------------------------------ palette
BLACK = "#000000"
AMBER = "#ffa028"      # labels, terminal text
ORANGE = "#fb8b1e"     # section bars, input fields
WHITE = "#ffffff"
SOFT = "#d6d6d6"
GREY = "#8c8c8c"
DIM = "#4a4a4a"
RULE = "#2b2b2b"
ROW = "#0d0d0d"
GREEN = "#3ddc84"
RED = "#ff433d"
BLUE = "#4da3ff"
NAVY_TOP = "#0d2850"
NAVY_BOT = "#030b18"
RED_BAR_TOP = "#b0120a"
RED_BAR_BOT = "#6d0904"

# ------------------------------------------------------------------ fonts
FACES = {
    "m": ("M", 400, "ibm-plex-mono-latin-400-normal.woff2"),
    "mb": ("M", 600, "ibm-plex-mono-latin-600-normal.woff2"),
    "s": ("S", 400, "ibm-plex-sans-condensed-latin-400-normal.woff2"),
    "sb": ("S", 600, "ibm-plex-sans-condensed-latin-600-normal.woff2"),
}
_fonts = {}


def font(face):
    if face not in _fonts:
        _fonts[face] = TTFont(FONT_DIR / FACES[face][2])
    return _fonts[face]


def tw(text, size, face):
    """Advance width of `text` in px."""
    f = font(face)
    cmap, hmtx = f.getBestCmap(), f["hmtx"]
    upm = f["head"].unitsPerEm
    total = 0
    for ch in text:
        g = cmap.get(ord(ch))
        total += hmtx[g][0] if g else upm * 0.6
    return total * size / upm


def wrap(text, size, face, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if tw(cand, size, face) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def embed(face, chars):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    f = TTFont(FONT_DIR / FACES[face][2])
    sub.populate(text="".join(sorted(chars)) + " ")
    sub.subset(f)
    buf = io.BytesIO()
    f.flavor = "woff2"
    f.save(buf)
    fam, weight, _ = FACES[face]
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:{fam};font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2');}}"


# ------------------------------------------------------------------ svg document
BASE_CSS = """
text{white-space:pre}
.m,.mb{font-family:M,'IBM Plex Mono',Consolas,Menlo,monospace}
.s,.sb{font-family:S,'IBM Plex Sans Condensed','Arial Narrow',Arial,sans-serif}
.m,.s{font-weight:400}.mb,.sb{font-weight:600}
.ld{animation:ld .45s cubic-bezier(.2,.6,.3,1) both}
@keyframes ld{from{opacity:0}to{opacity:1}}
.up{animation:up .55s cubic-bezier(.2,.6,.3,1) both}
@keyframes up{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.blink{animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.grow{transform-box:fill-box;transform-origin:left center;animation:grow .9s cubic-bezier(.3,.7,.2,1) both}
@keyframes grow{from{transform:scaleX(0)}to{transform:none}}
.rise{transform-box:fill-box;transform-origin:center bottom;animation:rise .8s cubic-bezier(.3,.7,.2,1) both}
@keyframes rise{from{transform:scaleY(0)}to{transform:none}}
.flash{animation:flash 9s ease-out infinite}
@keyframes flash{0%,100%{opacity:0}2%{opacity:.9}22%{opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


class Doc:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts, self.css, self.defs = [], [], []
        self.chars = {k: set() for k in FACES}
        self.n = 0

    def uid(self, p="i"):
        self.n += 1
        return f"{p}{self.n}"

    def add(self, s):
        self.parts.append(s)

    def t(self, x, y, text, size, face="m", fill=WHITE, anchor="start", cls="", style="", extra=""):
        self.chars[face].update(text)
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        st = f' style="{style}"' if style else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{face} {cls}" font-size="{size}" fill="{fill}"{a}{st}{extra}>{escape(text)}</text>')
        return x + tw(text, size, face)

    def run(self, x, y, segs, size, gap=0, cls="", style=""):
        """Place [(text, face, fill), ...] one after the other; returns end x."""
        for text, face, fill in segs:
            x = self.t(x, y, text, size, face, fill, cls=cls, style=style) + gap
        return x

    def render(self, crop=None):
        x, y, w, h = crop or (0, 0, self.w, self.h)
        fonts = "".join(embed(f, c) for f, c in self.chars.items() if c)
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                f'viewBox="{x} {y} {w} {h}" role="img" aria-label="{escape(self.title)}">'
                f"<title>{escape(self.title)}</title><style>{fonts}{BASE_CSS}{''.join(self.css)}</style>{defs}"
                + "\n".join(self.parts) + "</svg>\n")


def d(sec):
    return f"animation-delay:{sec:.2f}s"


# ------------------------------------------------------------------ glyph shapes (fonts lack them)
def tri(doc, x, y, s, up=True, fill=GREEN, cls="", style=""):
    pts = f"{x},{y-s*.8} {x-s*.6},{y+s*.25} {x+s*.6},{y+s*.25}" if up else f"{x},{y+s*.25} {x-s*.6},{y-s*.8} {x+s*.6},{y-s*.8}"
    doc.add(f'<polygon points="{pts}" fill="{fill}" class="{cls}" style="{style}"/>')


def caret(doc, x, y, fill=WHITE):
    doc.add(f'<polygon points="{x},{y-6} {x+7},{y-6} {x+3.5},{y-2}" fill="{fill}"/>')


def arrow_ne(doc, x, y, s, stroke):
    doc.add(f'<path d="M{x} {y} L{x+s} {y-s} M{x+s*.35} {y-s} H{x+s} V{y-s*.65}" stroke="{stroke}" '
            f'stroke-width="1.6" fill="none" stroke-linecap="round"/>')


SUITS = {
    "spade": "M50 2 C40 18 2 40 2 62 C2 80 22 90 38 80 C42 77 45 73 46 70 C45 82 40 92 30 98 H70 C60 92 55 82 54 70 C55 73 58 77 62 80 C78 90 98 80 98 62 C98 40 60 18 50 2Z",
    "heart": "M50 96 C38 82 2 60 2 30 C2 13 14 2 29 2 C40 2 47 9 50 18 C53 9 60 2 71 2 C86 2 98 13 98 30 C98 60 62 82 50 96Z",
    "diamond": "M50 2 L88 50 L50 98 L12 50Z",
    "club": "M50 4 A21 21 0 0 1 66 39 A21 21 0 1 1 57 74 C58 84 62 92 70 98 H30 C38 92 42 84 43 74 A21 21 0 1 1 34 39 A21 21 0 0 1 50 4Z",
}


def suit(doc, kind, cx, cy, size, fill, cls="", style=""):
    k = size / 100
    doc.add(f'<path d="{SUITS[kind]}" fill="{fill}" transform="translate({cx-size/2:.1f} {cy-size/2:.1f}) scale({k:.3f})" class="{cls}" style="{style}"/>')


# ------------------------------------------------------------------ terminal chrome
def section(doc, x, y, w, title, right="", delay=0.0):
    doc.add(f'<rect x="{x}" y="{y}" width="{w}" height="19" fill="{ORANGE}" class="ld" style="{d(delay)}"/>')
    doc.t(x + 7, y + 14, title, 12.5, "sb", BLACK, cls="ld", style=d(delay))
    if right:
        doc.t(x + w - 7, y + 14, right, 11, "m", BLACK, "end", cls="ld", style=d(delay))


def field(doc, x, y, text, size=11.5):
    w = tw(text, size, "m") + 10
    doc.add(f'<rect x="{x}" y="{y-12.5}" width="{w:.1f}" height="17" fill="{ORANGE}"/>')
    doc.t(x + 5, y, text, size, "m", BLACK)
    return x + w


def func_bar(doc, y, code, title, items=("91) Actions", "92) Export", "93) Settings"), right_note=""):
    """Command line + red menu bar, as at the top of every terminal function."""
    W = doc.w
    gid = doc.uid("rb")
    doc.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{RED_BAR_TOP}"/>'
                    f'<stop offset="1" stop-color="{RED_BAR_BOT}"/></linearGradient>')
    doc.add(f'<rect x="0" y="{y}" width="{W}" height="26" fill="url(#{gid})"/>')
    box_w = tw(code, 12.5, "mb") + 30
    doc.add(f'<rect x="6" y="{y+4}" width="{box_w:.1f}" height="18" fill="{BLACK}" stroke="#5a1210"/>')
    ex = doc.t(12, y + 17.5, code, 12.5, "mb", AMBER)
    doc.add(f'<rect x="{ex+3:.1f}" y="{y+8}" width="7" height="12" fill="{AMBER}" class="blink"/>')
    gx = 6 + box_w + 5
    doc.add(f'<rect x="{gx:.1f}" y="{y+4}" width="30" height="18" rx="2" fill="#1f8f3a"/>')
    doc.t(gx + 15, y + 17, "GO", 11, "mb", BLACK, "middle")
    x = gx + 46
    for it in items:
        x = doc.t(x, y + 17.5, it, 12, "m", WHITE) + 5
        caret(doc, x, y + 16)
        x += 22
    doc.t(W - 10, y + 17.5, title, 13, "sb", WHITE, "end")
    if right_note:
        doc.t(W - 10 - tw(title, 13, "sb") - 16, y + 17.5, right_note, 11, "m", "#ffd2cc", "end")


# ------------------------------------------------------------------ data
def load_data():
    contrib = json.loads((ROOT / "data/contributions.json").read_text())
    contrib = {dt.date.fromisoformat(k): int(v) for k, v in contrib.items()}
    stats = json.loads((ROOT / "data/stats.json").read_text())
    asof = dt.date.fromisoformat(stats["as_of"]) if "as_of" in stats else dt.date.today()
    return contrib, stats, asof


# ------------------------------------------------------------------ header (DES screen)
NEWS = [
    ("10/19", "Emoji vendor classifier: ConvNeXt + DINOv2 stack reaches 0.98663 on the public leaderboard"),
    ("10/04", "Wikipedia-game study maps 236M links across 2.78M French Wikipedia pages"),
    ("09/16", "Axiome v3.0.0 ships as a standalone portfolio app for Windows and macOS"),
    ("09/07", "LogReg4MNIST: a strictly linear model hits 98.75% test accuracy from 1,000 digits"),
    ("02/14", "Soussan cracks Jane Street's \"Subtiles 2\" puzzle and makes the official leaderboard"),
]

EVENTS = [
    ("2026-02-10", "A", "Portfolio Analysis Engine v2"),
    ("2026-02-14", "B", "Jane Street puzzle solved"),
    ("2026-05-04", "C", "Joins Deloitte (Casablanca)"),
    ("2026-09-16", "D", "Axiome v3.0.0 released"),
    ("2026-10-19", "E", "Emoji LB 0.98663"),
]


def header(contrib, stats, asof):
    W, H = 1000, 584
    doc = Doc(W, H, "Josh E. Soussan — terminal-style profile. BSc AI, Data & Management Sciences at "
                    "CentraleSupélec × ESSEC, GPA 4.00/4. Quantitative finance and applied AI. "
                    "Open to a 3-month summer internship.")
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/>')

    # line 1: security + quote
    sec = "JES FP Equity"
    bw = tw(sec, 12.5, "mb") + 12
    doc.add(f'<rect x="6" y="5" width="{bw:.1f}" height="18" fill="{AMBER}"/>')
    doc.t(12, 18.5, sec, 12.5, "mb", BLACK)
    x = 6 + bw + 14
    tri(doc, x + 5, 17, 9)
    x = doc.run(x + 14, 19, [("4.00", "mb", WHITE), ("/4.00", "m", AMBER), ("  GPA", "m", GREY)], 14)
    ytd = sum(v for k, v in contrib.items() if k.year == asof.year and k <= asof)
    x = doc.run(x + 26, 18.5, [("At ", "m", GREY), (asof.strftime("%d-%b-%y"), "m", WHITE),
                               ("   Vol ", "m", GREY), (f"{ytd} contrib YTD", "m", WHITE),
                               ("   Repos ", "m", GREY), (str(stats["public_repos"]), "m", WHITE)], 12)
    doc.t(W - 10, 18.5, "Paris · CET", 12, "m", GREY, "end")

    func_bar(doc, 28, "SOUSSAN DES", "Security Description: Profile", ("96) Actions", "97) Export", "98) Settings"))


    # ---- left column
    L, LW = 6, 556
    y = 88
    section(doc, L, y, LW, "Description", "BIO »", 0.05)
    desc = ("Josh E. Soussan is a BSc student in AI, Data & Management Sciences at CentraleSupélec × ESSEC, "
            "with a perfect 4.00/4 GPA. He builds quantitative tools where finance meets machine learning: "
            "portfolio optimisation, risk and valuation engines, forecasting ensembles and LLM agents, "
            "shipped as real software. Previously on desks at LCH (London Stock Exchange Group), "
            "SIX Financial Information and Deloitte.")
    y += 37
    for i, ln in enumerate(wrap(desc, 14.5, "s", LW - 14)):
        doc.t(L + 6, y + i * 19.5, ln, 14.5, "s", WHITE, cls="ld", style=d(.12 + i * .05))
    y += len(wrap(desc, 14.5, "s", LW - 14)) * 19.5 + 2

    section(doc, L, y, LW, "Key Data", delay=.3)
    kd = [("Name", "Josh E. Soussan", WHITE), ("Based", "Paris, France", WHITE),
          ("School", "CentraleSupélec × ESSEC", WHITE), ("Program", "BSc AIDAMS, 2024–2028", WHITE),
          ("Languages", "FR · EN (C2) · ES (B2)", WHITE), ("Status", "Open to summer internship", GREEN)]
    y += 37
    for i, (k, v, c) in enumerate(kd):
        cx = L + 6 + (i % 2) * 280
        cy = y + (i // 2) * 21
        doc.t(cx, cy, k, 11.5, "m", AMBER, cls="ld", style=d(.35 + i * .04))
        doc.t(cx + 82, cy, v, 13.5, "sb" if c == GREEN else "s", c, cls="ld", style=d(.35 + i * .04))
    y += 3 * 21 - 4

    section(doc, L, y, LW, "Key Indicators", "Value     Chg", .5)
    days30 = sum(v for k, v in contrib.items() if (asof - k).days < 30 and k <= asof)
    ki = [("GPA (out of 4.00)", "4.00", "max", GREY),
          ("Best public leaderboard (CV)", "0.98663", "+0.00040", GREEN),
          ("MNIST test acc., linear only", "98.75%", "+4.15pt", GREEN),
          ("Public repositories", str(stats["public_repos"]), "", GREEN),
          (f"Contributions {asof.year} YTD", str(ytd), f"+{days30} 30d" if days30 else "", GREEN)]
    y += 36
    for i, (k, v, chg, c) in enumerate(ki):
        cy = y + i * 20.5
        st = d(.55 + i * .05)
        if i % 2 == 0:
            doc.add(f'<rect x="{L}" y="{cy-14.5}" width="{LW}" height="20.5" fill="{ROW}" class="ld" style="{st}"/>')
        doc.t(L + 6, cy, f"{31+i})", 12, "m", AMBER, cls="ld", style=st)
        doc.t(L + 40, cy, k, 13.5, "s", WHITE, cls="ld", style=st)
        doc.t(L + 450, cy, v, 13, "mb", WHITE, "end", cls="ld", style=st)
        if chg:
            doc.t(L + LW - 6, cy, chg, 12, "m", c, "end", cls="ld", style=st)
    left_bottom = y + 5 * 20.5 - 8

    # ---- right column: GP chart
    R, RW = 576, 418
    y = 88
    section(doc, R, y, RW, "GP  Contributions, cumulative", "Line Chart", .1)
    fy = 125
    x = doc.t(R + 2, fy, "Range", 11.5, "m", WHITE) + 6
    start = dt.date(asof.year, 1, 1)
    x = field(doc, x, fy, start.strftime("%m/%d/%y")) + 4
    x = doc.t(x, fy, "-", 11.5, "m", WHITE) + 4
    x = field(doc, x, fy, asof.strftime("%m/%d/%y")) + 10
    x = doc.t(x, fy, "Period", 11.5, "m", WHITE) + 6
    x = field(doc, x, fy, "Weekly") + 10
    x = doc.t(x, fy, "Src", 11.5, "m", WHITE) + 6
    field(doc, x, fy, "GitHub")

    cx0, cx1, cy0, cy1 = R, R + RW, 136, 318
    px0, px1, py0, py1 = cx0 + 8, cx1 - 48, cy0 + 26, cy1 - 10
    gid = doc.uid("nv")
    doc.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{NAVY_TOP}"/>'
                    f'<stop offset="1" stop-color="{NAVY_BOT}"/></linearGradient>')
    aid = doc.uid("ar")
    doc.defs.append(f'<linearGradient id="{aid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3f86f0" stop-opacity=".55"/>'
                    f'<stop offset="1" stop-color="#3f86f0" stop-opacity=".02"/></linearGradient>')
    doc.add(f'<rect x="{cx0}" y="{cy0}" width="{RW}" height="{cy1-cy0+56}" fill="url(#{gid})"/>')

    # weekly series
    weeks = []
    wk = start
    while wk <= asof:
        end = min(wk + dt.timedelta(days=6), asof)
        weeks.append((wk, sum(v for k, v in contrib.items() if wk <= k <= end)))
        wk += dt.timedelta(days=7)
    cum, s = [], 0
    for _, v in weeks:
        s += v
        cum.append(s)
    top = max(cum[-1], 1)
    nice = max(10, math.ceil(top * 1.15 / 10) * 10)
    span = (asof - start).days or 1
    X = lambda day: px0 + (day - start).days / span * (px1 - px0)
    Y = lambda v: py1 - v / nice * (py1 - py0)
    for i in range(5):
        v = nice * i / 4
        yy = Y(v)
        doc.add(f'<line x1="{px0}" y1="{yy:.1f}" x2="{px1}" y2="{yy:.1f}" stroke="#2a4470" stroke-dasharray="2 3"/>')
        doc.t(px1 + 6, yy + 4, f"{v:.0f}", 10.5, "m", SOFT)
    for mth in range(1, asof.month + 1):
        day = dt.date(asof.year, mth, 1)
        xx = X(day)
        doc.add(f'<line x1="{xx:.1f}" y1="{py0}" x2="{xx:.1f}" y2="{cy1+46}" stroke="#1d3358" stroke-dasharray="2 3"/>')
        doc.t(xx + 3, cy1 + 66, day.strftime("%b"), 10.5, "m", SOFT)
    pts = [(X(w + dt.timedelta(days=6)) if w + dt.timedelta(days=6) <= asof else X(asof), Y(c)) for (w, _), c in zip(weeks, cum)]
    pts = [(px0, Y(0))] + pts
    line = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    plen = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    doc.css.append(f"@keyframes gp{{from{{stroke-dashoffset:{plen:.0f}}}to{{stroke-dashoffset:0}}}}")
    doc.add(f'<path d="{line} L{pts[-1][0]:.1f} {py1} L{px0} {py1}Z" fill="url(#{aid})" class="ld" style="{d(1.5)};animation-duration:.9s"/>')
    doc.add(f'<path d="{line}" fill="none" stroke="{WHITE}" stroke-width="1.8" stroke-linejoin="round" '
            f'stroke-dasharray="{plen:.0f}" style="animation:gp 1.9s cubic-bezier(.45,.05,.35,1) .3s both"/>')
    lx, ly = pts[-1]
    doc.add(f'<g class="ld" style="{d(2.1)}"><rect x="{px1+2}" y="{ly-8:.1f}" width="44" height="16" fill="{AMBER}"/>'
            f'<line x1="{lx:.1f}" y1="{ly:.1f}" x2="{px1+2}" y2="{ly:.1f}" stroke="{AMBER}" stroke-dasharray="2 2"/></g>')
    doc.t(px1 + 24, ly + 4, str(cum[-1]), 11, "mb", BLACK, "middle", cls="ld", style=d(2.1))
    # events
    used = []
    for date_s, letter, _ in EVENTS:
        day = dt.date.fromisoformat(date_s)
        if not (start <= day <= asof):
            continue
        idx = min(range(len(weeks)), key=lambda i: abs((weeks[i][0] - day).days))
        ex, ey = X(day), Y(cum[idx])
        by = ey - 24
        while any(abs(ex - ux) < 14 and abs(by - uy) < 14 for ux, uy in used):
            by -= 16
        by = max(by, cy0 + 2)
        used.append((ex, by))
        dl = .3 + 1.9 * (day - start).days / span
        doc.add(f'<g class="ld" style="{d(dl)}"><line x1="{ex:.1f}" y1="{by+12:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{AMBER}" stroke-width="1"/>'
                f'<rect x="{ex-6.5:.1f}" y="{by:.1f}" width="13" height="13" fill="{AMBER}"/></g>')
        doc.t(ex, by + 10.5, letter, 10.5, "mb", BLACK, "middle", cls="ld", style=d(dl))
    # volume
    vy0, vy1 = cy1 + 6, cy1 + 46
    doc.add(f'<line x1="{px0}" y1="{vy0}" x2="{px1}" y2="{vy0}" stroke="#2a4470"/>')
    vmax = max([v for _, v in weeks] + [1])
    bw = (px1 - px0) / max(len(weeks), 1) * .7
    for i, (w, v) in enumerate(weeks):
        if not v:
            continue
        hh = v / vmax * (vy1 - vy0 - 4)
        xx = X(w) + 1
        doc.add(f'<rect x="{xx:.1f}" y="{vy1-hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="{GREEN}" opacity=".85" class="rise" style="{d(.4+i*.02)}"/>')
    doc.t(px0 + 2, vy0 + 13, "Volume (weekly)", 10.5, "m", WHITE)
    doc.t(px1 + 6, vy1, f"{vmax}", 10.5, "m", SOFT)
    # legend
    ly0 = cy1 + 86
    for i, (_, letter, label) in enumerate(EVENTS):
        lx = R + 4 + (i % 2) * 212
        lyy = ly0 + (i // 2) * 18
        doc.add(f'<rect x="{lx}" y="{lyy-10}" width="12" height="12" fill="{AMBER}"/>')
        doc.t(lx + 6, lyy, letter, 10, "mb", BLACK, "middle")
        doc.t(lx + 18, lyy, label, 12.5, "s", WHITE)
    right_bottom = ly0 + 2 * 18 + 4

    # ---- news, full width
    y = max(left_bottom, right_bottom) + 6
    section(doc, 6, y, W - 12, "Top News", f"{len(NEWS)} stories  ·  BN", 1.0)
    y += 36
    for i, (date, head) in enumerate(NEWS):
        cy = y + i * 20.5
        st = d(1.05 + i * .07)
        if i % 2 == 0:
            doc.add(f'<rect x="6" y="{cy-14.5}" width="{W-12}" height="20.5" fill="{ROW}" class="ld" style="{st}"/>')
        if i == 0:
            doc.add(f'<rect x="6" y="{cy-14.5}" width="{W-12}" height="20.5" fill="{AMBER}" class="flash" style="animation-delay:1.6s" opacity="0"/>')
        x = doc.t(12, cy, f"{i+1})", 12, "m", AMBER, cls="ld", style=st) + 10
        x = doc.t(x, cy, "BN", 12, "mb", AMBER, cls="ld", style=st) + 10
        x = doc.t(x, cy, date, 12, "m", SOFT, cls="ld", style=st) + 14
        doc.t(x, cy, head, 14, "s", WHITE, cls="ld", style=st)
    return doc


# ------------------------------------------------------------------ clickable tab strip
TABS = [("1) Profile", "profile"), ("2) Track Record", "track-record"), ("3) Projects", "projects"),
        ("4) Side Projects", "side-projects"), ("5) Stack", "stack"), ("6) Activity", "activity")]


def tab_strip():
    """One small SVG per tab (each wrapped in a link in the README) plus a filler on the right."""
    out, used = [], 0
    for i, (label, anchor) in enumerate(TABS):
        w = round(tw(label, 12, "m") + 22 + (6 if i == 0 else 0) + 3)
        doc = Doc(w, 24, label)
        doc.add(f'<rect width="{w}" height="24" fill="{BLACK}"/>')
        x0 = 6 if i == 0 else 0
        active = i == 0
        doc.add(f'<rect x="{x0}" y="2" width="{w-3-x0}" height="20" fill="{AMBER if active else "#1c1c1c"}"/>')
        doc.t(x0 + 11, 16, label, 12, "mb" if active else "m", BLACK if active else SOFT)
        out.append((f"tab-{anchor}.svg", doc.render(), anchor, w))
        used += w
    w = 1000 - used
    doc = Doc(w, 24, "Page 1/1")
    doc.add(f'<rect width="{w}" height="24" fill="{BLACK}"/>')
    doc.t(w - 10, 16, "Page 1/1", 11.5, "m", GREY, "end")
    out.append(("tab-fill.svg", doc.render(), None, w))
    return out


# ------------------------------------------------------------------ contact bar
def contact():
    W, H = 1000, 40
    doc = Doc(W, H, "Contact: josh.soussan.candidatures@gmail.com. Open to a 3-month summer internship.")
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/><rect x=".5" y=".5" width="{W-1}" height="{H-1}" fill="none" stroke="{RULE}"/>')
    doc.add(f'<rect x="6" y="8" width="52" height="24" fill="{RED_BAR_TOP}"/>')
    doc.t(32, 25, "MSG", 13, "mb", WHITE, "middle")
    mail = "josh.soussan.candidatures@gmail.com"
    mw = tw(mail, 13.5, "mb") + 16
    group = tw("To", 12.5, "m") + 8 + mw + 8 + 38
    x = (W - group) / 2
    x = doc.t(x, 25, "To", 12.5, "m", AMBER) + 8
    doc.add(f'<rect x="{x:.1f}" y="8" width="{mw:.1f}" height="24" fill="{ORANGE}"/>')
    doc.t(x + 8, 25, mail, 13.5, "mb", BLACK)
    x += mw + 8
    doc.add(f'<rect x="{x:.1f}" y="8" width="38" height="24" rx="2" fill="#1f8f3a"/>')
    doc.t(x + 19, 24.5, "GO", 12.5, "mb", BLACK, "middle")
    txt = "Open to summer internship"
    tx = W - 12 - tw(txt, 14, "sb")
    doc.add(f'<circle cx="{tx-12:.1f}" cy="20" r="4.5" fill="{GREEN}"/>'
            f'<circle cx="{tx-12:.1f}" cy="20" r="4.5" fill="none" stroke="{GREEN}" class="pulse"/>')
    doc.css.append(".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2s ease-out infinite}"
                   "@keyframes pulse{from{transform:scale(1);opacity:.9}to{transform:scale(2.6);opacity:0}}")
    doc.t(tx, 25, txt, 14, "sb", GREEN)
    return doc.render()


# ------------------------------------------------------------------ career
CAREER = [
    ("2026 – now", "ESSEC Club of Economics", "Portfolio Analyst", "Cergy", (2026, 1), None,
     "Fundamental equity research (DCF, trading multiples, sensitivity analysis) for a student-managed fund, "
     "and in-house Python tools for portfolio optimisation, probabilistic valuation and AI forecasting."),
    ("May–Aug 2026", "Deloitte Extended Services", "Accounting & Tax Intern", "Casablanca", (2026, 5), (2026, 8),
     "Automated bank reconciliations and FX allowance requests in Python, saving ~4 h a week (scripts still used by the team). "
     "Built a complete VAT refund claim for a major French entity, end to end."),
    ("Summer 2025", "SIX Financial Information", "Summer Intern", "Paris", (2025, 6), (2025, 8),
     "Built an AI integration layer (MCP) on Apache Superset for management reporting, and an AI system that parses "
     "SEC filings into structured Excel inputs for valuation models."),
    ("Summer 2023", "LCH SA · London Stock Exchange Group", "Summer Intern", "Paris", (2023, 6), (2023, 8),
     "Contributed to an Initial Margin model for cleared digital-asset derivatives, working across Risk and IT Security. "
     "Treasury collateral analysis and daily liquidity optimisation."),
]


def career(asof):
    W = 1000
    rows = []
    for r in CAREER:
        rows.append((r, wrap(r[6], 13.5, "s", 730)))
    H = 26 + 8 + 24 + sum(30 + 18 * len(ls) + 10 for _, ls in rows) + 6
    doc = Doc(W, H, "Track record: " + "; ".join(f"{r[1]}, {r[2]} ({r[0]})" for r in CAREER))
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/>')
    func_bar(doc, 0, "CAREER", "Track Record", right_note=f"{len(CAREER)} positions")
    y = 34
    T0, T1 = 795, 988
    a0, a1 = dt.date(2023, 1, 1), dt.date(2027, 1, 1)
    TX = lambda dd: T0 + (dd - a0).days / (a1 - a0).days * (T1 - T0)
    doc.add(f'<rect x="0" y="{y}" width="{W}" height="22" fill="#141414"/>')
    for x, lab in [(10, "#"), (40, "Firm / Role"), (580, "Period"), (695, "Loc.")]:
        doc.t(x, y + 15, lab, 11.5, "mb", AMBER)
    for yr in range(2023, 2027):
        xx = TX(dt.date(yr, 1, 1))
        doc.t(xx + 3, y + 15, str(yr), 11, "m", AMBER)
    y += 22
    nowx = TX(asof)
    top_y = y
    for i, ((period, firm, role, loc, s, e, _), lines) in enumerate(rows):
        h = 30 + 18 * len(lines) + 10
        st = d(.15 + i * .12)
        if i % 2 == 0:
            doc.add(f'<rect x="0" y="{y}" width="{W}" height="{h}" fill="{ROW}"/>')
        doc.add(f'<line x1="0" y1="{y+h}" x2="{W}" y2="{y+h}" stroke="{RULE}"/>')
        by = y + 21
        doc.t(10, by, f"{i+1})", 12.5, "m", AMBER, cls="ld", style=st)
        x = doc.t(40, by, firm, 15, "sb", WHITE, cls="ld", style=st)
        doc.t(x + 12, by, role, 14, "s", AMBER, cls="ld", style=st)
        doc.t(580, by, period, 12, "m", WHITE, cls="ld", style=st)
        doc.t(695, by, loc, 12, "m", SOFT, cls="ld", style=st)
        for j, ln in enumerate(lines):
            doc.t(40, by + 21 + j * 18, ln, 13.5, "s", "#c9c9c9", cls="ld", style=d(.25 + i * .12))
        # timeline bar
        sd = dt.date(*s, 1)
        ed = asof if e is None else (dt.date(e[0] + (e[1] == 12), e[1] % 12 + 1, 1) - dt.timedelta(days=1))
        x0, x1 = TX(sd), TX(ed)
        col = GREEN if e is None else AMBER
        doc.add(f'<rect x="{x0:.1f}" y="{by-9}" width="{max(x1-x0, 5):.1f}" height="10" fill="{col}" class="grow" style="{d(.4+i*.12)}"/>')
        if e is None:
            doc.add(f'<circle cx="{x1:.1f}" cy="{by-4}" r="4" fill="{GREEN}"/>')
            doc.t(x1 - 4, by + 13, "ACTIVE", 10, "mb", GREEN, "end", cls="ld", style=d(1))
        y += h
    for yr in range(2023, 2027):
        xx = TX(dt.date(yr, 1, 1))
        doc.add(f'<line x1="{xx:.1f}" y1="{top_y}" x2="{xx:.1f}" y2="{y}" stroke="#262626" stroke-dasharray="2 3"/>')
    doc.add(f'<line x1="{nowx:.1f}" y1="{top_y}" x2="{nowx:.1f}" y2="{y}" stroke="{GREEN}" stroke-opacity=".5" stroke-dasharray="3 3"/>')
    doc.add(f'<line x1="{T0-10}" y1="{top_y-22}" x2="{T0-10}" y2="{y}" stroke="{RULE}"/>')
    return doc.render()


# ------------------------------------------------------------------ section bar
def bar(code, title, note):
    doc = Doc(1000, 26, f"{title}. {note}")
    func_bar(doc, 0, code, title, right_note=note)
    return doc.render()


# ------------------------------------------------------------------ project panels
def viz_frontier(doc, x0, y0, x1, y1):
    rnd = random.Random(4)
    pts = []
    for _ in range(170):
        sig = rnd.uniform(.1, 1)
        top = math.sqrt(max(sig - .08, 0)) * .95
        mu = top - abs(rnd.gauss(0, .22)) - .02
        if mu > 0:
            pts.append((sig, mu))
    sx = lambda s: x0 + 10 + s * (x1 - x0 - 16)
    sy = lambda m: y1 - 12 - m * (y1 - y0 - 18) / 1.0
    for k, (s, m) in enumerate(pts):
        sh = m / s
        col = AMBER if sh > .9 else ("#7fb3ff" if sh > .5 else "#3a5f99")
        doc.add(f'<circle cx="{sx(s):.1f}" cy="{sy(m):.1f}" r="1.7" fill="{col}" class="ld" style="{d(.3+(k%5)*.12)}"/>')
    fr = [(s / 50, math.sqrt(max(s / 50 - .08, 0)) * .95) for s in range(5, 51)]
    path = "M" + " L".join(f"{sx(s):.1f} {sy(m):.1f}" for s, m in fr)
    L = sum(math.dist((sx(fr[i][0]), sy(fr[i][1])), (sx(fr[i + 1][0]), sy(fr[i + 1][1]))) for i in range(len(fr) - 1))
    doc.css.append(f"@keyframes fr{{from{{stroke-dashoffset:{L:.0f}}}to{{stroke-dashoffset:0}}}}")
    doc.add(f'<path d="{path}" fill="none" stroke="{WHITE}" stroke-width="1.6" stroke-dasharray="{L:.0f}" style="animation:fr 1.4s ease-in-out .8s both"/>')
    best = max(fr[1:], key=lambda p: (p[1] - .02) / p[0])
    bx, by = sx(best[0]), sy(best[1])
    doc.add(f'<polygon points="{bx},{by-6} {bx+5},{by} {bx},{by+6} {bx-5},{by}" fill="{GREEN}" class="ld" style="{d(1.9)}"/>')
    doc.add(f'<rect x="{bx-80:.1f}" y="{by-25:.1f}" width="72" height="15" fill="{BLACK}" class="ld" style="{d(1.9)}"/>')
    doc.t(bx - 44, by - 13.5, "max Sharpe", 10.5, "m", GREEN, "middle", cls="ld", style=d(1.9))
    doc.t(x1 - 2, y1 - 1, "σ", 11, "m", GREY, "end")
    doc.t(x0 + 2, y0 + 10, "μ", 11, "m", GREY)


def viz_montecarlo(doc, x0, y0, x1, y1):
    rnd = random.Random(8)
    n, steps = 36, 40
    paths = []
    for _ in range(n):
        v, p = 0.0, [0.0]
        for _ in range(steps):
            v += .012 + rnd.gauss(0, .055)
            p.append(v)
        paths.append(p)
    lo = min(min(p) for p in paths)
    hi = max(max(p) for p in paths)
    X = lambda i: x0 + 6 + i / steps * (x1 - x0 - 46)
    Y = lambda v: y1 - 8 - (v - lo) / (hi - lo) * (y1 - y0 - 16)
    for k, p in enumerate(paths):
        doc.add(f'<path d="M' + " L".join(f"{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(p)) +
                f'" fill="none" stroke="#4d8ef0" stroke-opacity=".28" stroke-width="1" class="ld" style="{d(.3+k*.015)}"/>')
    for q, col, lab in [(.05, RED, "P5"), (.5, WHITE, "P50"), (.95, GREEN, "P95")]:
        qs = [sorted(p[i] for p in paths)[int(q * (n - 1))] for i in range(steps + 1)]
        doc.add(f'<path d="M' + " L".join(f"{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(qs)) +
                f'" fill="none" stroke="{col}" stroke-width="1.5" class="ld" style="{d(1.0)}"/>')
        doc.t(X(steps) + 5, Y(qs[-1]) + 4, lab, 10.5, "mb", col, cls="ld", style=d(1.1))


def viz_leaderboard(doc, x0, y0, x1, y1):
    vals = [("s02", .96618), ("s04", .98238), ("s03", .98380), ("s07", .98582), ("s06", .98582), ("s05", .98623), ("A", .98663)]
    lo, hi = .960, .988
    n = len(vals)
    bw = (x1 - x0 - 50) / n
    Y = lambda v: y1 - 14 - (v - lo) / (hi - lo) * (y1 - y0 - 30)
    for g in (.965, .975, .985):
        doc.add(f'<line x1="{x0}" y1="{Y(g):.1f}" x2="{x1-40}" y2="{Y(g):.1f}" stroke="#262626" stroke-dasharray="2 3"/>')
        doc.t(x1 - 2, Y(g) + 4, f"{g:.3f}", 10, "m", GREY, "end")
    for i, (lab, v) in enumerate(vals):
        bx = x0 + 4 + i * bw
        last = i == n - 1
        doc.add(f'<rect x="{bx:.1f}" y="{Y(v):.1f}" width="{bw*.68:.1f}" height="{y1-14-Y(v):.1f}" '
                f'fill="{GREEN if last else "#3a5f99"}" class="rise" style="{d(.3+i*.08)}"/>')
        doc.t(bx + bw * .34, y1 - 2, lab, 9.5, "m", GREY, "middle")
    lx = x0 + 4 + (n - 1) * bw + bw * .34
    doc.t(lx - 4, Y(vals[-1][1]) - 6, "0.98663", 11, "mb", GREEN, "end", cls="ld", style=d(1))


def viz_mnist(doc, x0, y0, x1, y1):
    rows = [("v2  sklearn, pixels", .9460, "#3a5f99"), ("v3  k-means conv feats", .9875, GREEN)]
    lo, hi = .90, 1.0
    X = lambda v: x0 + 4 + (v - lo) / (hi - lo) * (x1 - x0 - 10)
    for g in (.92, .94, .96, .98, 1.0):
        doc.add(f'<line x1="{X(g):.1f}" y1="{y0+4}" x2="{X(g):.1f}" y2="{y1-14}" stroke="#262626" stroke-dasharray="2 3"/>')
        doc.t(X(g), y1 - 2, f"{g*100:.0f}", 10, "m", GREY, "middle")
    for i, (lab, v, col) in enumerate(rows):
        yy = y0 + 22 + i * 44
        doc.t(x0 + 4, yy - 6, lab, 11, "m", SOFT)
        doc.add(f'<rect x="{X(lo):.1f}" y="{yy}" width="{X(v)-X(lo):.1f}" height="16" fill="{col}" class="grow" style="{d(.4+i*.3)}"/>')
        doc.t(X(v) - 5, yy + 12.5, f"{v*100:.2f}%", 11.5, "mb", BLACK, "end", cls="ld", style=d(.9 + i * .3))


def viz_graph(doc, x0, y0, x1, y1):
    cx, cy = (x0 + x1) / 2 - 34, (y0 + y1) / 2 + 6
    rnd = random.Random(2)
    nodes = [(cx, cy)]
    for k in range(9):
        a = k / 9 * 2 * math.pi + .3
        r = 40 + rnd.uniform(-6, 8)
        nodes.append((cx + r * 1.45 * math.cos(a), cy + r * math.sin(a)))
    edges = [(0, k, "v") for k in (1, 2, 4, 6, 7)] + [(0, 3, "p"), (0, 8, "p"), (2, 5, "v"), (6, 9, "r"), (0, 9, "r"), (4, 5, "p")]
    style = {"v": (GREEN, ""), "p": (AMBER, 'stroke-dasharray="5 4" class="march"'), "r": (RED, 'stroke-dasharray="1.5 3"')}
    doc.css.append(".march{animation:march 1.2s linear infinite}@keyframes march{to{stroke-dashoffset:-9}}")
    for a, b, kd in edges:
        col, ex = style[kd]
        doc.add(f'<line x1="{nodes[a][0]:.1f}" y1="{nodes[a][1]:.1f}" x2="{nodes[b][0]:.1f}" y2="{nodes[b][1]:.1f}" stroke="{col}" stroke-width="1.4" {ex}/>')
    for k, (nx, ny) in enumerate(nodes):
        r = 7 if k == 0 else 4.5
        doc.add(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{r}" fill="{BLACK}" stroke="{WHITE if k == 0 else SOFT}" stroke-width="1.5" class="ld" style="{d(.2+k*.06)}"/>')
    for i, (lab, col) in enumerate([("verified", GREEN), ("predicted", AMBER), ("rumour", RED)]):
        yy = y0 + 12 + i * 15
        doc.add(f'<rect x="{x1-74}" y="{yy-7}" width="9" height="4" fill="{col}"/>')
        doc.t(x1 - 60, yy, lab, 10.5, "m", col)


def viz_ccdf(doc, x0, y0, x1, y1):
    out_q = [(21, .75), (40, .5), (93, .25), (203, .1), (612, .01)]
    in_q = [(4, .75), (14, .5), (59, .25), (160, .1), (863, .01)]
    lx0, lx1, ly0, ly1 = math.log10(2), math.log10(1500), math.log10(.006), 0
    X = lambda v: x0 + 26 + (math.log10(v) - lx0) / (lx1 - lx0) * (x1 - x0 - 34)
    Y = lambda p: y1 - 14 - (math.log10(p) - ly0) / (ly1 - ly0) * (y1 - y0 - 22)
    for v in (10, 100, 1000):
        doc.add(f'<line x1="{X(v):.1f}" y1="{y0+4}" x2="{X(v):.1f}" y2="{y1-14}" stroke="#262626" stroke-dasharray="2 3"/>')
        doc.t(X(v), y1 - 2, f"{v:,}", 10, "m", GREY, "middle")
    for p, lab in [(.01, "1%"), (.1, "10%"), (1, "100%")]:
        doc.t(x0 + 22, Y(p) + 4, lab, 9.5, "m", GREY, "end")
    for k, (series, col, lab) in enumerate([(out_q, AMBER, "out-degree"), (in_q, BLUE, "in-degree")]):
        pts = [(X(v), Y(p)) for v, p in series]
        doc.add(f'<path d="M' + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts) + f'" fill="none" stroke="{col}" stroke-width="1.6" class="ld" style="{d(.4+k*.3)}"/>')
        for j, (a, b) in enumerate(pts):
            doc.add(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="2.8" fill="{col}" class="ld" style="{d(.4+k*.3+j*.07)}"/>')
        doc.t(x1 - 4, y0 + 12 + k * 15, lab, 10.5, "m", col, "end")


def viz_grid(doc, x0, y0, x1, y1):
    n = 9
    s = min((x1 - x0 - 70) / n, (y1 - y0 - 6) / n)
    gx, gy = x0 + 4, y0 + 2
    rnd = random.Random(26)
    shades = [AMBER, "#c77800", "#7a4a00", "#3a5f99", "#4d8ef0", "#1c1c1c"]
    for r in range(n):
        for c in range(n):
            col = shades[(r // 3 * 3 + c // 3 + rnd.randint(0, 1)) % len(shades)]
            doc.add(f'<rect x="{gx+c*s:.1f}" y="{gy+r*s:.1f}" width="{s-1.5:.1f}" height="{s-1.5:.1f}" fill="{col}" class="ld" style="{d(.2+(r+c)*.04)}"/>')
    tx = gx + n * s + 10
    doc.t(tx, y0 + 40, "Answer", 11, "m", AMBER)
    doc.t(tx, y0 + 64, "9072", 20, "mb", GREEN, cls="ld", style=d(1.0))
    doc.t(tx, y0 + 88, "min × max", 10.5, "m", GREY)
    doc.t(tx, y0 + 102, "row sums", 10.5, "m", GREY)


def viz_flow(doc, x0, y0, x1, y1):
    boxes = [("LLM host", WHITE), ("MCP server", AMBER), ("Vision model", GREEN)]
    bw, bh = 112, 24
    bx = x0 + 2
    gap = (y1 - y0 - 3 * bh - 6) / 2
    ys = [y0 + 2 + i * (bh + gap) for i in range(3)]
    for i, (lab, col) in enumerate(boxes):
        doc.add(f'<rect x="{bx}" y="{ys[i]:.1f}" width="{bw}" height="{bh}" fill="{BLACK}" stroke="{col}" stroke-width="1.3" class="ld" style="{d(.2+i*.2)}"/>')
        doc.t(bx + bw / 2, ys[i] + 16.5, lab, 12, "m", col, "middle", cls="ld", style=d(.2 + i * .2))
    doc.css.append(".mv{animation:mv 1s linear infinite}@keyframes mv{to{stroke-dashoffset:-8}}")
    down = ["describe_image", "image + prompt"]
    up = ["text answer", "description"]
    for i in range(2):
        a, b = ys[i] + bh, ys[i + 1]
        dx, ux = bx + bw / 2 - 16, bx + bw / 2 + 16
        doc.add(f'<line x1="{dx}" y1="{a:.1f}" x2="{dx}" y2="{b-5:.1f}" stroke="{SOFT}" stroke-dasharray="4 4" class="mv"/>')
        tri(doc, dx, b - 1, 5, up=False, fill=SOFT)
        doc.add(f'<line x1="{ux}" y1="{b:.1f}" x2="{ux}" y2="{a+5:.1f}" stroke="{GREEN}" stroke-dasharray="4 4" class="mv"/>')
        tri(doc, ux, a + 5, 5, up=True, fill=GREEN)
        mid = (a + b) / 2
        lx = bx + bw + 10
        tri(doc, lx + 3, mid - 6, 4, up=False, fill=SOFT)
        doc.t(lx + 10, mid - 3, down[i], 10.5, "m", SOFT)
        tri(doc, lx + 3, mid + 10, 4, up=True, fill=GREEN)
        doc.t(lx + 10, mid + 12, up[i], 10.5, "m", GREEN)


PROJECTS = [
    dict(slug="axiome", code="AXIOME", name="Portfolio Management Platform", url="github.com/joshsssn/Axiome",
         desc="Desktop app to build, analyse, optimise and stress-test portfolios: Sharpe/Sortino/Calmar, VaR & CVaR, "
              "Markowitz frontier, backtests and crisis scenarios (2008, COVID, rate shocks).",
         fields=[("Release", "v3.0.0, Win + macOS"), ("Front", "React 19 · Tauri"), ("Engine", "FastAPI · PyPortfolioOpt"), ("Data", "yfinance · SQLite")],
         viz=("Efficient frontier", viz_frontier)),
    dict(slug="engine", code="PAE", name="Portfolio Analysis Engine", url="github.com/joshsssn/Portfolio-Analysis-Engine",
         desc="Rebuilds a fund from partial holdings, finds the utility-maximising allocation, values candidates "
              "with Monte Carlo DCF, and forecasts with a 7-model ensemble plus FinBERT + LLM sentiment.",
         fields=[("Valuation", "Monte Carlo DCF"), ("Risk", "Ledoit-Wolf · CVaR"), ("Forecast", "7-model ensemble"), ("NLP", "FinBERT + LLM")],
         viz=("Monte Carlo DCF paths", viz_montecarlo)),
    dict(slug="emoji", code="EMOJI", name="Emoji Vendor Classification", url="github.com/joshsssn/Computer-vision-final-project",
         desc="Which of 7 vendors drew an emoji? Fine-tuned ConvNeXt stacked with DINOv2/CLIP kNN and image "
              "metadata, 5-fold CV and pseudo-labelling ablations.",
         fields=[("Best LB", "0.98663 accuracy"), ("Data", "9,879 images"), ("Models", "ConvNeXt · DINOv2"), ("Team", "with E. Souied")],
         viz=("Public leaderboard by submission", viz_leaderboard)),
    dict(slug="mnist", code="LR4MNIST", name="LogReg4MNIST", url="github.com/joshsssn/LogReg4MNIST",
         desc="How far can a strictly linear classifier go with only 1,000 digits? Unsupervised k-means conv "
              "features, on-the-fly GPU augmentation, Optuna tuning and a CV ensemble.",
         fields=[("Test acc.", "98.75%"), ("Train set", "1,000 images"), ("Model", "softmax regression"), ("Tooling", "PyTorch · Optuna")],
         viz=("Test accuracy, %", viz_mnist)),
    dict(slug="scout", code="SCOUT", name="Football Scout Agent", url="github.com/nsalapete/FootballScoot…",
         desc="Neo4j graph of European transfers (7 leagues since 2015), link prediction and a LangGraph "
              "recruitment agent that tags every claim verified, predicted or rumour.",
         fields=[("Graph", "Neo4j · GDS"), ("Agent", "LangGraph"), ("Serving", "FastAPI · Docker"), ("Team", "4 students")],
         viz=("Levels of truth", viz_graph)),
    dict(slug="wiki", code="WIKI", name="Landmarks of the Wikipedia Game", url="github.com/joshsssn/DDS_final_project",
         desc="Full link graph of French Wikipedia built from raw dumps: are the hubs players use really the "
              "best shortcuts between two articles? BFS over 200,000 random pairs.",
         fields=[("Pages", "2.78M"), ("Links", "236M"), ("Storage", "CSR · DuckDB"), ("Team", "4 students")],
         viz=("Degree distribution, P(X > x)", viz_ccdf)),
    dict(slug="jane", code="JSPZ", name="Jane Street Puzzle: Subtiles 2", url="github.com/joshsssn/Jane-Street-Feb-26",
         desc="Solved Jane Street's February 2026 puzzle with an OR-Tools CP-SAT solver and parallel shape "
              "generation, with a write-up of the maths. Listed on the official leaderboard.",
         fields=[("Result", "Leaderboard"), ("Solver", "OR-Tools CP-SAT"), ("Answer", "9072"), ("Write-up", "PDF, maths")],
         viz=("Tiling search", viz_grid)),
    dict(slug="mcp", code="MCPV", name="mcp-vision-server", url="github.com/joshsssn/mcp-vision-server",
         desc="An MCP server that lets any LLM see a local image through an OpenAI-compatible vision endpoint. "
              "One tool, one line to install.",
         fields=[("Protocol", "MCP over stdio"), ("Install", "uvx, one line"), ("Backends", "vLLM · Ollama"), ("Lang", "Python")],
         viz=("Request flow", viz_flow)),
]


def project(p):
    W, H = 490, 268
    doc = Doc(W, H, f"{p['name']}: {p['desc']} " + "; ".join(f"{k}: {v}" for k, v in p["fields"]))
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/>')
    doc.add(f'<rect x="0" y="0" width="{W}" height="24" fill="{ORANGE}"/>')
    x = doc.t(8, 17, p["code"], 13, "mb", BLACK) + 10
    doc.t(x, 17, p["name"], 14, "sb", BLACK)
    doc.t(W - 26, 16.5, "OPEN", 11, "mb", BLACK, "end")
    arrow_ne(doc, W - 20, 18, 9, BLACK)
    lines = wrap(p["desc"], 13.5, "s", W - 20)[:3]
    for i, ln in enumerate(lines):
        doc.t(10, 44 + i * 18, ln, 13.5, "s", "#e4e4e4", cls="ld", style=d(.1 + i * .05))
    doc.add(f'<line x1="0" y1="102" x2="{W}" y2="102" stroke="{RULE}"/>')
    for i, (k, v) in enumerate(p["fields"]):
        yy = 126 + i * 26
        st = d(.25 + i * .06)
        doc.add(f'<rect x="0" y="{yy-17}" width="232" height="26" fill="{ROW if i % 2 == 0 else BLACK}" class="ld" style="{st}"/>')
        doc.t(10, yy, k, 11.5, "m", AMBER, cls="ld", style=st)
        size = 13.5
        while tw(v, size, "sb") > 232 - 86 and size > 10:
            size -= .5
        doc.t(86, yy, v, size, "sb", GREEN if i == 0 else WHITE, cls="ld", style=st)
    us = 10.5
    while tw(p["url"], us, "m") > 216 and us > 8:
        us -= .25
    doc.t(10, H - 12, p["url"], us, "m", GREY)
    doc.add(f'<line x1="240" y1="102" x2="240" y2="{H}" stroke="{RULE}"/>')
    title, fn = p["viz"]
    doc.t(250, 120, title, 11, "m", AMBER)
    fn(doc, 250, 130, W - 10, H - 10)
    doc.add(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" fill="none" stroke="#3a3a3a"/>')
    return doc.render()


# ------------------------------------------------------------------ activity heatmap
def activity(contrib, asof):
    W, H = 1000, 222
    end = asof
    start = end - dt.timedelta(days=end.weekday() + 1 + 52 * 7)  # a Sunday, 53 columns
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    total = sum(contrib.get(x, 0) for x in days)
    active = sum(1 for x in days if contrib.get(x, 0))
    best = max(days, key=lambda x: contrib.get(x, 0))
    streak = cur = 0
    for x in days:
        cur = cur + 1 if contrib.get(x, 0) else 0
        streak = max(streak, cur)
    doc = Doc(W, H, f"Contribution activity: {total} contributions in the last year, {active} active days, longest streak {streak} days.")
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/>')
    func_bar(doc, 0, "GH", "Contribution Activity", right_note=f"{total} in the last year")
    cell, gap = 14, 3
    gx, gy = 46, 58
    vmax = max([contrib.get(x, 0) for x in days] + [1])
    ramp = ["#161616", "#4a2e00", "#8a5400", "#d27f00", AMBER]

    def level(v):
        if v == 0:
            return 0
        return min(4, 1 + int(3 * math.log1p(v) / math.log1p(vmax) + .0001))

    last_m = None
    for x in days:
        col = (x - start).days // 7
        row = (x.weekday() + 1) % 7
        cx, cy = gx + col * (cell + gap), gy + row * (cell + gap)
        doc.add(f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="2" fill="{ramp[level(contrib.get(x, 0))]}"/>')
        if row == 0 and x.month != last_m and x.day <= 7:
            doc.t(cx, gy - 7, x.strftime("%b"), 11, "m", AMBER)
            last_m = x.month
    for row, lab in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        doc.t(8, gy + row * (cell + gap) + 11, lab, 10.5, "m", GREY)
    # reveal sweep (an overlay that slides away; off-canvas when animations are off)
    cid = doc.uid("cl")
    gw = 53 * (cell + gap)
    doc.defs.append(f'<clipPath id="{cid}"><rect x="{gx-2}" y="{gy-2}" width="{gw+4}" height="{7*(cell+gap)+2}"/></clipPath>')
    doc.css.append(f".sweep{{transform:translateX({gw+40}px);animation:sweep 1.6s cubic-bezier(.5,0,.3,1) .2s both}}"
                   f"@keyframes sweep{{from{{transform:translateX(0)}}to{{transform:translateX({gw+40}px)}}}}")
    doc.add(f'<g clip-path="url(#{cid})"><rect x="{gx-2}" y="{gy-2}" width="{gw+4}" height="{7*(cell+gap)+2}" fill="{BLACK}" class="sweep"/></g>')
    y = gy + 7 * (cell + gap) + 22
    x = doc.run(10, y, [("Total ", "m", AMBER), (str(total), "mb", WHITE), ("    Active days ", "m", AMBER), (str(active), "mb", WHITE),
                        ("    Longest streak ", "m", AMBER), (f"{streak} d", "mb", WHITE),
                        ("    Busiest day ", "m", AMBER), (f"{best.strftime('%d %b %Y')} ({contrib.get(best, 0)})", "mb", WHITE)], 12)
    lx = W - 10 - 5 * 17 - tw("More", 11, "m") - 6
    doc.t(lx - 6, y, "Less", 11, "m", GREY, "end")
    for i, c in enumerate(ramp):
        doc.add(f'<rect x="{lx+i*17}" y="{y-11}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    doc.t(lx + 5 * 17 + 2, y, "More", 11, "m", GREY)
    return doc.render()


# ------------------------------------------------------------------ footer
def footer(asof):
    W, H = 1000, 46
    doc = Doc(W, H, "")
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/><rect width="{W}" height="2" fill="{ORANGE}"/>')
    doc.t(8, 20, "Paris 33 · Saclay · Cergy · Casablanca 212        CentraleSupélec × ESSEC        "
                 "Hand-written SVG, refreshed daily by GitHub Actions", 11, "m", GREY)
    doc.t(8, 37, f"Copyright {asof.year} J. E. Soussan L.P.", 11, "m", GREY)
    doc.t(W - 8, 37, f"SN 2024 AIDAMS   CET   G{asof.strftime('%d-%b-%y')}", 11, "m", GREY, "end")
    return doc.render()


# ------------------------------------------------------------------ side projects, terminal style
def mini_card(doc, x, y, rank, kind, red, delay):
    ink = "#c8102e" if red else "#151515"
    doc.add(f'<g class="up" style="{d(delay)}"><rect x="{x}" y="{y}" width="40" height="56" rx="4" fill="#fbfaf6"/>')
    doc.t(x + 8, y + 17, rank, 14, "sb", ink, "middle")
    suit(doc, kind, x + 8, y + 26, 9, ink)
    suit(doc, kind, x + 22, y + 36, 20, ink)
    doc.add("</g>")


def sviz_poker(doc, x0, y0, x1, y1):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 4
    rx, ry = (x1 - x0) / 2 - 14, (y1 - y0) / 2 - 12
    doc.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#0c3b24" stroke="#3a5f3f" stroke-width="2"/>')
    for k in range(6):
        a = k / 6 * 2 * math.pi - math.pi / 2
        sx, sy = cx + (rx + 2) * math.cos(a), cy + (ry + 2) * math.sin(a)
        col = GREEN if k == 0 else SOFT
        doc.add(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="{BLACK}" stroke="{col}" stroke-width="1.5" class="ld" style="{d(.2+k*.08)}"/>')
    mini_card(doc, cx - 66, cy - 28, "A", "spade", False, .5)
    mini_card(doc, cx - 20, cy - 28, "K", "spade", False, .62)
    doc.t(cx + 30, cy - 6, "POT", 10.5, "m", AMBER)
    doc.t(cx + 30, cy + 12, "1,240", 15, "mb", WHITE, cls="ld", style=d(.9))


def sviz_soiree(doc, x0, y0, x1, y1):
    games = ["Mot Chaud", "Action/Vérité", "Quiplash", "Jeu du Vote", "Le Dilemme",
             "Le Menteur", "Le Tribunal", "Le Duel", "Blackjack", "Espion"]
    colw = (x1 - x0) / 2
    for i, g in enumerate(games):
        x = x0 + (i // 5) * colw
        y = y0 + 14 + (i % 5) * 21
        st = d(.2 + i * .05)
        doc.t(x, y, f"{i+1})", 11.5, "m", AMBER, cls="ld", style=st)
        doc.t(x + 26, y, g, 13, "s", WHITE, cls="ld", style=st)


def sviz_lasers(doc, x0, y0, x1, y1):
    n = 8
    s = min(x1 - x0, y1 - y0 - 4) / n
    gx = (x0 + x1) / 2 - n * s / 2
    gy = y0 + 2
    for r in range(n + 1):
        doc.add(f'<line x1="{gx}" y1="{gy+r*s:.1f}" x2="{gx+n*s:.1f}" y2="{gy+r*s:.1f}" stroke="#262626"/>')
        doc.add(f'<line x1="{gx+r*s:.1f}" y1="{gy}" x2="{gx+r*s:.1f}" y2="{gy+n*s:.1f}" stroke="#262626"/>')
    # a 2x2 triangle at (col 4, row 2) deflects the beam fired from the left edge
    tx, ty = gx + 4 * s, gy + 2 * s
    doc.add(f'<polygon points="{tx},{ty+2*s} {tx+2*s},{ty+2*s} {tx+2*s},{ty}" fill="#3a5f99" stroke="{BLUE}"/>')
    doc.add(f'<rect x="{gx+1*s+2:.1f}" y="{gy+5*s+2:.1f}" width="{2*s-4:.1f}" height="{2*s-4:.1f}" fill="#7a4a00" stroke="{AMBER}" transform="rotate(45 {gx+2*s:.1f} {gy+6*s:.1f})"/>')
    hit_y = gy + 3.5 * s
    pts = [(gx - 8, hit_y), (tx + s * .5, hit_y), (tx + s * .5, gy - 8)]
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    doc.css.append(f"@keyframes lz{{from{{stroke-dashoffset:{L:.0f}}}to{{stroke-dashoffset:0}}}}")
    path = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    doc.add(f'<path d="{path}" fill="none" stroke="{RED}" stroke-width="2.2" stroke-dasharray="{L:.0f}" '
            f'style="animation:lz 1.3s ease-in-out .5s both"/>')
    doc.add(f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]+4:.1f}" r="4" fill="{RED}" class="ld" style="{d(1.8)}"/>')


SIDE = [
    dict(slug="poker", code="POKR", name="ImmersivePoker", url="github.com/joshsssn/ImmersivePoker",
         desc="Real-time Texas Hold'em: the PC is the table, phones are your hands.",
         fields=[("Engine", "NL Hold'em · rebuys"), ("Stack", "FastAPI · WebSockets")], viz=("Table view", sviz_poker)),
    dict(slug="soiree", code="SOIR", name="Soirée", url="github.com/joshsssn/Anis-bday-games",
         desc="Ten party games on your phones. No install, join with a 4-letter code.",
         fields=[("Players", "up to 20"), ("Stack", "static JS · no server")], viz=("Game menu", sviz_soiree)),
    dict(slug="lasers", code="LASR", name="Lasers & Formes", url="joshsssn.github.io/Test_game",
         desc="Browser deduction duel: fire lasers, read the bounces, call the shapes.",
         fields=[("Mode", "2 players, 1 device"), ("Play", "GitHub Pages")], viz=("Laser probe", sviz_lasers)),
]


def side(p):
    W, H = 330, 330
    doc = Doc(W, H, f"{p['name']}: {p['desc']}")
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/>')
    doc.add(f'<rect width="{W}" height="24" fill="{ORANGE}"/>')
    x = doc.t(8, 17, p["code"], 13, "mb", BLACK) + 9
    doc.t(x, 17, p["name"], 14, "sb", BLACK)
    arrow_ne(doc, W - 20, 18, 9, BLACK)
    lines = wrap(p["desc"], 13.5, "s", W - 20)
    assert len(lines) <= 2, p["name"]
    for i, ln in enumerate(lines):
        doc.t(10, 44 + i * 18, ln, 13.5, "s", "#e4e4e4", cls="ld", style=d(.1 + i * .05))
    doc.add(f'<line x1="0" y1="82" x2="{W}" y2="82" stroke="{RULE}"/>')
    title, fn = p["viz"]
    doc.t(10, 100, title, 11, "m", AMBER)
    fn(doc, 10, 108, W - 10, 226)
    doc.add(f'<line x1="0" y1="236" x2="{W}" y2="236" stroke="{RULE}"/>')
    for i, (k, v) in enumerate(p["fields"]):
        yy = 258 + i * 24
        if i % 2 == 0:
            doc.add(f'<rect x="0" y="{yy-16}" width="{W}" height="24" fill="{ROW}"/>')
        doc.t(10, yy, k, 11.5, "m", AMBER)
        doc.t(84, yy, v, 13.5, "sb", WHITE)
    doc.t(10, H - 12, p["url"], 10.5, "m", GREY)
    doc.add(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" fill="none" stroke="#3a3a3a"/>')
    return doc.render()


BUTTONS = [("poker", "CODE", "github.com/joshsssn/ImmersivePoker", AMBER),
           ("soiree", "PLAY", "joshsssn.github.io/Anis-bday-games", GREEN),
           ("lasers", "PLAY", "joshsssn.github.io/Test_game", GREEN)]


def button(key, url, col):
    W, H = 330, 36
    doc = Doc(W, H, f"{key}: {url}")
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/><rect x=".5" y=".5" width="{W-1}" height="{H-1}" fill="none" stroke="#3a3a3a"/>')
    kw = tw(key, 13, "mb") + 40
    doc.add(f'<rect x="6" y="6" width="{kw:.1f}" height="24" rx="2" fill="{"#1f8f3a" if col == GREEN else ORANGE}"/>')
    if key == "PLAY":
        doc.add(f'<polygon points="16,12 16,24 26,18" fill="{BLACK}"/>')
    else:
        doc.add(f'<path d="M20 12l-6 6 6 6M26 12l6 6-6 6" stroke="{BLACK}" stroke-width="2" fill="none"/>')
    doc.t(36, 23, key, 13, "mb", BLACK)
    us = 11.5
    while tw(url, us, "m") > W - kw - 52 and us > 8:
        us -= .25
    doc.t(kw + 16, 22.5, url, us, "m", col)
    arrow_ne(doc, W - 18, 23, 8, col)
    return doc.render()


# ------------------------------------------------------------------ stack with logos
ICONS = json.loads((Path(__file__).resolve().parent / "icons.json").read_text())  # Simple Icons, CC0

LOGO_STACK = [
    ("Languages", [("Python", "python"), ("TypeScript", "typescript"), ("JavaScript", "javascript"), ("Rust", "rust"),
                   ("SQL", "x-sql"), ("LaTeX", "latex")], ["ALL"]),
    ("Quant & data", [("NumPy", "numpy"), ("pandas", "pandas"), ("SciPy", "scipy"), ("Polars", "polars"), ("Jupyter", "jupyter"),
                      ("Monte Carlo", "x-dice"), ("Markowitz", "x-frontier"), ("VaR / CVaR", "x-var"), ("DCF", "x-dcf")], ["AXIOME", "PAE"]),
    ("Machine learning", [("PyTorch", "pytorch"), ("TensorFlow", "tensorflow"), ("scikit-learn", "scikitlearn"),
                          ("Hugging Face", "huggingface"), ("MLflow", "mlflow"), ("CUDA", "nvidia"), ("Optuna", "optuna"), ("XGBoost", "x-tree")],
     ["EMOJI", "LR4MNIST"]),
    ("LLMs & agents", [("LangGraph", "langchain"), ("Ollama", "ollama"), ("OpenAI API", "openai"), ("MCP", "modelcontextprotocol"), ("FinBERT", "huggingface")],
     ["SCOUT", "MCPV"]),
    ("Data & backend", [("FastAPI", "fastapi"), ("DuckDB", "duckdb"), ("Neo4j", "neo4j"), ("PostgreSQL", "postgresql"),
                        ("SQLite", "sqlite"), ("Parquet", "apacheparquet"), ("Docker", "docker")], ["WIKI", "SCOUT"]),
    ("Apps", [("React", "react"), ("Tauri", "tauri"), ("Vite", "vite"), ("Tailwind CSS", "tailwindcss"), ("Streamlit", "streamlit")],
     ["AXIOME", "POKER"]),
    ("Tooling & markets", [("Git", "git"), ("GitHub Actions", "githubactions"), ("uv", "uv"), ("Superset", "apachesuperset"),
                           ("SAP", "sap"), ("Refinitiv / Eikon", "x-terminal"), ("Excel / VBA", "microsoftexcel"), ("Power BI", "powerbi")], ["SIX", "LCH"]),
]


def logo_color(hexcode):
    r, g, b = (int(hexcode[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = .2126 * r + .7152 * g + .0722 * b
    return WHITE if lum < .22 else f"#{hexcode}"


def stack_logos():
    W = 1000
    X0, X1 = 196, 852
    CH, GAP, LINE = 26, 6, 32

    def chip_w(name, icon):
        return tw(name, 12.5, "sb" if icon else "s") + (34 if icon else 18)

    layout = []
    for area, items, used in LOGO_STACK:
        rows, x, cur = [], X0, []
        for name, icon in items:
            w = chip_w(name, icon)
            if x + w > X1 and cur:
                rows.append(cur)
                cur, x = [], X0
            cur.append((x, name, icon, w))
            x += w + GAP
        rows.append(cur)
        layout.append((area, rows, used))
    H = 26 + 8 + 22 + sum(12 + LINE * len(r) for _, r, _ in layout) + 4
    doc = Doc(W, H, "Tech stack: " + "; ".join(f"{a}: {', '.join(n for n, _ in it)}" for a, it, _ in LOGO_STACK))
    doc.add(f'<rect width="{W}" height="{H}" fill="{BLACK}"/>')
    n_tools = sum(len(it) for _, it, _ in LOGO_STACK)
    func_bar(doc, 0, "SKIL", "Tech Stack", right_note=f"{n_tools} tools · {len(LOGO_STACK)} areas")
    y = 34
    doc.add(f'<rect x="0" y="{y}" width="{W}" height="22" fill="#141414"/>')
    for x, lab in [(10, "#"), (40, "Area"), (X0, "Toolkit"), (868, "Used in")]:
        doc.t(x, y + 15, lab, 11.5, "mb", AMBER)
    y += 22
    k = 0
    for i, (area, rows, used) in enumerate(layout):
        h = 12 + LINE * len(rows)
        if i % 2 == 0:
            doc.add(f'<rect x="0" y="{y}" width="{W}" height="{h}" fill="{ROW}"/>')
        by = y + 6
        doc.t(10, by + 18, f"{i+1})", 12.5, "m", AMBER)
        doc.t(40, by + 18, area, 14.5, "sb", WHITE)
        for r, row in enumerate(rows):
            cy = by + r * LINE
            for x, name, icon, w in row:
                st = d(.15 + i * .1 + k * .012)
                k += 1
                doc.add(f'<g class="ld" style="{st}">')
                doc.add(f'<rect x="{x:.1f}" y="{cy}" width="{w:.1f}" height="{CH}" rx="3" fill="#121212" stroke="{"#333" if icon else "#2a2a2a"}"/>')
                if icon:
                    ic = ICONS[icon]
                    col = logo_color(ic["hex"])
                    if "svg" in ic:
                        doc.add(f'<g transform="translate({x+9:.1f} {cy+6}) scale({14/24:.4f})">{ic["svg"].replace('"C"', f'"{col}"')}</g>')
                    else:
                        doc.add(f'<path d="{ic["path"]}" fill="{col}" transform="translate({x+9:.1f} {cy+6}) scale({14/24:.4f})"/>')
                    doc.t(x + 28, cy + 17.5, name, 12.5, "sb", WHITE)
                else:
                    doc.t(x + 9, cy + 17.5, name, 12.5, "s", AMBER)
                doc.add("</g>")
        ux = 868
        for u in used:
            w = tw(u, 11, "mb") + 12
            if ux + w > W - 6:
                break
            doc.add(f'<rect x="{ux}" y="{by+5}" width="{w:.1f}" height="18" fill="none" stroke="{BLUE}"/>')
            doc.t(ux + 6, by + 18, u, 11, "mb", BLUE)
            ux += w + 5
        doc.add(f'<line x1="0" y1="{y+h}" x2="{W}" y2="{y+h}" stroke="{RULE}"/>')
        y += h
    return doc.render()


def main():
    contrib, stats, asof = load_data()
    OUT.mkdir(exist_ok=True)
    head = header(contrib, stats, asof)
    files = {
        "header-top.svg": head.render(crop=(0, 0, 1000, 56)),
        "header.svg": head.render(crop=(0, 82, 1000, head.h - 82)),
        "contact.svg": contact(),
        "career.svg": career(asof),
        "bar-projects.svg": bar("PROJ", "Featured Projects", "click a panel to open the repo"),
        "bar-fun.svg": bar("FUN", "Side Projects", "built for fun"),
        "stack-logos.svg": stack_logos(),
        "activity.svg": activity(contrib, asof),
        "footer.svg": footer(asof),
    }
    for name, content, _, _ in tab_strip():
        files[name] = content
    for p in PROJECTS:
        files[f"proj-{p['slug']}.svg"] = project(p)
    for p in SIDE:
        files[f"side-{p['slug']}.svg"] = side(p)
    for slug, key, url, col in BUTTONS:
        files[f"btn-{slug}.svg"] = button(key, url, col)
    for old in OUT.glob("*.svg"):
        if old.name not in files:
            old.unlink()
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"assets/{name:<24} {len(content)/1024:6.1f} KB")


if __name__ == "__main__":
    main()
