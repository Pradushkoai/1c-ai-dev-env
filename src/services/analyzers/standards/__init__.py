"""
Пакет standards — правила проверки .bsl файлов на стандарты 1С.

Этап 2.1: декомпозиция god-файла check_1c_standards.py (1685 LOC) на 5 модулей:
- style: 10 правил стиля кода (no_yo, no_dashes, no_commented_code, etc.)
- architecture: 12 правил архитектуры и безопасности (no_vypolnit, no_hardcoded_credentials, etc.)
- queries: 7 правил запросов (no_pereyti, no_full_outer_join, etc.)
- client_server: 13 правил клиент-сервер (no_transaction_in_nacliente, etc.)
- misc: 20 правил разного (no_otkaz_lozh, no_deep_nesting, etc.)

Всего: 62 правил (по ALL_RULES).

Использование:
    from src.services.analyzers.standards.style import RULES as STYLE_RULES
    from src.services.analyzers.standards._common import Violation

Для обратной совместимости с tests/test_check_standards.py (который обращается
к std.rule_<name> как к атрибуту модуля) — все rule_* функции re-exported здесь.
"""

from __future__ import annotations

from ._common import Violation as Violation  # noqa: F401 — explicit re-export
from .architecture import *  # noqa: F401, F403 — re-export rule_* functions
from .architecture import RULES as ARCHITECTURE_RULES
from .client_server import *  # noqa: F401, F403
from .client_server import RULES as CLIENT_SERVER_RULES
from .misc import *  # noqa: F401, F403
from .misc import RULES as MISC_RULES
from .queries import *  # noqa: F401, F403
from .queries import RULES as QUERY_RULES
from .style import *  # noqa: F401, F403
from .style import RULES as STYLE_RULES

# Все 62 правил
ALL_RULES = STYLE_RULES + ARCHITECTURE_RULES + QUERY_RULES + CLIENT_SERVER_RULES + MISC_RULES

# __all__ НЕ определяем — чтобы `from .standards import *` экспортировал ВСЕ
# публичные имена (включая все rule_* функции) для обратной совместимости
# с tests/test_check_standards.py (обращается к std.rule_<name>).
