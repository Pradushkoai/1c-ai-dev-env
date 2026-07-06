# experimental/

> ⚠️ **Не для production.** Код в этой директории заморожен и не
> поддерживается до выполнения критериев Beta → Production-Ready
> (см. [ROADMAP.md](../ROADMAP.md#критерии-перехода-beta--production-ready)).

## Что здесь

Модули, перенесённые из `src/services/` в рамках
[Этапа 0.1](../CHANGELOG.md) поэтапного плана улучшения. Эти модули
реализуют SaaS/Enterprise/Plugin фичи, которые:

1. Имеют 0 реальных пользователей
2. Не могут поддерживаться solo-dev
3. Тянут зависимости и тесты, увеличивая cognitive load
4. Создают ложное впечатление, что проект готов к enterprise-продакшену

Подробное обоснование — в [ADR-0006](../adr/0006-scope-reduction-v6.md).

## Структура

```
experimental/
├── services/
│   ├── billing_stub.py     — Заглушка billing для S1 SaaS-подготовки
│   ├── enterprise.py       — Audit logger для S3 Enterprise Features
│   └── plugin_manager.py   — S2 Plugin System
└── tests/
    ├── test_saas_preparation.py  — Тесты billing_stub + namespace isolation
    ├── test_enterprise.py        — Тесты enterprise audit logger
    └── test_plugin_system.py     — Тесты plugin manager
```

## Что не поддерживается

- ❌ Тесты из `experimental/tests/` **не запускаются** в CI
  (`testpaths = ["tests"]` в `pyproject.toml`)
- ❌ Код **не проверяется** mypy strict (исключён в `pyproject.toml`)
- ❌ Код **не линтуется** ruff (исключён в `pyproject.toml`)
- ❌ Код **не входит** в coverage (исключён в `pyproject.toml`)
- ❌ Код **не импортируется** из `src/` — main работает без него

## Когда вернуть обратно

При выполнении **всех** условий:

1. Проект перешёл из Beta в Production-Ready (см. ROADMAP.md)
2. Появился ≥ 1 активный контрибьютор кроме автора (bus factor > 1)
3. Есть реальные пользователи SaaS/Enterprise/Plugin (≥ 1 issue/PR)
4. Покрытие core-модулей ≥ 80% (чтобы не отвлекаться на experimental)

Тогда модули возвращаются в `src/services/` по одному, с обновлением
тестов и импортов. См. задачу 8.3 в
[поэтапном плане](../docs/IMPROVEMENT_PLAN.md).

## Импорт для тестирования вручную

```python
# Только для локальной проверки, не в CI
import sys
sys.path.insert(0, '.')

from experimental.services.billing_stub import BillingStub
from experimental.services.enterprise import AuditLogger
from experimental.services.plugin_manager import PluginManager
```
