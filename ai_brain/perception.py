"""Talamus: duyusal girdiyi (şimdilik metin) bağlam bayraklarına çevirir.

Gerçek entegrasyonda kamera/mikrofon/dokunma sensörlerinden gelen veriler
burada aynı bayraklara dönüştürülecek.
"""

from __future__ import annotations

PATTERNS: dict[str, tuple[str, ...]] = {
    "someone_in_need": ("yardım", "muhtaç", "aç biri", "ağlayan", "dilenci", "düştü", "yaşlı", "fakir",
                        "help", "homeless", "crying", "in need", "beggar"),
    "found_wallet": ("cüzdan", "para buldum", "yerde para", "wallet", "found money"),
    "danger": ("tehlike", "yangın", "saldırgan", "köpek saldır", "silah", "deprem", "fire", "danger",
               "attack", "earthquake", "gun"),
    "insulted": ("hakaret", "küfür", "aşağıla", "alay", "insult", "mock", "aptal dedi"),
    "asked_question": ("?", "soru", "sordu", "nedir", "neden", "nasıl", "kim", "what", "why", "how"),
    "made_mistake": ("hata yaptım", "kırdım", "bozdum", "suçlu", "mistake", "broke"),
    "prayer_time": ("ezan", "namaz vakti", "prayer time", "kilise çanı"),
    "good_news": ("müjde", "kazandı", "doğdu", "başardı", "good news"),
    "bad_news": ("vefat", "öldü", "kaybetti", "hastalandı", "bad news"),
    "food_available": ("yemek", "sofra", "ekmek", "food"),
    "friend_nearby": ("arkadaş", "dost", "friend"),
    "new_info": ("kitap", "haber", "ilginç", "book", "interesting"),
}


def perceive(text: str | None) -> set[str]:
    if not text:
        return set()
    t = text.lower()
    flags = {flag for flag, words in PATTERNS.items() if any(w in t for w in words)}
    if "found_wallet" in flags:
        flags.add("temptation")
    return flags
