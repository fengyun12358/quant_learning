"""
MACrossQMT — MiniQMT 适配器
============================
与 MACrossBT 职责完全对称：

  接收行情 → MACrossLogic → RiskGate → BrokerGateway

不修改 MACrossLogic 和 RiskGate，只做平台翻译。
"""

from strategy.MACrossStrategy import MACrossStrategy   # 仅作参考，实际用 MACrossLogic
from risk.RiskGate import RiskGate, RiskContext
from adapter.broker_gateway import BrokerGateway


# 导入独立的 MACrossLogic（和 Backtrader 版共用的那一个）
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MACrossQMT:
    """
    MiniQMT 适配器。

    职责完全对称于 MACrossBT：
      - MACrossBT 在 Backtrader 的 next() 里接收 K 线
      - MACrossQMT 在 MiniQMT 的 on_bar() 里接收 K 线

    其余 Logic / RiskGate / BrokerGateway 调用链完全一致。
    """

    def __init__(self, logic, risk_gate: RiskGate, broker: BrokerGateway,
                 stop_pct: float = 0.03):
        self.logic = logic          # MACrossLogic 实例（和 Backtrader 版共用）
        self.gate = risk_gate       # RiskGate 实例（和 Backtrader 版共用）
        self.broker = broker        # MockBrokerGateway / MiniQMTGateway
        self.stop_pct = stop_pct
        self._sma_short_vals = []   # 模拟均线计算（实际中 MiniQMT 可以调 talib）
        self._sma_long_vals = []
        self._in_position = False
        self._entry_price = 0.0
        self._consecutive_losses = 0

    def on_bar(self, symbol: str, open_p, high, low, close, volume,
               market_status: str = "TRADING"):
        """
        收到一根 K 线——等同于 Backtrader 的 next()。
        每根 bar 调用一次。

        参数全部是平台无关的原始数据，不依赖 QMT API 结构体。
        """
        # 1. 更新均线（简化版，实际中用 talib 或 pandas）
        self._sma_short_vals.append(close)
        self._sma_long_vals.append(close)
        if len(self._sma_short_vals) > 5:
            self._sma_short_vals.pop(0)
        if len(self._sma_long_vals) > 20:
            self._sma_long_vals.pop(0)

        if len(self._sma_long_vals) < 20:
            return  # 数据不足，不产生信号

        sma_short = sum(self._sma_short_vals) / len(self._sma_short_vals)
        sma_long = sum(self._sma_long_vals) / len(self._sma_long_vals)

        # 2. 信号生成 → MACrossLogic（和 Backtrader 版完全相同）
        signal = self.logic.update(sma_short, sma_long)

        # 3. 构建 RiskContext（QMT 版 ContextBuilder 的职责——内联简化）
        pos = self.broker.query_position(symbol)
        current_pos_pct = (pos.size * close / self.broker.query_total_asset()
                           if pos and self.broker.query_total_asset() > 0 else 0.0)

        context = RiskContext(
            signal=signal,
            symbol=symbol,
            price=close,
            current_position=current_pos_pct,
            total_asset=self.broker.query_total_asset(),
            cash=self.broker.query_cash(),
            consecutive_losses=self._consecutive_losses,
            market_status=market_status,
        )

        # 4. 风控门检查（和 Backtrader 版完全相同）
        result = self.gate.check(context)

        # 5. 通过后才下单
        if signal == "buy" and not self._in_position:
            if not result.approved:
                print(f"  [风控拒绝] {result.rule_name}: {result.reason}")
                return

            size = self._calc_size(close)
            order_result = self.broker.buy(symbol, close, size)
            if order_result.status == "filled":
                self._in_position = True
                self._entry_price = close
                print(f"{symbol} 买入 {size}股 @{close:.3f}")

        elif signal == "sell" and self._in_position:
            pos = self.broker.query_position(symbol)
            if pos and pos.size > 0:
                self.broker.sell(symbol, close, pos.size)
                pnl = (close - self._entry_price) / self._entry_price
                if pnl < 0:
                    self._consecutive_losses += 1
                else:
                    self._consecutive_losses = 0
                self._in_position = False
                print(f"{symbol} 卖出 {pos.size}股 @{close:.3f} 盈亏={pnl:.2%}")

    def _calc_size(self, price):
        """根据可用资金的 60% 计算买入股数（100 的整数倍）。"""
        cash = self.broker.query_cash()
        size = int(cash * 0.6 / price / 100) * 100
        return max(size, 100)
