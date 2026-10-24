"""Render assets/city.svg: an isometric night skyline, one building per day of the last year.

The city geometry is adapted from Giorgi Kobaidze's profile generator
(https://github.com/georgekobaidze/georgekobaidze, tools/profile/render.py, build_city):

    MIT License

    Copyright (c) 2026 Giorgi Kobaidze

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

Changes: red palette, softer frame matching the Neovim header, standalone data fetch.

Data: GraphQL contribution calendar. GH_TOKEN with repo/read:user scope includes private
contributions (the viewer's own calendar); without it the public calendar of USER is used.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import urllib.request
from html import escape
from pathlib import Path

USER = "Siruyy"
OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "city.svg"

W, H = 920, 600
BAR = 36                                   # title bar height
TW, TH = 25, 12.5                          # iso tile width / height
OX, OY = 165, 172                          # grid origin (week 0, Sunday)
HMAX = 118                                 # tallest building, px

BG, BAR_BG, BORDER, DOT = "#0e0e0e", "#161616", "#262626", "#3a3a3a"
TEXT, DIM, ACCENT = "#cfcfcf", "#6e6e6e", "#ff6b6b"
EMPTY, EMPTY_EDGE = "#171717", "#0e0e0e"
ROOFS = ["#4a1616", "#8b2323", "#d13d3d", "#ff6b6b"]   # quiet → busiest
WALL_L, WALL_R = "#1f1717", "#151010"
WIN_ON, WIN_ON_SIDE, WIN_OFF = "#ffc2b8", "#ff9a8c", "#1a1212"

QUERY = """query($login: String!) {
  user(login: $login) { contributionsCollection {
    contributionCalendar { weeks { contributionDays { date contributionCount } } } } }
}"""
VIEWER_QUERY = """query {
  viewer { contributionsCollection {
    contributionCalendar { weeks { contributionDays { date contributionCount } } } } }
}"""


def fetch_calendar(token: str) -> list[tuple[dt.date, int]]:
    body = {"query": VIEWER_QUERY} if os.environ.get("GH_TOKEN") else {"query": QUERY, "variables": {"login": USER}}
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    root = payload["data"]["viewer" if "viewer" in payload["data"] else "user"]
    weeks = root["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def _p(x: float, y: float) -> str:
    return f"{x:.1f},{y:.1f}"


def _rng(seed: str):
    """Deterministic PRNG so the same data draws the same windows."""
    state = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    while True:
        state = (state * 6364136223846793005 + 1442695040888963407) % 2**64
        yield (state >> 11) / 2**53


def _levels(counts: list[int]) -> list[int]:
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [1, 1, 1]
    return [nz[min(len(nz) - 1, int(len(nz) * f))] for f in (.25, .5, .75)]


def build(days: list[tuple[dt.date, int]]) -> str:
    counts = [n for _, n in days]
    total, peak = sum(counts), max(counts, default=0) or 1
    lv = _levels(counts)
    rnd = _rng(f"{days[-1][0]}-{total}")
    start = days[0][0]

    cells = sorted((((d - start).days // 7, (d.weekday() + 1) % 7, n) for d, n in days),
                   key=lambda c: (c[0] + c[1], c[0]))          # back to front

    shapes: list[str] = []
    flick = 0
    for w, dow, n in cells:
        cx, cy = OX + (w - dow) * TW / 2, OY + (w + dow) * TH / 2
        L, R, T, B = (cx - TW / 2, cy), (cx + TW / 2, cy), (cx, cy - TH / 2), (cx, cy + TH / 2)
        if n == 0:
            shapes.append(f'<path d="M{_p(*T)}L{_p(*R)}L{_p(*B)}L{_p(*L)}Z" fill="{EMPTY}" stroke="{EMPTY_EDGE}" stroke-width=".6"/>')
            continue
        h = 8 + (HMAX - 8) * math.sqrt(n / peak)
        level = sum(n > t for t in lv)
        Tu, Ru, Bu, Lu = [(x, y - h) for x, y in (T, R, B, L)]
        shapes.append(f'<path d="M{_p(*L)}L{_p(*B)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{WALL_L}"/>'
                      f'<path d="M{_p(*B)}L{_p(*R)}L{_p(*Ru)}L{_p(*Bu)}Z" fill="{WALL_R}"/>'
                      f'<path d="M{_p(*Tu)}L{_p(*Ru)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{ROOFS[level]}"/>')
        on, side, off, fl = [], [], [], []
        for face, (a, b) in (("l", (L, B)), ("r", (B, R))):
            for r in range(int((h - 6) // 7)):
                v0 = 5 + r * 7
                for u0 in (.18, .58):
                    lit = next(rnd) < .5
                    if not lit and next(rnd) < .5:
                        continue
                    pts = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - v)
                           for u, v in ((u0, v0), (u0 + .26, v0), (u0 + .26, v0 + 3.2), (u0, v0 + 3.2))]
                    seg = "M" + "L".join(_p(*q) for q in pts) + "Z"
                    if not lit:
                        off.append(seg)
                    elif next(rnd) < .03:
                        fl.append((seg, face))
                    else:
                        (on if face == "l" else side).append(seg)
        if off:
            shapes.append(f'<path d="{"".join(off)}" fill="{WIN_OFF}"/>')
        if on:
            shapes.append(f'<path d="{"".join(on)}" fill="{WIN_ON}"/>')
        if side:
            shapes.append(f'<path d="{"".join(side)}" fill="{WIN_ON_SIDE}"/>')
        for seg, face in fl:
            flick += 1
            shapes.append(f'<path class="f{flick % 3}" d="{seg}" fill="{WIN_ON if face == "l" else WIN_ON_SIDE}"/>')

    stars = []
    for i in range(40):
        x, y = 470 + next(rnd) * 400, BAR + 24 + next(rnd) * 200
        if x > 760 and y < 160:                      # keep the moon clear
            continue
        cls = ' class="tw"' if i % 3 == 0 else ""
        stars.append(f'<circle{cls} cx="{x:.1f}" cy="{y:.1f}" r="{(.6, .8, 1.1)[i % 3]}" fill="#d0d0d0" opacity="{.3 + next(rnd) * .5:.2f}"/>')

    busiest_d, busiest_n = max(days, key=lambda t: t[1])
    active = sum(1 for n in counts if n)
    info = [
        f'<tspan fill="{ACCENT}" font-weight="700">{total:,}</tspan> contributions in the last year',
        f'busiest day <tspan fill="{TEXT}">{busiest_d:%b} {busiest_d.day}</tspan> with {busiest_n}' if busiest_n else "",
        f'{active} active days',
    ]
    info_svg = "".join(f'<text x="34" y="{478 + i * 22}" fill="{DIM}" font-size="13">{t}</text>'
                       for i, t in enumerate(info) if t)
    legend = "".join(f'<rect x="{86 + i * 16}" y="{H - 38}" width="11" height="11" rx="2" fill="{c}"/>'
                     for i, c in enumerate([EMPTY] + ROOFS))
    desc = (f"Contribution city: an isometric night skyline with one building per day of the last year, "
            f"taller and brighter for busier days. {total:,} contributions, busiest day "
            f"{busiest_d:%B} {busiest_d.day} with {busiest_n}.")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="14" role="img" aria-labelledby="t d">
  <title id="t">Contribution city</title>
  <desc id="d">{escape(desc)}</desc>
  <style>
    @keyframes tw{{0%,100%{{opacity:.9}}50%{{opacity:.15}}}}
    @keyframes fl{{0%,40%,100%{{opacity:1}}45%,60%{{opacity:.1}}}}
    @keyframes fly{{from{{transform:translate(-40px,0)}}to{{transform:translate({W + 40}px,-30px)}}}}
    @keyframes blink{{0%,90%,100%{{opacity:0}}93%{{opacity:1}}}}
    .tw{{animation:tw 3s infinite}}
    .f0{{animation:fl 5s infinite}}.f1{{animation:fl 7s infinite 2s}}.f2{{animation:fl 9s infinite 4s}}
    .plane{{animation:fly 30s linear infinite}}.bl{{animation:blink 1.4s infinite}}
  </style>
  <defs>
    <radialGradient id="moonglow"><stop offset="0" stop-color="#f3f3f3" stop-opacity=".18"/><stop offset="1" stop-color="#f3f3f3" stop-opacity="0"/></radialGradient>
    <clipPath id="frame"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14"/></clipPath>
  </defs>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>
  <g clip-path="url(#frame)">
    <rect x="0" y="0" width="{W}" height="{BAR}" fill="{BAR_BG}"/>
    <line x1="0" y1="{BAR}" x2="{W}" y2="{BAR}" stroke="{BORDER}"/>
    <circle cx="22" cy="18" r="5.5" fill="{DOT}"/><circle cx="40" cy="18" r="5.5" fill="{DOT}"/><circle cx="58" cy="18" r="5.5" fill="{DOT}"/>
    <text x="{W / 2:.0f}" y="23" fill="{DIM}" text-anchor="middle" font-size="12">~/contribution-city</text>
    <text x="34" y="{BAR + 30}"><tspan fill="{ACCENT}">❯ </tspan><tspan fill="{TEXT}">render-city --last 365d</tspan><tspan fill="{DIM}">  # one building per day</tspan></text>
    <g>{"".join(stars)}</g>
    <circle cx="{W - 90}" cy="{BAR + 70}" r="40" fill="url(#moonglow)"/>
    <circle cx="{W - 90}" cy="{BAR + 70}" r="14" fill="#ececec"/>
    <circle cx="{W - 84}" cy="{BAR + 65}" r="12.5" fill="{BG}"/>
    <g class="plane"><g transform="translate(0 {BAR + 110})"><rect width="14" height="2" rx="1" fill="#555"/><circle class="bl" cx="0" cy="1" r="1.6" fill="{ACCENT}"/><circle class="bl" cx="14" cy="1" r="1.6" fill="#f0f0f0" style="animation-delay:.7s"/></g></g>
    {"".join(shapes)}
    {info_svg}
    <text x="34" y="{H - 28}" fill="{DIM}" font-size="11">quiet</text>{legend}<text x="{86 + 5 * 16 + 6}" y="{H - 28}" fill="{DIM}" font-size="11">skyscraper</text>
  </g>
</svg>
'''


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("set GH_TOKEN (private + public) or GITHUB_TOKEN (public only)")
    days = fetch_calendar(token)
    if not days:
        raise SystemExit("empty contribution calendar")
    OUTPUT.write_text(build(days), encoding="utf-8")


if __name__ == "__main__":
    main()
