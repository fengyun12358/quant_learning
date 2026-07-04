"""
DailyResetValidator — 每日重置验证
==================================
验证每日 PnL / ConsecutiveLosses / Monitor State / SQLite risk_state 是否正确归零。
"""

from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DailyResetValidator:
    def __init__(self, persistence=None):
        self._persistence = persistence
        self._end_of_day: dict = {}
        self._results: list[dict] = []

    def record_end_of_day(self, daily_pnl: float, consecutive_losses: int,
                          monitor_alerts: dict):
        """记录当日收市状态。"""
        self._end_of_day = {
            "date": _utc_now()[:10],
            "daily_pnl": daily_pnl,
            "consecutive_losses": consecutive_losses,
            "monitor_alerts": monitor_alerts,
        }

    def validate_morning_reset(self, daily_pnl: float,
                               consecutive_losses: int,
                               monitor_state_ok: bool = True) -> bool:
        """
        验证次日开盘状态是否正确重置。
        返回 True = 重置成功。
        """
        errors = []

        if daily_pnl != 0.0:
            errors.append(f"DailyPnL 未归零: {daily_pnl}")
        if consecutive_losses != 0:
            errors.append(f"ConsecutiveLoss 未归零: {consecutive_losses}")
        if not monitor_state_ok:
            errors.append("Monitor 状态异常")

        # 检查 SQLite risk_state
        if self._persistence:
            try:
                rs = self._persistence.load_risk_state(scope="GLOBAL")
                daily_pnl_db = float(rs.get("daily_pnl", "0"))
                if abs(daily_pnl_db) > 0.0001:
                    errors.append(f"SQLite daily_pnl 未归零: {daily_pnl_db}")
            except Exception as e:
                errors.append(f"SQLite 读取失败: {e}")

        passed = len(errors) == 0
        self._results.append({
            "date": _utc_now()[:10],
            "passed": passed,
            "errors": errors,
        })
        return passed

    def summary(self) -> dict:
        total = len(self._results)
        passed = sum(1 for r in self._results if r["passed"])
        return {
            "total_days": total,
            "passed": passed,
            "failed": total - passed,
            "details": self._results[-3:] if self._results else [],
        }
