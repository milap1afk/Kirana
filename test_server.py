import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import server

# Real replies captured from Groq by `python3 server.py demo`, so the tests need no key.
RECORDED = json.loads(server.SAMPLES_PATH.read_text())
DHAI_SAU, DEDH_HAZAAR = server.SAMPLE_NOTES[0], server.SAMPLE_NOTES[2]


def recorded(request, timeout=None):
    note = json.loads(request.data)["messages"][1]["content"]
    return io.BytesIO(json.dumps({"choices": [{"message": {"content": RECORDED[note]}}]}).encode())


def failing(error):
    def fetch(request, timeout=None):
        raise error
    return fetch


def http_error(code, headers=None):
    return urllib.error.HTTPError(server.URL, code, "", headers or {}, None)


@mock.patch.object(server, "api_key", lambda: "test-key")
class ParseTest(unittest.TestCase):
    def test_honorifics_are_trimmed(self):
        for spoken in ("Ramesh bhai", "ramesh ji", "Shri Ramesh G", "Ramesh by", "RAMESH"):
            self.assertEqual(server.clean_name(spoken), "Ramesh")
        self.assertEqual(server.clean_name("Bhai"), "Bhai")

    def test_recorded_notes_become_entries(self):
        entry = lambda customer, amount, kind: {"customer": customer, "amount": amount, "type": kind}
        with mock.patch.object(server, "fetch", recorded):
            notes = [server.parse_note(note) for note in server.SAMPLE_NOTES]
        self.assertEqual(notes, [
            [entry("Ramesh", 250, "udhar"), entry("Suresh", 500, "payment")],
            [entry("Ramesh", 200, "udhar")],
            [entry("Nakad", 1500, "sale"), entry("Geeta Didi", 1250, "udhar")],
            [entry("Imran", 350, "payment"), entry("Imran", 80, "udhar")],
            [entry("Sunita", 1200, "udhar"), entry("Nakad", 2000, "sale"), entry("Ramesh", 100, "payment")],
        ])

    def test_request_uses_model_temperature_zero_and_json(self):
        seen = {}

        def spy(request, timeout=None):
            seen.update(json.loads(request.data), auth=request.get_header("Authorization"))
            return recorded(request)
        with mock.patch.object(server, "fetch", spy):
            server.parse_note(DHAI_SAU)
        self.assertEqual((seen["model"], seen["temperature"], seen["response_format"], seen["auth"]),
                         ("openai/gpt-oss-120b", 0, {"type": "json_object"}, "Bearer test-key"))

    def test_failures_map_to_plain_messages(self):
        cases = {"offline": urllib.error.URLError("down"), "key": http_error(401), "wait": http_error(429),
                 "cap": http_error(429, {"retry-after": "3600"}), "confused": http_error(500)}
        for code, error in cases.items():
            with mock.patch.object(server, "fetch", failing(error)), self.assertRaises(server.AIError) as caught:
                server.parse_note("x")
            self.assertEqual(caught.exception.code, code)
            self.assertIn(code, server.MESSAGES)

    def test_timeouts_and_dropped_connections_are_offline_or_confused(self):
        import http.client
        import socket
        for error, code in ((socket.timeout("slow"), "offline"), (ConnectionResetError(), "offline"),
                            (http.client.RemoteDisconnected("gone"), "offline"), (http.client.IncompleteRead(b""), "confused")):
            with mock.patch.object(server, "fetch", failing(error)), self.assertRaises(server.AIError) as caught:
                server.parse_note("x")
            self.assertEqual(caught.exception.code, code)

    def test_429_wait_seconds(self):
        for headers, seconds in (({"retry-after": "7.2"}, 7), ({}, 8), ({"retry-after": "soon"}, 8)):
            with mock.patch.object(server, "fetch", failing(http_error(429, headers))), self.assertRaises(server.AIError) as caught:
                server.parse_note("x")
            self.assertEqual((caught.exception.code, caught.exception.retry_after), ("wait", seconds))

    def test_bad_replies_are_confused(self):
        for raw in (None, [], [{"customer": "A", "amount": 0, "type": "udhar"}], [{"customer": "", "amount": 5, "type": "udhar"}],
                    [{"customer": "A", "amount": 5, "type": "gift"}], [{"customer": "A", "amount": "lots", "type": "sale"}], ["x"]):
            with self.assertRaises(server.AIError):
                server.clean_entries(raw)

    def test_missing_key(self):
        with mock.patch.object(server, "api_key", lambda: ""), self.assertRaises(server.AIError) as caught:
            server.parse_note("x")
        self.assertEqual(caught.exception.code, "key")


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.db = server.connect(":memory:")
        self.addCleanup(self.db.close)

    def rows(self):
        return self.db.execute("SELECT customer, amount, type FROM entries ORDER BY id").fetchall()

    def test_save_then_undo(self):
        ids = server.save(self.db, [{"customer": "Ramesh", "amount": 200, "type": "udhar"},
                                    {"customer": "Suresh", "amount": 50, "type": "payment"}])
        self.assertEqual(self.rows(), [("Ramesh", 200, "udhar"), ("Suresh", 50, "payment")])
        server.undo(self.db, ids[:1])
        self.assertEqual(self.rows(), [("Suresh", 50, "payment")])

    def test_balance_is_udhar_minus_payments_without_sales(self):
        entry = lambda customer, amount, kind: {"customer": customer, "amount": amount, "type": kind}
        ids = server.save(self.db, [
            entry("Ramesh", 250, "udhar"), entry("Ramesh", 200, "udhar"), entry("Ramesh", 100, "payment"),
            entry("Ramesh", 900, "sale"), entry("Geeta", 1250, "udhar"),
            entry("Suresh", 500, "udhar"), entry("Suresh", 500, "payment"), entry("Nakad", 1500, "sale"),
        ])
        self.assertEqual(server.balances(self.db), [{"customer": "Geeta", "balance": 1250},
                                                    {"customer": "Ramesh", "balance": 350}])
        server.undo(self.db, ids[2:3])
        self.assertEqual(server.balances(self.db)[1], {"customer": "Ramesh", "balance": 450})

    def test_state_splits_today_from_older(self):
        server.save(self.db, [{"customer": "Ramesh", "amount": 200, "type": "udhar"}, {"customer": "Nakad", "amount": 90, "type": "sale"}])
        self.db.execute("INSERT INTO entries (customer, amount, type, created_at) VALUES ('Old', 70, 'udhar', '2020-01-01 10:00:00')")
        state = server.state(self.db)
        self.assertEqual(state["today"], {"udhar": 200, "payment": 0, "sale": 90})
        self.assertEqual([e["customer"] for e in state["entries"]], ["Nakad", "Ramesh"])
        self.assertEqual([(e["customer"], e["at"]) for e in state["older"]], [("Old", "2020-01-01 10:00:00")])
        self.assertFalse(state["empty"])

    def test_sample_day_loads_only_into_an_empty_ledger(self):
        self.assertTrue(server.state(self.db)["empty"])
        self.assertTrue(server.load_sample(self.db))
        state = server.state(self.db)
        self.assertEqual(state["today"], {"udhar": 2980, "payment": 950, "sale": 3500})
        self.assertEqual(state["balances"], [{"customer": "Geeta Didi", "balance": 1250},
                                             {"customer": "Sunita", "balance": 1200}, {"customer": "Ramesh", "balance": 350}])
        self.assertFalse(server.load_sample(self.db))
        self.assertEqual(len(server.state(self.db)["entries"]), 10)


class HttpTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        handler = type("TestHandler", (server.Handler,), {"db_path": f"{folder.name}/test.db"})
        self.keep = server.connect(handler.db_path)
        self.web = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.web.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (self.web.shutdown(), self.web.server_close(), self.keep.close(), folder.cleanup()))

    def call(self, path, body=None):
        url = f"http://127.0.0.1:{self.web.server_port}{path}"
        data = None if body is None else json.dumps(body).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data)) as reply:
                return reply.status, reply.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def count(self):
        return self.keep.execute("SELECT count(*) FROM entries").fetchone()[0]

    def test_page_is_served(self):
        status, body = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("बोलो, लिखा गया".encode(), body)

    def test_nothing_is_saved_before_confirm_and_undo_removes(self):
        with mock.patch.object(server, "api_key", lambda: "k"), mock.patch.object(server, "fetch", recorded):
            status, body = self.call("/api/parse", {"note": DHAI_SAU})
        entries = json.loads(body)["entries"]
        self.assertEqual((status, len(entries), self.count()), (200, 2, 0))
        ids = json.loads(self.call("/api/confirm", {"entries": entries[:1]})[1])["ids"]
        self.assertEqual(self.count(), 1)
        self.assertEqual(json.loads(self.call("/api/state")[1])["balances"], [{"customer": "Ramesh", "balance": 250}])
        self.call("/api/undo", {"ids": ids})
        self.assertEqual(self.count(), 0)
        self.assertTrue(json.loads(self.call("/api/state")[1])["empty"])

    def test_ai_failure_returns_a_plain_message(self):
        with mock.patch.object(server, "api_key", lambda: "k"), \
                mock.patch.object(server, "fetch", failing(http_error(429, {"retry-after": "7"}))):
            status, body = self.call("/api/parse", {"note": "x"})
        self.assertEqual((status, json.loads(body)), (502, {"error": "wait", "message": server.MESSAGES["wait"], "retry_after": 7}))

    def test_sample_button_and_home_screen_files(self):
        self.assertEqual(json.loads(self.call("/api/sample", {})[1]), {"ok": True})
        self.assertEqual(self.count(), 10)
        manifest = json.loads(self.call("/manifest.json")[1])
        self.assertEqual((manifest["display"], len(manifest["icons"])), ("standalone", 2))
        status, png = self.call(manifest["icons"][0]["src"])
        self.assertEqual((status, png[:8], png[16:24]), (200, b"\x89PNG\r\n\x1a\n", (192).to_bytes(4, "big") * 2))

    def test_page_has_reminder_whatsapp_and_phone_basics(self):
        page = self.call("/")[1].decode()
        for part in ("wa.me/?text=", "जी, ${rs(d.balance)} बाकी हैं।", "second रुको", "min-height: 44px", "Noto+Sans",
                     'rel="manifest"', "width=device-width", "आज का हिसाब", "सब entries", "Sample day"):
            self.assertIn(part, page)

    def test_unexpected_errors_give_one_plain_line_not_a_traceback(self):
        plain = {"error": "oops", "message": server.MESSAGES["oops"]}
        with mock.patch.object(server, "parse_note", side_effect=RuntimeError("boom")):
            self.assertEqual(json.loads(self.call("/api/parse", {"note": "x"})[1]), plain)
        with mock.patch.object(server, "save", side_effect=server.sqlite3.OperationalError("disk full")):
            status, body = self.call("/api/confirm", {"entries": [{"customer": "A", "amount": 5, "type": "udhar"}]})
        self.assertEqual((status, json.loads(body)), (500, plain))
        with mock.patch.object(server, "state", side_effect=RuntimeError("boom")):
            self.assertEqual(json.loads(self.call("/api/state")[1]), plain)
        for message in server.MESSAGES.values():
            self.assertNotIn("\n", message)
            self.assertNotIn("Traceback", message)

    def test_bad_confirm_is_rejected(self):
        self.assertEqual(self.call("/api/confirm", {"entries": [{"customer": "A", "amount": -5, "type": "udhar"}]})[0], 400)
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
