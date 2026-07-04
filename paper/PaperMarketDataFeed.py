"""
PaperMarketDataFeed — 从历史 CSV 推送 K 线
=========================================
模拟行情到达。每次 next_bar() 返回一根 K 线。
"""

import pandas as pd
from typing import Optional
from data.DataLoader import DataLoader


class PaperMarketDataFeed:
    def __init__(self, csv_path: str):
        self._df = DataLoader(csv_path).load()
        if "日期" in self._df.columns:
            self._df["日期"] = pd.to_datetime(self._df["日期"])
        self._index = 0

    def next_bar(self) -> Optional[dict]:
        """返回下一根K线，数据耗尽返回None。"""
        if self._index >= len(self._df):
            return None
        row = self._df.iloc[self._index]
        self._index += 1
        return {
            "date": str(row.get("日期", self._index)),
            "open": float(row["开盘"]),
            "high": float(row["最高"]),
            "low": float(row["最低"]),
            "close": float(row["收盘"]),
            "volume": float(row["成交量"]),
        }

    def reset(self):
        self._index = 0

    @property
    def total_bars(self):
        return len(self._df)

    @property
    def progress(self):
        return self._index
