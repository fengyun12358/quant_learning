"""
风控门模块 (Risk Gate)
======================
策略信号在变成真实订单之前，必须通过风控门检查。

架构:
  RiskContext  — 封装所有运行时数据
  RiskResult   — 统一返回结构
  RiskRule     — 规则基类（新增规则 = 新增子类）
  RiskGate     — 协调器（遍历规则，短路返回）

纯 Python，不依赖 Backtrader / MiniQMT / 任何券商 API。
"""

from dataclasses import dataclass, field
from typing import Any


# ============================================================
# 数据结构
# ============================================================

@dataclass
class RiskContext:
    """风控运行时上下文——每次 check() 传入一份。"""
    signal: str                    # "buy" / "sell" / "hold"
    symbol: str = ""               # 标的代码
    price: float = 0.0             # 当前价格
    current_position: float = 0.0  # 当前策略持仓比例 (0~1)
    total_position: float = 0.0    # 所有策略总持仓比例 (0~1)
    total_asset: float = 0.0       # 总资产
    cash: float = 0.0              # 可用现金
    daily_pnl: float = 0.0         # 当日累计盈亏 (比例)
    consecutive_losses: int = 0    # 连续亏损笔数
    market_status: str = "TRADING" # "TRADING" / "PRE_OPEN" / "CLOSED" / "LIMIT_UP" / "LIMIT_DOWN"
    lot_size: int = 100            # 最小交易单位 (ETF = 100 份)
    price_limit_pct: float = 0.10  # 涨跌停幅度 (主板 0.10, 科创 0.20)


@dataclass
class RiskResult:
    """风控检查结果。approved=True 表示通过，可以下单。"""
    approved: bool
    rule_name: str = ""            # 拒绝时记录哪条规则拦截
    reason: str = ""               # 人类可读的拒绝原因
    metadata: dict = field(default_factory=dict)  # 扩展信息: {"剩余仓位": 0.12, ...}

    @classmethod
    def ok(cls):
        """便捷工厂：通过"""
        return cls(approved=True)

    @classmethod
    def reject(cls, rule_name: str, reason: str, **metadata):
        """便捷工厂：拒绝"""
        return cls(approved=False, rule_name=rule_name, reason=reason, metadata=metadata)


# ============================================================
# 规则基类
# ============================================================

class RiskRule:
    """
    风控规则基类。

    子类只需实现 check(self, context) → RiskResult。
    构造函数参数由各子类自行声明，互不干扰。
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def check(self, context: RiskContext) -> RiskResult:
        raise NotImplementedError(f"{self.name}.check() 未实现")


# ============================================================
# 具体规则
# ============================================================

class PositionLimitRule(RiskRule):
    """
    仓位限制：
      max_single = 单策略最大仓位 (默认 0.3)
      max_total  = 全部策略合计最大仓位 (默认 1.0 即不限制)
    """

    def __init__(self, max_single: float = 0.3, max_total: float = 1.0):
        self.max_single = max_single
        self.max_total = max_total

    def check(self, context: RiskContext) -> RiskResult:
        if context.signal != "buy":
            return RiskResult.ok()

        new_single = context.current_position + 0.1  # 粗略估计单笔买入约 10%仓位
        if new_single > self.max_single:
            return RiskResult.reject(
                self.name,
                f"单策略仓位将达 {new_single:.0%}，超过上限 {self.max_single:.0%}",
                剩余仓位=max(0, self.max_single - context.current_position),
            )

        new_total = context.total_position + 0.1
        if new_total > self.max_total:
            return RiskResult.reject(
                self.name,
                f"总仓位将达 {new_total:.0%}，超过上限 {self.max_total:.0%}",
                剩余仓位=max(0, self.max_total - context.total_position),
            )

        return RiskResult.ok()


class DailyLossRule(RiskRule):
    """
    日内亏损熔断：当日累计亏损超过阈值 → 停止交易直到次日。
    """

    def __init__(self, max_daily_loss: float = 0.05):
        self.max_daily_loss = max_daily_loss

    def check(self, context: RiskContext) -> RiskResult:
        if context.daily_pnl < -self.max_daily_loss:
            return RiskResult.reject(
                self.name,
                f"当日累计亏损 {context.daily_pnl:.2%}，超过熔断阈值 {self.max_daily_loss:.0%}",
                恢复时间="次日 09:30",
            )
        return RiskResult.ok()


class ConsecutiveLossRule(RiskRule):
    """
    连续亏损熔断：连续 N 笔亏损 → 停止交易。
    """

    def __init__(self, max_consecutive: int = 3):
        self.max_consecutive = max_consecutive

    def check(self, context: RiskContext) -> RiskResult:
        if context.consecutive_losses >= self.max_consecutive:
            return RiskResult.reject(
                self.name,
                f"连续亏损 {context.consecutive_losses} 笔，达到上限 {self.max_consecutive}",
            )
        return RiskResult.ok()


class MarketStatusRule(RiskRule):
    """
    市场状态限制：涨停不能买、跌停不能卖、非交易时段不操作。
    """

    def check(self, context: RiskContext) -> RiskResult:
        status = context.market_status

        if status == "LIMIT_UP" and context.signal == "buy":
            return RiskResult.reject(self.name, "涨停板，无法买入")
        if status == "LIMIT_DOWN" and context.signal == "sell":
            return RiskResult.reject(self.name, "跌停板，无法卖出")
        if status in ("PRE_OPEN", "CLOSED"):
            return RiskResult.reject(self.name, f"非交易时段 ({status})")

        return RiskResult.ok()


# ============================================================
# 协调器
# ============================================================

class RiskGate:
    """
    风控门——协调所有规则。

    用法:
      gate = RiskGate()
      gate.add_rule(PositionLimitRule(max_single=0.3))
      gate.add_rule(DailyLossRule(max_daily_loss=0.05))
      result = gate.check(context)
      if not result.approved:
          print(f"风控拒绝: {result.reason}")
    """

    def __init__(self):
        self._rules: list[RiskRule] = []

    def add_rule(self, rule: RiskRule):
        """注册一条风控规则。"""
        self._rules.append(rule)

    def remove_rule(self, rule_name: str):
        """按类名移除规则。"""
        self._rules = [r for r in self._rules if r.name != rule_name]

    def check(self, context: RiskContext) -> RiskResult:
        """
        遍历所有规则。
        任一规则拒绝 → 立刻短路返回。
        全部通过 → RiskResult.ok()。
        """
        for rule in self._rules:
            result = rule.check(context)
            if not result.approved:
                return result
        return RiskResult.ok()

    @property
    def rule_names(self) -> list[str]:
        return [r.name for r in self._rules]


# ============================================================
# Context Builder — 将平台状态翻译为 RiskContext
# ============================================================

class ContextBuilder:
    """
    ContextBuilder 基类。

    每个交易平台（Backtrader / MiniQMT）实现自己的 build()。
    RiskGate 不依赖任何平台——ContextBuilder 负责翻译。
    """

    def build(self, signal: str) -> RiskContext:
        raise NotImplementedError


class BtContextBuilder(ContextBuilder):
    """
    Backtrader → RiskContext 适配器。

    从 Backtrader 的 broker / strategy / data 中提取运行时状态，
    翻译为平台无关的 RiskContext。
    """

    def __init__(self, strategy, data):
        """
        strategy: bt.Strategy 实例 (MACrossBT)
        data:     bt.feeds.PandasData 实例
        """
        self._strategy = strategy
        self._data = data
        self._consecutive_losses = 0
        self._last_trade_pnl = 0.0

    def build(self, signal: str) -> RiskContext:
        broker = self._strategy.broker
        pos = self._strategy.position

        return RiskContext(
            signal=signal,
            symbol=self._data._name or "",
            price=self._data.close[0],
            current_position=pos.size * self._data.close[0] / broker.getvalue()
                              if pos and broker.getvalue() > 0 else 0.0,
            total_position=broker.getvalue() - broker.getcash(),
            total_asset=broker.getvalue(),
            cash=broker.getcash(),
            daily_pnl=0.0,               # Backtrader 不自动算日内盈亏，需策略层跟踪
            consecutive_losses=self._consecutive_losses,
            market_status="TRADING",
        )

    def on_trade_closed(self, pnl: float):
        """策略层通知：一笔交易已平仓，盈亏 = pnl。"""
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
