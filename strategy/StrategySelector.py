class StrategySelector:
    def __init__(self, trend_strategy, revert_strategy):
        self.trend_strategy = trend_strategy
        self.revert_strategy = revert_strategy
    
    def fit(self, df):
        # 1. 在两个副本上分别跑策略
        df_trend = self.trend_strategy.fit(df.copy())
        df_revert = self.revert_strategy.fit(df.copy())
        
        # 2. df 里已经有 "regime" 列（RegimeDetector 加的）
        # 3. 按 regime 分别取对应策略的信号
        mask_trend = df["regime"] == "trend"
        mask_revert = df["regime"] == "mean_revert"
        
        df["buy_signal"] = False
        df["sell_signal"] = False
        if mask_trend.any():
            df.loc[mask_trend, "buy_signal"] = df_trend.loc[mask_trend, "buy_signal"]
            df.loc[mask_trend, "sell_signal"] = df_trend.loc[mask_trend, "sell_signal"]

        if mask_revert.any():
            df.loc[mask_revert, "buy_signal"] = df_revert.loc[mask_revert, "buy_signal"]
            df.loc[mask_revert, "sell_signal"] = df_revert.loc[mask_revert, "sell_signal"]

        # df.loc[mask_trend, "buy_signal"] = df_trend.loc[mask_trend, "buy_signal"]
        # df.loc[mask_trend, "sell_signal"] = df_trend.loc[mask_trend, "sell_signal"]
        # df.loc[mask_revert, "buy_signal"] = df_revert.loc[mask_revert, "buy_signal"]
        # df.loc[mask_revert, "sell_signal"] = df_revert.loc[mask_revert, "sell_signal"]
        
        return df

