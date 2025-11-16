import json
import logging
import os
import ast
import re
from typing import List, Dict, Union, Any, Optional
from time import time
from pathlib import Path

from nimrod.core.merge_scenario_under_analysis import MergeScenarioUnderAnalysis
from nimrod.test_suite_generation.generators.prompt_manager import PromptManager
from nimrod.test_suite_generation.generators.test_suite_generator import TestSuiteGenerator
from nimrod.tests.utils import get_config
from nimrod.utils import load_json, save_json

from google import genai
from google.genai import types as genai_types
import shutil


class GeminiApi:
    
    def __init__(self, api_key: str, timeout_seconds: int, temperature: float, model: str) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.model = model
        self.client = genai.Client(api_key=api_key)
        self.branch: Optional[str] = None
        
        logging.debug(f"Gemini API initialized with model: {model}, temperature: {temperature}")
    
    def set_branch(self, branch: str) -> None:
        """Sets the branch to be used in the API requests."""
        self.branch = branch

    def generate_output(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generates output by sending messages to the Gemini API."""
        start_time = time()

        content = self._convert_messages_to_gemini_format(messages)
        generation_config = genai_types.GenerateContentConfig(
            temperature=self.temperature,
            seed=666,
            max_output_tokens=8192,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=[content],
            config=generation_config,
        )

        end_time = time()
        duration_ns = int((end_time - start_time) * 1_000_000_000)
        response_text = response.text if hasattr(response, 'text') else str(response)

        return {
            "response": response_text,
            "total_duration": duration_ns,
        }
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> str:
        content_parts = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                content_parts.append(f"System: {content}")
            elif role == "user":
                content_parts.append(content)
            elif role == "assistant":
                content_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(content_parts)
        

class PythonTestSuiteGenerator(TestSuiteGenerator):
    
    def __init__(self, python_tool=None, model_key: str = "gemini", model_config: Dict[str, Any] = None):
        super().__init__(python_tool)
        self.model_key = model_key
        self.model_config = model_config or {}
        self.api = None
        self.prompt_manager = PromptManager()

        # Loads global configurations
        global_config = get_config()

        # Prompt configurations (priority: model_config > global_config > default)
        self.prompt_template = (
            self.model_config.get("prompt_template") or 
            global_config.get("prompt_template") or 
            "zero_shot"
        )
        
        logging.info(f"Initialized {self.model_key} with template: {self.prompt_template}")
    
    def generate_messages_list(self, method_info: Dict[str, str], full_class_name: str,
                               branch: str, output_path: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Generates messages for API requests using the configurable prompt system.
        Supports different templates (zero-shot, one-shot) and context combinations.
        """
        self.api.set_branch(branch)  # Set the branch
        class_name = full_class_name.split('.')[-1]
        method_name = method_info.get("method_name", "")
        
        logging.debug(f"Generating messages for {class_name}.{method_name} using template: {self.prompt_template}")

        # Generate messages using the PromptManager
        messages_dict = self.prompt_manager.generate_all_combinations(
            method_info=method_info,
            class_name=class_name,
            branch=branch,
            template_name=self.prompt_template
        )
        
        # Save generated messages
        self.prompt_manager.save_generated_messages(
            messages_dict=messages_dict,
            output_path=output_path,
            class_name=class_name,
            method_name=method_name
        )
        
        logging.info(f"Generated {len(messages_dict)} prompt variations for {class_name}.{method_name}")

        return messages_dict
    
    def _ensure_api_initialized(self) -> None:
        """Initializes the API if it has not been initialized yet."""
        if self.api is not None:
            return

        config = get_config()
        api_params = config["api_params"]
        model_params = self.model_config or api_params[self.model_key]
        api_key = model_params["api_key"]

        self.api = GeminiApi(
            api_key=api_key,
            timeout_seconds=model_params.get("timeout_seconds", 60),
            temperature=model_params.get("temperature", 0),
            model=model_params.get("model", "gemini-2.5-flash"),
        )

    def get_generator_tool_name(self) -> str:
        self._ensure_api_initialized()
        config_suffix = self._generate_config_suffix()
        return f"{self.model_key.upper()}{config_suffix}"
    
    def _generate_config_suffix(self) -> str:
        """Generates a suffix with configuration information for folder identification"""
        if not self.api:
            return ""

        # Prompt format: ZS (zero-shot) or 1S (one-shot)
        prompt_code = "ZS" if self.prompt_template == "zero_shot" else "1S"

        # Temperature: T00, T05, T07, etc. (always with 2 digits)
        temp_value = int(self.api.temperature * 100)  # 0.7 -> 70, 0.05 -> 5, 0 -> 0
        temp_code = f"T{temp_value:02d}"  # Formats with 2 digits: T00, T05, T07
        
        return f"_{prompt_code}_{temp_code}"

    def _get_test_suite_class_paths(self, path: str) -> List[str]:
        """Get all Python test files in a directory (excluding source files)."""
        paths: List[str] = []
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".py"):
                    # Only include files that are actually test files
                    # Skip source files like DiscountCalculator.py
                    file_basename = file.replace(".py", "")
                    if (file_basename.startswith("Test") or 
                        file_basename.endswith("Test") or 
                        "Test_" in file_basename or
                        file.startswith("test_")):
                        paths.append(os.path.join(root, file))
        return paths

    def _get_test_suite_class_names(self, test_suite_path: str) -> List[str]:
        """Get class names from Python test files."""
        return [os.path.basename(path).replace(".py", "") for path in self._get_test_suite_class_paths(test_suite_path)]

    def save_output(self, test_template: str, output: str, dir: str, output_file_name: str) -> None:
        """Saves the output generated by the model to a file, replacing #TEST_METHODS# in the template."""
        # Remove content between <think> tags
        output = re.sub(r'<think>.*?</think>', '', output, flags=re.DOTALL)

        # Extract only the content inside ``` blocks (excluding the ``` markers)
        matches = re.findall(r'```(?:\w+)?\n?(.*?)```', output, flags=re.DOTALL)
        if matches:
            output = '\n'.join(matches).strip()
        
        # Remove lines starting with "number. <text>" 
        output = re.sub(r"^\d+\.\s.*$", "", output, flags=re.MULTILINE)

        # Look for test methods or setup methods and extract them
        lines = output.split('\n')
        test_methods = []
        current_method = []
        in_method = False
        
        for line in lines:
            # Check if this line starts a new test method
            if line.strip().startswith('def test_') or line.strip().startswith('def setUp'):
                # Save previous method if exists
                if current_method:
                    test_methods.append('\n'.join(current_method))
                # Start new method
                current_method = ['    ' + line.strip()]  # Add proper indentation
                in_method = True
            elif in_method and line.strip():
                # Continue adding lines to current method with proper indentation
                if line.startswith('    '):
                    current_method.append('    ' + line)  # Add extra indentation for class method
                elif line.strip():
                    current_method.append('        ' + line.strip())  # Add method body indentation
            elif in_method and not line.strip():
                # Empty line within method
                current_method.append('')
        
        # Add the last method
        if current_method:
            test_methods.append('\n'.join(current_method))
        
        # Join all methods with proper spacing
        indented_output = '\n\n'.join(test_methods) if test_methods else '    pass  # No test methods found'

        llm_outputs_dir = os.path.join(dir, "llm_outputs")
        output_file_path = os.path.join(llm_outputs_dir, f"{output_file_name}.py")
        filled_template = test_template.replace("#TEST_METHODS#", indented_output)

        os.makedirs(llm_outputs_dir, exist_ok=True)
        with open(output_file_path, "w", encoding='utf-8') as file:
            file.write(filled_template)

    def parse_code(self, source_code_path: str) -> tuple:
        """Parse Python source code using AST."""
        with open(source_code_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        tree = ast.parse(source_code)
        return source_code, tree

    def extract_class_info(self, source_code_path: str, full_method_name: str, full_class_name: str) -> tuple:
        """
        Extract constructor (__init__) and target method from Python source code.
        """
        try:
            class_name = full_class_name.split('.')[-1]
            method_name = full_method_name.split('(')[0]
            
            source_code, tree = self.parse_code(source_code_path)
            
            class_constructors = []
            class_method = ""
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    # Extract only constructor and target method
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if item.name == "__init__":
                                class_constructors.append(ast.unparse(item))
                            elif item.name == method_name:
                                class_method = ast.unparse(item)
                    break
            
            return class_constructors, class_method

        except Exception as e:
            logging.error(f"An error occurred while extracting class info for '{full_class_name}': {e}")
            raise e

    def save_scenario_infos(self, scenario_infos_path: str, class_name: str, methods: Union[List[str], List[Dict[str, str]]], source_code_path: str) -> None:
        """Store relevant scenario information (for each class and method) in a JSON file"""
        if os.path.exists(scenario_infos_path):
            scenario_infos_dict = load_json(scenario_infos_path)
        else:
            scenario_infos_dict = {}

        if class_name not in scenario_infos_dict:
            scenario_infos_dict[class_name] = []

        for method_item in methods:
            if not isinstance(method_item, dict):
                method = method_item
                left_changes_summary = ""
                right_changes_summary = ""
            else:
                method = method_item.get("method", "")
                left_changes_summary = method_item.get("leftChangesSummary", "")
                right_changes_summary = method_item.get("rightChangesSummary", "")

            method = re.sub(r'\|', ',', method)
            constructor_codes, method_code = self.extract_class_info(source_code_path, method, class_name)

            scenario_infos_dict[class_name].append({
                'constructor_codes': constructor_codes if constructor_codes else [],
                'method_name': method,
                'method_code': method_code if method_code else "",
                'left_changes_summary': left_changes_summary,
                'right_changes_summary': right_changes_summary,
                'test_template': (
                    "import pytest\n"
                    "import sys\n"
                    "import os\n\n"
                    f"# Import the class under test\n"
                    f"from {class_name.split('.')[-1]} import {class_name.split('.')[-1]}\n\n"
                    f"class Test{class_name.split('.')[-1]}:\n"
                    "#TEST_METHODS#\n"
                )
            })

        save_json(scenario_infos_path, scenario_infos_dict)

    def save_imports(self, class_name: str, source_code_path: str, imports_path: str) -> None:
        """Extract import statements from Python source code and store them in a JSON file"""
        source_code, tree = self.parse_code(source_code_path)

        if os.path.exists(imports_path):
            imports_dict = load_json(imports_path)
        else:
            imports_dict = {}

        class_imports = imports_dict.setdefault(class_name, [])

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_line = f"import {alias.name}"
                    if alias.asname:
                        import_line += f" as {alias.asname}"
                    class_imports.append(import_line + "\n")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    import_line = f"from {module} import {alias.name}"
                    if alias.asname:
                        import_line += f" as {alias.asname}"
                    class_imports.append(import_line + "\n")

        save_json(imports_path, imports_dict)

    def _copy_source_file_to_test_dir(self, output_path: str, source_code_path: str, class_name: str, branch: str) -> None:
        """Copy source file to test directory with proper naming for imports."""
        if os.path.exists(source_code_path):
            # Copy the source file with the class name, but use branch-specific naming for identification
            dest_path = os.path.join(output_path, f"{class_name.split('.')[-1]}.py")
            shutil.copy2(source_code_path, dest_path)
            logging.info(f"Copied {branch} branch file {source_code_path} to {dest_path}")

    def _copy_all_branch_files_to_test_dir(self, output_path: str, scenario, class_name: str) -> None:
        """Copy all 4 branch files to test directory with branch-specific names."""
        branches = ['base', 'left', 'right', 'merge']
        
        for branch in branches:
            source_file = getattr(scenario.scenario_files, branch)
            if source_file and os.path.exists(source_file):
                # Copy with branch-specific name: ClassName_branch.py
                dest_path = os.path.join(output_path, f"{class_name.split('.')[-1]}_{branch}.py")
                shutil.copy2(source_file, dest_path)
                logging.info(f"Copied {branch} branch file {source_file} to {dest_path}")
            else:
                logging.warning(f"Branch file not found for {branch}: {source_file}")

    def extract_individual_tests(self, output_path: str, test_template: str, class_name: str, imports: List[str], i: int, j: int, prompt_key: str, branch: str) -> None:
        """Extract individual tests from the generated test suite and save them to separate files"""
        llm_outputs_path = os.path.join(output_path, "llm_outputs")
        counter = 0

        # Format: {i}{j}_{branch}_{class_name.split('.')[-1]}_{prompt_key}.py
        pattern = rf"^{i}{j}_{re.escape(branch)}_{re.escape(class_name.split('.')[-1])}_{prompt_key}\.py$"
        
        if not os.path.exists(llm_outputs_path):
            logging.warning(f"LLM outputs directory not found: {llm_outputs_path}")
            return
            
        files_found = [f for f in os.listdir(llm_outputs_path) if re.match(pattern, f)]
        
        if not files_found:
            logging.warning(f"No files found matching pattern: {pattern}")
            return

        for file in files_found:
            source_code_path = os.path.join(llm_outputs_path, file)
            
            try:
                with open(source_code_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                
                tree = ast.parse(source_code)
                test_methods = []
                setup_methods = []
                
                # Look for functions at module level (outside class) that start with 'test_'
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check if function is a test method (starts with 'test_')
                        if node.name.startswith('test_'):
                            test_methods.append(ast.unparse(node))
                        elif node.name in ['setUp', 'setup', 'setUpClass', 'tearDown', 'tearDownClass']:
                            setup_methods.append(ast.unparse(node))
                
                logging.info(f"Found {len(test_methods)} test methods in {file}")
                
                # Create individual test files for each test method
                for idx, test_method in enumerate(test_methods):
                    method_name = f"{class_name.split('.')[-1]}Test_{branch}_{prompt_key}_{j}_{i}_{counter}_{idx}"
                    output_file_path = os.path.join(output_path, f"{method_name}.py")

                    # Create pytest-style test file
                    imports_str = "".join(imports) if imports else ""
                    test_template_header = test_template.split("#TEST_METHODS#")[0] if "#TEST_METHODS#" in test_template else test_template
                    
                    # Properly indent the test method (it's already properly formatted from ast.unparse)
                    indented_test_method = "\n".join(f"    {line}" if line.strip() else "" for line in test_method.split("\n"))
                    
                    full_test_content = f"{test_template_header}{indented_test_method}\n"
                    
                    # Add setup methods if they exist
                    if setup_methods:
                        for setup_method in setup_methods:
                            indented_setup = "\n".join(f"    {line}" if line.strip() else "" for line in setup_method.split("\n"))
                            full_test_content = full_test_content.replace(indented_test_method, f"{indented_setup}\n\n{indented_test_method}")
                    
                    with open(output_file_path, "w", encoding='utf-8') as f:
                        f.write(full_test_content)
                    
                    logging.debug(f"Created individual test file: {method_name}.py")
                    counter += 1
                    
            except Exception as e:
                logging.error(f"Error processing file {file}: {e}")
                continue

    def find_source_code_paths(self, input_file: str, class_name: str, project_name: str) -> Dict[str, str]:
        """Find the source code files for the given class name in the specified Python file path"""
        from nimrod.tests.utils import get_base_output_path
        base_output = get_base_output_path()
        base_path = os.path.join(os.path.dirname((os.path.dirname(os.path.dirname(base_output)))), "python_files")

        return {
            "left": os.path.join(base_path, "left.py"),
            "right": os.path.join(base_path, "right.py"),
            "base": os.path.join(base_path, "base.py"),
            "merge": os.path.join(base_path, "merge.py"),
        }

    def fetch_source_code_branch(self, input_file: str, class_name: str, project_name: str) -> tuple:
        """Retrieve the source code path and branch for the given Python file path"""
        source_code_paths = self.find_source_code_paths(input_file, class_name.split('.')[-1], project_name)
        branches = ["base", "left", "right", "merge"]
        branch = next(b for b in branches if b in input_file)
        return source_code_paths.get(branch), branch, source_code_paths

    def record_output_duration(self, time_duration_path: str, output_path: str, class_name: str,
                               output_file_name: str, total_duration: int, project_name: str) -> None:
        """Record the duration of output generation for the given class and output file"""
        os.makedirs(os.path.dirname(time_duration_path), exist_ok=True)

        if not os.path.exists(time_duration_path):
            with open(time_duration_path, "w") as file:
                json.dump({}, file)

        time_duration_dict = load_json(time_duration_path)

        project_data = time_duration_dict.setdefault(project_name, {})
        class_data = project_data.setdefault(class_name, {"total_duration": 0, "outputs": {}})

        key_name = output_path.split(os.sep)[-1] + '_' + output_file_name

        total_duration_seconds = total_duration / 1_000_000_000

        duration_rounded = round(total_duration_seconds, 2)
        class_data["outputs"][key_name] = duration_rounded
        class_data["total_duration"] = round(class_data["total_duration"] + duration_rounded, 2)

        save_json(time_duration_path, time_duration_dict)

    def _execute_tool_for_tests_generation(self, input_file: str, output_path: str, scenario: MergeScenarioUnderAnalysis, use_determinism: bool) -> None:
        self._ensure_api_initialized()

        # Define paths for storing scenario information, importing data, and recording time duration
        scenario_infos_path = os.path.join(output_path, "scenario_infos.json")
        imports_path = os.path.join(output_path, "imports.json")
        
        # Generate config suffix for the duration file
        config_suffix = self._generate_config_suffix().replace("_", "") if hasattr(self, '_generate_config_suffix') else ""
        duration_filename = f"{self.model_key}{config_suffix}_time_duration.json"
        
        time_duration_path = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(output_path))), "reports", duration_filename)

        project_name = scenario.project_name
        targets = scenario.targets

        # Fetch the source code paths for each class and save the associated scenario information and import data
        for class_name, methods in targets.items():
            source_code_path, branch, source_paths = self.fetch_source_code_branch(input_file, class_name, project_name)
            self.save_scenario_infos(scenario_infos_path, class_name, methods, source_code_path)
            self.save_imports(class_name, source_code_path, imports_path)
            # Copy ALL branch files to test directory for dynamic switching during execution
            self._copy_all_branch_files_to_test_dir(output_path, scenario, class_name)
            # Also copy current branch as main class file for generation
            self._copy_source_file_to_test_dir(output_path, source_code_path, class_name, branch)

        # Load scenario information and import data into dictionaries
        scenario_infos_dict = load_json(scenario_infos_path)
        imports_dict = load_json(imports_path)

        # Generate tests for each method in every class and save the results
        for class_name, scenario_infos_list in scenario_infos_dict.items():
            logging.debug("Generating tests for target methods in class '%s'", class_name)
            for i, method_info in enumerate(scenario_infos_list):
                messages_list = self.generate_messages_list(method_info, class_name, branch, output_path)
                test_template = method_info.get("test_template", "")
                self._process_prompts(messages_list=messages_list, test_template=test_template, output_path=output_path,
                                      branch=branch, class_name=class_name, imports=imports_dict.get(class_name, []),
                                      i=i, time_duration_path=time_duration_path, project_name=project_name)

    def _process_prompts(self, messages_list: Dict[str, List[Dict[str, str]]], test_template: str, output_path: str, branch: str,
                         class_name: str, imports: List[str], i: int, time_duration_path: str, project_name: str,
                         num_outputs: int = 1) -> None:
        for j in range(num_outputs):
            for prompt_key, messages in messages_list.items():
                output_file_name = f"{i}{j}_{branch}_{class_name.split('.')[-1]}_{prompt_key}"
                self._process_single_prompt(messages, test_template, output_path, branch, class_name, imports, i, j, time_duration_path, project_name, output_file_name, prompt_key)

    def _process_single_prompt(self, messages: List[Dict[str, str]], test_template: str, output_path: str, branch: str,
                               class_name: str, imports: List[str], i: int, j: int, time_duration_path: str,
                               project_name: str, output_file_name: str, prompt_key: str) -> None:
        output = self.api.generate_output(messages)
        response = output.get("response", "Response not found.")
        total_duration = int(output.get("total_duration", self.api.timeout_seconds * 1_000_000_000))
        self.save_output(test_template, response, output_path, output_file_name)
        self.record_output_duration(time_duration_path, output_path, class_name, output_file_name, total_duration, project_name)
        self.extract_individual_tests(output_path, test_template, class_name, imports, i, j, prompt_key, branch)