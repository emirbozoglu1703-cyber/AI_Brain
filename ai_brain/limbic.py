"""Limbik sistem: Amigdala (duygular) + Hipotalamus (ihtiyaçlar / homeostaz)."""

from __future__ import annotations

from dataclasses import dataclass, field

EMOTIONS = ("joy", "fear", "anger", "sadness", "guilt", "peace", "curiosity")
EMOTION_TR = {"joy": "sevinç", "fear": "korku", "anger": "öfke", "sadness": "üzüntü",
              "guilt": "vicdan azabı", "peace": "huzur", "curiosity": "merak"}
BASELINE = {"joy": 0.3, "fear": 0.05, "anger": 0.05, "sadness": 0.1, "guilt": 0.0,
            "peace": 0.4, "curiosity": 0.3}

DRIVES = ("hunger", "thirst", "fatigue", "pain", "safety", "social", "curiosity",
          "spiritual", "guilt", "anger", "desire")
DRIVE_TR = {"hunger": "açlık", "thirst": "susuzluk", "fatigue": "yorgunluk", "pain": "ağrı",
            "safety": "güvenlik ihtiyacı", "social": "yalnızlık", "curiosity": "merak",
            "spiritual": "manevi ihtiyaç", "guilt": "vicdan rahatlatma", "anger": "öfke boşaltma",
            "desire": "nefsani arzu"}


@dataclass
class Amygdala:
    state: dict[str, float] = field(default_factory=lambda: dict(BASELINE))

    def decay(self, rate: float = 0.25) -> None:
        for k in EMOTIONS:
            self.state[k] += (BASELINE[k] - self.state[k]) * rate

    def feel(self, emotion: str, amount: float) -> None:
        self.state[emotion] = min(1.0, max(0.0, self.state[emotion] + amount))

    def appraise_context(self, context: set[str]) -> None:
        if "danger" in context:
            self.feel("fear", 0.6)
        if "insulted" in context:
            self.feel("anger", 0.5)
        if "someone_in_need" in context:
            self.feel("sadness", 0.2)
        if "good_news" in context:
            self.feel("joy", 0.4)
        if "bad_news" in context:
            self.feel("sadness", 0.4)
        if "made_mistake" in context:
            self.feel("guilt", 0.35)
            self.feel("fear", 0.2)
        if "new_info" in context:
            self.feel("curiosity", 0.3)

    @property
    def mood(self) -> float:
        s = self.state
        return (s["joy"] + s["peace"]) - (s["fear"] + s["anger"] + s["sadness"] + s["guilt"])

    def dominant(self) -> str:
        k = max(EMOTIONS, key=lambda e: self.state[e] - BASELINE[e] * 0.5)
        return EMOTION_TR[k]


@dataclass
class Hypothalamus:
    """Vücut ve duygu durumundan ihtiyaç (drive) seviyeleri üretir."""
    social_need: float = 0.2
    curiosity_need: float = 0.3
    spiritual_need: float = 0.3

    def tick(self, minutes: float, faith: float) -> None:
        self.social_need = min(1.0, self.social_need + 0.0012 * minutes)
        self.curiosity_need = min(1.0, self.curiosity_need + 0.0015 * minutes)
        self.spiritual_need = min(1.0, self.spiritual_need + 0.0035 * minutes * faith)

    def satisfy(self, drive: str, amount: float) -> None:
        attr = {"social": "social_need", "curiosity": "curiosity_need", "spiritual": "spiritual_need"}.get(drive)
        if attr:
            setattr(self, attr, max(0.0, getattr(self, attr) - amount))

    def drives(self, vitals: dict[str, float], emotions: dict[str, float], context: set[str]) -> dict[str, float]:
        return {
            "hunger": vitals["hunger"],
            "thirst": vitals["thirst"],
            "fatigue": vitals["fatigue"],
            "pain": vitals["pain"],
            "safety": emotions["fear"] if "danger" in context or emotions["fear"] > 0.3 else emotions["fear"] * 0.3,
            "social": self.social_need,
            "curiosity": max(self.curiosity_need, emotions["curiosity"] * 0.5),
            "spiritual": max(self.spiritual_need, 0.8) if "prayer_time" in context else self.spiritual_need,
            "guilt": emotions["guilt"],
            "anger": emotions["anger"],
            "desire": 0.6 if "temptation" in context else 0.0,
        }
