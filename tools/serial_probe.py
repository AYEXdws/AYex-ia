#!/usr/bin/env python3
import argparse
import time

import serial

SYNC_1 = 0xA5
SYNC_2 = 0x5A


def main() -> None:
    parser = argparse.ArgumentParser(description="ESP32 serial ham/protokol probe")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--seconds", type=int, default=10)
    args = parser.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=0.2)
    start = time.time()
    total = 0
    sync_hits = 0
    frames = 0
    buf = bytearray()

    print(f"[info] probing {args.port} @ {args.baud} for {args.seconds}s")
    try:
        while time.time() - start < args.seconds:
            chunk = ser.read(4096)
            if not chunk:
                continue
            total += len(chunk)
            buf.extend(chunk)
            while True:
                idx = buf.find(bytes([SYNC_1, SYNC_2]))
                if idx < 0:
                    if len(buf) > 8192:
                        del buf[:-16]
                    break
                sync_hits += 1
                if len(buf) < idx + 5:
                    if idx > 0:
                        del buf[:idx]
                    break
                frame_type = buf[idx + 2]
                length = buf[idx + 3] | (buf[idx + 4] << 8)
                if len(buf) < idx + 5 + length:
                    if idx > 0:
                        del buf[:idx]
                    break
                frames += 1
                print(f"[frame] type=0x{frame_type:02X} len={length}")
                del buf[: idx + 5 + length]
        print(f"[done] bytes={total} sync_hits={sync_hits} frames={frames}")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
