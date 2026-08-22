from unittest.mock import Mock, patch

from tools import sync_tushare_interface_specs


def test_legacy_sync_cli_now_only_scans_and_creates_alerts(capsys):
    service = Mock()
    service.scan.return_value = {
        "complete_scan": False,
        "failure_count": 1,
        "changed_count": 2,
    }
    with patch.object(sync_tushare_interface_specs, "get_tushare_spec_monitor_service", return_value=service), \
         patch.object(sync_tushare_interface_specs, "init_db"), \
         patch("sys.argv", ["sync_tushare_interface_specs", "--api", "ci_daily"]):
        exit_code = sync_tushare_interface_specs.main()

    service.scan.assert_called_once_with(["ci_daily"], trigger="legacy_cli")
    assert exit_code == 2
    assert '"complete_scan": false' in capsys.readouterr().out
