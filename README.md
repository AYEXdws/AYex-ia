# AYEX-IA

**Ahmet Cemal Kurulay'a hizmet etmek için var olan kişisel zeka sistemi.**

AYEX-IA, birden fazla yapay zeka modelinin en verimli hallerinin bir araya getirildiği, tek kullanıcılı, merkezi bir kişisel zeka sistemidir. Ahmet'i yakından tanıyan, ondan feyz alan, onun bakış açısını taşıyan ve gerektiği yerde ona destek olan bir zihin ortağı olmayı hedefler.

---

## 🎯 Vizyon

AYEX-IA sıradan bir chatbot değildir. Amaçları:

- **Ahmet'i tanımak** — Her konuşmada sıfırdan başlamadan, Ahmet'in kim olduğunu hatırlayarak konuşur.
- **Ahmet'i geliştirmek** — Pasif bir soru-cevap aracı değil, aktif bir koç ve ortak.
- **Kendini geliştirmek** — Konuşmalardan öğrenir, kendini analiz eder, kendini görür.
- **Projeleri yürütmek** — Ahmet'in yanında değil, onun adına projeler yürütebilen bir sistem.
- **Ayağa kaldırmak** — Gerektiği yerde ve zamanda Ahmet'e destek olur.
- **Zamanla kendini genişletmek** — İleride kendi kendine eklenti ekleyebilecek seviyeye ulaşır.

---

## 📐 Kapsam

### Şu Anki Faz — MVP (Faz 0.1)

```
┌──────────────────────────────────────────────────┐
│  🧠 ANA CHAT (kesintisiz)                        │
│  Ahmet'i her konuşmada tanıyan, sürekli sohbet   │
└──────────────────────────────────────────────────┘
           ↕ bilgi paylaşımı ↕
┌──────────────────────────────────────────────────┐
│  📁 PROJE CHAT'LERİ                              │
│  Her projenin kendi bağlamı, ana chat'le bağlı   │
└──────────────────────────────────────────────────┘
```

**Bu fazın özellikleri:**

- ✅ Çoklu AI model routing (OpenAI GPT-5/4o-mini + Anthropic Claude Haiku 4.5 / Sonnet 4.6)
- 🚧 Tek ana chat (sınırsız, Ahmet'i sürekli tanır)
- 🚧 Proje chat'leri (ayrı bağlam, ana chat'le bilgi alışverişi)
- 🚧 5 katmanlı bellek: çekirdek kimlik + aktif profil + RAG + oturum + proje
- 🚧 Prompt caching ile maliyet optimizasyonu
- 🚧 PostgreSQL + Qdrant ile sunucu tabanlı kalıcı bellek
- 🚧 Her yerden erişim (sunucuda çalışır, tarayıcıdan)

### Sonraki Fazlarda (Vizyon)

Bu özellikler şu anki kapsamda **yok**, ileride yapılacak:

- 🔮 Kişisel veri entegrasyonu (takvim, email, notlar, dosyalar)
- 🔮 Sosyal medya kontrolü (Instagram, Twitter/X, LinkedIn)
- 🔮 WhatsApp entegrasyonu
- 🔮 Self-modifying kod / kendi kendine eklenti yazma
- 🔮 Donanım ses istemcisi (ESP32-S3)

---

## 🧠 Bellek Sistemi (Hedef Mimari)

AYEX-IA her chat isteğinde 5 katmanlı bir bağlam inşa eder:

| Katman | İçerik | Boyut | Strateji |
|---|---|---|---|
| 1. **Çekirdek Kimlik** | Ahmet'in kendi yazdığı persona metni | ~500 token | **Cached** (her zaman) |
| 2. **Aktif Profil** | Son 30 gün özeti, mood, aktif hedefler | ~1500 token | **Cached** (her zaman) |
| 3. **İlgili Anılar** | Vektör aramadan gelen ilgili geçmiş konuşmalar | ~800 token | RAG ile seçilir |
| 4. **Oturum Geçmişi** | Şu anki konuşmanın son N mesajı | ~1000 token | Rolling window |
| 5. **Proje Bağlamı** | Sadece proje chat'lerinde: proje state'i | ~2000 token | Proje-spesifik |

**Toplam:** ~3.800 token (ana chat) / ~5.800 token (proje chat)

---

## 💰 Maliyet Stratejisi

### Kullanılacak Teknikler

1. **Prompt Caching (Anthropic)** — Çekirdek kimlik ve aktif profil cache'lenir, %90 indirim
2. **Akıllı Model Routing** — Basit mesajlar için Haiku, karmaşık için Sonnet/GPT-5
3. **Vektör RAG** — Tüm geçmiş yerine sadece ilgili 3-5 anı çekilir
4. **Arka Plan Özetleme** — Her 20 mesajda bir Haiku ile sıkıştırma
5. **İki Aşamalı Yanıt** — Thinking mode sadece gerektiğinde

### Tahmini Aylık Maliyet

| Kalem | Minimum | Aktif Kullanım |
|---|---|---|
| AI (OpenAI + Anthropic) | ~$10 | ~$25-30 |
| Backend (Render Starter) | $7 | $7 |
| PostgreSQL (Neon free) | $0 | $0 |
| Qdrant Cloud (free) | $0 | $0 |
| Frontend (Vercel Hobby) | $0 | $0 |
| **Toplam** | **~$17/ay** | **~$35/ay** |

---

## 🛠️ Teknoloji Stack'i

### Şu An

| Katman | Teknoloji |
|---|---|
| Backend | Python 3.11+ · FastAPI · Pydantic v2 · PyJWT |
| Frontend | React 18 · Vite 5 · Tailwind CSS · Framer Motion |
| AI Provider | OpenAI 2.x SDK · Anthropic 0.9x SDK |
| Storage | Dosya tabanlı JSON/JSONL (local) |
| CI | GitHub Actions (`ruff` + `pytest`) |
| Deploy | Render.com (`render.yaml`) |

### Hedef (Faz 0.1 Sonrası)

| Katman | Teknoloji |
|---|---|
| Ana DB | **PostgreSQL** (Neon / Render) |
| Vektör DB | **Qdrant** (Cloud free tier) |
| Cache | **Redis** (Upstash free tier) |
| Object Storage | S3-uyumlu (R2 / Backblaze) |
| Frontend Deploy | Vercel / Cloudflare Pages |

---

## 🚀 Hızlı Başlatma

### Lokal Geliştirme

```bash
# 1. Sanal ortam
python3 -m venv .venv
source .venv/bin/activate

# 2. Backend bağımlılıkları
pip install -r requirements.txt

# 3. Frontend bağımlılıkları
cd frontend && npm install && npm run build && cd ..

# 4. Environment
cp .env.example .env
# .env dosyasını aç, OPENAI_API_KEY ve AYEX_JWT_SECRET doldur

# 5. Başlat
./run_mvp.sh
```

Aç:
- **Uygulama:** http://127.0.0.1:8000/
- **Health:** http://127.0.0.1:8000/health
- **Detaylı Durum:** http://127.0.0.1:8000/health/ready

### Sunucuya Deploy

`render.yaml` hazır. Adımlar:

1. Render.com'da yeni "Blueprint" → repo'yu bağla
2. Environment variables'ı gir:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `AYEX_JWT_SECRET` (güçlü random)
   - `AYEX_PASS` (Ahmet'in şifresi)
3. Deploy

---

## 📂 Proje Yapısı

```
.
├── CLAUDE.md                  # AI asistan operasyon rehberi (MUTLAKA oku)
├── README.md                  # Bu dosya
│
├── backend/
│   ├── src/
│   │   ├── config/            # Env & settings
│   │   ├── intel/             # Intel event sistemi (feed ingest)
│   │   ├── middleware/        # Auth, metrics
│   │   ├── routes/            # HTTP endpoint'ler
│   │   ├── services/          # İş mantığı (model, chat, memory, vb.)
│   │   ├── tools/             # Web search, URL fetch, market data
│   │   └── utils/             # Logging
│   └── tests/                 # pytest birim testler
│
├── frontend/
│   └── src/
│       ├── components/        # React bileşenleri
│       ├── pages/             # Sayfa bileşenleri
│       └── styles/            # CSS
│
├── docs/                      # Teknik dokümantasyon
├── scripts/                   # Runtime check, smoke test
├── .ayex/                     # Yerel veri (gitignored)
├── render.yaml                # Render.com deploy blueprint
├── requirements.txt           # Python bağımlılıkları
└── run_mvp.sh                 # Yerel başlatma scripti
```

---

## 🧪 Test

```bash
# Birim testler
.venv/bin/pytest backend/tests -q

# Linter
.venv/bin/ruff check backend

# Frontend build
cd frontend && npm run build
```

CI pipeline: `.github/workflows/backend-ci.yml` (her PR'da çalışır)

---

## 📚 Önemli Dokümanlar

- **[CLAUDE.md](./CLAUDE.md)** — AI asistanlar için operasyon rehberi (her oturumda oku)
- **[docs/architecture-overview.md](./docs/architecture-overview.md)** — Detaylı mimari
- **[docs/request-flow.md](./docs/request-flow.md)** — Request lifecycle
- **[docs/future-phases.md](./docs/future-phases.md)** — Gelecek fazlar

---

## 🛡️ Güvenlik

- API key'ler **asla** git'e girmez (`.env` gitignored)
- JWT auth ile endpoint koruması
- Günlük request & karakter limiti (cost guard)
- Intel ingest rate limit
- Her request'e `x-request-id` header (trace edilebilir)

---

## 📅 Yol Haritası

### ✅ Faz 0.0 — Temel Altyapı
Multi-model routing, intel ingest, bellek özetleme, CI, Render blueprint.

### 🚧 Faz 0.1 — Kişisel Zeka Sistemi (ŞU AN)
- PostgreSQL migration
- Çekirdek kimlik (Ahmet yazacak)
- 5 katmanlı prompt inşası
- Qdrant vektör bellek
- Prompt caching
- Ana chat + proje chat ayrımı
- Sunucu deployment

### 🔜 Faz 1 — Derinleşme
Mood takibi, otonom task runner, proaktif bildirimler, ses modu.

### 🔮 Faz 2+ — Entegrasyonlar
Takvim/email, sosyal medya, WhatsApp, self-analysis, plugin marketplace.

---

## 🤝 Geliştirme Prensipleri

1. **Tek kullanıcı** — AYEX-IA asla çoklu kullanıcıya açılmaz.
2. **Sürekli öğrenme** — Her konuşmadan Ahmet hakkında bir şey öğrenir.
3. **Dürüstlük** — Yalakalık yapmaz, gerçekçi geri bildirim verir.
4. **Maliyet bilinci** — Her token, her cache hit önemli.
5. **Dokümantasyon canlı** — CLAUDE.md ve README.md her değişiklikte güncellenir.

---

**Son güncelleme:** 2026-04-20 — Faz 0.1 başladı.
