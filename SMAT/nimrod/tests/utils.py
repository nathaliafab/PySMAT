import logging
import logging.handlers
import os
from json import JSONDecodeError
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from nimrod.utils import load_json

PATH = os.path.dirname(os.path.abspath(__file__))


def get_config() -> Dict[str, Any]:
    config_path = os.path.join(PATH, "env-config.json")
    return load_json(config_path)


def setup_logging():
    try:
        config = get_config()
        config_level = config.get('logger_level', 'INFO').upper()
    except (FileNotFoundError, JSONDecodeError, KeyError):
        config_level = 'INFO'
    
    level = getattr(logging, config_level, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s [%(name)s:%(lineno)d] %(funcName)s() - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s - %(message)s',
        datefmt='%H:%M:%S'
    )

    try:
        main_log_file = log_dir / "smat_nimrod.log"
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(detailed_formatter)
        logger.addHandler(main_handler)
    except (OSError, PermissionError):
        fallback_log = log_dir / f"smat_nimrod_{datetime.now().strftime('%Y%m%d')}.log"
        fallback_handler = logging.FileHandler(fallback_log, mode='a', encoding='utf-8')
        fallback_handler.setLevel(logging.DEBUG)
        fallback_handler.setFormatter(detailed_formatter)
        logger.addHandler(fallback_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    logger.info("SMAT Logging initialized - Level: %s", config_level)

def get_base_output_path() -> str:
    current_dir = os.getcwd()
    base_dir = current_dir.replace("/nimrod/proj", "") if "/nimrod/proj" in current_dir else current_dir
    return os.path.join(base_dir, "output-test-dest", "projects")
