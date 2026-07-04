"""
Monitor — 监控器基类
====================
所有 Monitor 子类实现 check(context) → MonitorResult。
不持有状态，不修改 context。
"""

from abc import ABC, abstractmethod

from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult


class Monitor(ABC):
    """监控器基类。子类只需实现 check()。"""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def check(self, context: MonitorContext) -> MonitorResult:
        ...
