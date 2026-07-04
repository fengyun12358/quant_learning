"""
RuntimeMetrics — 运行时指标采集
===============================
CPU / Memory / SQLite Size / Pending Orders / Broker Status / Reconcile Diff.
"""

import os
import time


class RuntimeMetrics:
    def __init__(self, db_path: str = "data/trading.db",
                 broker=None, order_manager=None):
        self._db_path = db_path
        self._broker = broker
        self._om = order_manager
        self._start_time = time.time()
        self._baseline: dict | None = None

    def snapshot(self) -> dict:
        """返回当前所有运行时指标。"""
        mem_mb = 0.0
        try:
            import psutil
            mem_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        except ImportError:
            pass

        sqlite_mb = 0.0
        if os.path.exists(self._db_path):
            sqlite_mb = os.path.getsize(self._db_path) / 1024 / 1024

        broker_ok = True
        reconcile_diff = 0
        pending_count = 0
        pending_max_age = 0.0
        order_count = 0

        if self._broker:
            broker_ok = getattr(self._broker, 'is_connected',
                                lambda: True)()
            pending_count = getattr(self._broker, 'pending_count',
                                    lambda: 0)()

        if self._om:
            order_count = len(getattr(self._om, '_orders', {}))
            pending_count = max(pending_count,
                                getattr(self._om, 'pending_count', lambda: 0)())

        return {
            "timestamp": time.time(),
            "uptime_sec": time.time() - self._start_time,
            "cpu_pct": 0.0,  # psutil.cpu_percent() if installed
            "mem_mb": round(mem_mb, 1),
            "sqlite_mb": round(sqlite_mb, 2),
            "broker_connected": broker_ok,
            "reconcile_diff_count": reconcile_diff,
            "pending_count": pending_count,
            "pending_max_age_sec": round(pending_max_age, 1),
            "order_count": order_count,
        }

    def baseline(self):
        self._baseline = self.snapshot()

    def delta(self) -> dict:
        if not self._baseline:
            return {}
        now = self.snapshot()
        return {
            k: round(now[k] - self._baseline.get(k, 0), 3)
            for k in ("mem_mb", "sqlite_mb", "pending_count", "order_count")
        }

    def to_csv_header(self) -> str:
        return "timestamp,uptime_sec,mem_mb,sqlite_mb,broker_ok," \
               "reconcile_diff,pending,order_count"

    def to_csv_row(self) -> str:
        s = self.snapshot()
        return (f"{s['timestamp']:.0f},{s['uptime_sec']:.0f},"
                f"{s['mem_mb']},{s['sqlite_mb']},{int(s['broker_connected'])},"
                f"{s['reconcile_diff_count']},{s['pending_count']},"
                f"{s['order_count']}")
