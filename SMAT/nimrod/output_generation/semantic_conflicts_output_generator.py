from typing import Dict, List, TypedDict, Union
from nimrod.output_generation.output_generator import OutputGenerator, OutputGeneratorContext
from nimrod.test_suites_execution.main import TestSuitesExecution
from os import path
import logging
import json


class SemanticConflictsOutput(TypedDict):
    project_name: str
    scenario_commits: Dict[str, str]
    criteria: str
    test_case_name: str
    test_case_results: Dict[str, str]
    test_suite_path: str
    scenario_targets: Dict[str, Union[List[Dict[str, str]], List[str]]]
    exercised_targets: Dict[str, List[str]]


class SemanticConflictsOutputGenerator(OutputGenerator[List[SemanticConflictsOutput]]):
    def __init__(self, test_suites_execution: TestSuitesExecution) -> None:
        super().__init__("semantic_conflicts")
        self._test_suites_execution = test_suites_execution

    def _generate_report_data(self, context: OutputGeneratorContext) -> List[SemanticConflictsOutput]:
        report_data: List[SemanticConflictsOutput] = list()

        for semantic_conflict in context.semantic_conflicts:
            # We need to detect which targets from the input were exercised in this conflict.
            exercised_targets: Dict[str, List[str]] = dict()
            try:
                coverage_report_root = self._test_suites_execution.execute_test_suite_with_coverage(
                    test_suite=semantic_conflict.detected_in.test_suite,
                    target_file=context.scenario.scenario_files.merge,
                    test_cases=[semantic_conflict.detected_in.name]
                )

                exercised_targets = self._extract_exercised_targets_from_coverage_report(
                    coverage_report_root=coverage_report_root,
                    targets=context.scenario.targets
                )

            except Exception as e:
                # If we cannot execute the test suite with coverage, we log the error and continue.
                logging.error(f"Error executing test suite with coverage for semantic conflict: {e}")
                exercised_targets = {}

            report_data.append({
                "project_name": context.scenario.project_name,
                "scenario_commits": context.scenario.scenario_commits.__dict__,
                "criteria": semantic_conflict._satisfying_criteria.__class__.__name__,
                "test_case_name": semantic_conflict.detected_in.name,
                "test_case_results": {
                    "base": semantic_conflict.detected_in.base,
                    "left": semantic_conflict.detected_in.left,
                    "right": semantic_conflict.detected_in.right,
                    "merge": semantic_conflict.detected_in.merge
                },
                "test_suite_path": semantic_conflict.detected_in.test_suite.path,
                "scenario_targets": context.scenario.targets,
                "exercised_targets": exercised_targets
            })

        return report_data

    def _extract_exercised_targets_from_coverage_report(self, coverage_report_root: str, targets: Dict[str, Union[List[Dict[str, str]], List[str]]]):
        exercised_targets: Dict[str, List[str]] = dict()

        try:
            coverage_json_path = path.join(coverage_report_root, 'coverage.json')
            
            if not path.exists(coverage_json_path):
                logging.warning(f"Coverage JSON report not found at {coverage_json_path}")
                return exercised_targets

            with open(coverage_json_path, 'r', encoding='utf-8') as f:
                unified_report = json.load(f)

            # Extract exercised targets from unified coverage report
            conflicted_tests_coverage = unified_report.get('conflicted_tests_coverage', [])
            
            for test_coverage in conflicted_tests_coverage:
                coverage_data = test_coverage.get('coverage_data')
                if coverage_data and coverage_data.get('line_coverage'):
                    line_coverage = coverage_data.get('line_coverage', {})
                    executed_lines = line_coverage.get('executed_lines', [])
                    
                    # If the test executed any lines, mark all targets as exercised
                    if executed_lines:
                        for class_name in targets.keys():
                            if class_name not in exercised_targets:
                                exercised_targets[class_name] = []
                            
                            for method_item in targets[class_name]:
                                if isinstance(method_item, dict):
                                    method_name = method_item.get("method", "")
                                else:
                                    method_name = method_item
                                
                                # Add method to exercised targets if not already present
                                if method_name and method_name not in exercised_targets[class_name]:
                                    exercised_targets[class_name].append(method_name)

        except Exception as e:
            logging.error(f"Error extracting exercised targets from coverage report: {e}")

        return exercised_targets
