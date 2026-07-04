"""
MockBrokerGateway — 模拟券商网关
================================
只打印订单，不连接任何券商。
用于架构验证：证明 Logic → RiskGate → BrokerGateway 通路正确。
"""

import uuid
from adapter.broker_gateway import BrokerGateway, OrderResult, Position


class MockBrokerGateway(BrokerGateway):
    """
    模拟券商——所有操作只打印日志，返回模拟结果。

    用途：验证调用链完整性，不验证实际交易逻辑。
    """

    def __init__(self, initial_cash: float = 100000.0):
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._order_log: list[OrderResult] = []

    def buy(self, symbol, price, size, order_type="market"):
        order_id = f"MOCK-{uuid.uuid4().hex[:8]}"
        result = OrderResult(
            order_id=order_id,
            status="filled",
            filled_price=price,
            filled_size=size,
        )
        # 模拟更新持仓
        if symbol in self._positions:
            p = self._positions[symbol]
            total_cost = p.avg_cost * p.size + price * size
            p.size += size
            p.avg_cost = total_cost / p.size
        else:
            self._positions[symbol] = Position(
                symbol=symbol, size=size, avg_cost=price, current_price=price
            )
        self._cash -= price * size
        self._order_log.append(result)
        print(f"  [MOCK 买入] {symbol} {size}股 @{price:.3f}  id={order_id}")
        return result

    def sell(self, symbol, price, size, order_type="market"):
        order_id = f"MOCK-{uuid.uuid4().hex[:8]}"
        result = OrderResult(
            order_id=order_id,
            status="filled",
            filled_price=price,
            filled_size=size,
        )
        if symbol in self._positions:
            self._positions[symbol].size -= size
            if self._positions[symbol].size <= 0:
                del self._positions[symbol]
        self._cash += price * size
        self._order_log.append(result)
        print(f"  [MOCK 卖出] {symbol} {size}股 @{price:.3f}  id={order_id}")
        return result

    def cancel(self, order_id):
        print(f"  [MOCK 撤单] {order_id}")
        return OrderResult(order_id=order_id, status="filled", reject_reason="已模拟撤销")

    def query_position(self, symbol):
        return self._positions.get(symbol)

    def query_cash(self):
        return self._cash

    def query_total_asset(self):
        position_value = sum(
            p.size * p.current_price for p in self._positions.values()
        )
        return self._cash + position_value
