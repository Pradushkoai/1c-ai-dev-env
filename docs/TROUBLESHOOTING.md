# Troubleshooting — решение типичных проблем

## Установка

### Проблема: `1c-ai: command not found`

**Причина:** пакет не установлен или PATH не настроен.

**Решение:**
```bash
pip install -e ".[dev,mcp]"
export PATH="$HOME/.local/bin:$PATH"
# Проверка:
which 1c-ai
```

### Проблема: `ModuleNotFoundError: No module named 'src'`

**Причина:** пакет не установлен в editable режиме.

**Решение:**
```bash
cd /path/to/1c-ai-dev-env
pip install -e .
```

### Проблема: `Java not found` / `BSL LS not available`

**Причина:** Java не установлена или BSL LS не скачан.

**Решение:**
```bash
# Установить Java 17+
sudo apt install openjdk-17-jre-headless

# Установить BSL LS
bash install.sh

# Проверка
1c-ai validate
# → ✅ bsl_ls
```

**Примечание:** BSL LS опционален. Без него работают все инструменты кроме `analyze_bsl`.

---

## Конфигурации

### Проблема: `config-registry.json пустой (0 configs)`

**Причина:** диск сброшен или данные не восстановлены.

**Решение:**
```bash
1c-ai data release-pull    # скачать data-package
1c-ai data autoload        # восстановить
1c-ai config list          # проверить
```

### Проблема: `build()` не создаёт unified-metadata-index.json

**Причина:** metadata_extractor.py не найден или упал.

**Решение:**
```bash
# Проверить что скрипт существует
ls scripts/metadata_extractor.py

# Запустить вручную
python3 scripts/metadata_extractor.py data/configs/ut11 derived/configs/ut11/unified-metadata-index.json

# Проверить ошибки
```

### Проблема: MCP tool `get_object_structure` возвращает `metadata-index not found`

**Причина:** индекс не построен.

**Решение:**
```bash
1c-ai config build --name ut11
# Это запустит все 4 парсера включая metadata_extractor
```

---

## Поиск

### Проблема: `search_1c_methods` возвращает пустой результат

**Причина:** нет platform index (`derived/platform/`).

**Решение:**
```bash
# Построить индекс платформы (нужен .hbk файл)
python3 scripts/build_syntax_helper_index.py /path/to/syntax.hbk derived/platform/
```

**Примечание:** `search_1c_methods` опционален. `search_code` (по конфигурации) работает без него.

### Проблема: `search_code` работает медленно при первом вызове

**Причина:** при первом вызове строится BM25 индекс (4-5 сек).

**Решение:** это нормально. Последующие вызовы — < 1 сек (индекс кэшируется).

---

## MCP / IDE

### Проблема: Cursor / Claude Desktop не видит MCP tools

**Решение:**
1. Проверить конфиг:
```bash
cat ~/.cursor/mcp.json
# или
cat ~/.config/Claude/claude_desktop_config.json
```

2. Проверить что сервер запускается:
```bash
1c-ai mcp serve
# должен ждать ввода (stdio)
```

3. Проверить список tools:
```bash
1c-ai mcp tools
# должно показать 27 tools
```

4. Перезапустить IDE после изменения конфига.

### Проблема: MCP tool возвращает `error: file not found`

**Причина:** путь указан относительно, а MCP не знает рабочий каталог.

**Решение:** используйте абсолютные пути:
```bash
# Неправильно:
audit_security(file_path='module.bsl')

# Правильно:
audit_security(file_path='/home/user/project/module.bsl')
# или
audit_security(file_path='data/configs/ut11/CommonModules/ОбменДокументы/Ext/Module.bsl')
```

---

## Производительность

### Проблема: Индексация УТ11 долго работает

**Ожидаемое время:**
- metadata_extractor: ~15 сек (7128 объектов, 35 типов)
- build_api_reference: ~30 сек (6729 модулей)
- skd_parser: ~5 сек (360 СКД-схем)
- form_analyzer: ~10 сек (3174 формы)
- **Итого: ~60 сек**

Если дольше 5 минут — проверьте:
```bash
# Размер данных
du -sh data/configs/ut11/
# Должно быть ~2 ГБ для полной XML выгрузки

# Если 200 МБ — это .cf извлечение (неполное)
```

### Проблема: `unified-metadata-index.json` слишком большой (200+ МБ)

**Решение:** это нормально для большой конфигурации (УТ11). Для уменьшения можно удалить `config_dump_info` секцию.

---

## Ошибки парсинга

### Проблема: `XML parse error` при индексации

**Решение:**
```bash
# Проверить конкретный файл
python3 -c "
from scripts.xml_parser import parse_xml
from pathlib import Path
root = parse_xml(Path('path/to/file.xml'))
print(f'OK: {root.tag}')
"

# Использовать lxml (быстрее и с лучшими сообщениями об ошибках)
pip install lxml
```

### Проблема: `metadata_extractor` пропускает объекты

**Решение:** проверьте что XML выгрузка полная:
```bash
# Должны быть эти директории:
ls data/configs/ut11/Catalogs/  # 385+ XML файлов
ls data/configs/ut11/Documents/ # 214+ XML файлов
ls data/configs/ut11/Roles/     # 641+ папок
```

Если директорий нет — это .cf извлечение (неполное). Нужна полная XML выгрузка Конфигуратора.

---

## GitHub

### Проблема: `data release-push` — `401 Unauthorized`

**Решение:** проверьте токен:
```bash
echo $GITHUB_TOKEN
# Должен быть <YOUR_GITHUB_TOKEN>...

# Проверить права:
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### Проблема: Push отклонён (`non-fast-forward`)

**Решение:**
```bash
git pull origin main
git push origin main
```
