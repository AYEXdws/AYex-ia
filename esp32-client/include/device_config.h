#pragma once

#include <Arduino.h>

namespace device_config {

// Fill these before uploading.
inline constexpr const char* WIFI_SSID = "AYEX";
inline constexpr const char* WIFI_PASS = "AYEX293905a";
inline constexpr const char* AYEX_VOICE_HOST = "192.168.1.10";
inline constexpr uint16_t AYEX_VOICE_PORT = 8000;
inline constexpr const char* AYEX_VOICE_PATH = "/voice/turn";  // Backward-compatible endpoint alias.
inline constexpr const char* AYEX_WORKSPACE = "/Users/ayexdws/ayex-ia";
inline constexpr const char* AYEX_VOICE_NAME = "alloy";

inline constexpr uint32_t SAMPLE_RATE = 24000;
inline constexpr uint32_t HTTP_TIMEOUT_MS = 180000;
inline constexpr uint32_t MAX_RECORD_MS = 2500;
inline constexpr uint32_t SILENCE_MS = 550;
inline constexpr uint32_t MIN_SPEECH_MS = 350;
inline constexpr uint32_t TURN_COOLDOWN_MS = 450;
inline constexpr float SPK_GAIN = 1.8f;
inline constexpr int MIC_START_THRESHOLD = 920;
inline constexpr int MIC_CONTINUE_THRESHOLD = 620;
inline constexpr size_t PRE_ROLL_FRAMES = 6;  // ~60ms
inline constexpr size_t MAX_PCM_BYTES = (SAMPLE_RATE * 2 * MAX_RECORD_MS) / 1000;

// INMP441
inline constexpr int MIC_BCLK_PIN = 4;
inline constexpr int MIC_WS_PIN = 5;
inline constexpr int MIC_SD_PIN = 6;

// MAX98357A
inline constexpr int SPK_BCLK_PIN = 17;
inline constexpr int SPK_WS_PIN = 18;
inline constexpr int SPK_DIN_PIN = 16;

}  // namespace device_config
