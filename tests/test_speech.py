import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from ai_brain import Brain
from ai_brain.language import OllamaCortex
from ai_brain.speech import SAY, Responder
from ai_brain.actions import ACTIONS


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"models": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.last = body
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"message": {"content": "Doğal cevap."}}).encode())


class SpeechTests(unittest.TestCase):
    def bot(self, seed=0):
        b = Brain(seed=seed)
        b.memory.add_fact("Amigdala", "Amigdala beynin temporal lobunda badem şeklinde bir yapıdır. "
                          "Korku ve duyguların işlenmesinde rol oynar.", "wikipedia:tr", "tr", "u")
        b.memory.add_fact("Amigo", "Amigo İspanyolca arkadaş demektir ve sıkça kullanılan bir kelimedir.",
                          "wikipedia:tr", "tr", "u2")
        return Responder(b)

    def test_every_action_has_a_sentence(self):
        self.assertEqual(set(SAY), {a.name for a in ACTIONS})

    def test_replies_are_short_and_hide_thinking(self):
        r = self.bot().reply("Yerde içi para dolu bir cüzdan buldum")
        self.assertIn("sahibine", r)
        for hidden in ("İhtiyaçlarım", "Düşünüyorum", "değer:", "Vücut:"):
            self.assertNotIn(hidden, r)
        self.assertLess(len(r), 600)

    def test_small_talk(self):
        bot = self.bot()
        self.assertIn("Aleykümselam", bot.reply("Merhaba"))
        self.assertIn("nasılsın", bot.reply("Nasılsın?").lower())
        self.assertIn("yapay zekâ", bot.reply("Sen kimsin?"))

    def test_situation_beats_bodily_needs(self):
        bot = self.bot()
        bot.brain.body.vitals.hunger = 0.95
        bot.brain.body.vitals.fatigue = 0.95
        self.assertIn("içki", bot.reply("Arkadaşlar bana içki teklif etti").lower())

    def test_whatif_and_question(self):
        bot = self.bot()
        self.assertIn("günah", bot.reply("Yalan söylersem ne olur?"))
        ans = bot.reply("Amigdala nedir?")
        self.assertIn("badem", ans)
        self.assertIn("Kaynak: Amigdala", ans)

    def test_ollama_used_when_running(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            cortex = OllamaCortex(host=f"http://127.0.0.1:{srv.server_port}")
            self.assertTrue(cortex.available)
            bot = self.bot()
            bot.brain.language = cortex
            self.assertEqual(bot.reply("Yerde içi para dolu bir cüzdan buldum"), "Doğal cevap.")
            sent = FakeOllama.last["messages"][1]["content"]
            self.assertIn("sahibine", sent)  # beyin kararı dil modeline iletildi
        finally:
            srv.shutdown()

    def test_ollama_absent(self):
        cortex = OllamaCortex(host="http://127.0.0.1:9")
        self.assertFalse(cortex.available)


if __name__ == "__main__":
    unittest.main()
