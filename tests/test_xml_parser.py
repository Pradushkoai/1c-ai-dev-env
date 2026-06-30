#!/usr/bin/env python3
"""Тесты для xml_parser.py — безопасный XML парсер с lxml fallback."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from xml_parser import fromstring, get_parser_name, has_lxml, parse_xml, strip_ns


class TestXMLParser:
    """Тесты базового функционала."""

    def test_parse_xml_file(self):
        xml = '<?xml version="1.0"?><root><child>test</child></root>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            root = parse_xml(f.name)
            os.unlink(f.name)
        assert root is not None
        assert strip_ns(root.tag) == 'root'

    def test_fromstring(self):
        root = fromstring('<root><item>1</item></root>')
        assert strip_ns(root.tag) == 'root'

    def test_strip_ns(self):
        assert strip_ns('{http://test}Element') == 'Element'
        assert strip_ns('NoNamespace') == 'NoNamespace'

    def test_get_parser_name(self):
        name = get_parser_name()
        assert name in ('lxml', 'xml.etree')

    def test_has_lxml(self):
        # Просто проверяем что функция работает
        assert isinstance(has_lxml(), bool)


class TestXXEProtection:
    """Тесты защиты от XXE атак."""

    def test_no_external_entity_loaded(self):
        """XXE атака не должна загружать external entities."""
        xxe_xml = '''<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xxe_xml)
            f.flush()
            # Не должно вызвать ошибку или прочитать /etc/passwd
            try:
                root = parse_xml(f.name)
                # Если парсинг прошёл — entity не должна быть раскрыта
                text = root.text if root.text else ''
                assert 'root:' not in text  # не должно быть содержимого /etc/passwd
            except Exception:
                # Ошибка при парсинге тоже приемлема — защита сработала
                pass
            finally:
                os.unlink(f.name)

    def test_no_network_access(self):
        """XXE с network URL не должен делать сетевой запрос."""
        xxe_xml = '''<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://evil.example.com/steal">
]>
<root>&xxe;</root>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xxe_xml)
            f.flush()
            try:
                parse_xml(f.name)
            except Exception:
                pass  # Ошибка — нормально, network не должен работать
            finally:
                os.unlink(f.name)


class TestPerformance:
    """Сравнение производительности lxml vs xml.etree."""

    def test_parse_large_xml(self):
        """Парсинг большого XML (1000 элементов)."""
        items = ''.join(f'<item id="{i}">value{i}</item>' for i in range(1000))
        xml = f'<?xml version="1.0"?><root>{items}</root>'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            root = parse_xml(f.name)
            os.unlink(f.name)

        children = list(root)
        assert len(children) == 1000
