"""Hipokampus: uzun süreli hafıza.

- facts:    dış dünyadan öğrenilen bilgiler (anlamsal hafıza), FTS5 ile aranır
- causal:   "X olursa Y olur" türü neden-sonuç cümleleri ("ne olur?" düşünmesi için)
- episodes: beynin yaşadığı olaylar (anısal hafıza)
- pages / frontier: bilgi toplayıcının nerede kaldığı (her çalışmada kaldığı yerden devam eder)
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts(
    id INTEGER PRIMARY KEY, title TEXT, text TEXT, source TEXT, lang TEXT, url TEXT, fetched_at REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(title, text, content='facts', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, title, text) VALUES (new.id, new.title, new.text); END;
CREATE TABLE IF NOT EXISTS causal(
    id INTEGER PRIMARY KEY, cause TEXT, relation TEXT, effect TEXT, sentence TEXT, source TEXT, lang TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS causal_fts USING fts5(cause, effect, sentence, content='causal', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS causal_ai AFTER INSERT ON causal BEGIN
    INSERT INTO causal_fts(rowid, cause, effect, sentence) VALUES (new.id, new.cause, new.effect, new.sentence); END;
CREATE TABLE IF NOT EXISTS episodes(
    id INTEGER PRIMARY KEY, t REAL, perception TEXT, context TEXT, action TEXT, moral TEXT,
    reward REAL, monologue TEXT);
CREATE TABLE IF NOT EXISTS commonsense(
    id INTEGER PRIMARY KEY, rel TEXT, start TEXT, end TEXT, start_lang TEXT, end_lang TEXT,
    weight REAL, surface TEXT);
CREATE INDEX IF NOT EXISTS cs_start ON commonsense(start, rel);
CREATE TABLE IF NOT EXISTS scripture(
    id INTEGER PRIMARY KEY, tradition TEXT, edition TEXT, ref TEXT, text TEXT, lang TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS scripture_fts USING fts5(text, content='scripture', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS scripture_ai AFTER INSERT ON scripture BEGIN
    INSERT INTO scripture_fts(rowid, text) VALUES (new.id, new.text); END;
CREATE TABLE IF NOT EXISTS ingest_progress(
    source TEXT, part TEXT, done INTEGER, finished INTEGER, updated REAL, PRIMARY KEY(source, part));
CREATE TABLE IF NOT EXISTS pages(key TEXT PRIMARY KEY, fetched_at REAL);
CREATE TABLE IF NOT EXISTS frontier(key TEXT PRIMARY KEY, depth INTEGER, added_at REAL);
"""

_WORD = re.compile(r"[\wçğıöşüÇĞİÖŞÜ]{2,}", re.UNICODE)
STOP = {"ve", "ile", "bir", "bu", "şu", "ne", "da", "de", "mi", "mı", "mu", "mü", "için", "olur",
        "nedir", "nasıl", "neden", "the", "a", "an", "of", "is", "what", "how", "why", "and", "or",
        "to", "in", "if", "ben", "ise", "yaparsam", "eğer", "kendine", "kendi", "yap", "et", "ver", "olan",
        "olarak", "gibi", "daha", "çok", "sonra", "önce", "kadar", "ama", "fakat", "ki", "yaparsak", "olursa"}


def fts_query(text: str) -> str:
    words = [w for w in _WORD.findall(text.lower()) if w not in STOP]
    # Türkçe ekleri tolere etmek için kelime köküne yakın önek araması
    terms = [f'"{w[:max(4, len(w) - 3)]}"*' if len(w) > 5 else f'"{w}"' for w in words]
    return " OR ".join(terms)


def expand_concepts(concepts: list[str]) -> list[str]:
    """İngilizce fiil biçimlerini genişletir: steal → stealing, lie → lying, run → running."""
    out: list[str] = []
    for c in concepts:
        c = c.lower().strip()
        first, _, rest = c.partition(" ")
        forms = {first, first + "ing"}
        if first.endswith("ie"):
            forms.add(first[:-2] + "ying")
        elif first.endswith("e"):
            forms.add(first[:-1] + "ing")
        if len(first) <= 4 and first[-1:] not in "aeiouwy":
            forms.add(first + first[-1] + "ing")
        for f in forms:
            out.append(f + (" " + rest if rest else ""))
    return list(dict.fromkeys(out))


class Hippocampus:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    # --- anlamsal hafıza -------------------------------------------------
    def add_fact(self, title: str, text: str, source: str, lang: str, url: str = "") -> None:
        self.db.execute("INSERT INTO facts(title,text,source,lang,url,fetched_at) VALUES(?,?,?,?,?,?)",
                        (title, text, source, lang, url, time.time()))

    def add_causal(self, cause: str, relation: str, effect: str, sentence: str, source: str, lang: str) -> None:
        self.db.execute("INSERT INTO causal(cause,relation,effect,sentence,source,lang) VALUES(?,?,?,?,?,?)",
                        (cause, relation, effect, sentence, source, lang))

    def add_commonsense_many(self, rows: list[tuple]) -> None:
        """rows: (rel, start, end, start_lang, end_lang, weight, surface)"""
        self.db.executemany("INSERT INTO commonsense(rel,start,end,start_lang,end_lang,weight,surface) "
                            "VALUES(?,?,?,?,?,?,?)", rows)

    def add_scripture(self, tradition: str, edition: str, ref: str, text: str, lang: str) -> None:
        self.db.execute("INSERT INTO scripture(tradition,edition,ref,text,lang) VALUES(?,?,?,?,?)",
                        (tradition, edition, ref, text, lang))

    def commit(self) -> None:
        self.db.commit()

    def optimize(self) -> None:
        self.db.commit()
        for t in ("facts_fts", "causal_fts", "scripture_fts"):
            self.db.execute(f"INSERT INTO {t}({t}) VALUES('optimize')")
        self.db.commit()

    def commonsense(self, concepts: list[str], rels: tuple[str, ...] | None = None,
                    limit: int = 12) -> list[dict]:
        """ConceptNet sağduyusu: kavramdan çıkan ilişkiler (ağırlığa göre)."""
        if not concepts:
            return []
        q = ("SELECT rel, start, end, weight, surface, start_lang FROM commonsense WHERE start IN (%s)"
             % ",".join("?" * len(expand_concepts(concepts))))
        params: list = expand_concepts(concepts)
        if rels:
            q += " AND rel IN (%s)" % ",".join("?" * len(rels))
            params += list(rels)
        q += " ORDER BY weight DESC LIMIT ?"
        params.append(limit)
        return [{"rel": r[0], "start": r[1], "end": r[2], "weight": r[3], "surface": r[4], "lang": r[5]}
                for r in self.db.execute(q, params).fetchall()]

    def scripture_ref(self, tradition: str, edition: str, ref: str) -> dict | None:
        r = self.db.execute("SELECT tradition, edition, ref, text, lang FROM scripture WHERE tradition=? "
                            "AND edition=? AND ref=?", (tradition, edition, ref)).fetchone()
        return {"tradition": r[0], "edition": r[1], "ref": r[2], "text": r[3], "lang": r[4]} if r else None

    def scripture_search(self, query: str, tradition: str | None = None, lang: str | None = None,
                         limit: int = 3) -> list[dict]:
        q = fts_query(query)
        if not q:
            return []
        sql = ("SELECT s.tradition, s.edition, s.ref, s.text, s.lang FROM scripture_fts "
               "JOIN scripture s ON s.id = scripture_fts.rowid WHERE scripture_fts MATCH ?")
        params: list = [q]
        if tradition:
            sql += " AND s.tradition = ?"
            params.append(tradition)
        if lang:
            sql += " AND s.lang = ?"
            params.append(lang)
        sql += " ORDER BY bm25(scripture_fts) LIMIT ?"
        params.append(limit)
        return [{"tradition": r[0], "edition": r[1], "ref": r[2], "text": r[3], "lang": r[4]}
                for r in self.db.execute(sql, params).fetchall()]

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        q = fts_query(query)
        if not q:
            return []
        rows = self.db.execute(
            "SELECT f.title, snippet(facts_fts, 1, '«', '»', ' … ', 40), f.url, f.lang "
            "FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid WHERE facts_fts MATCH ? "
            "ORDER BY bm25(facts_fts, 5.0, 1.0) LIMIT ?", (q, limit)).fetchall()
        return [{"title": r[0], "snippet": r[1], "url": r[2], "lang": r[3]} for r in rows]

    def recall_consequences(self, query: str, limit: int = 5, cause_only: bool = True) -> list[dict]:
        """Neden-sonuç cümleleri. cause_only: yalnızca 'neden' kısmı sorguyla eşleşenler (daha isabetli)."""
        q = fts_query(query)
        if not q:
            return []
        if cause_only:
            q = f"cause : ({q})"
        rows = self.db.execute(
            "SELECT c.cause, c.relation, c.effect, c.sentence, c.source FROM causal_fts "
            "JOIN causal c ON c.id = causal_fts.rowid WHERE causal_fts MATCH ? "
            "ORDER BY bm25(causal_fts, 4.0, 1.0, 1.0) LIMIT ?", (q, limit)).fetchall()
        return [{"cause": r[0], "relation": r[1], "effect": r[2], "sentence": r[3], "source": r[4]}
                for r in rows]

    # --- anısal hafıza ---------------------------------------------------
    def remember_episode(self, perception: str, context: set[str], action: str, moral: dict,
                         reward: float, monologue: str) -> None:
        self.db.execute("INSERT INTO episodes(t,perception,context,action,moral,reward,monologue) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (time.time(), perception, ",".join(sorted(context)), action,
                         json.dumps(moral, ensure_ascii=False), reward, monologue))
        self.db.commit()

    def similar_episodes(self, context: set[str], limit: int = 3) -> list[tuple[str, float]]:
        if not context:
            return []
        key = ",".join(sorted(context))
        return self.db.execute("SELECT action, AVG(reward) FROM episodes WHERE context=? GROUP BY action "
                               "ORDER BY AVG(reward) DESC LIMIT ?", (key, limit)).fetchall()

    # --- tarayıcı durumu -------------------------------------------------
    def seen(self, key: str) -> bool:
        return self.db.execute("SELECT 1 FROM pages WHERE key=?", (key,)).fetchone() is not None

    def mark_seen(self, key: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO pages VALUES(?,?)", (key, time.time()))
        self.db.execute("DELETE FROM frontier WHERE key=?", (key,))

    def push_frontier(self, keys: list[str], depth: int) -> None:
        self.db.executemany("INSERT OR IGNORE INTO frontier VALUES(?,?,?)",
                            [(k, depth, time.time()) for k in keys if not self.seen(k)])

    def pop_frontier(self) -> tuple[str, int] | None:
        row = self.db.execute("SELECT key, depth FROM frontier ORDER BY depth, added_at LIMIT 1").fetchone()
        return (row[0], row[1]) if row else None

    def requeue(self, key: str) -> None:
        self.db.execute("UPDATE frontier SET added_at=?, depth=depth+1 WHERE key=?", (time.time(), key))

    def drop_frontier(self, key: str) -> None:
        self.db.execute("DELETE FROM frontier WHERE key=?", (key,))

    def stats(self) -> dict[str, int]:
        out = {}
        for t in ("facts", "causal", "commonsense", "scripture", "episodes", "pages", "frontier"):
            out[t] = self.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return out
