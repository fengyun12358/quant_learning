"""
MiniQMTGateway V2 — 仿真盘券商网关
===================================
implements BrokerGateway。零业务逻辑。

V2 新增:
  - 真实 xtquant API 调用
  - 订单状态: SUBMITTED → ACCEPTED → FILLED
  - on_order_update / on_trade_update 回调分离
  - 参数化 Reconcile 周期
  - xtquant 不可用时自动降级为 PaperBroker (开发环境兼容)

用法:
  gw = MiniQMTGateway(account_id="888888", qmt_path="D:/国金QMT")
  gw.connect()
  result = gw.buy("510330", 3.5, 1000)  # 返回 pending, 等回调
"""

import time
from typing import Optional
from adapter.broker_gateway import BrokerGateway, OrderResult, Position

# 尝试导入 xtquant，不可用时降级
try:
    from xtquant import xtdata, xtconstant
    _HAS_XTQUANT = True
except ImportError:
    _HAS_XTQUANT = False


class MiniQMTGateway(BrokerGateway):
    """
    国金 MiniQMT 券商网关。
    V2: 真实 xtquant + PaperBroker 降级。
    V3: 实盘账户 (account_type="REAL")。
    """

    # ---- xtquant 订单状态 → OrderStatus ----
    XT_STATUS_MAP = {
        48: "submitted",    # 已提交
        49: "accepted",     # 交易所已接受
        50: "partial",      # 部分成交
        51: "partial",      # 部成(本日)
        52: "filled",       # 全部成交
        53: "filled",       # 全部成交(本日)
        54: "cancelled",    # 已撤
        55: "rejected",     # 废单
        56: "rejected",     # 拒单
    }

    def __init__(self, account_id: str = "", qmt_path: str = "",
                 is_simulation: bool = True, initial_cash: float = 100000.0,
                 reconcile_interval_sec: int = 300):
        self._account = account_id
        self._qmt_path = qmt_path
        self._simulation = is_simulation
        self._connected = False
        self._xt_trader = None
        self._session_id = int(time.time()) % 100000

        # 降级
        self._use_xtquant = _HAS_XTQUANT and bool(qmt_path)
        if not self._use_xtquant:
            from paper.PaperBroker import PaperBroker
            self._broker = PaperBroker(initial_cash)
        else:
            self._broker = None

        # 回调
        self._order_callback = None
        self._trade_callback = None

        # ID 映射: local_order_id → xt_order_id
        self._id_map: dict[str, str] = {}
        self._reverse_id_map: dict[str, str] = {}

        # Reconcile
        self._reconcile_interval = reconcile_interval_sec
        self._last_reconcile = 0.0

    # ================================================================
    # 上下文管理
    # ================================================================

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ================================================================
    # 连接管理 (按建议顺序)
    # ================================================================

    def connect(self) -> bool:
        """1. 连接 → xtquant 或 降级"""
        if not self._use_xtquant:
            self._connected = True
            return True

        try:
            from xtquant import XTQuantTrader
            self._xt_trader = XTQuantTrader(self._qmt_path, self._session_id)
            self._xt_trader.set_callback(_QMTCallback(self))
            self._xt_trader.start()
            # 等待连接确认 (最多 5 秒)
            for _ in range(50):
                if self._connected:
                    break
                time.sleep(0.1)
            if self._connected and self._account:
                self._xt_trader.subscribe(self._account)
            return self._connected
        except Exception as e:
            self._connected = False
            return False

    def disconnect(self):
        if self._xt_trader:
            try:
                self._xt_trader.stop()
            except Exception:
                pass
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ================================================================
    # BrokerGateway 接口
    # ================================================================

    def buy(self, symbol: str, price: float, size: int,
            order_type: str = "market", order_id: str = "") -> OrderResult:
        """2a. 下单 → xtquant / 降级"""
        return self._submit(symbol, "buy", price, size, order_type, order_id)

    def sell(self, symbol: str, price: float, size: int,
             order_type: str = "market", order_id: str = "") -> OrderResult:
        return self._submit(symbol, "sell", price, size, order_type, order_id)

    def cancel(self, order_id: str) -> OrderResult:
        """3. 撤单"""
        if not self._use_xtquant:
            return self._broker.cancel(order_id)

        xt_id = self._id_map.get(order_id, order_id)
        try:
            self._xt_trader.cancel_order_stock(self._account, xt_id)
            return OrderResult(order_id=order_id, status="pending",
                               reject_reason="撤单请求已发送")
        except Exception as e:
            return OrderResult(order_id=order_id, status="rejected",
                               reject_reason=str(e))

    def query_position(self, symbol: str) -> Optional[Position]:
        """4. 查询持仓 → xtquant / 降级"""
        if not self._use_xtquant:
            return self._broker.query_position(symbol)

        try:
            pos = self._xt_trader.query_stock_position(self._account, symbol)
            if pos and pos.volume > 0:
                return Position(
                    symbol=symbol, size=pos.volume,
                    avg_cost=pos.open_price, current_price=pos.market_value / max(pos.volume, 1)
                )
        except Exception:
            pass
        return None

    def query_cash(self) -> float:
        if not self._use_xtquant:
            return self._broker.query_cash()

        try:
            asset = self._xt_trader.query_stock_asset(self._account)
            return float(asset.cash) if asset else 0.0
        except Exception:
            return 0.0

    def query_total_asset(self) -> float:
        """5. 总资产 → 优先券商返回值"""
        if not self._use_xtquant:
            return self._broker.query_total_asset()

        try:
            asset = self._xt_trader.query_stock_asset(self._account)
            return float(asset.total_asset) if asset else 0.0
        except Exception:
            return self.query_cash()

    # ================================================================
    # 回调注册
    # ================================================================

    def set_order_callback(self, callback):
        """6a. OrderManager.on_broker_fill 回调 (降级时转发到 PaperBroker)"""
        self._order_callback = callback
        if not self._use_xtquant and hasattr(self._broker, 'set_order_callback'):
            self._broker.set_order_callback(callback)

    def set_trade_callback(self, callback):
        """6b. 成交明细回调 (SQLite 写入)"""
        self._trade_callback = callback

    # ================================================================
    # Reconcile
    # ================================================================

    def maybe_reconcile(self, reconciler) -> bool:
        """
        7. 按周期执行 Broker Reconcile。
        reconciler: BrokerReconcile 实例。
        """
        now = time.time()
        if now - self._last_reconcile < self._reconcile_interval:
            return False

        broker_positions = {}
        for symbol in self._get_known_symbols():
            pos = self.query_position(symbol)
            if pos and pos.size > 0:
                broker_positions[symbol] = (pos.size, pos.avg_cost)

        reconciler.reconcile(broker_positions)
        self._last_reconcile = now
        return True

    # ================================================================
    # V1 兼容方法 (PaperBroker 降级时使用)
    # ================================================================

    def set_current_price(self, symbol: str, price: float):
        if not self._use_xtquant and hasattr(self._broker, 'set_current_price'):
            self._broker.set_current_price(symbol, price)

    def pending_count(self) -> int:
        return getattr(self._broker, 'pending_count', lambda: 0)() if not self._use_xtquant else 0

    def update(self, clock_tick: float = 1.0):
        if not self._use_xtquant:
            self._broker.update(clock_tick)

    # ================================================================
    # 内部
    # ================================================================

    def _submit(self, symbol, side, price, size, order_type, order_id):
        if not self._use_xtquant:
            return self._broker.buy(symbol, price, size, order_type, order_id) \
                   if side == "buy" else \
                   self._broker.sell(symbol, price, size, order_type, order_id)

        try:
            from xtconstant import STOCK_BUY, STOCK_SELL, FIX_PRICE
            direction = STOCK_BUY if side == "buy" else STOCK_SELL
            xt_id = self._xt_trader.order_stock(
                self._account, symbol, direction, size, FIX_PRICE, price
            )
            if xt_id and order_id:
                self._id_map[order_id] = str(xt_id)
                self._reverse_id_map[str(xt_id)] = order_id

            return OrderResult(
                order_id=xt_id or order_id,
                status="submitted",
            )
        except Exception as e:
            return OrderResult(
                order_id=order_id,
                status="rejected",
                reject_reason=str(e),
            )

    def _get_known_symbols(self):
        return list(set(
            list(self._reverse_id_map.keys()) + ["510330", "510500", "588000", "513100"]
        ))


# ================================================================
# xtquant 回调 → 系统内部事件
# ================================================================

class _QMTCallback:
    """
    xtquant 回调适配器。
    职责: 将 xtquant 事件翻译为 MiniQMTGateway 可理解的回调。
    """

    def __init__(self, gateway: MiniQMTGateway):
        self._gw = gateway

    def on_connected(self):
        self._gw._connected = True

    def on_disconnected(self):
        self._gw._connected = False

    def on_order_update(self, xt_order):
        """
        xtquant 订单状态变化。
        映射: xt_order.order_status → OrderStatus → on_broker_fill 回调。
        """
        status = MiniQMTGateway.XT_STATUS_MAP.get(
            xt_order.order_status, "pending"
        )
        local_id = self._gw._reverse_id_map.get(
            str(xt_order.order_id), str(xt_order.order_id)
        )
        price = getattr(xt_order, 'price', 0)
        vol = getattr(xt_order, 'volume', 0)

        cb = self._gw._order_callback
        if cb and status in ("filled", "partial"):
            cb(local_id, price, vol)
        elif cb and status == "rejected":
            cb(local_id, 0, 0)  # fill_size=0 表示拒单

    def on_trade_update(self, xt_trade):
        """
        成交明细（与订单更新分离）。
        """
        cb = self._gw._trade_callback
        if cb:
            cb(xt_trade)

    def on_account_update(self, xt_account):
        pass
