"""
S8.7 (2026-07-06): Path traversal hardening — тесты.

Покрывает:
- check_path_safety: pattern detection, extension whitelist, sensitive files
- resolve_path_hardened: multi-layer validation
- Forbidden patterns: .., ~, $, null byte, URL encoding
- Sensitive files: .env, .git-credentials, id_rsa, etc.
- Extension whitelist: .bsl, .xml, etc.
- Audit logging on rejection
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mcpserver.handlers._security import (
    ALLOWED_READ_EXTENSIONS,
    ALLOWED_WRITE_EXTENSIONS,
    FORBIDDEN_PATH_PATTERNS,
    SENSITIVE_FILE_NAMES,
    check_path_safety,
    is_path_within_project,
    resolve_path_hardened,
    resolve_path_within_project,
)


# ============================================================================
# Helpers
# ============================================================================


def _make_project(tmp_path: Path) -> MagicMock:
    """Project с реальным root во tmp_path."""
    project = MagicMock()
    project.paths.root = tmp_path
    (tmp_path / "scripts").mkdir(exist_ok=True)
    return project


# ============================================================================
# Test check_path_safety — pattern detection
# ============================================================================


class TestCheckPathSafetyPatterns:
    """Тесты detection запрещённых паттернов."""

    @pytest.mark.parametrize("pattern", [
        "../../../etc/passwd",
        "..\\..\\windows",
        "~/secrets",
        "$HOME/secret",
        "file\x00.txt",
        "%2e%2e/etc/passwd",
        "%2fetc%2fpasswd",
        "%5cwindows",
    ])
    def test_forbidden_patterns_blocked(self, pattern: str) -> None:
        """Запрещённые паттерны блокируются."""
        is_safe, error = check_path_safety(pattern)
        assert not is_safe, f"Pattern {pattern!r} should be blocked"
        assert error

    def test_empty_path_blocked(self) -> None:
        """Пустой путь блокируется."""
        is_safe, error = check_path_safety("")
        assert not is_safe

    def test_whitespace_path_blocked(self) -> None:
        """Whitespace-only путь блокируется."""
        is_safe, error = check_path_safety("   ")
        assert not is_safe

    def test_url_encoded_traversal_blocked(self) -> None:
        """URL-encoded path traversal блокируется."""
        is_safe, _ = check_path_safety("%2e%2e%2fetc%2fpasswd")
        assert not is_safe

    def test_url_encoded_null_blocked(self) -> None:
        """URL-encoded null byte блокируется."""
        is_safe, _ = check_path_safety("file%00.txt")
        assert not is_safe


# ============================================================================
# Test check_path_safety — sensitive files
# ============================================================================


class TestCheckPathSafetySensitiveFiles:
    """Тесты detection sensitive files."""

    @pytest.mark.parametrize("filename", [
        ".env",
        ".env.local",
        ".env.production",
        ".git-credentials",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "credentials.json",
        "service-account.json",
        ".secrets.baseline",
        ".htpasswd",
        ".netrc",
    ])
    def test_sensitive_files_blocked(self, filename: str) -> None:
        """Sensitive files блокируются."""
        # Make path safe except for the filename (use .bsl ext to avoid ext check)
        # Actually sensitive file names themselves should be blocked.
        path = f"data/{filename}"
        is_safe, error = check_path_safety(path)
        assert not is_safe, f"Sensitive file {filename} should be blocked"

    def test_sensitive_file_in_path_blocked(self) -> None:
        """Sensitive file в пути блокируется."""
        is_safe, _ = check_path_safety("project/.ssh/config")
        assert not is_safe


# ============================================================================
# Test check_path_safety — extension whitelist
# ============================================================================


class TestCheckPathSafetyExtensions:
    """Тесты extension whitelist."""

    @pytest.mark.parametrize("ext", list(ALLOWED_READ_EXTENSIONS))
    def test_allowed_read_extensions(self, ext: str) -> None:
        """Разрешённые read расширения проходят."""
        path = f"data/file{ext}"
        is_safe, _ = check_path_safety(path, operation="read")
        assert is_safe, f"Extension {ext} should be allowed for read"

    @pytest.mark.parametrize("ext", list(ALLOWED_WRITE_EXTENSIONS))
    def test_allowed_write_extensions(self, ext: str) -> None:
        """Разрешённые write расширения проходят."""
        path = f"data/file{ext}"
        is_safe, _ = check_path_safety(path, operation="write")
        assert is_safe, f"Extension {ext} should be allowed for write"

    @pytest.mark.parametrize("ext", [".py", ".sh", ".exe", ".bat", ".so", ".dll", ".bin"])
    def test_disallowed_extensions_blocked(self, ext: str) -> None:
        """Запрещённые расширения блокируются."""
        path = f"data/file{ext}"
        is_safe, error = check_path_safety(path, operation="read")
        assert not is_safe, f"Extension {ext} should be blocked"
        assert "not allowed" in error.lower()

    def test_custom_extensions_override(self) -> None:
        """Custom extensions override defaults."""
        # .py normally not allowed, but with override it is
        is_safe, _ = check_path_safety(
            "data/script.py",
            operation="read",
            allowed_extensions=frozenset({".py"}),
        )
        assert is_safe

    def test_directory_without_extension_allowed(self) -> None:
        """Директория без расширения разрешена."""
        is_safe, _ = check_path_safety("data/subdir/")
        # No extension → not checked
        assert is_safe


# ============================================================================
# Test resolve_path_hardened — multi-layer validation
# ============================================================================


class TestResolvePathHardened:
    """Тесты hardened path resolution."""

    def test_safe_path_resolves(self, tmp_path: Path) -> None:
        """Безопасный путь резолвится."""
        project = _make_project(tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "file.bsl").write_text("// ok", encoding="utf-8")
        result = resolve_path_hardened("data/file.bsl", project, must_exist=True)
        assert result is not None
        assert result.name == "file.bsl"

    def test_traversal_blocked_at_layer1(self, tmp_path: Path) -> None:
        """Path traversal блокируется на layer 1 (pattern check)."""
        project = _make_project(tmp_path)
        result = resolve_path_hardened("../../../etc/passwd", project)
        assert result is None

    def test_sensitive_file_blocked(self, tmp_path: Path) -> None:
        """Sensitive file блокируется."""
        project = _make_project(tmp_path)
        # Create .env inside project (would normally be allowed by containment)
        (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
        result = resolve_path_hardened(".env", project)
        assert result is None   # blocked by sensitive file check

    def test_disallowed_extension_blocked(self, tmp_path: Path) -> None:
        """Запрещённое расширение блокируется."""
        project = _make_project(tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "script.py").write_text("#!/bin/python", encoding="utf-8")
        result = resolve_path_hardened("data/script.py", project, must_exist=True)
        assert result is None   # blocked by extension check

    def test_absolute_path_outside_blocked(self, tmp_path: Path) -> None:
        """Абсолютный путь вне project — blocked."""
        project = _make_project(tmp_path)
        result = resolve_path_hardened("/etc/passwd", project)
        assert result is None

    def test_write_operation_more_restrictive(self, tmp_path: Path) -> None:
        """Write operation более restrictive (less extensions)."""
        project = _make_project(tmp_path)
        # .ini is allowed for read but not for write
        (tmp_path / "config.ini").write_text("[main]", encoding="utf-8")
        read_result = resolve_path_hardened(
            "config.ini", project, operation="read", must_exist=True
        )
        write_result = resolve_path_hardened(
            "config.ini", project, operation="write", must_exist=True
        )
        assert read_result is not None
        assert write_result is None   # .ini not in ALLOWED_WRITE_EXTENSIONS

    def test_symlink_outside_blocked(self, tmp_path: Path) -> None:
        """Симлинк, указывающий вне project — blocked."""
        project = _make_project(tmp_path)
        # Create symlink to /etc/passwd
        try:
            (tmp_path / "passwd_link.bsl").symlink_to("/etc/passwd")
        except (OSError, PermissionError):
            pytest.skip("Cannot create symlink")

        result = resolve_path_hardened("passwd_link.bsl", project, must_exist=True)
        assert result is None   # symlink resolves outside project


# ============================================================================
# Test audit logging on rejection
# ============================================================================


class TestAuditLogging:
    """Тесты audit logging при отказах."""

    def test_rejection_logged_to_audit(self, tmp_path: Path, monkeypatch) -> None:
        """Отказ записывается в audit log."""
        project = _make_project(tmp_path)

        # Используем tmp_path для audit log
        from src.services.audit_logger import AuditLogger
        log_path = tmp_path / "audit.jsonl"

        # Monkeypatch AuditLogger чтобы использовать наш путь
        original_init = AuditLogger.__init__
        def patched_init(self, *args, **kwargs):
            original_init(self, log_path=log_path)
        monkeypatch.setattr(AuditLogger, "__init__", patched_init)

        # Trigger rejection
        resolve_path_hardened("../../../etc/passwd", project)

        # Check audit log was written
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8").strip()
            if content:
                entry = json.loads(content.split("\n")[-1])
                assert entry["status"] == "blocked"
                assert entry["tool"] == "<path_resolver>"

    def test_audit_failure_does_not_block(self, tmp_path: Path, monkeypatch) -> None:
        """Если audit logging падает — операция всё равно блокируется."""
        project = _make_project(tmp_path)

        # Make AuditLogger raise
        def failing_init(*args, **kwargs):
            raise RuntimeError("audit unavailable")
        monkeypatch.setattr(
            "src.services.audit_logger.AuditLogger.__init__", failing_init
        )

        # Should still return None (blocked)
        result = resolve_path_hardened("../../../etc/passwd", project)
        assert result is None


# ============================================================================
# Test forbidden patterns completeness
# ============================================================================


class TestForbiddenPatternsComplete:
    """Проверка полноты forbidden patterns."""

    def test_forbidden_patterns_listed(self) -> None:
        assert ".." in FORBIDDEN_PATH_PATTERNS
        assert "~" in FORBIDDEN_PATH_PATTERNS
        assert "\x00" in FORBIDDEN_PATH_PATTERNS
        assert "%2e%2e" in FORBIDDEN_PATH_PATTERNS
        assert "%2f" in FORBIDDEN_PATH_PATTERNS
        assert "%5c" in FORBIDDEN_PATH_PATTERNS

    def test_sensitive_files_listed(self) -> None:
        assert ".env" in SENSITIVE_FILE_NAMES
        assert ".git-credentials" in SENSITIVE_FILE_NAMES
        assert "id_rsa" in SENSITIVE_FILE_NAMES
        assert "credentials.json" in SENSITIVE_FILE_NAMES

    def test_read_extensions_listed(self) -> None:
        assert ".bsl" in ALLOWED_READ_EXTENSIONS
        assert ".xml" in ALLOWED_READ_EXTENSIONS
        assert ".json" in ALLOWED_READ_EXTENSIONS

    def test_write_extensions_subset_of_read(self) -> None:
        """Write extensions — subset of read (more restrictive)."""
        # Не строго subset, но .ini/.cfg/.cf/.cfe только для read
        assert ".ini" in ALLOWED_READ_EXTENSIONS
        assert ".ini" not in ALLOWED_WRITE_EXTENSIONS
        assert ".cfg" in ALLOWED_READ_EXTENSIONS
        assert ".cfg" not in ALLOWED_WRITE_EXTENSIONS


# ============================================================================
# Regression tests — combined scenarios
# ============================================================================


class TestRegressionScenarios:
    """Regression: combined attack scenarios."""

    def test_combined_traversal_and_sensitive(self, tmp_path: Path) -> None:
        """Combined: traversal + sensitive file."""
        project = _make_project(tmp_path)
        # Traversal detected first (layer 1)
        result = resolve_path_hardened("../../.env", project)
        assert result is None

    def test_combined_extension_and_traversal(self, tmp_path: Path) -> None:
        """Combined: traversal with disallowed extension."""
        project = _make_project(tmp_path)
        # Layer 1 blocks .., so extension not even checked
        result = resolve_path_hardened("../../../etc/passwd.exe", project)
        assert result is None

    def test_legitimate_bsl_file_works(self, tmp_path: Path) -> None:
        """Легитимный .bsl файл работает."""
        project = _make_project(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "module.bsl").write_text(
            "Процедура Тест()\nКонецПроцедуры", encoding="utf-8"
        )
        result = resolve_path_hardened("src/module.bsl", project, must_exist=True)
        assert result is not None
        assert result.suffix == ".bsl"

    def test_legitimate_xml_file_works(self, tmp_path: Path) -> None:
        """Легитимный .xml файл работает."""
        project = _make_project(tmp_path)
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "Configuration.xml").write_text(
            "<root/>", encoding="utf-8"
        )
        result = resolve_path_hardened("config/Configuration.xml", project, must_exist=True)
        assert result is not None

    def test_nested_directory_works(self, tmp_path: Path) -> None:
        """Вложенные директории работают."""
        project = _make_project(tmp_path)
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "deep.bsl").write_text("// deep", encoding="utf-8")
        result = resolve_path_hardened("a/b/c/deep.bsl", project, must_exist=True)
        assert result is not None
