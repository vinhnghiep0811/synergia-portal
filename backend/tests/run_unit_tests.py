import argparse
import dis
import logging
import sys
import trace
import unittest
from collections import defaultdict
from pathlib import Path
from types import CodeType


ROOT_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT_DIR / "tests"
APP_DIR = ROOT_DIR / "app"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class SummaryTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
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

    def startTest(self, test):
        self.module_stats[self._module_name(test)]["total"] += 1
        super().startTest(test)

    def addSuccess(self, test):
        self.module_stats[self._module_name(test)]["passed"] += 1
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.module_stats[self._module_name(test)]["failed"] += 1
        super().addFailure(test, err)

    def addError(self, test, err):
        self.module_stats[self._module_name(test)]["errors"] += 1
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.module_stats[self._module_name(test)]["skipped"] += 1
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.module_stats[self._module_name(test)]["expected_failures"] += 1
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.module_stats[self._module_name(test)]["unexpected_successes"] += 1
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
        start_dir=str(TESTS_DIR),
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


def print_summary(result: SummaryTestResult, file_reports: list[dict[str, object]], total_executed: int, total_executable: int) -> None:
    print("\n=== Test Summary ===")

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

    print("\n=== Coverage Summary ===")
    if total_executable == 0:
        print("No executable lines found under app/.")
        return

    overall_coverage = total_executed / total_executable * 100
    print(
        f"app/: {total_executed}/{total_executable} executable lines covered "
        f"({overall_coverage:.2f}%)"
    )

    touched_reports = [report for report in file_reports if report["executed"] > 0]
    if not touched_reports:
        print("No app/ source lines were executed by this test run.")
        return

    print("\nFiles touched by tests:")
    for report in touched_reports:
        print(
            f"- {report['path']}: {report['executed']}/{report['executable']} "
            f"({report['coverage_pct']:.2f}%)"
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
    coverage_results = tracer.results()
    file_reports, total_executed, total_executable = collect_coverage(coverage_results.counts)

    print_summary(result, file_reports, total_executed, total_executable)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
