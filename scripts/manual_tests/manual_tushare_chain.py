# -*- coding: utf-8 -*-
"""Manual online test. Requires a real .env token and network access."""
from datetime import datetime, timedelta

from integrations.market_data.tushare.client import TushareClient, call_tushare_api


def main() -> None:
    end_day = datetime.now().date()
    start_day = end_day - timedelta(days=7)
    df, error = call_tushare_api(
        "trade_cal",
        exchange="SSE",
        start_date=start_day.strftime("%Y%m%d"),
        end_date=end_day.strftime("%Y%m%d"),
        fields="exchange,cal_date,is_open,pretrade_date",
    )
    if error:
        raise SystemExit(f"调用失败：{error}")
    print(f"mode={TushareClient.mode()} rows={len(df)}")
    print(df.head())


if __name__ == "__main__":
    main()
