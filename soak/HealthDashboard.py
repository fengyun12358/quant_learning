"""
HealthDashboard — 健康仪表盘
============================
每 N bar 打印一行可读状态。同时支持 CSV 落盘。
"""

from datetime import datetime


class HealthDashboard:
    def __init__(self, report_interval_bars: int = 100,
                 csv_path: str = ""):
        self._interval = report_interval_bars
        self._csv_path = csv_path
        self._csv_file = None
        self._alert_w = 0
        self._alert_e = 0
        self._alert_c = 0

    def open_csv(self):
        if self._csv_path:
            self._csv_file = open(self._csv_path, "w")
            self._csv_file.write(
                "time,bar,cpu,mem_mb,sqlite_mb,broker_ok,"
                "pending,reconcile_diff,alerts_W,alerts_E,alerts_C\n"
            )

    def close_csv(self):
        if self._csv_file:
            self._csv_file.close()

    def accumulate_alerts(self, results: list):
        """统计 Monitor 结果（调用方传入 check_all() 的返回值）。"""
        for r in results:
            sev = str(r.severity.value)
            if sev == "warning":
                self._alert_w += 1
            elif sev == "error":
                self._alert_e += 1
            elif sev == "critical":
                self._alert_c += 1

    def print_header(self):
        print(f"{'Time':>10s} {'Bar':>6s} {'CPU':>4s} {'Mem':>6s} "
              f"{'SQLite':>7s} {'Broker':>6s} {'Pend':>4s} {'RecDiff':>6s} "
              f"{'W':>3s} {'E':>3s} {'C':>3s}")

    def print_row(self, bar_index: int, metrics: dict, force: bool = False):
        """metrics: RuntimeMetrics.snapshot() 的返回值。"""
        if not force and bar_index % self._interval != 0:
            return

        s = metrics
        now = datetime.now().strftime("%H:%M:%S")
        line = (f"{now:>10s} {bar_index:>6d} "
                f"{s['cpu_pct']:>4.0f}% {s['mem_mb']:>5.0f}MB "
                f"{s['sqlite_mb']:>6.1f}MB "
                f"{'OK' if s['broker_connected'] else 'DOWN':>6s} "
                f"{s['pending_count']:>4d} {s['reconcile_diff_count']:>6d} "
                f"{self._alert_w:>3d} {self._alert_e:>3d} {self._alert_c:>3d}")
        print(line)

        if self._csv_file:
            self._csv_file.write(
                f"{now},{bar_index},{s['cpu_pct']:.0f},{s['mem_mb']:.0f},"
                f"{s['sqlite_mb']:.1f},{int(s['broker_connected'])},"
                f"{s['pending_count']},{s['reconcile_diff_count']},"
                f"{self._alert_w},{self._alert_e},{self._alert_c}\n"
            )

    @property
    def totals(self) -> dict:
        return {"W": self._alert_w, "E": self._alert_e, "C": self._alert_c}
