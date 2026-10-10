#!/usr/bin/env python3
"""Kirana: voice khata for corner shops. Standard library only.

python3 server.py [port] serve the page on http://localhost:8000
python3 server.py demo   parse the sample notes with the real model and print the entries
"""
import functools
import http.client
import json
import re
import sqlite3
import struct
import sys
import urllib.error
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH, ENV_PATH, SAMPLES_PATH = ROOT / "kirana.db", ROOT / ".env", ROOT / "samples.json"
URL, MODEL = "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"
TYPES = ("udhar", "payment", "sale")
HONORIFICS = {"shri", "shree", "sri", "mr", "mrs", "smt", "ji", "jee", "g", "bhai", "by", "bhaiya", "sahab", "saheb"}

MESSAGES = {
    "offline": "Internet nahi chal raha. Net check karke dobara try karo.",
    "key": "AI ki key galat hai. .env mein GROQ_API_KEY check karo.",
    "wait": "AI abhi busy hai. Thodi der mein dobara try karo.",
    "cap": "Aaj ki AI limit poori ho gayi. Thodi der baad try karo.",
    "confused": "AI samajh nahi paya. Note thoda saaf bolkar dobara try karo.",
    "oops": "Kuch gadbad hui. Dobara try karo.",
}

PROMPT = """You turn an Indian shopkeeper's spoken Hinglish note into ledger entries.
Reply with JSON only: {"entries": [{"customer": "Ramesh", "amount": 200, "type": "udhar"}]}
- type "udhar": the customer took goods on credit. "payment": the customer paid money back
  (jama, diye, chukaye, wapas). "sale": a paid cash sale (nakad, cash, bikri).
- One note can hold several entries. Return every one, in order.
- amount is whole rupees as a number. Hindi number words must work: sau=100, hazaar=1000,
  dedh=1.5x, dhai=2.5x, sawa=1.25x, saadhe=+half, paune=-quarter. paanch sau=500,
  dhai sau=250, dedh hazaar=1500, sawa hazaar=1250, saadhe teen sau=350, paune do sau=175.
- customer is the person's name as spoken. An udhar or payment with no name belongs to the
  person named just before it in the same note. Use "" only for a cash sale with no name.
- If the speaker corrects themselves (nahi nahi, matlab), keep only the corrected amount.
- If the note has no entry, reply {"entries": []}."""

SAMPLE_NOTES = [
    "ramesh bhai ko dhai sau ka udhar diya, aur suresh ji ne paanch sau jama kiye",
    "shri ramesh ji phir aaye the, 200 ka saman udhar le gaye",
    "aaj dedh hazaar ki nakad bikri hui, haan aur geeta didi ne sawa hazaar ka udhar liya",
    "umm imran bhai ne teen sau chukaye... nahi nahi saadhe teen sau, aur 80 ka doodh udhar",
    "sunita ji ko barah sau ka ration udhaar, cash mein 2 hazaar ki bikri, ramesh by ne 100 wapas diye",
]

fetch = urllib.request.urlopen  # tests swap this for recorded replies


class AIError(Exception):
    def __init__(self, code, retry_after=None):
        super().__init__(code)
        self.code, self.retry_after = code, retry_after


def api_key():
    for line in ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []:
        name, _, value = line.partition("=")
        if name.strip() == "GROQ_API_KEY":
            return value.strip().strip("\"'")
    return ""


def clean_name(name):
    words = re.sub(r"[^\w\s]", " ", str(name)).split()
    kept = [w for w in words if w.lower() not in HONORIFICS] or words
    return " ".join(w.capitalize() for w in kept)


def clean_entries(raw):
    """Validate entries from the model or the browser. Raises AIError('confused')."""
    entries = []
    try:
        for item in raw:
            kind, amount = item["type"], round(float(item["amount"]))
            customer = clean_name(item.get("customer") or "")
            if kind not in TYPES or amount <= 0 or not (customer or kind == "sale"):
                raise ValueError(item)
            entries.append({"customer": customer or "Nakad", "amount": amount, "type": kind})
    except (TypeError, KeyError, ValueError, AttributeError, OverflowError):
        raise AIError("confused")
    if not entries:
        raise AIError("confused")
    return entries


def ask(note):
    """Send one note to the model and return its raw JSON reply text."""
    key = api_key()
    if not key:
        raise AIError("key")
    body = {
        "model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": note}],
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "kirana"}
    try:
        with fetch(urllib.request.Request(URL, json.dumps(body).encode(), headers), timeout=30) as reply:
            return json.load(reply)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as error:
        if error.code == 429:
            try:
                seconds = max(1, round(float(error.headers.get("retry-after") or 8)))
            except ValueError:
                seconds = 8
            raise AIError("wait", seconds) if seconds <= 60 else AIError("cap")
        raise AIError("key" if error.code in (401, 403) else "confused")
    except OSError:  # no network, DNS failure, timeout, dropped connection
        raise AIError("offline")
    except (ValueError, KeyError, TypeError, IndexError, http.client.HTTPException):
        raise AIError("confused")


def read_reply(content):
    try:
        return clean_entries(json.loads(content)["entries"])
    except (ValueError, KeyError, TypeError):
        raise AIError("confused")


def parse_note(note):
    return read_reply(ask(note))


# --- ledger ----------------------------------------------------------------

def connect(path=DB_PATH):
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY, customer TEXT NOT NULL, amount INTEGER NOT NULL, type TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")
    return db


def save(db, entries):
    with db:
        return [db.execute("INSERT INTO entries (customer, amount, type) VALUES (?, ?, ?)",
                           (e["customer"], e["amount"], e["type"])).lastrowid for e in entries]


def undo(db, ids):
    with db:
        db.executemany("DELETE FROM entries WHERE id = ?", [(int(i),) for i in ids])


def balances(db):
    """Who owes how much: udhar minus payments per customer. Sales are excluded."""
    rows = db.execute("""SELECT customer, SUM(CASE type WHEN 'udhar' THEN amount ELSE -amount END) AS due
        FROM entries WHERE type IN ('udhar', 'payment') GROUP BY customer HAVING due > 0 ORDER BY due DESC, customer""")
    return [{"customer": customer, "balance": due} for customer, due in rows]


def state(db):
    """Everything the page shows: balances, today's three totals, today's and older entries."""
    today = "date(created_at) = date('now', 'localtime')"
    totals = dict.fromkeys(TYPES, 0)
    totals.update(db.execute(f"SELECT type, SUM(amount) FROM entries WHERE {today} GROUP BY type"))
    rows = db.execute(f"SELECT id, customer, amount, type, created_at, {today} FROM entries ORDER BY id DESC LIMIT 300").fetchall()
    entry = lambda row: dict(zip(("id", "customer", "amount", "type", "at"), row))
    return {"balances": balances(db), "today": totals, "empty": not rows,
            "entries": [entry(r) for r in rows if r[5]], "older": [entry(r) for r in rows if not r[5]]}


def load_sample(db):
    """Fill an empty ledger with the recorded sample day. Does nothing if entries exist."""
    if db.execute("SELECT 1 FROM entries LIMIT 1").fetchone():
        return False
    replies = json.loads(SAMPLES_PATH.read_text())
    save(db, [entry for note in SAMPLE_NOTES for entry in read_reply(replies[note])])
    return True


# --- home screen -----------------------------------------------------------

MANIFEST = {
    "name": "Kirana — बोलो, लिखा गया", "short_name": "Kirana", "start_url": "/", "display": "standalone",
    "background_color": "#f6f4ee", "theme_color": "#17794c",
    "icons": [{"src": f"/icon-{size}.png", "sizes": f"{size}x{size}", "type": "image/png", "purpose": "any maskable"}
              for size in (192, 512)],
}


@functools.lru_cache()
def icon(size):
    """A green tile with a white ledger page, drawn without an image library."""
    green, white = b"\x17\x79\x4c", b"\xff\xff\xff"

    def pixel(x, y):
        if not (0.28 < x < 0.72 and 0.22 < y < 0.78):
            return green
        line = any(abs(y - middle) < 0.03 for middle in (0.36, 0.5, 0.64))
        return green if line and 0.36 < x < (0.64 if y < 0.57 else 0.52) else white

    rows = b"".join(b"\0" + b"".join(pixel((x + 0.5) / size, (y + 0.5) / size) for x in range(size)) for y in range(size))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


# --- http ------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    db_path = DB_PATH

    def send(self, status, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self.send(200, (ROOT / "index.html").read_bytes(), "text/html")
        if self.path == "/manifest.json":
            return self.send(200, MANIFEST, "application/manifest+json")
        if self.path in ("/icon-192.png", "/icon-512.png"):
            return self.send(200, icon(int(self.path[6:9])), "image/png")
        if self.path == "/api/state":
            try:
                db = connect(self.db_path)
                try:
                    return self.send(200, state(db))
                finally:
                    db.close()
            except Exception:
                return self.send(500, {"error": "oops", "message": MESSAGES["oops"]})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            db = connect(self.db_path)
        except Exception:
            return self.send(500, {"error": "oops", "message": MESSAGES["oops"]})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.path == "/api/parse":
                self.send(200, {"entries": parse_note(str(data.get("note", "")).strip())})
            elif self.path == "/api/confirm":
                try:
                    entries = clean_entries(data.get("entries"))
                except AIError:
                    raise ValueError("bad entries")
                self.send(200, {"ids": save(db, entries)})
            elif self.path == "/api/undo":
                undo(db, data.get("ids", []))
                self.send(200, {"ok": True})
            elif self.path == "/api/sample":
                self.send(200, {"ok": load_sample(db)})
            else:
                self.send(404, {"error": "not found"})
        except AIError as error:
            self.send(502, {"error": error.code, "message": MESSAGES[error.code], "retry_after": error.retry_after})
        except (ValueError, TypeError, AttributeError):
            self.send(400, {"error": "bad request", "message": MESSAGES["oops"]})
        except Exception:  # never show the shopkeeper a traceback
            self.send(500, {"error": "oops", "message": MESSAGES["oops"]})
        finally:
            db.close()

    def log_message(self, *args):
        pass


def demo():
    """Parse the sample notes with the real model, print the entries, record the replies."""
    replies = {}
    for note in SAMPLE_NOTES:
        print(f"\n{note}")
        try:
            replies[note] = ask(note)
            for e in read_reply(replies[note]):
                print(f"  {e['customer']:<12} ₹{e['amount']:<6} {e['type']}")
        except AIError as error:
            print(f"  ! {MESSAGES[error.code]}")
    SAMPLES_PATH.write_text(json.dumps(replies, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["demo"]:
        demo()
    else:
        port = int(sys.argv[1]) if sys.argv[1:] and sys.argv[1].isdigit() else 8000
        try:
            web = ThreadingHTTPServer(("", port), Handler)
        except OSError:
            sys.exit(f"Port {port} is busy. Try another one: python3 server.py {port + 1}")
        print(f"Kirana: http://localhost:{port}")
        try:
            web.serve_forever()
        except KeyboardInterrupt:
            print("\nKirana stopped.")
