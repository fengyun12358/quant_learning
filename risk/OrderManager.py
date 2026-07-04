"""
OrderManager — 订单生命周期管理
================================
职责：
  1. 订单状态机（CREATED→PENDING→FILLED/REJECTED/TIMEOUT）
  2. 超时检测 + 自动重试
  3. 串行保证（同一标的前一单未完成，后一单进入等待队列）
  4. 回调通知策略层（on_filled / on_rejected / on_timeout）

纯 Python。不依赖 Backtrader / MiniQMT。
"""

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from adapter.broker_gateway import BrokerGateway, Order, OrderResult, Position


# ============================================================
# 订单状态机
# ============================================================

class OrderStatus(Enum):
    CREATED    = "created"     # 已创建，尚未提交
    SUBMITTED  = "submitted"   # 已提交到券商，等待交易所确认
    ACCEPTED   = "accepted"    # 交易所已接受，等待成交
    PARTIAL    = "partial"     # 部分成交
    FILLED     = "filled"      # 完全成交
    REJECTED   = "rejected"    # 券商/交易所拒单
    CANCELLED  = "cancelled"   # 已撤销
    TIMEOUT    = "timeout"     # 超时未成交


@dataclass
class ManagedOrder:
    """OrderManager 内部追踪的订单——比 BrokerGateway.Order 多了生命周期字段。"""
    order: Order
    order_id: str
    status: OrderStatus = OrderStatus.CREATED
    filled_price: float = 0.0
    filled_size: int = 0
    reject_reason: str = ""
    created_at: float = 0.0      # time.time()
    submitted_at: float = 0.0
    retry_count: int = 0
    callback: Optional["OrderCallbacks"] = None


# ============================================================
# 回调接口
# ============================================================

class OrderCallbacks(ABC):
    """策略层实现此接口，接收订单生命周期事件。"""

    @abstractmethod
    def on_order_filled(self, order_id: str, filled_price: float,
                        filled_size: int):
        ...

    @abstractmethod
    def on_order_rejected(self, order_id: str, reason: str):
        ...

    @abstractmethod
    def on_order_timeout(self, order_id: str):
        ...


# ============================================================
# OrderManager
# ============================================================

class OrderManager:
    """
    订单管理器。

    用法:
      om = OrderManager(broker, timeout_sec=5, max_retries=2)
      om.submit(order, callbacks=my_callbacks)

      # 在主循环里每 tick 调用一次
      om.update()
    """

    def __init__(self, broker: BrokerGateway,
                 timeout_sec: float = 5.0,
                 max_retries: int = 2,
                 persistence=None):            # Optional[SQLitePersistence]
        self._broker = broker
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries
        self._persistence = persistence
        self._orders: dict[str, ManagedOrder] = {}
        self._pending_queue: list[ManagedOrder] = []

    # ---- 公共接口 ----

    def submit(self, order: Order,
               callbacks: Optional[OrderCallbacks] = None) -> str:
        """
        提交订单。返回 order_id。
        如果 broker 繁忙（有未完成订单），进入等待队列。
        """
        mo = ManagedOrder(
            order=order,
            order_id=f"ORD-{uuid.uuid4().hex[:8]}",
            status=OrderStatus.CREATED,
            created_at=time.time(),
            callback=callbacks,
        )
        self._orders[mo.order_id] = mo

        if self._has_pending():
            self._pending_queue.append(mo)
        else:
            self._send_to_broker(mo)

        return mo.order_id

    def cancel(self, order_id: str):
        """撤销订单。"""
        mo = self._orders.get(order_id)
        if mo and mo.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIAL):
            self._broker.cancel(order_id)
            mo.status = OrderStatus.CANCELLED

    def update(self):
        """
        每 tick 调用一次。Must be called from main loop.
        检查超时、处理重试逻辑、发送等待队列中的订单。
        """
        now = time.time()

        for mo in list(self._orders.values()):
            # 超时检测
            if mo.status == OrderStatus.SUBMITTED:
                elapsed = now - mo.submitted_at
                if elapsed > self._timeout_sec:
                    if mo.retry_count < self._max_retries:
                        mo.retry_count += 1
                        self._send_to_broker(mo)  # 重试
                    else:
                        mo.status = OrderStatus.TIMEOUT
                        if mo.callback:
                            mo.callback.on_order_timeout(mo.order_id)

        # 队列中下一个订单（如果没有进行中的单子了）
        if not self._has_pending() and self._pending_queue:
            next_mo = self._pending_queue.pop(0)
            self._send_to_broker(next_mo)

    def get_order(self, order_id: str) -> Optional[ManagedOrder]:
        return self._orders.get(order_id)

    def pending_count(self) -> int:
        return sum(1 for mo in self._orders.values()
                   if mo.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIAL))

    # ---- 对外通知 ----

    def on_broker_fill(self, order_id: str, fill_price: float, fill_size: int):
        """Broker 成交后回调——PaperBroker.update() 内部调用。"""
        mo = self._orders.get(order_id)
        if mo and mo.status == OrderStatus.SUBMITTED:
            mo.status = OrderStatus.FILLED
            mo.filled_price = fill_price
            mo.filled_size = fill_size
            if mo.callback:
                mo.callback.on_order_filled(order_id, fill_price, fill_size)
            if self._persistence:
                self._persistence.save_order(mo)

    def notify_result(self, order_id: str, result: OrderResult):
        """
        Broker 层返回结果后调用此方法（或在同一线程内直接调）。
        根据 result.status 驱动状态机迁移。
        """
        mo = self._orders.get(order_id)
        if mo is None:
            return

        if result.status == "filled":
            mo.status = OrderStatus.FILLED
            mo.filled_price = result.filled_price
            mo.filled_size = result.filled_size
            if mo.callback:
                mo.callback.on_order_filled(
                    order_id, result.filled_price, result.filled_size
                )

        elif result.status == "rejected":
            mo.status = OrderStatus.REJECTED
            mo.reject_reason = result.reject_reason
            if mo.callback:
                mo.callback.on_order_rejected(order_id, result.reject_reason)

        elif result.status == "pending":
            mo.status = OrderStatus.SUBMITTED

        # 状态迁移 → 自动持久化
        if self._persistence:
            self._persistence.save_order(mo)

    # ---- 内部 ----

    def _send_to_broker(self, mo: ManagedOrder):
        """真正发送订单到 BrokerGateway。"""
        mo.submitted_at = time.time()

        if mo.order.side == "buy":
            result = self._broker.buy(
                mo.order.symbol, mo.order.price,
                mo.order.size, mo.order.order_type,
                order_id=mo.order_id,
            )
        else:
            result = self._broker.sell(
                mo.order.symbol, mo.order.price,
                mo.order.size, mo.order.order_type,
                order_id=mo.order_id,
            )

        # 事件驱动模型：Broker 返回 pending → 等 Broker 回调
        # 同步模型：Broker 立即返回 filled/rejected → 直接 notify
        if result.status == "pending":
            mo.status = OrderStatus.SUBMITTED
            if hasattr(self._broker, 'set_order_callback'):
                self._broker.set_order_callback(self.on_broker_fill)
        else:
            self.notify_result(mo.order_id, result)

    def _has_pending(self) -> bool:
        return any(
            mo.status in (OrderStatus.SUBMITTED, OrderStatus.ACCEPTED,
                          OrderStatus.PARTIAL)
            for mo in self._orders.values()
        )
