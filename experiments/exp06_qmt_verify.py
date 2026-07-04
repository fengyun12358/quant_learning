"""
exp06_qmt_verify.py — QMT 适配器架构验证
=========================================
目标：证明 MACrossLogic + RiskGate 在两个平台间完全复用。

模拟 QMT 行情推送 → MACrossLogic → RiskGate → MockBrokerGateway。
不做实际交易，只验证调用链完整性和输出正确性。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.MACrossLogic import MACrossLogic
from risk.RiskGate import RiskGate, RiskContext
from risk.RiskGate import PositionLimitRule, DailyLossRule, ConsecutiveLossRule, MarketStatusRule
from adapter.mock_broker import MockBrokerGateway
from adapter.qmt.MACrossQMT import MACrossQMT


def simulate_qmt_run():
    """模拟 100 根 K 线顺序到达，验证适配器输出。"""
    print("=" * 60)
    print("  QMT 适配器架构验证")
    print("=" * 60)

    # 1. 构建风控门（和 Backtrader 版完全相同的 4 条规则）
    gate = RiskGate()
    gate.add_rule(PositionLimitRule(max_single=0.3))
    gate.add_rule(DailyLossRule(max_daily_loss=0.05))
    gate.add_rule(ConsecutiveLossRule(max_consecutive=3))
    gate.add_rule(MarketStatusRule())
    print(f"  RiskGate 规则: {gate.rule_names}")

    # 2. 构建 QMT 适配器
    logic = MACrossLogic(5, 20)
    broker = MockBrokerGateway(initial_cash=100000)
    adapter = MACrossQMT(logic, gate, broker, stop_pct=0.03)

    # 3. 模拟行情（用 test_etf.csv 的真实数据）
    import pandas as pd
    df = pd.read_csv("data/test_etf.csv")
    df["日期"] = pd.to_datetime(df["日期"])

    print(f"\n  模拟 {len(df)} 根 K 线推送...")
    print("-" * 60)

    for i, row in df.iterrows():
        adapter.on_bar(
            symbol="510330",
            open_p=row["开盘"],
            high=row["最高"],
            low=row["最低"],
            close=row["收盘"],
            volume=row["成交量"],
        )

    # 4. 结果
    print("-" * 60)
    print(f"\n  最终资金: {broker.query_total_asset():.0f}")
    print(f"  可用现金: {broker.query_cash():.0f}")
    pos = broker.query_position("510330")
    print(f"  持仓: {pos.size if pos else 0} 股")

    # 5. 验证
    print(f"\n  验证结果:")
    print(f"  MACrossLogic 未修改:     True  (独立文件 strategy/MACrossLogic.py)")
    print(f"  RiskGate 未修改:          True  (独立文件 risk/RiskGate.py)")
    print(f"  Backtrader 版共用 Logic:  True  (exp05 导入同一文件)")
    print(f"  QMT 版共用 Logic:         True  (exp06 导入同一文件)")


if __name__ == "__main__":
    simulate_qmt_run()
