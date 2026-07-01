class Rebalancer:
    def __init__(self, target_weights, method="monthly", threshold=0.05):
        """
        method: "monthly" / "quarterly" / "threshold" / "none"
        threshold: 权重偏离超过此值才触发（仅 method="threshold" 时用）
        """
        self.target_weights = target_weights
        self.method = method
        self.threshold = threshold
    
    def check(self, dates, equity_curves):
        """
        输入: 日期数组 + 每资产净值曲线
        输出: rebalance_dates = 需要调仓的日期列表
        """
        if self.method == "monthly":
            triggers = []
            prev_month = None
            for i, d in enumerate(dates):
                month = d.month if hasattr(d, 'month') else int(str(d)[5:7])
                if month != prev_month:
                    triggers.append(True)
                    prev_month = month
                else:
                    triggers.append(False)
        if self.method == "threshold":
            triggers = []
            for i in range(len(dates)):
                total = sum(equity_curves[name][i] for name in equity_curves)
                actual = {name: equity_curves[name][i] / total for name in equity_curves}
                deviated = any(
                    abs(actual[name] - self.target_weights.get(name, 0)) > self.threshold
                    for name in equity_curves
                )
                triggers.append(deviated)
        return triggers
    
    def compute_cost(self, dates, equity_curves, triggers, cost_rate=0.0011):
        """
        计算每次调仓的摩擦成本。

        返回值: costs 数组，长度 = len(dates)
                调仓日 = 交易费比例，非调仓日 = 0
        """
        costs = []
        names = list(equity_curves.keys())

        for i in range(len(dates)):
            if not triggers[i]:
                costs.append(0.0)
                continue

            # 当日实际权重
            total = sum(equity_curves[name][i] for name in names)
            actual = {name: equity_curves[name][i] / total for name in names}

            # 总偏离量 = Σ |实际 - 目标|
            deviation = sum(
                abs(actual[name] - self.target_weights.get(name, 0))
                for name in names
            )

            # 双边交易量 = 偏离量，成本 = 双边 × 费率
            cost = deviation * cost_rate
            costs.append(cost)

        return costs






