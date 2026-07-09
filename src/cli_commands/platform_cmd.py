"""
platform_cmd.py — CLI команды для работы с методами платформы 1С.

B11: Команды:
  1c-ai platform search <query>     — поиск методов платформы
  1c-ai platform method <name>      — полная карточка метода
  1c-ai platform check <file.bsl>   — проверка BSL-кода на контекст
  1c-ai platform versions           — список доступных версий
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.project import Project


def cmd_platform_search(project: Project, args: argparse.Namespace) -> None:
    """Поиск методов платформы 1С."""
    from src.services.platform_methods_index import PlatformMethodsIndex

    idx = PlatformMethodsIndex(platform_version=args.version or None)
    if not idx.is_available():
        print("❌ Индекс платформы не построен.")
        print("   Запустите: python3 scripts/build_platform_methods_index.py")
        sys.exit(1)

    results = idx.search(args.query, limit=args.limit)
    idx.close()

    if not results:
        print(f"Ничего не найдено по запросу: {args.query}")
        return

    print(f"Найдено методов: {len(results)}")
    print(f"Версия платформы: {idx.platform_version}")
    print()
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['name_ru']} ({r['name_en']})")
        print(f"     Категория: {r['category']}")
        if r.get("availability_raw"):
            print(f"     Доступность: {r['availability_raw']}")
        if r.get("version_since"):
            print(f"     Версия: {r['version_since']}")
        if r.get("description"):
            print(f"     Описание: {r['description'][:100]}...")
        print()


def cmd_platform_method(project: Project, args: argparse.Namespace) -> None:
    """Полная карточка метода платформы 1С."""
    from src.services.platform_methods_index import PlatformMethodsIndex

    idx = PlatformMethodsIndex(platform_version=args.version or None)
    if not idx.is_available():
        print("❌ Индекс платформы не построен.")
        sys.exit(1)

    method = idx.get_method(args.name)
    idx.close()

    if method is None:
        print(f"❌ Метод '{args.name}' не найден")
        sys.exit(1)

    print(f"═══════════════════════════════════════════════════════")
    print(f"  {method.get('title', method.get('name_ru', '?'))}")
    print(f"═══════════════════════════════════════════════════════")
    print()
    print(f"Имя (RU):  {method.get('name_ru', '?')}")
    print(f"Имя (EN):  {method.get('name_en', '?')}")
    print(f"Категория: {method.get('category', '?')}")
    if method.get("version_since"):
        print(f"Версия:    доступен с {method.get('version_since')}")
    if method.get("version_deprecated"):
        print(f"⚠️  Устарел с версии {method.get('version_deprecated')}")
    print()

    if method.get("syntax"):
        print(f"── Синтаксис ──")
        print(f"  {method['syntax']}")
        print()

    if method.get("params_json"):
        import json as json_mod
        params = json_mod.loads(method["params_json"])
        if params:
            print(f"── Параметры ({len(params)}) ──")
            for p in params:
                req = "обязательный" if "обязательный" in p.get("required", "") else "необязательный"
                print(f"  <{p['name']}> ({req})")
                if p.get("description"):
                    print(f"    {p['description'][:150]}")
            print()

    if method.get("description"):
        print(f"── Описание ──")
        print(f"  {method['description']}")
        print()

    if method.get("availability_raw"):
        print(f"── Доступность ──")
        print(f"  {method['availability_raw']}")
        if method.get("availability_json"):
            import json as json_mod
            avail = json_mod.loads(method["availability_json"])
            print(f"  Флаги: ", end="")
            active = [k for k, v in avail.items() if v]
            print(", ".join(active) if active else "недоступен нигде")
        print()

    if method.get("example"):
        print(f"── Пример ──")
        print(f"  {method['example']}")
        print()

    if method.get("see_also_json"):
        import json as json_mod
        see_also = json_mod.loads(method["see_also_json"])
        if see_also:
            print(f"── См. также ──")
            print(f"  {', '.join(see_also[:10])}")
            print()


def cmd_platform_check(project: Project, args: argparse.Namespace) -> None:
    """Проверка BSL-кода на доступность методов."""
    from src.services.analyzers.bsl_context_checker import BslContextChecker

    bsl_path = Path(args.file)
    if not bsl_path.is_absolute():
        bsl_path = project.paths.root / bsl_path

    if not bsl_path.exists():
        print(f"❌ Файл не найден: {bsl_path}")
        sys.exit(2)

    checker = BslContextChecker()
    target_context = args.context.split(",") if args.context else None

    content = bsl_path.read_text(encoding="utf-8-sig", errors="replace")
    violations = checker.check_code(content, target_context=target_context)

    if not violations:
        print("✅ Нарушений контекста не найдено")
        return

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    print(f"Найдено: {len(errors)} errors, {len(warnings)} warnings")
    print()

    for v in violations:
        icon = "❌" if v.severity == "error" else "⚠️"
        print(f"  {icon} {v.rule_id} (строка {v.line}): {v.message}")
        if v.available_in:
            print(f"     Доступен: {v.available_in}")
        if v.recommendation:
            print(f"     Рекомендация: {v.recommendation}")
        print()

    if errors:
        sys.exit(1)


def cmd_platform_versions(project: Project, args: argparse.Namespace) -> None:
    """Список доступных версий платформы."""
    from src.services.platform_methods_index import PlatformMethodsIndex

    idx = PlatformMethodsIndex()
    versions = idx.list_versions()

    if not versions:
        print("❌ Нет построенных индексов платформы.")
        print("   Запустите: python3 scripts/build_platform_methods_index.py")
        return

    print(f"Доступные версии платформы: {len(versions)}")
    print()
    for v in versions:
        manifest_path = idx._paths.platform_manifest(v)
        methods_count = "?"
        if manifest_path.exists():
            import json as json_mod
            manifest = json_mod.loads(manifest_path.read_text(encoding="utf-8"))
            methods_count = manifest.get("total_methods", "?")

        marker = " ← текущая" if v == idx.platform_version else ""
        print(f"  {v}: {methods_count} методов{marker}")

    idx.close()


def register_platform_commands(subparsers) -> None:
    """Регистрация команд 1c-ai platform ..."""
    p_platform = subparsers.add_parser("platform", help="Работа с методами платформы 1С")
    platform_sub = p_platform.add_subparsers(dest="platform_command", required=True)

    # platform search
    p_search = platform_sub.add_parser("search", help="Поиск методов платформы")
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument("--limit", type=int, default=5, help="Максимум результатов")
    p_search.add_argument("--version", help="Версия платформы (по умолчанию 8.3.20)")

    # platform method
    p_method = platform_sub.add_parser("method", help="Полная карточка метода")
    p_method.add_argument("name", help="Имя метода (русское или английское)")
    p_method.add_argument("--version", help="Версия платформы")

    # platform check
    p_check = platform_sub.add_parser("check", help="Проверка BSL-кода на контекст")
    p_check.add_argument("file", help="Путь к .bsl файлу")
    p_check.add_argument(
        "--context",
        help="Целевой контекст (через запятую): thin_client,server,mobile_client",
    )

    # platform versions
    platform_sub.add_parser("versions", help="Список доступных версий платформы")
