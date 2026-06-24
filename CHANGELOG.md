# Changelog

## [2.0.0] — 2026-06-24

### Добавлено

**4-слойная архитектура:**
- `data/` — исходные данные (configs, archives, hbk)
- `derived/` — производные (индексы по конфигурациям и платформе)
- `tools/` — инструменты (16 форкнутых репозиториев + BSL LS)
- `runtime/` — файлы работы (paths, registry, soul, session-resume)

**Универсальная система конфигураций:**
- `register_config.py` — CLI (add, register, activate, archive, build, build-all, list, remove)
- `build_api_reference.py` — универсальный парсер API (любая конфигурация)
- `config-registry.json` — реестр всех конфигураций
- `paths.env` + `paths.py` — единый конфиг путей

**Инструменты:**
- BSL Language Server v1.0.1 (анализ .bsl + --baseline/--diff)
- 94 скила Desko77 (JSON DSL: meta-compile, form-compile, cfe-*)
- 168 проверок EDT-MCP
- 187 диагностик BSL LS
- v8unpack (распаковка .cf/.cfe)
- TF-IDF семантический поиск (fast_search_1c.py)
- hbk_extractor.py (распаковка .hbk синтакс-помощника)

**Фичи из Hermes Agent:**
- Learning loop (auto-skill creation в learned-skills/)
- LSP post-write diff (bsl-analyze.sh --diff)
- user-profile.md + soul.md (персона)
- Role-switching protocol (4 роли, 3 протокола)

**Стандартные файлы:**
- LICENSE (MIT)
- CONTRIBUTING.md, CODE_OF_CONDUCT.md
- .editorconfig
- .github/ (ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE)
- ARCHITECTURE.md

**Форки:**
- Все 16 репозиториев форкнуты на github.com/Pradushkoai/*
- manifest.json обновлён — URL указывают на форки

## [1.0.0] — 2026-06-23

- Initial release
- 8 скриптов, paths.env/paths.py, manifest.json, install.sh
- Шаблоны session-resume и project-context
