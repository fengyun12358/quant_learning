"""
MACrossStrategy — 双均线交叉（向量化版）
========================================
委托 MACrossLogic 产生信号，本类只负责 DataFrame 列的输出。
"""

from strategy.MACrossLogic import MACrossLogic


class MACrossStrategy:
    """策略 = 参数 + MACrossLogic。数据进入，信号出来。"""

    def __init__(self, ma_short=5, ma_long=20, stop_pct=0.03):
        if ma_short <= 0 or ma_long <= 0:
            raise ValueError("均线窗口必须为正整数")
        if ma_short >= ma_long:
            raise ValueError("短期均线必须小于长期均线")

        self.ma_short = ma_short
        self.ma_long = ma_long
        self.stop_pct = stop_pct

    def fit(self, df):
        """逐行调用 MACrossLogic.update()，产出 golden_cross/death_cross/buy_signal/sell_signal。"""
        logic = MACrossLogic(self.ma_short, self.ma_long)

        signals = [logic.update(c) for c in df["收盘"]]

        df["golden_cross"] = [s == "buy" for s in signals]
        df["death_cross"] = [s == "sell" for s in signals]
        df["buy_signal"] = df["golden_cross"].shift(1).fillna(False)
        df["sell_signal"] = df["death_cross"].shift(1).fillna(False)
        return df
