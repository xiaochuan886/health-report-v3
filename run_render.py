#!/usr/bin/env python3
import sys
import time
sys.path.insert(0, 'src')
start = time.time()
print('Starting render...')
from report_pipeline.cli import main
result = main(['render', '--input-dir', 'output/customer-run', '--markdown-output', 'output/customer-run/report.md', '--pdf-output', 'output/customer-run/report.pdf'])
print(f'Render done in {time.time()-start:.1f}s, result={result}')
