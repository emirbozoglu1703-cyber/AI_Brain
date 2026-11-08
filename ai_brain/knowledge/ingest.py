"""Bilgi toplayıcı: açık kaynaklardan (şimdilik Vikipedi TR/EN) öğrenir.

- Zaman bütçesiyle çalışır (ör. `--minutes 40`) ve kaldığı yerden devam eder
  (ziyaret edilen sayfalar ve sıradaki sayfalar veritabanında saklanır).
- Metni parçalara bölüp anlamsal hafızaya yazar.
- "X, Y'ye yol açar / neden olur / causes / leads to" kalıbındaki cümleleri
  neden-sonuç hafızasına çıkarır → beyin "bunu yaparsam ne olur?" diye
  düşünürken bunları kullanır.
- Kibar tarayıcı: kimlik belirten User-Agent, istekler arası bekleme, maxlag.

Yeni kaynak eklemek için `Source` sınıfını genişletmek yeterli.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterable

from ..memory import Hippocampus

USER_AGENT = "AI-Brain-learner/0.1 (open-source educational cognitive architecture)"

SEED_TOPICS: dict[str, list[str]] = {
    "tr": ["İnsan beyni", "Nöron", "Prefrontal korteks", "Amigdala", "Hipokampus", "Beyincik",
           "Duygu", "Karar verme", "Ahlak", "Etik", "Vicdan", "İslam ahlakı", "Günah", "Sevap",
           "Namaz", "Oruç", "Zekât", "Kur'an", "Hadis", "Din", "Felsefe", "Psikoloji",
           "Bilinç", "Hafıza", "Öğrenme", "İnsan vücudu", "Kalp", "Akciğer", "Beslenme", "Uyku",
           "Stres", "Empati", "Dürüstlük", "Hırsızlık", "Yalan", "Adalet", "Merhamet", "Aile",
           "Toplum", "Hukuk", "Tıp", "Fizik", "Kimya", "Biyoloji", "Tarih", "Matematik"],
    "en": ["Human brain", "Neuroscience", "Decision-making", "Morality", "Ethics", "Conscience",
           "Emotion", "Consciousness", "Memory", "Reinforcement learning", "Cognitive architecture",
           "Theory of mind", "Islamic ethics", "Sin", "Virtue", "Homeostasis", "Motor cortex",
           "Basal ganglia", "Causality", "Common sense", "Psychology", "Human body", "Sleep",
           "Nutrition", "Stress (biology)", "Empathy", "Honesty", "Theft", "Lie", "Justice"],
}

CAUSAL_PATTERNS = {
    "tr": re.compile(r"^(?P<cause>.{3,200}?)\s*(?P<rel>yol açar|yol açabilir|neden olur|neden olabilir|"
                     r"sebep olur|sebep olabilir|artırır|azaltır|engeller|önler|tetikler|sonuçlanır|"
                     r"etkiler|zarar verir|iyileştirir)(?P<effect>.{0,200})", re.IGNORECASE),
    "en": re.compile(r"^(?P<cause>.{3,200}?)\s+(?P<rel>causes|cause|leads to|lead to|results in|"
                     r"increases|decreases|reduces|prevents|triggers|can cause|may cause|"
                     r"is associated with|improves|damages)\s+(?P<effect>.{3,200})", re.IGNORECASE),
}
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, size: int = 900) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n{1,}", text) if len(p.strip()) > 40 and not p.startswith("==")]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            chunks.append(cur)
            cur = ""
        cur = (cur + "\n" + p).strip()
    if cur:
        chunks.append(cur)
    return chunks


def extract_causal(text: str, lang: str) -> list[tuple[str, str, str, str]]:
    pat = CAUSAL_PATTERNS.get(lang)
    if not pat:
        return []
    out = []
    for sent in SENTENCE_SPLIT.split(text.replace("\n", " ")):
        sent = sent.strip()
        if not (20 < len(sent) < 400):
            continue
        m = pat.search(sent)
        if m:
            out.append((m.group("cause").strip(" ,;:"), m.group("rel").lower(),
                        m.group("effect").strip(" .,;:"), sent))
    return out


class Source:
    name = "base"

    def fetch(self, key: str) -> tuple[str, str, str, list[str]] | None:
        """key → (başlık, düz metin, url, takip edilecek yeni anahtarlar)"""
        raise NotImplementedError


class WikipediaSource(Source):
    def __init__(self, lang: str, delay: float = 1.5, max_links: int = 25):
        self.lang = lang
        self.name = f"wikipedia:{lang}"
        self.delay = delay
        self.max_links = max_links
        self._last = 0.0

    def _get(self, params: dict) -> dict:
        wait = self.delay - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        params = {**params, "format": "json", "formatversion": 2, "maxlag": 5}
        url = f"https://{self.lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    self._last = time.time()
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (429, 503):
                    retry_after = e.headers.get("Retry-After", "")
                    wait_s = float(retry_after) if retry_after.isdigit() else 5 * 2 ** attempt
                    time.sleep(min(wait_s, 60))
                    self.delay = min(self.delay * 1.5, 10.0)  # sunucu yoruldu → yavaşla
                    continue
                raise
        raise RuntimeError("Vikipedi sürekli 'çok fazla istek' döndürüyor")

    def fetch(self, title: str):
        data = self._get({"action": "query", "prop": "extracts|links", "explaintext": 1, "titles": title,
                          "redirects": 1, "plnamespace": 0, "pllimit": self.max_links})
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return None
        p = pages[0]
        text = (p.get("extract") or "")[:40000]
        links = [l["title"] for l in p.get("links", [])][: self.max_links]
        url = f"https://{self.lang}.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))
        return p["title"], text, url, links


def learn(memory: Hippocampus, minutes: float = 40, langs: Iterable[str] = ("tr", "en"),
          max_pages: int | None = None, max_depth: int = 3, extra_topics: Iterable[str] = (),
          log: Callable[[str], None] = print, sources: dict[str, Source] | None = None) -> dict:
    """Zaman bütçesi dolana kadar öğrenir. Tekrar çağrıldığında kaldığı yerden devam eder."""
    langs = list(langs)
    sources = sources or {l: WikipediaSource(l) for l in langs}
    for l in langs:
        seeds = SEED_TOPICS.get(l, []) + list(extra_topics)
        memory.push_frontier([f"{l}|{t}" for t in seeds], 0)
    memory.commit()

    deadline = time.time() + minutes * 60
    stats = {"pages": 0, "facts": 0, "causal": 0, "errors": 0}
    while time.time() < deadline and (max_pages is None or stats["pages"] < max_pages):
        item = memory.pop_frontier()
        if not item:
            log("Öğrenilecek sayfa kalmadı.")
            break
        key, depth = item
        lang, _, title = key.partition("|")
        src = sources.get(lang)
        if src is None:
            memory.drop_frontier(key)
            continue
        try:
            res = src.fetch(title)
        except Exception as e:  # ağ hatası vb. → sayfayı sıranın sonuna at, sonra tekrar dene
            stats["errors"] += 1
            log(f"  ! {key}: {e}")
            memory.requeue(key)
            memory.commit()
            continue
        memory.mark_seen(key)
        if res is None:
            memory.commit()
            continue
        real_title, text, url, links = res
        memory.mark_seen(f"{lang}|{real_title}")
        for chunk in chunk_text(text):
            memory.add_fact(real_title, chunk, src.name, lang, url)
            stats["facts"] += 1
        for cause, rel, effect, sent in extract_causal(text, lang):
            memory.add_causal(cause, rel, effect, sent, f"{src.name}/{real_title}", lang)
            stats["causal"] += 1
        if depth < max_depth:
            memory.push_frontier([f"{lang}|{t}" for t in links], depth + 1)
        memory.commit()
        stats["pages"] += 1
        left = max(0, int(deadline - time.time()))
        log(f"  + [{lang}] {real_title}  (+{len(text)} karakter, kalan {left // 60}dk {left % 60}sn)")
    return stats
