# ADR-0006: Scope Reduction v6.x — заморозка SaaS/Enterprise/Plugin

**Дата:** 2026-07-04
**Статус:** Accepted

## Контекст

Проект 1c-ai-dev-env v6.0.0 (2026-07-03) был заявлен как "Production-Ready",
но объективные метрики противоречат этому:

| Метрика | Текущее | Production-Ready target |
|---------|---------|-------------------------|
| Coverage | 71.44% | ≥ 80% |
| mypy strict | с исключениями (warn_return_any=false) | без исключений |
| Bus factor | 1 (solo-dev) | ≥ 2 |
| Реальные пользователи SaaS/Enterprise | 0 | ≥ 1 issue/PR |
| Активные контрибьюторы | 1 (author) | ≥ 2 |
| Срок между major bumps | 1 день (5.3→6.0) | ≥ 2 недели |

При этом в репозитории реализованы:

- **S1: SaaS-подготовка** — `billing_stub.py`, namespace isolation, multi-tenant
  architecture (docs/SAAS_ARCHITECTURE.md)
- **S3: Enterprise Features** — `enterprise.py` (audit logger, RBAC stub)
- **S2: Plugin System** — `plugin_manager.py`

Эти модули:

1. Имеют **0 реальных пользователей** (0 issue, 0 PR, 0 stars от enterprise)
2. **Не могут поддерживаться** solo-dev (multi-tenant/RBAC требуют команды)
3. **Тянут зависимости и тесты** — 3 модуля (~598 LOC) + 3 тест-файла
   (~670 LOC) = ~1268 LOC, которые нужно поддерживать
4. **Создают ложное впечатление** готовности к enterprise-prod, что
   противоречит реальному статусу Beta
5. **Увеличивают cognitive load** при onboarding (новый разработчик не
   понимает, что core, а что — speculative future-proofing)

## Рассмотренные варианты

### Вариант A: Оставить как есть, "починить потом"

- **Pros:**
  - 0 work сейчас
  - Код сохраняется в `src/services/`, готов к "включению"
- **Cons:**
  - Поддержка ~1268 LOC, который не используется
  - Coverage/mypy/ruff continuing покрывают эти модули — это пустая работа
  - Создаёт ложное impression для новых контрибьюторов
  - ROADMAP остаётся противоречивым ("Production-Ready" при Beta-метриках)

### Вариант B: Удалить модули полностью

- **Pros:**
  - Максимально чистый репозиторий
  - 0 maintenance overhead
- **Cons:**
  - Потеря наработок (billing stub, audit logger могут пригодиться)
  - git history становится сложнее (если когда-то вернёмся — придётся
    cherry-pick из старых коммитов)
  - Нарушает принцип "сохранить IP" — даже если сейчас не используется,
    код может быть полезен как референс

### Вариант C: Quarantine в `experimental/` (выбран)

- **Pros:**
  - Код сохранён (IP не потерян)
  - Исключён из main (`src/` не импортирует)
  - Исключён из CI (ruff/mypy/coverage/pytest не проверяют)
  - Явная маркировка "не для production" через `experimental/README.md`
  - Простой путь возврата при выполнении критериев
  - ROADMAP/CHANGELOG явно фиксируют решение
- **Cons:**
  - Содержит ~1268 LOC "мёртвого" кода в репозитории
  - Требует обновления импортов при возврате (но это и явный сигнал
    "вы сознательно возвращаете SaaS фичи — готовы?")

## Решение

**Вариант C — quarantine в `experimental/`.**

### Что сделано

1. **Перенос модулей** (git mv, история сохранена):
   - `src/services/billing_stub.py` → `experimental/services/billing_stub.py`
   - `src/services/enterprise.py` → `experimental/services/enterprise.py`
   - `src/services/plugin_manager.py` → `experimental/services/plugin_manager.py`

2. **Перенос тестов** (git mv):
   - `tests/test_saas_preparation.py` → `experimental/tests/test_saas_preparation.py`
   - `tests/test_enterprise.py` → `experimental/tests/test_enterprise.py`
   - `tests/test_plugin_system.py` → `experimental/tests/test_plugin_system.py`

3. **Обновление импортов** в experimental/tests/:
   - `from src.services.X` → `from experimental.services.X`

4. **Исключения в `pyproject.toml`**:
   - `ruff.extend-exclude += "experimental/"`
   - `mypy.exclude += "experimental/"`
   - `coverage.omit += "experimental/*"`
   - `pytest.testpaths = ["tests"]` — уже не собирал experimental/
   - `setuptools.packages.find` — уже включал только `src*`

5. **Документация**:
   - `experimental/README.md` — что здесь, почему, когда вернуть
   - `docs/SAAS_ARCHITECTURE.md` — обновлены import paths + warning
   - `ROADMAP.md` — S1/S2/S3 перенесены в BACKLOG
   - `CHANGELOG.md` — задачи 0.1, 0.2, 0.3 зафиксированы

6. **Статус понижен**:
   - v6.0.0: "Production-Ready" → "Beta"
   - README badge: `status-Beta` со ссылкой на критерии перехода

### Критерии возврата в `src/services/`

Модули возвращаются из `experimental/` при выполнении **всех** условий
(см. [ROADMAP.md](../ROADMAP.md#критерии-перехода-beta--production-ready)):

1. Coverage core ≥ 80% (этап 5.2)
2. mypy strict без исключений (этап 3.1-3.2)
3. Реальные пользователи — ≥ 3 внешних issue/PR от non-author
4. Bus factor > 1 — ≥ 1 активный контрибьютор кроме автора
5. Документация актуальна — Stability Matrix в README
6. Нет критических TODO/FIXME без issue-ссылки (этап 3.4)
7. Demo-конфигурация проходит smoke-тест у внешнего пользователя (этап 7.1)

Возврат происходит **по одному модулю**, с обновлением тестов и
импортов. См. задачу 8.3 в поэтапном плане.

## Последствия

### Положительные

- ✅ Main (`src/`) больше не содержит speculative future-proofing
- ✅ Coverage/mypy/ruff не тратят время на замороженный код
- ✅ ROADMAP/CHANGELOG честно отражают Beta-статус
- ✅ Новый разработчик видит: core = `src/`, experimental = `experimental/`
- ✅ Простая история возврата: git mv обратно + обновить импорты

### Отрицательные

- ⚠️ ~1268 LOC "мёртвого" кода в репо (но git mv сохраняет blame)
- ⚠️ При возврате нужно обновить импорты в тестах
- ⚠️ Документация (SAAS_ARCHITECTURE.md) ссылается на `experimental/`,
  что может смутить новых читателей — mitigation: явные warnings

### Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Code rot в experimental/ | Высокая (нет CI) | Среднее | explicit README: "не поддерживается" |
| Пользователь импортирует experimental/ в prod | Низкая | Высокое | README warning + отсутствие в `pip install` |
| При возврате конфликты с main | Средняя | Среднее | git mv сохраняет историю; возврат — отдельная задача |
| Утеря IP при fork/reorg | Низкая | Высокое | experimental/ в репо, не удалён |

### Future implications

- При переходе Beta → Production-Ready: задача 8.3 возвращает модули
- При появлении реального enterprise-пользователя: S3 возвращается первым
  (audit logger — простая, изолированная фича)
- S1 (SaaS) — последним, требует namespace isolation testing
- S2 (Plugin) — только после community request (≥ 1 плагина от non-author)

## Связанные документы

- [ROADMAP.md](../ROADMAP.md) — критерии Beta → Production-Ready
- [CHANGELOG.md](../CHANGELOG.md) — задачи 0.1, 0.2, 0.3, 0.4
- [experimental/README.md](../experimental/README.md) — что в experimental/
- [docs/SAAS_ARCHITECTURE.md](../docs/SAAS_ARCHITECTURE.md) — обновлённые
  import paths
- [ADR-0001](0001-solo-development-path.md) — Solo Development Path
  (контекст: почему SaaS/Enterprise/Plugin были добавлены изначально)
