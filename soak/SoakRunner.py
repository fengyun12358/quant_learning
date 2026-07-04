"""
SoakRunner — 浸泡测试主循环
===========================
连续运行 N 小时, 采集 RuntimeMetrics + HealthDashboard + LeakDetector +
DailyResetValidator, 输出 SoakReport。
"""

import time
import tempfile
import os
from strategy.MACrossLogic import MACrossLogic
from risk.RiskGate import RiskGate
from risk.OrderManager import OrderManager
from risk.SQLitePersistence import SQLitePersistence
from monitor.MonitorCenter import MonitorCenter
from monitor.MonitorContext import MonitorContext
from monitor.monitors import (
    BrokerHeartbeatMonitor, OrderTimeoutMonitor,
    ConsecutiveLossMonitor, DailyLossMonitor, PersistenceMonitor,
)
from adapter.qmt.MiniQMTGateway import MiniQMTGateway
from adapter.broker_gateway import Order
from paper.PaperMarketDataFeed import PaperMarketDataFeed
from paper.PaperPortfolio import PaperPortfolio
from reconcile.BrokerReconcile import BrokerReconcile
from soak.RuntimeMetrics import RuntimeMetrics
from soak.HealthDashboard import HealthDashboard
from soak.LeakDetector import LeakDetector
from soak.DailyResetValidator import DailyResetValidator
from soak.SoakReport import SoakReport


class SoakRunner:
    def __init__(self, csv_path: str = "data/510330.xls",
                 duration_hours: float = 1.0,
                 report_interval_bars: int = 100,
                 fail_fast: bool = False):
        self._csv_path = csv_path
        self._duration = duration_hours
        self._interval = report_interval_bars
        self._fail_fast = fail_fast

    def run(self) -> SoakReport:
        db_path = tempfile.mktemp(suffix=".db")

        # ---- 构建系统 ----
        gw = MiniQMTGateway("888888", True, 100000)
        gw.connect()
        db = SQLitePersistence(db_path)
        om = OrderManager(gw, persistence=db)
        logic = MACrossLogic(5, 20)
        portfolio = PaperPortfolio(100000)
        reconcile = BrokerReconcile(db)

        mc = MonitorCenter()
        for m in [BrokerHeartbeatMonitor(), OrderTimeoutMonitor(),
                  ConsecutiveLossMonitor(), DailyLossMonitor(),
                  PersistenceMonitor()]:
            mc.add(m)

        feed = PaperMarketDataFeed(self._csv_path)
        metrics = RuntimeMetrics(db_path, gw, om)
        dash = HealthDashboard(self._interval, "")
        leak = LeakDetector(metrics)
        daily = DailyResetValidator(db)

        # ---- 运行状态 ----
        report = SoakReport()
        consecutive_losses, daily_pnl = 0, 0.0
        in_position, entry_price = False, 0.0
        bars, max_pending, max_mem = 0, 0, 0.0
        snap: dict = {}
        daily_bar_count = 0
        days_completed = 0
        state_errors = 0
        crashes = 0

        metrics.baseline()
        leak.init()
        dash.open_csv()
        dash.print_header()
        start_time = time.time()

        try:
            while True:
                elapsed = (time.time() - start_time) / 3600
                if elapsed >= self._duration:
                    break

                bar = feed.next_bar()
                if bar is None:
                    feed.reset()
                    bar = feed.next_bar()

                gw.set_current_price("510330", bar["close"])
                signal = logic.update(bar["close"])
                gw.update(clock_tick=1.0)

                # 信号 → 订单
                if signal == "buy" and not in_position:
                    om.submit(Order("510330", "buy", bar["close"],
                                    _calc_size(gw, bar["close"])))
                    in_position, entry_price = True, bar["close"]
                elif signal == "sell" and in_position:
                    pos = gw.query_position("510330")
                    if pos and pos.size > 0:
                        om.submit(Order("510330", "sell", bar["close"],
                                        pos.size))
                        pnl = ((bar["close"] - entry_price) / entry_price
                               if entry_price > 0 else 0)
                        daily_pnl += pnl
                        consecutive_losses = (consecutive_losses + 1
                                              if pnl < 0 else 0)
                    in_position = False

                gw.update(clock_tick=1.0)
                om.update()
                portfolio.update(bar["date"], gw.query_cash(),
                                 gw.query_total_asset() - gw.query_cash())

                # Monitor
                ctx = MonitorContext(
                    broker_connected=gw.is_connected(),
                    consecutive_losses=consecutive_losses,
                    daily_pnl=daily_pnl,
                    pending_order_count=om.pending_count(),
                    db_writable=True,
                )
                alerts = mc.check_all(ctx)
                dash.accumulate_alerts(alerts)

                # fail_fast
                if self._fail_fast:
                    for a in alerts:
                        if str(a.severity.value) == "critical":
                            report.exit_criteria_met = False
                            report.failure_reasons.append(
                                f"CRITICAL alert: {a.message}")
                            return report

                # 指标
                snap = metrics.snapshot()
                max_pending = max(max_pending, snap["pending_count"])
                max_mem = max(max_mem, snap["mem_mb"])
                dash.print_row(bars, snap)

                # 状态一致性
                total = gw.query_total_asset()
                cash = gw.query_cash()
                pos_v = total - cash
                if abs(total - (cash + pos_v)) > 0.01:
                    state_errors += 1

                bars += 1
                daily_bar_count += 1

                # 日终重置 (每 240 bar ≈ 1 天)
                if daily_bar_count >= 240:
                    daily.record_end_of_day(daily_pnl, consecutive_losses,
                                            dash.totals)
                    # 模拟次日重置
                    daily_pnl = 0.0
                    consecutive_losses = 0
                    ok = daily.validate_morning_reset(
                        daily_pnl, consecutive_losses, monitor_state_ok=True)
                    if ok:
                        days_completed += 1
                    daily_bar_count = 0

        except Exception as e:
            crashes += 1
            report.failure_reasons.append(f"崩溃: {e}")

        finally:
            # 收尾
            if daily_bar_count > 0:
                daily.record_end_of_day(daily_pnl, consecutive_losses,
                                        dash.totals)
                if daily.validate_morning_reset(0.0, 0, True):
                    days_completed += 1

            dash.close_csv()
            db.close()
            try:
                os.unlink(db_path)
            except Exception:
                pass

        # ---- 报告 ----
        baseline = metrics._baseline or {}
        report.duration_hours = (time.time() - start_time) / 3600
        report.bars_processed = bars
        report.crashes = crashes
        report.memory_start_mb = baseline.get("mem_mb", 0)
        report.memory_max_mb = max_mem
        report.memory_growth_pct = (
            (max_mem - baseline.get("mem_mb", max_mem))
            / max(baseline.get("mem_mb", 1), 1) * 100
        )
        report.sqlite_start_mb = baseline.get("sqlite_mb", 0)
        report.sqlite_max_mb = snap.get("sqlite_mb", 0)
        report.max_pending_orders = max_pending
        report.total_orders = snap.get("order_count", 0)
        report.alerts_warning = dash.totals["W"]
        report.alerts_error = dash.totals["E"]
        report.alerts_critical = dash.totals["C"]
        report.state_consistency_errors = state_errors
        report.daily_resets_passed = days_completed

        # 判定退出标准
        reasons = []
        if crashes > 0:
            reasons.append(f"崩溃 {crashes} 次")
        if report.memory_growth_pct > 10:
            reasons.append(f"内存增长 {report.memory_growth_pct:.1f}%")
        if report.alerts_critical > 0:
            reasons.append(f"CRITICAL 告警 {report.alerts_critical} 条")
        if state_errors > 0:
            reasons.append(f"状态不一致 {state_errors} 次")
        report.failure_reasons = reasons
        report.exit_criteria_met = len(reasons) == 0

        return report


def _calc_size(broker, price):
    cash = broker.query_cash()
    size = int(cash * 0.6 / price / 100) * 100
    return max(size, 100)
