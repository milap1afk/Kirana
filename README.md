<!-- stats:start -->
![Spoken vs typed minutes per prompt](chart.svg)

| # | When | Words | Spoken | Typed | Saved |
|--:|---|--:|--:|--:|--:|
| 0 | 2026-10-10 14:21 +0530 | 179 | 1:50 | 4:28 | 2:38 |
| 1 | 2026-10-10 14:44 +0530 | 401 | ~2:40 | 10:02 | 7:22 |
<!-- stats:end -->

# Kirana

**बोलो, लिखा गया.** A voice khata for Indian corner shops. The shopkeeper dictates
the day's notes in Hinglish; Kirana turns each note into ledger entries, shows a
confirm card for each one, and keeps who owes how much.

Built so far: the note parser with confirm cards, save and undo (step 1) and
balances (step 2). Still to come: WhatsApp reminders, today's view, phone polish.

The project is built by voice. Every prompt is logged word for word in
[voice-log.md](voice-log.md), and the chart above compares how long each prompt
took to say with how long it would have taken to type at 40 words a minute.

## Layout

| File | What it does |
|---|---|
| [CLAUDE.md](CLAUDE.md) | The working rules |
| [voice-log.md](voice-log.md) | Every prompt, with timestamp, word count and timings |
| [server.py](server.py) | The server: Groq parser, SQLite ledger, balances |
| [index.html](index.html) | The page: note box, confirm cards, कौन कितना बाकी |
| [test_server.py](test_server.py) | Server tests on recorded model replies; no key needed |
| [stats.py](stats.py) | Logs prompts; regenerates `chart.svg` and the table above |
| [test_stats.py](test_stats.py) | Stats tests |
| [.githooks/pre-commit](.githooks/pre-commit) | Runs the tests and `stats.py` on every commit |

## Use

```sh
git config core.hooksPath .githooks       # once per clone
echo 'GROQ_API_KEY=...' > .env            # your Groq key; never committed
python3 server.py                         # open http://localhost:8000
python3 server.py demo                    # parse 5 sample notes with the real model
python3 -m unittest                       # run the tests
python3 stats.py log 45 < prompt.txt      # log a prompt that took 45 s to say
python3 stats.py                          # regenerate the chart and table
```

Spoken times marked `~` are estimates at 150 words a minute, used when the real
duration isn't given. Keys in prompts are replaced with `[REDACTED]`.
