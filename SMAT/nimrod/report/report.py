import os
import csv
from csv import reader
from nimrod.report.scenario import Scenario

class Report:

    def __init__(self):
        self.path_final_report = ""

    def check_if_first_suite_detects_behavior_change(self, line):
        if line[5] == "True":
            return True
        else:
            return False

    def check_tool_detected_behavior_change(self, line):
        if (line[4] == "evosuite"):
            self.evosuite += 1
        elif (line[4] == "differential-evosuite"):
            self.evosuite_diff += 1
        elif (line[4] == "randoop"):
            self.randoop += 1

    def check_detected_behavior_changes_by_suites(self, lines):
        detected_behavior = 0
        first_time_detected = None
        number_suites = 0
        for line in lines:
            number_suites += 1
            if line[5] == "True":
                self.check_tool_detected_behavior_change(line)
                detected_behavior += 1
                if first_time_detected == None:
                    first_time_detected = number_suites

        return detected_behavior, number_suites

    def check_if_majority_suites_detect_behavior_change(self, detected_behavior, number_suites):
        return (detected_behavior > number_suites/2)

    def get_lines_by_individual_cases(self, path_csv_file):
        individual_scenarios = {}
        not_executed = {}
        if (os.path.exists(path_csv_file)):
            with open(path_csv_file) as read_obj:
                csv_reader = reader(read_obj)
                header = next(csv_reader)
                if header != None:
                    for row in csv_reader:
                        scenario = str(row[0])+"-"+str(row[1])+"-"+str(row[2])+"-"+str(row[3])+"-"+str(row[8])+"-"+str(row[9])
                        if (row[5] != "NONE"):
                            if (individual_scenarios.get(scenario) == None):
                                individual_scenarios[scenario] = [row]
                            else:
                                aux = individual_scenarios.get(scenario)
                                aux.append(row)
                                individual_scenarios[scenario] = aux
                        else:
                            if (not_executed.get(scenario) == None):
                                not_executed[scenario] = [row]
                            else:
                                aux = not_executed.get(scenario)
                                aux.append(row)
                                not_executed[scenario] = aux

        return individual_scenarios, not_executed

    def get_report(self, path_csv_file):
        result = self.get_lines_by_individual_cases(path_csv_file)
        scenarios_reports = []

        for key in result[0]:
            scenarios_reports.append(Scenario(key, result[0].get(key)))

        for scenario in scenarios_reports:
            self.write_final_report_for_scenario(scenario.scenario.split("-")[0], scenario.scenario.split("-")[3], scenario)

    def write_final_report_for_scenario(self, project_name, merge_hash, report):
        if (os.path.isfile(os.getcwd().replace("/nimrod/proj","/")+'/final_report.csv') == False):
            self.create_result_file()
        else:
            self.path_final_report = os.getcwd().replace("/nimrod/proj", "/") + "/final_report.csv"
        self.write_each_result(self.path_final_report, self.formate_output_line_test_conflicts(project_name, merge_hash, report))

    def formate_output_line_test_conflicts(self, project_name, merge_commit, scenario):
        return [project_name, merge_commit, scenario.diff_evosuite_first_suite_detection, scenario.evosuite_first_suite_detection,
                scenario.randoop_first_suite_detection, scenario.general_first_suite_detection, scenario.diff_evosuite_detected_sm_by_suites,
                scenario.evosuite_detected_sm_by_suites, scenario.randoop_detected_sm_by_suites, scenario.diff_evosuite_detected_sm_until_first,
                scenario.evosuite_detected_sm_until_first, scenario.randoop_detected_sm_until_first, (scenario.diff_evosuite_detected_sm_by_suites +
                scenario.evosuite_detected_sm_by_suites + scenario.randoop_detected_sm_by_suites)/3]

    def write_each_result(self, file_path, output):
        with open(file_path, 'a+') as fd:
            writer = csv.writer(fd)
            writer.writerow(output)

    def create_result_file(self):
        with open(os.getcwd().replace("/nimrod/proj","/")+'/final_report.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["project_name", "merge_commit", "first_suite_semantic_conflict_diff_evosuite",
                             "first_suite_semantic_conflict_evosuite", "first_suite_semantic_conflict_randoop",
                             "first_suite_semantic_conflict_general", "suites_with_detection_diff_evosuite",
                             "suites_with_detection_evosuite", "suites_with_detection_diff_randoop",
                             "calls_until_first_detection_diff_evosuite", "calls_until_first_detection_evosuite",
                             "calls_until_first_detection_randoop", "detected_call_mean_by_tools"])

        self.path_final_report = os.getcwd().replace("/nimrod/proj", "/") + "/final_report.csv"

#report = Report()
#result = report.get_report("/home/leusonmario/PycharmProjects/nimrod-hunor/test_conflicts.csv")