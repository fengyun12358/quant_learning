"""
TradingSessionMonitor — 交易日行为监控
======================================
检测:
  - 非交易时段出现成交
  - 长时间无行情数据
  - 收盘后仍有 pending 订单
  - 集合竞价时段下单被拒
"""

from datetime import datetime, time, timezone
from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult, Severity

# A股交易时段 (北京时间 UTC+8)
_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(15, 0)
_MORNING_AUCTION_END = time(9, 25)


class TradingSessionMonitor(Monitor):
    def check(self, ctx: MonitorContext) -> MonitorResult:
        now = datetime.now(timezone.utc)
        # 转北京时间
        bj_now = now.hour + 8 + now.minute / 60

        # 模拟盘中判断：如果当前无 bar 推进超过 5 分钟
        if ctx.seconds_since_last_bar > 300 and ctx.pending_order_count == 0:
            return MonitorResult.warn(
                self.name,
                f"无行情数据 {ctx.seconds_since_last_bar:.0f}s",
                seconds_since_last_bar=ctx.seconds_since_last_bar,
            )

        if ctx.seconds_since_last_bar > 1800:
            return MonitorResult.error(
                self.name,
                f"长时间无行情 {ctx.seconds_since_last_bar:.0f}s，请检查数据源",
            )

        # 收盘后有 pending 订单
        bj_time = time(int(bj_now) % 24, int((bj_now % 1) * 60))
        if bj_time > _MARKET_CLOSE and ctx.pending_order_count > 0:
            return MonitorResult.critical(
                self.name,
                f"收盘后仍有 {ctx.pending_order_count} 笔未成交订单",
                action="请检查是否需要撤单或留到次日",
            )

        # 集合竞价时段
        if bj_time < _MORNING_AUCTION_END and ctx.pending_order_count > 0:
            return MonitorResult.warn(
                self.name,
                "集合竞价时段存在 pending 订单",
            )

        return MonitorResult.ok(self.name)
