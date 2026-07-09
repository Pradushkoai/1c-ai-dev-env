"""
T5.7 (2026-07-06): Тесты для BSL Code Templates.

Проверяет:
- 20+ шаблонов зарегистрированы
- Каждый шаблон возвращает валидный BSL код
- Параметры подставляются корректно
- Категории работают
- Registry API: get_template, list_templates
- Edge cases: пустые параметры, unknown template
- BSLTemplates class API
"""

from __future__ import annotations

import pytest

from src.services.bsl_templates import (
    BSLTemplates,
    TemplateInfo,
    _TEMPLATES,
    get_template,
    list_templates,
)


# ============================================================================
# Registry tests
# ============================================================================


class TestRegistry:
    """Тесты registry шаблонов."""

    def test_at_least_20_templates_registered(self) -> None:
        """Минимум 20 шаблонов зарегистрировано."""
        assert len(_TEMPLATES) >= 20, f"Expected >=20 templates, got {len(_TEMPLATES)}"

    def test_all_templates_have_info(self) -> None:
        """Все шаблоны имеют TemplateInfo."""
        for name, info in _TEMPLATES.items():
            assert isinstance(info, TemplateInfo), f"{name} not TemplateInfo"
            assert info.name == name
            assert info.description
            assert info.category
            assert isinstance(info.parameters, list)
            assert callable(info.generator)

    def test_template_names_unique(self) -> None:
        """Имена шаблонов уникальны."""
        names = [t.name for t in _TEMPLATES.values()]
        assert len(names) == len(set(names))


# ============================================================================
# get_template tests
# ============================================================================


class TestGetTemplate:
    """Тесты get_template function."""

    def test_get_existing_template(self) -> None:
        """Существующий шаблон возвращает код."""
        code = get_template("catalog_find_by_code", catalog_name="Номенклатура")
        assert isinstance(code, str)
        assert "Номенклатура" in code
        assert "Функция" in code

    def test_get_unknown_template_raises(self) -> None:
        """Несуществующий шаблон → KeyError."""
        with pytest.raises(KeyError, match="not found"):
            get_template("nonexistent_template")

    def test_get_template_with_all_params(self) -> None:
        """Шаблон с всеми параметрами."""
        code = get_template(
            "query_with_join",
            table1="Документ.Продажа",
            table2="Справочник.Номенклатура",
            join_field="Номенклатура",
        )
        assert "Документ.Продажа" in code
        assert "Справочник.Номенклатура" in code
        assert "Номенклатура" in code

    def test_get_template_with_default_params(self) -> None:
        """Шаблон с default параметрами."""
        code = get_template("catalog_find_by_code", catalog_name="Товары")
        # Должен использовать default code_var="Код"
        assert "Товары" in code
        assert "&Код" in code or "Код" in code


# ============================================================================
# list_templates tests
# ============================================================================


class TestListTemplates:
    """Тесты list_templates function."""

    def test_list_all_returns_all(self) -> None:
        """list_templates без category возвращает все."""
        all_templates = list_templates()
        assert len(all_templates) == len(_TEMPLATES)

    def test_list_by_category_catalog(self) -> None:
        """Фильтр по category='catalog'."""
        catalog_templates = list_templates(category="catalog")
        assert len(catalog_templates) >= 4
        assert all(t.category == "catalog" for t in catalog_templates)

    def test_list_by_category_document(self) -> None:
        """Фильтр по category='document'."""
        doc_templates = list_templates(category="document")
        assert len(doc_templates) >= 3
        assert all(t.category == "document" for t in doc_templates)

    def test_list_by_category_query(self) -> None:
        """Фильтр по category='query'."""
        query_templates = list_templates(category="query")
        assert len(query_templates) >= 3

    def test_list_unknown_category_returns_empty(self) -> None:
        """Неизвестная category → пустой список."""
        assert list_templates(category="nonexistent") == []


# ============================================================================
# Catalog templates tests
# ============================================================================


class TestCatalogTemplates:
    """Тесты шаблонов справочников."""

    def test_catalog_find_by_code(self) -> None:
        code = BSLTemplates.catalog_find_by_code(
            catalog_name="Номенклатура", code_var="КодТовара"
        )
        assert "Номенклатура" in code
        assert "Справочник.Номенклатура" in code
        assert "Функция" in code
        assert "КонецФункции" in code

    def test_catalog_find_by_name(self) -> None:
        code = BSLTemplates.catalog_find_by_name(
            catalog_name="Контрагенты", name_var="Имя"
        )
        assert "Контрагенты" in code
        assert "Наименование" in code  # всегда Наименование в BSL коде

    def test_catalog_create_element(self) -> None:
        code = BSLTemplates.catalog_create_element(catalog_name="Склады")
        assert "Склады" in code
        assert "СоздатьЭлемент" in code
        assert "Записать" in code

    def test_catalog_find_or_create(self) -> None:
        code = BSLTemplates.catalog_find_or_create(catalog_name="СтавкиНДС")
        assert "СтавкиНДС" in code
        assert "НайтиИлиСоздать" in code
        assert "СоздатьЭлемент" in code

    def test_catalog_find_by_code_includes_validation(self) -> None:
        """Шаблон включает проверку пустого кода."""
        code = BSLTemplates.catalog_find_by_code(catalog_name="Номенклатура")
        assert "ПустаяСтрока" in code or "ПустаяСтрок" in code


# ============================================================================
# Document templates tests
# ============================================================================


class TestDocumentTemplates:
    """Тесты шаблонов документов."""

    def test_document_create_with_header(self) -> None:
        code = BSLTemplates.document_create_with_header(document_name="Продажа")
        assert "Продажа" in code
        assert "Документы.Продажа" in code
        assert "СоздатьДокумент" in code

    def test_document_fill_tabular_section(self) -> None:
        code = BSLTemplates.document_fill_tabular_section(
            document_name="Заказ", tabular_name="Услуги"
        )
        assert "Заказ" in code
        assert "Услуги" in code
        assert "Очистить" in code

    def test_document_fill_tabular_default(self) -> None:
        """Default tabular_name='Товары'."""
        code = BSLTemplates.document_fill_tabular_section(document_name="Заказ")
        assert "Товары" in code

    def test_document_post_with_validation(self) -> None:
        code = BSLTemplates.document_post_with_validation(document_name="Приход")
        assert "Приход" in code
        assert "Проведение" in code
        assert "ЗначениеЗаполнено" in code


# ============================================================================
# Query templates tests
# ============================================================================


class TestQueryTemplates:
    """Тесты шаблонов запросов."""

    def test_query_with_filter(self) -> None:
        code = BSLTemplates.query_with_filter(
            table_name="Справочник.Номенклатура", filter_field="Артикул"
        )
        assert "Справочник.Номенклатура" in code
        assert "Артикул" in code
        assert "УстановитьПараметр" in code

    def test_query_with_grouping(self) -> None:
        code = BSLTemplates.query_with_grouping(
            table_name="Документ.Продажа.Товары",
            group_field="Номенклатура",
            sum_field="Сумма",
        )
        assert "СГРУППИРОВАТЬ ПО" in code
        assert "СУММА" in code
        assert "Номенклатура" in code

    def test_query_with_join(self) -> None:
        code = BSLTemplates.query_with_join(
            table1="Документ.Продажа",
            table2="Справочник.Номенклатура",
            join_field="Номенклатура",
        )
        assert "ЛЕВОЕ СОЕДИНЕНИЕ" in code
        assert "Документ.Продажа" in code
        assert "Справочник.Номенклатура" in code

    def test_query_with_filter_uses_parameterized_query(self) -> None:
        """Запрос использует параметризованный запрос (не конкатенация)."""
        code = BSLTemplates.query_with_filter(
            table_name="Справочник.Номенклатура", filter_field="Код"
        )
        # Должен быть &ЗначениеФильтра, а не " + ЗначениеФильтра
        assert "&ЗначениеФильтра" in code
        assert '+"' not in code  # нет конкатенации


# ============================================================================
# Output templates tests
# ============================================================================


class TestOutputTemplates:
    """Тесты шаблонов вывода."""

    def test_output_to_spreadsheet_document(self) -> None:
        code = BSLTemplates.output_to_spreadsheet_document()
        assert "ТабличныйДокумент" in code
        assert "ПостроительОтчета" in code
        assert "Процедура" in code


# ============================================================================
# Form templates tests
# ============================================================================


class TestFormTemplates:
    """Тесты шаблонов форм."""

    def test_form_open_choice_with_handler(self) -> None:
        code = BSLTemplates.form_open_choice_with_handler(catalog_name="Номенклатура")
        assert "Номенклатура" in code
        assert "ОткрытьФорму" in code
        assert "ОписаниеОповещения" in code

    def test_form_get_template_and_fill(self) -> None:
        code = BSLTemplates.form_get_template_and_fill(
            template_name="ПечатнаяФорма", area_name="Шапка"
        )
        assert "ПечатнаяФорма" in code
        assert "Шапка" in code
        assert "ПолучитьМакет" in code


# ============================================================================
# HTTP templates tests
# ============================================================================


class TestHTTPTemplates:
    """Тесты HTTP шаблонов."""

    def test_http_get_request_safe_enforces_https(self) -> None:
        """Шаблон требует HTTPS."""
        code = BSLTemplates.http_get_request_safe()
        assert "https://" in code
        assert "ЗащищенноеСоединениеOpenSSL" in code
        assert "СтрНачинаетсяС" in code

    def test_http_get_request_has_timeout(self) -> None:
        """Шаблон включает timeout."""
        code = BSLTemplates.http_get_request_safe()
        assert "30" in code  # timeout 30 секунд


# ============================================================================
# JSON templates tests
# ============================================================================


class TestJSONTemplates:
    """Тесты JSON шаблонов."""

    def test_json_read_file(self) -> None:
        code = BSLTemplates.json_read_file()
        assert "ЧтениеJSON" in code
        assert "ФайлСуществует" in code

    def test_json_write_file(self) -> None:
        code = BSLTemplates.json_write_file()
        assert "ЗаписьJSON" in code
        assert "КодировкаТекста.UTF8" in code


# ============================================================================
# Security templates tests
# ============================================================================


class TestSecurityTemplates:
    """Тесты security шаблонов."""

    def test_check_access_rights(self) -> None:
        code = BSLTemplates.check_access_rights(
            metadata_object="Справочник.Номенклатура", right_name="Чтение"
        )
        assert "ПравоДоступа" in code
        assert "Справочник.Номенклатура" in code
        assert "Чтение" in code

    def test_transaction_with_rollback(self) -> None:
        code = BSLTemplates.transaction_with_rollback()
        assert "НачатьТранзакцию" in code
        assert "ЗафиксироватьТранзакцию" in code
        assert "ОтменитьТранзакцию" in code

    def test_log_to_event_log(self) -> None:
        code = BSLTemplates.log_to_event_log(event_name="МоеСобытие")
        assert "ЗаписьЖурналаРегистрации" in code
        assert "МоеСобытие" in code


# ============================================================================
# Background job templates tests
# ============================================================================


class TestBackgroundJobTemplates:
    """Тесты шаблонов фоновых заданий."""

    def test_background_job_with_wait(self) -> None:
        code = BSLTemplates.background_job_with_wait(procedure_name="МояПроцедура")
        assert "ФоновыеЗадания.Выполнить" in code
        assert "МояПроцедура" in code
        assert "СостояниеФоновогоЗадания" in code

    def test_background_job_async(self) -> None:
        code = BSLTemplates.background_job_async(procedure_name="АсинхПроц")
        assert "ФоновыеЗадания.Выполнить" in code
        assert "АсинхПроц" in code


# ============================================================================
# BSLTemplates class tests
# ============================================================================


class TestBSLTemplatesClass:
    """Тесты BSLTemplates class."""

    def test_list_all(self) -> None:
        all_templates = BSLTemplates.list_all()
        assert len(all_templates) >= 20

    def test_list_by_category(self) -> None:
        catalog = BSLTemplates.list_by_category("catalog")
        assert len(catalog) >= 4
        assert all(t.category == "catalog" for t in catalog)

    def test_get_by_name(self) -> None:
        code = BSLTemplates.get("catalog_find_by_code", catalog_name="Товары")
        assert "Товары" in code

    def test_static_methods_callable(self) -> None:
        """Все static methods доступны и callable."""
        assert callable(BSLTemplates.catalog_find_by_code)
        assert callable(BSLTemplates.document_create_with_header)
        assert callable(BSLTemplates.query_with_filter)


# ============================================================================
# BSL code validity tests
# ============================================================================


class TestBSLCodeValidity:
    """Проверка что генерируемый код — валидный BSL."""

    @pytest.mark.parametrize("template_name", sorted(_TEMPLATES.keys()))
    def test_all_templates_return_non_empty_string(self, template_name: str) -> None:
        """Все шаблоны возвращают непустую строку."""
        # Получаем параметры шаблона
        info = _TEMPLATES[template_name]
        # Создаём dummy значения для всех параметров
        kwargs = dict.fromkeys(info.parameters, "test_value")
        code = get_template(template_name, **kwargs)
        assert isinstance(code, str)
        assert len(code) > 50   # BSL код должен быть существенным

    @pytest.mark.parametrize("template_name", sorted(_TEMPLATES.keys()))
    def test_all_templates_have_bsl_keywords(self, template_name: str) -> None:
        """Все шаблоны содержат BSL-ключевые слова."""
        info = _TEMPLATES[template_name]
        kwargs = dict.fromkeys(info.parameters, "test_value")
        code = get_template(template_name, **kwargs)
        # BSL код должен содержать хотя бы одно ключевое слово
        bsl_keywords = [
            "Функция", "Процедура", "КонецФункции", "КонецПроцедуры",
            "Если", "Тогда", "КонецЕсли", "Для", "Цикл", "КонецЦикла",
            "Попытка", "Исключение", "КонецПопытки", "Возврат",
            "Новый", "Экспорт",
        ]
        assert any(kw in code for kw in bsl_keywords), (
            f"Template '{template_name}' has no BSL keywords"
        )

    def test_all_templates_have_comments(self) -> None:
        """Все шаблоны начинаются с комментария (документация)."""
        for name, info in _TEMPLATES.items():
            kwargs = dict.fromkeys(info.parameters, "test_value")
            code = get_template(name, **kwargs)
            first_line = code.strip().split("\n")[0]
            assert first_line.startswith("//"), (
                f"Template '{name}' should start with comment, got: {first_line[:50]}"
            )


# ============================================================================
# Categories distribution tests
# ============================================================================


class TestCategories:
    """Проверка распределения шаблонов по категориям."""

    def test_all_expected_categories_present(self) -> None:
        """Все ожидаемые категории представлены."""
        categories = {t.category for t in _TEMPLATES.values()}
        expected = {"catalog", "document", "query", "output", "form",
                    "http", "json", "security", "background"}
        assert expected.issubset(categories), (
            f"Missing categories: {expected - categories}"
        )

    def test_catalog_category_has_at_least_4(self) -> None:
        """Категория 'catalog' содержит минимум 4 шаблона."""
        assert len(list_templates("catalog")) >= 4

    def test_document_category_has_at_least_3(self) -> None:
        assert len(list_templates("document")) >= 3

    def test_query_category_has_at_least_3(self) -> None:
        assert len(list_templates("query")) >= 3

    def test_security_category_has_at_least_3(self) -> None:
        assert len(list_templates("security")) >= 3
