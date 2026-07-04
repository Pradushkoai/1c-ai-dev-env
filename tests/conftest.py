"""
Pytest конфигурация.
После `pip install -e .` пакет `src` доступен для импорта без sys.path хаков.
"""

import sys


def pytest_runtest_teardown(item, nextitem):
    """Cleanup: удаляем динамически загруженные модули из sys.modules после каждого теста.

    Фиксура scope='module' в test_check_standards.py загружает check_1c_standards
    в sys.modules, что загрязняет последующие тесты (test_solve и др.).
    Этот cleanup удаляет такие модули после каждого теста.
    """
    # Модули, которые могут быть загружены динамически и загрязнять sys.modules
    _dynamic_modules = [
        "check_1c_standards",
        "check_metadata_standards",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "security_auditor",
        "code_metrics",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "transaction_checker",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "query_analyzer",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "architecture_analyzer",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "form_quality_checker",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "skd_quality_checker",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "diff_analyzer",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "code_generator",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "code_validator",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "epf_builder",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "cf_extractor",
        "metadata_extractor",
        "skd_parser",
        "form_analyzer",
        "build_api_reference",
        "build_config_index_generic",
        "cf_to_xml_adapter",
        "improved_cf_adapter",
        "v8_metadata_parser",
        "xml_parser",
        "img_grid",
        "hbk_extractor",
        "fast_search_1c",
        "form_indexer",
    ]
    for mod_name in _dynamic_modules:
        sys.modules.pop(mod_name, None)
