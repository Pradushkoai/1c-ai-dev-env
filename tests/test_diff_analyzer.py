#!/usr/bin/env python3
"""Тесты для diff_analyzer.py."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from diff_analyzer import ConfigDiff, DiffAnalyzer, ObjectChange


@pytest.fixture
def analyzer():
    return DiffAnalyzer()


class TestAddedObjects:
    def test_added_catalog_detected(self, analyzer):
        old = {"objects": {"Catalogs": [{"name": "Старый", "child_objects": {}}]}}
        new = {
            "objects": {"Catalogs": [{"name": "Старый", "child_objects": {}}, {"name": "Новый", "child_objects": {}}]}
        }
        diff = analyzer.compare_data(old, new)
        assert len(diff.added_objects) == 1
        assert diff.added_objects[0].object_name == "Новый"

    def test_no_added_when_same(self, analyzer):
        old = {"objects": {"Catalogs": [{"name": "Тест", "child_objects": {}}]}}
        new = {"objects": {"Catalogs": [{"name": "Тест", "child_objects": {}}]}}
        diff = analyzer.compare_data(old, new)
        assert len(diff.added_objects) == 0


class TestRemovedObjects:
    def test_removed_catalog_detected(self, analyzer):
        old = {
            "objects": {
                "Catalogs": [{"name": "Удалённый", "child_objects": {}}, {"name": "Остался", "child_objects": {}}]
            }
        }
        new = {"objects": {"Catalogs": [{"name": "Остался", "child_objects": {}}]}}
        diff = analyzer.compare_data(old, new)
        assert len(diff.removed_objects) == 1
        assert diff.removed_objects[0].object_name == "Удалённый"


class TestModifiedObjects:
    def test_added_attribute_detected(self, analyzer):
        old = {
            "objects": {
                "Catalogs": [{"name": "Тест", "child_objects": {"attributes": [{"name": "Рекв1", "types": []}]}}]
            }
        }
        new = {
            "objects": {
                "Catalogs": [
                    {
                        "name": "Тест",
                        "child_objects": {
                            "attributes": [{"name": "Рекв1", "types": []}, {"name": "Рекв2", "types": []}]
                        },
                    }
                ]
            }
        }
        diff = analyzer.compare_data(old, new)
        assert len(diff.modified_objects) == 1
        assert any("Рекв2" in d for d in diff.modified_objects[0].details)

    def test_removed_attribute_detected(self, analyzer):
        old = {
            "objects": {
                "Catalogs": [{"name": "Тест", "child_objects": {"attributes": [{"name": "Рекв1"}, {"name": "Рекв2"}]}}]
            }
        }
        new = {"objects": {"Catalogs": [{"name": "Тест", "child_objects": {"attributes": [{"name": "Рекв1"}]}}]}}
        diff = analyzer.compare_data(old, new)
        assert len(diff.modified_objects) == 1
        assert any("Рекв2" in d for d in diff.modified_objects[0].details)

    def test_synonym_changed_detected(self, analyzer):
        old = {"objects": {"Catalogs": [{"name": "Тест", "synonym": "Старый", "child_objects": {}}]}}
        new = {"objects": {"Catalogs": [{"name": "Тест", "synonym": "Новый", "child_objects": {}}]}}
        diff = analyzer.compare_data(old, new)
        assert len(diff.modified_objects) == 1
        assert any("синоним" in d.lower() for d in diff.modified_objects[0].details)

    def test_no_changes_when_identical(self, analyzer):
        old = {
            "objects": {
                "Catalogs": [
                    {
                        "name": "Тест",
                        "synonym": "Синоним",
                        "child_objects": {"attributes": [{"name": "А"}], "forms": [{"name": "Ф"}]},
                    }
                ]
            }
        }
        new = {
            "objects": {
                "Catalogs": [
                    {
                        "name": "Тест",
                        "synonym": "Синоним",
                        "child_objects": {"attributes": [{"name": "А"}], "forms": [{"name": "Ф"}]},
                    }
                ]
            }
        }
        diff = analyzer.compare_data(old, new)
        assert len(diff.modified_objects) == 0


class TestRolesSubsystems:
    def test_added_role_detected(self, analyzer):
        old = {"objects": {}, "roles": [{"name": "СтараяРоль"}]}
        new = {"objects": {}, "roles": [{"name": "СтараяРоль"}, {"name": "НоваяРоль"}]}
        diff = analyzer.compare_data(old, new)
        assert diff.added_roles == 1

    def test_removed_subsystem_detected(self, analyzer):
        old = {"objects": {}, "subsystems": [{"name": "Подсистема1"}, {"name": "Подсистема2"}]}
        new = {"objects": {}, "subsystems": [{"name": "Подсистема1"}]}
        diff = analyzer.compare_data(old, new)
        assert diff.removed_subsystems == 1

    def test_added_event_subscription(self, analyzer):
        old = {"objects": {}, "event_subscriptions": []}
        new = {"objects": {}, "event_subscriptions": [{"name": "НоваяПодписка"}]}
        diff = analyzer.compare_data(old, new)
        assert diff.added_event_subscriptions == 1

    def test_removed_scheduled_job(self, analyzer):
        old = {"objects": {}, "scheduled_jobs": [{"name": "Задание1"}, {"name": "Задание2"}]}
        new = {"objects": {}, "scheduled_jobs": [{"name": "Задание1"}]}
        diff = analyzer.compare_data(old, new)
        assert diff.removed_scheduled_jobs == 1


class TestSummary:
    def test_summary_calculated(self, analyzer):
        old = {"objects": {"Catalogs": [{"name": "А", "child_objects": {}}]}}
        new = {"objects": {"Catalogs": [{"name": "А", "child_objects": {}}, {"name": "Б", "child_objects": {}}]}}
        diff = analyzer.compare_data(old, new)
        assert diff.summary["total_added"] == 1
        assert diff.summary["total_removed"] == 0


class TestFormatReport:
    def test_report_has_content(self, analyzer):
        diff = ConfigDiff(
            added_objects=[ObjectChange("added", "Catalogs", "Новый")],
            removed_objects=[ObjectChange("removed", "Documents", "Старый")],
        )
        diff.summary = {"total_added": 1, "total_removed": 1, "total_modified": 0}
        report = analyzer.format_report(diff)
        assert "Новый" in report
        assert "Старый" in report
        assert "ДОБАВЛЕННЫЕ" in report
        assert "УДАЛЁННЫЕ" in report
