import pandas as pd
import numpy as np


class BacktestEngine:
    def __init__(self, cost_rate=0.0011):
        self.cost_rate = cost_rate

    def _compute_position(self, df):
        """
        根据买卖信号计算每日持仓状态 (1=持有, 0=空仓)。
        用 NaN + ffill() 处理买入到卖出之间的填充。
        """
        df["signal_raw"] = float("nan")                   # 默认 NaN，不是 0
        df.loc[df["buy_signal"], "signal_raw"] = 1        # 买入 → 1
        df.loc[df["sell_signal"], "signal_raw"] = 0       # 卖出 → 0
        df["position"] = df["signal_raw"].ffill().fillna(0)  # 直接 ffill，不需要 replace 了
        return df

    def _apply_stop_loss(self, df, stop_pct=0.03):
        """
        应用止损过滤器：当价格跌破入场价*(1-stop_pct)时强制平仓。

        参数:
            df:      包含 'position', '开盘', '最低' 列的DataFrame
            stop_pct: 止损幅度，默认0.03 (3%)

        返回:
            DataFrame: 修改后的原df (position列可能被强制改为0)
        """
        # 输入检查
        required_cols = ['position', '开盘', '最低']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame 必须包含 '{col}' 列")
        
        # 步骤1: 在入场日记录 entry_price（position从0变1的那天，取开盘价）
        df['entry_price'] = None
        
        # 找到入场日：前一天position=0，今天position=1
        entry_mask = (df['position'] == 1) & (df['position'].shift(1) == 0)
        df.loc[entry_mask, 'entry_price'] = df.loc[entry_mask, '开盘']
        
        # 步骤2: 用 .ffill() 把入场价填满整个持仓期
        # 只在持仓期间填充（position=1时），避免影响空仓期
        df['entry_price'] = df['entry_price'].ffill()
        # 持仓结束后，entry_price应该清空（但为了后续计算，保留也可以）
        # 更严谨：空仓期把entry_price设为None
        df.loc[df['position'] == 0, 'entry_price'] = None
        
        # 步骤3: 检查止损条件
        # entry_price 为 None 的行，把 stop_price 填成 +inf
        # inf 与任何数比较都不会告警，且 最低 < inf 永远为 True
        # 配合 position==1 的条件过滤，空仓期不会误触发
        stop_price = (df['entry_price'] * (1 - stop_pct)).fillna(float('inf'))

        stop_trigger = (df['position'] == 1) & (df['最低'] < stop_price)

        # 触发日把 position 强制改为 0
        df.loc[stop_trigger, 'position'] = 0
        
        # 清理辅助列（可选）
        # df.drop('entry_price', axis=1, inplace=True)
        
        return df
        

    def _pair_trades(self, df):
        """
        从持仓状态提取每笔交易的入场/出场配对。

        position 列中 0→1 为入场, 1→0 为出场。
        入场用"开盘"价, 出场用"开盘"价。
        如果最后一天仍持仓，用当日"收盘"价强制平仓。

        参数:
            df: 含 "position", "开盘", "收盘", "日期" 列的 DataFrame
        返回:
            entry_prices: np.ndarray  入场价格序列
            exit_prices:  np.ndarray  出场价格序列
        """
        df["position_in"] = df["position"].diff() == 1
        df["position_out"] = df["position"].diff() == -1
        entry_dates = df.loc[df["position"].diff() == 1]
        exit_dates  = df.loc[df["position"].diff() == -1]
        if df["position"].iloc[-1] == 1:
            last_row = df.iloc[[-1]].copy()
            last_row["开盘"] = last_row["收盘"]  # 出场价用收盘价
            exit_dates = pd.concat([exit_dates, last_row], ignore_index=True)
        entry_prices = entry_dates["开盘"].values
        exit_prices  = exit_dates["开盘"].values
        # 如果有仓位管理，取仓位比例；否则默认全仓
        if "position_pct" in entry_dates.columns:
            entry_pcts = entry_dates["position_pct"].values
        else:
            entry_pcts = np.ones(len(entry_dates))
        return entry_prices, exit_prices, entry_pcts 

    def _compute_returns(self, entry_prices, exit_prices, position_pcts, cost_rate=0.0):
        """
        计算每笔交易收益率（可选扣除成本）。

        参数:
            entry_prices: 买入价数组
            exit_prices:  卖出价数组
            cost_rate:    单边成本费率 (佣金+滑点), 默认 0
        返回:
            np.ndarray: 每笔收益率
        """
        # 配对：只取前 min(len(entry), len(exit)) 对
        n = min(len(entry_prices), len(exit_prices))

        # 每笔收益率 = (卖出价 - 买入价) / 买入价
        # returns = (exit_prices[:n] - entry_prices[:n]) / entry_prices[:n]
        exit_prices_real = exit_prices * (1 - cost_rate)
        entry_prices_real = entry_prices * (1 + cost_rate)
        # returns = (exit_prices_real[:n] - entry_prices_real[:n]) / entry_prices_real[:n]
        # 收益 = 价格变化率 × 仓位比例
        # 如果 position_pct = 0.6，那实际只投入了 60% 的资金
        returns = (exit_prices_real - entry_prices_real) / entry_prices_real
        returns = returns * position_pcts[:n]    # 仓位缩放
        return returns

    def _extract_trade_dates(self, df):
        return df.loc[df["position"].diff() == 1, "日期"].values

    
    def run(self, df, stop_pct=0):
        """
        核心方法：接收策略产出的 df（含 buy_signal/sell_signal），
        跑完全部回测流程，返回每笔收益率数组。
        stop_pct=0 表示不止损, >0 表示止损幅度(如0.03=3%)。
        """
        # 1. compute_position
        df = self._compute_position(df)
        # 2. apply_stop_loss（stop_pct > 0 时才启用止损）
        if stop_pct > 0:
            df = self._apply_stop_loss(df, stop_pct)
        # 3. pair_trades
        entry_prices,exit_prices,position_pcts = self._pair_trades(df)
        # 4. compute_returns
        returns = self._compute_returns(entry_prices, exit_prices, position_pcts, self.cost_rate)
        
        # 从 _pair_trades 里提取入场日期
        trade_dates = self._extract_trade_dates(df)
        
        return returns, trade_dates
