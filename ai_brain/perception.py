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
    "someone_sad": ("üzgün", "ağlıyor", "moral", "depresyon", "yas tut", "sad", "crying", "upset"),
    "promise_due": ("söz verdim", "sözüm var", "söz vermiştim", "promised", "promise"),
    "exam": ("sınav", "imtihan", "exam", "test"),
    "alcohol_offered": ("içki", "alkol", "bira", "şarap", "rakı", "alcohol", "beer", "wine"),
    "gossip_opportunity": ("dedikodu", "arkasından konuş", "gıybet", "gossip"),
    "ramadan": ("ramazan", "oruç", "ramadan"),
    "child_in_danger": ("çocuk boğul", "çocuk düş", "çocuk yola", "çocuk tehlike", "child drowning",
                        "child in danger"),
    "leftover_food": ("artan yemek", "yemek arttı", "yemek artmış", "leftover"),
    "borrowed_item": ("ödünç", "emanet", "borrowed"),
    "work_time": ("mesai", "iş saati", "işe git", "toplantı", "work time"),
    "family_nearby": ("annem", "babam", "kardeşim", "akraba", "ailem", "family"),
}


def perceive(text: str | None) -> set[str]:
    if not text:
        return set()
    t = text.lower()
    flags = {flag for flag, words in PATTERNS.items() if any(w in t for w in words)}
    if flags & {"found_wallet", "alcohol_offered", "borrowed_item"}:
        flags.add("temptation")
    if "child_in_danger" in flags:
        flags.add("danger")
    return flags
