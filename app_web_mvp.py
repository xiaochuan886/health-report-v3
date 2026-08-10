import sys

from report_pipeline.macos_statusbar import run_statusbar_app
from report_pipeline.web_mvp import main


if __name__ == "__main__":
    if run_statusbar_app(sys.argv[1:]):
        raise SystemExit(0)
    raise SystemExit(main(["--open-browser", *sys.argv[1:]]))
