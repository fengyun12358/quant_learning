"""
ConsecutiveLossMonitor — 连续亏损检测
"""
from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult


class ConsecutiveLossMonitor(Monitor):
    def check(self, ctx: MonitorContext) -> MonitorResult:
        n = ctx.consecutive_losses

        if n == 0:
            return MonitorResult.ok(self.name)
        elif n >= 5:
            return MonitorResult.critical(
                self.name, f"连续亏损 {n} 笔，建议暂停交易排查策略",
                action="暂停自动交易，检查策略逻辑是否适应当前行情",
                consecutive_losses=n,
            )
        elif n >= 3:
            return MonitorResult.error(
                self.name, f"连续亏损 {n} 笔", consecutive_losses=n,
            )
        else:
            return MonitorResult.warn(
                self.name, f"连续亏损 {n} 笔", consecutive_losses=n,
            )
