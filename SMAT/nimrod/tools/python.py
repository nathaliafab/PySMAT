import logging
import os
import sys
import subprocess
import ast
import importlib.util
import tempfile
from pathlib import Path

TIMEOUT = 10 * 60


class Python:
    """
    Python execution and management class for handling Python files instead of Java.
    """

    def __init__(self, python_executable=None):
        self.python_executable = python_executable or sys.executable
        self._check()

    def _check(self):
        """Check if Python executable is available."""
        try:
            self._version()
        except FileNotFoundError:
            logging.error(f"Python executable not found: {self.python_executable}")
            raise SystemExit()

    def _version(self):
        """Get Python version."""
        return self.simple_exec('-V')

    def simple_exec(self, *args):
        """Execute Python with simple arguments."""
        return self.exec_python(None, self.get_env(), TIMEOUT, *args)

    def exec_python(self, cwd, env, timeout, *args):
        """Execute Python command."""
        return self._exec(self.python_executable, cwd, env, timeout, *args)

    def exec_python_file(self, python_file, cwd=None, env=None, timeout=TIMEOUT, *args):
        """Execute a Python file."""
        args = list(args)
        args.insert(0, python_file)
        return self._exec(self.python_executable, cwd, env or self.get_env(), timeout, *args)

    def exec_python_code(self, code, cwd=None, env=None, timeout=TIMEOUT):
        """Execute Python code directly."""
        return self._exec(self.python_executable, cwd, env or self.get_env(), timeout, '-c', code)

    @staticmethod
    def _exec(program, cwd, env, timeout, *args):
        """Execute command with subprocess."""
        try:
            command = [program] + list(args)
            
            logging.debug(f"Starting execution of Python command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)
                
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Python command failed: {e}")
            raise e
        except subprocess.TimeoutExpired as e:
            logging.error(f"Python command timed out: {e}")
            raise e
        except FileNotFoundError as e:
            logging.error(f'[ERROR] {program}: not found.')
            raise e

    def get_env(self, variables=None):
        """Get environment variables for Python execution."""
        env = os.environ.copy()
        env['PYTHONPATH'] = env.get('PYTHONPATH', '') + os.pathsep + os.getcwd()
        
        if variables:
            for key, value in variables.items():
                env[key] = value
                
        return env

    def validate_syntax(self, python_file):
        """Validate Python file syntax."""
        try:
            with open(python_file, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            return True
        except SyntaxError as e:
            logging.error(f"Syntax error in {python_file}: {e}")
            return False
        except Exception as e:
            logging.error(f"Error validating {python_file}: {e}")
            return False

    def import_module_from_file(self, file_path, module_name=None):
        """Import a Python module from a file path."""
        if module_name is None:
            module_name = Path(file_path).stem
            
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            raise ImportError(f"Could not load spec from {file_path}")
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def get_classes_from_file(self, python_file):
        """Extract class names from a Python file."""
        try:
            with open(python_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    
            return classes
        except Exception as e:
            logging.error(f"Error parsing {python_file}: {e}")
            return []

    def get_methods_from_class(self, python_file, class_name):
        """Extract method names from a specific class in a Python file."""
        try:
            with open(python_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            methods = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                            
            return methods
        except Exception as e:
            logging.error(f"Error parsing {python_file}: {e}")
            return []

    def create_test_runner_file(self, test_code, output_file):
        """Create a temporary Python file for running tests."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(test_code)