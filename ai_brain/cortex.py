"""Prefrontal korteks (hayal etme / "bunu yaparsam ne olur?"), bazal ganglionlar
(eylem seçimi ve alışkanlık öğrenme), motor korteks + beyincik (vücut kontrolü)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .actions import Action
from .body import Body
from .conscience import Conscience, MoralJudgment
from .limbic import DRIVE_TR
from .memory import Hippocampus


@dataclass
class Imagined:
    action: Action
    relief: dict[str, float]
    moral: MoralJudgment
    mood_delta: float
    risk: float
    others: float
    utility: float = 0.0
    knowledge: list[dict] = field(default_factory=list)

    def narrative(self) -> str:
        parts = [f"Eğer '{self.action.tr}' yaparsam:"]
        gains = [f"{DRIVE_TR.get(d, d)} %{int(v * 100)} azalır" for d, v in self.relief.items() if v > 0.05]
        if gains:
            parts.append("  • Kendim için: " + ", ".join(gains) + ".")
        if self.others > 0.1:
            parts.append(f"  • Başkalarına faydası olur (+{self.others:.1f}).")
        elif self.others < -0.1:
            parts.append(f"  • Başkalarına zarar verir ({self.others:.1f}).")
        if self.risk > 0.1:
            parts.append(f"  • Risk taşır (%{int(self.risk * 100)}).")
        parts.append(f"  • Ahlaki hüküm: {self.moral.label} (puan {self.moral.score:+.1f})"
                     + ("  ⛔ YASAK" if self.moral.forbidden else ""))
        for r in self.moral.reasons[:2]:
            parts.append(f"      – {r}")
        mood = "daha iyi" if self.mood_delta > 0.05 else "daha kötü" if self.mood_delta < -0.05 else "aynı"
        parts.append(f"  • Sonrasında kendimi {mood} hissederim.")
        for k in self.knowledge[:2]:
            parts.append(f"  • Bildiğim bir bilgi: \"{k['sentence'][:160]}\" ({k['source']})")
        return "\n".join(parts)


def urgency(level: float) -> float:
    """İhtiyaç arttıkça aciliyet doğrusal değil, hızla artar (susuzluk 1.0 ≫ 0.5)."""
    return 3.0 * level ** 2 + (8.0 * (level - 0.7) if level > 0.7 else 0.0)


class PrefrontalCortex:
    """Dünya modeli: eylemlerin sonuçlarını hayal eder ve deneyimle düzeltir."""

    def __init__(self, conscience: Conscience, memory: Hippocampus, personality: dict[str, float]):
        self.conscience = conscience
        self.memory = memory
        self.p = personality
        # Öğrenilmiş düzeltmeler: eylem -> ihtiyaç -> gerçekleşen/beklenen oranı
        self.learned: dict[str, dict[str, float]] = {}

    def predicted_relief(self, action: Action) -> dict[str, float]:
        corr = self.learned.get(action.name, {})
        return {d: v * corr.get(d, 1.0) for d, v in action.relief.items()}

    def imagine(self, action: Action, drives: dict[str, float], use_knowledge: bool = False) -> Imagined:
        relief = self.predicted_relief(action)
        moral = self.conscience.judge(action)
        faith = self.conscience.faith_strength
        mood = sum(drives.get(d, 0) * v for d, v in relief.items()) * 0.5
        mood += self.conscience.peace_after(moral) - self.conscience.guilt_after(moral)
        mood += action.others * 0.3 * self.p["empathy"]
        knowledge = self.memory.recall_consequences(action.tr) if use_knowledge else []
        im = Imagined(action, relief, moral, mood, action.risk, action.others, knowledge=knowledge)
        im.utility = self.utility(im, drives, faith)
        return im

    def utility(self, im: Imagined, drives: dict[str, float], faith: float) -> float:
        p = self.p
        need = sum(urgency(drives.get(d, 0)) * v for d, v in im.relief.items())
        moral = im.moral.score * 0.35 * (0.3 + faith) * p["conscientiousness"]
        if not (im.action.requires or im.action.requires_any) and moral > 0:
            # Her an yapılabilen iyi işler (dua, okuma...) ancak ilgili ihtiyaç varken öne çıkar;
            # böylece yangın sırasında namaza durmak gibi akıl dışı seçimler yapılmaz.
            relevance = max((drives.get(d, 0) for d in im.relief), default=0.0)
            moral *= min(1.0, relevance * 1.3)
        social = im.others * 1.2 * p["empathy"]
        risk = im.risk * 1.5 * (1 - p["impulsivity"])
        return need + moral + social + im.mood_delta - risk - im.action.minutes / 600

    def learn(self, action: Action, actual_relief: dict[str, float], lr: float = 0.2) -> None:
        corr = self.learned.setdefault(action.name, {})
        for d, expected in action.relief.items():
            if expected <= 0:
                continue
            ratio = actual_relief.get(d, 0.0) / expected
            corr[d] = corr.get(d, 1.0) + lr * (ratio - corr.get(d, 1.0))


class BasalGanglia:
    """Adaylar arasından seçim yapar. Düşük sıcaklıklı softmax: insan gibi küçük
    tutarsızlıklar olabilir ama 'deli gibi' rastgele davranmaz."""

    def __init__(self, temperature: float = 0.08, seed: int | None = None):
        self.temperature = temperature
        self.habit: dict[str, float] = {}   # alışkanlık / değer öğrenimi (Q değerleri)
        self.rng = random.Random(seed)
        self.recent: list[str] = []

    def select(self, options: list[Imagined]) -> Imagined:
        allowed = [o for o in options if not o.moral.forbidden]
        scores = []
        for o in allowed:
            s = o.utility + 0.3 * self.habit.get(o.action.name, 0.0)
            # Aynı şeyi ihtiyaç yokken tekrar tekrar yapmayı engelle (tutarlılık filtresi)
            s -= 0.4 * self.recent[-3:].count(o.action.name)
            o.utility = s
            scores.append(s)
        m = max(scores)
        weights = [math.exp((s - m) / self.temperature) for s in scores]
        choice = self.rng.choices(allowed, weights=weights, k=1)[0]
        self.recent = (self.recent + [choice.action.name])[-10:]
        return choice

    def reinforce(self, action: str, reward: float, lr: float = 0.15) -> None:
        q = self.habit.get(action, 0.0)
        self.habit[action] = q + lr * (reward - q)


class MotorSystem:
    """Motor korteks eylemi vücut komutlarına çevirir; beyincik uygulanabilirliği
    kontrol eder ve hareketleri yumuşatır; beyin sapı otomatik işlevleri ayarlar."""

    def execute(self, action: Action, body: Body) -> list[str]:
        logs = []
        for region, cmd, arg in action.motor:
            cmd, arg = self._cerebellum(region, cmd, arg, body)
            logs.append(body.apply(region, cmd, arg))
        for k, dv in action.vitals.items():
            setattr(body.vitals, k, getattr(body.vitals, k) + dv)
        body.vitals.clamp()
        return logs

    @staticmethod
    def _cerebellum(region: str, cmd: str, arg, body: Body):
        if region == "legs" and cmd == "run" and body.vitals.fatigue > 0.9:
            return "walk", arg  # çok yorgunken koşamaz
        if region == "heart" and arg is not None:
            arg = round(body.vitals.heart_rate + (float(arg) - body.vitals.heart_rate) * 0.7)
        return cmd, arg

    @staticmethod
    def brainstem(body: Body, fear: float) -> None:
        v = body.vitals
        target_hr = 68 + fear * 60
        v.heart_rate += (target_hr - v.heart_rate) * 0.3
        v.breath_rate += ((13 + fear * 12) - v.breath_rate) * 0.3
        v.clamp()
