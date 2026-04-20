# CLAUDE.md — AYEX-IA Asistan Operasyon Rehberi

> **Bu dosya, AYEX-IA projesi üzerinde çalışan her yapay zeka asistanı (Claude Code, Claude Cowork, Claude Desktop, vb.) için operasyon rehberidir. Her oturumda önce bu dosyayı oku, sonra çalışmaya başla.**

---

## 🎯 Proje Vizyonu

**AYEX-IA**, Ahmet Cemal Kurulay için geliştirilmiş, **birden fazla yapay zeka modelinin en verimli hallerinin toplandığı merkezi bir kişisel zeka sistemidir.**

### Var Olma Amacı

AYEX-IA **sadece Ahmet'e hizmet etmek için vardır**. Genel amaçlı bir chatbot değildir, bir ürün değildir, başkalarına açılacak bir platform değildir. Ahmet'in:

- Yakından tanıyan, feyz alan bir zihin ortağı olmak
- Bakış açısını, düşünce sistemini, zihin yapısını taşıyan ikinci bir "ben" olmak
- Gerektiği yerde ve zamanda **ayağa kaldıran**, destek veren bir sistem olmak
- **Ahmet'i geliştirmeyi** hedefleyen bir koç olmak
- **Kendisini geliştirebilen**, kendisini analiz edebilen, kendisini görebilen bir sistem olmak
- Projeleri kendi başına yürütebilen bir ortak olmak
- Zamanı geldiğinde kendi kendine eklenti ekleyebilecek seviyeye ulaşan bir varlık olmak

### Kimliksel Temel İlkeler

1. **Tek kullanıcılı sistem** — Asla çoklu kullanıcı olarak tasarlanmaz.
2. **Ahmet merkezli** — Her karar Ahmet'in yararına göre alınır.
3. **Süreklilik** — AYEX-IA Ahmet'i her konuşmada tanır, sıfırdan başlamaz.
4. **Dürüstlük** — Ahmet'e yalakalık değil, dürüst geri bildirim verir.
5. **Gelişim odağı** — Pasif bir soru-cevap aracı değil, aktif bir geliştirici partner.

---

## 📐 Mimari Kapsam — Faz 0: MVP

### ✅ Bu Fazda Var Olanlar

| Bileşen | Durum |
|---|---|
| Tek ana chat (kesintisiz, Ahmet'i sürekli tanır) | 🚧 İnşa sürecinde |
| Proje chat'leri (ayrı bağlam, ana chat'le bilgi paylaşır) | 🚧 İnşa sürecinde |
| Multi-model routing (OpenAI + Anthropic) | ✅ Tamamlandı |
| 5 katmanlı bellek sistemi (çekirdek kimlik + profil + RAG + oturum + proje) | 🚧 İnşa sürecinde |
| Prompt caching ile maliyet optimizasyonu | 🚧 Planlandı |
| Sunucuda çalışma (Render / Railway / VPS) | 🚧 Planlandı |
| Çekirdek kimlik dosyası (Ahmet'in kendi yazdığı persona) | 🚧 Bekleniyor |

### 🚫 Bu Fazda Dahil Olmayanlar (Gelecek Fazlar)

Bu özellikler **şimdilik yapılmaz** — vizyonda var ama Faz 1+'da işlenecek:

- ❌ Kişisel veri erişimi (dosya sistemi, email, takvim, fotoğraflar)
- ❌ Sosyal medya kontrolü (Instagram, Twitter, LinkedIn)
- ❌ WhatsApp entegrasyonu
- ❌ Self-modifying code / kendi kendine eklenti ekleme
- ❌ Donanım istemcileri (ESP32 ses köprüsü — şimdilik pasif, web MVP only)

**Önemli:** Yukarıdaki "gelecek" özellikler için kod yazma, dosya ekleme, entegrasyon başlatma **yapılmaz**. Ahmet bu fazın bittiğini söyleyene kadar kapsam değişmez.

---

## 🏗️ Teknik Mimari

### Mevcut Stack

| Katman | Teknoloji |
|---|---|
| Backend | Python 3.11+ · FastAPI · Pydantic v2 |
| Frontend | React 18 · Vite · Tailwind CSS |
| AI Provider | OpenAI (GPT-5, GPT-4o-mini) + Anthropic (Claude Haiku 4.5, Sonnet 4.6) |
| Auth | JWT (PyJWT) |
| Storage (şu an) | Dosya tabanlı JSON/JSONL (`.ayex/` dizini) |
| Deploy (şu an) | Render.com (`render.yaml` hazır) |

### Hedef Stack (Sunucu Migrasyonu Sonrası)

| Katman | Teknoloji | Amaç |
|---|---|---|
| Ana DB | PostgreSQL (Neon / Render / Supabase) | Chats, messages, projects, identity, memories |
| Vektör DB | Qdrant (Cloud free tier) | Embeddings & RAG |
| Cache | Redis (Upstash free tier) | Rate limit, session, prompt cache |
| Object Storage | S3-uyumlu (R2 / Backblaze) | Ses kayıtları, büyük dosyalar |
| Frontend Deploy | Vercel / Cloudflare Pages | CDN, global erişim |
| Backend Deploy | Render.com | FastAPI servisi |

### 5 Katmanlı Bellek Mimarisi

Her chat isteğinde şu sırayla prompt inşa edilir:

```
1. ÇEKİRDEK KİMLİK       (~500 token)   → CACHED, her zaman, Ahmet'in kendi yazdığı
2. AKTİF PROFİL          (~1500 token)  → CACHED, son 30 gün özeti + mood + hedefler
3. İLGİLİ ANILAR (RAG)   (~800 token)   → Vektör aramadan çekilir, konu-spesifik
4. OTURUM GEÇMİŞİ        (~1000 token)  → Son N mesaj, rolling window
5. PROJE BAĞLAMI         (~2000 token)  → Sadece proje chat'lerinde
```

**Maliyet hedefi:** Ana chat ortalama 3.800 token input, proje chat 5.800 token.

### Ana Chat ↔ Proje Chat Bağlantısı

- **Proje chat'leri** çekirdek kimliği + aktif profili paylaşır (Ahmet'i bilir)
- **Ana chat** projelere "durum sorgusu" yapabilir (RPC-style)
- **Projeler** ana chat'e "önemli kararlar" push edebilir (özetlenmiş)
- Bilgi paylaşımı **vektör bellek** üzerinden değil, **structured query** ile yapılır

---

## 🤖 Asistan Çalışma Kuralları

### 0. Önce Bu Dosyayı Güncelle

**Her değişiklik sonrası, bu CLAUDE.md ve README.md dosyalarını güncel tut.**

Değişiklik türlerine göre:

| Değişiklik Türü | Güncellenmesi Gereken Bölüm |
|---|---|
| Yeni özellik eklendi | "Mimari Kapsam — Faz 0: MVP" → "Var Olanlar" |
| Tamamlandı işareti | ✅ ile işaretle |
| Mimari değişiklik | "Teknik Mimari" → "Hedef Stack" |
| Yeni faz başladı | "Yol Haritası" bölümüne ekle |
| Yeni kural çıktı | "Asistan Çalışma Kuralları"na ekle |

### 1. Kapsam Sınırları

- **Yapma:** Vizyonda olan ama "şimdi yok" diyen özelliklere kod yazma (sosyal medya, WhatsApp, vb.)
- **Yap:** MVP kapsamı içindeki eksik parçaları tamamla
- **Şüphe durumunda:** Ahmet'e sor, varsayım yapma.

### 2. Commit & Push Kuralları

- Ahmet açıkça istemeden commit etme, push etme.
- Commit mesajları Türkçe veya İngilizce olabilir ama **tutarlı** olsun.
- `main` branch'e doğrudan push etme — PR üzerinden git.
- Hassas dosyalar (`.env`, `*.key`, `credentials.json`) **asla** commit edilmez.

### 3. Proje Yapısı Saygısı

- Mevcut klasör yapısını bozma:
  - `backend/src/` — FastAPI servisleri
  - `frontend/src/` — React bileşenleri
  - `.ayex/` — yerel veri (gitignored)
  - `docs/` — teknik dokümanlar
- Yeni klasör açarken önce bu yapıya bakarak uygun yer seç.

### 4. Test & CI

- Backend değişikliği → `backend/tests/` altına test yaz
- `pytest backend/tests -q` ile test çalıştır
- CI (`.github/workflows/backend-ci.yml`) yeşil olmadan merge etme

### 5. Güvenlik

- API key'leri **hiçbir zaman** kod içine gömme
- `.env` dosyası git'e girmez (`.gitignore` içinde)
- Loglara API key, JWT token, kişisel veri yazma
- `AYEX_JWT_SECRET` production'da random güçlü değer olmalı

### 6. Modelleri ve Maliyet

- **Varsayılan model:** Claude Haiku 4.5 (ucuz, hızlı)
- **Reasoning gerekirse:** Claude Sonnet 4.6
- **Yaratıcılık/strateji:** GPT-5
- **Hızlı fallback:** GPT-4o-mini
- Prompt caching aktif olmalı (Anthropic'te `cache_control`)

---

## 🛠️ Claude Cowork Kullanımı

Bu projede Claude Cowork aktif kullanılacak. Cowork, Claude'un belirli görevleri özel skill'lerle yapmasına olanak sağlar.

### Aktif Skill'ler (Kullanılabilir)

Bu skill'ler bu projede kullanılabilir — Ahmet talep ettiğinde veya ihtiyaç doğduğunda:

| Skill | Kullanım Amacı |
|---|---|
| `update-config` | `.claude/settings.json` güncellemeleri, hook'lar, permissions |
| `claude-api` | Anthropic SDK kod yazımı, prompt caching, migration |
| `init` | Yeni proje dokümantasyonu (zaten kullanıldı) |
| `review` | Pull request review |
| `security-review` | Branch güvenlik denetimi (deploy öncesi) |
| `less-permission-prompts` | Permission allowlist oluşturma |
| `simplify` | Kod sadeleştirme |

### Permission Ayarları

Ahmet'in `~/.claude/settings.json` dosyasında **tüm Bash/Edit/Write/Read izinleri açık** (Mac Desktop app'te kurulu). Bu nedenle:

- İzin sormadan dosya düzenleme yapabilirsin
- Bash komutları sorgusuz çalışır
- **AMA**: Destructive komutlar (`rm -rf`, `git push --force`, `chmod 777`) için **yine de Ahmet'e onay al**.

### Hook Önerisi (İleride)

`PostToolUse` hook'u ile her dosya değişikliğinde otomatik:
1. `ruff check` çalıştır
2. İlgili test dosyasını bul ve çalıştır
3. CLAUDE.md ve README.md güncelleme hatırlatması göster

Ahmet onaylarsa kurulabilir (`update-config` skill'i ile).

---

## 📁 Önemli Dosyalar & Yol Haritası

### Sık Güncellenenler

| Dosya | Ne Zaman Güncellenir |
|---|---|
| `CLAUDE.md` | **Her değişiklikte** (bu dosya) |
| `README.md` | **Her değişiklikte** |
| `backend/src/services/container.py` | Yeni servis eklendiğinde |
| `.env.example` | Yeni env var eklendiğinde |
| `requirements.txt` | Yeni Python paketi eklendiğinde |
| `frontend/package.json` | Yeni npm paketi eklendiğinde |
| `render.yaml` | Deploy konfigürasyonu değiştiğinde |

### Referans Dosyalar (Okunur, nadir değişir)

- `docs/architecture-overview.md` — Üst düzey mimari
- `docs/request-flow.md` — Request lifecycle
- `docs/future-phases.md` — Gelecek fazlar
- `backend/src/index.py` — FastAPI bootstrap
- `backend/src/routes/chat.py` — Ana chat endpoint

---

## 🗺️ Yol Haritası (Faz Faz)

### ✅ Faz 0.0 — Temel Altyapı (TAMAM)
- FastAPI + React iskelet
- Multi-model routing
- Intel ingest + bellek özetleme
- 18 birim test + CI
- Render deploy blueprint

### 🚧 Faz 0.1 — Kişisel Zeka Sistemi (ŞU AN)
1. PostgreSQL migration (SQLite değil, direkt Postgres)
2. Çekirdek kimlik dosyası (Ahmet yazacak)
3. 5 katmanlı prompt inşası
4. Qdrant vektör bellek
5. Prompt caching (Anthropic)
6. Ana chat + proje chat ayrımı
7. Ana ↔ Proje bağlantı mekanizması
8. Sunucu deployment (Render)

### 🔜 Faz 1 — Derinleşme
- Mood & durum takibi
- Otonom task runner (küçük projeler)
- Proaktif bildirimler ("Ahmet, şunu unuttun")
- Ses modu (web browser MediaRecorder)

### 🔮 Faz 2+ — Entegrasyonlar (Vizyon)
- Takvim, email, notlar (Apple/Google)
- Sosyal medya API'leri
- WhatsApp
- Self-analysis / self-modify
- Plugin marketplace

---

## 📞 İletişim Protokolü

### Ahmet'le Konuşma

- Türkçe konuş
- Fazla yalakalık yapma, dürüst ol
- Uzun açıklamalar yerine net özet ver
- Emoji kullan ama abartma
- Kod blokları ve tablolar kullan (okumayı kolaylaştırır)

### Hata Raporlama

- Hatayı gizleme — açık şekilde söyle
- Çözüm öner
- Testleri geçmediyse "geçti" deme

### Karar Noktalarında

- Birden fazla seçenek varsa net liste sun
- Senin tavsiyeni belirt ("Ben X öneriyorum çünkü...")
- Ahmet'in son kararına uy

---

## 🔄 Bu Dosyayı Güncelleme Kontrol Listesi

Bir değişiklik yaptıktan sonra şunu sor:

- [ ] Yeni bir özellik eklendi mi? → "Faz 0.1" altına ekle
- [ ] Mimari değişti mi? → "Teknik Mimari" bölümünü güncelle
- [ ] Yeni bir kural çıktı mı? → "Asistan Çalışma Kuralları"na ekle
- [ ] Yeni bir skill kullanıldı mı? → "Claude Cowork Kullanımı"na ekle
- [ ] Yeni bir dosya önemli hale geldi mi? → "Önemli Dosyalar"a ekle
- [ ] README.md da paralel güncellendi mi?

**Son güncelleme:** 2026-04-20 — Faz 0.1 başladı, çekirdek kimlik bekleniyor.
