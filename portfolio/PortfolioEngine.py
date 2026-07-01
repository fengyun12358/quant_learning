"""
PortfolioEngine — 投资组合引擎
==============================
输入多只资产的 (日期, 收益率) 序列，按权重合成组合收益。
"""

import numpy as np


class PortfolioEngine:
    def __init__(self, weights=None):
        """
        weights: dict, {"510330": 0.25, "510500": 0.25, ...}
                 不传则等权分配。
        """
        self.assets = {}        # {"name": (dates_array, returns_array)}
        self.weights = weights or {}

    def add_asset(self, name, dates, returns):
        """注册一只资产的交易记录。dates 和 returns 长度必须一致。"""
        self.assets[name] = (np.array(dates), np.array(returns))

    def run(self, rebalancer=None):
        """rebalancer: 可选 Rebalancer 实例。"""
        return self._run_simple(rebalancer)

    def _run_simple(self, rebalancer):
        """简易版：先算组合收益，有 rebalancer 时在调仓日扣成本。"""

        # 1. 日期 & 权重
        all_date_sets = [set(dates) for dates, _ in self.assets.values()]
        all_dates = sorted(set().union(*all_date_sets))
        n_assets = len(self.assets)
        weights = self.weights if self.weights else {
            name: 1.0 / n_assets for name in self.assets
        }

        # 2. 日期→收益 查找
        date_to_return = {}
        for name, (dates, returns) in self.assets.items():
            date_to_return[name] = dict(zip(dates, returns))

        # 3. 第一遍：算原始净值 + 原始组合收益
        asset_equity = {name: 1.0 for name in self.assets}
        equity_curves = {name: [] for name in self.assets}
        port_returns = []
        port_dates = []

        for date in all_dates:
            daily_return = 0.0
            has_trade = False
            for name in self.assets:
                r = date_to_return[name].get(date, 0.0)
                if r != 0.0:
                    has_trade = True
                    asset_equity[name] *= (1 + r)
                daily_return += weights[name] * r
            for name in self.assets:
                equity_curves[name].append(asset_equity[name])
            if has_trade:
                port_returns.append(daily_return)
                port_dates.append(date)

        # 4. 如果有 rebalancer，计算调仓日 + 成本，扣到组合收益里
        if rebalancer:
            triggers = rebalancer.check(
                all_dates,
                {name: np.array(eq) for name, eq in equity_curves.items()}
            )
            costs = rebalancer.compute_cost(
                all_dates,
                {name: np.array(eq) for name, eq in equity_curves.items()},
                triggers
            )
            # 只扣有交易日的成本
            cost_idx = 0
            for i, date in enumerate(all_dates):
                if cost_idx < len(port_dates) and date == port_dates[cost_idx]:
                    port_returns[cost_idx] -= costs[i]
                    cost_idx += 1

        return (np.array(port_returns), np.array(port_dates),
                {name: np.array(eq) for name, eq in equity_curves.items()})

    def describe(self, portfolio_returns, label="组合"):
        """快速输出组合基本统计。"""
        total = (1 + portfolio_returns).prod() - 1
        sharpe_approx = portfolio_returns.mean() / portfolio_returns.std() if portfolio_returns.std() > 0 else 0
        peak = np.maximum.accumulate((1 + portfolio_returns).cumprod())
        equity = (1 + portfolio_returns).cumprod()
        max_dd = ((equity - peak) / peak).min()

        print(f"\n{'='*45}")
        print(f"  {label}")
        print(f"{'='*45}")
        print(f"  总收益: {total:.2%}")
        print(f"  交易笔数: {len(portfolio_returns)}")
        print(f"  近似夏普: {sharpe_approx:.2f}")
        print(f"  最大回撤: {max_dd:.2%}")
        print(f"{'='*45}")
