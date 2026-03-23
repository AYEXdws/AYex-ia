# Request Flow

Ayrintili versiyon icin `README.md` kullanilir. Bu dosya sadece hizli ozet.

## Text Flow (`/chat`)

1. `RequestMetricsMiddleware` request id ve latency takip eder.
2. `AuthMiddleware` korumali endpointlerde bearer token dogrular.
3. `routes/chat.py` guard + session + intel + memory context olusturur.
4. `ModelService` secilen modele gore OpenAI/Anthropic cagrisi yapar.
5. Sonuc `ChatStore` ve `LongMemory` katmanina yazilir.
6. Memory summary arka planda uretilir, basarisizsa retry queue'ya alinır.

## Ingest Flow (`/events/ingest`)

1. Opsiyonel ingest token kontrolu
2. RPM rate limit kontrolu
3. Payload validate (`IntelService.validate_event_payload`)
4. Event score + persist + archive
5. Long memory event append

## Audio Flow (`/audio`, `/voice/turn`)

1. WAV upload
2. STT
3. Intent + model routing
4. TTS
5. WAV response

## Operational Headers

- `x-request-id`
- `x-response-time-ms`
