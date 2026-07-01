class RegimeDetector:
    def __init__(self, window=50, trend_threshold=0.6, mean_revert_threshold=0.3):
        self.window = window
        self.trend_threshold = trend_threshold
        self.mean_revert_threshold = mean_revert_threshold
    
    def fit(self, df):
        """
        输入: 含"收盘"列的 df
        输出: df 新增一列 "regime"
              regime = "trend" / "mean_revert" / "neutral"
        """
        price = df["收盘"]
        price = price.shift(1).fillna(price[0])
        total_move = (price - price.shift(self.window))         # N天终点 - 起点
        actual_path = price.diff().abs().rolling(self.window).sum()        # N天每一步的绝对值之和
        efficiency_ratio = abs(total_move) / actual_path
        # efficiency_ratio_avg = efficiency_ratio.mean()
        # 前 window 行的 ER 为 NaN，fillna 填什么最保守？
        condition = efficiency_ratio.copy()
        condition[:self.window] = None      # 前50天数据不足，标记为不确定

        df["regime"] = "neutral"                          # 默认不交易
        df.loc[condition > self.trend_threshold, "regime"] = "trend"
        df.loc[condition < self.mean_revert_threshold, "regime"] = "mean_revert"

        return df

