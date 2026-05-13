import argparse
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
REPO_ROOT = ROOT_DIR.parent
TESTS_DIR = ROOT_DIR / "tests"
UNIT_TESTS_DIR = TESTS_DIR / "services"
APP_DIR = ROOT_DIR / "app"
WORKER_APP_DIR = ROOT_DIR.parent / "worker" / "worker_app"

CRITERIA_ORDER = [
    "File validation",
    "DOI và fingerprint",
    "Canonical mapping",
    "LLM output schema",
    "Cache decision",
    "Search ranking helpers",
    "Other",
]

MODULE_TO_CRITERIA = {
    "tests.services.test_paper_service": "File validation",
    "tests.services.test_pdf_parse_service": "DOI và fingerprint",
    "tests.services.test_pdf_parse_task_canonical_mapping": "Canonical mapping",
    "tests.services.test_search_service_helpers": "Search ranking helpers",
}

CLASS_TO_CRITERIA = {
    "CacheDecisionTests": "Cache decision",
}

CRITERIA_TO_FILES = {
    "File validation": [APP_DIR / "services" / "paper_service.py"],
    "DOI và fingerprint": [APP_DIR / "services" / "pdf_parse_service.py"],
    "Canonical mapping": [WORKER_APP_DIR / "tasks" / "pdf_parse.py"],
    "LLM output schema": [
        APP_DIR / "services" / "llm_extraction_service.py",
        APP_DIR / "schemas" / "extraction_result.py",
    ],
    "Cache decision": [APP_DIR / "services" / "llm_extraction_service.py"],
    "Search ranking helpers": [APP_DIR / "services" / "search_service.py"],
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
        return criterion_for_test(test)

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
        start_dir=str(UNIT_TESTS_DIR),
        pattern=pattern,
        top_level_dir=str(ROOT_DIR),
    )


def criterion_for_test(test: unittest.case.TestCase) -> str:
    module = test.__class__.__module__
    class_name = test.__class__.__name__

    if module == "tests.services.test_llm_extraction_service":
        return CLASS_TO_CRITERIA.get(class_name, "LLM output schema")

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


def run_suite(pattern: str) -> SummaryTestResult:
    suite = build_test_suite(pattern)
    runner = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=2,
        resultclass=SummaryTestResult,
    )
    return runner.run(suite)


def collect_coverage(counts: dict[tuple[str, int], int]) -> tuple[list[dict[str, object]], int, int]:
    executed_by_file: dict[Path, set[int]] = defaultdict(set)

    for (filename, lineno), hit_count in counts.items():
        if hit_count <= 0:
            continue

        resolved = Path(filename).resolve()
        if APP_DIR in resolved.parents or resolved == APP_DIR:
            executed_by_file[resolved].add(lineno)

    file_reports: list[dict[str, object]] = []
    total_executable = 0
    total_executed = 0

    for file_path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in file_path.parts:
            continue

        executable_lines = executable_lines_for_file(file_path)
        if not executable_lines:
            continue

        executed_lines = executed_by_file.get(file_path.resolve(), set()) & executable_lines
        executable_count = len(executable_lines)
        executed_count = len(executed_lines)
        coverage_pct = (executed_count / executable_count * 100) if executable_count else 100.0

        file_reports.append(
            {
                "path": file_path.relative_to(ROOT_DIR).as_posix(),
                "executed": executed_count,
                "executable": executable_count,
                "coverage_pct": coverage_pct,
            }
        )

        total_executable += executable_count
        total_executed += executed_count

    return file_reports, total_executed, total_executable


def collect_coverage_for_files(
    counts: dict[tuple[str, int], int],
    file_paths: list[Path],
) -> tuple[list[dict[str, object]], int, int]:
    executed_by_file: dict[Path, set[int]] = defaultdict(set)

    for (filename, lineno), hit_count in counts.items():
        if hit_count <= 0:
            continue
        executed_by_file[Path(filename).resolve()].add(lineno)

    file_reports: list[dict[str, object]] = []
    total_executable = 0
    total_executed = 0

    def _format_path(path: Path) -> str:
        try:
            return path.relative_to(ROOT_DIR).as_posix()
        except ValueError:
            try:
                return path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                return path.as_posix()

    for file_path in file_paths:
        resolved = file_path.resolve()
        if not resolved.exists():
            file_reports.append({
                "path": _format_path(file_path),
                "executed": 0,
                "executable": 0,
                "coverage_pct": 0.0,
            })
            continue

        executable_lines = executable_lines_for_file(resolved)
        if not executable_lines:
            file_reports.append({
                "path": _format_path(resolved),
                "executed": 0,
                "executable": 0,
                "coverage_pct": 0.0,
            })
            continue

        executed_lines = executed_by_file.get(resolved, set()) & executable_lines
        executable_count = len(executable_lines)
        executed_count = len(executed_lines)
        coverage_pct = (executed_count / executable_count * 100) if executable_count else 100.0

        file_reports.append(
            {
                "path": _format_path(resolved),
                "executed": executed_count,
                "executable": executable_count,
                "coverage_pct": coverage_pct,
            }
        )

        total_executable += executable_count
        total_executed += executed_count

    return file_reports, total_executed, total_executable


def run_suite_for_coverage(suite: unittest.TestSuite) -> trace.CoverageResults:
    ignoredirs = {
        str(TESTS_DIR.resolve()),
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

        files = CRITERIA_TO_FILES.get(criterion_name, [])
        suite = build_suite_for_criterion(pattern, criterion_name)
        if suite.countTestCases() == 0 or not files:
            group_coverages[criterion_name] = {
                "executed": 0,
                "executable": 0,
                "coverage_pct": 0.0,
            }
            continue

        results = run_suite_for_coverage(suite)
        _, total_executed, total_executable = collect_coverage_for_files(results.counts, files)
        coverage_pct = (total_executed / total_executable * 100) if total_executable else 100.0
        group_coverages[criterion_name] = {
            "executed": total_executed,
            "executable": total_executable,
            "coverage_pct": coverage_pct,
        }

    return group_coverages


def print_summary(result: SummaryTestResult, group_coverages: dict[str, dict[str, float | int]]) -> None:
    print("\n=== Test Summary ===")

    print("\nBy testing criteria:")
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

    print("\n=== Coverage by testing criteria ===")
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
    parser = argparse.ArgumentParser(description="Run all backend unit tests with summary and coverage.")
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
