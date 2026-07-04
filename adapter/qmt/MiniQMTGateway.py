"""
MiniQMTGateway V1 — 仿真盘券商网关
===================================
implements BrokerGateway。零业务逻辑, 只做翻译。

V1: 内部委托 PaperBroker (架构验证)
V2: 替换 _call_broker 为真实 xtquant API 调用

职责边界:
  ✅ BrokerGateway 接口实现
  ✅ local_order_id ↔ broker_order_id 映射
  ✅ xtquant API 调用翻译 (V2)
  ❌ 超时重试 → OrderManager
  ❌ 风控判断 → RiskGate
  ❌ 对账策略 → BrokerReconcile
"""

from typing import Optional
from adapter.broker_gateway import BrokerGateway, OrderResult, Position
from paper.PaperBroker import PaperBroker


class MiniQMTGateway(BrokerGateway):
    """
    国金 MiniQMT 券商网关。V1 委托 PaperBroker。

    用法:
      with MiniQMTGateway(account_id="888888", is_simulation=True) as gw:
          gw.buy("510330", 3.5, 1000, order_id="ORD-001")
    """

    def __init__(self, account_id: str = "888888",
                 is_simulation: bool = True,
                 initial_cash: float = 100000.0):
        self._account = account_id
        self._simulation = is_simulation
        self._connected = False

        # V1: 内部委托 PaperBroker
        self._broker = PaperBroker(initial_cash)

        # local_order_id → broker_order_id 映射
        self._id_map: dict[str, str] = {}

    # ================================================================
    # 上下文管理
    # ================================================================

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ================================================================
    # 连接管理
    # ================================================================

    def connect(self, qmt_path: str = "") -> bool:
        """V1: 模拟连接。V2: xt_mini = xtquant.MiniQMTClient(qmt_path)。"""
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ================================================================
    # BrokerGateway 接口
    # ================================================================

    def buy(self, symbol: str, price: float, size: int,
            order_type: str = "market", order_id: str = "") -> OrderResult:
        """
        V1: 委托 PaperBroker。
        V2: xt_trader.order_stock(symbol, xtconstant.STOCK_BUY, size, ...)
        """
        result = self._broker.buy(symbol, price, size, order_type, order_id)

        # 记录 ID 映射
        if order_id and result.order_id:
            self._id_map[order_id] = result.order_id

        return result

    def sell(self, symbol: str, price: float, size: int,
             order_type: str = "market", order_id: str = "") -> OrderResult:
        result = self._broker.sell(symbol, price, size, order_type, order_id)

        if order_id and result.order_id:
            self._id_map[order_id] = result.order_id

        return result

    def cancel(self, order_id: str) -> OrderResult:
        """V2: xt_trader.cancel_order_stock(order_id)"""
        broker_id = self._id_map.get(order_id, order_id)
        return self._broker.cancel(broker_id)

    def query_position(self, symbol: str) -> Optional[Position]:
        """V2: xt_trader.query_stock_position(account, symbol)"""
        return self._broker.query_position(symbol)

    def query_cash(self) -> float:
        """V2: xt_trader.query_stock_asset(account)"""
        return self._broker.query_cash()

    def query_total_asset(self) -> float:
        """
        优先用券商返回值。V1 暂无 xtquant, 委托 PaperBroker。
        V2: xt_trader.query_stock_asset(account)['总资产']
        """
        return self._broker.query_total_asset()

    # ================================================================
    # 回调桥接
    # ================================================================

    def set_order_callback(self, callback):
        """注册成交回调 → PaperBroker 或 xtquant 的 on_order_update。"""
        self._broker.set_order_callback(callback)

    def update(self, clock_tick: float = 1.0):
        """V1: 推进 PaperBroker 时钟。V2: 不需要（xtquant 自行回调）。"""
        self._broker.update(clock_tick)

    # ================================================================
    # V2 预留
    # ================================================================

    def _call_qmt(self, method: str, **kwargs):
        """
        V2 替换点。
        所有 xtquant API 调用通过此方法，便于统一错误处理和重试。
        """
        raise NotImplementedError("V2: 替换为 xtquant API 调用")
