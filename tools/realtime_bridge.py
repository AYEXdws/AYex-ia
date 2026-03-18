#!/usr/bin/env python3
import argparse
import base64
import io
import json
import os
import signal
import sys
import time
import uuid
import wave
from pathlib import Path
from urllib import request as urlrequest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import serial
from serial.tools import list_ports
from serial.serialutil import SerialException

from ayex_core import AyexAgent
from ayex_core.config import DEFAULT_CHAT_MODEL, DEFAULT_MODEL as DEFAULT_AYEX_TEXT_MODEL

SYNC_1 = 0xA5
SYNC_2 = 0x5A
FRAME_MIC_TO_MAC = 0x01
FRAME_MAC_TO_SPK = 0x02

DEFAULT_BAUD = 921600
DEFAULT_REALTIME_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
SPEAKER_CHUNK_BYTES = 480
INPUT_SAMPLE_RATE = 24000
MIN_UTTERANCE_MS = 350


class AyexVoiceContext:
    def __init__(self, workspace: str | None = None, model: str | None = None, base_instructions: str = ""):
        workspace_path = Path(workspace).resolve() if workspace else Path.cwd().resolve()
        model_name = (
            model
            or os.environ.get("AYEX_VOICE_TEXT_MODEL")
            or os.environ.get("AYEX_CHAT_MODEL")
            or DEFAULT_CHAT_MODEL
            or DEFAULT_AYEX_TEXT_MODEL
        )
        self.agent = AyexAgent(workspace=workspace_path, model=model_name)
        self.base_instructions = base_instructions.strip()
        self.agent.mode = "sohbet"
        self.agent.chat_model = model_name
        self.agent.chat_max_tokens = 90

    def session_instructions(self) -> str:
        parts = [
            self.base_instructions,
            "Transcription mode. Only transcribe the user's Turkish speech accurately.",
        ]
        return "\n\n".join(part for part in parts if part)

    def _compact_context(self, transcript: str) -> str:
        retrieval = self.agent.memory.retrieve(transcript, limit=2)
        recent_items = list(self.agent.history)[-2:]
        recent = []
        for item in recent_items:
            recent.append(f"Kullanici: {item.get('user', '')}")
            recent.append(f"AYEX: {item.get('assistant', '')}")
        parts = []
        if retrieval:
            parts.append("Ilgili bellek:\n" + "\n".join(f"- {row}" for row in retrieval[:2]))
        if recent:
            parts.append("Son konusma:\n" + "\n".join(recent))
        return "\n\n".join(parts)

    def generate_reply(self, transcript: str) -> str:
        text = transcript.strip()
        if not text:
            return ""
        profile_capture = self.agent._capture_profile_facts(text)
        if profile_capture:
            self.record_turn(text, profile_capture)
            return profile_capture
        quick = self.agent._quick_reply(text, repeat_count=self.agent._repeat_count(text))
        if quick:
            reply = quick if quick.lower().startswith("ahmet") else f"Ahmet, {quick}"
            self.record_turn(text, reply)
            return reply

        prompt = (
            f"{self._compact_context(text)}\n\n"
            f"Kullanici: {text}\n\n"
            "Kurallar:\n"
            "- En fazla 2 cumle.\n"
            "- Kisa, net, dogal Turkce.\n"
            "- Sesli asistanda kolay anlasilacak kadar sade yaz.\n"
            "- Gereksiz tekrar, liste veya uzun analiz yapma.\n"
            "- Kullaniciyi taniyan bir asistan gibi cevap ver.\n"
        )
        reply = self.agent.chat_llm.generate(
            prompt=prompt,
            system=self.agent._chat_system(),
            temperature=0.2,
            max_tokens=90,
            allow_thinking=False,
        )
        reply = self.agent._normalize_reply(reply, user_text=text)
        reply = self.agent._limit_words(reply, 28)
        if not reply.lower().startswith("ahmet"):
            reply = f"Ahmet, {reply}"
        self.record_turn(text, reply)
        return reply

    def record_turn(self, user_text: str, assistant_text: str) -> None:
        user_text = user_text.strip()
        assistant_text = assistant_text.strip()
        if not user_text or not assistant_text:
            return
        intent = self.agent._rule_intent(user_text)
        normalized_reply = self.agent._normalize_reply(assistant_text, user_text=user_text)
        self.agent._record_turn(user_text, normalized_reply, intent=intent)


class SerialFramer:
    def __init__(self, ser: serial.Serial):
        self.ser = ser

    def read_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.ser.read(n - len(buf))
            if not self.ser.is_open:
                raise SerialException("serial port closed")
            if chunk:
                buf.extend(chunk)
        return bytes(buf)

    def read_frame(self):
        while True:
            if self.read_exact(1)[0] != SYNC_1:
                continue
            if self.read_exact(1)[0] != SYNC_2:
                continue
            frame_type = self.read_exact(1)[0]
            length_bytes = self.read_exact(2)
            length = length_bytes[0] | (length_bytes[1] << 8)
            payload = self.read_exact(length) if length else b""
            return frame_type, payload

    def write_frame(self, frame_type: int, payload: bytes):
        length = len(payload)
        header = bytes([SYNC_1, SYNC_2, frame_type, length & 0xFF, (length >> 8) & 0xFF])
        self.ser.write(header + payload)


class RealtimeBridge:
    def __init__(
        self,
        port: str,
        baud: int,
        model: str,
        instructions: str,
        voice: str,
        api_base_url: str,
        api_key: str,
        workspace: str | None,
        ayex_model: str | None,
    ):
        self.port = port
        self.baud = baud
        self.model = model
        self.instructions = instructions
        self.voice = voice
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.running = True
        self.tts_model = os.environ.get("AYEX_TTS_MODEL", DEFAULT_TTS_MODEL)
        self.voice_context = AyexVoiceContext(
            workspace=workspace,
            model=ayex_model,
            base_instructions=instructions,
        )

        self.ser = serial.Serial(self.port, self.baud, timeout=1)
        self.framer = SerialFramer(self.ser)

        self.mic_frame_count = 0
        self.mic_byte_count = 0
        self.out_audio_frame_count = 0
        self.out_audio_byte_count = 0
        self.last_mic_log_ts = 0.0
        self.last_spk_log_ts = 0.0
        self.speech_threshold = int(os.environ.get("AYEX_VOICE_THRESHOLD", "900"))
        self.silence_ms = int(os.environ.get("AYEX_VOICE_SILENCE_MS", "450"))
        self.max_utterance_ms = int(os.environ.get("AYEX_VOICE_MAX_MS", "8000"))
        self.turn_buffer = bytearray()
        self.in_speech = False
        self.last_voice_ms = 0
        self.speech_started_ms = 0

    def _multipart_body(self, fields: dict[str, str], file_field: str, filename: str, content_type: str, payload: bytes):
        boundary = f"----CodexBoundary{uuid.uuid4().hex}"
        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(str(value).encode())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(payload)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        return boundary, bytes(body)

    def _pcm_to_wav_bytes(self, pcm: bytes, sample_rate: int = INPUT_SAMPLE_RATE) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        return buf.getvalue()

    def _transcribe_pcm(self, pcm: bytes) -> str:
        wav_bytes = self._pcm_to_wav_bytes(pcm)
        fields = {
            "model": self.model,
            "language": "tr",
        }
        boundary, body = self._multipart_body(
            fields=fields,
            file_field="file",
            filename="audio.wav",
            content_type="audio/wav",
            payload=wav_bytes,
        )
        req = urlrequest.Request(
            f"{self.api_base_url}/audio/transcriptions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        with urlrequest.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data.get("text", "")).strip()

    def _synthesize_speech_pcm(self, text: str) -> bytes:
        payload = {
            "model": self.tts_model,
            "voice": self.voice,
            "input": text,
            "response_format": "wav",
        }
        if self.tts_model == "gpt-4o-mini-tts":
            payload["instructions"] = "Turkce, net, sicak ama kisa konus."
        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            f"{self.api_base_url}/audio/speech",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlrequest.urlopen(req, timeout=90) as resp:
            wav_bytes = resp.read()
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())
        if channels != 1 or sample_width != 2 or sample_rate != 24000:
            raise RuntimeError(
                f"TTS audio format beklenenden farkli: channels={channels}, width={sample_width}, rate={sample_rate}"
            )
        return pcm

    def _play_pcm_on_esp(self, pcm: bytes) -> None:
        if not pcm:
            return
        if len(pcm) % 2 != 0:
            pcm += b"\x00"
        offset = 0
        while offset < len(pcm) and self.running:
            chunk = pcm[offset : offset + SPEAKER_CHUNK_BYTES]
            self.framer.write_frame(FRAME_MAC_TO_SPK, chunk)
            self.out_audio_frame_count += 1
            self.out_audio_byte_count += len(chunk)
            now = time.time()
            if now - self.last_spk_log_ts >= 1.0:
                print(f"[debug] spk frames={self.out_audio_frame_count} bytes={self.out_audio_byte_count}")
                self.last_spk_log_ts = now
            # Conservative pacing reduces UART overruns and audible crackle.
            audio_sec = (len(chunk) / 2) / 24000.0
            time.sleep(audio_sec + 0.003)
            offset += len(chunk)

    def _handle_transcript(self, transcript: str) -> None:
        clean = transcript.strip()
        if not clean:
            return
        print(f"[debug] transcript tamamlandi: {clean}")
        reply = self.voice_context.generate_reply(clean)
        if not reply:
            return
        print(reply)
        pcm = self._synthesize_speech_pcm(reply)
        self._play_pcm_on_esp(pcm)

    def _process_mic_payload(self, payload: bytes) -> None:
        if not payload or len(payload) % 2 != 0:
            return
        self.mic_frame_count += 1
        self.mic_byte_count += len(payload)
        now = time.time()
        if now - self.last_mic_log_ts >= 1.0:
            print(f"[debug] mic frames={self.mic_frame_count} bytes={self.mic_byte_count}")
            self.last_mic_log_ts = now

        sample_count = len(payload) // 2
        samples = memoryview(payload).cast("h")
        avg_abs = sum(abs(int(s)) for s in samples) / max(1, sample_count)
        now_ms = int(time.time() * 1000)

        if avg_abs >= self.speech_threshold:
            if not self.in_speech:
                self.in_speech = True
                self.turn_buffer = bytearray()
                self.speech_started_ms = now_ms
            self.last_voice_ms = now_ms
            self.turn_buffer.extend(payload)
            return

        if self.in_speech:
            self.turn_buffer.extend(payload)
            too_long = (now_ms - self.speech_started_ms) >= self.max_utterance_ms
            silence_done = (now_ms - self.last_voice_ms) >= self.silence_ms
            if too_long or silence_done:
                utterance = bytes(self.turn_buffer)
                self.turn_buffer = bytearray()
                self.in_speech = False
                if len(utterance) >= (INPUT_SAMPLE_RATE * 2 * MIN_UTTERANCE_MS // 1000):
                    transcript = self._transcribe_pcm(utterance)
                    if transcript:
                        print(f"\n[you] {transcript}")
                        print(f"[debug] transcript tamamlandi: {transcript}")
                        self._handle_transcript(transcript)

    def run(self):
        if not self.api_key:
            raise RuntimeError("API anahtari eksik. OPENAI_API_KEY veya AYEX_API_KEY tanimla.")

        print(f"[info] Serial: {self.port} @ {self.baud}")
        print(f"[info] STT Model: {self.model}")
        print(f"[info] TTS Model: {self.tts_model}")

        while self.running:
            try:
                frame_type, payload = self.framer.read_frame()
            except SerialException:
                if self.running:
                    print("[warn] serial okuma durdu.")
                break
            if frame_type == FRAME_MIC_TO_MAC:
                self._process_mic_payload(payload)

    def stop(self):
        if not self.running:
            return
        self.running = False
        try:
            self.ser.close()
        except Exception:
            pass


def autodetect_port() -> str | None:
    ports = list(list_ports.comports())
    if not ports:
        return None

    # Prefer USB modem-like ports used by ESP32 boards on macOS.
    preferred = [p.device for p in ports if "usbmodem" in p.device.lower()]
    if preferred:
        return preferred[0]

    # Fallback: first USB serial device.
    usbish = [p.device for p in ports if "usb" in (p.description or "").lower()]
    return usbish[0] if usbish else ports[0].device


def parse_args():
    parser = argparse.ArgumentParser(description="ESP32-S3 <-> OpenAI Realtime ses koprusu")
    parser.add_argument("--port", help="Serial port. Ornek: /dev/tty.usbmodemXXXX")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument(
        "--model",
        default=(
            os.environ.get("OPENAI_REALTIME_MODEL")
            or os.environ.get("AYEX_API_MODEL_REALTIME")
            or DEFAULT_REALTIME_MODEL
        ),
    )
    parser.add_argument(
        "--api-base-url",
        default=(os.environ.get("OPENAI_API_BASE_URL") or os.environ.get("AYEX_API_BASE_URL") or DEFAULT_API_BASE),
    )
    parser.add_argument(
        "--api-key",
        default=(os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or ""),
    )
    parser.add_argument("--voice", default="alloy")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("AYEX_WORKSPACE", str(Path.cwd())),
        help="AYEX bellek/profil klasoru. Varsayilan: mevcut calisma dizini",
    )
    parser.add_argument(
        "--ayex-model",
        default=os.environ.get("AYEX_MODEL", None),
        help="AYEX metin mantigi icin kullanilacak OpenAI model adi",
    )
    parser.add_argument(
        "--instructions",
        default="Kullaniciyla Turkce konus. Cevaplari kisa, net ve yardimci tut.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    port = args.port or autodetect_port()
    if not port:
        raise RuntimeError("Serial port bulunamadi. --port ile elle ver.")

    try:
        bridge = RealtimeBridge(
            port=port,
            baud=args.baud,
            model=args.model,
            instructions=args.instructions,
            voice=args.voice,
            api_base_url=args.api_base_url,
            api_key=args.api_key,
            workspace=args.workspace,
            ayex_model=args.ayex_model,
        )
    except SerialException as exc:
        msg = str(exc).lower()
        if "resource busy" in msg:
            raise RuntimeError(
                f"Serial port mesgul: {port}. Arduino Serial Monitor'u kapatip tekrar dene."
            ) from exc
        raise RuntimeError(f"Serial port acilamadi: {exc}") from exc

    def handle_signal(sig, frame):
        print("\n[info] Cikis...")
        bridge.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        bridge.run()
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
