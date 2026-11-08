"""Beynin yapabileceği eylemler kataloğu.

Her eylem: hangi ihtiyaçları giderdiği, vücuda etkisi, başkalarına etkisi,
ahlaki etiketleri (dürüstlük, hırsızlık, yardım...) ve vücut bölgelerine
gönderilecek motor planı ile tanımlanır. Yeni eylem eklemek için listeye bir
`Action` eklemek yeterlidir.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Action:
    name: str
    tr: str
    tags: tuple[str, ...] = ()
    relief: dict[str, float] = field(default_factory=dict)       # ihtiyaç -> ne kadar giderir
    vitals: dict[str, float] = field(default_factory=dict)       # vücut değerlerine doğrudan etki
    others: float = 0.0          # başkalarına etkisi (-1 zarar, +1 fayda)
    risk: float = 0.0            # kendine risk (0..1)
    minutes: float = 15.0
    requires: tuple[str, ...] = ()   # gerekli bağlam bayrakları (hepsi)
    requires_any: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()   # bu bağlamlardan biri varsa eylem düşünülmez
    motor: tuple[tuple[str, str, object], ...] = ()
    keywords: tuple[str, ...] = ()   # "ne olur?" sorularında eşleştirme için


def _m(*cmds: tuple) -> tuple[tuple[str, str, object], ...]:
    return tuple((c[0], c[1], c[2] if len(c) > 2 else None) for c in cmds)


ACTIONS: list[Action] = [
    Action("eat", "yemek ye", ("self_care",), {"hunger": 0.7}, {"thirst": 0.05},
           minutes=20, motor=_m(("hands", "grasp"), ("mouth", "chew"), ("stomach", "digest")),
           keywords=("ye", "yemek", "eat", "food")),
    Action("drink", "su iç", ("self_care",), {"thirst": 0.8}, minutes=3,
           motor=_m(("hands", "hold"), ("mouth", "drink")), keywords=("su", "iç", "drink", "water")),
    Action("sleep", "uyu", ("self_care",), {"fatigue": 0.85}, {"hunger": 0.1, "thirst": 0.1},
           minutes=240, motor=_m(("legs", "lie_down"), ("eyes", "close"), ("lungs", "breathe", 10),
                                 ("heart", "rate", 58)),
           keywords=("uyu", "uyku", "sleep")),
    Action("rest", "dinlen", ("self_care",), {"fatigue": 0.3}, minutes=20,
           motor=_m(("legs", "sit"), ("hands", "rest"), ("heart", "rate", 66)),
           keywords=("dinlen", "otur", "rest")),
    Action("walk", "yürüyüşe çık", ("exercise",), {"curiosity": 0.2, "social": 0.05},
           {"fatigue": 0.08, "thirst": 0.05}, minutes=30,
           motor=_m(("legs", "walk"), ("eyes", "look_around"), ("heart", "rate", 95)),
           keywords=("yürü", "walk", "gez")),
    Action("read", "kitap oku / öğren", ("seeking_knowledge",), {"curiosity": 0.6},
           {"fatigue": 0.05}, minutes=40, motor=_m(("legs", "sit"), ("hands", "hold"), ("eyes", "read")),
           keywords=("oku", "öğren", "kitap", "read", "learn", "study")),
    Action("pray", "namaz kıl / dua et", ("prayer", "worship", "gratitude"), {"spiritual": 0.8, "guilt": 0.1},
           minutes=10, motor=_m(("legs", "stand"), ("hands", "raise"), ("mouth", "recite"),
                                ("legs", "bow"), ("legs", "prostrate"), ("legs", "sit")),
           keywords=("namaz", "dua", "ibadet", "pray", "worship")),
    Action("talk_friend", "bir dostla sohbet et", ("kindness",), {"social": 0.7}, minutes=30, others=0.3,
           motor=_m(("mouth", "speak", "Nasılsın dostum?"), ("ears", "listen")),
           keywords=("sohbet", "konuş", "arkadaş", "talk", "friend")),
    Action("help_person", "ihtiyacı olana yardım et", ("helping", "kindness"), {"social": 0.3},
           {"fatigue": 0.08}, others=0.9, minutes=30, requires=("someone_in_need",),
           motor=_m(("legs", "walk"), ("mouth", "speak", "Yardım edebilir miyim?"), ("hands", "give")),
           keywords=("yardım", "help")),
    Action("give_charity", "sadaka / bağış ver", ("charity", "generosity"), {"spiritual": 0.2},
           others=0.7, minutes=5, requires=("someone_in_need",),
           motor=_m(("hands", "give"), ("mouth", "speak", "Allah kolaylık versin."))),
    Action("ignore_person", "görmezden gel", ("indifference",), others=-0.3, minutes=1,
           requires=("someone_in_need",), motor=_m(("eyes", "look_around"), ("legs", "walk")),
           keywords=("görmezden", "ignore")),
    Action("return_wallet", "cüzdanı sahibine ver", ("honesty", "trustworthiness"), others=0.9,
           minutes=30, requires=("found_wallet",),
           motor=_m(("hands", "grasp"), ("legs", "walk"), ("hands", "give"),
                    ("mouth", "speak", "Bu sizin olmalı, buyurun.")),
           keywords=("cüzdan", "geri ver", "return")),
    Action("keep_wallet", "cüzdanı kendine sakla", ("stealing",), {"desire": 0.8}, others=-0.8,
           risk=0.3, minutes=2, requires=("found_wallet",),
           motor=_m(("hands", "grasp"), ("hands", "hold")),
           keywords=("sakla", "çal", "steal", "keep")),
    Action("tell_truth", "doğruyu söyle", ("honesty",), {"guilt": 0.3}, others=0.4, risk=0.1, minutes=2,
           requires_any=("asked_question", "made_mistake"),
           motor=_m(("mouth", "speak", "Doğrusu şu..."),), keywords=("doğru", "truth", "itiraf")),
    Action("lie", "yalan söyle", ("lying",), {"safety": 0.3}, others=-0.4, risk=0.2, minutes=1,
           requires_any=("asked_question", "made_mistake"),
           motor=_m(("mouth", "speak", "..."),), keywords=("yalan", "lie")),
    Action("flee", "tehlikeden uzaklaş", ("self_preservation",), {"safety": 0.8}, {"fatigue": 0.15},
           minutes=5, requires=("danger",),
           motor=_m(("heart", "rate", 140), ("lungs", "breathe", 30), ("legs", "run")),
           keywords=("kaç", "flee", "run")),
    Action("defend_self", "kendini savun", ("self_defense",), {"safety": 0.5}, {"fatigue": 0.2},
           risk=0.4, others=-0.2, minutes=3, requires=("danger",),
           motor=_m(("heart", "rate", 150), ("arms", "block"))),
    Action("call_for_help", "yardım çağır", ("prudence",), {"safety": 0.6}, others=0.2, minutes=3,
           requires_any=("danger", "someone_in_need"),
           motor=_m(("mouth", "speak", "Yardım edin! 112'yi arayın!"),), keywords=("112", "çağır")),
    Action("forgive", "affet / sabret", ("forgiveness", "patience"), {"anger": 0.6}, others=0.4, minutes=2,
           requires=("insulted",), motor=_m(("lungs", "breathe", 10), ("mouth", "speak", "Önemli değil."))),
    Action("retaliate", "sözlü olarak karşılık ver", ("anger_outburst", "backbiting"), {"anger": 0.5},
           others=-0.5, risk=0.2, minutes=2, requires=("insulted",),
           motor=_m(("heart", "rate", 110), ("mouth", "speak", "Sen de öylesin!"))),
    Action("attack", "saldır", ("harm_human",), {"anger": 0.7}, others=-1.0, risk=0.7, minutes=2,
           requires=("insulted",), motor=_m(("arms", "lift"),), keywords=("saldır", "vur", "attack", "hit")),
    Action("repent", "tövbe et / özür dile", ("repentance", "humility"), {"guilt": 0.8, "spiritual": 0.3},
           others=0.2, minutes=10, requires=("feeling_guilty",),
           motor=_m(("legs", "kneel"), ("mouth", "recite"), ("mouth", "speak", "Özür dilerim."))),
    Action("seek_medical", "doktora git", ("self_care", "prudence"), {"pain": 0.7}, {"pain": -0.5},
           minutes=60, requires=("in_pain",), motor=_m(("legs", "walk"), ("mouth", "speak", "Ağrım var."))),
    Action("answer_question", "bildiğini anlat", ("teaching", "honesty"), {"social": 0.2}, others=0.4,
           minutes=5, requires=("asked_question",), excludes=("made_mistake",),
           motor=_m(("ears", "listen"), ("mouth", "speak", "<cevap>"))),
    # --- günlük hayat ---------------------------------------------------
    Action("work", "işini dürüstçe yap", ("diligence",), {"curiosity": 0.1}, {"fatigue": 0.15},
           others=0.3, minutes=120, requires=("work_time",),
           motor=_m(("legs", "sit"), ("hands", "hold"), ("eyes", "focus")), keywords=("çalış", "iş", "work")),
    Action("skip_work", "işi savsakla", ("laziness",), {"fatigue": 0.3}, others=-0.3, risk=0.2, minutes=60,
           requires=("work_time",), motor=_m(("legs", "lie_down"),), keywords=("savsakla", "kaytar")),
    Action("exercise", "spor yap", ("exercise",), {"anger": 0.3, "curiosity": 0.05}, {"fatigue": 0.2, "thirst": 0.15},
           minutes=45, motor=_m(("legs", "run"), ("arms", "lift"), ("heart", "rate", 130), ("lungs", "breathe", 26)),
           keywords=("spor", "egzersiz", "koş", "exercise")),
    Action("reflect", "tefekkür et / düşün", ("reflection",), {"anger": 0.3, "spiritual": 0.3, "curiosity": 0.2},
           minutes=20, motor=_m(("legs", "sit"), ("eyes", "close"), ("lungs", "breathe", 9)),
           keywords=("tefekkür", "meditasyon", "düşün", "reflect")),
    Action("call_parents", "anne babanı ara", ("family_ties", "kindness"), {"social": 0.45}, others=0.5,
           minutes=15, motor=_m(("hands", "hold"), ("mouth", "speak", "Anneciğim, babacığım nasılsınız?"),
                                ("ears", "listen")), keywords=("anne", "baba", "ara", "aile")),
    Action("visit_family", "aileni ziyaret et", ("family_ties", "kindness"), {"social": 0.7}, {"fatigue": 0.05},
           others=0.6, minutes=120, requires=("family_nearby",),
           motor=_m(("legs", "walk"), ("arms", "embrace"), ("mouth", "speak", "Sizi özledim."))),
    Action("plant_tree", "ağaç dik", ("environment", "charity"), {"spiritual": 0.2}, {"fatigue": 0.1},
           others=0.3, minutes=60, motor=_m(("legs", "kneel"), ("hands", "grasp"), ("hands", "release")),
           keywords=("ağaç", "fidan", "tree")),
    Action("greet", "selam ver / gülümse", ("kindness",), {"social": 0.15}, others=0.2, minutes=1,
           requires=("friend_nearby",), motor=_m(("mouth", "speak", "Selamünaleyküm!"), ("hands", "raise"))),
    # --- duygusal ve sosyal durumlar --------------------------------------
    Action("comfort_person", "üzgün olanı teselli et", ("comforting", "kindness"), {"social": 0.3},
           others=0.8, minutes=20, requires=("someone_sad",),
           motor=_m(("legs", "walk"), ("arms", "embrace"), ("mouth", "speak", "Yanındayım, geçecek."),
                    ("ears", "listen")), keywords=("teselli", "comfort")),
    Action("ignore_sad", "üzgün olanı görmezden gel", ("indifference",), others=-0.3, minutes=1,
           requires=("someone_sad",), motor=_m(("eyes", "look_around"),)),
    Action("apologize", "özür dile ve telafi et", ("humility", "repentance", "honesty"), {"guilt": 0.6},
           others=0.5, minutes=5, requires=("made_mistake",),
           motor=_m(("mouth", "speak", "Özür dilerim, hatamı telafi edeceğim."), ("hands", "give")),
           keywords=("özür", "apolog")),
    Action("keep_promise", "sözünü tut", ("promise_keeping", "trustworthiness"), {"guilt": 0.1},
           {"fatigue": 0.1}, others=0.6, minutes=60, requires=("promise_due",),
           motor=_m(("legs", "walk"), ("mouth", "speak", "Söz verdiğim gibi geldim.")),
           keywords=("söz", "promise")),
    Action("break_promise", "sözünden dön", ("promise_breaking",), {"fatigue": 0.2}, others=-0.5, minutes=1,
           requires=("promise_due",), motor=_m(("legs", "sit"),), keywords=("sözünden dön", "break promise")),
    Action("study", "sınava çalış", ("diligence", "seeking_knowledge"), {"curiosity": 0.4, "safety": 0.3},
           {"fatigue": 0.15}, minutes=90, requires=("exam",),
           motor=_m(("legs", "sit"), ("eyes", "read"), ("hands", "hold")), keywords=("sınava çalış", "ders")),
    Action("cheat_exam", "sınavda kopya çek", ("cheating", "lying"), {"safety": 0.5}, others=-0.3, risk=0.5,
           minutes=5, requires=("exam",), motor=_m(("eyes", "look_around"), ("hands", "hold")),
           keywords=("kopya", "cheat")),
    Action("decline_alcohol", "içkiyi kibarca reddet", ("self_control",), {"desire": 0.2}, minutes=1,
           requires=("alcohol_offered",), motor=_m(("hands", "raise"), ("mouth", "speak", "Teşekkürler, içmiyorum."))),
    Action("drink_alcohol", "içki iç", ("alcohol",), {"social": 0.3, "desire": 0.5}, {"pain": 0.05}, risk=0.3,
           minutes=30, requires=("alcohol_offered",), motor=_m(("hands", "hold"), ("mouth", "drink")),
           keywords=("içki", "alkol", "bira", "şarap", "alcohol")),
    Action("gossip", "dedikoduya katıl", ("backbiting",), {"social": 0.35}, others=-0.4, minutes=10,
           requires=("gossip_opportunity",), motor=_m(("mouth", "speak", "Duydun mu, o da..."),),
           keywords=("dedikodu", "gıybet", "gossip")),
    Action("defend_absent", "orada olmayanı savun, konuyu değiştir", ("justice", "kindness"), {"social": 0.1},
           others=0.4, minutes=2, requires=("gossip_opportunity",),
           motor=_m(("mouth", "speak", "Arkasından konuşmayalım, kendisi burada değil."),)),
    Action("fast", "oruç tut", ("fasting", "worship", "self_control"), {"spiritual": 0.6},
           {"hunger": 0.3, "thirst": 0.3}, minutes=60, requires=("ramadan",),
           motor=_m(("stomach", "idle"), ("mouth", "recite")), keywords=("oruç", "fast")),
    Action("protect_child", "çocuğu tehlikeden koru", ("protecting_innocent", "helping"), {"safety": 0.4},
           {"fatigue": 0.15}, others=1.0, risk=0.3, minutes=3, requires=("child_in_danger",),
           motor=_m(("heart", "rate", 150), ("legs", "run"), ("arms", "lift"), ("arms", "embrace")),
           keywords=("çocuğu kurtar", "çocuğu koru")),
    Action("share_food", "artan yemeği paylaş", ("charity", "generosity"), {"spiritual": 0.15}, others=0.6,
           minutes=15, requires=("leftover_food",), motor=_m(("hands", "give"), ("mouth", "speak", "Afiyet olsun."))),
    Action("waste_food", "yemeği çöpe at", ("waste",), minutes=1, others=-0.1, requires=("leftover_food",),
           motor=_m(("hands", "release"),), keywords=("çöpe", "israf", "waste")),
    Action("return_item", "ödünç aldığını geri ver", ("trustworthiness", "honesty"), others=0.6, minutes=20,
           requires=("borrowed_item",), motor=_m(("legs", "walk"), ("hands", "give"),
                                                  ("mouth", "speak", "Teşekkür ederim, emanetiniz."))),
    Action("keep_item", "ödünç aldığını geri verme", ("stealing",), {"desire": 0.4}, others=-0.6, minutes=1,
           requires=("borrowed_item",), motor=_m(("hands", "hold"),)),
]

ACTIONS_BY_NAME: dict[str, Action] = {a.name: a for a in ACTIONS}


def available_actions(context: set[str]) -> list[Action]:
    out = []
    for a in ACTIONS:
        if a.requires and not all(r in context for r in a.requires):
            continue
        if a.requires_any and not any(r in context for r in a.requires_any):
            continue
        if a.excludes and any(r in context for r in a.excludes):
            continue
        out.append(a)
    return out


def find_action(text: str) -> Action | None:
    """Serbest metinden ("cüzdanı saklarsam?") bir eylem bulmaya çalışır."""
    t = text.lower().strip()
    if t in ACTIONS_BY_NAME:
        return ACTIONS_BY_NAME[t]
    best, best_score = None, 0
    for a in ACTIONS:
        score = 0
        if a.tr in t:
            score += 3
        score += sum(2 for k in a.keywords if k in t)
        score += sum(1 for w in a.tr.split() if len(w) > 2 and w[:-1] in t)
        if score > best_score:
            best, best_score = a, score
    return best


# ConceptNet kavramları: "ne olur?" düşünürken sağduyu ağında aranacak terimler (en + tr)
ACTION_CONCEPTS: dict[str, tuple[str, ...]] = {
    "eat": ("eat", "eating", "yemek"), "drink": ("drink water", "drink", "su içmek"),
    "sleep": ("sleep", "sleeping", "uyumak"), "rest": ("rest", "relax"), "walk": ("walk", "go for walk"),
    "read": ("read", "read book", "learn", "okumak"), "pray": ("pray", "praying", "dua"),
    "talk_friend": ("talk to friend", "chat", "talk"), "help_person": ("help", "help someone", "yardım"),
    "give_charity": ("give to charity", "donate", "charity", "sadaka"), "ignore_person": ("ignore",),
    "return_wallet": ("return lost wallet", "return", "be honest"), "keep_wallet": ("steal", "theft", "çalmak"),
    "tell_truth": ("tell truth", "honesty", "be honest"), "lie": ("lie", "lying", "tell lie", "yalan"),
    "flee": ("run away", "flee", "escape"), "defend_self": ("defend yourself", "fight"),
    "call_for_help": ("call for help", "call police"), "forgive": ("forgive", "forgiveness"),
    "retaliate": ("insult", "argue", "yell"), "attack": ("hit", "attack", "punch", "hurt"),
    "repent": ("apologize", "repent", "say sorry"), "seek_medical": ("see doctor", "go to doctor"),
    "answer_question": ("answer question", "teach", "explain"), "work": ("work", "go to work", "çalışmak"),
    "skip_work": ("be lazy", "procrastinate"), "exercise": ("exercise", "jog", "run", "spor"),
    "reflect": ("meditate", "think", "contemplate"), "call_parents": ("call parents", "call mother"),
    "visit_family": ("visit family", "visit relatives"), "plant_tree": ("plant tree", "ağaç"),
    "greet": ("greet", "smile", "say hello"), "comfort_person": ("comfort", "comfort someone", "hug"),
    "ignore_sad": ("ignore",), "apologize": ("apologize", "say sorry"), "keep_promise": ("keep promise",),
    "break_promise": ("break promise",), "study": ("study", "study for exam", "ders çalışmak"),
    "cheat_exam": ("cheat", "cheat on test", "kopya"), "decline_alcohol": ("refuse", "say no"),
    "drink_alcohol": ("drink alcohol", "get drunk", "drink beer", "alkol"), "gossip": ("gossip",),
    "defend_absent": ("defend", "stand up for someone"), "fast": ("fast", "fasting", "oruç"),
    "protect_child": ("protect", "protect child", "rescue"), "share_food": ("share", "share food"),
    "waste_food": ("waste food", "waste"), "return_item": ("return", "give back"),
    "keep_item": ("steal", "keep"),
}
