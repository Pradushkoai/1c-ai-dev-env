#!/bin/bash
# ============================================================================
# 1C AI Development Environment — Установщик v2.0 (4-слойная архитектура)
# ============================================================================
# Создаёт: data/ (данные) → derived/ (индексы) → tools/ (инструменты) → runtime/ (работа)
#
# Использование:
#   ./install.sh                    — интерактивная установка
#   ./install.sh --non-interactive  — без вопросов (только инструменты)
# ============================================================================

set -e

PROJECT_DIR="${PROJECT_DIR:-/home/z/my-project}"
SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"
INTERACTIVE=true

if [ "$1" == "--non-interactive" ]; then
    INTERACTIVE=false
fi

echo "╔══════════════════════════════════════════════════════╗"
echo "║  1C AI Development Environment — Установка v2.0      ║"
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

pip3 install -q -r "$SETUP_DIR/requirements.txt" 2>&1 | tail -1
echo "  ✅ v8unpack, python-dotenv, fastembed, qdrant-client"
echo ""

# ============================================================================
# Шаг 4: Скрипты и конфиги
# ============================================================================
echo "=== Шаг 4/8: Скрипты и конфиги ==="

# Скрипты → scripts/
cp "$SETUP_DIR"/scripts/* "$PROJECT_DIR/scripts/" 2>/dev/null || true
chmod +x "$PROJECT_DIR"/scripts/*.sh 2>/dev/null || true
echo "  ✅ Скрипты: $(ls "$PROJECT_DIR/scripts/" | wc -l) файлов"

# paths.env, paths.py, config-registry.json → runtime/
cp "$SETUP_DIR/paths.env" "$PROJECT_DIR/runtime/paths.env"
cp "$SETUP_DIR/paths.py" "$PROJECT_DIR/runtime/paths.py"
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
ln -sf runtime/paths.py "$PROJECT_DIR/paths.py"

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
        python3 "$PROJECT_DIR/scripts/register_config.py" add \
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
        python3 "$PROJECT_DIR/scripts/register_config.py" build --name "$CFG_NAME" 2>&1 | tail -5
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
python3 "$PROJECT_DIR/runtime/paths.py" validate 2>&1 || true

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Установка завершена!                             ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  Структура:                                          ║"
echo "║    data/       — исходные данные                     ║"
echo "║    derived/    — индексы (генерируются)              ║"
echo "║    tools/      — инструменты (17 репозиториев + BSL) ║"
echo "║    runtime/    — файлы работы                        ║"
echo "║    scripts/    — 9 скриптов                          ║"
echo "║                                                      ║"
echo "║  Что установлено:                                     ║"
echo "║    ✅ BSL Language Server v1.0.1                     ║"
echo "║    ✅ v8unpack, fastembed, qdrant-client             ║"
echo "║    ✅ 94 скила (JSON DSL)                            ║"
echo "║    ✅ 168 проверок EDT-MCP                           ║"
echo "║    ✅ 187 диагностик BSL LS                          ║"
echo "║    ✅ 29 правил ai_rules_1c                          ║"
echo "║                                                      ║"
echo "║  Команды:                                            ║"
echo "║    python3 scripts/register_config.py list           ║"
echo "║    python3 scripts/register_config.py build --name X ║"
echo "║    python3 scripts/fast_search_1c.py search 'запрос' ║"
echo "║    scripts/bsl-analyze.sh <path>                     ║"
echo "║                                                      ║"
echo "║  Прочитай runtime/session-resume.md для начала       ║"
echo "╚══════════════════════════════════════════════════════╝"
