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

    def converse(self, situation: str, decision: str, notes: list[str], profile: str) -> str | None:
        system = ("Sen insan gibi düşünen bir yapay beynin sesisin. Kullanıcıyla sohbet eden bir insan gibi, "
                  "birinci tekil şahısla, sıcak ve doğal Türkçe konuş. Beyin kararını zaten verdi; kararı ve "
                  "gerekçeyi DEĞİŞTİRME, sadece doğal bir dille 2-4 cümlede anlat. Ayet veya kaynak verilmişse "
                  f"kısaca an. Değer sistemi: {profile}. Liste, başlık veya emoji kullanma.")
        prompt = (f"Durum: {situation}\nBeynin kararı ve gerekçesi: {decision}\n"
                  + ("Ek notlar:\n" + "\n".join(f"- {n}" for n in notes) if notes else ""))
        return self._ask(system, prompt, 1200)

    def speak(self, monologue: str) -> str | None:
        system = ("Aşağıdaki iç sesi, bu beyni taşıyan insanın ağzından 1-3 cümlelik doğal Türkçe konuşmaya "
                  "veya düşünceye çevir. Abartma, kararı değiştirme.")
        return self._ask(system, monologue, 800)


class OllamaCortex(LanguageCortex):
    """Ücretsiz, bilgisayarda yerel çalışan dil modeli (https://ollama.com).

    Kurulum: Ollama'yı indir, sonra bir kez `ollama pull qwen2.5:3b` çalıştır.
    Model AI_BRAIN_OLLAMA_MODEL ortam değişkeniyle değiştirilebilir.
    """

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or os.environ.get("AI_BRAIN_OLLAMA_MODEL", "qwen2.5:3b")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.error = None
        self.client = self if self._reachable() else None
        if self.client is None:
            self.error = f"Ollama'ya ulaşılamadı ({self.host}). Ollama açık mı?"

    def _reachable(self) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def _ask(self, system: str, prompt: str, max_tokens: int = 4000) -> str | None:
        import json
        import urllib.request
        if not self.client:
            return None
        body = json.dumps({"model": self.model, "stream": False,
                           "options": {"num_predict": max_tokens},
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": prompt}]}).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            self.error = (f"Ollama hatası: {e}. Model indirildi mi? "
                          f"(ollama pull {self.model})")
            return None
        return (data.get("message", {}).get("content") or "").strip() or None


def make_language(prefer: str = "auto") -> LanguageCortex | None:
    """auto: önce ücretsiz yerel Ollama, yoksa Anthropic (kimlik bilgisi varsa)."""
    if prefer in ("auto", "ollama"):
        o = OllamaCortex()
        if o.available or prefer == "ollama":
            return o
    if prefer in ("auto", "claude"):
        has_creds = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if prefer == "claude" or has_creds:
            return LanguageCortex()
    return None
