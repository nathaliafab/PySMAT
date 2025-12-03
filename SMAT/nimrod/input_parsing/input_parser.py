from nimrod.utils import load_json
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from nimrod.core.merge_scenario_under_analysis import ScenarioInformation, MergeScenarioUnderAnalysis

# This interface is responsible for parsing user input from a file into SMAT internal model.
# If you wish to implement a new parser, just create a new implementation of it.
class InputParser(ABC):
    @abstractmethod
    def parse_input(self, file_path: str) -> "List[MergeScenarioUnderAnalysis]":
        pass


class JsonInputParser(InputParser):
    def parse_input(self, file_path: str) -> "List[MergeScenarioUnderAnalysis]":
        json_data: List[Dict[str, Any]] = []
        json_data = load_json(file_path)

        return [self._convert_to_internal_representation(scenario) for scenario in json_data]

    def _convert_to_internal_representation(self, scenario: "Dict[str, Any]"):
        scenario_commits_json: Any = scenario.get('scenarioCommits')
        
        scenario_files_json: Any = scenario.get('scenarioFiles')
        
        return MergeScenarioUnderAnalysis(
            project_name=str(scenario.get('projectName')),
            run_analysis=bool(scenario.get('runAnalysis')),
            scenario_commits=ScenarioInformation(
                base=scenario_commits_json.get('base'),
                left=scenario_commits_json.get('left'),
                right=scenario_commits_json.get('right'),
                merge=scenario_commits_json.get('merge'),
            ),
            targets=scenario.get('targets', dict()),
            scenario_files=ScenarioInformation(
                base=scenario_files_json.get('base'),
                left=scenario_files_json.get('left'),
                right=scenario_files_json.get('right'),
                merge=scenario_files_json.get('merge'),
            ),
        )