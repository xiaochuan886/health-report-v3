from types import SimpleNamespace

from report_pipeline.macos_statusbar import _discover_peer_pids, _extract_target_pids


def test_extract_target_pids_matches_app_signatures():
    """只匹配 .app bundle 路径和已知入口脚本名，不匹配同名无关进程。"""
    ps_output = """
    101 /Applications/HealthReportWeb.app/Contents/MacOS/HealthReportWeb --host 127.0.0.1
    202 /Applications/OtherApp.app/Contents/MacOS/OtherApp
    303 /tmp/HealthReportWeb --port 8766
    404 /usr/local/bin/python app_web_mvp.py --port 8766
    """
    sigs = (
        "HealthReportWeb.app/Contents/MacOS/HealthReportWeb",
        "app_web_mvp.py",
    )
    pids = _extract_target_pids(ps_output, app_signatures=sigs, current_pid=999)
    # 101（bundle）、404（入口脚本）匹配；202（无关 app）、303（同名无关二进制）不匹配
    assert pids == [101, 404]


def test_extract_target_pids_ignores_current_pid():
    ps_output = """
    808 /Applications/HealthReportWeb.app/Contents/MacOS/HealthReportWeb
    """
    sigs = ("HealthReportWeb.app/Contents/MacOS/HealthReportWeb",)
    pids = _extract_target_pids(ps_output, app_signatures=sigs, current_pid=808)
    assert pids == []


def test_extract_target_pids_does_not_match_generic_python():
    """关键回归：不得基于泛化的解释器名误杀其它 python 进程。"""
    ps_output = """
    501 /usr/local/bin/python /Users/someone/work/script.py
    502 /opt/homebrew/bin/python3 -m pytest
    """
    sigs = (
        "HealthReportWeb.app/Contents/MacOS/HealthReportWeb",
        "app_web_mvp.py",
    )
    pids = _extract_target_pids(ps_output, app_signatures=sigs, current_pid=999)
    assert pids == []


def test_discover_peer_pids_returns_empty_when_ps_failed(monkeypatch):
    monkeypatch.setattr(
        "report_pipeline.macos_statusbar.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    assert _discover_peer_pids(("HealthReportWeb.app/Contents/MacOS/HealthReportWeb",), 12345) == []
