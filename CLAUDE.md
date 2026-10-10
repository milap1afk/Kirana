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

Git: remote is `github.com/milap1afk/Kirana`. Commit after every step, push at the end.
After cloning: `git config core.hooksPath .githooks`.
