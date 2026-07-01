class MACrossStrategy:
    """
    双均线交叉策略。
    
    策略 = 算法 + 参数
    数据进入，信号出来。
    """
    
    def __init__(self, ma_short=5, ma_long=20, stop_pct=0.03):
        if ma_short <= 0 or ma_long <= 0:
            raise ValueError("均线窗口必须为正整数")
        if ma_short >= ma_long:
            raise ValueError("短期均线必须小于长期均线")
        
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.stop_pct = stop_pct
        self.short_col = f"ma{ma_short}"
        self.long_col = f"ma{ma_long}"
        

    def fit(self, df):
        df[self.short_col] = df["收盘"].rolling(self.ma_short).mean()
        df[self.long_col] = df["收盘"].rolling(self.ma_long).mean()
        df["today_up"] = df[self.short_col] > df[self.long_col]
        signal_int = df["today_up"].astype(int)
        df["golden_cross"] = signal_int.diff() == 1
        df["death_cross"] = signal_int.diff() == -1
        df["buy_signal"] = df["golden_cross"].shift(1).fillna(False)
        df["sell_signal"] = df["death_cross"].shift(1).fillna(False)
        return df

    # def fit(self, df):
    #     """
    #     检测均线交叉信号。
        
    #     参数:
    #         df:        含均线列的 DataFrame
    #         short_col: 短期均线列名 (如 "ma5")
    #         long_col:  长期均线列名 (如 "ma20")
    #     返回:
    #         在 df 上添加两列: "golden_cross", "death_cross"
    #     """
    #     df["today_up"] = df[short_col] > df[long_col]
    #     signal_int = df["today_up"].astype(int)
    #     df["golden_cross"] = signal_int.diff() == 1
    #     df["death_cross"] = signal_int.diff() == -1
    #     return df

    # def generate_trade_signals(df):
    #     """
    #     将交叉信号转为次日开盘执行的交易信号。
    #     金叉→次日买入, 死叉→次日卖出。
    #     .shift(1).fillna(False) 确保没有未来函数。
    #     """
    #     df["buy_signal"] = df["golden_cross"].shift(1).fillna(False)
    #     df["sell_signal"] = df["death_cross"].shift(1).fillna(False)
    #     return df