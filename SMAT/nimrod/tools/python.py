import logging
import os
import sys
import subprocess

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
