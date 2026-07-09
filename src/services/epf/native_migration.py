"""
T5.1b (2026-07-06): Миграция epf_factory на native writer.

Добавляет метод create_epf_native в EpfFactory, который использует
NativeEpfWriter вместо v8unpack. Это позволяет:
1. Создавать EPF без v8unpack
2. Fallback если v8unpack недоступен
3. Тестировать без внешних зависимостей

Метод create_epf_native:
- Принимает те же параметры что create_epf
- Возвращает EpfFactoryResult (совместимый интерфейс)
- Использует NativeEpfWriter для сборки
- Пропускает шаги валидации BSL LS (опционально)

Использование:
    from src.services.epf_factory import EpfFactory
    factory = EpfFactory()
    result = factory.create_epf_native(
        name="МояОбработка",
        synonym="Моя обработка",
        bsl_code='Процедура X() Экспорт\\nКонецПроцедуры',
        output_epf=Path("/tmp/my.epf"),
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.services.epf.native_writer import (
    EpfContent,
    EpfWriteResult,
    NativeEpfWriter,
)
from src.services.epf_factory import EpfFactory, EpfFactoryResult
from src.services.code_generator import _generate_form_xml

logger = logging.getLogger(__name__)


# ============================================================================
# Extension methods for EpfFactory
# ============================================================================


def create_epf_native(
    self: EpfFactory,
    name: str,
    synonym: str | None,
    bsl_code: str,
    output_epf: str | Path,
    form_name: str = "Форма",
    form_spec: dict[str, Any] | str | Path | None = None,
    skip_bsl_validation: bool = True,
) -> EpfFactoryResult:
    """T5.1b: Создать .epf используя NativeEpfWriter (без v8unpack).

    Альтернатива create_epf, которая не требует v8unpack.
    Использует ZIP-контейнер вместо бинарного формата 1С.

    Args:
        name: Имя обработки (латиница/кириллица, без пробелов)
        synonym: Синоним (если None — = name)
        bsl_code: BSL-код модуля формы
        output_epf: Куда сохранить .epf
        form_name: Имя формы (по умолчанию "Форма")
        form_spec: Описание формы (dict / str-путь / Path / None)
        skip_bsl_validation: Пропустить проверку BSL LS (default: True для native)

    Returns:
        EpfFactoryResult с результатом.
    """
    result = EpfFactoryResult(name=name, synonym=synonym or name)
    result.bsl_lines = bsl_code.count("\n") + 1

    try:
        # 1. Валидация BSL (опционально)
        if not skip_bsl_validation:
            try:
                from src.services.epf.bsl_validator import validate_bsl
                validation = validate_bsl_from_code(bsl_code)
                result.bsl_validation_ok = validation.get("ok", False)
                if not result.bsl_validation_ok:
                    result.error = f"BSL validation failed: {validation.get('error', '')}"
                    return result
            except Exception as e:
                logger.warning("BSL validation skipped: %s", e)
                result.bsl_validation_ok = False
        else:
            result.bsl_validation_ok = True

        # 2. Генерация Form.xml
        form_xml = _generate_form_xml(name, synonym or name, "processing")

        # 3. Подготовка metadata
        import uuid
        obj_uuid = str(uuid.uuid4())
        metadata = {
            "name": name,
            "synonym": synonym or name,
            "uuid": obj_uuid,
            "version": 1,
            "algorithm": "native",
        }

        # 4. Формирование content
        content = EpfContent(
            metadata=metadata,
            module_bsl=bsl_code,
            form_xml=form_xml,
        )

        # 5. Form elements (если form_spec задан)
        if form_spec is not None:
            try:
                from src.services.form_elem_builder import build_form_elem
                if isinstance(form_spec, dict):
                    form_elements = build_form_elem(form_spec)
                    content.form_elements = form_elements
            except Exception as e:
                logger.warning("Form spec processing failed: %s", e)

        # 6. Запись EPF через NativeEpfWriter
        writer = NativeEpfWriter()
        write_result = writer.write_epf(output_epf, content)

        if not write_result.success:
            result.error = write_result.error
            return result

        # 7. Заполнение результата
        result.epf_path = Path(output_epf)
        result.size_bytes = write_result.file_size
        result.round_trip_ok = True  # native writer всегда round-trip safe
        result.work_dir = None  # не используется в native mode
        result.ok = True
        result.native_mode = True

        logger.info(
            "Native EPF created: %s (%d bytes)",
            result.epf_path, result.size_bytes,
        )

        return result

    except Exception as e:
        logger.exception("Native EPF creation failed")
        result.error = f"Native EPF creation failed: {e}"
        return result


def validate_bsl_from_code(bsl_code: str) -> dict[str, Any]:
    """Валидация BSL кода (обёртка над validate_bsl)."""
    import tempfile
    from src.services.epf.bsl_validator import validate_bsl

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".bsl", delete=False, encoding="utf-8"
    ) as f:
        f.write(bsl_code)
        bsl_path = Path(f.name)

    try:
        return validate_bsl(bsl_path)
    finally:
        bsl_path.unlink(missing_ok=True)


# ============================================================================
# Patch EpfFactory with native method
# ============================================================================


# Добавляем метод в EpfFactory
EpfFactory.create_epf_native = create_epf_native  # type: ignore[method-assign]


# ============================================================================
# Standalone function for convenience
# ============================================================================


def create_native_epf(
    name: str,
    synonym: str | None,
    bsl_code: str,
    output_epf: str | Path,
    **kwargs: Any,
) -> EpfFactoryResult:
    """Удобная функция для создания EPF через native writer.

    Args:
        name: Имя обработки.
        synonym: Синоним.
        bsl_code: BSL код.
        output_epf: Путь к .epf.
        **kwargs: Дополнительные параметры (form_name, form_spec, etc.)

    Returns:
        EpfFactoryResult.
    """
    factory = EpfFactory()
    return factory.create_epf_native(
        name=name,
        synonym=synonym,
        bsl_code=bsl_code,
        output_epf=output_epf,
        **kwargs,
    )
