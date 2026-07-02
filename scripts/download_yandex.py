#!/usr/bin/env python3
"""Загрузка с Яндекс.Диска с автоматическим обновлением ссылки."""

import json
import os
import sys
import time
import urllib.request

PUBLIC_KEY = "https://disk.yandex.by/d/3hhpHMzmcgyKVg"
OUTPUT = "/tmp/ut11_xml_full.zip"
API_URL = "https://cloud-api.yandex.net/v1/disk/public/resources/download"


def get_download_url():
    """Получить прямую ссылку для скачивания."""
    url = f"{API_URL}?public_key={urllib.parse.quote(PUBLIC_KEY)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data.get("href")


def main():
    target_size = 636202377
    current = os.path.getsize(OUTPUT) if os.path.exists(OUTPUT) else 0
    print(f"Цель: {target_size / 1024 / 1024:.1f} МБ, текущий: {current / 1024 / 1024:.1f} МБ")

    max_attempts = 50
    for attempt in range(1, max_attempts + 1):
        if current >= target_size:
            print(f"\n✅ Готово! {current / 1024 / 1024:.1f} МБ")
            return True

        try:
            # Получаем свежую ссылку
            dl_url = get_download_url()
            if not dl_url:
                print(f"Попытка {attempt}: не удалось получить ссылку")
                time.sleep(3)
                continue

            headers = {"User-Agent": "Mozilla/5.0"}
            if current > 0:
                headers["Range"] = f"bytes={current}-"

            req = urllib.request.Request(dl_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200 and current > 0:
                    current = 0

                mode = "ab" if current > 0 else "wb"
                with open(OUTPUT, mode) as f:
                    while True:
                        chunk = response.read(512 * 1024)  # 512 КБ
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

            print(f"Попытка {attempt}: скачано до {current / 1024 / 1024:.1f} МБ")

        except Exception as e:
            print(f"Попытка {attempt}: ошибка на {current / 1024 / 1024:.1f} МБ: {e}")
            time.sleep(2)
            current = os.path.getsize(OUTPUT) if os.path.exists(OUTPUT) else 0

    return current >= target_size


if __name__ == "__main__":
    import urllib.parse

    sys.exit(0 if main() else 1)
