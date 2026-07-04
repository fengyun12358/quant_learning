"""
PaperPortfolio — 模拟账户净值追踪
=================================
每次 bar 调用 update()，记录现金、市值、总资产、回撤。
"""

from datetime import datetime, timezone


class PaperPortfolio:
    def __init__(self, initial_cash: float = 100000.0):
        self.initial_cash = initial_cash
        self._records: list[dict] = []
        self._peak = initial_cash

    def update(self, timestamp, cash: float, positions_value: float):
        total = cash + positions_value
        self._peak = max(self._peak, total)
        drawdown = (total - self._peak) / self._peak if self._peak > 0 else 0.0

        daily_return = 0.0
        if self._records:
            prev_total = self._records[-1]["total_asset"]
            if prev_total > 0:
                daily_return = (total - prev_total) / prev_total

        self._records.append({
            "timestamp": timestamp,
            "cash": cash,
            "market_value": positions_value,
            "total_asset": total,
            "drawdown": drawdown,
            "daily_return": daily_return,
        })

    def latest(self) -> dict:
        return self._records[-1] if self._records else {}

    def equity_curve(self) -> list[float]:
        return [r["total_asset"] for r in self._records]

    def max_drawdown(self) -> float:
        if not self._records:
            return 0.0
        return min(r["drawdown"] for r in self._records)

    def total_return(self) -> float:
        if not self._records:
            return 0.0
        final = self._records[-1]["total_asset"]
        return (final - self.initial_cash) / self.initial_cash

    def snapshot(self) -> dict:
        """返回当前权益快照，可直接喂给 MonitorContext。"""
        r = self.latest()
        return {
            "total_asset": r.get("total_asset", self.initial_cash),
            "cash": r.get("cash", self.initial_cash),
            "drawdown": r.get("drawdown", 0.0),
            "daily_return": r.get("daily_return", 0.0),
        }
