#!/usr/bin/env python3
"""Voice log stats, standard library only.

python3 stats.py                      regenerate chart.svg and the README stats block
python3 stats.py log [seconds] < txt  append a prompt to voice-log.md
"""
import math
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
LOG, README, CHART = ROOT / "voice-log.md", ROOT / "README.md", ROOT / "chart.svg"
TYPE_WPM, SPEAK_WPM = 40, 150
START, END = "<!-- stats:start -->", "<!-- stats:end -->"

SECRETS = [re.compile(p) for p in (
    r"sk-[\w-]{16,}", r"gsk_\w{20,}", r"gh[pousr]_\w{20,}", r"github_pat_\w{20,}", r"AKIA[0-9A-Z]{16}",
    r"AIza[\w-]{30,}", r"xox[abprs]-[\w-]{10,}", r"eyJ[\w-]+\.[\w-]+\.[\w-]+",
)]
NAMED = re.compile(r"(?i)\b([\w-]*(?:key|token|secret|password))(\s*[=:]\s*)(?=\S*\d)\S{12,}")
ENTRY = re.compile(r"^## (\d+) · (.+)\nwords (\d+) · spoken (~?)(\d+)s · typed (\d+)s$", re.M)


def redact(text):
    for pattern in SECRETS:
        text = pattern.sub("[REDACTED]", text)
    return NAMED.sub(r"\1\2[REDACTED]", text)


def entry(n, text, when, spoken=None):
    text = redact(text.strip())
    words = len(text.split())
    typed = round(words * 60 / TYPE_WPM)
    said = str(spoken) if spoken is not None else f"~{round(words * 60 / SPEAK_WPM)}"
    quote = "\n".join(f"> {line}".rstrip() for line in text.splitlines())
    return f"## {n} · {when}\nwords {words} · spoken {said}s · typed {typed}s\n\n{quote}\n"


def parse(log):
    return [
        dict(n=int(n), when=when, words=int(words), est=bool(est), spoken=int(spoken), typed=int(typed))
        for n, when, words, est, spoken, typed in ENTRY.findall(log)
    ]


# --- chart -----------------------------------------------------------------

W, H = 900, 300
BG, INK, MUTED, GRID = "#1a1a19", "#ffffff", "#c3c2b7", "#383835"
SPOKEN, TYPED = "#3987e5", "#d95926"
LEFT, RIGHT, TOP, BOTTOM = 64, 868, 128, 258


def tick_step(top):
    raw = top / 3
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)


def bar(x, y, w, h, fill, tip):
    r = min(4, w / 2, h)
    d = (f"M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
         f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h:.1f}Z")
    return f'<path class="bar" d="{d}" fill="{fill}"><title>{tip}</title></path>'


def svg(rows):
    spoken, typed = sum(r["spoken"] for r in rows) / 60, sum(r["typed"] for r in rows) / 60
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Spoken {spoken:.1f} min versus typed {typed:.1f} min across {len(rows)} prompts" '
        f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" fill="{BG}" stroke="{GRID}"/>',
        f'<text x="32" y="40" font-size="15" font-weight="600" fill="{INK}">Spoken vs typed minutes per prompt</text>',
    ]
    for x, colour, label in ((668, SPOKEN, "Spoken"), (748, TYPED, f"Typed at {TYPE_WPM} wpm")):
        out.append(f'<rect x="{x}" y="30" width="10" height="10" rx="2" fill="{colour}"/>')
        out.append(f'<text x="{x + 16}" y="39" font-size="12" fill="{MUTED}">{label}</text>')
    heads = ((f"{spoken:.1f} min", "spoken"), (f"{typed:.1f} min", "typed"),
             (f"{typed - spoken:.1f} min", "saved by voice"), (str(len(rows)), "prompts"))
    for i, (value, label) in enumerate(heads):
        x = 32 + 160 * i
        out.append(f'<text x="{x}" y="84" font-size="26" font-weight="700" fill="{INK}">{value}</text>')
        out.append(f'<text x="{x}" y="104" font-size="12" fill="{MUTED}">{label}</text>')

    step = tick_step(max([r["typed"] / 60 for r in rows] + [r["spoken"] / 60 for r in rows] + [0.1]))
    ticks = max(1, math.ceil(max([max(r["typed"], r["spoken"]) / 60 for r in rows] + [0.1]) / step))
    scale = (BOTTOM - TOP) / (ticks * step)
    for i in range(ticks + 1):
        y = BOTTOM - i * step * scale
        out.append(f'<line x1="{LEFT}" x2="{RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{LEFT - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end" fill="{MUTED}">'
                   f'{i * step:g} min</text>')

    slot = (RIGHT - LEFT) / max(len(rows), 1)
    width = max(1, min(28, (slot * 0.7 - 2) / 2))
    every = math.ceil(len(rows) / 20) or 1
    for i, r in enumerate(rows):
        x = LEFT + slot * i + (slot - 2 * width - 2) / 2
        for j, (key, colour) in enumerate((("spoken", SPOKEN), ("typed", TYPED))):
            h = r[key] / 60 * scale
            out.append(bar(x + j * (width + 2), BOTTOM - h, width, h, colour, f"#{r['n']} {key}: {r[key]}s"))
        if i % every == 0:
            out.append(f'<text x="{LEFT + slot * (i + 0.5):.1f}" y="{BOTTOM + 18}" font-size="11" '
                       f'text-anchor="middle" fill="{MUTED}">#{r["n"]}</text>')
    return "\n".join(out + ["</svg>"]) + "\n"


# --- readme ----------------------------------------------------------------

def clock(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def block(rows):
    lines = [START, "![Spoken vs typed minutes per prompt](chart.svg)", "",
             "| # | When | Words | Spoken | Typed | Saved |", "|--:|---|--:|--:|--:|--:|"]
    for r in rows:
        said = ("~" if r["est"] else "") + clock(r["spoken"])
        lines.append(f"| {r['n']} | {r['when']} | {r['words']} | {said} | {clock(r['typed'])} "
                     f"| {clock(max(0, r['typed'] - r['spoken']))} |")
    return "\n".join(lines + [END])


def sync(readme, rows):
    if START in readme and END in readme:
        head, rest = readme.split(START, 1)
        return head + block(rows) + rest.split(END, 1)[1]
    return block(rows) + "\n\n" + readme


def main(argv):
    if argv[:1] == ["log"]:
        rows = parse(LOG.read_text()) if LOG.exists() else []
        n = rows[-1]["n"] + 1 if rows else 0
        spoken = int(argv[1]) if len(argv) > 1 else None
        when = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
        head = LOG.read_text() if LOG.exists() else "# Voice log\n"
        LOG.write_text(head + "\n" + entry(n, sys.stdin.read(), when, spoken))
        print(f"logged voice prompt {n}")
        return
    rows = parse(LOG.read_text())
    CHART.write_text(svg(rows))
    README.write_text(sync(README.read_text(), rows))
    print(f"stats: {len(rows)} prompts")


if __name__ == "__main__":
    main(sys.argv[1:])
