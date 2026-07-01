from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream TTS audio from PIHUB and play it live.")
    parser.add_argument("text_file", type=Path, help="Path to a UTF-8 text file to synthesize.")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1/api/voice/tts",
        help="Voice TTS endpoint URL. Defaults to the gateway TTS route.",
    )
    parser.add_argument("--language", default="en", help="Language code to send to the server.")
    parser.add_argument("--voice", default="default", help="Voice name to send to the server.")
    parser.add_argument("--format", default="wav", choices=["wav", "mp3", "ogg"], help="Requested audio format.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Total request timeout in seconds.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=8192,
        help="How many response bytes to forward to the player per write.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=24000,
        help="PCM sample rate expected from the server.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.text_file.exists():
        print(f"Text file not found: {args.text_file}", file=sys.stderr)
        return 2

    text = args.text_file.read_text(encoding="utf-8").strip()
    if not text:
        print("Text file is empty.", file=sys.stderr)
        return 2

    player = shutil.which("ffplay")
    if not player:
        print("ffplay is not installed or not on PATH.", file=sys.stderr)
        return 2

    payload = {
        "text": text,
        "voice": args.voice,
        "language": args.language,
        "stream": True,
        "format": args.format,
        "cache": False,
    }

    command = [
        player,
        "-autoexit",
        "-nodisp",
        "-loglevel",
        "error",
        "-f",
        "s16le",
        "-ar",
        str(args.sample_rate),
        "-ac",
        "1",
        "-i",
        "pipe:0",
    ]
    player_proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    if player_proc.stdin is None:
        print("Failed to open ffplay stdin.", file=sys.stderr)
        return 2

    try:
        with httpx.stream("POST", args.endpoint, json=payload, timeout=args.timeout) as response:
            content_type = response.headers.get("content-type", "")
            if response.status_code >= 400:
                body = response.read().decode("utf-8", errors="replace")
                print(f"Server error {response.status_code}: {body}", file=sys.stderr)
                return 1
            if "audio/" not in content_type and "octet-stream" not in content_type:
                body = response.read().decode("utf-8", errors="replace")
                print(f"Unexpected content type: {content_type}", file=sys.stderr)
                print(body, file=sys.stderr)
                return 1

            for chunk in response.iter_bytes(chunk_size=args.chunk_size):
                if not chunk:
                    continue
                player_proc.stdin.write(chunk)
                player_proc.stdin.flush()
    except KeyboardInterrupt:
        return 130
    finally:
        try:
            player_proc.stdin.close()
        except Exception:
            pass
        player_proc.wait()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
