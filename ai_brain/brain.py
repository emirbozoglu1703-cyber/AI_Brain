"""Beyin: tüm bölgeleri bir 'düşünme döngüsü' içinde birleştirir.

Döngü (her adım):
  1. Talamus      → algıyı bağlama çevirir
  2. Amigdala     → duygusal tepki
  3. Hipotalamus  → ihtiyaçlar (açlık, yorgunluk, manevi ihtiyaç ...)
  4. Hipokampus   → benzer anılar ve bilgiler
  5. Prefrontal   → her olası eylem için "bunu yaparsam ne olur?" simülasyonu
  6. Vicdan       → sevap/günah değerlendirmesi, mutlak yasaklar
  7. Bazal gangl. → karar
  8. Motor sistem → vücut bölgelerine komutlar
  9. Öğrenme      → sonuç beklentiyle karşılaştırılır, model güncellenir
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from .actions import Action, available_actions, find_action
from .body import Body
from .conscience import Conscience
from .cortex import BasalGanglia, Imagined, MotorSystem, PrefrontalCortex
from .limbic import DRIVE_TR, EMOTION_TR, Amygdala, Hypothalamus
from .memory import Hippocampus
from .perception import perceive

DEFAULT_PERSONALITY = {"empathy": 0.8, "conscientiousness": 0.8, "impulsivity": 0.2}


@dataclass
class Thought:
    perception: str
    context: set[str]
    drives: dict[str, float]
    emotions: dict[str, float]
    options: list[Imagined]
    chosen: Imagined
    motor_log: list[str]
    reward: float
    speech: str | None = None
    memories: list[dict] = field(default_factory=list)

    def monologue(self, verbose: bool = True) -> str:
        top_drives = sorted(self.drives.items(), key=lambda kv: -kv[1])[:3]
        lines = []
        if self.perception:
            lines.append(f"👁  Algı: {self.perception}")
        lines.append("🧠 İhtiyaçlarım: " + ", ".join(f"{DRIVE_TR[d]} {v:.2f}" for d, v in top_drives))
        dom = sorted(self.emotions.items(), key=lambda kv: -kv[1])[:3]
        lines.append("❤️  Duygularım: " + ", ".join(f"{EMOTION_TR[e]} {v:.2f}" for e, v in dom))
        if verbose:
            lines.append("💭 Düşünüyorum, ne olur?")
            for o in sorted(self.options, key=lambda o: -o.utility)[:4]:
                lines.append(o.narrative())
                lines.append(f"     ⇒ değer: {o.utility:+.2f}")
        lines.append(f"✅ Kararım: {self.chosen.action.tr}  [{self.chosen.moral.label}]")
        if self.speech:
            lines.append(f"🗣  \"{self.speech}\"")
        lines.append("🦾 Vücut: " + "; ".join(self.motor_log))
        return "\n".join(lines)


class Brain:
    def __init__(self, profile: str = "islam", db_path: str | Path = ":memory:",
                 state_path: str | Path | None = None, personality: dict | None = None,
                 faith_strength: float = 0.8, seed: int | None = None):
        self.personality = {**DEFAULT_PERSONALITY, **(personality or {})}
        self.body = Body()
        self.amygdala = Amygdala()
        self.hypothalamus = Hypothalamus()
        self.memory = Hippocampus(db_path)
        self.conscience = Conscience(profile, faith_strength)
        self.prefrontal = PrefrontalCortex(self.conscience, self.memory, self.personality)
        self.basal = BasalGanglia(seed=seed)
        self.motor = MotorSystem()
        self.rng = random.Random(seed)
        self.clock_minutes = 0.0
        self.state_path = Path(state_path) if state_path else None
        if self.state_path and self.state_path.exists():
            self.load_state()

    # ------------------------------------------------------------------
    def internal_context(self) -> set[str]:
        ctx = set()
        if self.amygdala.state["guilt"] > 0.2:
            ctx.add("feeling_guilty")
        if self.body.vitals.pain > 0.4:
            ctx.add("in_pain")
        return ctx

    def drives(self, context: set[str]) -> dict[str, float]:
        return self.hypothalamus.drives(self.body.sense(), self.amygdala.state, context)

    def step(self, perception: str | None = None, minutes: float = 15.0) -> Thought:
        # zaman geçer
        self.clock_minutes += minutes
        self.body.passive_tick(minutes)
        self.hypothalamus.tick(minutes, self.conscience.faith_strength)
        self.amygdala.decay()

        context = perceive(perception) | self.internal_context()
        self.amygdala.appraise_context(context)
        discomfort = max(self.body.vitals.hunger, self.body.vitals.thirst, self.body.vitals.fatigue,
                         self.body.vitals.pain)
        if discomfort > 0.7:  # karnı çok aç / çok yorgun bir insan neşeli olmaz
            self.amygdala.feel("joy", -(discomfort - 0.7))
            self.amygdala.feel("sadness", (discomfort - 0.7) * 0.5)
        self.motor.brainstem(self.body, self.amygdala.state["fear"])
        drives = self.drives(context)

        candidates = available_actions(context)
        if "danger" in context:
            # Amigdala "kaç ya da savaş" modu: tehlike anında yalnızca güvenliğe hizmet eden
            # eylemler düşünülür (yangın varken yemek yemek/uyumak gibi saçma seçimler elenir).
            candidates = [a for a in candidates if a.relief.get("safety", 0) > 0] or candidates
        options = [self.prefrontal.imagine(a, drives) for a in candidates]
        # Geçmişte benzer durumda iyi sonuç veren eylemleri hatırla
        for action_name, avg_reward in self.memory.similar_episodes(context):
            for o in options:
                if o.action.name == action_name:
                    o.utility += 0.2 * avg_reward
        chosen = self.basal.select(options)
        chosen.knowledge = self.memory.recall_consequences(chosen.action.tr, limit=2)

        speech, memories = None, []
        if chosen.action.name == "answer_question" and perception:
            memories = self.memory.recall(perception, limit=3)
            speech = (memories[0]["snippet"] if memories
                      else "Bunu henüz bilmiyorum, öğrenmem gerekiyor.")
        else:
            speech = next((str(a) for r, c, a in chosen.action.motor if r == "mouth" and c == "speak"), None)

        motor_log = self.motor.execute(chosen.action, self.body)
        reward = self._consequences(chosen, drives)
        self.memory.remember_episode(perception or "", context, chosen.action.name,
                                     {"label": chosen.moral.label, "score": chosen.moral.score},
                                     reward, chosen.narrative())
        thought = Thought(perception or "", context, drives, dict(self.amygdala.state), options, chosen,
                          motor_log, reward, speech, memories)
        if self.state_path:
            self.save_state()
        return thought

    def _consequences(self, im: Imagined, drives: dict[str, float]) -> float:
        """Eylemin gerçek sonucu (biraz belirsizlikle) — beklentiyle kıyaslanır ve öğrenilir."""
        a = im.action
        actual = {d: v * self.rng.uniform(0.75, 1.15) for d, v in a.relief.items()}
        v = self.body.vitals
        for d, amt in actual.items():
            if d in ("hunger", "thirst", "fatigue", "pain"):
                setattr(v, d, getattr(v, d) - amt)
            elif d in ("social", "curiosity", "spiritual"):
                self.hypothalamus.satisfy(d, amt)
            elif d == "guilt":
                self.amygdala.feel("guilt", -amt)
            elif d == "anger":
                self.amygdala.feel("anger", -amt)
            elif d == "safety":
                self.amygdala.feel("fear", -amt)
        v.clamp()
        guilt = self.conscience.guilt_after(im.moral)
        peace = self.conscience.peace_after(im.moral)
        self.amygdala.feel("guilt", guilt)
        self.amygdala.feel("peace", peace - guilt * 0.5)
        relief_value = sum(drives.get(d, 0) * x for d, x in actual.items())
        self.amygdala.feel("joy", relief_value * 0.15)
        if a.name in ("read", "answer_question"):
            self.amygdala.feel("curiosity", -0.2)
        reward = relief_value + peace - guilt + a.others * self.personality["empathy"] * 0.5
        self.prefrontal.learn(a, actual)
        self.basal.reinforce(a.name, reward)
        return round(reward, 3)

    # ------------------------------------------------------------------
    def whatif(self, text: str) -> str:
        """'Bunu yaparsam ne olur?' — eylem simülasyonu + öğrenilmiş bilgi."""
        action = find_action(text)
        drives = self.drives(self.internal_context() | perceive(text))
        out = []
        if action:
            out.append(self.prefrontal.imagine(action, drives, use_knowledge=False).narrative())
        knowledge = self.memory.recall_consequences(text, limit=5)
        if knowledge:
            out.append("📚 Öğrendiğim bilgilere göre olası sonuçlar:")
            for k in knowledge:
                out.append(f"  • {k['sentence'][:220]}  ({k['source']})")
        if not out:
            out.append("Bu konuda henüz yeterli bilgim yok. `learn` komutu ile öğrenmeme izin ver.")
        return "\n".join(out)

    def ask(self, question: str) -> list[dict]:
        return self.memory.recall(question, limit=5)

    def status(self) -> str:
        v = self.body.vitals
        d = self.drives(self.internal_context())
        lines = [f"🕐 Geçen süre: {self.clock_minutes / 60:.1f} saat | İnanç profili: {self.conscience.name}",
                 f"🫀 Nabız {v.heart_rate:.0f} | Solunum {v.breath_rate:.0f} | Ateş {v.temperature:.1f}",
                 "🧠 İhtiyaçlar: " + ", ".join(f"{DRIVE_TR[k]} {x:.2f}" for k, x in d.items() if x > 0.05),
                 "❤️  Duygular: " + ", ".join(f"{EMOTION_TR[k]} {x:.2f}" for k, x in self.amygdala.state.items()),
                 f"📚 Hafıza: {self.memory.stats()}"]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def save_state(self) -> None:
        assert self.state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"clock": self.clock_minutes, "body": self.body.to_dict(), "emotions": self.amygdala.state,
                "hypothalamus": self.hypothalamus.__dict__, "learned": self.prefrontal.learned,
                "habit": self.basal.habit, "recent": self.basal.recent}
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def load_state(self) -> None:
        assert self.state_path
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.clock_minutes = data.get("clock", 0.0)
        self.body.load_dict(data.get("body", {}))
        self.amygdala.state.update(data.get("emotions", {}))
        self.hypothalamus.__dict__.update(data.get("hypothalamus", {}))
        self.prefrontal.learned = data.get("learned", {})
        self.basal.habit = data.get("habit", {})
        self.basal.recent = data.get("recent", [])


__all__ = ["Brain", "Thought", "Action"]
