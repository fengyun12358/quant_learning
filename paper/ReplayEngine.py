"""
ReplayEngine — 回放引擎
=======================
串联整个交易系统，逐根 bar 执行:

  CSV → MACrossLogic → RiskGate → OrderManager → PaperBroker → MonitorCenter

目的: 验证 OrderManager + SQLitePersistence + MonitorCenter 长期稳定性。
"""

import time
from strategy.MACrossLogic import MACrossLogic
from risk.RiskGate import RiskGate
from risk.OrderManager import OrderManager, OrderCallbacks
from risk.SQLitePersistence import SQLitePersistence
from monitor.MonitorCenter import MonitorCenter
from monitor.MonitorContext import MonitorContext
from monitor.monitors import (
    BrokerHeartbeatMonitor, OrderTimeoutMonitor,
    ConsecutiveLossMonitor, DailyLossMonitor, PersistenceMonitor,
)
from paper.PaperMarketDataFeed import PaperMarketDataFeed
from paper.PaperBroker import PaperBroker
from paper.PaperPortfolio import PaperPortfolio


from adapter.broker_gateway import Order


class ReplayEngine(OrderCallbacks):
    """
    回放引擎——实现 OrderCallbacks 以接收成交通知。

    用法:
      engine = ReplayEngine("data/510330.xls")
      engine.setup()
      engine.run()
      print(engine.portfolio.total_return())
    """

    def __init__(self, csv_path: str, initial_cash: float = 100000.0,
                 db_path: str = "data/paper_trading.db"):
        self.feed = PaperMarketDataFeed(csv_path)
        self.broker = PaperBroker(initial_cash)
        self.portfolio = PaperPortfolio(initial_cash)
        self._db_path = db_path

    def setup(self):
        """构建完整的交易流水线。"""

        # 1. 持久化
        self.persistence = SQLitePersistence(self._db_path)

        # 2. 风控门
        self.gate = RiskGate()

        # 3. 订单管理器
        self.om = OrderManager(self.broker, persistence=self.persistence)

        # 4. 策略
        self.logic = MACrossLogic(5, 20)

        # 5. 监控中心
        self.monitor = MonitorCenter()
        for m in [BrokerHeartbeatMonitor(), OrderTimeoutMonitor(),
                  ConsecutiveLossMonitor(), DailyLossMonitor(),
                  PersistenceMonitor()]:
            self.monitor.add(m)

        # 6. 风控状态追踪
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._in_position = False
        self._entry_price = 0.0

    def run(self, max_bars: int = 0) -> dict:
        """
        逐根 bar 执行。
        max_bars=0 表示跑完所有数据。
        返回: {"total_return", "max_dd", "bar_count", "alerts"}
        """
        alerts = []
        bars_processed = 0

        while True:
            bar = self.feed.next_bar()
            if bar is None:
                break
            if max_bars > 0 and bars_processed >= max_bars:
                break

            # 1. 更新行情
            self.broker.set_current_price("510330", bar["close"])

            # 2. 策略信号
            signal = self.logic.update(bar["close"])

            # 3. 风控检查
            # （简化版——完整版需构造 RiskContext）
            # 这里直接委托 OrderManager 处理信号
            if signal == "buy" and not self._in_position:
                self.om.submit(
                    Order(symbol="510330", side="buy", price=bar["close"],
                          size=self._calc_size(bar["close"])),
                    callbacks=self,
                )
                self._in_position = True
                self._entry_price = bar["close"]

            elif signal == "sell" and self._in_position:
                pos = self.broker.query_position("510330")
                size = pos.size if pos else 0
                if size > 0:
                    self.om.submit(
                        Order(symbol="510330", side="sell", price=bar["close"],
                              size=size),
                        callbacks=self,
                    )
                    pnl = (bar["close"] - self._entry_price) / self._entry_price
                    self._daily_pnl += pnl
                    if pnl < 0:
                        self._consecutive_losses += 1
                    else:
                        self._consecutive_losses = 0
                    self._in_position = False

            # 4. Broker 订单撮合
            self.broker.update()

            # 5. 更新净值
            self.portfolio.update(
                bar["date"],
                self.broker.query_cash(),
                self.broker.query_total_asset() - self.broker.query_cash(),
            )

            # 6. Monitor 检查
            ctx = self._build_monitor_context()
            results = self.monitor.check_all(ctx)
            for r in results:
                alerts.append({
                    "bar": bars_processed,
                    "monitor": r.monitor_name,
                    "severity": r.severity.value,
                    "message": r.message,
                })

            bars_processed += 1

        return {
            "total_return": self.portfolio.total_return(),
            "max_dd": self.portfolio.max_drawdown(),
            "bar_count": bars_processed,
            "alert_count": len(alerts),
            "alerts": alerts[:10],   # 只保留前 10 条
        }

    # ================================================================
    # OrderCallbacks
    # ================================================================

    def on_order_filled(self, order_id, filled_price, filled_size):
        pass   # 净值追踪已在主循环

    def on_order_rejected(self, order_id, reason):
        pass

    def on_order_timeout(self, order_id):
        pass

    # ================================================================
    # 内部
    # ================================================================

    def _calc_size(self, price):
        cash = self.broker.query_cash()
        size = int(cash * 0.6 / price / 100) * 100
        return max(size, 100)

    def _build_monitor_context(self):
        return MonitorContext(
            broker_connected=self.broker.pending_count() == 0,
            broker_last_heartbeat=time.time(),
            pending_order_count=self.broker.pending_count(),
            consecutive_losses=self._consecutive_losses,
            daily_pnl=self._daily_pnl,
            seconds_since_last_bar=0.0,
            last_bar_time="",
        )
