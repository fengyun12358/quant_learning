import numpy as np

class RSIStrategy:
    """
    RSI策略。
    
    策略 = 算法 + 参数
    数据进入，信号出来。
    """
    
    def __init__(self, period=14, oversold=30, overbought=70, stop_pct=0.03):
        if oversold <= 0 or overbought <= 0:
            raise ValueError("oversold 和 overbought 必须是正数")
        
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.stop_pct = stop_pct
        # self.oversold_col = f"ma{oversold}"
        # self.overbought_col = f"ma{overbought}"

    def _add_rsi(self, df, period=14, price_col="收盘"):
        """
        计算 RSI 指标并添加到 DataFrame。
        
        参数:
            df:        含价格列的 DataFrame
            period:    RSI 周期 (Wilder 原始建议 14)
            price_col: 用于计算的价格列名
        返回:
            (df, rsi_col) — df 添加了 RSI 列, rsi_col 为列名
        """
        delta = df[price_col].diff()
        
        # 涨幅: delta > 0 保留, 否则 0
        gain = delta.clip(lower=0)
        # 跌幅: delta < 0 取绝对值, 否则 0
        loss = (-delta).clip(lower=0)
        
        # N 日平均
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        
        # RS + RSI
        rs = np.where(
            avg_loss == 0,
            np.inf,                    # avg_loss=0 → RS=∞
            avg_gain / avg_loss        # 正常计算
        )
        rsi = np.where(
            avg_loss == 0,
            np.where(avg_gain == 0, 50, 100),   # 横盘→50, 全涨→100
            100 - (100 / (1 + rs))              # 正常情况
        )
        
        col_name = f"rsi{period}"
        df[col_name] = rsi
        return df, col_name
    
    def _add_rsi_signals(self, df, rsi_col, oversold=30, overbought=70):
        # 今天 vs 昨天，RSI 是否越过了阈值？
        df['rsi_yestoday'] = df[rsi_col].shift(1).fillna(50)
        df["rsi_buy"] = (df['rsi_yestoday'] < oversold) & (df[rsi_col] >= oversold)   # 从下方上穿 30
        df["rsi_sell"] = (df['rsi_yestoday'] > overbought) & (df[rsi_col] <= overbought)  # 从上方下穿 70
        df["buy_signal"] = df["rsi_buy"]
        df["sell_signal"] = df["rsi_sell"]
        return df
        

    def fit(self, df):
        df, col_name = self._add_rsi(df, self.period, "收盘")
        df = self._add_rsi_signals(df, col_name, self.oversold, self.overbought)
        return df