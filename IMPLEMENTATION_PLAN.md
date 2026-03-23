# AYEX-IA - IMPLEMENTATION PLAN

Last Updated: 2026-03-23

## 1. Purpose

Vizyon buyuk.
Ama uygulama sirasi daha da onemli.

Bu dosya, bugunden vizyona giderken neyi hangi sirayla yapacagimizi netlestirir.

## 2. Current Stage

Bugunku gercek durum:
- identity docs guclu
- backend calisiyor
- frontend MVP calisiyor
- intel ingest mevcut
- voice/device hattinin ilk calisan hali mevcut

Ama eksik olan sey:
- tek cognitive spine
- ortak context composer
- public axis urunu
- production-grade deploy discipline

Bu nedenle proje su an:
- late Phase 1
- early Phase 2 hazirligi

durumundadir.

## 3. Immediate Mission

Su an ana hedef:
- sistemi buyutmek degil
- sistemi hizalamak

Yanlis hareket:
- yeni tool eklemek
- yeni workflow acmak
- public surface'i erken buyutmek
- fiziksel tarafi erken sismek

Dogru hareket:
- omurgayi tek yapmak
- context katmanini birlestirmek
- repo sorumluluklarini netlestirmek

## 4. Workstream Order

### Workstream 1 - Single Spine

Goal:
`backend/src` ana cognitive runtime olsun.

Required outcomes:
- chat/action/audio ayni zihinsel omurgaya baglansin
- `src/ayex_core` yeni feature merkezi olmaktan ciksin
- compatibility layer sadece wrapper rolunde kalsin

Success condition:
- "AYEX'in asil zihni nerede?" sorusunun tek cevabi vardir

### Workstream 2 - Unified Context Layer

Goal:
tek bir context composition sistemi kurmak

Should combine:
- profile context
- session history
- recalled cross-session context
- long memory
- intel context
- response style

Success condition:
- `/chat`, `/action`, `/audio` farkli zihinler gibi davranmaz

### Workstream 3 - Public Axis Separation

Goal:
private assistant ile public insight surface'i ayirmak

Should define:
- private responses
- public-ready summaries
- publish eligibility rules
- public data shaping

Success condition:
- sistemin kamusal yuzu, private asistandan ayri ama ayni omurgaya bagli calisir

### Workstream 4 - Physical Alignment

Goal:
voice/device katmanini cognitive core ile tam hizalamak

Should define:
- same memory/context behavior
- same response identity
- stable audio turn contracts
- device config discipline

Success condition:
- cihaz uzerinden gelen AYEX, web uzerinden gelen AYEX ile ayni sistem hissini verir

### Workstream 5 - Operational Hardening

Goal:
deploy, CI, secrets, runtime state ve repo hijyenini guclendirmek

Should include:
- real deploy script/runbook parity
- frontend build checks
- integration smoke checks
- secret-safe firmware config strategy
- runtime data hygiene

Success condition:
- sistem sadece calismaz; guvenilir sekilde buyur

## 5. Concrete Priority Queue

Siradaki uygulanacak isler:
1. repo structure ve ownership map
2. canonical runtime karari ve gecis notlari
3. unified context design
4. chat/action flow convergence
5. public surface data contract
6. device config hardening
7. deploy and CI alignment

## 6. What We Should Not Do Yet

Simdilik ertelenecek alanlar:
- sensor-heavy context expansion
- high autonomy
- genis n8n workflow buyumesi
- fazla tool surface genislemesi
- public siteye icerik yigmak

Sebep:
omurga oturmadan genisleme, hiz yerine kaos uretir.

## 7. Definition Of Progress

Ilerleme sunlarla olculecek:
- daha fazla feature sayisi ile degil
- daha net sistem sinirlari ile
- daha tutarli AYEX davranisi ile
- daha temiz repo sorumluluklari ile
- daha guvenli deploy ve state yonetimi ile

## 8. Immediate Build Rule

Bugunden itibaren temel kural:

Once spine.
Sonra context.
Sonra public surface.
Sonra physical derinlesme.
Sonra autonomy.

Bu sira bozulmamalidir.
