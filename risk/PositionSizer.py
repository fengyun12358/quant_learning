"""
仓位管理模块 — Position Sizer
=============================
FixedPositionSizer : 固定仓位比例
FixedRiskSizer     : 固定风险预算（每笔交易亏损上限）
"""


def _compute_position(df):
    """共用：根据 buy_signal/sell_signal 计算持仓状态。"""
    df["signal_raw"] = float("nan")
    df.loc[df["buy_signal"], "signal_raw"] = 1
    df.loc[df["sell_signal"], "signal_raw"] = 0
    df["position"] = df["signal_raw"].ffill().fillna(0)
    return df


class FixedPositionSizer:
    """
    固定仓位比例。
    无论市场怎么变，永远用初始资金的 X% 交易。
    """

    def __init__(self, ratio=0.6):
        if not 0 < ratio <= 1.0:
            raise ValueError("ratio 必须在 (0, 1.0] 之间")
        self.ratio = ratio

    def size(self, df, capital=100000):
        df = _compute_position(df)
        df["position_pct"] = self.ratio * df["position"]
        return df


class FixedRiskSizer:
    """
    固定风险预算。
    每笔交易最多亏损 risk_per_trade（占总资金百分比）。
    止损距离 = stop_pct，仓位 = 愿亏 / 止损距离。

    例子: risk_per_trade=0.02 (愿亏2%), stop_pct=0.03 (止损3%)
          → position_pct = 0.02/0.03 = 0.67 (六成七仓位)
    """

    def __init__(self, risk_per_trade=0.02, stop_pct=0.03):
        if not 0 < risk_per_trade < stop_pct:
            raise ValueError("risk_per_trade 必须小于 stop_pct，否则仓位会超过100%")
        self.risk_per_trade = risk_per_trade
        self.stop_pct = stop_pct

    def size(self, df, capital=100000):
        df = _compute_position(df)
        pct = min(self.risk_per_trade / self.stop_pct, 1.0)
        df["position_pct"] = pct * df["position"]
        return df
    
class VolatilitySizer:
    """
    波动率自适应仓位。
    止损距离 = volatility_multiple × 近期日波动率
    仓位 = risk_per_trade / 动态止损距离
    """
    def __init__(self, risk_per_trade=0.02, volatility_multiple=2.0, window=20):
        self.risk_per_trade = risk_per_trade
        self.volatility_multiple = volatility_multiple
        self.window = window
    
    def size(self, df, capital=100000):
        # 1. 计算近期 volatility（收盘价的日波动率 std）
        # 2. 动态止损距离 = volatility_multiple × volatility
        # 3. 动态仓位 = risk_per_trade / 动态止损距离，截断到 [0, 1.0]
        # 4. df["position_pct"] = 动态仓位 × df["position"]
        df = _compute_position(df)
        # 日收益率
        daily_returns = df["收盘"].pct_change()
        # 过去 N 天的波动率（年化前，日度值通常 1%~3%）
        volatility = daily_returns.rolling(self.window).std()

        dyn_stop_pct = self.volatility_multiple * volatility   # 2.0 × 1.5% = 3%
        dyn_position_pct = self.risk_per_trade / dyn_stop_pct  # 0.02 / 0.03 = 0.67
        dyn_position_pct = dyn_position_pct.clip(0, 1.0)       # 截断到 [0, 1.0]
        dyn_position_pct = dyn_position_pct.fillna(0)


        df["position_pct"] = dyn_position_pct * df["position"]
        return df

