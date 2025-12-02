import logging
import re
import subprocess
import json
from os import path, makedirs
from typing import Dict, List
from nimrod.test_suite_generation.test_suite import TestSuite
from nimrod.test_suites_execution.test_case_result import TestCaseResult
from nimrod.tests.utils import get_base_output_path

reports_dir = path.join(path.dirname(get_base_output_path()), "reports")
makedirs(reports_dir, exist_ok=True)
EXECUTION_LOG_FILE = path.join(reports_dir, "execution_results.json")

def is_failed_caused_by_import_problem(test_case_name: str, failed_test_message: str) -> bool:
    """Check if test failed due to import/module issues"""
    my_regex = re.escape(test_case_name) + r"[0-9A-Za-z0-9_\(\.\)\n \:]+(ImportError|ModuleNotFoundError|AttributeError|NameError)"
    return re.search(my_regex, failed_test_message) is not None

def is_failed_caused_by_syntax_error(test_case_name: str, failed_test_message: str) -> bool:
    """Check if test failed due to syntax errors"""
    return "SyntaxError" in failed_test_message or "IndentationError" in failed_test_message

def get_result_for_test_case(failed_test: str, output: str) -> TestCaseResult:
    if is_failed_caused_by_import_problem(failed_test, output):
        return TestCaseResult.NOT_EXECUTABLE
    elif is_failed_caused_by_syntax_error(failed_test, output):
        return TestCaseResult.NOT_EXECUTABLE
    return TestCaseResult.FAIL

class TestSuiteExecutor:
    def __init__(self, python_tool=None) -> None:
        self._python = python_tool

    def execute_test_suite(self, test_suite: TestSuite, python_file: str, number_of_executions: int = 3) -> Dict[str, TestCaseResult]:
        results: Dict[str, TestCaseResult] = dict()

        # Load existing log if it exists
        try:
            with open(EXECUTION_LOG_FILE, "r") as log_file:
                execution_log = json.load(log_file)
        except (FileNotFoundError, json.JSONDecodeError):
            execution_log = {}

        for test_class in test_suite.test_classes_names:
            logging.debug("Python test file: %s", test_class)
            test_file_path = path.join(test_suite.path, f"{test_class}.py")

            if not path.exists(test_file_path):
                logging.warning("Python test file %s does not exist; skipping execution", test_file_path)
                continue

            if test_class not in execution_log:
                execution_log[test_class] = []

            # Check if the current test_suite.path is already in the log
            test_suite_entry = next((entry for entry in execution_log[test_class] if test_suite.path in entry), None)
            if not test_suite_entry:
                test_suite_entry = {test_suite.path: {"python_file": {}}}
                execution_log[test_class].append(test_suite_entry)

            # Ensure the Python file is tracked under the current test_suite.path
            if python_file not in test_suite_entry[test_suite.path]["python_file"]:
                test_suite_entry[test_suite.path]["python_file"][python_file] = []

            # Append execution results for the current Python file
            for i in range(0, number_of_executions):
                logging.info("Starting execution %d of %s from suite %s", i + 1, test_class, test_suite.path)
                response = self._execute_pytest(test_suite, python_file, test_class)
                logging.debug("PYTEST RESULTS: %s", response)
                for test_case, test_case_result in response.items():
                    test_fqname = f"{test_class}::{test_case}"
                    if results.get(test_fqname) and results.get(test_fqname) != test_case_result:
                        results[test_fqname] = TestCaseResult.FLAKY
                    elif not results.get(test_fqname):
                        results[test_fqname] = test_case_result

                test_suite_entry[test_suite.path]["python_file"][python_file].append({
                    "execution_number": i + 1,
                    "result": {test_case: str(test_case_result) for test_case, test_case_result in response.items()}
                })

        with open(EXECUTION_LOG_FILE, "w") as log_file:
            json.dump(execution_log, log_file, indent=4)

        return results

    def _execute_pytest(self, test_suite: TestSuite, target_file: str, test_class: str, extra_params: List[str] = []) -> Dict[str, TestCaseResult]:
        """Execute pytest on Python test files"""
        try:
            test_file_path = path.join(test_suite.path, f"{test_class}.py")
            
            # Basic pytest command
            params = ['pytest', test_file_path, '-v', '--tb=short'] + extra_params
            
            # Execute pytest
            result = subprocess.run(
                params,
                cwd=test_suite.path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            output = result.stdout + result.stderr
            return self._parse_pytest_results_from_output(output, test_class)
            
        except subprocess.TimeoutExpired:
            logging.error("Pytest execution timed out for %s", test_class)
            return {"test_timeout": TestCaseResult.NOT_EXECUTABLE}
        except subprocess.CalledProcessError as error:
            output = error.stdout + error.stderr if error.stdout or error.stderr else str(error)
            return self._parse_pytest_results_from_output(output, test_class)
        except Exception as e:
            logging.error("Unexpected error executing pytest for %s: %s", test_class, str(e))
            return {"test_error": TestCaseResult.NOT_EXECUTABLE}

    def _parse_pytest_results_from_output(self, output: str, test_class: str) -> Dict[str, TestCaseResult]:
        """Parse pytest output to extract test results"""
        results: Dict[str, TestCaseResult] = dict()
        
        # Parse pytest output patterns
        # Look for individual test results: test_file.py::test_function PASSED/FAILED/ERROR
        test_pattern = rf"{re.escape(test_class)}\.py::(test_\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)"
        matches = re.findall(test_pattern, output)
        
        for test_name, result in matches:
            if result == "PASSED":
                results[test_name] = TestCaseResult.PASS
            elif result == "FAILED":
                results[test_name] = get_result_for_test_case(test_name, output)
            elif result == "ERROR":
                results[test_name] = TestCaseResult.NOT_EXECUTABLE
            elif result == "SKIPPED":
                results[test_name] = TestCaseResult.NOT_EXECUTABLE
        
        # If no individual tests found, look for summary
        if not results:
            # Look for pytest summary: "X passed", "X failed", etc.
            summary_pattern = r"(\d+) (passed|failed|error|skipped)"
            summary_matches = re.findall(summary_pattern, output)
            
            total_tests = 0
            failed_tests = 0
            
            for count, status in summary_matches:
                count = int(count)
                total_tests += count
                if status in ['failed', 'error']:
                    failed_tests += count
            
            # Generate generic test names if we know the count
            if total_tests > 0:
                for i in range(total_tests):
                    test_name = f"test_{i:02d}"
                    if i < failed_tests:
                        results[test_name] = TestCaseResult.FAIL
                    else:
                        results[test_name] = TestCaseResult.PASS
        
        # If still no results, mark as not executable
        if not results:
            results["test_default"] = TestCaseResult.NOT_EXECUTABLE
            
        return results

    def execute_test_suite_with_coverage(self, test_suite: TestSuite, target_file: str, test_cases: List[str]) -> str:
        """Execute Python tests with coverage collection using pytest-cov"""
        coverage_dir = path.join(get_base_output_path(), "coverage_reports")
        makedirs(coverage_dir, exist_ok=True)
        
        report_dir = path.join(test_suite.path, 'coverage_report')
        makedirs(report_dir, exist_ok=True)
        
        logging.debug('Starting execution of Python test suite for coverage collection')
        
        try:
            # Execute pytest with coverage for specific test cases
            test_files = [path.join(test_suite.path, f"{tc}.py") for tc in test_cases if path.exists(path.join(test_suite.path, f"{tc}.py"))]
            
            if not test_files:
                logging.warning("No valid test files found for coverage collection")
                return report_dir
            
            coverage_params = [
                'pytest',
                '--cov=' + path.dirname(target_file),  # Coverage source directory
                '--cov-report=html:' + report_dir,     # HTML report output
                '--cov-report=term',                   # Terminal output
                '--cov-branch',                        # Include branch coverage
                '-v'
            ] + test_files
            
            result = subprocess.run(
                coverage_params,
                cwd=test_suite.path,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for coverage
            )
            
            if result.returncode == 0:
                logging.debug('Successfully collected coverage for Python test suite')
            else:
                logging.warning('Coverage collection completed with warnings: %s', result.stderr)
                
        except subprocess.TimeoutExpired:
            logging.error('Coverage collection timed out')
        except Exception as e:
            logging.error('Error during coverage collection: %s', str(e))
        
        logging.debug('Finished execution of Python test suite for coverage collection')
        return report_dir
