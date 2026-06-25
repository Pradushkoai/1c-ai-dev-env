"""
Тесты для BSLAnalyzer.
subprocess мокируется (чтобы не запускать Java/BSL LS).
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from src.services.bsl_analyzer import BSLAnalyzer, AnalysisResult, Diagnostic


def _fake_bsl_json(output_dir: Path) -> None:
    """Создать фейковый bsl-json.json в output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "fileinfos": [
            {
                "diagnostics": [
                    {
                        "code": "Typo",
                        "severity": "Info",
                        "message": "Опечатка в имени",
                        "range": {"start": {"line": 10}},
                    },
                    {
                        "code": "Typo",
                        "severity": "Info",
                        "message": "Другая опечатка",
                        "range": {"start": {"line": 20}},
                    },
                    {
                        "code": "CanonicalSpelling",
                        "severity": "Warning",
                        "message": "Каноническое написание",
                        "range": {"start": {"line": 5}},
                    },
                ]
            }
        ]
    }
    (output_dir / "bsl-json.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def test_analysis_result_from_json(tmp_path):
    """AnalysisResult.from_json корректно парсит JSON."""
    json_path = tmp_path / "result.json"
    _fake_bsl_json(tmp_path)
    # from_json ожидает bsl-json.json, переименуем
    (tmp_path / "bsl-json.json").rename(json_path)

    result = AnalysisResult.from_json(json_path)
    assert result.total == 3
    assert result.by_code.get("Typo") == 2
    assert result.by_code.get("CanonicalSpelling") == 1


def test_analysis_result_empty(tmp_path):
    """AnalysisResult.from_json для несуществующего файла → пустой результат."""
    result = AnalysisResult.from_json(tmp_path / "nope.json")
    assert result.total == 0
    assert len(result.diagnostics) == 0


def test_diagnostic_key():
    """Diagnostic.key уникален для разных сообщений."""
    d1 = Diagnostic(code="Typo", line=1, message="Ошибка 1")
    d2 = Diagnostic(code="Typo", line=1, message="Ошибка 2")
    d3 = Diagnostic(code="Typo", line=1, message="Ошибка 1")
    assert d1.key != d2.key
    assert d1.key == d3.key


def test_analyzer_analyze_with_mock(tmp_path):
    """analyze() запускает subprocess (замокано) и парсит результат."""
    analyzer = BSLAnalyzer(
        binary_path=tmp_path / "bsl-ls",
        config_path=tmp_path / "bsl.json",
        project_root=tmp_path,
    )

    def fake_run(cmd, **kwargs):
        # cmd: [binary, -c, config, analyze, -s, src, -r, json, -o, output, -q]
        # находим -o и создаём фейковый JSON
        out_idx = cmd.index("-o")
        output_dir = Path(cmd[out_idx + 1])
        _fake_bsl_json(output_dir)
        return MagicMock(returncode=0)

    with patch("src.services.bsl_analyzer.subprocess.run", side_effect=fake_run):
        result = analyzer.analyze(tmp_path)

    assert result.total == 3
    assert result.by_code["Typo"] == 2


def test_analyzer_baseline_persistence(tmp_path):
    """save_baseline + diff: baseline персистится в файл."""
    analyzer = BSLAnalyzer(
        binary_path=tmp_path / "bsl-ls",
        config_path=tmp_path / "bsl.json",
        project_root=tmp_path,
    )

    call_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        out_idx = cmd.index("-o")
        output_dir = Path(cmd[out_idx + 1])
        _fake_bsl_json(output_dir)
        return MagicMock(returncode=0)

    with patch("src.services.bsl_analyzer.subprocess.run", side_effect=fake_run):
        # Сохраняем baseline
        result = analyzer.save_baseline(tmp_path)
        assert result.total == 3
        assert analyzer.has_baseline is True

        # Файл должен существовать
        assert analyzer._baseline_path.exists()

        # Создаём новый анализатор — он должен подгрузить baseline из файла
        analyzer2 = BSLAnalyzer(
            binary_path=tmp_path / "bsl-ls",
            config_path=tmp_path / "bsl.json",
            project_root=tmp_path,
        )

        # diff должен обнаружить 0 новых (тот же результат)
        diff = analyzer2.diff(tmp_path)
        assert len(diff.new) == 0  # все диагностики уже в baseline


def test_analyzer_diff_no_baseline(tmp_path):
    """diff() без baseline → RuntimeError."""
    analyzer = BSLAnalyzer(
        binary_path=tmp_path / "bsl-ls",
        config_path=tmp_path / "bsl.json",
        project_root=tmp_path,
    )
    # Удаляем файл baseline если вдруг есть
    analyzer._baseline_path.unlink(missing_ok=True)

    with pytest.raises(RuntimeError, match="Нет baseline"):
        analyzer.diff(tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
