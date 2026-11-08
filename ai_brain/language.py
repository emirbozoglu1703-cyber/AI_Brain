"""Dil korteksi (Broca + Wernicke alanları): isteğe bağlı büyük dil modeli bağlantısı.

Kural tabanlı beyin her zaman tek başına çalışır. Anthropic API kimlik bilgisi
varsa (ANTHROPIC_API_KEY veya `ant auth login`) bu modül:
  • soruları hafızadaki bilgilere dayanarak doğal dille cevaplar (RAG),
  • "bunu yaparsam ne olur?" sorusunu zengin, çok adımlı bir senaryo olarak düşünür,
  • beynin iç sesini doğal Türkçe konuşmaya çevirir.

Karar yetkisi HER ZAMAN beyindedir: dil modeli yalnızca düşünür ve konuşur;
mutlak yasaklar (conscience.HARD_LIMITS) onun önerileriyle aşılamaz.
"""

from __future__ import annotations

import os

DEFAULT_MODEL = os.environ.get("AI_BRAIN_MODEL", "claude-opus-5-5")


class LanguageCortex:
    def __init__(self, model: str = DEFAULT_MODEL, effort: str = "low"):
        self.model = model
        self.effort = effort
        self.error: str | None = None
        try:
            import anthropic
        except ImportError:
            self.client = None
            self.error = "anthropic paketi kurulu değil (pip install anthropic)"
            return
        self._anthropic = anthropic
        try:
            self.client = anthropic.Anthropic()
        except Exception as e:  # kimlik bilgisi yoksa istemci oluşturulamayabilir
            self.client = None
            self.error = f"Anthropic istemcisi oluşturulamadı: {e}"

    @property
    def available(self) -> bool:
        return self.client is not None

    def _ask(self, system: str, prompt: str, max_tokens: int = 4000) -> str | None:
        if not self.client:
            return None
        a = self._anthropic
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                # Güvenlik sınıflandırıcısı reddederse sunucu tarafında önerilen modele geçer
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (a.AuthenticationError, a.PermissionDeniedError) as e:
            self.client = None  # kimlik bilgisi geçersiz → bu oturumda tekrar deneme
            self.error = f"Kimlik doğrulama hatası: {e}"
            return None
        except a.RateLimitError as e:
            self.error = f"Hız sınırı: {e}"
            return None
        except a.APIStatusError as e:
            self.error = f"API hatası ({e.status_code}): {e}"
            return None
        except a.APIConnectionError as e:
            self.error = f"Bağlantı hatası: {e}"
            return None
        except (TypeError, a.AnthropicError) as e:  # kimlik bilgisi hiç yok vb.
            self.client = None
            self.error = ("Anthropic kimlik bilgisi bulunamadı (ANTHROPIC_API_KEY veya `ant auth login`). "
                          f"Ayrıntı: {e}")
            return None
        if resp.stop_reason == "refusal":
            self.error = "Model bu isteği yanıtlamayı reddetti."
            return None
        return "".join(b.text for b in resp.content if b.type == "text").strip() or None

    # ------------------------------------------------------------------
    def answer(self, question: str, facts: list[dict], profile: str) -> str | None:
        ctx = "\n\n".join(f"[{i + 1}] {f['title']} ({f.get('url', '')}):\n{f['snippet']}"
                          for i, f in enumerate(facts))
        system = ("Sen bir yapay beynin dil merkezisin. Türkçe, sade ve doğru cevap ver. Önce verilen hafıza "
                  "kayıtlarını kullan ve [numara] ile kaynak göster; kayıtlarda olmayan bir şeyi söylüyorsan "
                  f"bunu açıkça belirt. Beynin değer sistemi: {profile}.")
        return self._ask(system, f"Hafıza kayıtları:\n{ctx or '(yok)'}\n\nSoru: {question}", 3000)

    def imagine(self, situation: str, action: str, rule_based: str, knowledge: list[str], profile: str) -> str | None:
        system = ("Sen bir yapay beynin prefrontal korteksisin: bir eylemin sonuçlarını hayal edersin. "
                  "Kısa vadeli, uzun vadeli, kendine, başkalarına ve toplumsal sonuçları; duygusal ve ahlaki "
                  f"boyutu ({profile}) ayrı ayrı düşün. En olası ve en kötü senaryoyu belirt. Türkçe, maddeler "
                  "halinde, en fazla 12 madde yaz. Bir insana zarar vermeyi asla önerme.")
        prompt = (f"Durum: {situation or '(belirtilmedi)'}\nDüşünülen eylem: {action}\n\n"
                  f"Beynin kural tabanlı ön tahmini:\n{rule_based}\n\nHafızadan ilgili bilgiler:\n"
                  + "\n".join(f"- {k}" for k in knowledge[:10]))
        return self._ask(system, prompt, 3000)

    def speak(self, monologue: str) -> str | None:
        system = ("Aşağıdaki iç sesi, bu beyni taşıyan insanın ağzından 1-3 cümlelik doğal Türkçe konuşmaya "
                  "veya düşünceye çevir. Abartma, kararı değiştirme.")
        return self._ask(system, monologue, 800)
