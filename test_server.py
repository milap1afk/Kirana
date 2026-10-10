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

# Model replies in the shape Groq returns them, so the tests need no key.
RECORDED = {
    "ramesh bhai ko dhai sau ka udhar diya, aur suresh ji ne paanch sau jama kiye":
        '{"entries":[{"customer":"Ramesh bhai","amount":250,"type":"udhar"},'
        '{"customer":"Suresh ji","amount":500,"type":"payment"}]}',
    "aaj dedh hazaar ki nakad bikri hui, haan aur geeta didi ne sawa hazaar ka udhar liya":
        '{"entries":[{"customer":"","amount":1500,"type":"sale"},'
        '{"customer":"Geeta didi","amount":1250,"type":"udhar"}]}',
}


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
        with mock.patch.object(server, "fetch", recorded):
            notes = [server.parse_note(note) for note in RECORDED]
        self.assertEqual(notes[0], [{"customer": "Ramesh", "amount": 250, "type": "udhar"},
                                    {"customer": "Suresh", "amount": 500, "type": "payment"}])
        self.assertEqual(notes[1], [{"customer": "Nakad", "amount": 1500, "type": "sale"},
                                    {"customer": "Geeta Didi", "amount": 1250, "type": "udhar"}])

    def test_request_uses_model_temperature_zero_and_json(self):
        seen = {}

        def spy(request, timeout=None):
            seen.update(json.loads(request.data), auth=request.get_header("Authorization"))
            return recorded(request)
        with mock.patch.object(server, "fetch", spy):
            server.parse_note(next(iter(RECORDED)))
        self.assertEqual((seen["model"], seen["temperature"], seen["response_format"], seen["auth"]),
                         ("openai/gpt-oss-120b", 0, {"type": "json_object"}, "Bearer test-key"))

    def test_failures_map_to_plain_messages(self):
        cases = {"offline": urllib.error.URLError("down"), "key": http_error(401),
                 "cap": http_error(429, {"retry-after": "7"}), "confused": http_error(500)}
        for code, error in cases.items():
            with mock.patch.object(server, "fetch", failing(error)), self.assertRaises(server.AIError) as caught:
                server.parse_note("x")
            self.assertEqual(caught.exception.code, code)
            self.assertIn(code, server.MESSAGES)
        self.assertEqual(caught.exception.retry_after, None)

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
            status, body = self.call("/api/parse", {"note": next(iter(RECORDED))})
        entries = json.loads(body)["entries"]
        self.assertEqual((status, len(entries), self.count()), (200, 2, 0))
        ids = json.loads(self.call("/api/confirm", {"entries": entries[:1]})[1])["ids"]
        self.assertEqual(self.count(), 1)
        self.assertEqual(json.loads(self.call("/api/balances")[1]), {"balances": [{"customer": "Ramesh", "balance": 250}]})
        self.call("/api/undo", {"ids": ids})
        self.assertEqual(self.count(), 0)
        self.assertEqual(json.loads(self.call("/api/balances")[1]), {"balances": []})

    def test_ai_failure_returns_a_plain_message(self):
        with mock.patch.object(server, "api_key", lambda: "k"), \
                mock.patch.object(server, "fetch", failing(http_error(429, {"retry-after": "7"}))):
            status, body = self.call("/api/parse", {"note": "x"})
        self.assertEqual((status, json.loads(body)), (502, {"error": "cap", "message": server.MESSAGES["cap"], "retry_after": "7"}))

    def test_bad_confirm_is_rejected(self):
        self.assertEqual(self.call("/api/confirm", {"entries": [{"customer": "A", "amount": -5, "type": "udhar"}]})[0], 400)
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
