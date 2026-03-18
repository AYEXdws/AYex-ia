#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include "driver/i2s.h"
#include "esp_heap_caps.h"
// Fill these before uploading.
static const char* WIFI_SSID = "YOUR_WIFI_SSID";
static const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
static const char* AYEX_VOICE_HOST = "192.168.1.10";
static const uint16_t AYEX_VOICE_PORT = 8000;
static const char* AYEX_VOICE_PATH = "/voice/turn";
static const char* AYEX_WORKSPACE = "/Users/ayexdws/ayex-ia";
static const char* AYEX_VOICE_NAME = "alloy";

static const uint32_t SAMPLE_RATE = 24000;
static const uint32_t HTTP_TIMEOUT_MS = 180000;
static const uint32_t MAX_RECORD_MS = 2500;
static const uint32_t SILENCE_MS = 550;
static const uint32_t MIN_SPEECH_MS = 350;
static const uint32_t TURN_COOLDOWN_MS = 450;
static const float SPK_GAIN = 1.8f;
static const int MIC_START_THRESHOLD = 920;
static const int MIC_CONTINUE_THRESHOLD = 620;
static const size_t PRE_ROLL_FRAMES = 6;  // ~60ms
static const size_t MAX_PCM_BYTES = (SAMPLE_RATE * 2 * MAX_RECORD_MS) / 1000;

// INMP441
static const int MIC_BCLK_PIN = 4;
static const int MIC_WS_PIN = 5;
static const int MIC_SD_PIN = 6;

// MAX98357A
static const int SPK_BCLK_PIN = 17;
static const int SPK_WS_PIN = 18;
static const int SPK_DIN_PIN = 16;

static const i2s_port_t MIC_I2S_PORT = I2S_NUM_0;
static const i2s_port_t SPK_I2S_PORT = I2S_NUM_1;

static const size_t MIC_FRAME_SAMPLES = 240;  // 10 ms @ 24 kHz
static const size_t MIC_FRAME_BYTES = MIC_FRAME_SAMPLES * sizeof(int16_t);

int32_t micRaw[MIC_FRAME_SAMPLES];
int16_t micPcm[MIC_FRAME_SAMPLES];
int16_t toneBuffer[240];
int16_t preRollPcm[PRE_ROLL_FRAMES][MIC_FRAME_SAMPLES];
size_t preRollBytes[PRE_ROLL_FRAMES];
uint8_t* utterancePcm = nullptr;
uint32_t lastTurnMs = 0;

void* allocAudioBuffer(size_t size) {
  void* ptr = heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!ptr) {
    ptr = heap_caps_malloc(size, MALLOC_CAP_8BIT);
  }
  return ptr;
}

void setupMic() {
  const i2s_config_t cfg = {
    .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = static_cast<int>(SAMPLE_RATE),
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 6,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0,
  };
  const i2s_pin_config_t pins = {
    .bck_io_num = MIC_BCLK_PIN,
    .ws_io_num = MIC_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = MIC_SD_PIN,
  };
  i2s_driver_install(MIC_I2S_PORT, &cfg, 0, nullptr);
  i2s_set_pin(MIC_I2S_PORT, &pins);
  i2s_zero_dma_buffer(MIC_I2S_PORT);
}

void setupSpeaker() {
  const i2s_config_t cfg = {
    .mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = static_cast<int>(SAMPLE_RATE),
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0,
  };
  const i2s_pin_config_t pins = {
    .bck_io_num = SPK_BCLK_PIN,
    .ws_io_num = SPK_WS_PIN,
    .data_out_num = SPK_DIN_PIN,
    .data_in_num = I2S_PIN_NO_CHANGE,
  };
  i2s_driver_install(SPK_I2S_PORT, &cfg, 0, nullptr);
  i2s_set_pin(SPK_I2S_PORT, &pins);
  i2s_zero_dma_buffer(SPK_I2S_PORT);
}

void playTestTone() {
  const float phaseStep = 2.0f * PI * 880.0f / static_cast<float>(SAMPLE_RATE);
  float phase = 0.0f;
  for (size_t n = 0; n < 30; ++n) {
    for (size_t i = 0; i < 240; ++i) {
      toneBuffer[i] = static_cast<int16_t>(sinf(phase) * 7000.0f);
      phase += phaseStep;
      if (phase >= 2.0f * PI) phase -= 2.0f * PI;
    }
    size_t written = 0;
    i2s_write(SPK_I2S_PORT, toneBuffer, sizeof(toneBuffer), &written, portMAX_DELAY);
  }
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi baglaniyor");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi OK: ");
  Serial.println(WiFi.localIP());
  Serial.print("Voice host: ");
  Serial.print(AYEX_VOICE_HOST);
  Serial.print(":");
  Serial.println(AYEX_VOICE_PORT);
  Serial.println("WiFi setup tamam");
}

size_t readMicFrame() {
  size_t bytesRead = 0;
  esp_err_t err = i2s_read(MIC_I2S_PORT, micRaw, sizeof(micRaw), &bytesRead, 20 / portTICK_PERIOD_MS);
  if (err != ESP_OK || bytesRead == 0) return 0;

  const size_t samplesRead = bytesRead / sizeof(int32_t);
  for (size_t i = 0; i < samplesRead; ++i) {
    int32_t sample = micRaw[i] >> 11;
    if (sample > 32767) sample = 32767;
    if (sample < -32768) sample = -32768;
    micPcm[i] = static_cast<int16_t>(sample);
  }
  return samplesRead * sizeof(int16_t);
}

size_t recordUtterance(uint8_t* out, size_t cap) {
  size_t pcmLen = 0;
  bool inSpeech = false;
  uint32_t speechStart = 0;
  uint32_t lastVoice = 0;
  size_t preRollHead = 0;
  size_t preRollCount = 0;
  const uint32_t startMs = millis();

  auto appendFrame = [&](const int16_t* src, size_t bytes) -> bool {
    if ((pcmLen + bytes) > cap) return false;
    memcpy(out + pcmLen, src, bytes);
    pcmLen += bytes;
    return true;
  };

  auto storePreRoll = [&](size_t bytes) {
    memcpy(preRollPcm[preRollHead], micPcm, bytes);
    preRollBytes[preRollHead] = bytes;
    preRollHead = (preRollHead + 1) % PRE_ROLL_FRAMES;
    if (preRollCount < PRE_ROLL_FRAMES) {
      preRollCount++;
    }
  };

  while ((millis() - startMs) < MAX_RECORD_MS) {
    size_t bytes = readMicFrame();
    if (!bytes) continue;

    uint32_t energy = 0;
    const size_t samples = bytes / sizeof(int16_t);
    for (size_t i = 0; i < samples; ++i) energy += abs(micPcm[i]);
    const uint32_t avgAbs = samples ? (energy / samples) : 0;
    const uint32_t now = millis();

    if (!inSpeech) {
      if (avgAbs < static_cast<uint32_t>(MIC_START_THRESHOLD)) {
        storePreRoll(bytes);
        continue;
      }

      inSpeech = true;
      speechStart = now;
      lastVoice = now;

      // Prepend short pre-roll so first hece/kelime kirpilmasin.
      for (size_t i = 0; i < preRollCount; ++i) {
        size_t idx = (preRollHead + PRE_ROLL_FRAMES - preRollCount + i) % PRE_ROLL_FRAMES;
        if (!appendFrame(preRollPcm[idx], preRollBytes[idx])) {
          return pcmLen;
        }
      }
      preRollCount = 0;
      preRollHead = 0;
      if (!appendFrame(micPcm, bytes)) {
        return pcmLen;
      }
      continue;
    }

    if (avgAbs >= static_cast<uint32_t>(MIC_CONTINUE_THRESHOLD)) {
      lastVoice = now;
    }
    if (!appendFrame(micPcm, bytes)) {
      return pcmLen;
    }

    if ((now - lastVoice) >= SILENCE_MS) {
      if ((now - speechStart) >= MIN_SPEECH_MS) return pcmLen;
      pcmLen = 0;
      inSpeech = false;
      preRollCount = 0;
      preRollHead = 0;
      continue;
    }
  }

  return 0;
}

void writeWavHeader(WiFiClient& client, size_t pcmLen) {
  const uint32_t dataSize = pcmLen;
  const uint32_t fileSize = 36 + dataSize;
  uint8_t hdr[44];
  size_t pos = 0;

  auto push32 = [&](uint32_t v) {
    hdr[pos++] = v & 0xFF;
    hdr[pos++] = (v >> 8) & 0xFF;
    hdr[pos++] = (v >> 16) & 0xFF;
    hdr[pos++] = (v >> 24) & 0xFF;
  };
  auto push16 = [&](uint16_t v) {
    hdr[pos++] = v & 0xFF;
    hdr[pos++] = (v >> 8) & 0xFF;
  };

  memcpy(hdr + pos, "RIFF", 4);
  pos += 4;
  push32(fileSize);
  memcpy(hdr + pos, "WAVEfmt ", 8);
  pos += 8;
  push32(16);
  push16(1);
  push16(1);
  push32(SAMPLE_RATE);
  push32(SAMPLE_RATE * 2);
  push16(2);
  push16(16);
  memcpy(hdr + pos, "data", 4);
  pos += 4;
  push32(dataSize);
  client.write(hdr, sizeof(hdr));
}

void writeSpeakerPcmBoosted(const uint8_t* data, size_t bytes) {
  if (!data || bytes < 2) return;
  const size_t evenBytes = bytes & ~static_cast<size_t>(1);
  const int16_t* in = reinterpret_cast<const int16_t*>(data);
  const size_t totalSamples = evenBytes / sizeof(int16_t);
  int16_t boosted[256];

  size_t pos = 0;
  while (pos < totalSamples) {
    const size_t block = min(static_cast<size_t>(256), totalSamples - pos);
    for (size_t i = 0; i < block; ++i) {
      float v = static_cast<float>(in[pos + i]) * SPK_GAIN;
      if (v > 32767.0f) v = 32767.0f;
      if (v < -32768.0f) v = -32768.0f;
      boosted[i] = static_cast<int16_t>(v);
    }
    size_t written = 0;
    i2s_write(SPK_I2S_PORT, boosted, block * sizeof(int16_t), &written, portMAX_DELAY);
    pos += block;
  }
}

bool streamVoiceTurn(const uint8_t* pcm, size_t pcmLen) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("voice turn: WiFi bagli degil");
    return false;
  }

  WiFiClient client;
  client.setTimeout(HTTP_TIMEOUT_MS / 1000);
  if (!client.connect(AYEX_VOICE_HOST, AYEX_VOICE_PORT)) {
    Serial.print("voice turn: host baglanti hatasi ");
    Serial.print(AYEX_VOICE_HOST);
    Serial.print(":");
    Serial.println(AYEX_VOICE_PORT);
    return false;
  }

  const String boundary = "----ESP32VoiceBoundary";
  String head;
  head += "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"workspace\"\r\n\r\n";
  head += String(AYEX_WORKSPACE) + "\r\n";
  head += "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"voice\"\r\n\r\n";
  head += String(AYEX_VOICE_NAME) + "\r\n";
  head += "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"audio\"; filename=\"audio.wav\"\r\n";
  head += "Content-Type: audio/wav\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";
  const size_t bodyLen = head.length() + 44 + pcmLen + tail.length();

  client.printf("POST %s HTTP/1.1\r\n", AYEX_VOICE_PATH);
  client.printf("Host: %s:%u\r\n", AYEX_VOICE_HOST, AYEX_VOICE_PORT);
  client.println("Connection: close");
  client.printf("Content-Type: multipart/form-data; boundary=%s\r\n", boundary.c_str());
  client.printf("Content-Length: %u\r\n\r\n", static_cast<unsigned>(bodyLen));
  client.print(head);
  writeWavHeader(client, pcmLen);
  client.write(pcm, pcmLen);
  client.print(tail);

  const uint32_t waitStart = millis();
  while (!client.available() && client.connected() && (millis() - waitStart) < HTTP_TIMEOUT_MS) {
    delay(10);
  }

  String statusLine = client.readStringUntil('\n');
  if (statusLine.length() == 0) {
    Serial.print("voice turn: bos HTTP status (wait_ms=");
    Serial.print(static_cast<unsigned>(millis() - waitStart));
    Serial.print(", connected=");
    Serial.print(client.connected() ? "1" : "0");
    Serial.print(", available=");
    Serial.print(client.available());
    Serial.println(")");
    return 0;
  }
  if (!statusLine.startsWith("HTTP/1.1 200") && !statusLine.startsWith("HTTP/1.0 200")) {
    Serial.print("HTTP status: ");
    Serial.println(statusLine);
    return 0;
  }

  while (client.connected()) {
    String line = client.readStringUntil('\n');
    if (line == "\r" || line.length() == 0) break;
  }

  bool wavReady = false;
  uint8_t wavProbe[512];
  size_t wavProbeLen = 0;
  uint8_t buf[1024];
  while (client.connected() || client.available()) {
    size_t avail = client.available();
    if (!avail) {
      delay(10);
      continue;
    }
    int n = client.readBytes(buf, min(avail, sizeof(buf)));
    if (n <= 0) continue;

    size_t offset = 0;
    if (!wavReady) {
      size_t copyNow = min(static_cast<size_t>(n), sizeof(wavProbe) - wavProbeLen);
      memcpy(wavProbe + wavProbeLen, buf, copyNow);
      wavProbeLen += copyNow;

      // Minimal WAV validation + dynamic "data" chunk search.
      if (wavProbeLen >= 12 &&
          wavProbe[0] == 'R' && wavProbe[1] == 'I' && wavProbe[2] == 'F' && wavProbe[3] == 'F' &&
          wavProbe[8] == 'W' && wavProbe[9] == 'A' && wavProbe[10] == 'V' && wavProbe[11] == 'E') {
        for (size_t i = 12; i + 8 <= wavProbeLen; ++i) {
          if (wavProbe[i] == 'd' && wavProbe[i + 1] == 'a' && wavProbe[i + 2] == 't' && wavProbe[i + 3] == 'a') {
            size_t audioStart = i + 8;
            if (audioStart < wavProbeLen) {
              size_t playable = wavProbeLen - audioStart;
              if (playable & 1) playable -= 1;
              if (playable > 0) {
                writeSpeakerPcmBoosted(wavProbe + audioStart, playable);
              }
            }
            wavReady = true;
            break;
          }
        }
      }

      if (!wavReady) {
        if (wavProbeLen >= sizeof(wavProbe)) {
          Serial.println("voice turn: wav header parse hatasi");
          return 0;
        }
        continue;
      }

      if (copyNow < static_cast<size_t>(n)) {
        offset = copyNow;
      } else {
        continue;
      }
    }

    size_t playable = static_cast<size_t>(n) - offset;
    if (playable & 1) playable -= 1;
    if (playable == 0) continue;
    writeSpeakerPcmBoosted(buf + offset, playable);
  }
  client.stop();
  return wavReady;
}

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("setup: alloc basliyor");
  utterancePcm = static_cast<uint8_t*>(allocAudioBuffer(MAX_PCM_BYTES));
  if (!utterancePcm) {
    Serial.println("buffer alloc hatasi");
    while (true) delay(1000);
  }
  Serial.println("setup: alloc tamam");
  setupMic();
  Serial.println("setup: mic tamam");
  setupSpeaker();
  Serial.println("setup: speaker tamam");
  playTestTone();
  Serial.println("setup: tone tamam");
  connectWifi();
  Serial.println("setup: wifi tamam");
}

void loop() {
  static bool firstLoop = true;
  if (firstLoop) {
    Serial.println("loop: basladi");
    firstLoop = false;
  }
  size_t utteranceLen = recordUtterance(utterancePcm, MAX_PCM_BYTES);
  if (!utteranceLen) {
    delay(30);
    return;
  }
  if ((millis() - lastTurnMs) < TURN_COOLDOWN_MS) {
    delay(20);
    return;
  }

  Serial.printf("Kayit alindi: %u byte PCM\n", static_cast<unsigned>(utteranceLen));
  if (!streamVoiceTurn(utterancePcm, utteranceLen)) {
    Serial.println("voice turn hatasi");
    lastTurnMs = millis();
    delay(300);
    return;
  }
  Serial.println("Cevap wav calindi");
  lastTurnMs = millis();
  delay(120);
}
