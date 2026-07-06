# Good First Issues (Этап 7.2)

> Этап 7.2: 10 issues с меткой `good first issue` созданы для привлечения контрибьюторов.
> Создано: 2026-07-04.

## Созданные issues

| # | Заголовок | Категория | Сложность |
|---|-----------|-----------|-----------|
| [#12](https://github.com/Pradushkoai/1c-ai-dev-env/issues/12) | Добавить типизацию для dict в diff.py | typing | 4 замены |
| [#13](https://github.com/Pradushkoai/1c-ai-dev-env/issues/13) | Добавить тест для DiffAnalyzer.format_report | testing | 2 теста |
| [#14](https://github.com/Pradushkoai/1c-ai-dev-env/issues/14) | Исправить ruff SIM102 в queries.py | code quality | 6 объединений if |
| [#15](https://github.com/Pradushkoai/1c-ai-dev-env/issues/15) | Исправить ruff E741 в code_metrics.py | code quality | 2 переименования |
| [#16](https://github.com/Pradushkoai/1c-ai-dev-env/issues/16) | Добавить тест для ConfigParser на demo | testing | 1 тест |
| [#17](https://github.com/Pradushkoai/1c-ai-dev-env/issues/17) | Исправить ruff F841 в misc.py | code quality | удалить 1 переменную |
| [#18](https://github.com/Pradushkoai/1c-ai-dev-env/issues/18) | Добавить тест для BorrowResult dataclass | testing | 2 теста |
| [#19](https://github.com/Pradushkoai/1c-ai-dev-env/issues/19) | Исправить ruff SIM102+E741 в architecture.py | code quality | 3 исправления |
| [#20](https://github.com/Pradushkoai/1c-ai-dev-env/issues/20) | Добавить docstring для demo | documentation | документация |
| [#21](https://github.com/Pradushkoai/1c-ai-dev-env/issues/21) | Добавить типизацию для dict в bsl_validator.py | typing | 1 замена |

## Категории

- **typing** (2): замена `dict` на `dict[str, Any]` — подготовка к Этапу 3.2 global
- **testing** (4): добавление тестов для непокрытых функций — подготовка к coverage 80%
- **code quality** (3): исправление ruff нарушений (SIM102, E741, F841)
- **documentation** (1): расширение demo/README.md

## Критерии good-first-issue

Каждый issue:
- Выполним за 1 вечер (30-60 минут)
- Имеет чёткое описание задачи
- Указан файл для изменения
- Указаны команды для проверки
- Указана сложность (начинающий)
- Связан с реальным техдолгом (не выдумка)

## Как использовать

1. Контрибьютор видит issues с меткой `good first issue`
2. Выбирает подходящий
3. Делает fork → branch → PR
4. PR проверяется через CI (ruff + mypy + pytest + smoke)
5. Merge после review

## Связанные документы

- [CONTRIBUTING.md](../CONTRIBUTING.md) — how-to гайды
- [demo/README.md](../demo/README.md) — quickstart для новых контрибьюторов
- [AGENTS.md](../AGENTS.md) — правила для AI-агентов
