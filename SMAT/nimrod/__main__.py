import logging
from typing import Dict, List
from nimrod.dynamic_analysis.behavior_change_checker import BehaviorChangeChecker
from nimrod.dynamic_analysis.criteria.first_semantic_conflict_criteria import FirstSemanticConflictCriteria
from nimrod.dynamic_analysis.criteria.second_semantic_conflict_criteria import SecondSemanticConflictCriteria
from nimrod.dynamic_analysis.main import DynamicAnalysis
from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.output_generation.behavior_change_output_generator import BehaviorChangeOutputGenerator
from nimrod.output_generation.output_generator import OutputGenerator
from nimrod.output_generation.semantic_conflicts_output_generator import SemanticConflictsOutputGenerator
from nimrod.output_generation.test_suites_output_generator import TestSuitesOutputGenerator
from nimrod.smat import SMAT
from nimrod.test_suite_generation.main import TestSuiteGeneration
from nimrod.tests.utils import setup_logging, get_config
from nimrod.test_suite_generation.generators.llm_test_suite_generator import PythonTestSuiteGenerator
from nimrod.test_suites_execution.main import TestSuitesExecution
from nimrod.test_suites_execution.python_test_suite_executor import PythonTestSuiteExecutor
from nimrod.tools.python import Python
from nimrod.tools.python_coverage import PythonCoverage
from nimrod.input_parsing.input_parser import JsonInputParser


def get_llm_test_suite_generators(config: Dict[str, str]) -> List[PythonTestSuiteGenerator]:
  """
  Creates test suite generators for all available LLM models configured in api_params.
  Each model gets its own generator instance to enable parallel processing and comparison.
  """
  generators: List[PythonTestSuiteGenerator] = list()
  api_params = config.get('api_params', {})
  
  for model_key, model_config in api_params.items():
    # Create a generator for each configured model
    generator = PythonTestSuiteGenerator(Python(), model_key, model_config)
    generators.append(generator)
    
  return generators


def get_test_suite_generators(config: Dict[str, str]) -> List[PythonTestSuiteGenerator]:
  config_generators = config.get(
      'test_suite_generators', ['llm', 'project'])
  generators: List[PythonTestSuiteGenerator] = list()

  # Python-only generators
  if 'llm' in config_generators:
    # Create one generator for each configured model
    generators.extend(get_llm_test_suite_generators(config))
  if 'project' in config_generators:
    # Use Python test suite generator for project tests
    generators.append(PythonTestSuiteGenerator(Python()))

  return generators


def get_output_generators(config: Dict[str, str]) -> List[OutputGenerator]:
  config_generators = config.get(
      'output_generators', ['behavior_changes', 'semantic_conflicts', 'test_suites'])
  generators: List[OutputGenerator] = list()

  if 'behavior_changes' in config_generators:
    generators.append(BehaviorChangeOutputGenerator())
  if 'semantic_conflicts' in config_generators:
    generators.append(SemanticConflictsOutputGenerator(
        TestSuitesExecution(PythonTestSuiteExecutor(Python(), PythonCoverage(Python())))))
  if 'test_suites' in config_generators:
    generators.append(TestSuitesOutputGenerator())

  return generators

def parse_scenarios_from_input(config: Dict[str, str]) -> List[MergeScenarioUnderAnalysis]:
    json_input = config.get('input_path', "")

    if json_input != "":
        return JsonInputParser().parse_input(json_input)
    else:
        logging.fatal('No input file provided')
        exit(1)

def main():
  setup_logging()
  config = get_config()
  test_suite_generators = get_test_suite_generators(config)
  test_suite_generation = TestSuiteGeneration(test_suite_generators)
  test_suites_execution = TestSuitesExecution(
      PythonTestSuiteExecutor(Python(), PythonCoverage(Python())))
  dynamic_analysis = DynamicAnalysis([
      FirstSemanticConflictCriteria(),
      SecondSemanticConflictCriteria()
  ], BehaviorChangeChecker())
  output_generators = get_output_generators(config)

  smat = SMAT(test_suite_generation, test_suites_execution, dynamic_analysis, output_generators)
  scenarios = parse_scenarios_from_input(config)

  for scenario in scenarios:
    if scenario.run_analysis:
      smat.run_tool_for_semmantic_conflict_detection(scenario)
    else:
      logging.info(f"Skipping tool execution for project {scenario.project_name}")


if __name__ == '__main__':
  main()
