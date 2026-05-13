import argparse
import ast
import dis
import io
import logging
import sys
import trace
import unittest
from collections import defaultdict
from pathlib import Path
from types import CodeType


ROOT_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT_DIR / "tests"
FIXTURES_PATH = TESTS_DIR / "integration" / "fixtures.py"

CRITERIA_ORDER = [
    "Upload và lưu trữ file",
    "Queue và worker",
    "Parse và canonical mapping",
    "Docling và build structure",
    "LLM extraction",
    "Embedding và semantic search",
    "Citation graph scoring",
    "Duplicate và canonical caching",
    "Other",
]

MODULE_TO_CRITERIA = {
    "tests.integration.test_upload_and_storage_integration": "Upload và lưu trữ file",
    "tests.integration.test_queue_and_worker_integration": "Queue và worker",
    "tests.integration.test_parse_and_canonical_mapping_integration": "Parse và canonical mapping",
    "tests.integration.test_docling_and_build_structure_integration": "Docling và build structure",
    "tests.integration.test_llm_extraction_integration": "LLM extraction",
    "tests.integration.test_embedding_and_semantic_search_integration": "Embedding và semantic search",
    "tests.integration.test_citation_graph_scoring_integration": "Citation graph scoring",
    "tests.integration.test_duplicate_and_canonical_caching_integration": "Duplicate và canonical caching",
}

CRITERIA_TARGETS: dict[str, list[tuple[Path, str]]] = {
    "Upload và lưu trữ file": [
        (FIXTURES_PATH, "WorkflowHarness.upload_pdf"),
        (FIXTURES_PATH, "WorkflowHarness.paper"),
        (FIXTURES_PATH, "FakeStorageService.upload_pdf"),
        (FIXTURES_PATH, "FakeStorageService.download"),
        (FIXTURES_PATH, "FakeStorageService.list_paths"),
    ],
    "Queue và worker": [
        (FIXTURES_PATH, "FakeQueue.enqueue"),
        (FIXTURES_PATH, "FakeQueue.pop_next"),
        (FIXTURES_PATH, "FakeQueue.size"),
        (FIXTURES_PATH, "WorkflowHarness.enqueue_stage"),
    ],
    "Parse và canonical mapping": [
        (FIXTURES_PATH, "WorkflowHarness.parse_and_map"),
        (FIXTURES_PATH, "WorkflowHarness.canonical_count"),
    ],
    "Docling và build structure": [
        (FIXTURES_PATH, "WorkflowHarness.build_structure"),
        (FIXTURES_PATH, "WorkflowHarness.chunks_for"),
    ],
    "LLM extraction": [
        (FIXTURES_PATH, "WorkflowHarness.run_llm_extraction"),
        (FIXTURES_PATH, "WorkflowHarness.get_cached_extraction"),
    ],
    "Embedding và semantic search": [
        (FIXTURES_PATH, "WorkflowHarness.create_embeddings"),
        (FIXTURES_PATH, "WorkflowHarness.semantic_search"),
        (FIXTURES_PATH, "WorkflowHarness._embed_text"),
        (FIXTURES_PATH, "WorkflowHarness._cosine"),
    ],
    "Citation graph scoring": [
        (FIXTURES_PATH, "WorkflowHarness.add_citation"),
        (FIXTURES_PATH, "WorkflowHarness.score_citation_graph"),
    ],
    "Duplicate và canonical caching": [
        (FIXTURES_PATH, "WorkflowHarness.mark_duplicate"),
        (FIXTURES_PATH, "WorkflowHarness.get_cached_extraction"),
    ],
}

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class SummaryTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.criterion_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "expected_failures": 0,
                "unexpected_successes": 0,
            }
        )
        self.module_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "expected_failures": 0,
                "unexpected_successes": 0,
            }
        )

    def _module_name(self, test: unittest.case.TestCase) -> str:
        return test.__class__.__module__

    def _criterion_name(self, test: unittest.case.TestCase) -> str:
        module = self._module_name(test)
        return MODULE_TO_CRITERIA.get(module, "Other")

    def startTest(self, test):
        self.module_stats[self._module_name(test)]["total"] += 1
        self.criterion_stats[self._criterion_name(test)]["total"] += 1
        super().startTest(test)

    def addSuccess(self, test):
        self.module_stats[self._module_name(test)]["passed"] += 1
        self.criterion_stats[self._criterion_name(test)]["passed"] += 1
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.module_stats[self._module_name(test)]["failed"] += 1
        self.criterion_stats[self._criterion_name(test)]["failed"] += 1
        super().addFailure(test, err)

    def addError(self, test, err):
        self.module_stats[self._module_name(test)]["errors"] += 1
        self.criterion_stats[self._criterion_name(test)]["errors"] += 1
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.module_stats[self._module_name(test)]["skipped"] += 1
        self.criterion_stats[self._criterion_name(test)]["skipped"] += 1
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.module_stats[self._module_name(test)]["expected_failures"] += 1
        self.criterion_stats[self._criterion_name(test)]["expected_failures"] += 1
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.module_stats[self._module_name(test)]["unexpected_successes"] += 1
        self.criterion_stats[self._criterion_name(test)]["unexpected_successes"] += 1
        super().addUnexpectedSuccess(test)


def iter_code_objects(code: CodeType):
    yield code
    for const in code.co_consts:
        if isinstance(const, CodeType):
            yield from iter_code_objects(const)


def executable_lines_for_file(file_path: Path) -> set[int]:
    source = file_path.read_text(encoding="utf-8")
    compiled = compile(source, str(file_path), "exec")
    executable_lines: set[int] = set()

    for code in iter_code_objects(compiled):
        executable_lines.update(
            line
            for _, line in dis.findlinestarts(code)
            if isinstance(line, int) and line > 0
        )

    return executable_lines


def build_test_suite(pattern: str) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    return loader.discover(
        start_dir=str(TESTS_DIR / "integration"),
        pattern=pattern,
        top_level_dir=str(ROOT_DIR),
    )


def run_suite(pattern: str) -> SummaryTestResult:
    suite = build_test_suite(pattern)
    runner = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=2,
        resultclass=SummaryTestResult,
    )
    return runner.run(suite)


def criterion_for_test(test: unittest.case.TestCase) -> str:
    module = test.__class__.__module__
    return MODULE_TO_CRITERIA.get(module, "Other")


def filter_suite(suite: unittest.TestSuite, predicate) -> unittest.TestSuite:
    filtered = unittest.TestSuite()
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            sub = filter_suite(test, predicate)
            if sub.countTestCases():
                filtered.addTests(sub)
        else:
            if predicate(test):
                filtered.addTest(test)
    return filtered


def build_suite_for_criterion(pattern: str, criterion_name: str) -> unittest.TestSuite:
    suite = build_test_suite(pattern)
    return filter_suite(suite, lambda t: criterion_for_test(t) == criterion_name)


def function_ranges_for_file(file_path: Path) -> dict[str, tuple[int, int]]:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    ranges: dict[str, tuple[int, int]] = {}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.end_lineno:
                    ranges[f"{node.name}.{item.name}"] = (item.lineno, item.end_lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno:
            ranges[node.name] = (node.lineno, node.end_lineno)

    return ranges


def collect_coverage_for_targets(
    counts: dict[tuple[str, int], int],
    targets_by_file: dict[Path, list[str]],
) -> tuple[int, int]:
    executed_by_file: dict[Path, set[int]] = defaultdict(set)
    ranges_cache: dict[Path, dict[str, tuple[int, int]]] = {}

    for (filename, lineno), hit_count in counts.items():
        if hit_count <= 0:
            continue
        executed_by_file[Path(filename).resolve()].add(lineno)

    total_executed = 0
    total_executable = 0

    for file_path, qualnames in targets_by_file.items():
        resolved = file_path.resolve()
        if not resolved.exists():
            continue

        ranges_cache.setdefault(resolved, function_ranges_for_file(resolved))
        ranges = ranges_cache[resolved]
        executable_lines = executable_lines_for_file(resolved)

        target_lines: set[int] = set()
        for qualname in qualnames:
            func_range = ranges.get(qualname)
            if not func_range:
                continue
            start, end = func_range
            target_lines.update(line for line in executable_lines if start <= line <= end)

        if not target_lines:
            continue

        executed_lines = executed_by_file.get(resolved, set()) & target_lines
        total_executed += len(executed_lines)
        total_executable += len(target_lines)

    return total_executed, total_executable


def run_suite_for_coverage(suite: unittest.TestSuite) -> trace.CoverageResults:
    ignoredirs = {
        str(Path(sys.prefix).resolve()),
        str(Path(sys.base_prefix).resolve()),
    }
    tracer = trace.Trace(count=1, trace=0, ignoredirs=tuple(ignoredirs))
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)

    previous_disable = logging.getLogger().manager.disable
    logging.disable(logging.CRITICAL)
    try:
        tracer.runfunc(lambda: runner.run(suite))
    finally:
        logging.disable(previous_disable)

    return tracer.results()


def collect_group_coverages(pattern: str) -> dict[str, dict[str, float | int]]:
    group_coverages: dict[str, dict[str, float | int]] = {}

    for criterion_name in CRITERIA_ORDER:
        if criterion_name == "Other":
            continue

        targets = CRITERIA_TARGETS.get(criterion_name, [])
        suite = build_suite_for_criterion(pattern, criterion_name)
        if suite.countTestCases() == 0 or not targets:
            group_coverages[criterion_name] = {
                "executed": 0,
                "executable": 0,
                "coverage_pct": 0.0,
            }
            continue

        targets_by_file: dict[Path, list[str]] = defaultdict(list)
        for file_path, qualname in targets:
            targets_by_file[file_path].append(qualname)

        results = run_suite_for_coverage(suite)
        executed, executable = collect_coverage_for_targets(results.counts, targets_by_file)
        coverage_pct = (executed / executable * 100) if executable else 100.0
        group_coverages[criterion_name] = {
            "executed": executed,
            "executable": executable,
            "coverage_pct": coverage_pct,
        }

    return group_coverages


def print_summary(result: SummaryTestResult, group_coverages: dict[str, dict[str, float | int]]) -> None:
    print("\n=== Integration Test Summary ===")

    print("\nBy integration testing criteria:")
    criteria_names = list(CRITERIA_ORDER)
    extra_criteria = sorted(name for name in result.criterion_stats if name not in CRITERIA_ORDER)
    for criterion_name in criteria_names + extra_criteria:
        stats = result.criterion_stats[criterion_name]
        print(
            f"- {criterion_name}: total={stats['total']}, "
            f"passed={stats['passed']}, failed={stats['failed']}, "
            f"errors={stats['errors']}, skipped={stats['skipped']}"
        )

    print("\nBy test module:")
    for module_name in sorted(result.module_stats):
        stats = result.module_stats[module_name]
        print(
            f"{module_name}: total={stats['total']}, "
            f"passed={stats['passed']}, failed={stats['failed']}, "
            f"errors={stats['errors']}, skipped={stats['skipped']}"
        )

    failed = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    expected_failures = len(result.expectedFailures)
    unexpected_successes = len(result.unexpectedSuccesses)
    passed = result.testsRun - failed - errors - skipped - expected_failures - unexpected_successes

    print(
        f"Overall: total={result.testsRun}, passed={passed}, failed={failed}, "
        f"errors={errors}, skipped={skipped}, "
        f"expected_failures={expected_failures}, unexpected_successes={unexpected_successes}"
    )

    print("\n=== Coverage by integration testing criteria ===")
    for criterion_name in CRITERIA_ORDER:
        if criterion_name == "Other":
            continue
        stats = group_coverages.get(criterion_name)
        if not stats:
            print(f"- {criterion_name}: no data")
            continue
        executed = stats["executed"]
        executable = stats["executable"]
        coverage_pct = stats["coverage_pct"]
        if executable == 0:
            print(f"- {criterion_name}: no executable lines found")
            continue
        print(
            f"- {criterion_name}: {executed}/{executable} "
            f"({coverage_pct:.2f}%)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all backend integration tests with summary and coverage.")
    parser.add_argument(
        "--pattern",
        default="test_*.py",
        help="Test discovery pattern. Default: test_*.py",
    )
    args = parser.parse_args()

    logging.getLogger("asyncio").setLevel(logging.ERROR)
    logging.getLogger("app.services.llm_extraction_service").setLevel(logging.ERROR)

    ignoredirs = {
        str(TESTS_DIR.resolve()),
        str(Path(sys.prefix).resolve()),
        str(Path(sys.base_prefix).resolve()),
    }

    tracer = trace.Trace(
        count=1,
        trace=0,
        ignoredirs=tuple(ignoredirs),
    )
    result = tracer.runfunc(run_suite, args.pattern)

    group_coverages = collect_group_coverages(args.pattern)
    print_summary(result, group_coverages)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
