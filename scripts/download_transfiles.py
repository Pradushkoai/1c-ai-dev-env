#!/usr/bin/env python3
"""Надёжная загрузка с transfiles.ru с retry."""

import os
import sys
import time
import urllib.request

URL = "https://transfiles.ru/getFiles/6467109"
OUTPUT = "/tmp/ut11_xml_full.zip"
REFERER = "https://transfiles.ru/7rcqv"
COOKIE_FILE = "/tmp/cookies.txt"


def load_cookies():
    """Загрузить cookies из файла."""
    cookies = []
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    parts = line.strip().split("\t")
                    if len(parts) >= 7:
                        cookies.append(f"{parts[5]}={parts[6]}")
    return "; ".join(cookies)


def main():
    total_attempts = 100
    target_size = 636202377  # 607 МБ

    # Текущий размер
    current = os.path.getsize(OUTPUT) if os.path.exists(OUTPUT) else 0
    print(f"Цель: {target_size / 1024 / 1024:.1f} МБ, текущий: {current / 1024 / 1024:.1f} МБ")

    cookies = load_cookies()

    for attempt in range(1, total_attempts + 1):
        if current >= target_size:
            print(f"\n✅ Готово! {current / 1024 / 1024:.1f} МБ")
            return True

        try:
            headers = {
                "Referer": REFERER,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Cookie": cookies,
            }
            if current > 0:
                headers["Range"] = f"bytes={current}-"

            req = urllib.request.Request(URL, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200 and current > 0:
                    current = 0

                mode = "ab" if current > 0 else "wb"
                with open(OUTPUT, mode) as f:
                    while True:
                        chunk = response.read(256 * 1024)  # 256 КБ
                        if not chunk:
                            break
                        f.write(chunk)
                        current += len(chunk)

                        if (current // (20 * 1024 * 1024)) > ((current - len(chunk)) // (20 * 1024 * 1024)):
                            pct = current / target_size * 100
                            print(
                                f"  {current / 1024 / 1024:.1f} / {target_size / 1024 / 1024:.1f} МБ ({pct:.1f}%)",
                                flush=True,
                            )

            print(f"Попытка {attempt}: {current / 1024 / 1024:.1f} МБ")

        except Exception as e:
            print(f"Попытка {attempt}: ошибка на {current / 1024 / 1024:.1f} МБ: {e}")
            time.sleep(2)
            current = os.path.getsize(OUTPUT) if os.path.exists(OUTPUT) else 0

    return current >= target_size


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
