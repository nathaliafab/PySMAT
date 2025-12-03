from typing import Dict, List, TypedDict, Union
from nimrod.output_generation.output_generator import OutputGenerator, OutputGeneratorContext
from nimrod.test_suites_execution.main import TestSuitesExecution
from os import path
from nimrod.utils import load_json
import logging


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

        # Group conflicts by test suite to run coverage once per suite
        conflicts_by_suite = {}
        for semantic_conflict in context.semantic_conflicts:
            suite_path = semantic_conflict.detected_in.test_suite.path
            if suite_path not in conflicts_by_suite:
                conflicts_by_suite[suite_path] = {
                    'test_suite': semantic_conflict.detected_in.test_suite,
                    'conflicts': []
                }
            conflicts_by_suite[suite_path]['conflicts'].append(semantic_conflict)

        # Execute coverage once per suite with all conflicted tests
        coverage_reports_by_suite = {}
        for suite_path, suite_data in conflicts_by_suite.items():
            try:
                test_cases = [conflict.detected_in.name for conflict in suite_data['conflicts']]
                coverage_report_root = self._test_suites_execution.execute_test_suite_with_coverage(
                    test_suite=suite_data['test_suite'],
                    target_file=context.scenario.scenario_files.merge,
                    test_cases=test_cases
                )
                coverage_reports_by_suite[suite_path] = coverage_report_root
            except Exception as e:
                logging.error(f"Error executing test suite with coverage for suite {suite_path}: {e}")
                coverage_reports_by_suite[suite_path] = None

        # Generate report data for each conflict using the shared coverage report
        for semantic_conflict in context.semantic_conflicts:
            suite_path = semantic_conflict.detected_in.test_suite.path
            exercised_targets: Dict[str, List[str]] = dict()
            
            if coverage_reports_by_suite.get(suite_path):
                try:
                    exercised_targets = self._extract_exercised_targets_from_coverage_report(
                        coverage_report_root=coverage_reports_by_suite[suite_path],
                        targets=context.scenario.targets
                    )
                except Exception as e:
                    logging.error(f"Error extracting exercised targets for {semantic_conflict.detected_in.name}: {e}")
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

            unified_report = load_json(coverage_json_path)

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
