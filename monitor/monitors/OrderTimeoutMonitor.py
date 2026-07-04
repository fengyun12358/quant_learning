"""
OrderTimeoutMonitor — 未成交订单超时检测
"""
from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult


class OrderTimeoutMonitor(Monitor):
    def check(self, ctx: MonitorContext) -> MonitorResult:
        if ctx.pending_order_count == 0:
            return MonitorResult.ok(self.name)

        secs = ctx.oldest_pending_seconds

        if secs < 5:
            return MonitorResult.warn(
                self.name,
                f"{ctx.pending_order_count} 笔订单未成交，最旧 {secs:.0f}s",
            )
        elif secs < 30:
            return MonitorResult.error(
                self.name,
                f"{ctx.pending_order_count} 笔订单未成交，最旧 {secs:.0f}s",
            )
        else:
            return MonitorResult.critical(
                self.name,
                f"{ctx.pending_order_count} 笔订单未成交，最旧 {secs:.0f}s",
                action="检查券商连接状态，考虑撤单重发",
            )
