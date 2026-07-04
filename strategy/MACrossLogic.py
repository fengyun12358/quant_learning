"""
MACrossLogic — 纯信号算法（平台无关）
=====================================
不依赖 Backtrader、MiniQMT、任何券商 API。
只做一件事：收两个 SMA 值 → 返回 "buy"/"sell"/"hold"。
"""


class MACrossLogic:
    """
    双均线交叉信号——纯 Python，无外部依赖。

    用法:
      logic = MACrossLogic(5, 20)
      signal = logic.update(sma_short_val, sma_long_val)
      # signal ∈ {"buy", "sell", "hold"}
    """

    def __init__(self, ma_short: int = 5, ma_long: int = 20):
        self.ma_short_period = ma_short
        self.ma_long_period = ma_long
        self._prev_relation: int | None = None   # 前一根 bar 的短期/长期关系

    def update(self, sma_short_val: float, sma_long_val: float) -> str:
        """
        每根 bar 调用一次。
        返回 "buy" / "sell" / "hold"。
        """
        relation = 1 if sma_short_val > sma_long_val else 0
        signal = "hold"

        if self._prev_relation is not None:
            # 0→1 金叉, 1→0 死叉
            if self._prev_relation == 0 and relation == 1:
                signal = "buy"
            elif self._prev_relation == 1 and relation == 0:
                signal = "sell"

        self._prev_relation = relation
        return signal
