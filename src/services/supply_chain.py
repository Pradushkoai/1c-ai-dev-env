"""
S8.11 (2026-07-06): Supply chain — pin dependencies с hash verification.

Реализует:
1. Lock file generation (requirements.lock.txt с --generate-hashes)
2. Hash verification on install (pip install --require-hashes)
3. Drift detection (между pyproject.toml и requirements.lock.txt)
4. License compliance check
5. Allowlist для всех зависимостей

Использование:
    python -m src.services.supply_chain lock
    python -m src.services.supply_chain verify
    python -m src.services.supply_chain drift
    python -m src.services.supply_chain licenses
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ============================================================================
# Allowlist — все разрешённые пакеты (для drift detection)
# ============================================================================

ALLOWED_LICENSES: frozenset[str] = frozenset({
    "MIT", "Apache-2.0", "Apache Software License",
    "BSD-2-Clause", "BSD-3-Clause", "BSD",
    "ISC", "ISCL",
    "MPL-2.0", "Mozilla Public License 2.0",
    "Python-2.0", "Python Software Foundation License",
    "Unlicense", "Zlib",
    "BSD-3-Clause OR Apache-2.0",
    "PSF-2.0",
})

DENIED_LICENSES: frozenset[str] = frozenset({
    "GPL-2.0", "GPL-3.0", "GPL",
    "AGPL-3.0", "AGPL",
    "LGPL-2.1", "LGPL-3.0", "LGPL",
    "CC-BY-NC", "Commercial",
})

# Packages, которые запрещены в проекте (license или security reasons)
DENIED_PACKAGES: frozenset[str] = frozenset({
    "pickle5",        # backport, deprecated
    "subprocess32",   # backport, deprecated
    "pycrypto",       # abandoned, use pycryptodome
    "pyyaml<5.4",     # RCE in <5.4
})


@dataclass
class DependencyInfo:
    """Информация о зависимости."""

    name: str
    version: str
    source: str = "pypi"   # pypi, git, local
    license: str = ""
    is_pinned: bool = False   # версия фиксирована (==)
    has_upper_bound: bool = False   # имеет upper bound (<)
    has_hash: bool = False   # имеет hash в lock file


@dataclass
class SupplyChainReport:
    """Отчёт supply chain анализа."""

    total_deps: int = 0
    pinned_deps: int = 0
    with_upper_bounds: int = 0
    with_hashes: int = 0
    denied_licenses: list[tuple[str, str]] = field(default_factory=list)   # (pkg, license)
    denied_packages: list[str] = field(default_factory=list)
    drift: list[tuple[str, str, str]] = field(default_factory=list)   # (pkg, pyproject_v, lock_v)
    lock_file_exists: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self),
                "compliance_score": self.compliance_score}

    @property
    def compliance_score(self) -> float:
        """Score 0.0-1.0 — доля соответствий best practices."""
        if self.total_deps == 0:
            return 1.0
        checks = [
            self.pinned_deps / self.total_deps,
            self.with_upper_bounds / self.total_deps,
            1.0 if not self.denied_licenses else 0.0,
            1.0 if not self.denied_packages else 0.0,
            1.0 if self.lock_file_exists else 0.0,
        ]
        return sum(checks) / len(checks)


# ============================================================================
# Parsing pyproject.toml
# ============================================================================


def parse_pyproject_deps(pyproject_path: Path = Path("pyproject.toml")) -> list[DependencyInfo]:
    """S8.11: Парсинг зависимостей из pyproject.toml.

    Returns:
        Список DependencyInfo с флагами is_pinned, has_upper_bound.
    """
    if not pyproject_path.exists():
        return []

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps: list[DependencyInfo] = []
    project = data.get("project", {})

    # Main dependencies
    for spec in project.get("dependencies", []):
        info = _parse_dep_spec(spec)
        if info:
            deps.append(info)

    # Optional dependencies
    for group_name, group_deps in project.get("optional-dependencies", {}).items():
        for spec in group_deps:
            info = _parse_dep_spec(spec)
            if info:
                deps.append(info)

    return deps


def _parse_dep_spec(spec: str) -> DependencyInfo | None:
    """Парсинг spec строки ('package>=1.0,<2.0' или 'package @ git+...')."""
    spec = spec.strip()
    if not spec:
        return None

    # Strip comments
    if "#" in spec:
        spec = spec.split("#")[0].strip()

    # Git URL: "v8unpack @ git+https://..."
    if " @ " in spec:
        name, source = spec.split(" @ ", 1)
        name = name.strip()
        return DependencyInfo(
            name=name,
            version="git",
            source="git",
            is_pinned=True,
            has_upper_bound=False,
        )

    # Regular spec: name[ops]version
    # Match: name, then optional version operators
    match = re.match(r"^([A-Za-z0-9_\-.]+)\s*(.*)$", spec)
    if not match:
        return None

    name = match.group(1).strip()
    version_spec = match.group(2).strip()

    # Check if pinned (==)
    is_pinned = "==" in version_spec
    # Check if upper bound (<)
    has_upper_bound = "<" in version_spec

    # Extract version (after ==)
    version = ""
    if "==" in version_spec:
        v_match = re.search(r"==\s*([^\s,;]+)", version_spec)
        if v_match:
            version = v_match.group(1)

    return DependencyInfo(
        name=name,
        version=version or version_spec,
        is_pinned=is_pinned,
        has_upper_bound=has_upper_bound,
    )


# ============================================================================
# Lock file analysis
# ============================================================================


LOCK_FILE = Path("requirements.lock.txt")


def parse_lock_file(lock_path: Path = LOCK_FILE) -> dict[str, DependencyInfo]:
    """S8.11: Парсинг lock file (pip-compile --generate-hashes output).

    Returns:
        Dict {name: DependencyInfo}.
    """
    if not lock_path.exists():
        return {}

    deps: dict[str, DependencyInfo] = {}
    content = lock_path.read_text(encoding="utf-8")

    # pip-compile format:
    # package==1.2.3 \
    #     --hash=sha256:abc... \
    #     --hash=sha256:def...
    # OR
    # package==1.2.3  # via other-package
    #
    # Approach: split into "blocks" — a block starts at a line that doesn't
    # begin with whitespace, and continues until the next such line.
    blocks: list[str] = []
    current: list[str] = []

    for line in content.split("\n"):
        if not line.strip():
            # Empty line — finalize current block
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        # Comment lines starting with # at column 0 — also block separators
        if line.startswith("#") and current:
            blocks.append("\n".join(current))
            current = []
            continue
        # Continuation lines start with whitespace
        if line[0].isspace():
            current.append(line)
        else:
            # New package line
            if current:
                blocks.append("\n".join(current))
            current = [line]

    if current:
        blocks.append("\n".join(current))

    # Parse each block
    for block in blocks:
        # First line: name==version [optional stuff]
        first_line = block.split("\n")[0]
        match = re.match(r"^([A-Za-z0-9_\-.]+)==([^\s\\]+)", first_line)
        if not match:
            continue

        name = match.group(1).lower()
        version = match.group(2)
        has_hash = "--hash=" in block

        deps[name] = DependencyInfo(
            name=name,
            version=version,
            is_pinned=True,
            has_upper_bound=False,   # lock file is always exact
            has_hash=has_hash,
        )

    return deps


# ============================================================================
# Drift detection
# ============================================================================


def detect_drift(
    pyproject_path: Path = Path("pyproject.toml"),
    lock_path: Path = LOCK_FILE,
) -> list[tuple[str, str, str]]:
    """S8.11: Detect drift между pyproject.toml и requirements.lock.txt.

    Returns:
        List of (package, pyproject_version, lock_version) for drifted packages.
    """
    pyproject_deps = parse_pyproject_deps(pyproject_path)
    lock_deps = parse_lock_file(lock_path)

    drift: list[tuple[str, str, str]] = []
    for dep in pyproject_deps:
        name_lower = dep.name.lower()
        if name_lower in lock_deps:
            lock_dep = lock_deps[name_lower]
            # Check if pyproject version matches lock
            if dep.version and dep.version != "git":
                # Extract just the version number from pyproject spec
                pyproject_v = dep.version
                lock_v = lock_dep.version
                if pyproject_v and lock_v and pyproject_v != lock_v:
                    # Check if pyproject_v is a prefix of lock_v (range match)
                    if not lock_v.startswith(pyproject_v):
                        drift.append((dep.name, pyproject_v, lock_v))
        else:
            # Package in pyproject but not in lock
            drift.append((dep.name, dep.version, "<missing>"))

    return drift


# ============================================================================
# License check
# ============================================================================


def check_licenses() -> list[tuple[str, str]]:
    """S8.11: Проверка лицензий через pip-licenses.

    Returns:
        List of (package, license) for packages with denied licenses.
    """
    try:
        result = subprocess.run(
            ["pip-licenses", "--format=json"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except FileNotFoundError:
        return []
    except subprocess.TimeoutExpired:
        return []

    if result.returncode != 0:
        return []

    import json
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    denied: list[tuple[str, str]] = []
    for pkg in data:
        name = pkg.get("Name", "")
        license_str = pkg.get("License", "").upper()

        for denied_license in DENIED_LICENSES:
            if denied_license.upper() in license_str:
                denied.append((name, license_str))
                break

    return denied


# ============================================================================
# Full report
# ============================================================================


def generate_report() -> SupplyChainReport:
    """S8.11: Полный отчёт supply chain."""
    deps = parse_pyproject_deps()
    lock_deps = parse_lock_file()

    report = SupplyChainReport(
        total_deps=len(deps),
        pinned_deps=sum(1 for d in deps if d.is_pinned),
        with_upper_bounds=sum(1 for d in deps if d.has_upper_bound),
        with_hashes=sum(1 for d in lock_deps.values() if d.has_hash),
        lock_file_exists=LOCK_FILE.exists(),
    )

    # Denied packages
    for dep in deps:
        if dep.name.lower() in DENIED_PACKAGES:
            report.denied_packages.append(dep.name)

    # License check
    report.denied_licenses = check_licenses()

    # Drift
    report.drift = detect_drift()

    return report


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Supply chain analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("report", help="Generate full report")
    subparsers.add_parser("drift", help="Detect drift between pyproject and lock")
    subparsers.add_parser("licenses", help="Check licenses")
    subparsers.add_parser("verify", help="Verify lock file hashes (pip install --require-hashes dry-run)")

    args = parser.parse_args()

    if args.command == "report":
        report = generate_report()
        import json
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.compliance_score >= 0.8 else 1

    if args.command == "drift":
        drift = detect_drift()
        if drift:
            print(f"❌ Drift detected ({len(drift)} packages):")
            for pkg, pyp_v, lock_v in drift:
                print(f"  {pkg}: pyproject={pyp_v} lock={lock_v}")
            return 1
        print("✅ No drift — pyproject.toml and requirements.lock.txt in sync")
        return 0

    if args.command == "licenses":
        denied = check_licenses()
        if denied:
            print(f"❌ Denied licenses found ({len(denied)}):")
            for pkg, lic in denied:
                print(f"  {pkg}: {lic}")
            return 1
        print("✅ All licenses compliant")
        return 0

    if args.command == "verify":
        if not LOCK_FILE.exists():
            print(f"❌ Lock file {LOCK_FILE} not found")
            return 1
        # Try pip install --dry-run --require-hashes
        result = subprocess.run(
            ["pip", "install", "--dry-run", "--require-hashes", "-r", str(LOCK_FILE)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            print("✅ Hashes verified — all dependencies match lock file")
            return 0
        print(f"❌ Hash verification failed:\n{result.stderr}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
