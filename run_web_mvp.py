#!/usr/bin/env .venv/bin/python
import sys
from pathlib import Path

repo_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(repo_root / "src"))

from report_pipeline.web_mvp import main

if __name__ == "__main__":
    raise SystemExit(main())
