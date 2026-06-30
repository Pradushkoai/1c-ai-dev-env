"""
Тесты для img_grid утилиты — наложение сетки на изображение.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Добавляем scripts/ в path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def test_image(tmp_path):
    """Создать тестовое изображение."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow не установлен")
    img = Image.new("RGB", (500, 300), "white")
    path = tmp_path / "test.png"
    img.save(path)
    return path


# ─────────────────────────────────────────────

def test_overlay_grid_creates_output(test_image, tmp_path):
    """overlay_grid создаёт файл с сеткой."""
    try:
        from img_grid import overlay_grid
    except ImportError:
        pytest.skip("img_grid не импортируется")

    output = tmp_path / "grid.png"
    result = overlay_grid(test_image, cols=20, output_path=output)

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_overlay_grid_default_output_name(test_image, tmp_path):
    """overlay_grid с output_path=None создаёт <name>-grid.png."""
    try:
        from img_grid import overlay_grid
    except ImportError:
        pytest.skip("img_grid не импортируется")

    result = overlay_grid(test_image, cols=10)
    expected = test_image.parent / "test-grid.png"
    assert result == expected
    assert expected.exists()


def test_overlay_grid_with_different_cols(test_image, tmp_path):
    """overlay_grid с разным количеством колонок."""
    try:
        from img_grid import overlay_grid
    except ImportError:
        pytest.skip("img_grid не импортируется")

    out1 = tmp_path / "grid_10.png"
    overlay_grid(test_image, cols=10, output_path=out1)
    out2 = tmp_path / "grid_50.png"
    overlay_grid(test_image, cols=50, output_path=out2)

    # Оба должны существовать
    assert out1.exists()
    assert out2.exists()


def test_overlay_grid_invalid_image_raises(tmp_path):
    """overlay_grid на несуществующий файл → FileNotFoundError."""
    try:
        from img_grid import overlay_grid
    except ImportError:
        pytest.skip("img_grid не импортируется")

    with pytest.raises(FileNotFoundError):
        overlay_grid(tmp_path / "missing.png", cols=10)


def test_overlay_grid_min_cols(test_image, tmp_path):
    """overlay_grid с cols < 2 — нормализует до 2."""
    try:
        from img_grid import overlay_grid
    except ImportError:
        pytest.skip("img_grid не импортируется")

    output = tmp_path / "grid.png"
    # cols=1 должен нормализоваться до 2
    result = overlay_grid(test_image, cols=1, output_path=output)
    assert result.exists()


def test_overlay_grid_with_rows(test_image, tmp_path):
    """overlay_grid с явным rows."""
    try:
        from img_grid import overlay_grid
    except ImportError:
        pytest.skip("img_grid не импортируется")

    output = tmp_path / "grid.png"
    result = overlay_grid(test_image, cols=20, rows=15, output_path=output)
    assert result.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
