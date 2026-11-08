"""Toplu bilgi yükleyici: büyük açık veri kümelerini indirip hafızaya işler.

Kaynaklar (hepsi açık lisanslı; bkz. NOTICE.md):
  wiki_tr      Türkçe Vikipedi'nin TAMAMI (düz metin, Hugging Face wikimedia/wikipedia)
  wiki_simple  Basit İngilizce Vikipedi'nin tamamı
  conceptnet   ConceptNet 5.7 sağduyu ağı (EN + TR): "X → neden olur → Y" vb. ~milyonlarca ilişki
  quran        Kur'an-ı Kerim: Diyanet meali (TR) + Sahih International (EN) — Tanzil.net
  gutenberg    Ahlak, felsefe, din ve psikoloji klasikleri (Project Gutenberg)

Her kaynak kaldığı yerden devam eder (ingest_progress tablosu). Bir kez
indirilmiş dosya tekrar indirilmez.
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Callable

from ..memory import Hippocampus
from .ingest import USER_AGENT, chunk_text, extract_causal

HF = "https://huggingface.co/datasets/wikimedia/wikipedia/resolve/main"
FILES = {
    "wiki_tr": [(f"{HF}/20231101.tr/train-00000-of-00002.parquet", "trwiki-0.parquet"),
                (f"{HF}/20231101.tr/train-00001-of-00002.parquet", "trwiki-1.parquet")],
    "wiki_simple": [(f"{HF}/20231101.simple/train-00000-of-00001.parquet", "simplewiki-0.parquet")],
    "conceptnet": [("https://conceptnet.s3.amazonaws.com/downloads/2019/edges/"
                    "conceptnet-assertions-5.7.0.csv.gz", "conceptnet-5.7.0.csv.gz")],
    "quran": [("https://tanzil.net/trans/?transID=tr.diyanet&type=txt-2", "quran-tr.diyanet.txt"),
              ("https://tanzil.net/trans/?transID=en.sahih&type=txt-2", "quran-en.sahih.txt")],
}

# Project Gutenberg kitap numaraları: ahlak, felsefe, din, psikoloji, insan doğası
GUTENBERG_BOOKS = {
    8438: "Aristoteles — Nikomakhos'a Etik", 2680: "Marcus Aurelius — Düşünceler",
    1497: "Platon — Devlet", 5682: "Kant — Ahlak Metafiziğinin Temelleri",
    5683: "Kant — Pratik Aklın Eleştirisi", 11224: "J. S. Mill — Faydacılık",
    3800: "Spinoza — Etika", 3330: "Konfüçyüs — Konuşmalar", 216: "Lao Tzu — Tao Te Ching",
    2388: "Bhagavad Gita", 2017: "Dhammapada", 10: "Kitab-ı Mukaddes (King James)",
    1227: "Darwin — İnsan ve Hayvanlarda Duyguların İfadesi", 57628: "W. James — Psikolojinin İlkeleri I",
    4280: "Kant — Saf Aklın Eleştirisi", 1232: "Machiavelli — Hükümdar", 3207: "Hobbes — Leviathan",
    7370: "Locke — Hükümet Üzerine İki İnceleme", 4705: "Hume — İnsan Doğası Üzerine İnceleme",
    5827: "B. Russell — Felsefenin Sorunları", 1998: "Nietzsche — Böyle Buyurdu Zerdüşt",
    4363: "Nietzsche — İyinin ve Kötünün Ötesinde", 2130: "Thomas More — Ütopya",
    3600: "Montaigne — Denemeler", 1656: "Platon — Sokrates'in Savunması",
    1658: "Platon — Phaidon", 1750: "Platon — Yasalar", 6762: "Aristoteles — Politika",
    10661: "Epiktetos — Enchiridion", 45109: "Epiktetos — Söylevler",
    3296: "Augustinus — İtiraflar",
}
CONCEPTNET_RELATIONS = {
    "Causes", "HasSubevent", "HasFirstSubevent", "HasLastSubevent", "HasPrerequisite",
    "MotivatedByGoal", "CausesDesire", "Desires", "NotDesires", "UsedFor", "CapableOf", "NotCapableOf",
    "ObstructedBy", "Entails", "HasProperty", "IsA", "PartOf", "AtLocation", "ReceivesAction",
    "CreatedBy", "MadeOf", "Antonym", "DistinctFrom", "HasA", "LocatedNear", "SymbolOf", "DefinedAs",
}
REL_TR = {
    "Causes": "neden olur", "HasSubevent": "sırasında olur", "HasFirstSubevent": "ilk adımı",
    "HasLastSubevent": "son adımı", "HasPrerequisite": "için önce gerekir", "MotivatedByGoal": "amacı",
    "CausesDesire": "isteği uyandırır", "Desires": "ister", "NotDesires": "istemez", "UsedFor": "işe yarar",
    "CapableOf": "yapabilir", "NotCapableOf": "yapamaz", "ObstructedBy": "engellenir", "Entails": "gerektirir",
    "HasProperty": "özelliği", "IsA": "bir türüdür", "PartOf": "parçasıdır", "AtLocation": "bulunur",
    "ReceivesAction": "şuna maruz kalır", "CreatedBy": "tarafından yapılır", "MadeOf": "yapılmıştır",
    "Antonym": "zıttı", "DistinctFrom": "farklıdır", "HasA": "sahiptir", "LocatedNear": "yakınında",
    "SymbolOf": "simgesidir", "DefinedAs": "tanımı",
}
SOURCES = ("quran", "conceptnet", "gutenberg", "wiki_simple", "wiki_tr")


def download(url: str, dest: Path, log: Callable[[str], None]) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"  ↓ indiriliyor: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)
    return dest


class Progress:
    def __init__(self, memory: Hippocampus):
        self.db = memory.db

    def get(self, source: str, part: str) -> int:
        row = self.db.execute("SELECT done FROM ingest_progress WHERE source=? AND part=?",
                              (source, part)).fetchone()
        return row[0] if row else 0

    def set(self, source: str, part: str, done: int, finished: bool = False) -> None:
        self.db.execute("INSERT OR REPLACE INTO ingest_progress VALUES(?,?,?,?,?)",
                        (source, part, done, int(finished), time.time()))

    def finished(self, source: str, part: str) -> bool:
        row = self.db.execute("SELECT finished FROM ingest_progress WHERE source=? AND part=?",
                              (source, part)).fetchone()
        return bool(row and row[0])


# ---------------------------------------------------------------------------
def ingest_wikipedia_parquet(memory: Hippocampus, path: Path, lang: str, source: str,
                             log: Callable[[str], None], limit: int | None = None,
                             deadline: float | None = None) -> int:
    import pyarrow.parquet as pq  # isteğe bağlı bağımlılık

    prog = Progress(memory)
    part = path.name
    if prog.finished(source, part):
        log(f"  = {part} zaten işlendi")
        return 0
    start = prog.get(source, part)
    pf = pq.ParquetFile(path)
    total = pf.metadata.num_rows
    row_i, added, t0 = 0, 0, time.time()
    for batch in pf.iter_batches(batch_size=1000, columns=["url", "title", "text"]):
        n = batch.num_rows
        if row_i + n <= start:
            row_i += n
            continue
        cols = batch.to_pydict()
        for i in range(n):
            if row_i + i < start:
                continue
            title, text, url = cols["title"][i], cols["text"][i] or "", cols["url"][i]
            for chunk in chunk_text(text):
                memory.add_fact(title, chunk, source, lang, url)
            for cause, rel, effect, sent in extract_causal(text, lang):
                memory.add_causal(cause, rel, effect, sent, f"{source}/{title}", lang)
            added += 1
        row_i += n
        prog.set(source, part, row_i)
        memory.commit()
        if row_i % 20000 < 1000:
            rate = added / max(1e-6, time.time() - t0)
            log(f"  [{source}] {row_i:,}/{total:,} makale  ({rate:.0f} makale/sn)")
        if (limit and added >= limit) or (deadline and time.time() > deadline):
            return added
    prog.set(source, part, row_i, finished=True)
    memory.commit()
    return added


def _cn_term(uri: str) -> tuple[str, str] | None:
    # /c/en/eat_food/v/... → ("en", "eat food")
    parts = uri.split("/")
    if len(parts) < 4 or parts[1] != "c" or parts[2] not in ("en", "tr"):
        return None
    return parts[2], parts[3].replace("_", " ")


def ingest_conceptnet(memory: Hippocampus, path: Path, log: Callable[[str], None],
                      limit: int | None = None, deadline: float | None = None) -> int:
    prog = Progress(memory)
    part = path.name
    if prog.finished("conceptnet", part):
        log("  = ConceptNet zaten işlendi")
        return 0
    start = prog.get("conceptnet", part)
    added, line_no = 0, 0
    rows: list[tuple] = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line_no += 1
            if line_no <= start:
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            rel = cols[1].rsplit("/", 1)[-1]
            if rel not in CONCEPTNET_RELATIONS:
                continue
            s, e = _cn_term(cols[2]), _cn_term(cols[3])
            if not s or not e:
                continue
            try:
                meta = json.loads(cols[4])
            except json.JSONDecodeError:
                meta = {}
            rows.append((rel, s[1], e[1], s[0], e[0], float(meta.get("weight", 1.0)),
                         meta.get("surfaceText") or ""))
            if len(rows) >= 20000:
                memory.add_commonsense_many(rows)
                added += len(rows)
                rows.clear()
                prog.set("conceptnet", part, line_no)
                memory.commit()
                if added % 200000 < 20000:
                    log(f"  [conceptnet] {added:,} ilişki (satır {line_no:,})")
                if (limit and added >= limit) or (deadline and time.time() > deadline):
                    return added
    if rows:
        memory.add_commonsense_many(rows)
        added += len(rows)
    prog.set("conceptnet", part, line_no, finished=True)
    memory.commit()
    return added


def ingest_quran(memory: Hippocampus, path: Path, edition: str, lang: str, log: Callable[[str], None]) -> int:
    prog = Progress(memory)
    if prog.finished("quran", edition):
        log(f"  = Kur'an ({edition}) zaten işlendi")
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        sura, aya, text = parts
        ref = f"{sura}:{aya}"
        title = f"Kur'an {ref}" if lang == "tr" else f"Quran {ref}"
        memory.add_fact(title, text.strip(), f"quran:{edition}", lang,
                        f"https://quran.com/{sura}/{aya}")
        memory.add_scripture("islam", edition, ref, text.strip(), lang)
        n += 1
    prog.set("quran", edition, n, finished=True)
    memory.commit()
    return n


_GB_START = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I | re.S)
_GB_END = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG", re.I)


def ingest_gutenberg(memory: Hippocampus, raw: Path, log: Callable[[str], None],
                     deadline: float | None = None) -> int:
    prog = Progress(memory)
    n = 0
    for book_id, name in GUTENBERG_BOOKS.items():
        key = str(book_id)
        if prog.finished("gutenberg", key):
            continue
        if deadline and time.time() > deadline:
            break
        dest = raw / "gutenberg" / f"pg{book_id}.txt"
        try:
            download(f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt", dest, log)
            time.sleep(1.5)
        except Exception as e:  # bir kitap alınamazsa diğerlerine devam
            log(f"  ! Gutenberg {book_id}: {e}")
            continue
        text = dest.read_text(encoding="utf-8", errors="replace")
        m = _GB_START.search(text)
        if m:
            text = text[m.end():]
        m = _GB_END.search(text)
        if m:
            text = text[:m.start()]
        title_m = re.search(r"^Title:\s*(.+)$", dest.read_text(encoding="utf-8", errors="replace"), re.M)
        title = title_m.group(1).strip() if title_m else name
        url = f"https://www.gutenberg.org/ebooks/{book_id}"
        chunks = chunk_text(text.replace("\r", ""), size=1200)
        for i, chunk in enumerate(chunks):
            memory.add_fact(f"{title} §{i + 1}", chunk, "gutenberg", "en", url)
        for cause, rel, effect, sent in extract_causal(text, "en"):
            memory.add_causal(cause, rel, effect, sent, f"gutenberg/{title}", "en")
        if book_id == 10:  # Kitab-ı Mukaddes → Hristiyanlık profili için kutsal metin
            for i, chunk in enumerate(chunks):
                memory.add_scripture("christianity", "kjv", f"§{i + 1}", chunk, "en")
        prog.set("gutenberg", key, len(chunks), finished=True)
        memory.commit()
        log(f"  ✓ Gutenberg: {title} ({len(chunks)} parça)")
        n += 1
    return n


def build(memory: Hippocampus, raw_dir: str | Path = "data/raw", sources=SOURCES,
          log: Callable[[str], None] = print, limit: int | None = None,
          hours: float | None = None) -> dict:
    """Seçilen kaynakları indirip işler. `hours` verilirse süre dolunca durur (sonra devam eder)."""
    raw = Path(raw_dir)
    deadline = time.time() + hours * 3600 if hours else None
    report: dict[str, int] = {}
    for src in sources:
        if deadline and time.time() > deadline:
            log("Süre doldu; bir sonraki çalıştırmada kaldığı yerden devam edecek.")
            break
        log(f"▶ {src}")
        t0 = time.time()
        if src == "gutenberg":
            report[src] = ingest_gutenberg(memory, raw, log, deadline)
        else:
            count = 0
            for url, name in FILES[src]:
                path = download(url, raw / name, log)
                if src == "wiki_tr":
                    count += ingest_wikipedia_parquet(memory, path, "tr", "wikipedia:tr", log, limit, deadline)
                elif src == "wiki_simple":
                    count += ingest_wikipedia_parquet(memory, path, "en", "wikipedia:simple", log, limit, deadline)
                elif src == "conceptnet":
                    count += ingest_conceptnet(memory, path, log, limit, deadline)
                elif src == "quran":
                    edition = name.split("-", 1)[1].rsplit(".", 1)[0]
                    count += ingest_quran(memory, path, edition, "tr" if edition.startswith("tr") else "en", log)
            report[src] = count
        log(f"  ✓ {src}: {report[src]:,} kayıt, {time.time() - t0:.0f} sn")
    memory.optimize()
    return report


__all__ = ["build", "SOURCES", "REL_TR", "GUTENBERG_BOOKS"]
