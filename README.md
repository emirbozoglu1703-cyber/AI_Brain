# 🧠 AI Brain — Yapay Zekâ Destekli İnsan Beyni

İnsan beyninin bölgelerinden esinlenmiş, **kendi kararını veren**, **doğruyu/yanlışı ve
sevabı/günahı tartan**, her eylemden önce **"bunu yaparsam ne olur?"** diye düşünen ve
**vücut bölgelerini tek tek kontrol eden** bir bilişsel mimari. Saf Python, ek bağımlılık yok.

> ⚠️ Gerçekçi not: Bu bir *bilişsel mimari prototipidir* — gerçek bir insan bilinci değildir.
> Dünyadaki bütün veriyi toplamak da fiziksel olarak mümkün değil; bunun yerine beyin açık
> kaynaklardan (şimdilik Vikipedi TR + EN) **sürekli ve kaldığı yerden devam ederek** öğrenir.

## Beyin bölgeleri

| Bölge | Dosya | Görevi |
|---|---|---|
| Talamus | `perception.py` | Algıyı (metin; ileride kamera/mikrofon) bağlama çevirir |
| Amigdala | `limbic.py` | Duygular: sevinç, korku, öfke, üzüntü, vicdan azabı, huzur, merak |
| Hipotalamus | `limbic.py` | İhtiyaçlar: açlık, susuzluk, yorgunluk, yalnızlık, manevi ihtiyaç, nefsani arzu… |
| Hipokampus | `memory.py` | Uzun süreli hafıza (SQLite + tam metin arama): bilgiler, neden-sonuç cümleleri, anılar |
| Prefrontal korteks | `cortex.py` | Her olası eylemi hayal eder: ihtiyaç, duygu, risk, başkalarına etki, ahlak |
| Vicdan (vmPFC) | `conscience.py` + `beliefs/*.json` | İnanç profiline göre sevap/günah; **mutlak yasaklar** |
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

## Kullanım
```bash
python -m ai_brain live --steps 10                     # beyin kendi hayatını yaşasın
python -m ai_brain step "Yerde içi para dolu bir cüzdan buldum."
python -m ai_brain chat                                # sen algı yaz, o karar versin
python -m ai_brain whatif "cüzdanı saklarsam ne olur"
python -m ai_brain learn --minutes 40                  # internetten öğren
python -m ai_brain ask "amigdala nedir"
python -m ai_brain status
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

## Yol haritası (entegrasyon)
1. **Algı**: `perception.py` → kamera (nesne tanıma), mikrofon (konuşma tanıma) bayrakları üretsin.
2. **Vücut**: `Body.apply` → robot/simülasyon (ör. ROS, MuJoCo, Unity) aktüatörlerine bağlansın.
3. **Dil**: `answer_question` ve "ne olur?" muhakemesi bir büyük dil modeline bağlanarak serbest
   konuşma ve çok daha zengin sonuç tahmini kazanabilir.
4. **Kaynaklar**: `knowledge.Source` sınıfından türeterek Vikikaynak, Project Gutenberg, açık
   makale arşivleri vb. eklenebilir.
