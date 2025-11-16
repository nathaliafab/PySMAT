import os

class Report_Writer:

    def write_functions_and_coverage_report(self, path_suite_base, path_suite_merge, functions, coverage):
        """Write Python test function and coverage comparison reports"""
        suites_path = path_suite_base[:path_suite_base.rfind("/")]  # Get the directory where the test suites are
        reports_path = suites_path + "/reports"

        if os.path.isdir(reports_path) is False:
            os.mkdir(reports_path)

        suite_name_base = path_suite_base[path_suite_base.rfind("/") + 1:]
        suite_name_merge = path_suite_merge[path_suite_merge.rfind("/") + 1:]

        # Functions report (equivalent to methods report for Python)
        functions_report_name = reports_path + "/functions_report_" + suite_name_base + "_" + suite_name_merge + ".csv"
        functions_report_headers = "Functions called,Number of calls(Base),Number of calls(Merge),Merge - Base,Percentage(Gain/Loss),Number of calls(Base-Normalized),Number of calls(Merge-Normalized),Merge - Base,Percentage(Gain/Loss)\n"

        self.write_csv_file(functions_report_name, functions_report_headers, functions, False)

        # Coverage report (equivalent to objects report for Python)  
        coverage_report_name = reports_path + "/coverage_report_" + suite_name_base + "_" + suite_name_merge + ".csv"
        coverage_report_headers = "Classes tested,Line coverage(Base),Line coverage(Merge),Merge - Base,Percentage(Gain/Loss),Function coverage(Base),Function coverage(Merge),Merge - Base,Percentage(Gain/Loss),Line coverage(Base-Normalized),Line coverage(Merge-Normalized),Merge - Base,Percentage(Gain/Loss),Function coverage(Base-Normalized),Function coverage(Merge-Normalized),Merge - Base,Percentage(Gain/Loss)\n"

        self.write_csv_file(coverage_report_name, coverage_report_headers, coverage, True)

        print(f"The analysis of Python test suites {suite_name_base} and {suite_name_merge} was completed")

    def write_csv_file(self, path_csv, headers, data, is_coverage_report):
        """Write CSV file with function or coverage comparison data"""
        with open(path_csv,"w") as output_file:
            output_file.write(headers)

            for key in data:
                text = key.replace(",","|") + "," + self.get_comparison(int(data.get(key)[0]), int(data.get(key)[1]))

                if is_coverage_report:
                    # Coverage report has additional metrics: function coverage and normalized values
                    text += "," + self.get_comparison(int(data.get(key)[2]), int(data.get(key)[3])) + "," + self.get_comparison(float(data.get(key)[4]), float(data.get(key)[5])) + "," + self.get_comparison(float(data.get(key)[6]), float(data.get(key)[7])) + "\n"
                else:
                    # Function report has normalized values
                    text += "," + self.get_comparison(float(data.get(key)[2]), float(data.get(key)[3])) + "\n"

                output_file.write(text)

            output_file.close()

    def get_comparison(self, number_base, number_merge):
        """Calculate comparison between base and merge values"""
        sub = number_merge - number_base

        if number_base == 0:
            relative = "INF"
        elif number_merge == 0:
            relative = "-INF"
        else:
            relative = (sub / number_base) * 100
            relative = str(round(relative, 2))

        return str(number_base) + "," + str(number_merge) + "," + str(
            sub) + "," + "\"" + relative + "%\""