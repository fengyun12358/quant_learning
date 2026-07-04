"""
BrokerGateway — 券商网关抽象接口
================================
任何券商（MiniQMT / 国金QMT / Backtrader模拟）都实现这个接口。
策略适配器只依赖这个接口——不依赖具体券商。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    """订单对象"""
    symbol: str
    side: str             # "buy" / "sell"
    price: float
    size: int             # 股数
    order_type: str = "market"   # "market" / "limit" / "stop"


@dataclass
class OrderResult:
    """订单执行结果"""
    order_id: str
    status: str           # "filled" / "rejected" / "pending"
    filled_price: float = 0.0
    filled_size: int = 0
    reject_reason: str = ""


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    size: int             # 当前持有股数
    avg_cost: float       # 持仓均价
    current_price: float = 0.0


class BrokerGateway(ABC):
    """
    券商网关抽象接口。

    实现类: MockBrokerGateway / MiniQMTGateway / GuojinQMTGateway
    """

    @abstractmethod
    def buy(self, symbol: str, price: float, size: int,
            order_type: str = "market") -> OrderResult:
        """发送买入订单"""
        ...

    @abstractmethod
    def sell(self, symbol: str, price: float, size: int,
             order_type: str = "market") -> OrderResult:
        """发送卖出订单"""
        ...

    @abstractmethod
    def cancel(self, order_id: str) -> OrderResult:
        """撤销订单"""
        ...

    @abstractmethod
    def query_position(self, symbol: str) -> Optional[Position]:
        """查询指定标的的持仓"""
        ...

    @abstractmethod
    def query_cash(self) -> float:
        """查询可用资金"""
        ...

    @abstractmethod
    def query_total_asset(self) -> float:
        """查询总资产"""
        ...
