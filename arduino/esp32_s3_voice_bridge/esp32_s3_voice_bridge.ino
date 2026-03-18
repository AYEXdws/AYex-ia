#include <Arduino.h>
#include "driver/i2s.h"
#include <math.h>

static const uint8_t SYNC_1 = 0xA5;
static const uint8_t SYNC_2 = 0x5A;
static const uint8_t FRAME_MIC_TO_MAC = 0x01;
static const uint8_t FRAME_MAC_TO_SPK = 0x02;

static const uint32_t SERIAL_BAUD = 921600;
static const uint32_t SAMPLE_RATE = 24000;
static const size_t MIC_SAMPLES_PER_FRAME = 240;   // 10 ms @ 24 kHz
static const size_t MIC_BYTES_PER_FRAME = MIC_SAMPLES_PER_FRAME * sizeof(int16_t);
static const float TEST_TONE_HZ = 880.0f;
static const int TEST_TONE_MS = 350;
static const int16_t TEST_TONE_AMPLITUDE = 7000;
static const float SPK_GAIN = 1.0f;
static const uint32_t PLAYBACK_PRIORITY_MS = 1200;
static const int MIC_ACTIVITY_THRESHOLD = 900;
static const uint32_t MIC_HANGOVER_MS = 350;

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

int32_t micRaw[MIC_SAMPLES_PER_FRAME];
int16_t micPcm[MIC_SAMPLES_PER_FRAME];
uint8_t spkBuffer[32768];
int16_t toneBuffer[240];

enum ParseState {
  WAIT_SYNC_1,
  WAIT_SYNC_2,
  WAIT_TYPE,
  WAIT_LEN_1,
  WAIT_LEN_2,
  WAIT_PAYLOAD
};

ParseState parseState = WAIT_SYNC_1;
uint8_t frameType = 0;
uint16_t frameLen = 0;
uint16_t frameRead = 0;
uint32_t lastSpeakerRxMs = 0;
uint32_t lastVoiceActivityMs = 0;

void writeFrame(uint8_t type, const uint8_t* payload, uint16_t length) {
  uint8_t header[5] = {
    SYNC_1,
    SYNC_2,
    type,
    static_cast<uint8_t>(length & 0xFF),
    static_cast<uint8_t>((length >> 8) & 0xFF),
  };
  Serial.write(header, sizeof(header));
  if (length > 0 && payload != nullptr) {
    Serial.write(payload, length);
  }
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

void sendMicFrame() {
  size_t bytesRead = 0;
  esp_err_t err = i2s_read(MIC_I2S_PORT, micRaw, sizeof(micRaw), &bytesRead, 20 / portTICK_PERIOD_MS);
  if (err != ESP_OK || bytesRead == 0) {
    return;
  }

  size_t samplesRead = bytesRead / sizeof(int32_t);
  if (samplesRead == 0) {
    return;
  }

  for (size_t i = 0; i < samplesRead; ++i) {
    int32_t sample = micRaw[i] >> 11;  // 24/32-bit INMP441 sample -> signed 16-bit PCM
    if (sample > 32767) sample = 32767;
    if (sample < -32768) sample = -32768;
    micPcm[i] = static_cast<int16_t>(sample);
  }

  uint32_t energySum = 0;
  for (size_t i = 0; i < samplesRead; ++i) {
    energySum += static_cast<uint32_t>(abs(micPcm[i]));
  }
  const uint32_t avgAbs = samplesRead ? (energySum / samplesRead) : 0;
  const uint32_t now = millis();
  if (avgAbs >= static_cast<uint32_t>(MIC_ACTIVITY_THRESHOLD)) {
    lastVoiceActivityMs = now;
  }
  if ((now - lastVoiceActivityMs) > MIC_HANGOVER_MS) {
    return;
  }

  writeFrame(FRAME_MIC_TO_MAC, reinterpret_cast<uint8_t*>(micPcm), samplesRead * sizeof(int16_t));
}

void playSpeakerPayload(const uint8_t* payload, uint16_t length) {
  if (length == 0 || payload == nullptr) {
    return;
  }

  int16_t* samples = reinterpret_cast<int16_t*>(const_cast<uint8_t*>(payload));
  const size_t sampleCount = length / sizeof(int16_t);
  for (size_t i = 0; i < sampleCount; ++i) {
    float boosted = static_cast<float>(samples[i]) * SPK_GAIN;
    if (boosted > 32767.0f) boosted = 32767.0f;
    if (boosted < -32768.0f) boosted = -32768.0f;
    samples[i] = static_cast<int16_t>(boosted);
  }

  size_t written = 0;
  i2s_write(SPK_I2S_PORT, payload, length, &written, portMAX_DELAY);
}

void playTestTone() {
  const size_t samples = sizeof(toneBuffer) / sizeof(toneBuffer[0]);
  const float phaseStep = 2.0f * PI * TEST_TONE_HZ / static_cast<float>(SAMPLE_RATE);
  float phase = 0.0f;
  const uint32_t iterations = (SAMPLE_RATE * TEST_TONE_MS / 1000) / samples;

  for (uint32_t n = 0; n < iterations; ++n) {
    for (size_t i = 0; i < samples; ++i) {
      toneBuffer[i] = static_cast<int16_t>(sinf(phase) * TEST_TONE_AMPLITUDE);
      phase += phaseStep;
      if (phase >= 2.0f * PI) {
        phase -= 2.0f * PI;
      }
    }
    playSpeakerPayload(reinterpret_cast<uint8_t*>(toneBuffer), sizeof(toneBuffer));
  }
}

void processIncomingByte(uint8_t b) {
  switch (parseState) {
    case WAIT_SYNC_1:
      if (b == SYNC_1) {
        parseState = WAIT_SYNC_2;
      }
      break;

    case WAIT_SYNC_2:
      parseState = (b == SYNC_2) ? WAIT_TYPE : WAIT_SYNC_1;
      break;

    case WAIT_TYPE:
      frameType = b;
      parseState = WAIT_LEN_1;
      break;

    case WAIT_LEN_1:
      frameLen = b;
      parseState = WAIT_LEN_2;
      break;

    case WAIT_LEN_2:
      frameLen |= static_cast<uint16_t>(b) << 8;
      frameRead = 0;
      if (frameLen == 0) {
        parseState = WAIT_SYNC_1;
      } else if (frameLen > sizeof(spkBuffer)) {
        parseState = WAIT_SYNC_1;
      } else {
        parseState = WAIT_PAYLOAD;
      }
      break;

    case WAIT_PAYLOAD:
      spkBuffer[frameRead++] = b;
      if (frameRead >= frameLen) {
        if (frameType == FRAME_MAC_TO_SPK) {
          lastSpeakerRxMs = millis();
          playSpeakerPayload(spkBuffer, frameLen);
        }
        parseState = WAIT_SYNC_1;
      }
      break;
  }
}

void pumpSerialInput() {
  while (Serial.available() > 0) {
    processIncomingByte(static_cast<uint8_t>(Serial.read()));
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);

  setupMic();
  setupSpeaker();
  delay(100);
  playTestTone();
}

void loop() {
  pumpSerialInput();
  if (millis() - lastSpeakerRxMs >= PLAYBACK_PRIORITY_MS) {
    sendMicFrame();
  }
  pumpSerialInput();
}
