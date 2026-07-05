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

### Проверка upstream (T5.2, 2026-07-05)

**Проведена проверка** saby-integration/v8unpack:

| Источник | Версия | Статус |
|----------|--------|--------|
| PyPI | 1.2.6 | Последняя на PyPI |
| GitHub main | 1.2.11 | 5 минорных версий вперёд PyPI |

**Changelog 1.2.7 → 1.2.11** (из `docs/history.md` в репозитории v8unpack):
- 1.2.7: fix расширения с пустой строкой в модуле приложения
- 1.2.8: fix код возврата при ошибке сборки
- 1.2.9: new параметр version для расширений и конфигураций
- 1.2.10: fix панели форм на старых платформах 8.2
- 1.2.11: new поддержка .erf (ExternalReport), fix OverflowError Windows FILETIME, fix base64 параметров

**Анализ кода `write_block`**: идентичен в 1.2.6 и 1.2.11:
```python
min_block_size = max(min_block_size, block_size)  # block_size = file_size(data)
header_data = (... int2hex(min_block_size) ...)   # пишется min_block_size
```

Для TOC-блока (когда `total_blocks == 1`) вызывается `write_block(f, doc_size=doc_size)` без `min_block_size`, поэтому `min_block_size = 0`, и в header пишется `block_size = file_size(data) = doc_size`.

**Вывод**: баг block_size для TOC НЕ исправлен в 1.2.11.

### План

1. ✅ Проверить актуальность бага в последней версии v8unpack — ВЫПОЛНЕНО (T5.2)
2. Создать минимальное воспроизведение (minimal reproducible example)
3. Открыть issue в https://github.com/saby-integration/v8unpack (upstream repo)
4. Если нет реакции 2 недели — fork v8unpack с патчем

### Минимальное воспроизведение

```python
import v8unpack
from pathlib import Path

# Создать .epf через v8unpack
v8unpack.build(src_dir, output_epf)

# Проверить block_size в TOC (сразу после 16-байтного header)
with open(output_epf, "rb") as f:
    header = f.read(16)
    import struct
    sig = struct.unpack("<I", header[:4])[0]
    block_size = struct.unpack("<I", header[4:8])[0]
    print(f"sig={hex(sig)}, block_size={block_size}")
    # Ожидается: sig=0x7fffffff, block_size=512
    # Фактически: sig=0x7fffffff, block_size=doc_size (неправильно для TOC)

    # TOC block header (offset 16, 31 байт):
    # \r\n + 8hex(doc_size) + ' ' + 8hex(block_size) + ' ' + 8hex(next) + ' \r\n
    toc_header = f.read(31)
    print(f"TOC header: {toc_header}")
    # Ожидается: block_size = 0x200 (512)
    # Фактически: block_size = doc_size (переменный)
```

### Версии

| Компонент | Версия | Статус |
|-----------|--------|--------|
| v8unpack (PyPI) | 1.2.6 | Баг подтверждён |
| v8unpack (GitHub main) | 1.2.11 | Баг НЕ исправлен (T5.2, 2026-07-05) |
| 1С:Предприятие | 8.3.11+ | Ожидает TOC block_size=512 |
| patch_epf_blocksize.py | — | Workaround активен (сохраняется) |
| 1c-ai-dev-env зависимость | 1.2.11 (git+https) | Обновлено в T5.2 |

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

- **P2.3:** Тесты + документация ✅
- **T5.2 (2026-07-05):** Проверка upstream — баг НЕ исправлен в 1.2.11 ✅
- **Future:** Открыть upstream issue с minimal reproducer
- **Future:** Fork v8unpack с патчем (если upstream не реагирует)
- **Future:** Автоматическое отключение патча при обновлении v8unpack
- **M6 T5.1:** Native EPF packer (расширение cf_extractor.py) — устранит зависимость
