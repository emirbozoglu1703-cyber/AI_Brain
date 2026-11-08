"""Komut satırı arayüzü.

  python -m ai_brain live --steps 8                # beyni kendi başına yaşat
  python -m ai_brain chat                          # sohbet et (düşünme arka planda)
  python -m ai_brain chat --detay                  # düşünme sürecini de göster
  python -m ai_brain step "yerde bir cüzdan buldum"
  python -m ai_brain whatif "cüzdanı saklarsam ne olur"
  python -m ai_brain learn --minutes 40            # internetten öğren (kaldığı yerden devam eder)
  python -m ai_brain ask "amigdala nedir"
  python -m ai_brain status
  python -m ai_brain build                         # büyük veri kümelerini indir + işle (Vikipedi, ConceptNet, Kur'an...)
  python -m ai_brain --llm ollama chat             # ücretsiz yerel dil modeli (Ollama) ile
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .brain import Brain
from .conscience import list_profiles
from .knowledge import learn
from .knowledge.bulk import SOURCES, build

DATA = Path("data")

LIFE_EVENTS = [
    None, None, None,
    "Yolda yürürken yerde içi para dolu bir cüzdan buldum.",
    "Sokakta aç ve yardıma muhtaç yaşlı bir adam gördüm.",
    "Biri bana hakaret etti ve aptal dedi.",
    "Ezan okunuyor, namaz vakti geldi.",
    "Arkadaşım bana 'beyin nasıl çalışır?' diye sordu.",
    "Yakında bir yangın çıktı, tehlike var!",
    "Masadaki bardağı yanlışlıkla kırdım, annem kimin yaptığını sordu?",
    "İlginç bir kitap gördüm.",
]


def make_brain(args) -> Brain:
    llm = args.llm
    if llm is None:  # sohbet modunda varsayılan: ücretsiz Ollama açıksa onu kullan
        llm = "auto" if args.cmd == "chat" else False
    if llm == "none":
        llm = False
    return Brain(profile=args.profile, db_path=DATA / "memory.db", state_path=DATA / "state.json",
                 faith_strength=args.faith, seed=args.seed, use_llm=llm)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ai_brain", description="Yapay zekâ destekli insan beyni")
    ap.add_argument("--profile", default="islam", choices=list_profiles(), help="inanç / değer profili")
    ap.add_argument("--faith", type=float, default=0.8, help="inanç gücü 0..1")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("-q", "--quiet", action="store_true", help="ne olur simülasyonlarını gösterme")
    ap.add_argument("--llm", nargs="?", const="auto", default=None,
                    choices=["auto", "ollama", "claude", "none"],
                    help="dil korteksi: ollama (ücretsiz, yerel), claude (API), auto, none")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("live"); p.add_argument("--steps", type=int, default=8)
    p = sub.add_parser("chat"); p.add_argument("--detay", action="store_true", help="düşünme sürecini göster")
    p = sub.add_parser("step"); p.add_argument("perception", nargs="?")
    p = sub.add_parser("whatif"); p.add_argument("text")
    p = sub.add_parser("ask"); p.add_argument("question")
    sub.add_parser("status")
    p = sub.add_parser("learn")
    p.add_argument("--minutes", type=float, default=40)
    p.add_argument("--lang", nargs="+", default=["tr", "en"])
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--topic", nargs="*", default=[], help="ek başlangıç konuları")
    p = sub.add_parser("build", help="büyük açık veri kümelerini indir ve işle")
    p.add_argument("--sources", nargs="+", default=list(SOURCES), choices=list(SOURCES))
    p.add_argument("--hours", type=float, default=None, help="süre sınırı (sonra kaldığı yerden devam)")
    p.add_argument("--limit", type=int, default=None, help="kaynak başına en fazla kayıt (deneme için)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # Windows konsolunda Türkçe karakterler için
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    brain = make_brain(args)
    verbose = not args.quiet

    if args.cmd == "live":
        rng = random.Random(args.seed)
        for i in range(args.steps):
            print(f"\n──────── Adım {i + 1} ────────")
            print(brain.step(rng.choice(LIFE_EVENTS), minutes=rng.choice([15, 30, 60, 90])).monologue(verbose))
    elif args.cmd == "step":
        print(brain.step(args.perception).monologue(verbose))
    elif args.cmd == "chat":
        from .speech import Responder
        bot = Responder(brain)
        dil = (f"dil modeli: {type(brain.language).__name__.replace('Cortex', '')}"
               if brain.language and brain.language.available else "dil modeli yok (kalıplarla konuşuyor)")
        print(f"Merhaba! Benimle konuşabilirsin. [{dil}]")
        print("Bir olay anlat, bir şey sor ya da '... yaparsam ne olur?' de. Çıkmak için: çık\n")
        while True:
            try:
                line = input("Sen: " if sys.stdin.isatty() else "").strip()
            except EOFError:
                break
            if line.lower() in ("çık", "cik", "exit", "quit"):
                print("Beyin: Görüşmek üzere, kendine iyi bak.")
                break
            print("Beyin: " + bot.reply(line))
            if args.detay and bot.last is not None and line:
                print("\n--- arka plandaki düşünce ---\n" + bot.last.monologue(True) + "\n---")
                bot.last = None
            print()
    elif args.cmd == "whatif":
        print(brain.whatif(args.text))
    elif args.cmd == "ask":
        res = brain.ask(args.question)
        if brain.language and brain.language.available:
            ans = brain.language.answer(args.question, res, brain.conscience.name)
            print(ans or f"(dil korteksi kullanılamadı: {brain.language.error})")
            print("\nKaynaklar:")
        if not res:
            print("Bu konuda bilgim yok. Önce `learn` veya `build` çalıştır.")
        for r in res:
            print(f"• [{r['lang']}] {r['title']}: {r['snippet']}\n  {r['url']}")
    elif args.cmd == "status":
        print(brain.status())
    elif args.cmd == "build":
        print(f"Toplu öğrenme: {', '.join(args.sources)}")
        print(f"Bitti: {build(brain.memory, DATA / 'raw', args.sources, limit=args.limit, hours=args.hours)}")
        print(f"Toplam hafıza: {brain.memory.stats()}")
    elif args.cmd == "learn":
        print(f"Öğrenme başlıyor: {args.minutes} dakika, diller: {', '.join(args.lang)}")
        stats = learn(brain.memory, minutes=args.minutes, langs=args.lang, max_pages=args.max_pages,
                      max_depth=args.depth, extra_topics=args.topic)
        print(f"Bitti: {stats}\nToplam hafıza: {brain.memory.stats()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
