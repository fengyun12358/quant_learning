"""
MonitorCenter — 监控协调器
==========================
遍历所有 Monitor，汇总结果。
新增 Monitor = monitor_center.add(NewMonitor()) — 不修改本类。
"""

from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult, Severity


class MonitorCenter:
    """监控中心——只读，不修改系统状态。"""

    def __init__(self):
        self._monitors: list[Monitor] = []

    def add(self, monitor: Monitor):
        """注册一个监控器。"""
        self._monitors.append(monitor)

    def check_all(self, context: MonitorContext,
                  include_ok: bool = False) -> list[MonitorResult]:
        """
        遍历所有 Monitor。
        include_ok=False → 只返回 WARNING/ERROR/CRITICAL（精简模式）。
        include_ok=True  → 返回全部结果。
        """
        results = []
        for m in self._monitors:
            result = m.check(context)
            if include_ok or result.severity != Severity.INFO:
                results.append(result)
        return results

    @property
    def monitor_names(self) -> list[str]:
        return [m.name for m in self._monitors]
