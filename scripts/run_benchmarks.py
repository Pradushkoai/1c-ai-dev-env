"""
P2.4: Benchmark скрипт для измерения производительности MCP tools.

Измеряет:
- Время индексации конфигурации
- Размер индексов (metadata, api, skd, form, depgraph)
- Latency MCP tools (search_1c_methods, get_api_reference, depgraph query)

Использование:
    python scripts/run_benchmarks.py --config ut11 --output docs/benchmark_results.json
    python scripts/run_benchmarks.py --config ut11 --compare baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def benchmark_search(project: Any, query: str, limit: int = 10) -> dict[str, Any]:
    """Измерить latency search_1c_methods.

    Returns:
        {query, limit, latency_ms, results_count}
    """
    start = time.monotonic()
    results = project.search_methods(query, limit=limit)
    latency = (time.monotonic() - start) * 1000  # ms

    return {
        "query": query,
        "limit": limit,
        "latency_ms": round(latency, 2),
        "results_count": len(results),
    }


def benchmark_api_reference(project: Any, config_name: str) -> dict[str, Any]:
    """Измерить latency get_api_reference.

    Returns:
        {config_name, latency_ms, modules_count, methods_count}
    """
    start = time.monotonic()
    modules = project.get_api_methods(config_name)
    latency = (time.monotonic() - start) * 1000

    return {
        "config_name": config_name,
        "latency_ms": round(latency, 2),
        "modules_count": len(modules),
        "methods_count": sum(1 for m in modules for _ in m.get("methods", []) or [m]),
    }


def benchmark_list_configs(project: Any) -> dict[str, Any]:
    """Измерить latency list_configs.

    Returns:
        {latency_ms, configs_count}
    """
    start = time.monotonic()
    configs = project.list_configs_info()
    latency = (time.monotonic() - start) * 1000

    return {
        "latency_ms": round(latency, 2),
        "configs_count": len(configs),
    }


def run_benchmarks(
    config_name: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Запустить все benchmarks.

    Args:
        config_name: Имя конфигурации для тестов (если None — только list_configs).
        output_path: Путь для сохранения результатов JSON.

    Returns:
        Словарь с результатами всех benchmarks.
    """
    from src.project import Project

    project = Project.from_cwd()
    results: dict[str, Any] = {
        "version": "1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config_name": config_name,
        "benchmarks": {},
    }

    # 1. list_configs latency
    print("=== Benchmark: list_configs ===")
    results["benchmarks"]["list_configs"] = benchmark_list_configs(project)
    print(f"  Latency: {results['benchmarks']['list_configs']['latency_ms']}ms")

    if config_name:
        # 2. get_api_reference latency
        print(f"=== Benchmark: get_api_reference ({config_name}) ===")
        try:
            results["benchmarks"]["get_api_reference"] = benchmark_api_reference(project, config_name)
            print(f"  Latency: {results['benchmarks']['get_api_reference']['latency_ms']}ms")
        except Exception as e:
            results["benchmarks"]["get_api_reference"] = {"error": str(e)}
            print(f"  Error: {e}")

        # 3. search_1c_methods latency (несколько запросов)
        print("=== Benchmark: search_1c_methods ===")
        queries = [
            "найти элемент по коду",
            "создать справочник",
            "выполнить запрос",
            "открыть форму",
            "получить значение реквизита",
        ]
        search_results: list[dict] = []
        for q in queries:
            r = benchmark_search(project, q)
            search_results.append(r)
            print(f"  '{q}': {r['latency_ms']}ms, {r['results_count']} results")
        results["benchmarks"]["search_1c_methods"] = search_results

    # 4. Index sizes
    print("=== Index sizes ===")
    index_sizes: dict[str, int] = {}
    for index_name in ["fast-search-index.json", "syntax-helper-index.json"]:
        index_path = project.paths.fast_search_index
        if index_path.exists():
            index_sizes[index_name] = index_path.stat().st_size
            print(f"  {index_name}: {index_sizes[index_name]} bytes")

    if config_name:
        derived_dir = project.paths.config_derived_dir(config_name)
        for index_file in [
            "unified-metadata-index.json",
            "api-reference.json",
            "skd-index.json",
            "form-index.json",
            "dependency-graph.json",
        ]:
            idx_path = derived_dir / index_file
            if idx_path.exists():
                index_sizes[f"{config_name}/{index_file}"] = idx_path.stat().st_size
                print(f"  {config_name}/{index_file}: {idx_path.stat().st_size} bytes")

    results["benchmarks"]["index_sizes"] = index_sizes

    # Save results
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nResults saved to: {output_path}")

    return results


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run benchmarks for 1c-ai-dev-env MCP tools (P2.4)")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Configuration name for benchmarks (e.g., ut11)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/benchmark_results.json"),
        help="Output JSON file for results",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="Compare with baseline JSON file",
    )

    args = parser.parse_args()

    results = run_benchmarks(config_name=args.config, output_path=args.output)

    # Compare with baseline if provided
    if args.compare and args.compare.exists():
        print(f"\n=== Comparison with baseline: {args.compare} ===")
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))

        # Compare list_configs latency
        current_lc = results["benchmarks"].get("list_configs", {})
        baseline_lc = baseline.get("benchmarks", {}).get("list_configs", {})
        if current_lc and baseline_lc:
            delta = current_lc.get("latency_ms", 0) - baseline_lc.get("latency_ms", 0)
            pct = (delta / baseline_lc.get("latency_ms", 1)) * 100 if baseline_lc.get("latency_ms") else 0
            print(f"  list_configs: {current_lc['latency_ms']}ms vs {baseline_lc['latency_ms']}ms ({pct:+.1f}%)")

    print("\n=== Benchmarks complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
