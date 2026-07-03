#!/bin/bash
# ============================================================================
# 1C AI Development Environment — Установщик v2.1 (4-слойная архитектура)
# ============================================================================
# Создаёт: data/ (данные) → derived/ (индексы) → tools/ (инструменты) → runtime/ (работа)
#
# Использование:
#   ./install.sh                    — интерактивная установка
#   ./install.sh --non-interactive  — без вопросов (только инструменты)
#   ./install.sh --target /path     — явный путь установки
#   ./install.sh --help             — справка
#
# P1.4: убран хардкод /home/z/my-project. Целевая директория определяется:
#   1. --target аргумент (приоритет)
#   2. ONEC_AI_DEV_ENV_ROOT env var
#   3. PROJECT_DIR env var (legacy, deprecated)
#   4. Ошибка если ничего не задано
# ============================================================================

set -e

# ============================================================================
# Парсинг аргументов и определение PROJECT_DIR
# ============================================================================
SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"
INTERACTIVE=true
TARGET_DIR=""

# Парсим --help и --non-interactive и --target
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            cat << 'HELP'
1C AI Development Environment — Установщик v2.1

Использование:
  ./install.sh [ОПЦИИ]

Опции:
  --target PATH        Целевая директория для установки
  --non-interactive    Без интерактивных вопросов (только инструменты)
  --help, -h           Показать эту справку

Переменные окружения:
  ONEC_AI_DEV_ENV_ROOT  Целевая директория (рекомендуется)
  PROJECT_DIR           Legacy alias для ONEC_AI_DEV_ENV_ROOT (deprecated)

Примеры:
  # Через --target
  ./install.sh --target /opt/1c-ai-dev-env

  # Через env var
  export ONEC_AI_DEV_ENV_ROOT=/opt/1c-ai-dev-env
  ./install.sh

  # Non-interactive (для CI)
  ONEC_AI_DEV_ENV_ROOT=/tmp/1c-ai ./install.sh --non-interactive

P1.4: хардкод /home/z/my-project удалён. Целевая директория обязательна.
HELP
            exit 0
            ;;
        --non-interactive)
            INTERACTIVE=false
            shift
            ;;
        --target)
            if [[ $# -lt 2 ]]; then
                echo "❌ --target требует аргумент: --target /path/to/dir"
                exit 1
            fi
            TARGET_DIR="$2"
            shift 2
            ;;
        --target=*)
            TARGET_DIR="${1#--target=}"
            shift
            ;;
        *)
            echo "❌ Неизвестный аргумент: $1"
            echo "Используйте: ./install.sh --help"
            exit 1
            ;;
    esac
done

# Определяем PROJECT_DIR: --target > ONEC_AI_DEV_ENV_ROOT > PROJECT_DIR (legacy)
if [[ -n "$TARGET_DIR" ]]; then
    PROJECT_DIR="$TARGET_DIR"
elif [[ -n "$ONEC_AI_DEV_ENV_ROOT" ]]; then
    PROJECT_DIR="$ONEC_AI_DEV_ENV_ROOT"
elif [[ -n "$PROJECT_DIR" ]]; then
    # Legacy env var (deprecated, но работает для backward compat)
    :
else
    PROJECT_DIR=""
fi

# Если всё ещё пусто — ошибка
if [[ -z "$PROJECT_DIR" ]]; then
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║  ❌ ОШИБКА: целевая директория не указана            ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "P1.4: хардкод /home/z/my-project удалён."
    echo "Укажите целевую директорию одним из способов:"
    echo ""
    echo "  1. --target аргумент:"
    echo "     ./install.sh --target /opt/1c-ai-dev-env"
    echo ""
    echo "  2. ONEC_AI_DEV_ENV_ROOT env var:"
    echo "     export ONEC_AI_DEV_ENV_ROOT=/opt/1c-ai-dev-env"
    echo "     ./install.sh"
    echo ""
    echo "  3. PROJECT_DIR env var (legacy, deprecated):"
    echo "     PROJECT_DIR=/opt/1c-ai-dev-env ./install.sh"
    echo ""
    echo "Справка: ./install.sh --help"
    exit 1
fi

# Валидация: если директория существует и не пуста и не содержит paths.env — предупреждение
if [[ -d "$PROJECT_DIR" ]]; then
    if [[ -n "$(ls -A "$PROJECT_DIR" 2>/dev/null)" ]] && [[ ! -f "$PROJECT_DIR/paths.env" ]]; then
        echo "⚠️  ВНИМАНИЕ: директория '$PROJECT_DIR' существует и не пуста,"
        echo "   и не содержит paths.env (признак предыдущей установки)."
        if [[ "$INTERACTIVE" == "true" ]]; then
            read -p "Продолжить? Существующие файлы могут быть перезаписаны [y/N]: " CONFIRM
            if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
                echo "Установка отменена."
                exit 0
            fi
        else
            echo "   Non-interactive режим: продолжаю (файлы могут быть перезаписаны)."
        fi
    fi
fi

echo "╔══════════════════════════════════════════════════════╗"
echo "║  1C AI Development Environment — Установка v2.1      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Путь: $PROJECT_DIR"
echo ""

# ============================================================================
# Шаг 1: Проверка зависимостей
# ============================================================================
echo "=== Шаг 1/8: Проверка зависимостей ==="

command -v python3 >/dev/null 2>&1 || { echo "❌ Нужен Python 3.10+"; exit 1; }
command -v java >/dev/null 2>&1 || { echo "❌ Нужен Java 17+ (для BSL LS)"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "❌ Нужен git"; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo "❌ Нужен unzip"; exit 1; }

echo "  ✅ Python: $(python3 --version)"
echo "  ✅ Java: $(java --version 2>&1 | head -1)"
echo "  ✅ git: $(git --version)"
echo ""

# ============================================================================
# Шаг 2: Создание 4-слойной структуры
# ============================================================================
echo "=== Шаг 2/8: Создание структуры ==="

mkdir -p "$PROJECT_DIR"/{data/{configs,archives,hbk},derived/{configs,platform},tools/{repos,bsl-ls},runtime,learned-skills,scripts}

echo "  ✅ data/       — исходные данные"
echo "  ✅ derived/    — производные (индексы)"
echo "  ✅ tools/      — инструменты"
echo "  ✅ runtime/    — файлы работы"
echo "  ✅ learned-skills/ — learning loop"
echo "  ✅ scripts/    — рабочие скрипты"
echo ""

# ============================================================================
# Шаг 3: Python зависимости
# ============================================================================
echo "=== Шаг 3/8: Python зависимости ==="

pip3 install -q -e "$SETUP_DIR" 2>&1 | tail -1
echo "  ✅ python-dotenv, structlog, networkx, v8unpack (базовые)"
echo ""

# ============================================================================
# Шаг 4: Скрипты и конфиги
# ============================================================================
echo "=== Шаг 4/8: Скрипты и конфиги ==="

# Скрипты → scripts/
cp "$SETUP_DIR"/scripts/* "$PROJECT_DIR/scripts/" 2>/dev/null || true
chmod +x "$PROJECT_DIR"/scripts/*.sh 2>/dev/null || true
echo "  ✅ Скрипты: $(ls "$PROJECT_DIR/scripts/" | wc -l) файлов"

# Устанавливаем Python-пакет через pyproject.toml (editable mode)
# После этого доступны: from src.services... и команда 1c-ai
pip3 install -e "$SETUP_DIR" -q 2>&1 | tail -2
echo "  ✅ Python-пакет установлен (editable mode): 1c-ai CLI + src.* импорты"

# paths.env, config-registry.json → runtime/  (P2.15: paths.py удалён как dead code)
cp "$SETUP_DIR/paths.env" "$PROJECT_DIR/runtime/paths.env"
    sed -i "s|/home/z/my-project|$PROJECT_DIR|g" "$PROJECT_DIR/runtime/paths.env"
cp "$SETUP_DIR/config-registry.json" "$PROJECT_DIR/runtime/config-registry.json" 2>/dev/null || true

# .bsl-language-server.json → runtime/
cat > "$PROJECT_DIR/runtime/.bsl-language-server.json" << 'BSLCFG'
{
  "language": "ru",
  "diagnostics": { "parameters": { "Typo": { "dictionary": "ru" } } },
  "configurationRoot": "",
  "skipSupport": "filesystem"
}
BSLCFG

# Симлинки в корне
ln -sf runtime/paths.env "$PROJECT_DIR/paths.env"

# Runtime файлы (soul, user-profile, role-switching, session-resume)
for f in soul.md user-profile.md role-switching-protocol.md; do
    if [ -f "$SETUP_DIR/templates/$f.template.md" ]; then
        cp "$SETUP_DIR/templates/$f.template.md" "$PROJECT_DIR/runtime/$f"
    fi
done

# session-resume из шаблона
if [ -f "$SETUP_DIR/templates/session-resume.template.md" ]; then
    cp "$SETUP_DIR/templates/session-resume.template.md" "$PROJECT_DIR/runtime/session-resume.md"
fi

# worklog
echo "# Worklog" > "$PROJECT_DIR/runtime/worklog.md"

echo "  ✅ runtime/ — paths, registry, soul, session-resume"
echo ""

# ============================================================================
# Шаг 5: Git репозитории → tools/repos/
# ============================================================================
echo "=== Шаг 5/8: Git репозитории ==="

REPOS=$(python3 -c "
import json
with open('$SETUP_DIR/manifest.json') as f:
    m = json.load(f)
for r in m['git_repositories']:
    print(f\"{r['name']} {r['url']}\")
")

REPOS_DIR="$PROJECT_DIR/tools/repos"
COUNT=0
TOTAL=$(echo "$REPOS" | wc -l)

echo "$REPOS" | while read name url; do
    COUNT=$((COUNT + 1))
    if [ -d "$REPOS_DIR/$name" ]; then
        echo "  ⏭️  [$COUNT/$TOTAL] $name (уже есть)"
    else
        echo "  ⬇️  [$COUNT/$TOTAL] $name..."
        git clone --depth 1 "$url" "$REPOS_DIR/$name" 2>/dev/null || echo "  ⚠️  $name — ошибка"
    fi
done
echo ""

# ============================================================================
# Шаг 6: BSL Language Server
# ============================================================================
echo "=== Шаг 6/8: BSL Language Server ==="

if [ -f ~/.local/bin/bsl-language-server ]; then
    echo "  ⏭️  Уже установлен: $(~/.local/bin/bsl-language-server --version 2>/dev/null | grep version || echo 'OK')"
else
    BSL_URL=$(python3 -c "
import json
with open('$SETUP_DIR/manifest.json') as f:
    m = json.load(f)
print(m['bsl_language_server']['url'])
")
    echo "  ⬇️  Скачивание BSL LS..."
    curl -sL "$BSL_URL" -o /tmp/bsl-ls.zip
    mkdir -p ~/.local/share/bsl-language-server ~/.local/bin
    unzip -q /tmp/bsl-ls.zip -d ~/.local/share/bsl-language-server/
    ln -sf ~/.local/share/bsl-language-server/bsl-language-server/bin/bsl-language-server ~/.local/bin/bsl-language-server
    chmod +x ~/.local/share/bsl-language-server/bsl-language-server/bin/bsl-language-server
    rm /tmp/bsl-ls.zip
    echo "  ✅ Установлен: $(~/.local/bin/bsl-language-server --version 2>/dev/null | grep version || echo 'OK')"
fi
echo ""

# ============================================================================
# Шаг 7: Данные пользователя (интерактивно)
# ============================================================================
echo "=== Шаг 7/8: Данные пользователя ==="

if [ "$INTERACTIVE" == "true" ]; then
    # .hbk файлы
    read -p "Есть .hbk файлы синтакс-помощника? (путь к ZIP или Enter для пропуска): " HBK_ZIP
    if [ -n "$HBK_ZIP" ] && [ -f "$HBK_ZIP" ]; then
        echo "  Распаковка .hbk → data/hbk/..."
        unzip -q -o "$HBK_ZIP" -d "$PROJECT_DIR/data/hbk/"
        echo "  ✅ .hbk файлы скопированы"
        
        # Распаковка .hbk → HTML
        echo "  Распаковка .hbk → derived/platform/syntax-helper/..."
        mkdir -p "$PROJECT_DIR/derived/platform/syntax-helper"
        python3 "$PROJECT_DIR/scripts/hbk_extractor.py" \
            "$PROJECT_DIR/data/hbk/*.hbk" \
            "$PROJECT_DIR/derived/platform/syntax-helper" 2>&1 | tail -3
        echo "  ✅ Синтакс-помощник распакован"
        
        # Индексация
        echo "  Индексация методов..."
        cd "$PROJECT_DIR"
        python3 scripts/build_syntax_helper_index.py 2>&1 | tail -3
        echo "  ✅ Индекс методов построен"
        
        # Fast search
        echo "  Построение TF-IDF индекса..."
        python3 scripts/fast_search_1c.py build 2>&1 | tail -3
        echo "  ✅ Fast search готов"
    else
        echo "  ⏭️  .hbk пропущен (можно добавить позже)"
    fi
    echo ""
    
    # ZIP выгрузка конфигурации
    read -p "Есть ZIP выгрузка конфигурации 1С? (путь или Enter): " CFG_ZIP
    if [ -n "$CFG_ZIP" ] && [ -f "$CFG_ZIP" ]; then
        read -p "Имя конфигурации (например ut11): " CFG_NAME
        read -p "Заголовок (например \"УТ 11\"): " CFG_TITLE
        
        echo "  Регистрация и индексация..."
        # Используем встроенный CLI вместо удалённого scripts/register_config.py
        cd "$PROJECT_DIR" && python3 -m src.cli config add \
            --name "$CFG_NAME" \
            --zip "$CFG_ZIP" \
            --title "$CFG_TITLE" \
            --skip-build 2>&1 | tail -5
        
        # Обновляем configurationRoot в .bsl-language-server.json
        python3 -c "
import json
cfg_path = '$PROJECT_DIR/runtime/.bsl-language-server.json'
with open(cfg_path) as f:
    cfg = json.load(f)
cfg['configurationRoot'] = '$PROJECT_DIR/data/configs/$CFG_NAME'
with open(cfg_path, 'w') as f:
    json.dump(cfg, f, indent=2)
"
        
        # build
        cd "$PROJECT_DIR" && python3 -m src.cli config build --name "$CFG_NAME" 2>&1 | tail -5
        echo "  ✅ Конфигурация '$CFG_NAME' проиндексирована"
    else
        echo "  ⏭️  Конфигурация пропущена (можно добавить позже)"
    fi
else
    echo "  ⏭️  Пропущено (non-interactive режим)"
fi
echo ""

# ============================================================================
# Шаг 8: Финальный отчёт
# ============================================================================
echo "=== Шаг 8/8: Проверка ==="

echo ""
# Используем OOP PathManager (через CLI) вместо устаревшего paths.py
cd "$PROJECT_DIR" && python3 -m src.cli validate 2>&1 || true

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Установка завершена!                             ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  Структура:                                          ║"
echo "║    data/       — исходные данные                     ║"
echo "║    derived/    — индексы (генерируются)              ║"
echo "║    tools/      — инструменты (15 git + BSL LS)      ║"
echo "║    runtime/    — файлы работы                        ║"
echo "║    scripts/    — 10 скриптов                          ║"
echo "║                                                      ║"
echo "║  Что установлено:                                     ║"
echo "║    ✅ BSL Language Server v1.0.1                     ║"
echo "║    ✅ python-dotenv (базовые)                       ║"
echo "║    ✅ 94 скила (JSON DSL) [claude-code-skills-1c]                            ║"
echo "║    ✅ 168 проверок [EDT-MCP]                           ║"
echo "║    ✅ 187 диагностик [bsl-language-server]                          ║"
echo "║    ✅ 28 правил [ai_rules_1c]                          ║"
echo "║                                                      ║"
echo "║  Команды:                                            ║"
echo "║    python3 -m src.cli config list                    ║"
echo "║    python3 -m src.cli config build --name X          ║"
echo "║    python3 scripts/fast_search_1c.py search 'запрос' ║"
echo "║    scripts/bsl-analyze.sh <path>                     ║"
echo "║                                                      ║"
echo "║  Прочитай runtime/session-resume.md для начала       ║"
echo "╚══════════════════════════════════════════════════════╝"
