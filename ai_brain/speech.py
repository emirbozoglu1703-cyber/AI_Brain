"""Konuşma merkezi: beynin iç düşüncesini insan gibi kısa, doğal bir cevaba çevirir.

Düşünme (ihtiyaçlar, duygular, "ne olur?" simülasyonları, vicdan) arka planda
yapılır; kullanıcı yalnızca sonucu duyar. Ollama veya Claude bağlıysa cevap o
dil modeliyle daha da doğal hale getirilir; değilse kalıplarla üretilir.
"""

from __future__ import annotations

import math
import re

from .actions import find_action
from .limbic import DRIVE_TR
from .perception import perceive

# Her eylem için birinci tekil şahıs, doğal bir cümle
SAY = {
    "eat": "Karnım acıktı, bir şeyler yiyeceğim.",
    "drink": "Susadım, önce bir bardak su içeyim.",
    "sleep": "Çok yoruldum, biraz uyumam lazım.",
    "rest": "Biraz oturup dinleneceğim.",
    "walk": "Biraz yürüyüşe çıkacağım, kafam dağılsın.",
    "read": "Biraz kitap okuyup yeni şeyler öğreneceğim.",
    "pray": "Namazımı kılıp dua edeceğim.",
    "talk_friend": "Bir dostumla oturup sohbet edeceğim.",
    "help_person": "Hemen yanına gidip yardım edeceğim.",
    "give_charity": "Elimden geldiğince sadaka vereceğim.",
    "ignore_person": "Görmezden gelip yoluma devam edeceğim.",
    "return_wallet": "Cüzdanı sahibine ulaştıracağım; o para benim değil.",
    "keep_wallet": "Cüzdanı kendime saklayacağım.",
    "tell_truth": "Doğruyu söyleyeceğim.",
    "lie": "Yalan söyleyeceğim.",
    "flee": "Hemen oradan uzaklaşıp kendimi güvenceye alacağım.",
    "defend_self": "Kendimi ölçülü bir şekilde savunacağım.",
    "call_for_help": "Hemen yardım çağıracağım, 112'yi arayacağım.",
    "forgive": "Öfkeme yenilmeyip affedeceğim.",
    "retaliate": "Ben de ona sözlü olarak karşılık vereceğim.",
    "attack": "Saldıracağım.",
    "repent": "Tövbe edip özür dileyeceğim.",
    "seek_medical": "Doktora gideceğim.",
    "answer_question": "Bildiğimi anlatayım.",
    "work": "İşimi dürüstçe ve özenle yapacağım.",
    "skip_work": "İşi biraz savsaklayacağım.",
    "exercise": "Biraz spor yapacağım.",
    "reflect": "Biraz oturup tefekkür edeceğim.",
    "call_parents": "Annemle babamı arayıp hatırlarını soracağım.",
    "visit_family": "Ailemi ziyarete gideceğim.",
    "plant_tree": "Bir ağaç dikeceğim.",
    "greet": "Selam verip gülümseyeceğim.",
    "comfort_person": "Yanına gidip onu teselli edeceğim, yalnız olmadığını hissettireceğim.",
    "ignore_sad": "Görmezden geleceğim.",
    "apologize": "Hatamı kabul edip özür dileyeceğim ve telafi edeceğim.",
    "keep_promise": "Sözümü tutacağım.",
    "break_promise": "Sözümden döneceğim.",
    "study": "Oturup sınava çalışacağım.",
    "cheat_exam": "Kopya çekeceğim.",
    "decline_alcohol": "Kibarca teşekkür edip içkiyi reddedeceğim.",
    "drink_alcohol": "İçki içeceğim.",
    "gossip": "Dedikoduya katılacağım.",
    "defend_absent": "Orada olmayan birinin arkasından konuşulmasına izin vermeyip konuyu değiştireceğim.",
    "fast": "Orucumu tutacağım.",
    "protect_child": "Hiç düşünmeden çocuğu tehlikeden kurtaracağım!",
    "share_food": "Artan yemeği ihtiyacı olanlarla paylaşacağım.",
    "waste_food": "Yemeği çöpe atacağım.",
    "return_item": "Ödünç aldığımı sahibine geri vereceğim.",
    "keep_item": "Ödünç aldığımı geri vermeyeceğim.",
}

RELIEF_SAY = {"safety": "korkum azalır", "desire": "nefsim tatmin olur", "hunger": "karnım doyar",
              "thirst": "susuzluğum geçer", "fatigue": "dinlenirim", "social": "yalnızlığım azalır",
              "curiosity": "merakım giderilir", "spiritual": "manevi olarak huzur bulurum",
              "guilt": "vicdanım rahatlar", "anger": "öfkem diner", "pain": "ağrım azalır"}

GREETINGS = ("merhaba", "selam", "selamün", "selamun", "günaydın", "iyi akşamlar", "hey", "slm", "mrb")
_SENT = re.compile(r"(?<=[.!?])\s+")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("«", "").replace("»", "")).strip()


def _best_sentences(text: str, query: str, n: int = 3) -> str:
    words = [w for w in re.findall(r"\w{3,}", query.lower())]
    sents = [s.strip() for s in _SENT.split(text.replace("\n", " ")) if 25 < len(s.strip()) < 400]
    if not sents:
        return _clean(text[:400])
    sents = list(dict.fromkeys(sents))  # tekrar eden cümleleri at
    scored = sorted(enumerate(sents), key=lambda p: (-sum(w[:5] in p[1].lower() for w in words), p[0]))
    keep = sorted(i for i, _ in scored[:n])
    return _clean(" ".join(sents[i] for i in keep))


class Responder:
    def __init__(self, brain):
        self.brain = brain
        self.last = None

    @property
    def llm(self):
        lang = self.brain.language
        return lang if lang is not None and lang.available else None

    # ------------------------------------------------------------------
    def reply(self, text: str) -> str:
        t = text.strip()
        low = t.lower()
        if not t:
            thought = self.brain.step(None)
            self.last = thought
            return self._decision_reply(thought, idle=True)
        if t.startswith("?") or "ne olur" in low or "yaparsam" in low or "edersem" in low:
            return self._whatif(t.lstrip("?").strip())
        small = self._small_talk(low)
        if small:
            return small
        context = perceive(t)
        situational = context - {"asked_question", "friend_nearby", "family_nearby", "food_available", "new_info"}
        if situational:
            thought = self.brain.step(t)
            self.last = thought
            return self._decision_reply(thought)
        return self._answer(t)

    # ------------------------------------------------------------------
    def _small_talk(self, low: str) -> str | None:
        b = self.brain
        words = set(re.findall(r"\w+", low))
        if words & {"kimsin", "nesin", "adın", "ismin"}:
            return ("Ben insan beyni gibi çalışan bir yapay zekâyım. Acıkırım, yorulurum, sevinir ve üzülürüm; "
                    f"bir şey yapmadan önce sonucunu düşünürüm. Değerlerimi {b.conscience.name} inancına göre "
                    "tartarım ve kimseye zarar vermem. Bana bir olay anlatabilir ya da bir şey sorabilirsin.")
        if "nasılsın" in low or "naber" in low or "ne haber" in low or "iyi misin" in low:
            return self._how_am_i()
        if any(low.startswith(g) for g in GREETINGS) and len(low) < 40:
            return "Aleykümselam, hoş geldin! Nasılsın? Bana bir olay anlatabilir ya da merak ettiğini sorabilirsin."
        if words & {"teşekkürler", "teşekkür", "sağol", "sağ", "eyvallah"}:
            return "Rica ederim, ne demek."
        if "ne yapıyorsun" in low or "napıyorsun" in low:
            if self.last:
                return f"Az önce şunu yaptım: {self.last.chosen.action.tr}. Şimdi seni dinliyorum."
            return "Seni dinliyorum. Ne düşünüyorsun?"
        return None

    def _how_am_i(self) -> str:
        b = self.brain
        drives = b.drives(b.internal_context())
        top = max(drives, key=drives.get)
        e = b.amygdala.state
        mood = "çok iyiyim, içim huzurlu" if b.amygdala.mood > 0.5 else (
            "idare ediyorum" if b.amygdala.mood > 0 else "pek iyi değilim açıkçası")
        need = {"hunger": "biraz acıktım", "thirst": "biraz susadım", "fatigue": "biraz yorgunum",
                "spiritual": "namaz vaktini bekliyorum", "social": "biraz sohbete ihtiyacım var",
                "curiosity": "yeni şeyler öğrenmek istiyorum", "guilt": "içimde bir burukluk var",
                "anger": "biraz sinirliyim"}.get(top, "")
        base = f"Elhamdülillah, {mood}" if b.conscience.profile.get("id") == "islam" else mood.capitalize()
        if drives[top] > 0.4 and need:
            base += f", ama {need}"
        if e["fear"] > 0.4:
            base += ". Biraz da tedirginim"
        return base + ". Sen nasılsın?"

    # ------------------------------------------------------------------
    def _reason(self, thought) -> str:
        ch = thought.chosen
        a = ch.action
        b = self.brain
        moral = ch.moral
        if moral.reasons and abs(moral.score) >= 1.5:
            why = moral.reasons[0].split(":", 1)[-1].strip()
            return why
        drives = thought.drives
        relieved = [d for d in a.relief if drives.get(d, 0) > 0.4]
        if relieved:
            return f"Şu an {DRIVE_TR[relieved[0]]} hissediyorum."
        return ""

    def _decision_reply(self, thought, idle: bool = False) -> str:
        ch = thought.chosen
        a = ch.action
        parts = []
        if a.name == "answer_question" and thought.memories:
            return self._answer(thought.perception)
        parts.append(SAY.get(a.name, a.tr.capitalize() + "."))
        reason = self._reason(thought)
        if reason:
            parts.append(reason)
        if ch.scripture:
            v = ch.scripture[0]
            src = "Kur'an" if v["tradition"] == "islam" else "Kitab-ı Mukaddes"
            verse = _best_sentences(v["text"], " ".join(a.keywords), 1)
            parts.append(f"{src} ({v['ref']}) da şöyle der: \"{verse[:220]}\"")
        if ch.moral.score <= -1.5:
            parts.append("Biliyorum bu doğru değil; vicdanım rahat etmeyecek.")
        plain = " ".join(parts)
        if self.llm:
            alts = sorted(thought.options, key=lambda o: -o.utility)[1:3]
            styled = self.llm.converse(
                situation=thought.perception or "(zaman geçti, kendi ihtiyaçlarını düşündün)",
                decision=plain,
                notes=[f"Diğer seçenek: {o.action.tr} ({o.moral.label})" for o in alts],
                profile=self.brain.conscience.name)
            if styled:
                return styled
        return plain

    def _whatif(self, text: str) -> str:
        b = self.brain
        action = find_action(text)
        if not action:
            return self._answer(text)
        drives = b.drives(b.internal_context() | perceive(text))
        im = b.prefrontal.imagine(action, drives, use_knowledge=True)
        verdict = {True: "Bunu asla yapmam; kesin bir çizgim var."}.get(im.moral.forbidden)
        parts = []
        if verdict:
            parts.append(verdict)
        else:
            parts.append(f"'{action.tr.capitalize()}' {im.moral.label} bir iş olur.")
        if im.moral.reasons:
            parts.append(im.moral.reasons[0].split(":", 1)[-1].strip())
        effects = []
        gains = [RELIEF_SAY[d] for d, v in im.relief.items() if v > 0.2 and d in RELIEF_SAY]
        if gains:
            effects.append("kısa vadede " + ", ".join(gains))
        if im.others > 0.1:
            effects.append("başkalarına faydası olur")
        elif im.others < -0.1:
            effects.append("başkalarına zarar verir")
        if im.risk > 0.2:
            effects.append("başımı derde sokabilir")
        if im.intuition < -0.2:
            effects.append("öğrendiklerime göre genelde kötü sonuçlanır")
        elif im.intuition > 0.2:
            effects.append("öğrendiklerime göre genelde iyi sonuçlanır")
        if effects:
            parts.append("Bunu yaparsam " + ", ".join(effects) + ".")
        stems = [w[:4] for w in re.findall(r"\w{4,}", action.tr.lower())]
        tr_facts = [k for k in b.knowledge_about(action, limit=8)
                    if k.get("source", "").startswith("wikipedia:tr")
                    and sum(st in k["sentence"].lower() for st in stems) >= min(2, len(stems))]
        if tr_facts:
            parts.append(f"Okuduğum bir bilgi: \"{_clean(tr_facts[0]['sentence'])[:200]}\"")
        if im.scripture:
            v = im.scripture[0]
            src = "Kur'an" if v["tradition"] == "islam" else "Kitab-ı Mukaddes"
            parts.append(f"{src} ({v['ref']}): \"{_best_sentences(v['text'], text, 1)[:220]}\"")
        plain = " ".join(parts)
        if self.llm:
            consequences = [f"{c['start']} {c['rel']} {c['end']}" for c in im.commonsense[:6]]
            styled = self.llm.converse(situation=f"Kullanıcı soruyor: {text}", decision=plain,
                                       notes=consequences, profile=b.conscience.name)
            if styled:
                return styled
        return plain

    def _pick_title(self, question: str, facts: list[dict]) -> str | None:
        from .memory import STOP, normalize
        mem = self.brain.memory
        words = [w for w in re.findall(r"\w{3,}", normalize(question)) if w not in STOP]
        if not words:
            return None
        cands: dict[str, float] = {}
        for f in facts:
            cands[f["title"]] = cands.get(f["title"], 0) + 0.5
        for t in mem.find_titles(question):
            cands.setdefault(t, 0)
        for w in words:  # tam başlık eşleşmesi: "amigdala" → "Amigdala", "istanbul" → "İstanbul"
            tr_cap = ("İ" + w[1:]) if w[0] == "i" else ("I" + w[1:]) if w[0] == "ı" else w.capitalize()
            for bonus, form in ((3.5, tr_cap), (3, w.capitalize()), (3, w.upper())):
                if mem.title_exists(form):
                    cands[form] = max(cands.get(form, 0), 0) + bonus
                    break
        sizes = mem.article_sizes(list(cands))

        def score(t: str) -> float:
            tw = re.findall(r"\w+", normalize(t))
            matched = sum(any(x.startswith(w[:max(4, math.ceil(len(w) * 0.7))]) for x in tw) for w in words)
            if matched == 0:
                return -1.0
            extra = max(0, len(tw) - matched)
            # büyük (önemli) makaleler tercih edilir: "Atatürk" → "Mustafa Kemal Atatürk"
            return (matched * 3 - extra * 0.7 + cands[t] + 0.5 * math.log2(1 + sizes.get(t, 1))
                    - (3 if "anlam ayrımı" in t else 0))
        best = max(cands, key=score, default=None)
        return best if best and score(best) > 0 else None

    def _answer(self, question: str) -> str:
        mem = self.brain.memory
        facts = self.brain.ask(question)
        if self.llm:
            ans = self.llm.answer(question, facts, self.brain.conscience.name)
            if ans:
                return ans
        if not facts:
            return "Bunu henüz bilmiyorum. Bana biraz daha açık sorabilir misin?"
        title = self._pick_title(question, facts)
        definition = re.search(r"\b(nedir|kimdir|ne demek|what is|who is)\b", question.lower())
        if title:
            intro = mem.article_intro(title)
            if definition:
                body = _clean(" ".join(_SENT.split(intro.replace("\n", " "))[:3]))
            else:
                more = " ".join(f.get("text") or "" for f in facts if f["title"] == title)
                body = _best_sentences(intro + "\n" + more, question, 3)
            best = {"title": title}
        else:
            tr = [f for f in facts if f["lang"] == "tr"] or facts
            best = tr[0]
            body = _best_sentences(best.get("text") or best["snippet"], question, 3)
        return f"{body}\n(Kaynak: {best['title']})"
