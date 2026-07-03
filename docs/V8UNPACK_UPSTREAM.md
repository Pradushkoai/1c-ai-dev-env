# v8unpack block_size Upstream Issue (P2.3)

> Документация бага v8unpack 1.2.6 и обходного пути.
> P2.3 (план v2 Solo Edition).

## Описание бага

**v8unpack 1.2.6** пишет `block_size = doc_size` (фактический размер данных блока)
вместо `block_size = 0x200` (512, стандартный размер блока V8 контейнера).

Из-за этого 1С:Предприятие при открытии .epf/.erf файла выдаёт ошибку:
> «Ошибка формата потока»

## Обходной путь

Проект использует `scripts/patch_epf_blocksize.py` — скрипт, который
проходит по всем блокам V8 контейнера и заменяет `block_size` на 512.

### Интеграция

- `EpfFactory._build_epf()` автоматически применяет патч после сборки .epf
  через v8unpack (см. `src/services/epf_factory.py`)
- AGENTS.md документирует правило: «Всегда применяй патч после v8unpack -B»

### Проверка

Тест `tests/test_v8unpack_blocksize.py` проверяет:
1. patch_epf_blocksize.py существует и работает
2. EpfFactory применяет патч
3. AGENTS.md документирует баг
4. Созданный .epf имеет block_size=512

## Upstream Issue

**Статус:** PENDING (не открыт upstream issue)

### План

1. Проверить актуальность бага в последней версии v8unpack
2. Создать минимальное воспроизведение (minimal reproducible example)
3. Открыть issue в https://github.com/.../v8unpack (upstream repo)
4. Если нет реакции 2 недели — fork v8unpack с патчем

### Минимальное воспроизведение

```python
import v8unpack
from pathlib import Path

# Создать .epf через v8unpack
v8unpack.build(src_dir, output_epf)

# Проверить block_size в header
with open(output_epf, "rb") as f:
    header = f.read(16)
    import struct
    sig = struct.unpack("<I", header[:4])[0]
    block_size = struct.unpack("<I", header[4:8])[0]
    print(f"sig={hex(sig)}, block_size={block_size}")
    # Ожидается: sig=0x7fffffff, block_size=512
    # Фактически: sig=0x7fffffff, block_size=doc_size (неправильно)
```

### Версии

| Компонент | Версия | Статус |
|-----------|--------|--------|
| v8unpack | 1.2.6 | Баг подтверждён |
| 1С:Предприятие | 8.3.11+ | Ожидает block_size=512 |
| patch_epf_blocksize.py | — | Workaround активен |

## Автоматизация

### CI проверка

Тест `tests/test_v8unpack_blocksize.py::TestPatchRealEpf::test_patch_creates_valid_epf`
создаёт реальный .epf через EpfFactory и проверяет:
- V8 сигнатура (0x7FFFFFFF) в header
- block_size = 512 после патча

Если тест падает — патч не сработал, .epf невалиден для 1С.

### Версионная проверка

```python
# В будущем: автоматическое отключение патча при обновлении v8unpack
import v8unpack
if hasattr(v8unpack, '__version__'):
    version = v8unpack.__version__
    if version >= '1.3.0':  # гипотетическая версия с фиксом
        # Патч не нужен
        pass
    else:
        # Применить патч
        apply_patch(epf_path)
```

## Roadmap

- **P2.3 (этот документ):** Тесты + документация ✅
- **Future:** Открыть upstream issue
- **Future:** Fork v8unpack с патчем (если upstream не реагирует)
- **Future:** Автоматическое отключение патча при обновлении v8unpack
