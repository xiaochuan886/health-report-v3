import sys, os, re
sys.path.insert(0, '/Users/re.stem/综合健康检测报告v3.0/src')
from report_pipeline.md2pdf import PDFBuilder

# Mock configuration for PDFBuilder
class MockConfig:
    def get(self, key, default=None):
        return default

builder = PDFBuilder()
builder.cfg = MockConfig()
builder.accent_hex = "#CC785C"
builder.ST = {'body': None, 'tc': None, 'th': None, 'code': None, 'part': None, 'chapter': None, 'h3': None, 'bullet': None, 'toc1': None, 'toc2': None}
builder.L = {"heading_decoration": "none"}
builder.body_w = 450
builder.body_h = 750
builder.T = {"accent": "red", "border": "gray", "canvas_sec": "lightgray", "ink": "black", "ink_faded": "gray"}

def mock_table(lines): return "TABLE"
builder.parse_table = mock_table # Bypass table building

# Test case: a very long table line with many Chinese characters
chinese_text = "心脑血管疾病是指心脏和血管系统的疾病，包括冠心病、心肌梗死、脑卒中（中风）、高血压等。" * 20
line = f"| Item | {chinese_text} |"
content = line + "\n" + line

import time
start = time.time()
builder.parse_md(content)
print(f"Time for parse_md: {time.time() - start:.4f}s")
