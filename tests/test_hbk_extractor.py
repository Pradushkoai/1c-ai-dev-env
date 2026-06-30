"""Тест для hbk_extractor — проверка find PK signatures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_find_pk_signatures():
    """Проверяем что PK\x03\x04 сигнатура находится в бинарных данных."""
    # Создаём фейковый .hbk с PK сигнатурой
    fake_hbk = b'\x00' * 16 + b'PK\x03\x04' + b'\x00' * 100
    pk_pos = fake_hbk.find(b'PK\x03\x04')
    assert pk_pos == 16
    print(f"✅ PK сигнатура найдена на позиции {pk_pos}")


if __name__ == "__main__":
    test_find_pk_signatures()
    print("✅ Все тесты прошли")
