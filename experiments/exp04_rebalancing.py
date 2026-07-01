"""
exp04_rebalancing.py — 再平衡方式对比
===================================
无 / 月度 / 阈值 — 对比再平衡成本与收益。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from config.settings import ETF_FILES, engine_real, PORTFOLIO_WEIGHTS
from data.DataLoader import DataLoader
from strategy.MACrossStrategy import MACrossStrategy
from portfolio.PortfolioEngine import PortfolioEngine
from portfolio.Rebalancer import Rebalancer


if __name__ == "__main__":
    ma = MACrossStrategy(5, 20)

    for method in ["none", "monthly", "threshold"]:
        pf = PortfolioEngine(weights=PORTFOLIO_WEIGHTS)

        for name, filepath in ETF_FILES.items():
            df = DataLoader(filepath).load()
            returns, dates = engine_real.run(ma.fit(df), stop_pct=0.03)
            pf.add_asset(name, dates, returns)

        rb = Rebalancer(PORTFOLIO_WEIGHTS, method=method) if method != "none" else None
        port_r, port_d, eq = pf.run(rebalancer=rb)

        total = (1 + port_r).prod() - 1
        peak = np.maximum.accumulate((1 + port_r).cumprod())
        max_dd = (((1 + port_r).cumprod() - peak) / peak).min()
        print(f"  Rebalance={method:10s}  return={total:.2%}  max_dd={max_dd:.2%}  trades={len(port_r)}")
