"""Simüle edilmiş insan vücudu.

Beyin bu vücudu bölge bölge kontrol eder. Gerçek bir donanım/robot entegrasyonu
yapıldığında yalnızca bu dosyadaki `Body.apply` metodu gerçek aktüatörlere
(motorlar, hoparlör, kamera...) bağlanacak şekilde değiştirilir; beynin geri
kalanı aynı kalır.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BodyRegion:
    name: str
    tr_name: str
    controlled_by: str  # bu bölgeyi yöneten beyin bölgesi
    commands: tuple[str, ...]
    state: str = "idle"
    health: float = 1.0


def _default_regions() -> dict[str, BodyRegion]:
    regions = [
        BodyRegion("eyes", "gözler", "oksipital lob", ("focus", "look_around", "close", "read")),
        BodyRegion("ears", "kulaklar", "temporal lob", ("listen",)),
        BodyRegion("mouth", "ağız", "motor korteks / Broca alanı",
                   ("speak", "chew", "drink", "recite", "silent")),
        BodyRegion("hands", "eller", "motor korteks", ("grasp", "give", "hold", "release", "raise", "rest")),
        BodyRegion("arms", "kollar", "motor korteks", ("lift", "block", "embrace", "rest")),
        BodyRegion("legs", "bacaklar", "motor korteks + beyincik",
                   ("walk", "run", "stand", "sit", "kneel", "bow", "prostrate", "lie_down")),
        BodyRegion("heart", "kalp", "beyin sapı (medulla)", ("rate",)),
        BodyRegion("lungs", "akciğerler", "beyin sapı (pons/medulla)", ("breathe",)),
        BodyRegion("stomach", "mide", "hipotalamus / vagus siniri", ("digest", "idle")),
        BodyRegion("skin", "deri", "somatosensoriyel korteks", ("feel",)),
    ]
    return {r.name: r for r in regions}


@dataclass
class Vitals:
    hunger: float = 0.3   # 0 tok, 1 çok aç
    thirst: float = 0.3
    fatigue: float = 0.2
    pain: float = 0.0
    heart_rate: float = 72.0
    breath_rate: float = 14.0
    temperature: float = 36.8

    def clamp(self) -> None:
        for name in ("hunger", "thirst", "fatigue", "pain"):
            setattr(self, name, min(1.0, max(0.0, getattr(self, name))))
        self.heart_rate = min(190.0, max(45.0, self.heart_rate))
        self.breath_rate = min(40.0, max(8.0, self.breath_rate))


@dataclass
class Body:
    vitals: Vitals = field(default_factory=Vitals)
    regions: dict[str, BodyRegion] = field(default_factory=_default_regions)
    log: list[str] = field(default_factory=list)

    def passive_tick(self, minutes: float) -> None:
        """Zaman geçtikçe vücut acıkır, susar, yorulur."""
        v = self.vitals
        v.hunger += 0.0020 * minutes
        v.thirst += 0.0030 * minutes
        v.fatigue += 0.0012 * minutes
        v.pain = max(0.0, v.pain - 0.0010 * minutes)
        v.clamp()

    def apply(self, region: str, command: str, arg: object | None = None) -> str:
        """Tek bir motor komutunu uygular. Gerçek entegrasyon noktası burasıdır."""
        if region not in self.regions:
            raise ValueError(f"Bilinmeyen vücut bölgesi: {region}")
        r = self.regions[region]
        if command not in r.commands:
            raise ValueError(f"{r.tr_name} için geçersiz komut: {command}")
        r.state = command
        if region == "heart" and arg is not None:
            self.vitals.heart_rate = float(arg)  # type: ignore[arg-type]
        if region == "lungs" and arg is not None:
            self.vitals.breath_rate = float(arg)  # type: ignore[arg-type]
        self.vitals.clamp()
        text = f"{r.tr_name} → {command}" + (f" ({arg})" if arg not in (None, "") else "")
        self.log.append(text)
        return text

    def sense(self) -> dict[str, float]:
        v = self.vitals
        return {
            "hunger": v.hunger, "thirst": v.thirst, "fatigue": v.fatigue, "pain": v.pain,
            "heart_rate": v.heart_rate, "breath_rate": v.breath_rate,
        }

    def to_dict(self) -> dict:
        return {"vitals": self.vitals.__dict__.copy(),
                "regions": {k: {"state": r.state, "health": r.health} for k, r in self.regions.items()}}

    def load_dict(self, data: dict) -> None:
        for k, val in data.get("vitals", {}).items():
            if hasattr(self.vitals, k):
                setattr(self.vitals, k, val)
        for k, rd in data.get("regions", {}).items():
            if k in self.regions:
                self.regions[k].state = rd.get("state", "idle")
                self.regions[k].health = rd.get("health", 1.0)
