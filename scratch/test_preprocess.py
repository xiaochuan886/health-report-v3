import sys, os, re
sys.path.insert(0, '/Users/re.stem/综合健康检测报告v3.0/src')
from report_pipeline.md2pdf import PDFBuilder

# A very long table row inspired by line 148
line = "| 心脑血管 | TG(above)；TC(above) | " + "A" * 1000 + " | " + "B" * 1000 + " |"
content = line + "\n" + line

start = os.times().elapsed
PDFBuilder._preprocess_md(content)
print(f"Time for _preprocess_md: {os.times().elapsed - start:.4f}s")
