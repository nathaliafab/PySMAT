import os
import json


def generate_python_path(paths):
    """Generate Python path from list of paths."""
    return os.pathsep.join([p for p in paths if p is not None and len(p) > 0])


def load_json(file_path, encoding="utf-8", default_value=None):
    """Loads a JSON file and return its content as a dictionary"""
    if default_value is None:
        default_value = {}
    
    with open(file_path, "r", encoding=encoding) as file:
        try:
            content = json.load(file)
        except json.JSONDecodeError:
            content = default_value
    return content


def save_json(file_path, content, encoding="utf-8", ensure_ascii=True, indent=4):
    """Saves a dictionary as a JSON file"""
    with open(file_path, "w", encoding=encoding) as file:
        json.dump(content, file, indent=indent, ensure_ascii=ensure_ascii)
