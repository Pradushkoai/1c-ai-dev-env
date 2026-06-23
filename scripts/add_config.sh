#!/bin/bash
# Скрипт для добавления новой конфигурации 1С в проект
#
# Использование:
#   ./add_config.sh <google_drive_file_id> <config_name> "<config_title>"
#
# Пример:
#   ./add_config.sh 1ABCdef... unp "Управление нашей фирмой"
#
# Что делает:
# 1. Скачивает ZIP с Google Drive через gdown
# 2. Распаковывает во временную папку
# 3. Строит индекс в /home/z/my-project/indexes/<name>-index.md
# 4. Перемещает ZIP в /home/z/my-project/archives/<name>_full.zip
# 5. Удаляет временную папку
# 6. Выводит инструкцию по обновлению project-context.md

set -e

# Проверка аргументов
if [ "$#" -lt 3 ]; then
    echo "❌ Использование: $0 <google_drive_file_id> <config_name> <config_title>"
    echo ""
    echo "Пример:"
    echo "  $0 1ABCdef... unp \"Управление нашей фирмой\""
    exit 1
fi

FILE_ID="$1"
CONFIG_NAME="$2"
CONFIG_TITLE="$3"

# Пути
# Пути из единого конфига
if [ -f "${0%/*}/../paths.env" ]; then
    source "${0%/*}/../paths.env"
fi
PROJECT_DIR="${PROJECT_ROOT:-/home/z/my-project}"
ARCHIVES_DIR="${PROJECT_DIR}/archives"
INDEXES_DIR="${PROJECT_DIR}/indexes"
TEMP_DIR="/tmp/config_${CONFIG_NAME}_$$"
ZIP_FILE="${ARCHIVES_DIR}/${CONFIG_NAME}_full.zip"
INDEX_FILE="${INDEXES_DIR}/${CONFIG_NAME}-index.md"

# Создаём директории
mkdir -p "$ARCHIVES_DIR" "$INDEXES_DIR"

echo "=== Добавление конфигурации: $CONFIG_TITLE ==="
echo "Имя: $CONFIG_NAME"
echo "Google Drive File ID: $FILE_ID"
echo ""

# Шаг 1: Скачать ZIP
echo "=== Шаг 1/5: Скачивание ZIP с Google Drive ==="
if [ -f "$ZIP_FILE" ]; then
    echo "✅ ZIP уже существует: $ZIP_FILE ($(du -h "$ZIP_FILE" | cut -f1))"
else
    echo "Скачиваю..."
    gdown "https://drive.google.com/uc?id=${FILE_ID}" -O "$ZIP_FILE"
    if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
        echo "❌ Не удалось скачать ZIP"
        exit 1
    fi
    echo "✅ Скачан: $(du -h "$ZIP_FILE" | cut -f1)"
fi
echo ""

# Шаг 2: Распаковать во временную папку
echo "=== Шаг 2/5: Распаковка ==="
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"
unzip -q "$ZIP_FILE" -d "$TEMP_DIR"

FILE_COUNT=$(find "$TEMP_DIR" -type f | wc -l)
echo "✅ Распаковано: $FILE_COUNT файлов"
echo ""

# Шаг 3: Построить индекс
echo "=== Шаг 3/5: Построение индекса ==="
python3 "${PROJECT_DIR}/scripts/build_config_index_generic.py" \
    "$TEMP_DIR" \
    "$INDEX_FILE" \
    "$CONFIG_TITLE"

if [ ! -f "$INDEX_FILE" ]; then
    echo "❌ Не удалось построить индекс"
    rm -rf "$TEMP_DIR"
    exit 1
fi
echo "✅ Индекс: $INDEX_FILE ($(du -h "$INDEX_FILE" | cut -f1))"
echo ""

# Шаг 4: Удалить временную папку
echo "=== Шаг 4/5: Очистка временной папки ==="
rm -rf "$TEMP_DIR"
echo "✅ Временная папка удалена"
echo ""

# Шаг 5: Сводка
echo "=== Шаг 5/5: Сводка ==="
echo ""
echo "✅ Конфигурация «$CONFIG_TITLE» добавлена"
echo ""
echo "Артефакты:"
echo "  ZIP:    $ZIP_FILE ($(du -h "$ZIP_FILE" | cut -f1))"
echo "  Индекс: $INDEX_FILE ($(du -h "$INDEX_FILE" | cut -f1))"
echo ""
echo "📊 Статистика из индекса:"
grep -E "Всего объектов метаданных|^## 2\.|^| " "$INDEX_FILE" | head -10
echo ""
echo "📝 Что нужно сделать вручную:"
echo "  1. Добавить запись о конфигурации в ${PROJECT_DIR}/project-context.md"
echo "  2. Обновить список конфигов в ${PROJECT_DIR}/session-resume.md"
echo ""
echo "🚀 Чтобы начать работу с этой конфигурацией:"
echo "  unzip -q $ZIP_FILE -d ${PROJECT_DIR}/config-${CONFIG_NAME}/"
echo ""
