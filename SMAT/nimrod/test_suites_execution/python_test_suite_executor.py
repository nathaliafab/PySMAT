import logging
import re
import subprocess
import json
import os
import shutil
from typing import Dict, List
from nimrod.test_suite_generation.test_suite import TestSuite
from nimrod.test_suites_execution.test_case_result import TestCaseResult
from nimrod.tests.utils import get_base_output_path
from nimrod.tools.python import Python
from nimrod.tools.python_coverage import PythonCoverage

reports_dir = os.path.join(os.path.dirname(get_base_output_path()), "reports")
os.makedirs(reports_dir, exist_ok=True)
EXECUTION_LOG_FILE = os.path.join(reports_dir, "execution_results.json")

def is_failed_caused_by_syntax_error(test_case_name: str, failed_test_message: str) -> bool:
    """Check if failure is caused by syntax or import errors in Python."""
    error_patterns = [
        r"SyntaxError", r"ImportError", r"ModuleNotFoundError", 
        r"NameError", r"AttributeError"
    ]
    for pattern in error_patterns:
        if re.search(pattern, failed_test_message, re.IGNORECASE):
            return True
    return False

def is_failed_caused_by_error(test_case_name: str, failed_test_message: str) -> bool:
    """Check if failure is caused by actual test error."""
    error_patterns = [r"AssertionError", r"Exception", r"Error"]
    for pattern in error_patterns:
        if re.search(pattern, failed_test_message, re.IGNORECASE):
            return True
    return False

def get_result_for_test_case(failed_test: str, output: str) -> TestCaseResult:
    """Determine test result based on output."""
    if is_failed_caused_by_syntax_error(failed_test, output):
        return TestCaseResult.NOT_EXECUTABLE
    elif is_failed_caused_by_error(failed_test, output):
        return TestCaseResult.FAIL
    return TestCaseResult.FAIL


class PythonTestSuiteExecutor:
    """
    Python test suite executor - equivalent to TestSuiteExecutor but for Python tests.
    """
    
    def __init__(self, python: Python, coverage: PythonCoverage) -> None:
        self._python = python
        self._coverage = coverage

    def execute_test_suite(self, test_suite: TestSuite, target_file: str, number_of_executions: int = 3, branch: str = "") -> Dict[str, TestCaseResult]:
        """
        Execute Python test suite and return results.
        
        Args:
            test_suite: TestSuite object containing test information
            target_file: Python file being tested
            number_of_executions: Number of times to execute each test
        
        Returns:
            Dictionary mapping test names to their results
        """
        results: Dict[str, TestCaseResult] = dict()

        # Load existing log if it exists
        try:
            with open(EXECUTION_LOG_FILE, "r") as log_file:
                execution_log = json.load(log_file)
        except (FileNotFoundError, json.JSONDecodeError):
            execution_log = {}

        for test_class in test_suite.test_classes_names:
            logging.debug("Test class: %s", test_class)
            
            # For Python, check if .py file exists
            test_file_path = os.path.join(test_suite.path, f"{test_class}.py")
            
            if not os.path.exists(test_file_path):
                logging.warning("Test file %s does not exist; skipping execution", test_file_path)
                continue

            if test_class not in execution_log:
                execution_log[test_class] = []

            # Check if the current test_suite.path is already in the log
            test_suite_entry = next((entry for entry in execution_log[test_class] if test_suite.path in entry), None)
            if not test_suite_entry:
                test_suite_entry = {test_suite.path: {"target_file": {}}}
                execution_log[test_class].append(test_suite_entry)

            # Ensure the target file is tracked under the current test_suite.path
            if target_file not in test_suite_entry[test_suite.path]["target_file"]:
                test_suite_entry[test_suite.path]["target_file"][target_file] = []

            # Execute tests multiple times
            for i in range(0, number_of_executions):
                logging.info("Starting execution %d of %s from suite %s on %s branch", i + 1, test_class, test_suite.path, branch or "current")
                response = self._execute_pytest(test_suite, target_file, test_class, branch)
                logging.debug("RESULTS: %s", response)
                
                for test_case, test_case_result in response.items():
                    test_fqname = f"{test_class}#{test_case}"
                    if results.get(test_fqname) and results.get(test_fqname) != test_case_result:
                        results[test_fqname] = TestCaseResult.FLAKY
                    elif not results.get(test_fqname):
                        results[test_fqname] = test_case_result

                test_suite_entry[test_suite.path]["target_file"][target_file].append({
                    "execution_number": i + 1,
                    "result": {test_case: str(test_case_result) for test_case, test_case_result in response.items()}
                })

        # Save execution log
        with open(EXECUTION_LOG_FILE, "w") as log_file:
            json.dump(execution_log, log_file, indent=4)

        return results

    def _switch_class_file_for_branch(self, test_suite_path: str, class_name: str, branch: str) -> bool:
        """
        Switch the class file to the specified branch version for execution.
        Renames ClassName_branch.py to ClassName.py temporarily.
        """
        try:
            # Extract simple class name
            simple_class_name = class_name.split('.')[-1]
            
            # Paths for source and target files
            branch_file = os.path.join(test_suite_path, f"{simple_class_name}_{branch}.py")
            main_file = os.path.join(test_suite_path, f"{simple_class_name}.py")
            
            if not os.path.exists(branch_file):
                logging.warning(f"Branch file not found: {branch_file}")
                return False
            
            # Backup current main file if it exists
            if os.path.exists(main_file):
                backup_file = os.path.join(test_suite_path, f"{simple_class_name}_backup.py")
                shutil.move(main_file, backup_file)
            
            # Copy branch file to main file
            shutil.copy2(branch_file, main_file)
            logging.debug(f"Switched to {branch} branch for class {simple_class_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error switching to {branch} branch for {class_name}: {e}")
            return False

    def _restore_class_file(self, test_suite_path: str, class_name: str) -> None:
        """
        Restore the original class file after branch execution.
        """
        try:
            simple_class_name = class_name.split('.')[-1]
            main_file = os.path.join(test_suite_path, f"{simple_class_name}.py")
            backup_file = os.path.join(test_suite_path, f"{simple_class_name}_backup.py")
            
            # Remove current main file
            if os.path.exists(main_file):
                os.remove(main_file)
            
            # Restore from backup if it exists
            if os.path.exists(backup_file):
                shutil.move(backup_file, main_file)
                
        except Exception as e:
            logging.error(f"Error restoring class file for {class_name}: {e}")

    def _execute_pytest(self, test_suite: TestSuite, target_file: str, test_class: str, branch: str = "", extra_params: List[str] = []) -> Dict[str, TestCaseResult]:
        """
        Execute Python tests using pytest and parse results.
        If branch is specified, switches to that branch version before execution.
        """
        try:
            # Switch to specific branch if requested
            if branch:
                class_name = self._extract_class_name_from_target_file(target_file, test_suite.path)
                if not self._switch_class_file_for_branch(test_suite.path, class_name, branch):
                    return {f"test_{test_class}": TestCaseResult.NOT_EXECUTABLE}
            
            # Create test execution command using pytest
            test_file_path = os.path.join(test_suite.path, f"{test_class}.py")
            
            # Run pytest with verbose output
            result = self._python.exec_python(
                test_suite.path,
                self._python.get_env({'PYTHONPATH': test_suite.path}),
                300,
                '-m', 'pytest', test_file_path, '-v', '--tb=short'
            )
            
            parsed_results = self._parse_pytest_results_from_output(result, test_class)
            
            # Restore original class file if we switched branches
            if branch:
                self._restore_class_file(test_suite.path, class_name)
            
            return parsed_results
            
        except subprocess.CalledProcessError as error:
            output = error.stderr or error.stdout or ""
            logging.error(f"Pytest execution failed: {output}")
            
            # Restore original class file if we switched branches
            if branch:
                self._restore_class_file(test_suite.path, class_name)
                
            return self._parse_pytest_results_from_output(output, test_class)
        except Exception as e:
            logging.error(f"Unexpected error during pytest execution: {e}")
            
            # Restore original class file if we switched branches
            if branch:
                self._restore_class_file(test_suite.path, class_name)
                
            return {f"test_{test_class}": TestCaseResult.NOT_EXECUTABLE}

    def _extract_class_name_from_target_file(self, target_file: str, test_suite_path: str = "") -> str:
        """Extract class name from target file path."""
        # Extract class name from the target file name
        target_basename = os.path.basename(target_file)
        # Remove file extension first
        target_name = os.path.splitext(target_basename)[0]
        
        if '_' in target_name:
            # Extract class name (e.g., DiscountCalculator from DiscountCalculator_merge)
            class_name = target_name.split('_')[0]
        else:
            # If no underscore, check if it's a variant file (base.py, left.py, right.py, merge.py)
            if target_name in ['base', 'left', 'right', 'merge'] and test_suite_path:
                # Find test files to extract class name
                import glob
                test_pattern = os.path.join(test_suite_path, "*Test_*.py")
                test_files = glob.glob(test_pattern)
                if test_files:
                    # Extract class name from first test file (e.g., DiscountCalculatorTest_*.py -> DiscountCalculator)
                    first_test = os.path.basename(test_files[0])
                    if 'Test_' in first_test:
                        class_name = first_test.split('Test_')[0]
                    else:
                        class_name = target_name
                else:
                    class_name = "DiscountCalculator"  # Fallback
            else:
                class_name = target_name
        
        logging.debug(f"Executor: target_file={target_file}, extracted class_name={class_name}")
        return class_name

    def _parse_pytest_results_from_output(self, output: str, test_class: str) -> Dict[str, TestCaseResult]:
        """
        Parse pytest output to determine test results.
        """
        results: Dict[str, TestCaseResult] = dict()
        
        # pytest patterns
        # PASSED: test_file.py::test_method PASSED
        # FAILED: test_file.py::test_method FAILED
        # ERROR: test_file.py::test_method ERROR
        
        # Extract test results from pytest verbose output
        test_result_pattern = r"(\w+\.py::test_\w+)\s+(PASSED|FAILED|ERROR)"
        test_results = re.findall(test_result_pattern, output)
        
        for test_path, result in test_results:
            # Extract just the test method name
            test_method = test_path.split("::")[-1]
            
            if result == "PASSED":
                results[test_method] = TestCaseResult.PASS
            elif result == "FAILED":
                if is_failed_caused_by_syntax_error(test_method, output):
                    results[test_method] = TestCaseResult.NOT_EXECUTABLE
                else:
                    results[test_method] = TestCaseResult.FAIL
            elif result == "ERROR":
                results[test_method] = TestCaseResult.NOT_EXECUTABLE
        
        # If no results found, try alternative parsing
        if not results:
            # Look for summary line: "1 passed", "2 failed", etc.
            summary_pattern = r"(\d+) (passed|failed|error)"
            summary_matches = re.findall(summary_pattern, output, re.IGNORECASE)
            
            if summary_matches:
                # Create generic test results
                for count, status in summary_matches:
                    count = int(count)
                    for i in range(count):
                        test_name = f"test_{test_class}_{i}"
                        if status.lower() == "passed":
                            results[test_name] = TestCaseResult.PASS
                        elif status.lower() == "failed":
                            results[test_name] = TestCaseResult.FAIL
                        else:
                            results[test_name] = TestCaseResult.NOT_EXECUTABLE
            else:
                # Default fallback
                results[f"test_{test_class}"] = TestCaseResult.NOT_EXECUTABLE
            
        return results

    def execute_test_suite_with_coverage(self, test_suite: TestSuite, target_file: str, test_cases: List[str]) -> str:
        """
        Execute Python test suite with coverage measurement using pytest-cov.
        
        Args:
            test_suite: TestSuite object
            target_file: Python file being tested
            test_cases: List of test cases to execute
            
        Returns:
            Path to coverage report directory
        """
        logging.debug('Starting execution of test suite for coverage collection')
        
        try:
            unified_report = self._coverage.run_coverage_for_conflicted_tests(
                test_suite.path,
                target_file, 
                test_cases
            )
            
            # Save coverage report in the test suite directory
            report_dir = os.path.join(test_suite.path, 'coverage_report')
            os.makedirs(report_dir, exist_ok=True)
            
            # Save unified coverage report as JSON
            coverage_file = os.path.join(report_dir, 'coverage.json')
            with open(coverage_file, 'w') as f:
                json.dump(unified_report, f, indent=2)
            
            # Log coverage summary
            if unified_report and 'conflicted_tests_coverage' in unified_report:
                logging.info("Conflicted tests coverage summary:")
                for test_entry in unified_report['conflicted_tests_coverage']:
                    test_name = test_entry['test_case_name']
                    coverage_data = test_entry.get('coverage_data')
                    if coverage_data:
                        overall_percent = coverage_data.get('overall_coverage_percent', 0)
                        line_coverage = coverage_data.get('line_coverage', {})
                        branch_coverage = coverage_data.get('branch_coverage', {})
                        logging.info(f"  {test_name}: {overall_percent:.1f}% overall (lines: {line_coverage.get('percent', 0):.1f}%, branches: {branch_coverage.get('percent', 0):.1f}%)")
                    else:
                        logging.info(f"  {test_name}: No coverage data available")
            
            logging.debug('Finished execution of test suite for coverage collection')
            return report_dir
            
        except Exception as e:
            logging.error(f"Coverage execution failed: {e}")
            return ""
