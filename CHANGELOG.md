# Changelog

## [1.0.0] — 2026-06-23

### Добавлено

**Базовая инфраструктура:**
- Единый конфиг путей (`paths.env` + `paths.py`) — 24 пути в 7 категориях
- `install.sh` — автоматическая установка среды
- `manifest.json` — список всех компонентов (11 git репозиториев, 8 скриптов, BSL LS)
- `requirements.txt` — Python зависимости (v8unpack, fastembed, qdrant-client, python-dotenv)
- `.gitignore` — исключения данных пользователя

**Скрипты (8 шт):**
- `hbk_extractor.py` — распаковка .hbk файлов синтакс-помощника 1С
- `build_config_index_generic.py` — универсальный парсер конфигураций 1С
- `build_syntax_helper_index.py` — индексация 8 141 методов платформы 1С
- `build_ut11_api_reference.py` — справочник API общих модулей конфигурации
- `fast_search_1c.py` — TF-IDF семантический поиск (2 сек, без нейросети)
- `bsl-analyze.sh` — анализ .bsl через BSL LS (--baseline, --diff режимы)
- `add_config.sh` — добавление новой конфигурации 1С
- `rag_1c_methods.py` — RAG индекс (опционально, требует GPU)

**Шаблоны:**
- `session-resume.template.md` — точка входа для новой сессии
- `project-context.template.md` — паспорт проекта

**Документация:**
- `README.md` — quick start guide
- `docs/research/` — исходники конкурентного анализа ИИ-инструментов для 1С

### Архитектура

**Принцип разделения:**
- `setup/` — код (коммитится в GitHub, ~240 КБ)
- `config/` — данные пользователя (НЕ коммитится)
- `indexes/` — генерируемые индексы (НЕ коммитятся)
- `syntax/` — клонируемые репозитории (НЕ коммитятся)

**Фичи из Hermes Agent (внедрены):**
- Learning loop — auto-skill creation после задач
- LSP post-write diff — только новые ошибки при рефакторинге
- user-profile.md — профиль пользователя
- soul.md — персона ассистента
- Role-switching protocol — 4 роли (Архитектор → Программист → Ревьюер → Документатор)

**Что НЕ внедрено (нам не подходит):**
- Cron scheduling (нет фоновых процессов)
- External memory providers (своя система)
- Multi-platform messaging
- Нейросетевой RAG (CPU слишком медленный, TF-IDF работает за 2 сек)
