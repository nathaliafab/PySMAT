from nimrod.report_metrics.metric import Metric

class Generated_Object_Metric(Metric):
    def metrics_comparison(self, path_suite_base, path_suite_merge) -> dict:
        """Compare coverage metrics between base and merge test suites"""
        coverage_data = {}  # Dictionary where class name is key and value is a list with
        # coverage metrics for line and function coverage from base and merge test suites

        coverage_data = self.extract_data(coverage_data, path_suite_base + "/coverage_report.csv", True)
        coverage_data = self.extract_data(coverage_data, path_suite_merge + "/coverage_report.csv", False)

        return coverage_data

    def extract_data(self, data, report_path, is_base_report) -> dict:
        """Extract coverage data from Python test reports"""
        try:
            with open(report_path) as coverage_report_file:
                coverage_report = coverage_report_file.read()

            lines = coverage_report.split("\n")
            for line in lines[1:-1]:  # Skip header and empty last line
                cells = line.split(",")
                if is_base_report:
                    # Base coverage data: [line_cov_base, line_cov_merge, func_cov_base, func_cov_merge, 
                    #                     line_cov_base_norm, line_cov_merge_norm, func_cov_base_norm, func_cov_merge_norm]
                    coverage_map = {cells[0]: [cells[1], 0, cells[2], 0, cells[3], 0, cells[4], 0]}
                    data.update(coverage_map)
                elif cells[0] in data:  # Class already exists, update merge data
                    data.get(cells[0])[1] = cells[1]  # line coverage merge
                    data.get(cells[0])[3] = cells[2]  # function coverage merge
                    data.get(cells[0])[5] = cells[3]  # line coverage merge normalized
                    data.get(cells[0])[7] = cells[4]  # function coverage merge normalized
                else:
                    # New class from merge suite only
                    coverage_map = {cells[0]: [0, cells[1], 0, cells[2], 0, cells[3], 0, cells[4]]}
                    data.update(coverage_map)

            return data
        except Exception as e:
            print(f"Error reading coverage_report.csv at {report_path}: {e}")
            return {}