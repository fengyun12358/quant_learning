"""
exp03_portfolio.py — 四 ETF 等权组合
===================================
对比单资产 vs 等权组合的收益和回撤。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from config.settings import ETF_FILES, engine_real, PORTFOLIO_WEIGHTS
from data.DataLoader import DataLoader
from strategy.MACrossStrategy import MACrossStrategy
from portfolio.PortfolioEngine import PortfolioEngine


if __name__ == "__main__":
    ma = MACrossStrategy(5, 20)
    pf = PortfolioEngine(weights=PORTFOLIO_WEIGHTS)

    for name, filepath in ETF_FILES.items():
        df = DataLoader(filepath).load()
        returns, dates = engine_real.run(ma.fit(df), stop_pct=0.03)
        pf.add_asset(name, dates, returns)

    port_r, port_d, eq = pf.run()
    pf.describe(port_r, "四ETF等权 MA(5,20) 组合")

    # 单资产对比
    print("\n  单资产对比:")
    for name in PORTFOLIO_WEIGHTS:
        print(f"    {name}: 期末净值 {eq[name][-1]:.3f}")
