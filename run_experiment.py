#!/usr/bin/env python3

import subprocess
import sys
import os
import logging
from pathlib import Path


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )


def run_smat():
    try:
        smat_dir = Path(__file__).parent / "SMAT"
        os.environ['PYTHONPATH'] = str(smat_dir)

        result = subprocess.run(
            [sys.executable, "-m", "nimrod"],
            cwd=smat_dir,
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            return True
        else:
            logging.error(f"SMAT failed with code: {result.returncode}")
            return False
            
    except KeyboardInterrupt:
        logging.info("Execution interrupted by user")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False


def main():
    setup_logging()
    
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("Usage: python3 run_experiment.py")
        return 0
    
    success = run_smat()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
