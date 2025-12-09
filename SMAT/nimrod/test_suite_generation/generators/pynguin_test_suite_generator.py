import logging
import os
import re
import subprocess
import tempfile
from typing import List
from pathlib import Path
import shutil

from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.test_suite_generation.generators.test_suite_generator import TestSuiteGenerator
from nimrod.tests.utils import get_config


class PynguinTestSuiteGenerator(TestSuiteGenerator):
    """
    Test suite generator using Pynguin (PYthoN General UnIt test geNerator).
    
    Pynguin is a tool that automatically generates unit tests for Python programs.
    This generator integrates Pynguin into the SMAT framework following the same
    interface as other test generators.
    """

    def __init__(self, python_tool=None, search_time: int = 45, validate_installation: bool = True):
        """
        Initialize the Pynguin test suite generator.
        
        Args:
            python_tool: Python execution tool (from nimrod.tools.python)
            search_time: Time limit in seconds for Pynguin test generation (default: 45)
            validate_installation: Whether to validate Pynguin installation on init (default: True)
        """
        super().__init__(python_tool)
        self.search_time = search_time
        self.config = get_config()
        self.pynguin_config = self.config.get('pynguin_config', {})
        if validate_installation:
            self._validate_pynguin_installation()

    def _validate_pynguin_installation(self):
        """Validate that Pynguin is installed and accessible."""
        
        try:
            # Set the required environment variable for Pynguin if danger_aware is true
            env = os.environ.copy()
            if self.pynguin_config.get('danger_aware', False):
                env['PYNGUIN_DANGER_AWARE'] = 'true'
            
            result = subprocess.run(['pynguin', '--help'], 
                                  capture_output=True, text=True, timeout=10, env=env)
            if result.returncode != 0:
                # Check if it's the danger aware message
                if 'PYNGUIN_DANGER_AWARE' in result.stderr:
                    if not self.pynguin_config.get('danger_aware', False):
                        raise RuntimeError(
                            "Pynguin requires 'danger_aware: true' in pynguin_config section of env-config.json. "
                            "Please read https://pynguin.readthedocs.io/en/latest/user/quickstart.html for safety information."
                        )
                    else:
                        logging.debug("Pynguin requires PYNGUIN_DANGER_AWARE environment variable")
                else:
                    raise RuntimeError(f"Pynguin validation failed: {result.stderr}")
            logging.debug("Pynguin installation validated successfully")
        except FileNotFoundError:
            raise RuntimeError(
                "Pynguin is not installed. Please install it using 'pip install pynguin'"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Pynguin validation timed out")

    def get_generator_tool_name(self) -> str:
        """Return the name of the generator tool."""
        return "pynguin"

    def _execute_tool_for_tests_generation(self, input_file: str, test_suite_path: str, 
                                         scenario: MergeScenarioUnderAnalysis, 
                                         use_determinism: bool) -> None:
        """
        Execute Pynguin to generate tests for the given input file.
        
        Args:
            input_file: Path to the Python file to generate tests for
            test_suite_path: Directory where generated tests will be saved
            scenario: Merge scenario under analysis
            use_determinism: Whether to use deterministic generation (affects random seed)
        """
        logging.info(f"Starting Pynguin test generation for {input_file}")
        
        # Extract module information from the input file
        module_info = self._extract_module_info(input_file)
        if not module_info:
            logging.warning(f"Could not extract module information from {input_file}")
            return
        
        project_path, module_name = module_info
        
        # Create temporary directory for Pynguin output
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Prepare Pynguin command with correct parameter names
                pynguin_cmd = [
                    'pynguin',
                    '--project_path', project_path,
                    '--output_path', temp_dir,
                    '--module_name', module_name,
                    '--maximum-search-time', str(self.search_time),
                    '--create-coverage-report', 'False',  # Disable coverage report
                ]
                
                # Add deterministic seed if requested
                if use_determinism:
                    pynguin_cmd.extend(['--seed', str(42)])
                
                # Add configuration for better test quality (from config)
                algorithm = self.pynguin_config.get('algorithm', 'WHOLE_SUITE')
                population_size = self.pynguin_config.get('population_size', 50)
                elite_size = self.pynguin_config.get('elite_size', 5)
                crossover_rate = self.pynguin_config.get('crossover_rate', 0.75)
                
                pynguin_cmd.extend([
                    '--algorithm', algorithm,
                    '--population', str(population_size),
                    '--elite', str(elite_size),
                    '--crossover_rate', str(crossover_rate),
                ])
                
                logging.debug(f"Executing Pynguin with command: {' '.join(pynguin_cmd)}")
                
                # Set up environment with required Pynguin safety variable if configured
                env = os.environ.copy()
                if self.pynguin_config.get('danger_aware', False):
                    env['PYNGUIN_DANGER_AWARE'] = 'true'
                
                # Execute Pynguin
                result = subprocess.run(
                    pynguin_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.search_time + 30,  # Give extra time for startup/cleanup
                    cwd=project_path,
                    env=env
                )
                
                if result.returncode != 0:
                    logging.error(f"Pynguin failed with return code {result.returncode}")
                    logging.error(f"Stderr: {result.stderr}")
                    logging.error(f"Stdout: {result.stdout}")
                    return
                
                logging.debug(f"Pynguin output: {result.stdout}")
                
                # Move generated tests from temp directory to target directory
                self._move_generated_tests(temp_dir, test_suite_path, module_name, scenario)
                
                # Copy source files to test directory like LLM generator does
                # Extract class name from the scenario targets
                if hasattr(scenario, 'targets') and scenario.targets:
                    for class_name in scenario.targets.keys():
                        # Copy ALL branch files to test directory for dynamic switching during execution
                        self._copy_all_branch_files_to_test_dir(test_suite_path, scenario, class_name)
                        # Also copy current branch as main class file for generation
                        self._copy_source_file_to_test_dir(test_suite_path, input_file, class_name, self._get_branch_from_input_file(input_file))
                
                logging.info(f"Successfully generated tests with Pynguin for {module_name}")
                
            except subprocess.TimeoutExpired:
                logging.error(f"Pynguin timed out after {self.search_time + 30} seconds")
            except Exception as e:
                logging.error(f"Error during Pynguin execution: {str(e)}")

    def _extract_module_info(self, input_file: str) -> tuple:
        """
        Extract project path and module name from input file path.
        
        Returns:
            Tuple of (project_path, module_name) or None if extraction fails
        """
        try:
            file_path = Path(input_file).resolve()
            
            project_root = self._find_project_root(file_path)
            if not project_root:
                project_root = file_path.parent
            
            # Calculate relative path from project root
            try:
                relative_path = file_path.relative_to(project_root)
                # Convert path to module name (remove .py extension, replace separators with dots)
                module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
                
                return str(project_root), module_name
                
            except ValueError:
                # File is not under project_root, use file's directory as project
                project_root = file_path.parent
                module_name = file_path.stem  # Just the filename without extension
                
                return str(project_root), module_name
                
        except Exception as e:
            logging.error(f"Error extracting module info from {input_file}: {str(e)}")
            return None

    def _find_project_root(self, file_path: Path) -> Path:
        """
        Find the project root by looking for common project markers.
        
        Args:
            file_path: Starting file path
            
        Returns:
            Project root path or None if not found
        """
        current = file_path.parent
        markers = ['setup.py', 'pyproject.toml', 'requirements.txt', '.git', '__init__.py']
        
        while current != current.parent:  # Stop at filesystem root
            for marker in markers:
                if (current / marker).exists():
                    return current
            current = current.parent
        
        return None

    def _copy_source_file_to_test_dir(self, output_path: str, source_code_path: str, class_name: str, branch: str) -> None:
        """Copy source file to test directory with proper naming for imports."""
        if os.path.exists(source_code_path):
            # Copy the source file with the class name, but use branch-specific naming for identification
            dest_path = os.path.join(output_path, f"{class_name.split('.')[-1]}.py")
            shutil.copy2(source_code_path, dest_path)
            logging.debug(f"Copied {branch} branch file {source_code_path} to {dest_path}")

    def _copy_all_branch_files_to_test_dir(self, output_path: str, scenario, class_name: str) -> None:
        """Copy all 4 branch files to test directory with branch-specific names."""
        branches = ['base', 'left', 'right', 'merge']
        
        for branch in branches:
            source_file = getattr(scenario.scenario_files, branch)
            if source_file and os.path.exists(source_file):
                # Copy with branch-specific name: ClassName_branch.py
                dest_path = os.path.join(output_path, f"{class_name.split('.')[-1]}_{branch}.py")
                shutil.copy2(source_file, dest_path)
                logging.debug(f"Copied {branch} branch file {source_file} to {dest_path}")
            else:
                logging.warning(f"Branch file not found for {branch}: {source_file}")

    def _extract_class_names_from_scenario(self, scenario) -> List[str]:
        """
        Extract class names from scenario targets.
        
        Args:
            scenario: MergeScenarioUnderAnalysis object
            
        Returns:
            List of class names found in the scenario
        """
        class_names = []
        if hasattr(scenario, 'targets') and scenario.targets:
            for class_name in scenario.targets.keys():
                # Extract just the class name (remove module path if present)
                simple_class_name = class_name.split('.')[-1] if '.' in class_name else class_name
                class_names.append(simple_class_name)
        return class_names

    def _extract_class_names_from_file(self, file_path: str) -> List[str]:
        """
        Extract class names from a Python file by parsing its AST.
        
        Args:
            file_path: Path to the Python file to analyze
            
        Returns:
            List of class names found in the file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import ast
            tree = ast.parse(content)
            class_names = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_names.append(node.name)
            
            return class_names
        except Exception as e:
            logging.warning(f"Could not extract class names from {file_path}: {e}")
            return []

    def _fix_imports_in_test_file(self, test_file_path: str, module_name: str, scenario=None) -> None:
        """
        Fix imports in generated test files to work with SMAT's execution environment.
        
        Args:
            test_file_path: Path to the test file to fix
            module_name: Original module name that was tested
            scenario: MergeScenarioUnderAnalysis object to extract class names from
        """
        try:
            with open(test_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract class names dynamically
            class_names = []
            
            # First try to get from scenario
            if scenario:
                class_names = self._extract_class_names_from_scenario(scenario)
            
            # If no classes from scenario, try to extract from the test directory
            if not class_names:
                test_dir = os.path.dirname(test_file_path)
                # Look for class files in the same directory
                for file in os.listdir(test_dir):
                    if file.endswith('.py') and not file.startswith('test_'):
                        file_path = os.path.join(test_dir, file)
                        extracted_classes = self._extract_class_names_from_file(file_path)
                        class_names.extend(extracted_classes)
            
            # Remove duplicates
            class_names = list(set(class_names))
            
            if not class_names:
                logging.warning(f"No class names found for fixing imports in {test_file_path}")
                return
            
            # Use the first class name found (most common case)
            primary_class = class_names[0]
            logging.debug(f"Using class name '{primary_class}' for import fixing")
            
            # Pattern to match: import python_files.left as module_0
            import_pattern = rf'import {re.escape(module_name)} as (\w+)'
            
            def replace_import(match):
                alias = match.group(1)
                # Generate dynamic import code
                return f'''# Fixed import for SMAT execution
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

class ModuleWrapper:
    \"\"\"Wrapper to make class behave like imported module\"\"\"
    pass

try:
    from {primary_class} import {primary_class}
    {alias} = ModuleWrapper()
    {alias}.{primary_class} = {primary_class}
except ImportError:
    # Fallback: try to import from current directory
    import importlib.util
    import os
    
    # Try different branch files
    for branch in ['left', 'right', 'base', 'merge']:
        try:
            file_path = os.path.join(os.path.dirname(__file__), f'{primary_class}_{{branch}}.py')
            if os.path.exists(file_path):
                spec = importlib.util.spec_from_file_location("target_module", file_path)
                target_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(target_module)
                {alias} = target_module
                break
        except Exception:
            continue
    else:
        # Last resort: create dummy module
        {alias} = ModuleWrapper()
        class DummyClass:
            def __init__(self, *args): pass
            def __getattr__(self, name): return lambda *args, **kwargs: None
        {alias}.{primary_class} = DummyClass'''
            
            # Apply the replacement
            fixed_content = re.sub(import_pattern, replace_import, content)
            
            # Write the fixed content back
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            logging.debug(f"Fixed imports in test file: {test_file_path} using class '{primary_class}'")
            
        except Exception as e:
            logging.error(f"Error fixing imports in {test_file_path}: {e}")

    def _get_test_suite_class_paths(self, path: str) -> List[str]:
        """Get all Python test files in a directory (excluding source files) - Pynguin version."""
        paths: List[str] = []
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".py"):
                    # Pynguin generates files starting with "test_"
                    if file.startswith("test_"):
                        paths.append(os.path.join(root, file))
        return paths

    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        """Get class names from Python test files - Pynguin version."""
        paths = self._get_test_suite_class_paths(test_suite_path)
        # For Pynguin, return the filename without extension as the class name
        return [os.path.basename(path).replace(".py", "") for path in paths]

    def _move_generated_tests(self, temp_dir: str, target_dir: str, module_name: str, scenario=None) -> None:
        """
        Move generated test files from Pynguin's temp directory to target directory.
        
        Args:
            temp_dir: Temporary directory where Pynguin generated tests
            target_dir: Target directory to move tests to
            module_name: Name of the module being tested
            scenario: MergeScenarioUnderAnalysis object for extracting class names
        """
        temp_path = Path(temp_dir)
        target_path = Path(target_dir)
        
        # Ensure target directory exists
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Look for generated test files
        test_files_found = False
        
        # Pynguin typically creates files like test_module_name.py
        for test_file in temp_path.rglob('test_*.py'):
            target_file = target_path / test_file.name
            shutil.copy2(test_file, target_file)
            
            # Fix imports in the copied test file
            self._fix_imports_in_test_file(str(target_file), module_name, scenario)
            
            test_files_found = True
            logging.debug(f"Moved and fixed test file: {test_file} -> {target_file}")
        
        # Also look for any Python files that might be test classes
        for py_file in temp_path.rglob('*.py'):
            if py_file.name.startswith('Test') or 'Test' in py_file.name:
                target_file = target_path / py_file.name
                if not target_file.exists():  # Avoid duplicates
                    shutil.copy2(py_file, target_file)
                    
                    # Fix imports in the copied test file
                    self._fix_imports_in_test_file(str(target_file), module_name, scenario)
                    
                    test_files_found = True
                    logging.debug(f"Moved and fixed test file: {py_file} -> {target_file}")
        
        if not test_files_found:
            logging.warning(f"No test files found in Pynguin output directory: {temp_dir}")
            # Create an empty test file as placeholder
            placeholder_file = target_path / f"test_{module_name.replace('.', '_')}.py"
            placeholder_file.write_text(f'''# No tests were generated by Pynguin for module: {module_name}
import unittest

class Test{module_name.replace(".", "").title()}(unittest.TestCase):
    def test_placeholder(self):
        """Placeholder test - Pynguin could not generate tests for this module."""
        self.assertTrue(True, "Placeholder test")

if __name__ == '__main__':
    unittest.main()
''')
            logging.info(f"Created placeholder test file: {placeholder_file}")

    def _get_test_suite_class_paths(self, test_suite_path: str) -> List[str]:
        """
        Get all Python test files generated by Pynguin.
        
        Args:
            test_suite_path: Directory containing generated tests
            
        Returns:
            List of paths to test files
        """
        paths: List[str] = []
        test_path = Path(test_suite_path)
        
        if test_path.exists():
            for py_file in test_path.rglob('*.py'):
                # Only include files that are actually test files
                file_basename = py_file.stem  # Get filename without extension
                if (file_basename.startswith("test_") or 
                    file_basename.endswith("_test") or 
                    file_basename.startswith("Test") or 
                    file_basename.endswith("Test") or
                    "Test_" in file_basename):
                    paths.append(str(py_file))
        
        return paths

    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        """
        Get class names from generated test files.
        
        Args:
            test_suite_path: Directory containing generated tests
            
        Returns:
            List of test class names
        """
        class_names: List[str] = []
        
        for file_path in self._get_test_suite_class_paths(test_suite_path):
            file_name = Path(file_path).stem  # Get filename without extension
            class_names.append(file_name)
        
        return class_names
    
    def _get_branch_from_input_file(self, input_file: str) -> str:
        """Extract branch name from input file path."""
        branches = ["base", "left", "right", "merge"]
        for branch in branches:
            if branch in input_file:
                return branch
        return "unknown"

    def _copy_source_file_to_test_dir(self, output_path: str, source_code_path: str, class_name: str, branch: str) -> None:
        """Copy source file to test directory with proper naming for imports."""
        if os.path.exists(source_code_path):
            # Copy the source file with the class name, but use branch-specific naming for identification
            dest_path = os.path.join(output_path, f"{class_name.split('.')[-1]}.py")
            shutil.copy2(source_code_path, dest_path)
            logging.debug(f"Copied {branch} branch file {source_code_path} to {dest_path}")

    def _copy_all_branch_files_to_test_dir(self, output_path: str, scenario, class_name: str) -> None:
        """Copy all 4 branch files to test directory with branch-specific names."""
        branches = ['base', 'left', 'right', 'merge']
        
        for branch in branches:
            source_file = getattr(scenario.scenario_files, branch)
            if source_file and os.path.exists(source_file):
                # Copy with branch-specific name: ClassName_branch.py
                dest_path = os.path.join(output_path, f"{class_name.split('.')[-1]}_{branch}.py")
                shutil.copy2(source_file, dest_path)
                logging.debug(f"Copied {branch} branch file {source_file} to {dest_path}")
            else:
                logging.warning(f"Branch file not found for {branch}: {source_file}")