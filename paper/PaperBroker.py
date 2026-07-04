"""
PaperBroker — 模拟真实券商
==========================
implements BrokerGateway。

特性:
  - 事件驱动延迟（不阻塞主循环）
  - 随机滑点（SlippageModel 可插拔）
  - 部分成交（10% 概率）
  - 涨跌停拒单（LIMP_UP 不买, LIMP_DOWN 不卖）
  - 价格偏离 >5% 拒单
"""

import random
import time
import uuid
from typing import Optional

from adapter.broker_gateway import BrokerGateway, OrderResult, Position
from paper.SlippageModel import SlippageModel, RandomSlippageModel


class PaperBroker(BrokerGateway):
    def __init__(self, initial_cash: float = 100000.0,
                 slippage: SlippageModel = None,
                 delay_range: tuple[float, float] = (0.1, 1.0),
                 partial_fill_prob: float = 0.10):
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._slippage = slippage or RandomSlippageModel(0.003)
        self._delay_range = delay_range
        self._partial_fill_prob = partial_fill_prob

        # 事件驱动: {order_id: PendingOrder}
        self._pending: dict[str, dict] = {}
        self._market_status: dict[str, str] = {}   # symbol → market_status

    # ================================================================
    # 行情注入
    # ================================================================

    def set_market_status(self, symbol: str, status: str):
        """设置涨跌停状态——由 MarketDataFeed 每根 bar 调用。"""
        self._market_status[symbol] = status

    def set_current_price(self, symbol: str, price: float):
        """更新当前价——用于 query_position 和市价估算。"""
        if symbol in self._positions:
            self._positions[symbol].current_price = price

    # ================================================================
    # BrokerGateway 接口
    # ================================================================

    def buy(self, symbol, price, size, order_type="market"):
        return self._submit(symbol, "buy", price, size, order_type)

    def sell(self, symbol, price, size, order_type="market"):
        return self._submit(symbol, "sell", price, size, order_type)

    def cancel(self, order_id):
        if order_id in self._pending:
            del self._pending[order_id]
            return OrderResult(order_id=order_id, status="filled",
                               reject_reason="已撤销（模拟）")
        return OrderResult(order_id=order_id, status="rejected",
                           reject_reason="订单不存在")

    def query_position(self, symbol):
        return self._positions.get(symbol)

    def query_cash(self):
        return self._cash

    def query_total_asset(self):
        pos_value = sum(
            p.size * p.current_price for p in self._positions.values()
        )
        return self._cash + pos_value

    # ================================================================
    # 事件驱动更新——主循环每 tick 调用
    # ================================================================

    def update(self, clock_tick: float = 1.0):
        """
        处理 pending 订单。
        clock_tick: 模拟时间推进秒数（默认 1.0s per bar）。

        实际处理逻辑: 所有 pending 订单都推进 clock_tick，
        到达 ready_time 则立即撮合。
        """
        self._sim_clock = getattr(self, '_sim_clock', 0.0) + clock_tick
        filled_ids = []

        for oid, po in list(self._pending.items()):
            if self._sim_clock >= po["ready_time"]:
                filled_ids.append(oid)

        for oid in filled_ids:
            po = self._pending.pop(oid)
            self._execute(po["symbol"], po["side"], po["price"],
                          po["size"], oid)

    def pending_count(self):
        return len(self._pending)

    def reset(self):
        """重置账户到初始状态（用于多轮测试）。"""
        self._cash = self._initial_cash
        self._positions.clear()
        self._pending.clear()

    # ================================================================
    # 内部
    # ================================================================

    def _submit(self, symbol, side, price, size, order_type):
        order_id = f"PAPER-{uuid.uuid4().hex[:8]}"

        # 涨跌停拦截
        status = self._market_status.get(symbol, "TRADING")
        if status == "LIMIT_UP" and side == "buy":
            return OrderResult(order_id=order_id, status="rejected",
                               reject_reason="涨停板，无法买入")
        if status == "LIMIT_DOWN" and side == "sell":
            return OrderResult(order_id=order_id, status="rejected",
                               reject_reason="跌停板，无法卖出")

        # 价格偏离 >5% → 拒单
        pos = self._positions.get(symbol)
        ref_price = pos.current_price if pos else price
        if abs(price - ref_price) / ref_price > 0.05:
            return OrderResult(order_id=order_id, status="rejected",
                               reject_reason=f"价格偏离 {abs(price-ref_price)/ref_price:.1%}>5%")

        # 事件驱动: 不 sleep, 记 ready_time
        delay = random.uniform(*self._delay_range)
        sim_now = getattr(self, '_sim_clock', 0.0)
        self._pending[order_id] = {
            "symbol": symbol,
            "side": side,
            "price": price,
            "size": size,
            "ready_time": sim_now + delay,
        }
        return OrderResult(order_id=order_id, status="pending")

    def _execute(self, symbol, side, price, size, order_id):
        """到达 ready_time 后真正撮合。"""
        exec_price = self._slippage.apply(price, side)

        # 部分成交: 10% 概率
        fill_size = size
        if random.random() < self._partial_fill_prob:
            fill_size = random.randint(int(size * 0.5), int(size * 0.9))
            fill_size = max(100, fill_size)   # 最少 100 股

        if side == "buy":
            cost = exec_price * fill_size
            if cost > self._cash:
                fill_size = int(self._cash / exec_price / 100) * 100
                if fill_size == 0:
                    return   # 买不起，静默失败
                cost = exec_price * fill_size
            self._cash -= cost
            self._update_position(symbol, fill_size, exec_price, is_buy=True)
        else:
            pos = self._positions.get(symbol)
            if not pos or pos.size < fill_size:
                fill_size = pos.size if pos else 0
            if fill_size == 0:
                return
            self._cash += exec_price * fill_size
            self._update_position(symbol, fill_size, exec_price, is_buy=False)

    def _update_position(self, symbol, size, price, is_buy):
        if symbol in self._positions:
            p = self._positions[symbol]
            if is_buy:
                total_cost = p.avg_cost * p.size + price * size
                p.size += size
                p.avg_cost = total_cost / p.size
            else:
                p.size -= size
                if p.size <= 0:
                    del self._positions[symbol]
        elif is_buy:
            self._positions[symbol] = Position(
                symbol=symbol, size=size, avg_cost=price, current_price=price
            )
