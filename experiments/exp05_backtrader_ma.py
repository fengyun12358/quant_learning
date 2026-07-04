import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import backtrader as bt
from data.DataLoader import DataLoader
from risk.RiskGate import RiskGate, BtContextBuilder
from risk.RiskGate import PositionLimitRule, DailyLossRule, ConsecutiveLossRule, MarketStatusRule

from strategy.MACrossLogic import MACrossLogic


class FixedPctSizer(bt.Sizer):
    """固定仓位比例：每次买入用资金的 X%"""
    params = dict(percents=60)

    def _getsizing(self, comminfo, cash, data, isbuy):
        if not isbuy:
            return self.broker.getposition(data).size  # 卖出 = 全部清仓
        size = (cash * self.p.percents / 100) / data.close[0]
        return int(size)


class MACrossBT(bt.Strategy):
    """Backtrader 版 —— 策略逻辑 + 风控门 + 订单执行"""
    params = dict(ma_short=5, ma_long=20, stop_pct=0.03)

    def __init__(self):
        self.logic = MACrossLogic(self.p.ma_short, self.p.ma_long)
        self.order = None
        self.stop_order = None

        # 风控门 + ContextBuilder（通过类属性注入）
        self.risk_gate = getattr(self.__class__, 'shared_gate', None)
        self.ctx_builder = BtContextBuilder(self, self.data)

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None
            # 平仓后通知 builder 更新连续亏损计数
            if order.status == order.Completed and order.executed.size > 0:
                pnl = order.executed.pnl
                self.ctx_builder.on_trade_closed(pnl)

    def _check_risk(self, signal):
        """风控门检查。通过返回 True，拒绝打印原因并返回 False。"""
        if self.risk_gate is None:
            return True
        ctx = self.ctx_builder.build(signal)
        result = self.risk_gate.check(ctx)
        if not result.approved:
            print(f"  [风控拒绝] {result.rule_name}: {result.reason}")
            return False
        return True

    def next(self):
        if self.order:
            return

        signal = self.logic.update(self.data.close[0])

        if signal == "buy" and not self.position:
            if not self._check_risk("buy"):
                return
            self.order = self.buy()
            stop_price = self.data.close[0] * (1 - self.p.stop_pct)
            self.stop_order = self.sell(exectype=bt.Order.Stop, price=stop_price)
            print(f"{self.data.datetime.date()} 买入 @{self.data.close[0]:.3f}")

        elif signal == "sell" and self.position:
            if self.stop_order:
                self.cancel(self.stop_order)
            self.order = self.sell()
            print(f"{self.data.datetime.date()} 卖出 @{self.data.close[0]:.3f}")



if __name__ == "__main__":
    # 1. 初始化 Cerebro（大脑——调度引擎）
    cerebro = bt.Cerebro()

    # 2. 加载你的真实数据
    df = DataLoader("data/510330.xls").load()
    df["日期"] = pd.to_datetime(df["日期"])
    df.set_index("日期", inplace=True)

    # data = bt.feeds.PandasData(dataname=df)  # 你的 DataFrame → Backtrader 格式
    data = bt.feeds.PandasData(
    dataname=df,
    datetime=None,        # None = 用 DataFrame 的 index 作为日期
    open="开盘",          # 列名 → Backtrader 标准字段
    high="最高",
    low="最低",
    close="收盘",
    volume="成交量",
    openinterest=-1,     # ETF 没有持仓量
)

    cerebro.adddata(data)

    # 3. 构建风控门
    gate = RiskGate()
    gate.add_rule(PositionLimitRule(max_single=0.3, max_total=1.0))
    gate.add_rule(DailyLossRule(max_daily_loss=0.05))
    gate.add_rule(ConsecutiveLossRule(max_consecutive=3))
    gate.add_rule(MarketStatusRule())

    # 4. 注入风控门 + 注册策略
    MACrossBT.shared_gate = gate
    cerebro.addsizer(FixedPctSizer)
    cerebro.addstrategy(MACrossBT)

    # 4. 设初始资金
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.0011)   # 单边 0.11%

    # 5. 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                        riskfreerate=0.02, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    # 6. 跑！
    print(f"初始资金: {cerebro.broker.getvalue():.0f}")
    results = cerebro.run()
    print(f"最终资金: {cerebro.broker.getvalue():.0f}")

    # 7. 打印分析结果
    strat = results[0]
    print(f"\n--- Backtrader Analyzer 结果 ---")
    sharpe = strat.analyzers.sharpe.get_analysis()
    print(f"夏普比率: {sharpe.get('sharperatio', 'N/A')}")
    dd = strat.analyzers.drawdown.get_analysis()
    print(f"最大回撤: {dd.max.drawdown:.2%}")
    trade = strat.analyzers.trades.get_analysis()
    print(f"总交易笔数: {trade.total.closed}")
    print(f"盈利笔数: {trade.won.total}, 亏损笔数: {trade.lost.total}")
    ret = strat.analyzers.returns.get_analysis()
    print(f"年化收益率: {ret.get('rnorm100', 0):.2f}%")

    # ---- 对比向量化版信号 ----
    from strategy.MACrossStrategy import MACrossStrategy
    df2 = DataLoader("data/510330.xls").load()
    df2 = MACrossStrategy(5, 20).fit(df2)
    signals = df2.loc[df2["golden_cross"] | df2["death_cross"],
                      ["日期", "golden_cross", "death_cross"]]
    print("\n向量化版信号 (头3 + 尾3):")
    print(pd.concat([signals.head(3), signals.tail(3)]).to_string())
    print(f"金叉: {(df2['golden_cross']).sum()}次  死叉: {(df2['death_cross']).sum()}次")
