"""
exp01_smoke_test.py — 模拟数据冒烟测试
======================================
跑 MA 和 RSI 策略 + 三个 Sizer 对比。
每次改代码后跑这个，30 秒确认没有损坏。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from config.settings import engine_raw, engine_real, analyzer
from strategy.MACrossStrategy import MACrossStrategy
from strategy.RSIStrategy import RSIStrategy
from risk.PositionSizer import FixedPositionSizer, FixedRiskSizer, VolatilitySizer


def run(name, df, strategy, sizer=None):
    """小工具：跑一个策略/sizer 组合并打印报告。"""
    df = strategy.fit(df.copy())
    if sizer:
        df = sizer.size(df)
    r_gross, _ = engine_raw.run(df)
    r_net, _ = engine_real.run(df, stop_pct=0.03)
    m_g = analyzer.analyze(r_gross, len(df))
    m_n = analyzer.analyze(r_net, len(df))
    analyzer.report(name, m_g, m_n, analyzer.buy_hold_benchmark(df))


if __name__ == "__main__":
    df = pd.read_csv("data/test_etf.csv")
    ma = MACrossStrategy(5, 20)
    rsi = RSIStrategy(14, 30, 70)

    print("=" * 50 + "\n  冒烟测试\n" + "=" * 50)

    run("MA(5,20) 全仓", df.copy(), ma)
    run("RSI(14) 全仓", df.copy(), rsi)
    run("MA 固定60%仓位", df.copy(), ma,
        FixedPositionSizer(ratio=0.6))
    run("MA 风险预算2%", df.copy(), ma,
        FixedRiskSizer(risk_per_trade=0.02, stop_pct=0.03))
    run("MA 波动率自适应", df.copy(), ma,
        VolatilitySizer(risk_per_trade=0.02, volatility_multiple=2.0, window=20))

    print("\n冒烟测试全部通过。\n")
