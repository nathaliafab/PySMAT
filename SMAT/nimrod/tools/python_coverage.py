import os
import subprocess
import tempfile
import json
from pathlib import Path
import logging


class PythonCoverage:
    """
    Python coverage analysis class - equivalent to Jacoco for Java.
    Uses the coverage.py library to measure code coverage.
    """
    
    def __init__(self, python_executor):
        self.python = python_executor

    def install_coverage(self):
        """Install coverage.py if not available."""
        try:
            import coverage
            return True
        except ImportError:
            try:
                subprocess.check_call([
                    self.python.python_executable, '-m', 'pip', 'install', 'coverage'
                ])
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install coverage: {e}")
                return False

    def run_with_coverage(self, python_file, test_code, source_files=None):
        """
        Run Python code with coverage measurement.
        
        Args:
            python_file: The main Python file to analyze
            test_code: The test code to execute
            source_files: List of source files to include in coverage
        
        Returns:
            Coverage data and results
        """
        if not self.install_coverage():
            raise RuntimeError("Could not install coverage.py")
        
        # Create temporary files for the test
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, 'test_runner.py')
            coverage_file = os.path.join(temp_dir, '.coverage')
            
            # Write the test code to a file
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_code)
            
            # Prepare coverage command
            coverage_cmd = [
                self.python.python_executable, '-m', 'coverage', 'run',
                '--data-file', coverage_file
            ]
            
            if source_files:
                for source in source_files:
                    coverage_cmd.extend(['--source', source])
            else:
                # Include the directory of the python_file
                source_dir = os.path.dirname(os.path.abspath(python_file))
                coverage_cmd.extend(['--source', source_dir])
            
            coverage_cmd.append(test_file)
            
            try:
                # Run the test with coverage
                result = subprocess.run(
                    coverage_cmd,
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    logging.warning(f"Test execution returned non-zero: {result.stderr}")
                
                # Generate coverage report
                coverage_data = self._generate_coverage_report(coverage_file, temp_dir)
                
                return {
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode,
                    'coverage': coverage_data
                }
                
            except subprocess.TimeoutExpired:
                logging.error("Coverage execution timed out")
                raise
            except Exception as e:
                logging.error(f"Error running coverage: {e}")
                raise

    def _generate_coverage_report(self, coverage_file, temp_dir):
        """Generate coverage report in JSON format."""
        try:
            # Generate JSON report
            json_report_cmd = [
                self.python.python_executable, '-m', 'coverage', 'json',
                '--data-file', coverage_file,
                '-o', os.path.join(temp_dir, 'coverage.json')
            ]
            
            subprocess.run(json_report_cmd, check=True, cwd=temp_dir)
            
            # Read the JSON report
            json_file = os.path.join(temp_dir, 'coverage.json')
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    coverage_data = json.load(f)
                return coverage_data
            else:
                return {}
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to generate coverage report: {e}")
            return {}

    def analyze_behavioral_differences(self, base_file, left_file, right_file, merge_file, test_inputs):
        """
        Analyze behavioral differences between different versions of Python files.
        
        Args:
            base_file: Base version Python file
            left_file: Left branch Python file  
            right_file: Right branch Python file
            merge_file: Merged version Python file
            test_inputs: List of test inputs to execute
            
        Returns:
            Dictionary with behavioral analysis results
        """
        results = {}
        
        for version_name, file_path in [
            ('base', base_file), ('left', left_file), 
            ('right', right_file), ('merge', merge_file)
        ]:
            version_results = []
            
            for test_input in test_inputs:
                try:
                    # Create test code for this input
                    test_code = self._create_test_code(file_path, test_input)
                    
                    # Run with coverage
                    coverage_result = self.run_with_coverage(file_path, test_code, [file_path])
                    
                    version_results.append({
                        'input': test_input,
                        'output': coverage_result.get('stdout', ''),
                        'error': coverage_result.get('stderr', ''),
                        'coverage': coverage_result.get('coverage', {}),
                        'success': coverage_result.get('returncode', 1) == 0
                    })
                    
                except Exception as e:
                    logging.error(f"Error testing {version_name} with input {test_input}: {e}")
                    version_results.append({
                        'input': test_input,
                        'output': '',
                        'error': str(e),
                        'coverage': {},
                        'success': False
                    })
            
            results[version_name] = version_results
        
        return results

    def _create_test_code(self, python_file, test_input):
        """Create test code for a specific input."""
        # Import the module and extract the main class/function
        module_name = Path(python_file).stem
        
        test_code = f"""
import sys
import os
sys.path.insert(0, os.path.dirname('{python_file}'))

from {module_name} import *

# Test execution
try:
    # Assuming DiscountCalculator class based on the example
    calculator = DiscountCalculator()
    result = calculator.apply({test_input})
    print(f"Input: {test_input}, Output: {{result}}")
except Exception as e:
    print(f"Error with input {test_input}: {{e}}")
"""
        return test_code

    def compare_behaviors(self, results_dict):
        """
        Compare behaviors between different versions.
        
        Args:
            results_dict: Dictionary with results from analyze_behavioral_differences
            
        Returns:
            Dictionary with comparison results and detected conflicts
        """
        conflicts = []
        base_results = results_dict.get('base', [])
        left_results = results_dict.get('left', [])
        right_results = results_dict.get('right', [])
        merge_results = results_dict.get('merge', [])
        
        # Compare outputs for each test input
        for i in range(len(base_results)):
            if i < len(left_results) and i < len(right_results) and i < len(merge_results):
                base_output = base_results[i]['output']
                left_output = left_results[i]['output']
                right_output = right_results[i]['output']
                merge_output = merge_results[i]['output']
                
                test_input = base_results[i]['input']
                
                # Check for semantic conflicts
                if (left_output != base_output and right_output != base_output):
                    # Both branches changed behavior
                    if merge_output != left_output and merge_output != right_output:
                        conflicts.append({
                            'type': 'semantic_conflict',
                            'input': test_input,
                            'base_output': base_output,
                            'left_output': left_output,
                            'right_output': right_output,
                            'merge_output': merge_output,
                            'description': 'Merge result differs from both branches'
                        })
                    elif left_output != right_output and merge_output == base_output:
                        conflicts.append({
                            'type': 'potential_conflict',
                            'input': test_input,
                            'base_output': base_output,
                            'left_output': left_output,
                            'right_output': right_output,
                            'merge_output': merge_output,
                            'description': 'Both branches changed but merge reverted to base'
                        })
        
        return {
            'conflicts': conflicts,
            'total_tests': len(base_results),
            'conflict_count': len(conflicts)
        }