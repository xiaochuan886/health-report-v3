import sys
import traceback

from report_pipeline.macos_statusbar import run_statusbar_app
from report_pipeline.web_mvp import main


def _pause_on_error(message: str) -> None:
    """异常时打印错误并等待用户按键，避免控制台窗口闪退。"""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[错误] {message}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    traceback.print_exc()
    print("\n按回车键退出...", file=sys.stderr)
    try:
        input()
    except (EOFError, OSError):
        pass


if __name__ == "__main__":
    try:
        if run_statusbar_app(sys.argv[1:]):
            raise SystemExit(0)
        raise SystemExit(main(["--open-browser", *sys.argv[1:]]))
    except SystemExit:
        raise
    except Exception as exc:
        _pause_on_error(str(exc))
        raise SystemExit(1)
