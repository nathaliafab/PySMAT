import os

from nimrod.report_metrics.target_method_metric import Target_Method_Metric
from nimrod.report_metrics.generated_object_metric import Generated_Object_Metric
from nimrod.report.report_writer import Report_Writer

class Report_Analysis:

    def __init__(self):
        self.target_method_metric = Target_Method_Metric()
        self.generated_object_metric = Generated_Object_Metric()
        self.report_writer = Report_Writer()

    def start_analysis(self, python_test_suites_base, python_test_suites_merge):
        """Analyze Python test suites from base and merge scenarios"""
        self.checking_suites_and_reports(python_test_suites_base[0][2], python_test_suites_merge[0][2])
        right_path_index_base = len(python_test_suites_base) - 1
        right_path_index_merge = len(python_test_suites_merge) - 1
        self.checking_suites_and_reports(python_test_suites_base[right_path_index_base][2], python_test_suites_merge[right_path_index_merge][2])

    def checking_suites_and_reports(self, path_suite_base, path_suite_merge):
        """Check if Python test suite directories and reports exist"""
        if os.path.isdir(path_suite_base) and os.path.isdir(path_suite_merge):
            if self.all_reports(path_suite_base, path_suite_merge):
                self.suites_comparison(path_suite_base, path_suite_merge)
            else:
                print(
                    f"It wasn't possible to compare the Python test suites because there are missing reports in paths: "
                    f"{path_suite_base} or {path_suite_merge}")
        else:
            print("It wasn't possible to make analysis because there are invalid Python test suite paths")

    def all_reports(self, path_suite_base, path_suite_merge):
        """Check if all required Python test reports exist"""
        return (os.path.isfile(path_suite_base + "/functions_report.csv") and 
                os.path.isfile(path_suite_merge + "/functions_report.csv") and
                os.path.isfile(path_suite_base + "/coverage_report.csv") and 
                os.path.isfile(path_suite_merge + "/coverage_report.csv"))

    def suites_comparison(self, path_suite_base, path_suite_merge):
        """Compare Python test suites and generate comparison metrics"""
        functions = self.target_method_metric.metrics_comparison(path_suite_base, path_suite_merge)
        coverage = self.generated_object_metric.metrics_comparison(path_suite_base, path_suite_merge)

        if len(functions) == 0 or len(coverage) == 0:
            print(f"It wasn't possible to compare the Python test suites {path_suite_base} and {path_suite_merge}")
        else:
            self.report_writer.write_functions_and_coverage_report(path_suite_base, path_suite_merge, functions, coverage)