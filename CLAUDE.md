# Kirana — rules

1. **Log every prompt** in `voice-log.md`, word for word, before doing the work:
   `python3 stats.py log [spoken_seconds] < prompt.txt`. It records the timestamp,
   word count, seconds spoken, and typing time at 40 wpm, and replaces keys with
   `[REDACTED]`. If the spoken seconds aren't given, it estimates them at 150 wpm (`~`).
2. **Never say "done" without running the tests**: `python3 -m unittest`.
3. **Every commit message ends with the voice prompt number**, as a final
   `Voice-Prompt: <n>` line.
4. **README stays in sync.** `stats.py` (standard library only) regenerates
   `chart.svg` and the stats block at the top of the README on every commit, via
   `.githooks/pre-commit`. Never edit between the `stats` markers by hand.
5. **Keys never get committed.** `.env` is gitignored.
6. **Don't stop to ask.** Think it through, make sensible calls, tell me after.
7. **Keep files small.** I review by voice.

## Product

Kirana is a voice khata for Indian corner shops. Tagline: **बोलो, लिखा गया.**
The shopkeeper dictates the day's notes in Hinglish; Kirana keeps the ledger and
writes the WhatsApp reminders.

- Python standard library only: one `server.py`, one static `index.html`, one SQLite file (`kirana.db`).
- AI: Groq, model `openai/gpt-oss-120b`, `GROQ_API_KEY` from `.env`, temperature 0, JSON output.
- Entry = customer, amount, type (`udhar`, `payment` or `sale`). One note can hold several.
- Hindi number words must work: paanch sau 500, dhai sau 250, dedh hazaar 1500, sawa hazaar 1250.
- Honorifics are trimmed: Ramesh bhai, Ramesh ji and Shri Ramesh ji are all Ramesh.
- Nothing is saved before the shopkeeper confirms a card. Saved entries can be undone.
- Balance per customer = udhar minus payments. Sales are excluded.
- Tests use recorded model replies, so they need no key.

## Steps

1. Parser and confirm cards — built
2. Balances (कौन कितना बाकी) — built
3. WhatsApp: copy-reminder button and `wa.me` button
4. Today's view (आज का हिसाब): three tiles and today's entries
5. Phone polish (360 px, 44 px buttons, home-screen manifest), hardening
   (429 retry countdown, sample-day button) and README

Git: remote is `github.com/milap1afk/Kirana`. Commit after every step, push at the end.
After cloning: `git config core.hooksPath .githooks`.
