import logging
import os
import glob
from typing import List, Union

from nimrod.test_suite_generation.generators.llm_test_suite_generator import PythonTestSuiteGenerator
from nimrod.test_suite_generation.generators.test_suite_generator import TestSuiteGenerator
from nimrod.test_suite_generation.test_suite import TestSuite
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.tests.utils import get_base_output_path


class TestSuiteGeneration:
    def __init__(self, test_suite_generators: List[Union[PythonTestSuiteGenerator, TestSuiteGenerator]]) -> None:
        self._test_suite_generators = test_suite_generators

    def _discover_existing_test_suites(self, scenario: MergeScenarioUnderAnalysis, generator_pattern: str) -> List[TestSuite]:
        """
        Discover existing test suites in the output directory that match the generator pattern.
        This allows execution of previously generated test suites when new generation fails.
        """
        existing_suites = []
        
        # Build the search path for existing test suites
        projects_path = os.path.join(get_base_output_path(), scenario.project_name)
        if not os.path.exists(projects_path):
            logging.debug(f"Projects path does not exist: {projects_path}")
            return existing_suites
            
        # Search for directories matching the generator pattern (e.g., "GEMINI_*", "pynguin_*")
        search_pattern = os.path.join(projects_path, "**", f"{generator_pattern}*")
        matching_dirs = glob.glob(search_pattern, recursive=True)
        
        logging.info(f"Found {len(matching_dirs)} existing test suite directories for pattern '{generator_pattern}'")
        
        for suite_dir in matching_dirs:
            if os.path.isdir(suite_dir):
                try:
                    # Extract generator name from directory name
                    dir_name = os.path.basename(suite_dir)
                    
                    # Get test class names from Python files in the directory
                    test_class_names = self._get_test_class_names_from_directory(suite_dir)
                    
                    if test_class_names:
                        # Create TestSuite object for existing suite
                        existing_suite = TestSuite(
                            generator_name=dir_name,
                            class_path=suite_dir,
                            path=suite_dir,
                            test_classes_names=test_class_names
                        )
                        existing_suites.append(existing_suite)
                        logging.info(f"Loaded existing test suite: {suite_dir} with {len(test_class_names)} test classes")
                    else:
                        logging.debug(f"No test classes found in directory: {suite_dir}")
                        
                except Exception as e:
                    logging.warning(f"Failed to load existing test suite from {suite_dir}: {e}")
        
        return existing_suites

    def _get_test_class_names_from_directory(self, directory: str) -> List[str]:
        """Get test class names from Python files in a directory."""
        test_class_names = []
        
        # Look for Python files that appear to be test files
        python_files = glob.glob(os.path.join(directory, "*.py"))
        
        for py_file in python_files:
            filename = os.path.basename(py_file)
            # Remove .py extension
            class_name = os.path.splitext(filename)[0]
            
            # Only include files that look like test files
            if (class_name.startswith("Test") or 
                class_name.endswith("Test") or 
                "Test_" in class_name or
                filename.startswith("test_")):
                test_class_names.append(class_name)
        
        return test_class_names

    def generate_test_suites(self, scenario: MergeScenarioUnderAnalysis, input_file: str, use_determinism: bool) -> List[TestSuite]:
        logging.info("Starting test generation for project %s using file %s", scenario.project_name, input_file)
        test_suites: List[TestSuite] = list()

        for generator in self._test_suite_generators:
            try:
                test_suites.append(generator.generate_and_compile_test_suite(
                    scenario, input_file, use_determinism))
            except Exception as error:
                logging.error(f"It was not possible to generate test suite using {generator.get_generator_tool_name()}: %s", error)
                
                # Try to discover existing test suites for this generator type
                generator_name = generator.get_generator_tool_name()
                if "GEMINI" in generator_name:
                    # For LLM generators, look for existing GEMINI test suites
                    existing_suites = self._discover_existing_test_suites(scenario, "GEMINI")
                    test_suites.extend(existing_suites)
                elif "pynguin" in generator_name.lower():
                    # For Pynguin generators, look for existing pynguin test suites
                    existing_suites = self._discover_existing_test_suites(scenario, "pynguin")
                    test_suites.extend(existing_suites)
                else:
                    logging.debug(f"No fallback discovery implemented for generator: {generator_name}")

        logging.info("Finished test generation for project %s using file %s", scenario.project_name, input_file)
        return test_suites
