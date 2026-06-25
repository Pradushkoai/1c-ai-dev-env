"""
Pytest конфигурация: добавляем setup/ в sys.path,
чтобы setup_src был импортируем как пакет.
"""
import sys
from pathlib import Path

# setup/ — родитель setup_src/
SETUP_DIR = Path(__file__).parent.parent
if str(SETUP_DIR) not in sys.path:
    sys.path.insert(0, str(SETUP_DIR))
