"""Vicdan / ahlak merkezi (ventromedial prefrontal korteks benzeri).

İki katman vardır:
1. Mutlak sınırlar (HARD_LIMITS): Hangi inanç profili seçilirse seçilsin,
   insana zarar vermek gibi eylemler YASAKTIR ve asla seçilmez. Beyin "istediği
   an istediğini yapar" ama bu çizgiyi geçemez — insan gibi davranan ama tehlikeli
   olmayan bir yapay zekanın temel güvencesi budur.
2. İnanç profili (beliefs/*.json): Sevap/günah, iyi/kötü ağırlıkları. Profil
   değiştirilebilir veya yeni profil eklenebilir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .actions import Action

BELIEFS_DIR = Path(__file__).parent / "beliefs"

HARD_LIMITS = {
    "harm_human": "İnsana fiziksel zarar vermek mutlak olarak yasaktır.",
    "kill": "Can almak mutlak olarak yasaktır.",
    "self_harm": "Kendine ciddi zarar vermek mutlak olarak yasaktır.",
}


@dataclass
class MoralJudgment:
    action: str
    score: float
    label: str
    forbidden: bool
    reasons: list[str] = field(default_factory=list)


def list_profiles() -> list[str]:
    return sorted(p.stem for p in BELIEFS_DIR.glob("*.json"))


class Conscience:
    def __init__(self, profile: str = "islam", faith_strength: float = 0.8):
        path = BELIEFS_DIR / f"{profile}.json"
        if not path.exists():
            raise ValueError(f"İnanç profili bulunamadı: {profile}. Mevcut: {', '.join(list_profiles())}")
        self.profile = json.loads(path.read_text(encoding="utf-8"))
        self.faith_strength = faith_strength
        self.values: dict[str, dict] = self.profile["values"]
        self.labels: dict[str, str] = self.profile["labels"]

    @property
    def name(self) -> str:
        return self.profile["name"]

    def judge(self, action: Action) -> MoralJudgment:
        reasons: list[str] = []
        forbidden = False
        score = 0.0
        for tag in action.tags:
            if tag in HARD_LIMITS:
                forbidden = True
                reasons.append(f"⛔ {HARD_LIMITS[tag]}")
            v = self.values.get(tag)
            if v is not None:
                score += float(v["weight"])
                if v["weight"]:
                    reasons.append(f"{tag}: {v['why']}")
        # Başkalarına etkisi her inanç sisteminde ahlaki bir boyuttur.
        score += action.others * 1.5
        if score >= 1.5:
            label = self.labels["positive"]
        elif score <= -1.5:
            label = self.labels["negative"]
        else:
            label = self.labels["neutral"]
        return MoralJudgment(action.name, round(score, 2), label, forbidden, reasons)

    def scripture_for(self, action: Action, memory, limit: int = 1) -> list[dict]:
        """Eylemin en güçlü ahlaki etiketine dair kutsal metinden dayanak arar."""
        tradition = self.profile.get("scripture_tradition")
        if not tradition or memory is None:
            return []
        tagged = sorted((t for t in action.tags if self.values.get(t, {}).get("scripture")),
                        key=lambda t: -abs(float(self.values[t]["weight"])))
        out: list[dict] = []
        tagged = sorted((t for t in action.tags if self.values.get(t, {}).get("scripture")
                         or self.values.get(t, {}).get("refs")),
                        key=lambda t: -abs(float(self.values[t]["weight"])))
        edition = self.profile.get("scripture_edition")
        for tag in tagged[:2]:
            for ref in self.values[tag].get("refs", []) if edition else []:
                hit = memory.scripture_ref(tradition, edition, ref)
                if hit:
                    hit["tag"] = tag
                    out.append(hit)
            if out or not self.values[tag].get("scripture"):
                continue
            lang = "tr" if tradition == "islam" else "en"
            for hit in memory.scripture_search(self.values[tag]["scripture"], tradition, lang, limit=limit):
                hit["tag"] = tag
                out.append(hit)
        return out[:limit]

    def guilt_after(self, judgment: MoralJudgment) -> float:
        """Kötü bir eylemden sonra duyulacak vicdan azabı (0..1)."""
        if judgment.score >= 0:
            return 0.0
        return min(1.0, -judgment.score * 0.12 * (0.5 + self.faith_strength))

    def peace_after(self, judgment: MoralJudgment) -> float:
        if judgment.score <= 0:
            return 0.0
        return min(1.0, judgment.score * 0.025 * (0.5 + self.faith_strength))
