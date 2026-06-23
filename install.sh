#!/bin/bash
# 1C AI Development Environment — установщик
# Использование: ./install.sh

set -e

PROJECT_DIR="${PROJECT_DIR:-/home/z/my-project}"
SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 1C AI Development Environment ==="
echo "Установка в: $PROJECT_DIR"
echo ""

# 1. Проверка зависимостей
echo "=== 1/6: Проверка зависимостей ==="
command -v python3 >/dev/null 2>&1 || { echo "❌ Нужен Python 3.10+"; exit 1; }
command -v java >/dev/null 2>&1 || { echo "❌ Нужен Java 17+"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "❌ Нужен git"; exit 1; }
echo "✅ Python: $(python3 --version)"
echo "✅ Java: $(java --version 2>&1 | head -1)"
echo "✅ git: $(git --version)"
echo ""

# 2. Python зависимости
echo "=== 2/6: Python зависимости ==="
pip3 install -q -r "$SETUP_DIR/requirements.txt" 2>&1 | tail -3
echo "✅ Установлено: v8unpack, fastembed, qdrant-client"
echo ""

# 3. Копирование скриптов
echo "=== 3/6: Скрипты ==="
mkdir -p "$PROJECT_DIR/scripts"
cp "$SETUP_DIR/scripts/"* "$PROJECT_DIR/scripts/" 2>/dev/null || true
chmod +x "$PROJECT_DIR/scripts/"*.sh 2>/dev/null || true
echo "✅ Скрипты скопированы: $(ls "$PROJECT_DIR/scripts/" | wc -l) файлов"
echo ""

# 4. Конфиги
echo "=== 4/6: Конфиги ==="
cp "$SETUP_DIR/configs/bsl-language-server.json" "$PROJECT_DIR/.bsl-language-server.json" 2>/dev/null || true
echo "✅ BSL LS конфиг установлен"
echo ""

# 5. Git репозитории
echo "=== 5/6: Git репозитории ==="
mkdir -p "$PROJECT_DIR/syntax"
REPOS=$(python3 -c "
import json
with open('$SETUP_DIR/manifest.json') as f:
    m = json.load(f)
for r in m['git_repositories']:
    print(f\"{r['name']} {r['url']}\")
")
echo "$REPOS" | while read name url; do
    if [ -d "$PROJECT_DIR/syntax/$name" ]; then
        echo "  ⏭️  $name (уже есть)"
    else
        echo "  ⬇️  $name..."
        git clone --depth 1 "$url" "$PROJECT_DIR/syntax/$name" 2>/dev/null || echo "  ⚠️  $name — ошибка"
    fi
done
echo ""

# 6. BSL Language Server
echo "=== 6/6: BSL Language Server ==="
if [ -f ~/.local/bin/bsl-language-server ]; then
    echo "  ⏭️  Уже установлен: $(~/.local/bin/bsl-language-server --version 2>/dev/null | grep version)"
else
    echo "  ⬇️  Скачивание BSL LS v1.0.1..."
    BSL_URL=$(python3 -c "
import json
with open('$SETUP_DIR/manifest.json') as f:
    m = json.load(f)
print(m['bsl_language_server']['url'])
")
    curl -sL "$BSL_URL" -o /tmp/bsl-ls.zip
    mkdir -p ~/.local/share/bsl-language-server
    unzip -q /tmp/bsl-ls.zip -d ~/.local/share/bsl-language-server/
    ln -sf ~/.local/share/bsl-language-server/bsl-language-server/bin/bsl-language-server ~/.local/bin/bsl-language-server
    chmod +x ~/.local/share/bsl-language-server/bsl-language-server/bin/bsl-language-server
    rm /tmp/bsl-ls.zip
    echo "  ✅ Установлен: $(~/.local/bin/bsl-language-server --version 2>/dev/null | grep version)"
fi
echo ""

# Финал
echo "=== Установка завершена! ==="
echo ""
echo "Что установлено:"
echo "  ✅ Python: v8unpack, fastembed, qdrant-client"
echo "  ✅ Скрипты: $(ls "$PROJECT_DIR/scripts/" | wc -l) файлов"
echo "  ✅ Git репозитории: $(ls "$PROJECT_DIR/syntax/" 2>/dev/null | wc -l) шт"
echo "  ✅ BSL Language Server"
echo ""
echo "Следующие шаги:"
echo "  1. Положи ZIP выгрузку конфигурации в $PROJECT_DIR/upload/"
echo "  2. Положи .hbk файлы синтакс-помощника в $PROJECT_DIR/upload/"
echo "  3. Запусти: $PROJECT_DIR/scripts/add_config.sh <file_id> <name> \"<title>\""
echo "  4. Распакуй .hbk: python3 $PROJECT_DIR/scripts/hbk_extractor.py 'upload/*.hbk' syntax-helper"
echo "  5. Построй индекс: python3 $PROJECT_DIR/scripts/build_syntax_helper_index.py"
echo "  6. Построй поиск: python3 $PROJECT_DIR/scripts/fast_search_1c.py build"
echo ""
echo "Готов к работе!"
