from abc import abstractmethod

class Metric:
    @abstractmethod
    def metrics_comparison(self, path_suite_base, path_suite_merge) -> dict:
        """Compare metrics between base and merge test suites"""
        pass

    @abstractmethod
    def extract_data(self, data, report_path, is_base_report) -> dict:
        """Extract data from test suite reports"""
        pass
