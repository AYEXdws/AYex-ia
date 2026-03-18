# ESP32 PlatformIO Usage

## Firmware path

- `esp32-client/platformio.ini`
- `esp32-client/src/main.cpp`
- `esp32-client/include/device_config.h`

## 1) Configure device constants

Edit `esp32-client/include/device_config.h`:

- `WIFI_SSID`
- `WIFI_PASS`
- `AYEX_VOICE_HOST`
- `AYEX_VOICE_PORT`
- `AYEX_VOICE_PATH` (default `/voice/turn` for compatibility)

## 2) Build

```bash
cd esp32-client
pio run
```

## 3) Upload

```bash
pio run -t upload
```

## 4) Serial monitor

```bash
pio device monitor
```

## Notes

- Framework: Arduino
- Board: `esp32-s3-devkitc-1`
- Audio stack: INMP441 via I2S RX, MAX98357 via I2S TX
- No external Arduino libraries are required beyond core ESP32 Arduino framework
