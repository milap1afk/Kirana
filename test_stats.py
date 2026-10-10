import unittest

import stats

LOG = "# Voice log\n\n" + stats.entry(0, "one two three four", "2026-10-10 14:21 +0530") + "\n" + stats.entry(
    1, "word " * 80, "2026-10-10 14:22 +0530", spoken=30)


class RedactTest(unittest.TestCase):
    def test_known_key_shapes(self):
        for key in ("sk-ant-abc123def456ghi789", "ghp_" + "a1" * 18, "AKIAABCDEFGHIJKLMNOP", "gsk_" + "b2" * 20):
            self.assertEqual(stats.redact(f"use {key} now"), "use [REDACTED] now")

    def test_named_value(self):
        self.assertEqual(stats.redact("API_KEY=abc123def456ghi"), "API_KEY=[REDACTED]")

    def test_plain_speech_untouched(self):
        text = "5 keys, 11: get ignored. the key: regenerating everything"
        self.assertEqual(stats.redact(text), text)


class LogTest(unittest.TestCase):
    def test_entry_counts_and_times(self):
        rows = stats.parse(LOG)
        self.assertEqual(rows[0], dict(n=0, when="2026-10-10 14:21 +0530", words=4, est=True, spoken=2, typed=6))
        self.assertEqual((rows[1]["words"], rows[1]["spoken"], rows[1]["typed"], rows[1]["est"]), (80, 30, 120, False))

    def test_entry_keeps_words_and_redacts(self):
        text = stats.entry(2, "first line\nkey sk-ant-abc123def456ghi789", "now")
        self.assertIn("> first line\n> key [REDACTED]\n", text)


class ChartTest(unittest.TestCase):
    def test_card_size_bars_and_headlines(self):
        svg = stats.svg(stats.parse(LOG))
        self.assertIn('width="900" height="300"', svg)
        self.assertEqual(svg.count('class="bar"'), 4)
        for text in ("0.5 min", "2.1 min", "1.6 min", "Spoken", "Typed at 40 wpm", ">#1<"):
            self.assertIn(text, svg)

    def test_empty_log_still_renders(self):
        self.assertIn("</svg>", stats.svg([]))


class ReadmeTest(unittest.TestCase):
    def test_sync_is_idempotent_and_keeps_prose(self):
        rows = stats.parse(LOG)
        once = stats.sync("# Kirana\n\nprose\n", rows)
        self.assertEqual(stats.sync(once, rows), once)
        self.assertTrue(once.startswith(stats.START))
        self.assertIn("| 1 | 2026-10-10 14:22 +0530 | 80 | 0:30 | 2:00 | 1:30 |", once)
        self.assertTrue(once.endswith("# Kirana\n\nprose\n"))


if __name__ == "__main__":
    unittest.main()
