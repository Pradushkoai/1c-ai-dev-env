# Fuzzing (P2.8)

> Coverage-guided fuzzing для парсеров XML 1С через atheris.
> P2.8 (план v2 Solo Edition).

## Обзор

Fuzzing — это метод автоматического тестирования, при котором инструмент
генерирует случайные/мутированные входные данные и проверяет, что программа
не падает (crash/hang). Это особенно важно для парсеров, которые обрабатывают
пользовательский ввод (XML-выгрузки конфигураций 1С).

1c-ai-dev-env использует **atheris** — coverage-guided fuzzer от Google
для Python. Atheris использует coverage feedback для эффективного поиска
edge cases.

## Парсеры под fuzzing

| Парсер | Файл | Что парсит |
|--------|------|------------|
| **xml_parser** | `scripts/xml_parser.py` | XML файлы 1С (безопасная обёртка над lxml) |
| **form_analyzer** | `scripts/form_analyzer.py` | Form.xml — формы 1С |
| **metadata_extractor** | `scripts/metadata_extractor.py` | Метаданные 1С (35 типов объектов) |

## Запуск

### Быстрые тесты (pytest, ~30 секунд)

```bash
# Установить atheris
pip install -e ".[dev]"

# Запустить fuzz тесты (быстрые, 100 итераций)
pytest tests/test_fuzzing.py -v --timeout=30
```

### Длительный fuzzing (standalone, 30+ минут)

```bash
# Standalone скрипт для длительного fuzzing
# Создаст tests/fuzz/ скрипты при необходимости
python -m atheris --instrument_imports tests/test_fuzzing.py
```

## Что проверяет fuzzing

1. **No crash** — парсер не должен падать с segfault, SystemExit, или другими
   фатальными ошибками на любых входных данных
2. **Graceful error handling** — парсер должен возвращать ValueError/ParseError
   для невалидных данных, а не crash
3. **No hang** — парсер не должен зависать на больших/сложных входных данных
   (timeout проверка)

## Типы fuzzing входных данных

| Тип | Пример | Что проверяет |
|-----|--------|---------------|
| Random bytes | `\x00\x01\x02...` | Устойчивость к бинарному мусору |
| Malformed XML | `<unclosed>` | Обработка невалидного XML |
| Empty input | `""` | Пустые файлы |
| Very large input | `<root>` + 10KB + `</root>` | Большие файлы |
| Valid XML | `<Form/>` | Корректная обработка валидных данных |
| Mixed encoding | UTF-8 + CP1251 | Смешанные кодировки |

## CI Integration

Fuzzing запускается в weekly CI job (аналогично mutation testing):

- **Workflow:** `.github/workflows/mutation-testing.yml` (шаблон для fuzzing)
- **Расписание:** Еженедельно
- **Duration:** 30 минут на каждый парсер
- **Результат:** GitHub Issue с отчётом о найденных crash

## Triage найденных crash

Если fuzzing находит crash:

1. **Воспроизвести** — запустить с найденным входом локально
2. **Минимальный пример** — уменьшить до минимального воспроизведения
3. **Regression test** — добавить тест в `tests/test_fuzzing.py`
4. **Фикс** — исправить парсер чтобы не crash
5. **Документация** — обновить этот файл если нужно

## Зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| atheris | >=3.0,<4.0 | Coverage-guided fuzzer для Python |

## Roadmap

- **P2.8 (этот документ):** Базовые fuzz тесты + документация ✅
- **Future:** Standalone fuzz скрипты (tests/fuzz/)
- **Future:** CI workflow специально для fuzzing (отдельный от mutation)
- **Future:** Fuzzing для EDT парсера (после P2.1)
- **Future:** Corpus seeding — использовать реальные XML 1С как seeds
