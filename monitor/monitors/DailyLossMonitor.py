"""
DailyLossMonitor — 日内累计亏损检测
"""
from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult


class DailyLossMonitor(Monitor):
    def check(self, ctx: MonitorContext) -> MonitorResult:
        pnl = ctx.daily_pnl

        if pnl >= 0:
            return MonitorResult.ok(self.name)
        elif pnl > -0.03:
            return MonitorResult.warn(
                self.name, f"日内亏损 {pnl:.2%}", daily_pnl=pnl,
            )
        elif pnl > -0.05:
            return MonitorResult.error(
                self.name, f"日内亏损 {pnl:.2%}", daily_pnl=pnl,
            )
        else:
            return MonitorResult.critical(
                self.name, f"日内亏损 {pnl:.2%}，触发熔断阈值",
                action="暂停当日交易，检查持仓和策略",
                daily_pnl=pnl,
            )
