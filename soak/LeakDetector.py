"""
LeakDetector — 长期运行泄漏检测
===============================
关注: RSS Memory / SQLite 大小 / Pending Queue 长度 / Order Count 增速。
不检测 Python 对象数量 (CPython GC 会误报)。
"""

from soak.RuntimeMetrics import RuntimeMetrics


class LeakDetector:
    def __init__(self, metrics: RuntimeMetrics,
                 max_mem_growth_pct: float = 20.0,
                 max_sqlite_growth_mb: float = 100.0,
                 max_pending_sustained: int = 5):
        self._metrics = metrics
        self._max_mem_growth = max_mem_growth_pct
        self._max_sqlite_growth = max_sqlite_growth_mb
        self._max_pending = max_pending_sustained

        # 基线
        self._baseline: dict = {}

    def init(self):
        self._metrics.baseline()
        self._baseline = self._metrics.snapshot()

    def check(self) -> list[str]:
        """返回异常报告列表。无异常返回空列表。"""
        now = self._metrics.snapshot()
        issues = []

        # 内存增长
        mem_delta = now["mem_mb"] - self._baseline["mem_mb"]
        if self._baseline["mem_mb"] > 0:
            mem_pct = mem_delta / self._baseline["mem_mb"] * 100
            if mem_pct > self._max_mem_growth:
                issues.append(f"内存增长 {mem_pct:.1f}% ({mem_delta:.0f}MB)")

        # SQLite 增长
        sqlite_delta = now["sqlite_mb"] - self._baseline["sqlite_mb"]
        if sqlite_delta > self._max_sqlite_growth:
            issues.append(f"SQLite 增长 {sqlite_delta:.1f}MB")

        # Pending 积压
        if now["pending_count"] > self._max_pending:
            issues.append(f"Pending 积压 {now['pending_count']} 笔")

        # Order count 增速异常
        orders_per_hour = (now["order_count"] - self._baseline["order_count"])
        hours = max(now["uptime_sec"] / 3600, 0.01)
        if orders_per_hour / hours > 10000:
            issues.append(f"订单增速异常: {orders_per_hour/hours:.0f}/h")

        return issues
