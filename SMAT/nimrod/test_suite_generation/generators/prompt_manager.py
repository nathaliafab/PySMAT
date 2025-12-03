#!/usr/bin/env python3
import os
from typing import Dict, List, Any, Optional
from nimrod.utils import save_json, load_json


class PromptManager:    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "prompt_templates.json")
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        try:
            return load_json(self.config_path, default_value={"prompt_templates": {"zero_shot": {}}})
        except (FileNotFoundError, OSError, ValueError):
            return {"prompt_templates": {"zero_shot": {}}}
    
    def _format_template(self, template: Dict[str, str], **kwargs) -> Dict[str, str]:
        formatted = template.copy()
        if "content" in formatted:
            formatted["content"] = formatted["content"].format(**kwargs)
        return formatted
    
    def _prepare_context_data(self, method_info: Dict[str, Any]) -> Dict[str, str]:
        constructors = method_info.get("constructor_codes", [])
        constructors_str = "\n".join(constructors) if constructors else ""
        
        return {
            "constructors": constructors_str,
            "method_code": method_info.get("method_code", ""),
            "left_changes_summary": method_info.get("left_changes_summary", ""),
            "right_changes_summary": method_info.get("right_changes_summary", "")
        }
    
    def generate_messages_for_template(self, template_name: str, method_info: Dict[str, Any], 
                                     class_name: str, branch: str, context_keys: List[str] = None) -> List[Dict[str, str]]:
        template_config = self.config.get("prompt_templates", {}).get(template_name, {})
        
        context_data = self._prepare_context_data(method_info)
        context_data.update({"class_name": class_name, "branch": branch, "method_name": method_info.get("method_name", "")})
        
        messages = []
        
        if "system_message" in template_config:
            messages.append(self._format_template(template_config["system_message"], **context_data))
        
        if "user_init_message" in template_config:
            messages.append(self._format_template(template_config["user_init_message"], **context_data))
        
        if context_keys:
            context_templates = template_config.get("context_templates", {})
            for key in context_keys:
                if key in context_templates:
                    messages.append(self._format_template(context_templates[key], **context_data))
        
        if "method_context_message" in template_config:
            messages.append(self._format_template(template_config["method_context_message"], **context_data))
        
        return messages
    
    def generate_all_combinations(self, method_info: Dict[str, Any], class_name: str, 
                                branch: str, template_name: str = "zero_shot") -> Dict[str, List[Dict[str, str]]]:
        """Generates only 2 combinations: simplest and most complete"""
        combinations = [
            [],                                                      # prompt1: mais simples (sem contexto)
            ["changes_summary", "constructors"]                      # prompt2: mais completo (com construtor e mudanças)
        ]
        
        messages_dict = {}
        for i, context_keys in enumerate(combinations, 1):
            messages_dict[f"prompt{i}"] = self.generate_messages_for_template(
                template_name, method_info, class_name, branch, context_keys
            )
        
        return messages_dict
    
    def save_generated_messages(self, messages_dict: Dict[str, List[Dict[str, str]]], 
                              output_path: str, class_name: str, method_name: str) -> None:
        output_file_path = os.path.join(output_path, "generated_messages.json")
        
        try:
            if os.path.exists(output_file_path):
                existing_data = load_json(output_file_path)
            else:
                existing_data = {}
        except (FileNotFoundError, OSError, ValueError):
            existing_data = {}
        
        if class_name not in existing_data:
            existing_data[class_name] = {}
        
        existing_data[class_name][method_name] = messages_dict
        
        os.makedirs(output_path, exist_ok=True)
        save_json(output_file_path, existing_data, ensure_ascii=False)
