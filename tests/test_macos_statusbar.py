from types import SimpleNamespace

from report_pipeline.macos_statusbar import _discover_peer_pids, _extract_target_pids


def test_extract_target_pids_matches_health_report_commands():
    ps_output = """
    101 /Applications/HealthReportWeb.app/Contents/MacOS/HealthReportWeb --host 127.0.0.1
    202 /Applications/OtherApp.app/Contents/MacOS/OtherApp
    303 /tmp/HealthReportWeb --port 8766
    """
    pids = _extract_target_pids(ps_output, executable_name="HealthReportWeb", current_pid=999)
    assert pids == [101, 303]


def test_extract_target_pids_ignores_current_pid():
    ps_output = """
    808 /Applications/HealthReportWeb.app/Contents/MacOS/HealthReportWeb
    """
    pids = _extract_target_pids(ps_output, executable_name="HealthReportWeb", current_pid=808)
    assert pids == []


def test_discover_peer_pids_returns_empty_when_ps_failed(monkeypatch):
    monkeypatch.setattr(
        "report_pipeline.macos_statusbar.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    assert _discover_peer_pids("HealthReportWeb", 12345) == []
