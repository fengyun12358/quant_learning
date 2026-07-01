"""
exp02_sizer_comparison.py — 真实 ETF 仓位管理对比
=================================================
全仓 vs 固定60% vs 风险预算2% vs 波动率自适应。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import ETF_FILES, engine_raw, engine_real, analyzer
from data.DataLoader import DataLoader
from strategy.MACrossStrategy import MACrossStrategy
from risk.PositionSizer import FixedPositionSizer, FixedRiskSizer, VolatilitySizer


def run_with_sizer(name, df, strategy, sizer=None):
    df = strategy.fit(df.copy())
    if sizer:
        df = sizer.size(df)
    r_gross, _ = engine_raw.run(df)
    r_net, _ = engine_real.run(df, stop_pct=0.03)
    m_g = analyzer.analyze(r_gross, len(df))
    m_n = analyzer.analyze(r_net, len(df))
    analyzer.report(name, m_g, m_n, analyzer.buy_hold_benchmark(df))


if __name__ == "__main__":
    ma = MACrossStrategy(5, 20)
    fixed60 = FixedPositionSizer(ratio=0.6)
    risk2 = FixedRiskSizer(risk_per_trade=0.02, stop_pct=0.03)
    vol = VolatilitySizer(risk_per_trade=0.02, volatility_multiple=2.0, window=20)

    for label, sizer in [("全仓", None), ("固定60%", fixed60),
                          ("风险预算2%", risk2), ("波动率自适应", vol)]:
        print(f"\n{'#'*60}\n#  真实ETF — MA(5,20) {label}\n{'#'*60}")
        for name, filepath in ETF_FILES.items():
            df = DataLoader(filepath).load()
            run_with_sizer(f"{name} {label}", df, ma, sizer=sizer)
