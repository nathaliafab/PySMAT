from abc import ABC, abstractmethod

import os
import sys
import shutil
import subprocess
import threading

from collections import namedtuple
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.project_info.merge_scenario import MergeScenario
from nimrod.utils import get_python_files, generate_python_path

TIMEOUT = 3000

lock = threading.RLock()

Suite = namedtuple('Suite', ['suite_name', 'suite_dir', 'suite_classes_dir',
                             'test_classes'])


class PythonSuiteGenerator(ABC):
    """
    Python test suite generator - equivalent to SuiteGenerator but for Python.
    """

    def __init__(self, python_tool, python_path, tests_src, sut_class=None, sut_classes=None, sut_method=None, params=None, scenario: MergeScenario = None, input: MergeScenarioUnderAnalysis = None):
        self.python = python_tool
        self.tests_src = tests_src
        self.python_path = python_path
        self.sut_class = sut_class
        self.sut_classes = sut_classes
        self.sut_method = sut_method
        self.parameters = params if params else []
        self.suite_dir = None
        self.suite_classes_dir = None
        self.suite_name = self._set_suite_name()
        self.scenario = scenario
        self.input = input

    @abstractmethod
    def _exec_tool(self):
        pass

    def _validate_syntax(self):
        """Validate Python syntax for all test files."""
        self.suite_classes_dir = os.path.join(self.suite_dir, 'tests')
        self._create_dirs(self.suite_classes_dir)

        python_path = generate_python_path([self.python_path, self.suite_dir, self.suite_classes_dir]
                                         + self._extra_python_path())

        for python_file in self._get_python_files():
            python_file_path = os.path.join(self.suite_dir, python_file)
            try:
                # Validate syntax
                if not self.python.validate_syntax(python_file_path):
                    print(f'[ERROR] Syntax error in {python_file}', file=sys.stderr)
            except Exception as e:
                print(f'[ERROR] Validating {self._get_tool_name()} tests: {e}', file=sys.stderr)

    def _get_python_files(self):
        """Get all Python files in the suite directory."""
        return sorted(get_python_files(self.suite_dir))

    @staticmethod
    def _extra_python_path():
        """Extra Python path entries."""
        return []

    def _get_suite_dir(self):
        return self.suite_dir

    @abstractmethod
    def _test_classes(self):
        pass

    @staticmethod
    def _get_timeout():
        return TIMEOUT

    @staticmethod
    @abstractmethod
    def _get_tool_name():
        return "python_tool"

    def _exec(self, *command):
        """Execute Python command."""
        try:
            return self.python.exec_python(self.suite_dir, self.python.get_env(),
                                         self._get_timeout(), *command)
        except subprocess.CalledProcessError as e:
            print(f'[ERROR] {self._get_tool_name()} call process error with command {command}: {e}', file=sys.stderr)
            raise e
        except subprocess.TimeoutExpired:
            print(f'[WARNING] {self._get_tool_name()} timeout.')

    def _make_src_dir(self):
        """Create source directory for tests."""
        self.suite_dir = os.path.join(self.tests_src, self.suite_name)
        self._create_dirs(self.suite_dir)

    def _set_suite_name(self):
        """Set unique suite name."""
        lock.acquire()
        self._create_dirs(self.tests_src, False)
        src_dirs = [file for file in os.listdir(self.tests_src)
                    if file.startswith(self._get_tool_name())]
        result = f'{self._get_tool_name()}_{len(src_dirs) + 1}'
        lock.release()
        return result

    @staticmethod
    def _create_dirs(path, remove_if_exists=True):
        """Create directories."""
        if remove_if_exists and os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)

    def generate(self, make_dir=True):
        """Generate test suite."""
        if make_dir:
            self._make_src_dir()
        self._exec_tool()
        self._validate_syntax()

        return Suite(suite_name=self.suite_name, suite_dir=self.suite_dir,
                     suite_classes_dir=self.suite_classes_dir,
                     test_classes=self._test_classes())