"""
Единый CLI для всех команд проекта.

Usage:
    1c-ai config list
    1c-ai config add --name ut11 --zip ut11.zip --title "УТ 11"
    1c-ai config build --name ut11
    1c-ai config build-all
    1c-ai bsl analyze <path>
    1c-ai bsl baseline <path>
    1c-ai bsl diff <path>
    1c-ai validate
    1c-ai search "найти по коду"
    1c-ai standards <path>            # проверка .bsl на стандарты 1С
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# P2.1: BSL команды вынесены в src/cli_commands/bsl.py
from .cli_commands.bsl import cmd_bsl_analyze, cmd_bsl_baseline, cmd_bsl_diff, cmd_validate

# P2.1: config команды вынесены в src/cli_commands/config.py
from .cli_commands.config import (
    cmd_config_add,
    cmd_config_build,
    cmd_config_build_all,
    cmd_config_list,
)
from .cli_commands.inspect import (  # noqa: F401
    _inspect_cf,
    _inspect_form,
    _inspect_meta,
    _inspect_mxl,
    _inspect_role,
    _inspect_skd,
    _inspect_subsystem,
    cmd_inspect,
)

# P2.1: search/solve/standards/backup команды вынесены в cli_commands/
from .cli_commands.search import cmd_call_graph, cmd_search, cmd_search_code
from .cli_commands.solve import (  # noqa: F401
    _solve_check,
    _solve_context,
    cmd_backup,
    cmd_solve,
    cmd_standards,
)
from .cli_commands.tools import (  # noqa: F401
    cmd_cfe,
    cmd_depgraph,
    cmd_dsl,
    cmd_epf_factory,
    cmd_openspec,
    cmd_session,
    cmd_skd_trace,
)
from .project import Project


def cmd_mcp(project: Project, args: argparse.Namespace) -> None:
    """Управление MCP-сервером."""
    if args.mcp_command == "serve":
        try:
            import asyncio

            from .mcp_server import run_mcp_server

            asyncio.run(run_mcp_server())
        except ImportError as e:
            print(f"❌ MCP SDK не установлен: {e}")
            print("   Установите: pip install mcp")
            sys.exit(1)
    elif args.mcp_command == "tools":
        # Выводим список tools — парсим из mcp_server.py
        import re

        mcp_src = Path(__file__).parent / "mcp_server.py"
        src = mcp_src.read_text(encoding="utf-8")
        # Извлекаем все name="..." из types.Tool( блоков
        tools = re.findall(r'name="([a-z_0-9]+)"', src)
        # Убираем дубликаты сохраняя порядок
        seen = set()
        unique_tools = []
        for t in tools:
            if t not in seen:
                seen.add(t)
                unique_tools.append(t)
        print(f"MCP tools ({len(unique_tools)}):")
        print()
        for t in unique_tools:
            print(f"  • {t}")


def cmd_data(project: Project, args: argparse.Namespace) -> None:
    """Управление данными проекта (persistence)."""
    from .services.data_package import DataPackage

    dp = DataPackage(project.paths)

    if args.data_command == "save-pkg":
        output = Path(args.output) if args.output else dp.default_package_path
        if not output.is_absolute():
            output = project.paths.root / output

        print(f"Сохранение данных в: {output}")
        print(f"  Включая raw (data/): {'да' if args.include_raw else 'нет'}")
        print("  Включая derived: да")
        print()

        result = dp.save(
            output,
            include_raw=args.include_raw,
            include_derived=True,
            description=args.description or "",
        )

        size_mb = result.stat().st_size / 1024 / 1024
        info = dp.info(result)
        manifest = info.get("manifest", {})

        print(f"✅ Пакет создан: {result}")
        print(f"   Размер: {size_mb:.1f} МБ")
        print(f"   Файлов: {info['total_files']}")
        if manifest:
            print(f"   Конфигураций: {len(manifest.get('configs', []))}")
            print(f"   Создан: {manifest.get('created_at', '?')[:19]}")

    elif args.data_command == "load-pkg":
        path = Path(args.path)
        if not path.is_absolute():
            path = project.paths.root / path

        if not path.exists():
            print(f"❌ Пакет не найден: {path}")
            sys.exit(1)

        print(f"Восстановление из: {path}")
        print()

        # Сначала покажем что внутри
        info = dp.info(path)
        manifest = info.get("manifest")
        if manifest:
            print(f"Пакет создан: {manifest.get('created_at', '?')[:19]}")
            print(f"Конфигураций: {len(manifest.get('configs', []))}")
            for c in manifest.get("configs", []):
                print(f"  • {c['name']} v{c['version']} — {c['objects_count']} объектов")
            print()

        # Распаковка
        stats = dp.load(path)
        print(f"✅ Восстановлено файлов: {stats['files_restored']}")
        print(f"   Из них derived: {stats['derived_restored']}")
        print(f"   Из них data (raw): {stats['raw_restored']}")
        print(f"   config-registry.json: {'✅' if stats['configs_loaded'] else '—'}")
        print()
        print("Теперь данные доступны для:")
        print("  • 1c-ai search '<запрос>'        — поиск по методам платформы")
        print("  • 1c-ai config list              — список конфигураций")
        print("  • 1c-ai mcp serve                — MCP-сервер для IDE")

    elif args.data_command == "info":
        path = Path(args.path) if args.path else dp.default_package_path
        if not path.is_absolute():
            path = project.paths.root / path

        if not path.exists():
            print(f"❌ Пакет не найден: {path}")
            sys.exit(1)

        info = dp.info(path)
        print(f"Пакет: {path}")
        print(f"Размер: {info['size_mb']:.1f} МБ")
        print(f"Файлов: {info['total_files']}")
        if info["manifest"]:
            m = info["manifest"]
            print()
            print("Манифест:")
            print(f"  Версия: {m.get('version', '?')}")
            print(f"  Создан: {m.get('created_at', '?')[:19]}")
            print(f"  Включая raw: {m.get('include_raw', False)}")
            print(f"  Конфигураций: {len(m.get('configs', []))}")
            for c in m.get("configs", []):
                print(f"    • {c['name']} v{c['version']} — {c.get('objects_count', 0)} объектов")
            if m.get("description"):
                print(f"  Описание: {m['description']}")
        print()
        print(f"Первые {len(info['file_list_sample'])} файлов:")
        for f in info["file_list_sample"][:20]:
            print(f"  {f}")
        if info["total_files"] > 20:
            print(f"  ... и ещё {info['total_files'] - 20}")

    elif args.data_command == "autosave":
        print(f"Автосохранение в: {dp.default_package_path}")
        result = dp.autosave(
            include_raw=args.include_raw,
            description=args.description or "Autosave",
        )
        size_mb = result.stat().st_size / 1024 / 1024
        info = dp.info(result)
        print(f"✅ Сохранено: {result}")
        print(f"   Размер: {size_mb:.1f} МБ, файлов: {info['total_files']}")

    elif args.data_command == "autoload":
        if not dp.has_autosave():
            print(f"❌ Автосохранение не найдено: {dp.default_package_path}")
            print("   Сначала выполните: 1c-ai data autosave")
            sys.exit(1)

        print(f"Восстановление из: {dp.default_package_path}")
        stats = dp.load(dp.default_package_path)
        print(f"✅ Восстановлено файлов: {stats['files_restored']}")
        print(f"   derived: {stats['derived_restored']}")
        print(f"   data (raw): {stats['raw_restored']}")

    elif args.data_command == "status":
        status = dp.status()
        print("Статус данных проекта:")
        print()
        print("Платформа 1С:")
        print(f"  Индекс поиска:      {'✅' if status['has_platform_index'] else '❌'}")
        print(f"  Методы (syntax-helper): {'✅' if status['has_platform_methods'] else '❌'}")
        print()
        print(f"Конфигурации ({len(status['configs'])}):")
        if not status["configs"]:
            print("  (нет)")
        else:
            print(f"  {'Имя':<15} {'Версия':<15} {'Статус':<10} {'API':<5} {'Индекс':<7} {'Raw':<5}")
            print("  " + "-" * 60)
            for c in status["configs"]:
                api = "✅" if c["has_api"] else "❌"
                der = "✅" if c["has_derived"] else "❌"
                raw = "✅" if c["has_raw"] else "—"
                print(f"  {c['name']:<15} {c['version']:<15} {c['status']:<10} {api:<5} {der:<7} {raw:<5}")
        print()
        print(f"Автосохранение: {'✅ доступно' if status['autosave_available'] else '❌ нет'}")
        if status["autosave_available"]:
            ai = status["autosave_info"]
            print(f"  Размер: {ai['size_mb']:.1f} МБ")
            print(f"  Файлов: {ai['total_files']}")
            if ai["manifest"]:
                print(f"  Создан: {ai['manifest'].get('created_at', '?')[:19]}")
                print("  Восстановить: 1c-ai data autoload")

    elif args.data_command == "release-push":
        # Загрузить в GitHub Releases
        from .services.github_releases import GitHubReleases

        gh = GitHubReleases(project.paths)
        if not gh.is_configured():
            print("❌ GitHub Releases не настроен")
            print("   Установите GITHUB_TOKEN в окружении:")
            print("   export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>")
            sys.exit(1)

        if not dp.has_autosave():
            print("❌ Автосохранение не найдено. Сначала:")
            print("   1c-ai data autosave --include-raw")
            sys.exit(1)

        print("Загрузка в GitHub Releases...")
        print(f"   Repo: {gh._repo}")
        print(f"   Пакет: {dp.default_package_path}")
        print()
        result = gh.push(body=args.body or "Autosave data package")
        if result.get("success"):
            print(f"✅ Загружено в release '{result['tag']}'")
            print(f"   Размер: {result['size_mb']:.1f} МБ")
            print(f"   Release: {result['release_url']}")
            print(f"   Asset: {result['asset_url']}")
            print()
            print("В новой сессии восстановите:")
            print("   1c-ai data release-pull")
            print("   1c-ai data autoload")
        else:
            print(f"❌ Ошибка: {result.get('error', 'неизвестная')}")
            sys.exit(1)

    elif args.data_command == "release-pull":
        # Скачать из GitHub Releases
        from .services.github_releases import GitHubReleases

        gh = GitHubReleases(project.paths)
        if not gh.is_configured():
            print("❌ GitHub Releases не настроен")
            print("   Установите GITHUB_TOKEN: export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>")
            sys.exit(1)

        print("Скачивание из GitHub Releases...")
        print(f"   Repo: {gh._repo}")
        print(f"   Target: {dp.default_package_path}")
        print()
        result = gh.pull()
        if result.get("success"):
            print(f"✅ Скачано в: {result['path']}")
            print(f"   Размер: {result['size_mb']:.1f} МБ")
            print(f"   Release tag: {result['tag']}")
            print()
            print("Восстановите данные:")
            print("   1c-ai data autoload")
        else:
            print(f"❌ Ошибка: {result.get('error', 'неизвестная')}")
            sys.exit(1)

    elif args.data_command == "release-status":
        # Статус GitHub Releases
        from .services.github_releases import GitHubReleases

        gh = GitHubReleases(project.paths)
        status = gh.status()
        print("GitHub Releases статус:")
        print(f"  Настроен: {'✅' if status['configured'] else '❌'}")
        print(f"  Repo: {status['repo'] or '(не определён)'}")
        print(f"  Token: {'✅' if status['token_set'] else '❌'}")
        if status["configured"]:
            print(f"  Release существует: {'✅' if status['release_exists'] else '❌'}")
            if status["release_exists"]:
                print(f"  Tag: {status['release_tag']}")
                print(f"  Создан: {status['release_created_at']}")
                print(f"  Размер asset: {status['asset_size_mb']:.1f} МБ")
                print(f"  Имя asset: {status['asset_name']}")
                print(f"  URL: {status['release_url']}")
                print()
                print("Восстановить:")
                print("   1c-ai data release-pull")
                print("   1c-ai data autoload")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="src.cli",
        description="1C AI Development Environment CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # config
    p_cfg = sub.add_parser("config", help="Управление конфигурациями")
    cfg_sub = p_cfg.add_subparsers(dest="config_command", required=True)

    cfg_sub.add_parser("list", help="Список")

    p_add = cfg_sub.add_parser("add", help="Добавить из ZIP")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--zip", help="ZIP выгрузка конфигурации")
    p_add.add_argument("--cf", help=".cf/.cfe/.epf файл конфигурации")
    p_add.add_argument("--title", default="")
    p_add.add_argument("--skip-build", action="store_true")

    p_build = cfg_sub.add_parser("build", help="Индексы для одной")
    p_build.add_argument("--name", required=True)
    p_build.add_argument("--force", action="store_true", help="Перестроить даже если индексы свежие")
    p_build.add_argument("--check-freshness", action="store_true", help="Только проверить актуальность индексов")
    p_build.add_argument("--validate", action="store_true", help="Только проверить исходники")

    p_build_all = cfg_sub.add_parser("build-all", help="Индексы для всех")
    p_build_all.add_argument("--force", action="store_true", help="Перестроить даже если свежие")

    # bsl
    p_bsl = sub.add_parser("bsl", help="Анализ .bsl")
    bsl_sub = p_bsl.add_subparsers(dest="bsl_command", required=True)

    p_a = bsl_sub.add_parser("analyze", help="Анализ")
    p_a.add_argument("path")

    p_b = bsl_sub.add_parser("baseline", help="Сохранить baseline")
    p_b.add_argument("path")

    p_d = bsl_sub.add_parser("diff", help="Только новые ошибки")
    p_d.add_argument("path")

    # validate
    sub.add_parser("validate", help="Проверить окружение")

    # search
    p_search = sub.add_parser("search", help="Семантический поиск методов 1С")
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument("--limit", type=int, default=10, help="Кол-во результатов")

    # search-code — поиск по коду конфигураций
    p_scode = sub.add_parser("search-code", help="Поиск по коду конфигурации (115K+ методов)")
    p_scode.add_argument("query", help="Поисковый запрос")
    p_scode.add_argument("--config", required=True, help="Имя конфигурации (ut11, edo2, edo3, unp)")
    p_scode.add_argument("--limit", type=int, default=10, help="Кол-во результатов")

    # call-graph — граф вызовов методов
    p_cgraph = sub.add_parser("call-graph", help="Граф вызовов методов конфигурации")
    p_cgraph.add_argument("--config", required=True, help="Имя конфигурации")
    p_cgraph.add_argument(
        "action",
        choices=["stats", "callers", "callees", "dead-code", "cycles", "json"],
        default="stats",
        help="Действие: stats (по умолчанию), callers, callees, dead-code, cycles, json",
    )
    p_cgraph.add_argument("--module", help="Имя модуля (для callers/callees)")
    p_cgraph.add_argument("--method", help="Имя метода (для callers/callees)")

    # standards
    p_std = sub.add_parser("standards", help="Проверка .bsl на стандарты 1С")
    p_std.add_argument("path", help="Путь к .bsl файлу или директории")
    p_std.add_argument("--format", choices=["text", "json"], default="text", help="Формат вывода")
    p_std.add_argument("--severity", choices=["error", "all"], default="all", help="Минимальный уровень severity")

    # backup
    p_backup = sub.add_parser("backup", help="Backup/restore данных проекта")
    backup_sub = p_backup.add_subparsers(dest="backup_command", required=True)

    p_b_create = backup_sub.add_parser("create", help="Создать backup")
    p_b_create.add_argument("--output", "-o", help="Путь к ZIP файлу")
    p_b_create.add_argument(
        "--include-derived", action="store_true", help="Включить индексы derived/ (можно перестроить)"
    )

    p_b_restore = backup_sub.add_parser("restore", help="Восстановить из backup")
    p_b_restore.add_argument("path", help="Путь к ZIP файлу")

    p_b_list = backup_sub.add_parser("list", help="Список backup'ов")
    p_b_list.add_argument("--dir", help="Папка с backup'ами")

    # solve
    p_solve = sub.add_parser("solve", help="Автоматический цикл решения задачи")
    solve_sub = p_solve.add_subparsers(dest="solve_command", required=True)

    p_s_ctx = solve_sub.add_parser("context", help="Собрать контекст для LLM")
    p_s_ctx.add_argument("query", help="Описание задачи")
    p_s_ctx.add_argument("--config", help="Имя конфигурации")
    p_s_ctx.add_argument("--limit", type=int, default=5, help="Кол-во результатов поиска")

    p_s_chk = solve_sub.add_parser("check", help="Проверить .bsl код")
    p_s_chk.add_argument("path", help="Путь к .bsl файлу")
    p_s_chk.add_argument("--config", help="Имя конфигурации")
    p_s_chk.add_argument(
        "--level",
        choices=["quick", "standard", "full"],
        default="standard",
        help="Уровень проверки: quick (только стандарты), standard (+BSL LS), full (+метаданные)",
    )
    p_s_chk.add_argument("--ci", action="store_true", help="CI-режим: только errors, exit code 1 при errors")
    p_s_chk.add_argument("--json", action="store_true", help="JSON-вывод для парсинга в CI/CD")
    p_s_chk.add_argument(
        "--sarif", metavar="PATH", help="Записать SARIF 2.1.0 отчёт по указанному пути (для GitHub Code Scanning)"
    )

    # mcp
    p_mcp = sub.add_parser("mcp", help="MCP-сервер для IDE/LLM")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("serve", help="Запустить MCP-сервер (stdio)")
    mcp_sub.add_parser("tools", help="Вывести список доступных tools")

    # data — persistence данных
    p_data = sub.add_parser("data", help="Управление данными (persistence между сессиями)")
    data_sub = p_data.add_subparsers(dest="data_command", required=True)

    p_save = data_sub.add_parser("save-pkg", help="Сохранить данные в ZIP")
    p_save.add_argument("--output", "-o", help="Путь к ZIP (по умолчанию download/)")
    p_save.add_argument(
        "--include-raw", action="store_true", help="Включить data/ (распакованные конфиги — большой объём)"
    )
    p_save.add_argument("--description", "-d", default="", help="Описание пакета")

    p_load = data_sub.add_parser("load-pkg", help="Восстановить данные из ZIP")
    p_load.add_argument("path", help="Путь к ZIP файлу")

    p_info = data_sub.add_parser("info", help="Информация о пакете без распаковки")
    p_info.add_argument("path", nargs="?", help="Путь к ZIP (по умолчанию autosave)")

    p_auto = data_sub.add_parser("autosave", help="Сохранить в стандартное место (download/)")
    p_auto.add_argument("--include-raw", action="store_true")
    p_auto.add_argument("--description", "-d", default="")

    data_sub.add_parser("autoload", help="Восстановить из стандартного места (download/)")

    data_sub.add_parser("status", help="Статус данных: что доступно, что нужно перестроить")

    # GitHub Releases
    p_rpush = data_sub.add_parser("release-push", help="Загрузить пакет в GitHub Releases")
    p_rpush.add_argument("--body", "-b", default="", help="Описание релиза")

    data_sub.add_parser("release-pull", help="Скачать пакет из GitHub Releases")

    data_sub.add_parser("release-status", help="Статус GitHub Releases интеграции")

    # dsl — JSON DSL компиляторы
    p_dsl = sub.add_parser("dsl", help="JSON DSL → XML компиляторы для 1С")
    dsl_sub = p_dsl.add_subparsers(dest="dsl_command", required=True)

    p_dsl_meta = dsl_sub.add_parser("meta", help="Скомпилировать объект метаданных")
    p_dsl_meta.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_meta.add_argument("--json-string", help="JSON-строка")
    p_dsl_meta.add_argument("--output-dir", required=True)

    p_dsl_form = dsl_sub.add_parser("form", help="Скомпилировать форму")
    p_dsl_form.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_form.add_argument("--json-string", help="JSON-строка")
    p_dsl_form.add_argument("--output-path", required=True)

    p_dsl_skd = dsl_sub.add_parser("skd", help="Скомпилировать СКД")
    p_dsl_skd.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_skd.add_argument("--json-string", help="JSON-строка")
    p_dsl_skd.add_argument("--output-path", required=True)

    p_dsl_mxl = dsl_sub.add_parser("mxl", help="Скомпилировать MXL-макет")
    p_dsl_mxl.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_mxl.add_argument("--json-string", help="JSON-строка")
    p_dsl_mxl.add_argument("--output-path", required=True)

    p_dsl_role = dsl_sub.add_parser("role", help="Скомпилировать роль")
    p_dsl_role.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_role.add_argument("--json-string", help="JSON-строка")
    p_dsl_role.add_argument("--output-dir", required=True)

    # cfe — работа с расширениями
    p_cfe = sub.add_parser("cfe", help="Работа с расширениями конфигураций (CFE)")
    cfe_sub = p_cfe.add_subparsers(dest="cfe_command", required=True)

    p_cfe_borrow = cfe_sub.add_parser("borrow", help="Заимствовать объект")
    p_cfe_borrow.add_argument("--extension-path", required=True)
    p_cfe_borrow.add_argument("--config-path", required=True)
    p_cfe_borrow.add_argument("--object-ref", required=True)

    p_cfe_patch = cfe_sub.add_parser("patch", help="Сгенерировать перехватчик метода")
    p_cfe_patch.add_argument("--extension-path", required=True)
    p_cfe_patch.add_argument("--module-path", required=True)
    p_cfe_patch.add_argument("--method-name", required=True)
    p_cfe_patch.add_argument("--interceptor-type", required=True, choices=["Before", "After", "ModificationAndControl"])
    p_cfe_patch.add_argument("--context", default="НаСервере")
    p_cfe_patch.add_argument("--is-function", action="store_true")

    p_cfe_diff = cfe_sub.add_parser("diff", help="Анализ расширения")
    p_cfe_diff.add_argument("--extension-path", required=True)
    p_cfe_diff.add_argument("--config-path", required=True)

    # skd-trace — трассировка поля СКД
    p_skd_trace = sub.add_parser("skd-trace", help="Трассировка поля СКД")
    p_skd_trace.add_argument("template_path")
    p_skd_trace.add_argument("field_name")

    # depgraph — граф зависимостей
    p_depgraph = sub.add_parser("depgraph", help="Граф зависимостей метаданных")
    depgraph_sub = p_depgraph.add_subparsers(dest="depgraph_command", required=True)

    p_dg_build = depgraph_sub.add_parser("build", help="Построить граф")
    p_dg_build.add_argument("--name", required=True)
    p_dg_build.add_argument("--output")

    p_dg_query = depgraph_sub.add_parser("query", help="Запрос к графу")
    p_dg_query.add_argument("--name", required=True)
    p_dg_query.add_argument(
        "--query-type",
        required=True,
        choices=[
            "what_depends_on",
            "dependencies_of",
            "transitive_dependencies",
            "transitive_dependents",
            "find_cycles",
            "find_unused_objects",
            "find_root_objects",
            "shortest_path",
            "stats",
        ],
    )
    p_dg_query.add_argument("--object")
    p_dg_query.add_argument("--target")

    p_dg_validate = depgraph_sub.add_parser("validate", help="Проверить что граф DAG")
    p_dg_validate.add_argument("--name", required=True)

    # openspec
    p_openspec = sub.add_parser("openspec", help="OpenSpec — управление изменениями")
    openspec_sub = p_openspec.add_subparsers(dest="openspec_command", required=True)

    p_os_init = openspec_sub.add_parser("init", help="Инициализировать openspec/")
    p_os_init.add_argument("--project-name")

    p_os_proposal = openspec_sub.add_parser("proposal", help="Создать proposal")
    p_os_proposal.add_argument("--change-id", required=True)
    p_os_proposal.add_argument("--title", required=True)
    p_os_proposal.add_argument("--context")
    p_os_proposal.add_argument("--approach")
    p_os_proposal.add_argument("--tasks")
    p_os_proposal.add_argument("--files")

    p_os_list = openspec_sub.add_parser("list", help="Список changes")
    p_os_list.add_argument("--archived", action="store_true")

    p_os_update = openspec_sub.add_parser("update", help="Обновить задачу")
    p_os_update.add_argument("--change-id", required=True)
    p_os_update.add_argument("--task-index", type=int, required=True)
    p_os_update.add_argument("--completed", action="store_true")
    p_os_update.add_argument("--not-completed", action="store_true")
    p_os_update.add_argument("--notes")

    p_os_archive = openspec_sub.add_parser("archive", help="Архивировать")
    p_os_archive.add_argument("--change-id", required=True)

    p_os_validate = openspec_sub.add_parser("validate", help="Валидация")
    p_os_validate.add_argument("--change-id", required=True)

    # session
    p_session = sub.add_parser("session", help="Управление AI-сессиями")
    session_sub = p_session.add_subparsers(dest="session_command", required=True)

    p_s_save = session_sub.add_parser("save", help="Сохранить сессию")
    p_s_save.add_argument("--task")
    p_s_save.add_argument("--completed")
    p_s_save.add_argument("--pending")
    p_s_save.add_argument("--next-action")
    p_s_save.add_argument("--decisions")
    p_s_save.add_argument("--modified")
    p_s_save.add_argument("--summary")

    session_sub.add_parser("restore", help="Восстановить сессию")
    session_sub.add_parser("retro", help="Ретроспектива")
    session_sub.add_parser("clear", help="Очистить сессию")

    # inspect — единый анализ
    p_inspect = sub.add_parser("inspect", help="Единый анализ объектов 1С")
    p_inspect.add_argument("target", choices=["cf", "meta", "form", "skd", "mxl", "role", "subsystem", "depgraph"])
    p_inspect.add_argument("path")
    p_inspect.add_argument("--mode", default="overview", choices=["overview", "brief", "full", "trace"])
    p_inspect.add_argument("--name")

    # epf-factory — полный цикл создания внешней обработки 1С (.epf)
    p_epf = sub.add_parser("epf-factory", help="Создание внешней обработки 1С (.epf) из шаблонов")
    epf_sub = p_epf.add_subparsers(dest="epf_command", required=True)

    p_epf_create = epf_sub.add_parser("create", help="Создать .epf из BSL-кода")
    p_epf_create.add_argument("--name", required=True, help="Имя обработки (латиница/кириллица, без пробелов)")
    p_epf_create.add_argument("--synonym", help="Синоним (по умолчанию = name)")
    p_epf_create.add_argument("--bsl", required=True, help="Путь к .bsl файлу с модулем формы")
    p_epf_create.add_argument("--output", required=True, help="Путь к выходному .epf файлу")
    p_epf_create.add_argument("--form-name", default="Форма", help="Имя формы (по умолчанию Форма)")
    p_epf_create.add_argument("--form-spec", help="Путь к JSON-файлу с DSL-описанием формы (реквизиты, колонки)")
    p_epf_create.add_argument(
        "--save-sources", action="store_true", help="Сохранить v8unpack-исходники в work_dir (не удалять)"
    )
    p_epf_create.add_argument("--skip-bsl-validation", action="store_true", help="Пропустить проверку BSL через BSL LS")

    epf_sub.add_parser("templates", help="Список доступных шаблонов")

    args = parser.parse_args()
    project = Project()

    if args.command == "config":
        if args.config_command == "list":
            cmd_config_list(project, args)
        elif args.config_command == "add":
            cmd_config_add(project, args)
        elif args.config_command == "build":
            cmd_config_build(project, args)
        elif args.config_command == "build-all":
            cmd_config_build_all(project, args)
    elif args.command == "bsl":
        if args.bsl_command == "analyze":
            cmd_bsl_analyze(project, args)
        elif args.bsl_command == "baseline":
            cmd_bsl_baseline(project, args)
        elif args.bsl_command == "diff":
            cmd_bsl_diff(project, args)
    elif args.command == "validate":
        cmd_validate(project, args)
    elif args.command == "search":
        cmd_search(project, args)
    elif args.command == "search-code":
        cmd_search_code(project, args)
    elif args.command == "call-graph":
        cmd_call_graph(project, args)
    elif args.command == "standards":
        cmd_standards(project, args)
    elif args.command == "backup":
        cmd_backup(project, args)
    elif args.command == "solve":
        cmd_solve(project, args)
    elif args.command == "mcp":
        cmd_mcp(project, args)
    elif args.command == "data":
        cmd_data(project, args)
    elif args.command == "dsl":
        cmd_dsl(project, args)
    elif args.command == "cfe":
        cmd_cfe(project, args)
    elif args.command == "skd-trace":
        cmd_skd_trace(project, args)
    elif args.command == "depgraph":
        cmd_depgraph(project, args)
    elif args.command == "openspec":
        cmd_openspec(project, args)
    elif args.command == "session":
        cmd_session(project, args)
    elif args.command == "inspect":
        cmd_inspect(project, args)
    elif args.command == "epf-factory":
        cmd_epf_factory(project, args)


# ============================================================================
# EPF Factory — полный цикл создания внешней обработки 1С
# ============================================================================


if __name__ == "__main__":
    main()
