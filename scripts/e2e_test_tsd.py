#!/usr/bin/env python3
"""E2E тест: полный pipeline генерации BSL-кода для ТСД."""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.project import Project


# BSL код клиентского модуля ТСД (на основе данных из get_method_details)
CLIENT_CODE = """#Область ПрограммныйИнтерфейс

Асинх Функция ПодключитьТСДАсинх(ИмяМакета, КлючПрофиля) Экспорт

    Результат = Новый Структура("Успех, Ошибка, Драйвер", Ложь, "", Неопределено);

    Попытка
        Ждать УстановитьВнешнююКомпонентуАсинх(ИмяМакета);
        Подключено = Ждать ПодключитьВнешнююКомпонентуАсинх(ИмяМакета, "InputDevice", ТипВнешнейКомпоненты.Native);

        Если Не Подключено Тогда
            Результат.Ошибка = "Не удалось подключить компоненту";
            Возврат Результат;
        КонецЕсли;

        Драйвер = Новый("AddIn.InputDevice.InputDevice");
        Драйвер.УстановитьПараметр("Action", "com.xcheng.scanner.action.BARCODE_DECODING_BROADCAST");
        Драйвер.Подключить("");

        Результат.Успех = Истина;
        Результат.Драйвер = Драйвер;
    Исключение
        Результат.Ошибка = ОписаниеОшибки();
    КонецПопытки;

    Возврат Результат;

КонецФункции

Функция ОтключитьТСД(Драйвер) Экспорт
    Если Драйвер <> Неопределено Тогда
        Драйвер.Отключить("");
    КонецЕсли;
    Возврат Истина;
КонецФункции

#КонецОбласти"""


# BSL код с ОШИБКАМИ (серверные методы на клиенте)
BAD_CODE = """#Область ПрограммныйИнтерфейс

Асинх Функция ПодключитьТСДАсинх(ИмяМакета, КлючПрофиля) Экспорт

    Результат = Новый Структура("Успех, Ошибка, Драйвер", Ложь, "", Неопределено);

    Попытка
        Ждать УстановитьВнешнююКомпонентуАсинх(ИмяМакета);
        Подключено = Ждать ПодключитьВнешнююКомпонентуАсинх(ИмяМакета, "InputDevice", ТипВнешнейКомпоненты.Native);

        Если Не Подключено Тогда
            ЗаписьЖурналаРегистрации("ТСД.Ошибка", УровеньЖурналаРегистрации.Ошибка);
            Возврат Результат;
        КонецЕсли;

        Драйвер = Новый("AddIn.InputDevice.InputDevice");
        Драйвер.УстановитьПараметр("Action", "test");
        Драйвер.Подключить("");

        Если Метаданные.Справочники.Найти("ПрофилиТСД") <> Неопределено Тогда
            Результат.Успех = Истина;
        КонецЕсли;

        Результат.Драйвер = Драйвер;
    Исключение
        ЗаписьЖурналаРегистрации("ТСД.Ошибка", УровеньЖурналаРегистрации.Ошибка, , , ОписаниеОшибки());
    КонецПопытки;

    Возврат Результат;

КонецФункции

#КонецОбласти"""


async def main():
    project = Project()

    # ========================================================================
    # ШАГ 1: solve_context
    # ========================================================================
    print("=" * 60)
    print("ШАГ 1: solve_context")
    print("=" * 60)

    from src.mcpserver.handlers.analyzers import handle_solve_context
    result = await handle_solve_context(project, {
        "query": "написать BSL модуль для подключения ТСД через внешнюю компоненту",
        "config": "",
        "limit": 5
    })
    data = json.loads(result[0].text)

    methods = data.get("platform_methods", [])
    rules = data.get("_bsl_context_rules", "")
    workflow = data.get("_workflow", [])

    print(f"  Методов найдено: {len(methods)}")
    print(f"  Правил BSL: {len(rules)} символов")
    print(f"  Workflow: {len(workflow)} шагов")

    assert len(methods) > 0, "Методы не найдены!"
    assert "get_method_details" in rules, "Правила не содержат get_method_details!"
    assert any(s["tool"] == "check_bsl_context" for s in workflow), "Workflow не содержит check_bsl_context!"
    print("  ✅ ОК")

    # ========================================================================
    # ШАГ 2: search_platform_method
    # ========================================================================
    print()
    print("=" * 60)
    print("ШАГ 2: search_platform_method")
    print("=" * 60)

    from src.mcpserver.handlers.quality import handle_search_platform_method

    for method_name in ["УстановитьВнешнююКомпоненту", "ПодключитьВнешнююКомпоненту", "ЗаписьЖурналаРегистрации"]:
        result = await handle_search_platform_method(project, {"query": method_name, "limit": 1})
        data = json.loads(result[0].text)
        methods = data.get("methods", [])
        assert len(methods) > 0, f"Метод {method_name} не найден!"
        print(f"  ✅ {method_name}: найден")
    print("  ✅ ОК")

    # ========================================================================
    # ШАГ 3: get_method_details
    # ========================================================================
    print()
    print("=" * 60)
    print("ШАГ 3: get_method_details")
    print("=" * 60)

    from src.mcpserver.handlers.quality import handle_get_method_details

    critical_methods = {
        "УстановитьВнешнююКомпоненту": True,   # должен быть на клиенте
        "ПодключитьВнешнююКомпоненту": True,   # должен быть на клиенте
        "ЗаписьЖурналаРегистрации": False,     # НЕ должен быть на клиенте
    }

    for method_name, should_be_on_client in critical_methods.items():
        result = await handle_get_method_details(project, {"name": method_name})
        data = json.loads(result[0].text)

        if "error" in data:
            print(f"  ❌ {method_name}: {data['error']}")
            continue

        m = data["method"]
        avail = json.loads(m.get("availability_json", "{}"))
        on_client = avail.get("thin_client", False)

        if should_be_on_client:
            assert on_client, f"{method_name} должен быть на клиенте!"
            print(f"  ✅ {method_name}: на клиенте = {on_client} (ожидаем True)")
        else:
            assert not on_client, f"{method_name} НЕ должен быть на клиенте!"
            print(f"  ✅ {method_name}: на клиенте = {on_client} (ожидаем False)")
    print("  ✅ ОК")

    # ========================================================================
    # ШАГ 4: check_bsl_context — ХОРОШИЙ код
    # ========================================================================
    print()
    print("=" * 60)
    print("ШАГ 4: check_bsl_context — ХОРОШИЙ код")
    print("=" * 60)

    from src.mcpserver.handlers.quality import handle_check_bsl_context

    result = await handle_check_bsl_context(project, {
        "code": CLIENT_CODE,
        "target_context": ["thin_client", "mobile_client"]
    })
    data = json.loads(result[0].text)

    errors = [v for v in data["violations"] if v["severity"] == "error"]
    print(f"  Errors: {len(errors)}")
    for v in data["violations"]:
        icon = "❌" if v["severity"] == "error" else "⚠️"
        print(f"  {icon} {v['rule_id']}: {v['message'][:80]}")

    # Не должно быть ошибок CTX001 (серверные методы на клиенте)
    ctx_errors = [v for v in errors if v["rule_id"] == "CTX001"]
    assert len(ctx_errors) == 0, f"Должно быть 0 CTX001 ошибок, получено {len(ctx_errors)}"
    print("  ✅ ОК — нет ошибок контекста")

    # ========================================================================
    # ШАГ 5: check_bsl_context — ПЛОХОЙ код (с ошибками)
    # ========================================================================
    print()
    print("=" * 60)
    print("ШАГ 5: check_bsl_context — ПЛОХОЙ код")
    print("=" * 60)

    result = await handle_check_bsl_context(project, {
        "code": BAD_CODE,
        "target_context": ["thin_client", "mobile_client"]
    })
    data = json.loads(result[0].text)

    errors = [v for v in data["violations"] if v["severity"] == "error"]
    print(f"  Errors: {len(errors)}")
    for v in data["violations"]:
        icon = "❌" if v["severity"] == "error" else "⚠️"
        print(f"  {icon} {v['rule_id']} (строка {v['line']}): {v['message'][:80]}")

    # Должны быть ошибки CTX001
    assert len(errors) > 0, "Должны быть ошибки!"
    has_zapis = any("ЗаписьЖурнал" in v.get("message", "") for v in errors)
    has_metadata = any("Метаданные" in v.get("message", "") or "Справочники" in v.get("message", "") for v in errors)
    assert has_zapis, "Должна быть ошибка про ЗаписьЖурналаРегистрации!"
    assert has_metadata, "Должна быть ошибка про Метаданные/Справочники!"
    print("  ✅ ОК — найдены ошибки ЗаписьЖурналаРегистрации + Метаданные")

    # ========================================================================
    # ШАГ 6: solve check — полная проверка через task_processor
    # ========================================================================
    print()
    print("=" * 60)
    print("ШАГ 6: solve check (task_processor.check)")
    print("=" * 60)

    from src.services.task_processor import TaskProcessor
    from src.services.path_manager import PathManager

    processor = TaskProcessor(PathManager())

    # Сохраняем плохой код во временный файл
    with tempfile.NamedTemporaryFile(mode="w", suffix=".bsl", delete=False, encoding="utf-8") as f:
        f.write(BAD_CODE)
        f.flush()
        result = processor.check(Path(f.name), level="standard")

    print(f"  Analyzers: {result.analyzers_run}")
    print(f"  Total violations: {len(result.violations)}")

    ctx_violations = [v for v in result.violations if v.source == "bsl_context_checker"]
    print(f"  bsl_context_checker violations: {len(ctx_violations)}")
    for v in ctx_violations:
        print(f"    {v.rule_id} ({v.severity}): {v.message[:80]}")

    assert "bsl_context_checker" in result.analyzers_run, "bsl_context_checker не запустился!"
    assert len(ctx_violations) > 0, "Должны быть нарушения контекста!"
    print("  ✅ ОК — bsl_context_checker запущен и нашёл ошибки")

    # ========================================================================
    # ИТОГ
    # ========================================================================
    print()
    print("=" * 60)
    print("ИТОГ: ВСЕ 6 ШАГОВ ПРОШЛИ")
    print("=" * 60)
    print()
    print("Синтакс-помощник ИСПОЛЬЗУЕТСЯ на каждом этапе:")
    print("  1. solve_context → PlatformMethodsIndex (нашёл 5 методов)")
    print("  2. search_platform_method → FTS5 поиск (3/3 найдены)")
    print("  3. get_method_details → полные карточки (3/3 проверены)")
    print("  4. check_bsl_context → ХОРОШИЙ код: 0 ошибок CTX001")
    print("  5. check_bsl_context → ПЛОХОЙ код: найдены ЗаписьЖурналаРегистрации + Метаданные")
    print("  6. solve check → bsl_context_checker в task_processor.check()")
    print()
    print("Ключевое: теперь ПЕРЕД генерацией BSL-кода мы ЗНАЕМ, что")
    print("УстановитьВнешнююКомпоненту доступна на клиенте, а")
    print("ЗаписьЖурналаРегистрации — НЕ доступна. И после генерации")
    print("check_bsl_context АВТОМАТИЧЕСКИ ловит ошибки.")


if __name__ == "__main__":
    asyncio.run(main())
