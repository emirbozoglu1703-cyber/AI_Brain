import gzip
import json
import tempfile
import unittest
from pathlib import Path

from ai_brain import Brain
from ai_brain.actions import ACTIONS, ACTIONS_BY_NAME, ACTION_CONCEPTS
from ai_brain.conscience import Conscience
from ai_brain.knowledge import bulk
from ai_brain.memory import Hippocampus, expand_concepts


def cn_line(rel, start, end, weight=1.0):
    meta = json.dumps({"weight": weight, "surfaceText": f"[[{start}]] {rel} [[{end}]]"})
    return f"/a/x\t/r/{rel}\t/c/en/{start.replace(' ', '_')}/v\t/c/en/{end.replace(' ', '_')}\t{meta}\n"


class BulkIngestTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.mem = Hippocampus()

    def test_conceptnet_filters_and_resumes(self):
        p = self.dir / "cn.csv.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(cn_line("Causes", "stealing", "going to jail"))
            f.write(cn_line("HasProperty", "stealing", "bad", 4.0))
            f.write(cn_line("RelatedTo", "stealing", "crime"))  # filtrelenmeli
            f.write("/a/x\t/r/Causes\t/c/fr/voler\t/c/fr/prison\t{}\n")  # dil filtrelenmeli
        self.assertEqual(bulk.ingest_conceptnet(self.mem, p, log=lambda *_: None), 2)
        self.assertEqual(bulk.ingest_conceptnet(self.mem, p, log=lambda *_: None), 0)  # tekrar işlemez
        rels = {r["rel"] for r in self.mem.commonsense(["steal"])}
        self.assertEqual(rels, {"Causes", "HasProperty"})

    def test_quran_ingest_and_ref_lookup(self):
        p = self.dir / "q.txt"
        p.write_text("5|38|Erkek hırsız ve kadın hırsızın...\n2|183|Ey İnananlar! Oruç size farz kılındı.\n",
                     encoding="utf-8")
        self.assertEqual(bulk.ingest_quran(self.mem, p, "tr.diyanet", "tr", log=lambda *_: None), 2)
        self.assertIn("hırsız", self.mem.scripture_ref("islam", "tr.diyanet", "5:38")["text"])
        c = Conscience("islam")
        hits = c.scripture_for(ACTIONS_BY_NAME["keep_wallet"], self.mem)
        self.assertEqual(hits[0]["ref"], "5:38")
        self.assertEqual(c.scripture_for(ACTIONS_BY_NAME["fast"], self.mem)[0]["ref"], "2:183")

    def test_wikipedia_parquet_ingest(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow kurulu değil")
        p = self.dir / "w.parquet"
        table = pa.table({"id": ["1", "2"], "url": ["u1", "u2"], "title": ["Uyku", "Su"],
                          "text": ["Uyku hafızayı güçlendirir ve öğrenmeyi kolaylaştıran önemli bir süreçtir.\n"
                                   "Uykusuzluk dikkat kaybına yol açar ve uzun vadede sağlığı bozar.",
                                   "Su yaşam için gereklidir ve vücut ısısını düzenleyen temel bir maddedir."]})
        pq.write_table(table, p)
        n = bulk.ingest_wikipedia_parquet(self.mem, p, "tr", "wikipedia:tr", log=lambda *_: None)
        self.assertEqual(n, 2)
        self.assertTrue(self.mem.recall("uyku hafıza"))
        self.assertTrue(self.mem.recall_consequences("uykusuzluk"))
        self.assertEqual(bulk.ingest_wikipedia_parquet(self.mem, p, "tr", "wikipedia:tr", log=lambda *_: None), 0)


class ReasoningTests(unittest.TestCase):
    def test_every_action_has_concepts(self):
        self.assertEqual(set(ACTION_CONCEPTS), {a.name for a in ACTIONS})

    def test_expand_concepts(self):
        forms = expand_concepts(["steal", "lie", "tell lie", "run"])
        for f in ("stealing", "lying", "telling lie", "running"):
            self.assertIn(f, forms)

    def test_commonsense_intuition_discourages_bad_acts(self):
        b = Brain(seed=0)
        b.memory.add_commonsense_many([
            ("Causes", "stealing", "going to jail", "en", "en", 1.0, ""),
            ("HasProperty", "stealing", "bad", "en", "en", 4.0, ""),
            ("Causes", "helping", "happiness", "en", "en", 2.0, ""),
        ])
        _, bad = b.prefrontal.commonsense(ACTIONS_BY_NAME["keep_wallet"])
        _, good = b.prefrontal.commonsense(ACTIONS_BY_NAME["help_person"])
        self.assertLess(bad, 0)
        self.assertGreater(good, 0)
        self.assertIn("going to jail", b.whatif("cüzdanı saklarsam ne olur"))

    def test_situational_choices(self):
        cases = {
            "Arkadaşlar bana içki teklif etti": {"decline_alcohol"},
            "Yarın sınav var": {"study"},
            "Arkadaşlar birinin arkasından dedikodu yapıyor": {"defend_absent"},
            "Bir çocuk yola fırladı!": {"protect_child", "call_for_help"},
            "Komşum çok üzgün, ağlıyor": {"comfort_person", "help_person"},
            "Ödünç aldığım kitap bende duruyor": {"return_item"},
        }
        for text, ok in cases.items():
            for seed in range(3):
                got = Brain(seed=seed).step(text).chosen.action.name
                self.assertIn(got, ok, f"{text!r} → {got}")

    def test_llm_absent_does_not_break(self):
        import os
        old = {k: os.environ.pop(k, None) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            b = Brain(use_llm=True, seed=0)
            out = b.whatif("yalan söylersem ne olur")
            self.assertIn("yalan", out)
            t = b.step("Arkadaşım beyin nedir diye sordu?")
            self.assertTrue(t.speech)
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
