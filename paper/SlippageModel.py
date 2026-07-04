"""
SlippageModel — 滑点模型
========================
V1 实现 RandomSlippageModel。
接口预留，未来可扩展 Fixed / Percentage。
"""

import random
from abc import ABC, abstractmethod


class SlippageModel(ABC):
    """滑点模型基类"""

    @abstractmethod
    def apply(self, price: float, side: str) -> float:
        """
        传入理想价格，返回含滑点的成交价。
        side = "buy" → 成交价 >= 理想价
        side = "sell" → 成交价 <= 理想价
        """
        ...


class RandomSlippageModel(SlippageModel):
    """
    随机滑点: 成交价在 [price, price*(1+max_pct)] 之间均匀分布。
    """

    def __init__(self, max_pct: float = 0.003):
        self.max_pct = max_pct

    def apply(self, price: float, side: str) -> float:
        slip = random.uniform(0, self.max_pct)
        if side == "buy":
            return price * (1 + slip)
        else:
            return price * (1 - slip)


class NoSlippageModel(SlippageModel):
    """零滑点——用于对比测试。"""

    def apply(self, price: float, side: str) -> float:
        return price
