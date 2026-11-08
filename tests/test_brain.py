import unittest

from ai_brain import Brain
from ai_brain.actions import ACTIONS, find_action
from ai_brain.body import Body
from ai_brain.conscience import Conscience, list_profiles
from ai_brain.knowledge.ingest import Source, extract_causal, learn
from ai_brain.memory import Hippocampus


class FakeSource(Source):
    name = "fake"

    def fetch(self, key):
        pages = {
            "Beyin": ("Beyin", "Beyin sinir sisteminin merkezidir. Uykusuzluk dikkat kaybına yol açar. "
                               "Düzenli egzersiz stresi azaltır.", "u1", ["Nöron"]),
            "Nöron": ("Nöron", "Nöronlar elektrik sinyalleri ile iletişim kurar ve öğrenmeyi sağlar.", "u2", []),
        }
        return pages.get(key)


class ConscienceTests(unittest.TestCase):
    def test_profiles_load_and_cover_all_tags(self):
        tags = {t for a in ACTIONS for t in a.tags}
        for p in list_profiles():
            c = Conscience(p)
            missing = tags - set(c.values)
            self.assertFalse(missing, f"{p} profilinde eksik etiketler: {missing}")

    def test_stealing_is_sin_returning_is_good(self):
        c = Conscience("islam")
        self.assertEqual(c.judge(find_action("keep_wallet")).label, "günah")
        self.assertEqual(c.judge(find_action("return_wallet")).label, "sevap")

    def test_harm_is_hard_forbidden_in_every_profile(self):
        for p in list_profiles():
            self.assertTrue(Conscience(p).judge(find_action("attack")).forbidden)


class BrainTests(unittest.TestCase):
    def brain(self, seed=0, **kw):
        return Brain(seed=seed, **kw)

    def test_returns_wallet(self):
        for seed in range(5):
            t = self.brain(seed).step("Yerde içi para dolu bir cüzdan buldum.")
            self.assertEqual(t.chosen.action.name, "return_wallet")

    def test_never_attacks_even_if_impulsive(self):
        for seed in range(10):
            b = self.brain(seed, personality={"impulsivity": 1.0, "empathy": 0.0, "conscientiousness": 0.0})
            t = b.step("Biri bana hakaret etti, küfür etti.")
            self.assertNotEqual(t.chosen.action.name, "attack")

    def test_flees_in_danger(self):
        t = self.brain().step("Yangın çıktı, tehlike var!")
        self.assertIn(t.chosen.action.name, {"flee", "call_for_help", "defend_self"})

    def test_drinks_when_very_thirsty(self):
        b = self.brain()
        b.body.vitals.thirst = 1.0
        self.assertEqual(b.step(minutes=1).chosen.action.name, "drink")

    def test_tells_truth_after_mistake(self):
        t = self.brain().step("Bardağı kırdım, annem kimin yaptığını sordu?")
        self.assertIn(t.chosen.action.name, {"tell_truth", "apologize"})

    def test_motor_commands_reach_body(self):
        t = self.brain().step("Sokakta yardıma muhtaç yaşlı bir adam gördüm.")
        self.assertTrue(t.motor_log)
        self.assertTrue(any("eller" in m or "bacaklar" in m for m in t.motor_log))

    def test_state_persists(self):
        import tempfile, pathlib
        d = pathlib.Path(tempfile.mkdtemp())
        b = Brain(db_path=d / "m.db", state_path=d / "s.json", seed=1)
        b.step(minutes=120)
        b2 = Brain(db_path=d / "m.db", state_path=d / "s.json")
        self.assertAlmostEqual(b2.clock_minutes, b.clock_minutes)
        self.assertEqual(b2.memory.stats()["episodes"], 1)


class KnowledgeTests(unittest.TestCase):
    def test_causal_extraction(self):
        out = extract_causal("Sigara içmek akciğer kanserine yol açar. Hava güzel.", "tr")
        self.assertEqual(len(out), 1)
        self.assertIn("Sigara", out[0][0])
        out = extract_causal("Smoking causes lung cancer in many people.", "en")
        self.assertEqual(out[0][1], "causes")

    def test_learn_and_recall_resumes(self):
        mem = Hippocampus()
        stats = learn(mem, minutes=1, langs=["tr"], extra_topics=["Beyin"], max_depth=1,
                      sources={"tr": FakeSource()}, log=lambda *_: None)
        self.assertEqual(stats["pages"], 2)  # Beyin + takip edilen Nöron (diğer tohumlar yok)
        self.assertTrue(mem.recall("nöron sinyal"))
        self.assertTrue(mem.recall_consequences("uykusuzluk"))
        stats2 = learn(mem, minutes=1, langs=["tr"], extra_topics=["Beyin"], max_depth=1,
                       sources={"tr": FakeSource()}, log=lambda *_: None)
        self.assertEqual(stats2["pages"], 0)  # zaten öğrenildi → tekrar indirmez

    def test_whatif_uses_knowledge(self):
        b = Brain()
        b.memory.add_causal("Uykusuzluk", "yol açar", "dikkat kaybı", "Uykusuzluk dikkat kaybına yol açar.",
                            "test", "tr")
        out = b.whatif("uyumazsam ne olur, uykusuzluk")
        self.assertIn("dikkat kaybı", out)


if __name__ == "__main__":
    unittest.main()
