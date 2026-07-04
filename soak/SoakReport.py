"""
SoakReport — 浸泡测试最终报告
=============================
纯数据结构，记录 N 小时/天运行后的全部关键指标。
"""

from dataclasses import dataclass, field


@dataclass
class SoakReport:
    duration_hours: float = 0.0
    bars_processed: int = 0
    crashes: int = 0

    # 资源
    memory_start_mb: float = 0.0
    memory_max_mb: float = 0.0
    memory_growth_pct: float = 0.0
    sqlite_start_mb: float = 0.0
    sqlite_max_mb: float = 0.0

    # 订单
    max_pending_orders: int = 0
    max_order_latency_ms: float = 0.0
    total_orders: int = 0

    # 告警
    alerts_warning: int = 0
    alerts_error: int = 0
    alerts_critical: int = 0

    # 状态一致性
    state_consistency_errors: int = 0

    # 每日重置
    daily_resets_passed: int = 0
    daily_resets_total: int = 0

    # 判定
    exit_criteria_met: bool = False
    failure_reasons: list[str] = field(default_factory=list)

    def print(self):
        print("\n" + "=" * 60)
        print("  SOAK TEST REPORT")
        print("=" * 60)
        print(f"  运行时长: {self.duration_hours:.1f}h  {self.bars_processed} bars")
        print(f"  崩溃: {self.crashes}")
        print(f"  内存: {self.memory_start_mb:.0f} → {self.memory_max_mb:.0f}MB "
              f"(+{self.memory_growth_pct:.1f}%)")
        print(f"  SQLite: {self.sqlite_start_mb:.1f} → {self.sqlite_max_mb:.1f}MB")
        print(f"  订单: total={self.total_orders} max_pending={self.max_pending_orders}")
        print(f"  告警: W={self.alerts_warning} E={self.alerts_error} "
              f"C={self.alerts_critical}")
        print(f"  状态不一致: {self.state_consistency_errors}")
        print(f"  每日重置: {self.daily_resets_passed}/{self.daily_resets_total}")
        print(f"  {'='*30}")
        print(f"  EXIT CRITERIA: {'PASS' if self.exit_criteria_met else 'FAIL'}")
        if self.failure_reasons:
            for reason in self.failure_reasons:
                print(f"    FAIL: {reason}")
        print("=" * 60)
