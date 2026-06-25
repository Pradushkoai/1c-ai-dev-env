"""
Интеграционный тест: полный flow add_from_zip → build → analyze.

Создаёт синтетическую конфигурацию 1С (мини-выгрузку) в ZIP,
регистрирует её через ConfigManager, строит индексы (с моками subprocess),
и проверяет что все артефакты создались корректно.
"""
import json
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from src.project import Project
from src.services.path_manager import PathManager
from src.models.config_registry import ConfigurationRegistry


def _make_mini_config_zip(zip_path: Path) -> None:
    """
    Создать ZIP с мини-конфигурацией 1С:
    - Configuration.xml (свойства)
    - ConfigDumpInfo.xml (дамп метаданных)
    - Catalogs/Товары/Товары.xml (справочник)
    - CommonModules/Модуль/Модуль.bsl (общий модуль с экспортной функцией)
    """
    files = {
        "Configuration.xml": """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <Configuration>
    <Properties>
      <Name>МиниКонфигурация</Name>
      <Version>1.0.0</Version>
      <Vendor>Test</Vendor>
      <ScriptVariant>Russian</ScriptVariant>
    </Properties>
    <ChildObjects>
      <Subsystem>Основная</Subsystem>
    </ChildObjects>
  </Configuration>
</ConfigDumpInfo>
""",
        "ConfigDumpInfo.xml": """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <Metadata name="Catalog.Товары" id="cat-1"/>
  <Metadata name="Catalog.Товары.Form.ФормаСписка" id="form-1"/>
  <Metadata name="CommonModule.Модуль" id="mod-1"/>
</ConfigDumpInfo>
""",
        "Catalogs/Товары/Товары.xml": """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <Catalog>
    <Properties>
      <Name>Товары</Name>
      <Synonym><item><content>Товары</content></item></Synonym>
    </Properties>
  </Catalog>
</ConfigDumpInfo>
""",
        "CommonModules/Модуль.xml": """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <CommonModule>
    <Properties>
      <Name>Модуль</Name>
      <Server>true</Server>
      <Global>false</Global>
    </Properties>
  </CommonModule>
</ConfigDumpInfo>
""",
        "CommonModules/Модуль/Ext/Module.bsl": """// Поиск товара по коду.
//
// Параметры:
//  Код - Строка - код товара
//
// Возвращаемое значение:
//  СправочникСсылка - найденный товар
Функция НайтиТовар(Код) Экспорт
    Возврат Справочники.Товары.НайтиПоКоду(Код);
КонецФункции
""",
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


@pytest.fixture
def project_env(tmp_path, monkeypatch):
    """Создать изолированное окружение проекта во временной директории."""
    # Минимальная структура каталогов
    for d in ["data/configs", "data/archives", "derived/configs", "derived/platform",
              "tools/repos", "runtime", "scripts"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # paths.env
    (tmp_path / "runtime" / "paths.env").write_text(
        f"PROJECT_ROOT={tmp_path}\n", encoding="utf-8"
    )

    # Пустой реестр конфигураций
    (tmp_path / "runtime" / "config-registry.json").write_text(
        '{"version": "2.0", "configs": {}}', encoding="utf-8"
    )

    # .bsl-language-server.json
    (tmp_path / "runtime" / ".bsl-language-server.json").write_text(
        '{"language": "ru", "configurationRoot": "", "skipSupport": "filesystem"}',
        encoding="utf-8",
    )

    # Мокаем PathManager._detect_root чтобы он нашёл наш tmp_path
    monkeypatch.setattr(
        "src.services.path_manager.PathManager._detect_root",
        lambda self: tmp_path,
    )

    # Скрипты должны быть доступны — используем реальные scripts/ из setup/
    setup_scripts = Path(__file__).parent.parent / "scripts"
    if setup_scripts.exists():
        # Копируем только нужные скрипты
        for script_name in ["build_config_index_generic.py", "build_api_reference.py"]:
            src = setup_scripts / script_name
            if src.exists():
                shutil.copy(src, tmp_path / "scripts" / script_name)

    # Переключаем CWD в tmp_path — PathManager использует _detect_root
    monkeypatch.chdir(tmp_path)

    return tmp_path


def test_integration_add_build_analyze(project_env):
    """
    Полный flow:
    1. add_from_zip — распаковка и регистрация
    2. build — индекс метаданных + API-справочник
    3. Проверка артефактов (index.md, api-reference.md, api-reference.json)
    """
    tmp = project_env

    # === 1. Создаём ZIP с мини-конфигурацией ===
    zip_path = tmp / "mini_config.zip"
    _make_mini_config_zip(zip_path)

    # === 2. Project + add_from_zip ===
    project = Project()
    config = project.config_manager.add_from_zip("mini", zip_path, "Мини конфигурация")

    assert config.name == "mini"
    assert config.version == "1.0.0"
    assert config.status == "active"
    assert config.path.exists()
    assert (config.path / "Configuration.xml").exists()
    assert (config.path / "CommonModules" / "Модуль" / "Ext" / "Module.bsl").exists()

    # === 3. Build (с замоканным subprocess для внешних скриптов) ===
    # ConfigManager.build() вызывает:
    #   - build_config_index_generic.py (реально выполнится)
    #   - build_api_reference.py (реально выполнится)
    # subprocess.run в ConfigManager._build_metadata_index и _build_api_reference
    # Мы НЕ мокаем subprocess — пусть реальные скрипты выполнятся на синтетике.
    # Это и есть суть интеграционного теста.
    report = project.config_manager.build("mini")

    assert report["name"] == "mini"
    assert report["index"] is True
    assert report["api"] is True

    # === 4. Проверяем артефакты ===
    derived_dir = project.paths.config_derived_dir("mini")
    index_md = derived_dir / "index.md"
    api_md = derived_dir / "api-reference.md"
    api_json = derived_dir / "api-reference.json"

    assert index_md.exists(), "index.md не создан"
    assert api_md.exists(), "api-reference.md не создан"
    assert api_json.exists(), "api-reference.json не создан"

    # === 5. Проверяем содержимое ===
    index_content = index_md.read_text(encoding="utf-8")
    assert "Мини конфигурация" in index_content or "МиниКонфигурация" in index_content
    assert "Товары" in index_content
    assert "Модуль" in index_content

    api_content = api_md.read_text(encoding="utf-8")
    assert "НайтиТовар" in api_content
    assert "Экспорт" in api_content

    api_data = json.loads(api_json.read_text(encoding="utf-8"))
    # Должна быть информация о модуле с экспортной функцией
    assert isinstance(api_data, (list, dict))
    api_str = json.dumps(api_data, ensure_ascii=False)
    assert "НайтиТовар" in api_str

    # === 6. Проверяем что реестр обновился ===
    cfg = project.registry.get("mini")
    assert cfg is not None
    assert cfg.objects_count > 0  # Catalog + CommonModule = 2 объекта

    # === 7. BSL analyze (с моком subprocess, т.к. Java недоступна) ===
    bsl_path = config.path / "CommonModules" / "Модуль" / "Ext" / "Module.bsl"

    # Мокаем subprocess.run для BSL LS
    def fake_bsl_run(cmd, **kwargs):
        # cmd: [binary, -c, config, analyze, -s, src, -r, json, -o, output, -q]
        out_idx = cmd.index("-o")
        output_dir = Path(cmd[out_idx + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        # Создаём фейковый отчёт BSL LS
        fake_report = {
            "fileinfos": [
                {
                    "diagnostics": [
                        {
                            "code": "Typo",
                            "severity": "Info",
                            "message": "Возможная опечатка",
                            "range": {"start": {"line": 5}},
                        }
                    ]
                }
            ]
        }
        (output_dir / "bsl-json.json").write_text(
            json.dumps(fake_report, ensure_ascii=False), encoding="utf-8"
        )
        return MagicMock(returncode=0)

    with patch("src.services.bsl_analyzer.subprocess.run", side_effect=fake_bsl_run):
        result = project.bsl_analyzer.analyze(bsl_path)

    assert result.total == 1
    assert "Typo" in result.by_code


def test_integration_archive_and_restore(project_env):
    """
    Полный flow архивации и восстановления:
    add → build → archive → activate → build снова
    """
    tmp = project_env

    zip_path = tmp / "mini.zip"
    _make_mini_config_zip(zip_path)

    project = Project()
    project.config_manager.add_from_zip("mini", zip_path, "Мини")

    # Build
    project.config_manager.build("mini")
    derived_dir = project.paths.config_derived_dir("mini")
    assert (derived_dir / "index.md").exists()

    # Archive
    project.config_manager.archive("mini")
    cfg = project.registry.get("mini")
    assert cfg.status == "archived"
    assert cfg.archive.exists()
    assert cfg.path is None  # path становится None после архивации

    # Derived должен остаться (архивация не трогает индексы)
    assert (derived_dir / "index.md").exists()

    # Activate
    project.config_manager.activate("mini")
    cfg = project.registry.get("mini")
    assert cfg.status == "active"
    assert cfg.path.exists()
    assert (cfg.path / "Configuration.xml").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
