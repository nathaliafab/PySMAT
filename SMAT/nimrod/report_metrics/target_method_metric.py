import re
from nimrod.report_metrics.metric import Metric

class Target_Method_Metric(Metric):
    def metrics_comparison(self, path_suite_base, path_suite_merge) -> dict:
        """Compare function call metrics between base and merge test suites"""
        functions_data = {}  # Dictionary where function name is key and value is a list with 
        # the number of times that the function was called for base and merge test suites

        functions_data = self.extract_data(functions_data, path_suite_base + "/functions_report.csv", True)
        functions_data = self.extract_data(functions_data, path_suite_merge + "/functions_report.csv", False)

        return functions_data
    
    def extract_data(self, data, report_path, is_base_report) -> dict:
        """Extract function call data from Python test reports"""
        try:
            with open(report_path) as functions_report_file:
                functions_report = functions_report_file.read()

            lines = functions_report.split("\n")
            for line in lines[1:-1]:  # Skip header and empty last line
                cells = re.split("(?<=\"),", line)
                aux = re.split(",", cells[1])
                cells[1] = aux[0]
                cells.append(aux[1])
                
                if is_base_report:
                    # Base test suite data: [base_calls, merge_calls, base_normalized, merge_normalized]
                    function_map = {cells[0]: [cells[1], 0, cells[2], 0]}
                    data.update(function_map)
                elif cells[0] in data:  # Function already exists, update merge data
                    data.get(cells[0])[1] = cells[1]
                    data.get(cells[0])[3] = cells[2]
                else:
                    # New function from merge suite only
                    function_map = {cells[0]: [0, cells[1], 0, cells[2]]}
                    data.update(function_map)
        except Exception as e:
            print(f"Error reading functions_report.csv at {report_path}: {e}")

        return data