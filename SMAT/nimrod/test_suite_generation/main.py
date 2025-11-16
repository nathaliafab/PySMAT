import logging
from typing import List

from nimrod.test_suite_generation.generators.llm_test_suite_generator import PythonTestSuiteGenerator
from nimrod.test_suite_generation.test_suite import TestSuite
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis


class TestSuiteGeneration:
    def __init__(self, test_suite_generators: List[PythonTestSuiteGenerator]) -> None:
        self._test_suite_generators = test_suite_generators

    def generate_test_suites(self, scenario: MergeScenarioUnderAnalysis, input_file: str, use_determinism: bool) -> List[TestSuite]:
        logging.info("Starting Python test generation for project %s using file %s", scenario.project_name, input_file)
        test_suites: List[TestSuite] = list()

        for generator in self._test_suite_generators:
            try:
                test_suites.append(generator.generate_and_compile_test_suite(
                    scenario, input_file, use_determinism))
            except Exception as error:
                logging.error(f"It was not possible to generate test suite using {generator.get_generator_tool_name()}")
                logging.debug(error)

        logging.info("Finished Python test generation for project %s using file %s", scenario.project_name, input_file)
        return test_suites
