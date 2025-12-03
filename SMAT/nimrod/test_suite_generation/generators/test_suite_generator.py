from abc import ABC, abstractmethod
import logging
from os import makedirs, path
from time import time
from typing import List
import json

from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.tests.utils import get_base_output_path
from nimrod.test_suite_generation.test_suite import TestSuite

from nimrod.utils import generate_python_path


class TestSuiteGenerator(ABC):

    def __init__(self, python_tool=None) -> None:
        self._python = python_tool

    def generate_and_compile_test_suite(self, scenario: MergeScenarioUnderAnalysis, input_file: str, use_determinism: bool) -> TestSuite:
        if use_determinism:
            logging.debug('Using deterministic test suite generation')
            
        suite_dir = self.get_generator_tool_name() + "_" + str(int(time()))
        test_suite_path = path.join(get_base_output_path(), scenario.project_name, scenario.scenario_commits.merge[:6], suite_dir)

        makedirs(test_suite_path, exist_ok=True)

        logging.info(f"Starting generation with {self.get_generator_tool_name()}")
        self._execute_tool_for_tests_generation(input_file, test_suite_path, scenario, use_determinism)
        logging.info(f"Finished generation with {self.get_generator_tool_name()}")

        logging.info(f"Starting Python test validation for suite generated with {self.get_generator_tool_name()}")
        tests_class_path = self._validate_test_suite(input_file, test_suite_path)
        logging.info(f"Finished Python test validation for suite generated with {self.get_generator_tool_name()}")

        return TestSuite(
            generator_name=self.get_generator_tool_name(),
            class_path=tests_class_path,
            path=test_suite_path,
            test_classes_names=self._get_test_suite_class_names(test_suite_path)
        )

    @abstractmethod
    def get_generator_tool_name(self) -> str:
        pass

    @abstractmethod
    def _execute_tool_for_tests_generation(self, input_file: str, test_suite_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        pass

    @abstractmethod
    def _get_test_suite_class_paths(self, test_suite_path: str) -> List[str]:
        pass

    @abstractmethod
    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        pass

    def _update_compilation_results(self, test_suite_path: str, python_file: str, output: str) -> None:
        """Updates the compilation results file with the output of the compilation of a test suite class."""
        reports_dir = path.join(path.dirname(get_base_output_path()), "reports")
        COMPILATION_LOG_FILE = path.join(reports_dir, "compilation_results.json")
        
        makedirs(reports_dir, exist_ok=True)

        if path.exists(COMPILATION_LOG_FILE):
            with open(COMPILATION_LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    compilation_results = json.load(f)
                except json.JSONDecodeError:
                    compilation_results = {}
        else:
            compilation_results = {}

        test_suite_entry = compilation_results.setdefault(test_suite_path, {"validation_output": {}})
        safe_output = output.strip() if output.strip() else ""
        test_suite_entry["validation_output"][python_file] = safe_output

        with open(COMPILATION_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(compilation_results, f, indent=4)

    def _validate_test_suite(self, input_file: str, test_suite_path: str, extra_python_path: List[str] = []) -> str:
        """Validate Python test files for syntax errors"""
        # Python path generation
        python_path = generate_python_path([test_suite_path] + extra_python_path)
        
        for python_file in self._get_test_suite_class_paths(test_suite_path):
            output = ""
            try:
                # Simple Python syntax validation using compile()
                with open(python_file, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                compile(source_code, python_file, 'exec')
                logging.debug("Validated syntax for %s successfully.", python_file)
            
            # In case of syntax error, remove the file
            except SyntaxError as e:
                output = f"Syntax error on line {e.lineno}: {e.msg}"
                logging.error("Syntax error in %s: %s", python_file, output)
                path.remove(python_file)
            except Exception as e:
                output = f"Unexpected error: {str(e)}"
                logging.error("Unexpected error validating %s: %s", python_file, output)
                path.remove(python_file)
                
            self._update_compilation_results(test_suite_path, python_file, output)
        
        return python_path
