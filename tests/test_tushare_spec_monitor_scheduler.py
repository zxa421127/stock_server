from datetime import datetime
from zoneinfo import ZoneInfo

from services.tushare_spec_monitor_service import next_monitor_run


def test_next_run_from_monday_is_wednesday_0230_shanghai():
    now = datetime(2026, 7, 27, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = next_monitor_run(now)
    assert result.isoformat() == "2026-07-29T02:30:00+08:00"


def test_next_run_after_wednesday_slot_is_sunday():
    now = datetime(2026, 7, 29, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = next_monitor_run(now)
    assert result.isoformat() == "2026-08-02T02:30:00+08:00"


def test_next_run_before_sunday_slot_is_same_sunday():
    now = datetime(2026, 8, 2, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = next_monitor_run(now)
    assert result.isoformat() == "2026-08-02T02:30:00+08:00"
