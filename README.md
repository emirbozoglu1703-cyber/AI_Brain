# 🧠 AI Brain — Yapay Zekâ Destekli İnsan Beyni

İnsan beyninin bölgelerinden esinlenmiş, **kendi kararını veren**, **doğruyu/yanlışı ve
sevabı/günahı tartan**, her eylemden önce **"bunu yaparsam ne olur?"** diye düşünen ve
**vücut bölgelerini tek tek kontrol eden** bir bilişsel mimari. Saf Python, ek bağımlılık yok.

> ⚠️ Gerçekçi not: Bu bir *bilişsel mimari prototipidir* — gerçek bir insan bilinci değildir.
> Dünyadaki bütün veriyi toplamak fiziksel olarak mümkün değil; bunun yerine beyin büyük açık
> veri kümelerini (aşağıda) toplu olarak işler ve Vikipedi'den canlı öğrenmeye devam eder.

## Bilgi tabanı (`python -m ai_brain build`)

| Kaynak | Ne işe yarar | Boyut (yaklaşık) |
|---|---|---|
| Türkçe Vikipedi'nin **tamamı** | Genel dünya bilgisi, `ask` soruları, neden-sonuç cümleleri | ~535 bin makale |
| Basit İngilizce Vikipedi'nin tamamı | İngilizce genel bilgi | ~242 bin makale |
| ConceptNet 5.7 (EN+TR) | Sağduyu: "çalmak → neden olur → hapse girmek", "içki → neden olur → muhakeme bozukluğu" | ~473 bin ilişki |
| Kur'an-ı Kerim (Diyanet meali + Sahih International) | Vicdanın dayanak gösterdiği ayetler | 6.236 ayet × 2 |
| 31 klasik (Aristoteles, Platon, Kant, Spinoza, Mill, Konfüçyüs, Kitab-ı Mukaddes, Darwin, W. James...) | Ahlak felsefesi, din, psikoloji | ~19 bin parça |

İndirme ≈1,2 GB, işlenmiş hafıza birkaç GB'dır; tam kurulum sıradan bir bilgisayarda yaklaşık
15–30 dakika sürer ve kesilirse kaldığı yerden devam eder. Lisanslar: `NOTICE.md`.

**Bu bilgiler kararlara nasıl yansır?**
- *Sağduyu içgüdüsü:* ConceptNet'te bir eylem "kötü/yasa dışı/hapse götürür" diye geçiyorsa beyin ondan
  kaçınır; "mutluluk/sağlık getirir" diye geçiyorsa yönelir. Bu, kurallara ek olarak **veriden öğrenilmiş** bir
  iyi-kötü sezgisidir.
- *Dayanak:* Vicdan, kararın ahlaki gerekçesini Kur'an'dan (veya Hristiyanlık profilinde KJV'den) ayetle gösterir.
- *Ne olur?* `whatif` hem ConceptNet sonuçlarını hem de Vikipedi/kitaplardan çıkarılmış neden-sonuç cümlelerini listeler.

## Beyin bölgeleri

| Bölge | Dosya | Görevi |
|---|---|---|
| Talamus | `perception.py` | Algıyı (metin; ileride kamera/mikrofon) bağlama çevirir |
| Amigdala | `limbic.py` | Duygular: sevinç, korku, öfke, üzüntü, vicdan azabı, huzur, merak |
| Hipotalamus | `limbic.py` | İhtiyaçlar: açlık, susuzluk, yorgunluk, yalnızlık, manevi ihtiyaç, nefsani arzu… |
| Hipokampus | `memory.py` | Uzun süreli hafıza (SQLite + tam metin arama): bilgiler, neden-sonuç cümleleri, anılar |
| Prefrontal korteks | `cortex.py` | Her olası eylemi hayal eder: ihtiyaç, duygu, risk, başkalarına etki, ahlak |
| Vicdan (vmPFC) | `conscience.py` + `beliefs/*.json` | İnanç profiline göre sevap/günah, kutsal metinden dayanak; **mutlak yasaklar** |
| Dil korteksi (Broca/Wernicke) | `language.py` | İsteğe bağlı: Claude ile doğal dil cevap, derin "ne olur?" düşünmesi |
| Bazal ganglionlar | `cortex.py` | Karar + alışkanlık öğrenme (pekiştirmeli öğrenme) |
| Motor korteks + beyincik + beyin sapı | `cortex.py` | Eylemi vücut komutlarına çevirir, uygulanabilirliği denetler, nabız/solunumu ayarlar |
| Vücut | `body.py` | Göz, kulak, ağız, el, kol, bacak, kalp, akciğer, mide, deri — **entegrasyon noktası** |

### Düşünme döngüsü (her adımda)
```
algı → duygu → ihtiyaçlar → hafıza → "ne olur?" simülasyonu (her eylem için)
     → vicdan (sevap/günah + mutlak yasaklar) → karar → vücut komutları → sonuçtan öğrenme
```

### "Deli gibi görünmemesi" için
- Düşük sıcaklıklı seçim: küçük insani tutarsızlıklar olur, rastgele saçmalık olmaz.
- Aciliyet doğrusal değil: çok susamışsa önce su içer.
- Tehlike anında "kaç ya da savaş" modu: yangın varken yemek yemez, uyumaz, namaza durmaz.
- Her an yapılabilen iyi işler (dua, kitap) ancak ilgili ihtiyaç varken öne çıkar.
- Aynı şeyi gereksiz yere tekrar etmeme filtresi.

### Din ve ahlak
- `beliefs/islam.json` (varsayılan), `christianity.json`, `secular.json`. Yeni bir profil için
  JSON dosyası eklemeniz yeterli. Ağırlıklar basitleştirilmiş modeldir; **fetva/hüküm değildir**.
- Hangi profil seçilirse seçilsin **insana zarar vermek mutlak olarak yasaktır** (`HARD_LIMITS`).
  Testler, kişiliği tamamen dürtüsel ve empatisiz yapılsa bile beynin saldırmadığını doğrular.

## Sohbet
```bash
python -m ai_brain chat            # düşünme arka planda, sadece cevap görünür
python -m ai_brain chat --detay    # arka plandaki düşünceyi de göster
```
Örnek: *"Yerde cüzdan buldum"*, *"Arkadaşlar içki teklif etti"*, *"Yalan söylersem ne olur?"*,
*"Amigdala nedir?"*, *"Atatürk kimdir"*, *"Nasılsın?"*

### Ücretsiz dil modeli (Ollama) — isteğe bağlı
1. https://ollama.com adresinden Ollama'yı kur.
2. Bir kez: `ollama pull qwen2.5:3b` (≈2 GB; güçlü bilgisayarda `qwen2.5:7b` daha iyi konuşur).
3. `python -m ai_brain chat`: Ollama açıksa otomatik kullanılır; cevaplar daha doğal olur.
   Model değiştirmek için: `AI_BRAIN_OLLAMA_MODEL` ortam değişkeni.

## Diğer komutlar
```bash
python -m ai_brain live --steps 10                     # beyin kendi hayatını yaşasın
python -m ai_brain step "Yerde içi para dolu bir cüzdan buldum."
python -m ai_brain chat                                # sen algı yaz, o karar versin
python -m ai_brain whatif "cüzdanı saklarsam ne olur"
python -m ai_brain learn --minutes 40                  # internetten öğren
python -m ai_brain ask "amigdala nedir"
python -m ai_brain status
python -m ai_brain build                               # tüm büyük veri kümeleri (bkz. yukarı)
python -m ai_brain build --sources quran conceptnet    # yalnızca bazıları
python -m ai_brain --llm whatif "işimi bırakırsam ne olur"   # dil korteksi ile derin düşünme
python -m ai_brain --llm ask "amigdala ne işe yarar"
python -m ai_brain --profile secular --faith 0.3 live  # farklı inanç / kişilik
```
Hafıza ve beyin durumu `data/` klasöründe saklanır (git'e eklenmez).

### Her saat 40 dakika öğrenme
`learn` her çalıştırıldığında kaldığı yerden devam eder. Kendi bilgisayarınızda / sunucunuzda:
```cron
0 * * * *  cd /yol/AI_Brain && python3 -m ai_brain learn --minutes 40 >> data/learn.log 2>&1
```

## Testler
```bash
python -m unittest discover -s tests -v
```

## Dil korteksi (isteğe bağlı)
Ücretsiz yol: Ollama (yukarıda). Ücretli alternatif: `pip install anthropic` ve `ANTHROPIC_API_KEY`
(veya `ant auth login`) ile `--llm claude`.
Varsayılan model `claude-opus-5-5` (`AI_BRAIN_MODEL` ortam değişkeniyle değiştirilebilir). Dil modeli
yalnızca **düşünür ve konuşur**; karar ve mutlak yasaklar beyindedir. Kimlik bilgisi yoksa beyin
sorunsuz biçimde kendi başına çalışmaya devam eder.

## Eylemler ve durumlar
49 eylem (yemek, uyku, namaz, oruç, sadaka, yardım, teselli, sözünü tutmak, ders çalışmak, kopya,
içki, dedikodu, çocuğu korumak, kaçmak...) ve 25'ten fazla algılanan durum (cüzdan bulmak, tehlike,
hakaret, sınav, ramazan, üzgün biri, ödünç eşya...). Yeni eylem: `actions.py`'ye bir `Action` ve
`ACTION_CONCEPTS` girdisi; yeni durum: `perception.py`'ye bir kalıp.

## Yol haritası (entegrasyon)
1. **Algı**: `perception.py` → kamera (nesne tanıma), mikrofon (konuşma tanıma) bayrakları üretsin.
2. **Vücut**: `Body.apply` → robot/simülasyon (ör. ROS, MuJoCo, Unity) aktüatörlerine bağlansın.
3. **Dil**: ✅ `language.py` (Claude) hazır; API anahtarı ile etkinleşir.
4. **Kaynaklar**: `knowledge.Source` sınıfından türeterek Vikikaynak, Project Gutenberg, açık
   makale arşivleri vb. eklenebilir.
