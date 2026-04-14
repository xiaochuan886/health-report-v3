#!/usr/bin/env .venv/bin/python
import sys
import time
from pathlib import Path

# Add src to path to find report_pipeline package
repo_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(repo_root / "src"))

start = time.time()
print('Starting render using local venv...')
from report_pipeline.cli import main
result = main(['render', '--input-dir', 'output/customer-run', '--markdown-output', 'output/customer-run/report.md', '--pdf-output', 'output/customer-run/report.pdf'])
print(f'Render done in {time.time()-start:.1f}s, result={result}')
