<!-- stats:start -->
![Spoken vs typed minutes per prompt](chart.svg)

| # | When | Words | Spoken | Typed | Saved |
|--:|---|--:|--:|--:|--:|
| 0 | 2026-10-10 14:21 +0530 | 179 | 1:50 | 4:28 | 2:38 |
| 1 | 2026-10-10 14:44 +0530 | 401 | ~2:40 | 10:02 | 7:22 |
<!-- stats:end -->

# Kirana

A project built by voice. Every prompt is logged word for word in
[voice-log.md](voice-log.md), and the chart above compares how long each prompt
took to say with how long it would have taken to type at 40 words a minute.

## Layout

| File | What it does |
|---|---|
| [CLAUDE.md](CLAUDE.md) | The working rules |
| [voice-log.md](voice-log.md) | Every prompt, with timestamp, word count and timings |
| [stats.py](stats.py) | Logs prompts; regenerates `chart.svg` and the table above |
| [test_stats.py](test_stats.py) | Tests |
| [.githooks/pre-commit](.githooks/pre-commit) | Runs the tests and `stats.py` on every commit |

## Use

```sh
git config core.hooksPath .githooks       # once per clone
python3 -m unittest                       # run the tests
python3 stats.py log 45 < prompt.txt      # log a prompt that took 45 s to say
python3 stats.py                          # regenerate the chart and table
```

Spoken times marked `~` are estimates at 150 words a minute, used when the real
duration isn't given. Keys in prompts are replaced with `[REDACTED]`.
