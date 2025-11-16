import os
from nimrod.report.output import Output

class Result_Summary(Output):

    def __init__(self, output_path, file_name):
        Output.__init__(self, output_path, file_name)
        self.summary = []
        self.python_test_suites = {}

    def generate_summary(self, test_conflict_report_file, coverage_report_file):
        test_conflict_report = open(test_conflict_report_file)
        test_conflicts = test_conflict_report.read()
        test_conflict_report.close()

        lines = test_conflicts.split("\n")
        current_merge_scenario = ""
        current_target_method = ""
        parent_one = ""
        parent_two = ""
        merge_scenario_values = []

        for line in lines[1:-1]:
            values = line.split(",");
            if(current_merge_scenario == ""):
                current_merge_scenario = values[4]
                current_target_method = values[11]
            if (parent_one == ""):
                parent_one = values[2]
            if (parent_two == "" and values[3] != parent_one and values[3] != "NOT-REQUIRED"):
                parent_two = values[3]

            if ((values[4] == current_merge_scenario or values[4] == "NOT-REQUIRED") and values[11] == current_target_method):
                merge_scenario_values.append(values)
            else:
                self.summary_by_target_method(merge_scenario_values, parent_one, parent_two, "python3.8")
                self.summary_by_target_method(merge_scenario_values, parent_one, parent_two, "python3.9")
                self.summary_by_target_method(merge_scenario_values, parent_one, parent_two, "python3.10")

                current_merge_scenario = values[4]
                current_target_method = values[11]
                merge_scenario_values = []
                merge_scenario_values.append(values)
                parent_one = ""
                parent_two = ""

        if(len(merge_scenario_values)>0):
            self.summary_by_target_method(merge_scenario_values, parent_one, parent_two, "python3.8")
            self.summary_by_target_method(merge_scenario_values, parent_one, parent_two, "python3.9")
            self.summary_by_target_method(merge_scenario_values, parent_one, parent_two, "python3.10")

        for summary_line in self.summary:
            suite_key = summary_line[3]+"-"+summary_line[4]
            if suite_key in self.python_test_suites and len(self.python_test_suites[suite_key]) > 0:
                print(f"Processing test suite: {self.python_test_suites[suite_key]}")
                suite_path = self.python_test_suites[suite_key][0]
                # For Python tests, we track test coverage and execution metrics
                comparison = self.get_python_test_metrics(suite_path, str(summary_line[3]).split(" | ")[0],
                                                         str(summary_line[1]).split("(")[0], summary_line[2])

                coverage_report = open(coverage_report_file)
                coverage_report_info = coverage_report.read()
                coverage_report.close()

                lines = coverage_report_info.split("\n")

                for line in lines[1:-1]:
                    values = line.split(",");
                    if (suite_path == values[3] and summary_line[3] == values[0] and summary_line[4] == values[1]):
                        try:
                            line_coverage_original = 0
                            line_coverage_modified = 0
                            if (values[15] != ""):
                                line_coverage_modified = float(values[15])
                            if (values[14] != ""):
                                line_coverage_original = float(values[14])

                            method_coverage_original = 0
                            method_coverage_modified = 0
                            if (values[18] != ""):
                                method_coverage_modified = float(values[18])
                            if (values[17] != ""):
                                method_coverage_original = float(values[17])

                            if (line_coverage_modified > line_coverage_original):
                                summary_line[14] = True
                            elif (line_coverage_modified == line_coverage_original):
                                summary_line[14] = "SAME"
                            else:
                                summary_line[14] = False

                            if (method_coverage_modified > method_coverage_original):
                                summary_line[15] = True
                            elif (method_coverage_modified == method_coverage_original):
                                summary_line[15] = "SAME"
                            else:
                                summary_line[15] = False

                        except Exception:
                            print("It was not possible to get coverage information. \n")

                self.python_test_suites[summary_line[3]+"-"+summary_line[4]].remove(suite_path)
                summary_line[12] = comparison[0]
                summary_line[13] = comparison[1]

        for summary_line in self.summary:
            self.write_output_line(summary_line)

    def get_python_test_metrics(self, suite_path, merge_scenario, target_class, target_method):
        """Get Python test execution metrics for the target class and method"""
        target_class = target_class.split(" | ")[0]
        target_method = target_method.split("(")[0]
        
        # Default values
        class_coverage_improvement = "UNAVAILABLE"
        method_test_improvement = "UNAVAILABLE"
        
        try:
            # Look for Python test reports in the reports directory
            reports_dir = suite_path.split(merge_scenario)[0] + merge_scenario + "/reports"
            
            if os.path.exists(reports_dir):
                # Check for Python coverage reports
                coverage_report_path = os.path.join(reports_dir, f"python_coverage_{os.path.basename(suite_path)}.csv")
                if os.path.exists(coverage_report_path):
                    with open(coverage_report_path, 'r') as f:
                        lines = f.readlines()
                        
                    for line in lines[1:]:  # Skip header
                        values = line.strip().split(",")
                        if len(values) > 3 and target_class in values[0]:
                            if values[2]:  # Class coverage data
                                class_coverage_improvement = values[2].replace('"', '')
                            break
                
                # Check for method-specific test metrics
                test_report_path = os.path.join(reports_dir, f"python_tests_{os.path.basename(suite_path)}.csv")
                if os.path.exists(test_report_path):
                    with open(test_report_path, 'r') as f:
                        lines = f.readlines()
                        
                    for line in lines[1:]:  # Skip header
                        values = line.strip().split(",")
                        if len(values) > 2 and f"{target_class}.{target_method}" in values[0]:
                            if values[1]:  # Method test data
                                method_test_improvement = values[1].replace('"', '')
                            break
                            
        except Exception as e:
            print(f"Error reading Python test metrics: {e}")
            
        return [class_coverage_improvement, method_test_improvement]

    def get_file_collumn_names(self):
        return ["project_name","merge_scenario","target_class","target_method","target_parent","python_version","conflict_detection_first_criterion","tools",
                "conflict_detection_second_criterion","tools","behavior_change","tools","improvement_class_coverage",
                "improvement_on_target_method_tests","improvement_on_coverage_target_class","improvement_on_coverage_target_method"]

    def write_output_line(self, text):
        if (os.path.isfile(self.output_file_path) == False):
            self.create_result_file()
        self.write_each_result(text)

    def formate_output_line(self, project_name, criteria_validation, class_information, method_information):
        pass

    def summary_by_target_method(self, values, parent_one, parent_two, python_version):
        self.summary_by_target_commit(values, parent_one, python_version)
        self.summary_by_target_commit(values, parent_two, python_version)

    def summary_by_target_commit(self, values, target_parent, python_version):
        conflict_occurrence_first = False
        conflict_tools_first = []
        conflict_occurrence_second = False
        conflict_tools_second = []
        behavior_change = False
        behavior_change_tools = []
        project_name = ""
        merge_commit = ""
        target_class = ""
        target_method = ""

        for value in values:
            if (value[13] == python_version and value[2] == target_parent):
                if (value[6] == 'True'):
                    if (value[7] == "FIRST_CRITERION"):
                        conflict_occurrence_first = True;
                        if (not value[5] in conflict_tools_first):
                            conflict_tools_first.append(value[5])
                    elif (value[7] == "SECOND_CRITERION"):
                        conflict_occurrence_second = True;
                        if (not value[5] in conflict_tools_second):
                            conflict_tools_second.append(value[5])
                    elif (value[7] == "BEHAVIOR_CHANGE_COMMIT_PAIR"):
                        behavior_change = True;
                        if (not value[5] in behavior_change_tools):
                            behavior_change_tools.append(value[5])

                if (project_name == ""):
                    project_name = value[0]
                if (merge_commit == ""):
                    merge_commit = value[4]
                if (target_class == ""):
                    target_class = value[10].replace("\"","")
                if (target_method == ""):
                    target_method = value[11].replace("\"","")

                if(value[5] in ["PYTHON", "PYTEST"] and not value[4] == "NOT-REQUIRED"):
                    suite_key = value[4]+"-"+value[2]
                    if suite_key not in self.python_test_suites:
                        self.python_test_suites[suite_key] = [value[9]]
                    elif value[9] not in self.python_test_suites[suite_key]:
                        self.python_test_suites[suite_key].append(value[9])

        if (project_name != ""):
            self.summary.append([project_name, target_class, target_method, merge_commit, target_parent, python_version, str(conflict_occurrence_first),
                                 str(conflict_tools_first).replace("\'",""), str(conflict_occurrence_second), str(conflict_tools_second).replace("\'",""),
                                 str(behavior_change),str(behavior_change_tools).replace("\'",""),"","","",""])
