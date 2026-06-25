# 📋 Резюме сессии

> Входная точка — прочитай этот файл первым

## ⚡ БЫСТРЫЙ СТАРТ

### Шаг 0: Проверить окружение
```bash
python3 /home/z/my-project/runtime/paths.py validate
```

### Шаг 1: Прочитать контекст
1. `runtime/session-resume.md` (этот файл)
2. `runtime/soul.md` — персона
3. `runtime/user-profile.md` — профиль пользователя
4. `runtime/role-switching-protocol.md` — протокол ролей
5. `runtime/project-context.md` — паспорт проекта

### 🎭 Role-Switching Protocol
| Тип | Роли |
|------|------|
| Сложная | 🧠 Архитектор → 👨‍💻 Программист → 🔍 Ревьюер → 📝 Документатор |
| Простая | 👨‍💻 Программист → 🔍 Ревьюер |

---

## 📊 Конфигурации

| # | Конфигурация | Версия | Статус | Объектов |
|---|--------------|--------|--------|----------|
| 1 | УТ 11 (отраслевая) | 11.3.4.197 | active (метаданные) | 7 488 |
| 2 | Приемка товаров | 1.2 | active (полная) | 23 |

Реестр: `runtime/config-registry.json`

---

## 🏗 Архитектура (4 слоя)

```
/home/z/my-project/
├── data/              ИСХОДНЫЕ ДАННЫЕ (от пользователя)
│   ├── configs/       Конфигурации 1С (распакованные)
│   │   ├── ut11/
│   │   └── priemka/
│   ├── archives/      ZIP архивы
│   └── hbk/           Исходные .hbk файлы
│
├── derived/           ПРОИЗВОДНЫЕ (генерируются скриптами)
│   ├── configs/       Индексы по конфигурациям
│   │   └── priemka/   (index.md, api-reference.md/json)
│   └── platform/      Индексы платформы 1С
│
├── tools/             ИНСТРУМЕНТЫ
│   ├── repos/         18 git репозиториев
│   └── bsl-ls/        BSL LS binary
│
├── runtime/           ФАЙЛЫ РАБОТЫ
│   ├── paths.env      Конфиг путей
│   ├── paths.py       Python-модуль путей
│   ├── config-registry.json
│   ├── session-resume.md, soul.md, worklog.md, ...
│   └── .bsl-language-server.json
│
├── learned-skills/    LEARNING LOOP
├── scripts/           Рабочие скрипты (9 шт)
└── setup/             CODE FOR GITHUB
```

## 🧰 Команды

```bash
# Управление конфигурациями
python3 scripts/register_config.py list
python3 scripts/register_config.py build --name priemka
python3 scripts/register_config.py build-all
python3 scripts/register_config.py add --name <name> --zip <path> --title "Title"

# Поиск
python3 scripts/fast_search_1c.py search "найти по коду"

# Анализ .bsl
scripts/bsl-analyze.sh <path>
scripts/bsl-analyze.sh --baseline <path> && scripts/bsl-analyze.sh --diff <path>

# Создание объектов (JSON DSL)
python3 tools/repos/claude-code-skills-1c/skills/1c-meta-compile/scripts/meta-compile.py \
  -JsonPath /tmp/catalog.json -OutputDir data/configs/ut11
```

## ❌ Ограничения
- Нет подключения к live базе 1С
- Нет запуска кода 1С (нет платформы)
- УТ11 сейчас только метаданные (нужна полная выгрузка для .bsl кода)
- Синтакс-помощник не распакован (нужны .hbk файлы)

## 📋 TODO
- [ ] UT11 полная выгрузка (ZIP) — для .bsl кода
- [ ] .hbk файлы — для синтакс-помощника
- [ ] УНП ZIP — для API справочника
- [ ] ЭДО2 и ЭДО3 — проиндексировать
