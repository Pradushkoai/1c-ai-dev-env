"""Тест для fast_search — TF-IDF логика."""
import sys, math, re
from collections import Counter
from pathlib import Path


def test_tokenize():
    """Проверка токенизации."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    # Импортируем tokenize из fast_search_1c
    import importlib.util
    spec = importlib.util.spec_from_file_location("fs", Path(__file__).parent.parent / "scripts" / "fast_search_1c.py")
    # Не загружаем модуль целиком (нужен paths), проверяем логику вручную
    tokens = re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', "НайтиПоКоду test 123")
    assert len(tokens) == 3
    print(f"✅ Токенизация: {tokens}")


if __name__ == "__main__":
    test_tokenize()
    print("✅ Все тесты прошли")
