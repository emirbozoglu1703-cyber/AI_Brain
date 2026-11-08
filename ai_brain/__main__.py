"""Komut satırı arayüzü.

  python -m ai_brain live --steps 8                # beyni kendi başına yaşat
  python -m ai_brain chat                          # algı yaz, beyin karar versin
  python -m ai_brain step "yerde bir cüzdan buldum"
  python -m ai_brain whatif "cüzdanı saklarsam ne olur"
  python -m ai_brain learn --minutes 40            # internetten öğren (kaldığı yerden devam eder)
  python -m ai_brain ask "amigdala nedir"
  python -m ai_brain status
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .brain import Brain
from .conscience import list_profiles
from .knowledge import learn

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
    return Brain(profile=args.profile, db_path=DATA / "memory.db", state_path=DATA / "state.json",
                 faith_strength=args.faith, seed=args.seed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ai_brain", description="Yapay zekâ destekli insan beyni")
    ap.add_argument("--profile", default="islam", choices=list_profiles(), help="inanç / değer profili")
    ap.add_argument("--faith", type=float, default=0.8, help="inanç gücü 0..1")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("-q", "--quiet", action="store_true", help="ne olur simülasyonlarını gösterme")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("live"); p.add_argument("--steps", type=int, default=8)
    sub.add_parser("chat")
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
    args = ap.parse_args(argv)
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
        print("Bir algı yaz (boş satır = zaman geçsin, 'çık' = çıkış, '?ne olur ...' = simülasyon)")
        while True:
            try:
                line = input("> " if sys.stdin.isatty() else "").strip()
            except EOFError:
                break
            if line in ("çık", "exit", "quit"):
                break
            if line.startswith("?"):
                print(brain.whatif(line[1:]))
            else:
                print(brain.step(line or None).monologue(verbose))
            print()
    elif args.cmd == "whatif":
        print(brain.whatif(args.text))
    elif args.cmd == "ask":
        res = brain.ask(args.question)
        if not res:
            print("Bu konuda bilgim yok. Önce `learn` çalıştır.")
        for r in res:
            print(f"• [{r['lang']}] {r['title']}: {r['snippet']}\n  {r['url']}")
    elif args.cmd == "status":
        print(brain.status())
    elif args.cmd == "learn":
        print(f"Öğrenme başlıyor: {args.minutes} dakika, diller: {', '.join(args.lang)}")
        stats = learn(brain.memory, minutes=args.minutes, langs=args.lang, max_pages=args.max_pages,
                      max_depth=args.depth, extra_topics=args.topic)
        print(f"Bitti: {stats}\nToplam hafıza: {brain.memory.stats()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
