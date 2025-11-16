import os

from nimrod.tools.python_suite_generator import PythonTestSuiteGenerator
from nimrod.utils import get_class_files


class LLM(PythonTestSuiteGenerator):

    def _get_tool_name(self):
        return "llm"

    def _test_classes(self):
        classes = []

        for class_file in sorted(get_class_files(self.suite_classes_dir)):
            filename, _ = os.path.splitext(class_file)
            classes.append(filename.replace(os.sep, '.'))

        return classes

    def _get_suite_dir(self):
        return os.path.join(self.suite_dir, 'llm-tests')
