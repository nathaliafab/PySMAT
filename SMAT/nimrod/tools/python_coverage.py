import os
import subprocess
import json
import glob
from datetime import datetime
import logging


class PythonCoverage:
    """
    Python coverage analysis.
    """
    
    def __init__(self, python_executor):
        self.python = python_executor

    def install_coverage(self):
        """Install pytest-cov if not available."""
        try:
            subprocess.check_call([
                self.python.python_executable, '-m', 'pip', 'install', 'pytest-cov'
            ])
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install pytest-cov: {e}")
            return False
        except ImportError:
            try:
                subprocess.check_call([
                    self.python.python_executable, '-m', 'pip', 'install', 'pytest-cov'
                ])
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install pytest-cov: {e}")
                return False

    def run_coverage_for_conflicted_tests(self, test_suite_path, merge_file, conflicted_test_names):
        """
        Run coverage only for conflicted tests on merge version.
        
        Args:
            test_suite_path: Path to test suite directory
            merge_file: Merge version Python file 
            conflicted_test_names: List of test case names that detected conflicts
            
        Returns:
            Unified coverage report for conflicted tests
        """
        if not self.install_coverage():
            raise RuntimeError("Could not install pytest-cov")
        
        if not conflicted_test_names:
            return {}
        
        # Extract class name from merge file or test files
        class_name = self._extract_class_name(merge_file, test_suite_path)
        logging.info(f"Running coverage for class: {class_name}")
        
        # Setup files
        main_file = os.path.join(test_suite_path, f"{class_name}.py")
        backup_file = os.path.join(test_suite_path, f"{class_name}_backup.py")
        
        # Create output directory
        output_dir = self._create_output_directory(test_suite_path, merge_file)
        
        try:
            # Backup and copy merge file
            self._setup_merge_file(merge_file, main_file, backup_file)
            
            # Map conflicted tests to actual test files
            test_file_mapping = self._map_conflicted_tests_to_files(
                conflicted_test_names, test_suite_path, class_name
            )
            
            # Run coverage for each conflicted test
            coverage_results = self._run_individual_coverage(
                test_file_mapping, test_suite_path, class_name, output_dir
            )
            
            # Create unified report
            unified_report = self._create_unified_report(
                conflicted_test_names, coverage_results, output_dir
            )
            
            return unified_report
            
        finally:
            self._restore_original_file(main_file, backup_file)
    def _extract_class_name(self, target_file, test_suite_path):
        """Extract class name from target file or test files."""
        target_name = os.path.splitext(os.path.basename(target_file))[0]
        
        if '_' in target_name:
            class_name = target_name.split('_')[0]
        elif target_name in ['base', 'left', 'right', 'merge']:
            # Find class name from test files
            test_files = glob.glob(os.path.join(test_suite_path, "*Test_*.py"))
            if test_files:
                first_test = os.path.basename(test_files[0])
                if 'Test_' in first_test:
                    class_name = first_test.split('Test_')[0]
                else:
                    # Extract from any .py file that's not a test file
                    py_files = glob.glob(os.path.join(test_suite_path, "*.py"))
                    for py_file in py_files:
                        base_name = os.path.splitext(os.path.basename(py_file))[0]
                        if not base_name.endswith('Test') and not base_name.startswith('test'):
                            class_name = base_name
                            break
                    else:
                        raise ValueError("Could not determine class name from test suite directory")
            else:
                # Look for any non-test Python file
                py_files = glob.glob(os.path.join(test_suite_path, "*.py"))
                for py_file in py_files:
                    base_name = os.path.splitext(os.path.basename(py_file))[0]
                    if not base_name.endswith('Test') and not base_name.startswith('test'):
                        class_name = base_name
                        break
                else:
                    raise ValueError("Could not determine class name from test suite directory")
        else:
            class_name = target_name
        
        return class_name

    def _create_output_directory(self, test_suite_path, merge_file):
        """Create output directory for coverage reports."""
        reports_base_dir = os.path.join(os.path.dirname(test_suite_path), '..', '..', 'reports')
        os.makedirs(reports_base_dir, exist_ok=True)
        
        suite_name = os.path.basename(test_suite_path)
        merge_name = os.path.splitext(os.path.basename(merge_file))[0]
        output_dir = os.path.join(reports_base_dir, f'{suite_name}_{merge_name}_conflicts_coverage')
        os.makedirs(output_dir, exist_ok=True)
        
        return output_dir

    def _setup_merge_file(self, merge_file, main_file, backup_file):
        """Backup original and copy merge file."""
        if os.path.exists(main_file):
            import shutil
            shutil.copy2(main_file, backup_file)
        
        if os.path.exists(merge_file):
            import shutil
            shutil.copy2(merge_file, main_file)

    def _map_conflicted_tests_to_files(self, conflicted_tests, test_suite_path, class_name):
        """Map conflicted test names to actual test files."""
        all_test_files = glob.glob(os.path.join(test_suite_path, f"{class_name}Test_*.py"))
        test_file_mapping = {}
        
        for conflicted_test in conflicted_tests:
            test_class_part = conflicted_test.split('#')[0] if '#' in conflicted_test else conflicted_test
            logging.info(f"Looking for test class: {test_class_part}")
            
            for test_file in all_test_files:
                test_basename = os.path.basename(test_file)
                if test_class_part in test_basename:
                    test_file_mapping[conflicted_test] = test_basename
                    break
            else:
                logging.warning(f"Could not find test file for: {conflicted_test}")
        return test_file_mapping

    def _run_individual_coverage(self, test_file_mapping, test_suite_path, class_name, output_dir):
        """Run coverage for each conflicted test individually."""
        coverage_results = {}
        env = os.environ.copy()
        env['PYTHONPATH'] = test_suite_path
        
        for test_case, test_file in test_file_mapping.items():
            logging.info(f"Running coverage for: {test_case}")
            
            # Create coverage output files
            coverage_json = os.path.join(output_dir, f'coverage_{test_file}.json')
            
            # Run pytest with coverage
            pytest_cmd = [
                self.python.python_executable, '-m', 'pytest',
                '--cov-report=json:' + coverage_json,
                '--cov', class_name,
                '--cov-branch',
                test_file,
                '-v'
            ]
            
            result = subprocess.run(
                pytest_cmd,
                cwd=test_suite_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Load and store coverage data
            coverage_data = self._load_coverage_json(coverage_json)
            coverage_results[test_case] = {
                'test_file': test_file,
                'coverage_data': coverage_data,
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            status = "Success" if result.returncode == 0 else "Failed"
            logging.info(f"Coverage for {test_case}: {status}")
        
        return coverage_results

    def _create_unified_report(self, conflicted_tests, coverage_results, output_dir):
        """Create unified report combining conflict detection with coverage data."""
        unified_report = {
            'summary': {
                'total_conflicted_tests': len(conflicted_tests),
                'tests_with_coverage': len(coverage_results),
                'timestamp': datetime.now().isoformat()
            },
            'conflicted_tests_coverage': []
        }
        
        for test_name in conflicted_tests:
            test_entry = {
                'test_case_name': test_name,
                'conflict_detected': True,
                'coverage_data': None
            }
            
            if test_name in coverage_results:
                coverage_data = coverage_results[test_name]['coverage_data']
                files = coverage_data.get('files', {})
                for file_path, file_data in files.items():
                    if file_path.endswith('.py'):
                        summary_data = file_data.get('summary', {})
                        
                        # Calculate line coverage
                        executed_lines = file_data.get('executed_lines', [])
                        missing_lines = file_data.get('missing_lines', [])
                        total_statements = summary_data.get('num_statements', 0)
                        covered_statements = summary_data.get('covered_lines', 0)
                        line_coverage_percent = summary_data.get('percent_statements_covered', 0)
                        
                        # Calculate branch coverage
                        total_branches = summary_data.get('num_branches', 0)
                        covered_branches = summary_data.get('covered_branches', 0)
                        branch_coverage_percent = summary_data.get('percent_branches_covered', 0)
                        
                        test_entry['coverage_data'] = {
                            'line_coverage': {
                                'percent': line_coverage_percent,
                                'covered_statements': covered_statements,
                                'total_statements': total_statements,
                                'executed_lines': executed_lines,
                                'missing_lines': missing_lines
                            },
                            'branch_coverage': {
                                'percent': branch_coverage_percent,
                                'covered_branches': covered_branches,
                                'total_branches': total_branches,
                                'executed_branches': file_data.get('executed_branches', []),
                                'missing_branches': file_data.get('missing_branches', [])
                            },
                            'overall_coverage_percent': summary_data.get('percent_covered', 0)
                        }
                        break
            
            unified_report['conflicted_tests_coverage'].append(test_entry)
        
        # Save unified report
        unified_file = os.path.join(output_dir, 'unified_conflicts_coverage.json')
        with open(unified_file, 'w') as f:
            json.dump(unified_report, f, indent=2)
        return unified_report

    def _restore_original_file(self, main_file, backup_file):
        """Restore original file from backup."""
        if os.path.exists(backup_file):
            import shutil
            shutil.copy2(backup_file, main_file)
            os.remove(backup_file)

    def _load_coverage_json(self, coverage_json_file):
        """Load coverage data from pytest-cov JSON report."""
        try:
            if os.path.exists(coverage_json_file):
                with open(coverage_json_file, 'r', encoding='utf-8') as f:
                    coverage_data = json.load(f)
                return coverage_data
            else:
                logging.warning(f"Coverage JSON file not found: {coverage_json_file}")
                return {}
                
        except Exception as e:
            logging.error(f"Failed to load coverage JSON report: {e}")
            return {}

