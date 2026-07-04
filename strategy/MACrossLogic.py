"""
MACrossLogic — 纯信号算法（平台无关）
=====================================
不依赖 Backtrader、MiniQMT、任何券商 API。
只做一件事：收收盘价 → 内部算 SMA → 返回 "buy"/"sell"/"hold"。

向量化版、Backtrader版、QMT版共用同一个 update(close_price)。
"""

from collections import deque


class MACrossLogic:
    """
    双均线交叉信号——纯 Python，无外部依赖。

    用法:
      logic = MACrossLogic(5, 20)
      for close in price_list:
          signal = logic.update(close)
      # signal ∈ {"buy", "sell", "hold"}
    """

    def __init__(self, ma_short: int = 5, ma_long: int = 20):
        if ma_short >= ma_long:
            raise ValueError(f"ma_short({ma_short}) 必须小于 ma_long({ma_long})")
        self.ma_short = ma_short
        self.ma_long = ma_long
        self._prices: deque[float] = deque(maxlen=ma_long)  # 自动维护窗口
        self._prev_relation: int | None = None

    def update(self, close_price: float) -> str:
        """
        每根 bar 调用一次。传收盘价，内部算 SMA，返回信号。
        """
        self._prices.append(close_price)

        if len(self._prices) < self.ma_long:
            return "hold"           # 数据不足 ma_long 根，不产生信号

        # 用 deque 切片算 SMA（O(k)，k=窗口长度）
        sma_short = sum(list(self._prices)[-self.ma_short:]) / self.ma_short
        sma_long = sum(self._prices) / self.ma_long

        relation = 1 if sma_short > sma_long else 0
        signal = "hold"

        if self._prev_relation is not None:
            # 0→1 金叉, 1→0 死叉
            if self._prev_relation == 0 and relation == 1:
                signal = "buy"
            elif self._prev_relation == 1 and relation == 0:
                signal = "sell"

        self._prev_relation = relation
        return signal
