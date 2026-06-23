#!/bin/bash
# BSL Language Server — анализ с поддержкой diff (LSP post-write как в Hermes)
#
# Использование:
#   bsl-analyze.sh <path> [output_dir]              — обычный анализ
#   bsl-analyze.sh --baseline <path>                 — сохранить baseline
#   bsl-analyze.sh --diff <path>                     — показать только НОВЫЕ ошибки
#
# Пример workflow при рефакторинге:
#   1. bsl-analyze.sh --baseline file.bsl           → сохранили baseline
#   2. (редактируем file.bsl)
#   3. bsl-analyze.sh --diff file.bsl               → видим только что изменилось

# Пути из единого конфига
if [ -f "${0%/*}/../paths.env" ]; then
    source "${0%/*}/../paths.env"
fi
BSL_LS="${BSL_LS_BINARY:-$HOME/.local/bin/bsl-language-server}"
CONFIG="${BSL_LS_CONFIG:-$PWD/.bsl-language-server.json}"
BASELINE_DIR="${BASELINE_DIR:-/tmp/bsl_baseline}"
TMP_DIR="${TMP_DIR:-/tmp/bsl_tmp}"

mkdir -p "$BASELINE_DIR" "$TMP_DIR"

run_analysis() {
    local SRC="$1"
    local OUT="$2"
    mkdir -p "$OUT"
    rm -rf "$OUT"/*
    "$BSL_LS" -c "$CONFIG" analyze -s "$SRC" -r json -o "$OUT" -q 2>/dev/null
    echo "$OUT/bsl-json.json"
}

extract_diagnostics() {
    local JSON="$1"
    python3 -c "
import json, sys
with open('$JSON', 'rb') as f:
    data = json.loads(f.read().decode('utf-8'))
diags = set()
for fi in data.get('fileinfos', []):
    for d in fi.get('diagnostics', []):
        code = d.get('code', '?')
        line = d.get('range', {}).get('start', {}).get('line', 0)
        msg = d.get('message', '')[:150]
        diags.add(f'{code}|{line}|{msg}')
for d in sorted(diags):
    print(d)
" 2>/dev/null
}

print_summary() {
    local JSON="$1"
    python3 -c "
import json
with open('$JSON', 'rb') as f:
    data = json.loads(f.read().decode('utf-8'))
total = 0
by_code = {}
for fi in data.get('fileinfos', []):
    for d in fi.get('diagnostics', []):
        code = d.get('code', '?')
        by_code[code] = by_code.get(code, 0) + 1
        total += 1
print(f'Всего: {total}')
for code, count in sorted(by_code.items(), key=lambda x: -x[1])[:15]:
    print(f'  {count:4d}  {code}')
" 2>/dev/null
}

if [ "$1" == "--baseline" ]; then
    SRC="$2"
    [ -z "$SRC" ] && { echo "Укажи: bsl-analyze.sh --baseline <path>"; exit 1; }
    echo "=== Baseline для $SRC ==="
    JSON=$(run_analysis "$SRC" "$TMP_DIR/baseline")
    extract_diagnostics "$JSON" > "$BASELINE_DIR/diagnostics.txt"
    print_summary "$JSON"
    echo ""
    echo "✅ Baseline: $(wc -l < "$BASELINE_DIR/diagnostics.txt") уникальных диагностик"
    echo "Теперь: bsl-analyze.sh --diff $SRC"

elif [ "$1" == "--diff" ]; then
    SRC="$2"
    [ -z "$SRC" ] && { echo "Укажи: bsl-analyze.sh --diff <path>"; exit 1; }
    [ ! -f "$BASELINE_DIR/diagnostics.txt" ] && { echo "❌ Нет baseline. Сначала: bsl-analyze.sh --baseline $SRC"; exit 1; }
    
    echo "=== Анализ после редактирования ==="
    JSON=$(run_analysis "$SRC" "$TMP_DIR/after")
    extract_diagnostics "$JSON" > "$BASELINE_DIR/after.txt"
    
    echo ""
    print_summary "$JSON"
    
    echo ""
    echo "=== 🆕 НОВЫЕ (появились после редактирования) ==="
    NEW=$(comm -13 <(sort "$BASELINE_DIR/diagnostics.txt") <(sort "$BASELINE_DIR/after.txt"))
    if [ -n "$NEW" ]; then
        echo "$NEW" | head -20
    else
        echo "  (нет новых)"
    fi
    
    echo ""
    echo "=== ✅ ИСПРАВЛЕННЫЕ (исчезли после редактирования) ==="
    FIXED=$(comm -23 <(sort "$BASELINE_DIR/diagnostics.txt") <(sort "$BASELINE_DIR/after.txt"))
    if [ -n "$FIXED" ]; then
        echo "$FIXED" | head -10
    else
        echo "  (нет исправленных)"
    fi
    
    # Обновляем baseline
    cp "$BASELINE_DIR/after.txt" "$BASELINE_DIR/diagnostics.txt"
    echo ""
    echo "✅ Baseline обновлён"

else
    SRC="$1"
    OUT="${2:-/tmp/bsl_report_$(date +%s)}"
    [ -z "$SRC" ] && {
        echo "Использование:"
        echo "  bsl-analyze.sh <path> [output]        — анализ"
        echo "  bsl-analyze.sh --baseline <path>      — сохранить baseline"
        echo "  bsl-analyze.sh --diff <path>          — только новые ошибки"
        exit 1
    }
    echo "=== BSL analysis: $SRC ==="
    JSON=$(run_analysis "$SRC" "$OUT")
    echo ""
    print_summary "$JSON"
    echo ""
    echo "Отчёт: $JSON"
fi
