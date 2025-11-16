import os
import json


def get_python_files(path):
    """Get all Python files in a directory."""
    return get_files(path, ext='.py')


def get_files(path, root='', ext=None):
    """Get all files with specified extension in a directory."""
    files = []

    for node in os.listdir(path):
        node_path = os.path.join(path, node)
        if os.path.isdir(node_path):
            files += get_files(node_path, os.path.join(root, node), ext)
        elif ext is None or os.path.splitext(node_path)[1] == ext:
            files.append(os.path.join(root, node))

    return files


def generate_python_path(paths):
    """Generate Python path from list of paths."""
    return os.pathsep.join([p for p in paths if p is not None and len(p) > 0])


def package_to_dir(package):
    return package.replace('.', os.sep)


def dir_to_package(directory):
    return directory.replace(os.sep, '.')


def load_json(file_path):
    """Loads a JSON file and return its content as a dictionary"""
    with open(file_path, "r") as file:
        try:
            content = json.load(file)
        except json.JSONDecodeError:
            content = {}
    return content


def save_json(file_path, content):
    """Saves a dictionary as a JSON file"""
    with open(file_path, "w") as file:
        json.dump(content, file, indent=4)
