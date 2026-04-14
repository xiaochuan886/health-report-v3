import sys, os
sys.path.insert(0, '/Users/re.stem/综合健康检测报告v3.0/src')
from report_pipeline.md2pdf import _font_wrap, _is_cjk
import time

text = "心脑血管疾病是指心脏和血管系统的疾病，包括冠心病、心肌梗死、脑卒中（中风）、高血压等。" * 100
start = time.time()
wrapped = _font_wrap(text)
print(f"Time to wrap {len(text)} chars: {time.time()-start:.4f}s")
print(f"Result length: {len(wrapped)}")
