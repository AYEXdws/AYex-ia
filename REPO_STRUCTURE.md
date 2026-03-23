# AYEX-IA - REPO STRUCTURE

Last Updated: 2026-03-23

## 1. Purpose

Bu dosya, repodaki klasorlerin neye hizmet ettigini ve hangi katmana ait oldugunu netlestirir.

Ana kural:
- tek omurga
- net sorumluluk
- gecis alanlari belgeli
- feature coplugu yok

## 2. Canonical Runtime

AYEX-IA icin kanonik runtime:
- `backend/src`
- `frontend/src`
- `esp32-client`

Uyumluluk / gecis katmani:
- `src/ayex_api`
- `src/ayex_core`

Kritik nokta:
`src/ayex_core` aktif urun omurgasi degil; gecis ve legacy etkisi tasiyan alandir.

## 3. Axis Map

### Cognitive Axis

Primary folders:
- `backend/src`
- `src/ayex_core` (legacy influence)
- `.ayex` (runtime state)

Responsibilities:
- chat/action routing
- profile and memory context
- intel ingestion and synthesis
- model routing
- tool usage discipline

### Physical Axis

Primary folders:
- `esp32-client`
- `arduino`
- `tools/realtime_bridge.py`
- `tools/serial_probe.py`

Responsibilities:
- voice capture/playback
- device connectivity
- firmware compatibility
- serial and local bridge tooling

### Public Axis

Primary folders:
- `frontend/src`
- future public publishing surfaces in `backend/src`

Responsibilities:
- visible interaction surface
- future insight/publishing surfaces
- future outward presentation

Important note:
mevcut frontend bugun private command deck agirliklidir; tam public axis degildir.

## 4. Folder Responsibility Map

### `backend/src`

Current role:
- primary application spine
- API entrypoint
- auth
- chat/action routes
- intel ingest/store/archive
- memory services
- model and tool orchestration

Rule:
burasi cognitive core'un buyudugu yerdir.

### `frontend/src`

Current role:
- private web interaction surface
- login
- chat panel
- system status panel

Rule:
bugunku hali private MVP'dir; ileride private ve public surface ayrisabilir.

### `esp32-client`

Current role:
- aktif cihaz istemcisi
- voice request / response akisi
- backend ile sesli etkilesim

Rule:
cihaz kodu cekirdege hizmet eder; cekirdegin yerine gecmez.

### `arduino`

Current role:
- referans / onceki deneysel firmware

Rule:
aktif urun omurgasi burada degil.

### `src/ayex_api`

Current role:
- compatibility wrapper

Rule:
yeni davranis burada gelistirilmemeli.

### `src/ayex_core`

Current role:
- legacy cognitive core
- terminal agent
- eski memory/tool abstractions
- voice tarafinda halen dolayli etkisi olan alan

Rule:
bu alan yeni omurga gibi buyutulmemeli.
Ya kucultulmeli ya da kontrollu bicimde `backend/src` icine emilmeli.

### `docs`

Current role:
- teknik akislar
- architecture/request/device notlari

Rule:
teknik gercek burada belgelenir.

### `.ayex`

Current role:
- runtime state
- profile
- conversations
- long memory
- intel event persistence
- usage records

Rule:
source code degildir; runtime data alanidir.

### `openclaw`

Current role:
- harici buyuk kaynak / referans clone
- AYEX aktif urun omurgasinin parcasi degil

Rule:
AYEX deploy ve product logic bu klasore baglanmamalidir.

## 5. Product-Critical Paths

Asagidaki alanlar bugun urun acisindan kritik:
- `backend/src/index.py`
- `backend/src/routes/chat.py`
- `backend/src/routes/action.py`
- `backend/src/routes/events.py`
- `backend/src/services/container.py`
- `backend/src/services/model_service.py`
- `backend/src/services/long_memory.py`
- `backend/src/services/memory_summarizer.py`
- `backend/src/intel/*`
- `frontend/src/pages/SystemPage.jsx`
- `frontend/src/components/ChatPanel.jsx`
- `esp32-client/src/main.cpp`
- `esp32-client/include/device_config.h`

## 6. Immediate Structural Truths

Bugunku repo gercegi:
- backend yeni omurga
- `ayex_core` halen etkili legacy
- frontend private MVP
- public axis daha cok niyet seviyesinde
- physical axis calisiyor ama cekirdekle tam hizali degil

## 7. Near-Term Structural Goal

Yakin hedef:
1. `backend/src` ana cognitive spine olarak kesinlestirilecek
2. `src/ayex_core` gecis/legacy alanina indirgenecek
3. private surface ve public surface ayrimi netlestirilecek
4. physical voice flow ayni context omurgasina baglanacak

## 8. Change Rules

Bir degisiklik yapmadan once su sorular sorulmali:
1. Bu degisiklik hangi eksene hizmet ediyor?
2. Bu degisiklik canonical runtime'da mi?
3. Bu degisiklik omurgayi netlestiriyor mu, bulandiriyor mu?
4. Yeni feature mi ekliyor, yoksa mevcut omurgayi guclendiriyor mu?

Omurgayi bulandiran degisiklikler ertelenmeli veya reddedilmelidir.
