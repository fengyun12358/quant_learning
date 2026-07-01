import numpy as np


class PerformanceAnalyzer:
    """不 print，只计算。输出交给调用方决定（print / 写文件 / 画图）。"""
    
    @staticmethod
    def analyze(returns, trading_days):
        """返回指标 dict，纯计算"""
        # 1. 总收益率（复利累乘）
        cumulative_return = (1 + returns).prod() - 1   # .prod() = 所有元素连乘

        # 2. 胜率
        win_rate = (returns > 0).sum() / len(returns)   # True=1, False=0 → sum 就是计数

        # 3. 最大单笔盈利
        max_profit = returns.max()

        # 4. 最大单笔亏损
        max_loss = returns.min()

        # Sharpe Ratio（夏普比率）
        # = (年化收益率 - 无风险利率) / 年化波动率
        # 衡量"每承受1%的波动，换来了多少超额收益"

        # Calmar Ratio（卡尔玛比率）
        # = 年化收益率 / 最大回撤的绝对值
        # 衡量"每承受1%的回撤，换来了多少收益"

        # 年化收益率（假设 returns 的跨度是 N 年）
        years = trading_days / 250    # 约500天/250=2年，5是估计的交易天数占回测天数的比例
        # 更精确：years = (回测结束日 - 开始日).days / 365
        annual_return = (1 + cumulative_return) ** (1 / years) - 1

        # 年化波动率：单笔收益 std × sqrt(年交易次数)
        annual_vol = returns.std() * np.sqrt(len(returns) / years)

        # 夏普
        sharpe = (annual_return - 0.02) / annual_vol if annual_vol > 0 else 0

        # 权益曲线 → 最大回撤
        equity = (1 + returns).cumprod()
        peak = np.maximum.accumulate(equity)
        max_dd = ((equity - peak) / peak).min()     # 负数

        # 卡尔玛
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0



        return {
            "总收益率": cumulative_return,
            "胜率": win_rate,
            "最大盈利": max_profit,
            "最大亏损": max_loss,
            "夏普": sharpe,
            "卡尔玛": calmar,
            "最大回撤": max_dd,
        }
    
    @staticmethod
    def buy_hold_benchmark(df, cost_rate=0.0011):
        """返回买入持有收益率，纯计算"""
        bh_entry = df["开盘"].iloc[0] * (1 + cost_rate)
        bh_exit  = df["收盘"].iloc[-1] * (1 - cost_rate)
        bh_return = (bh_exit - bh_entry) / bh_entry
        return bh_return
    
    @staticmethod
    def report(strategy_name, metrics_gross, metrics_net, bh_return):
        print(f"\n{'='*60}")
        print(f"  策略: {strategy_name}")
        print(f"{'='*60}")
        print(f"             总收益    胜率    夏普   卡尔玛   最大回撤")
        print(f"{'-'*60}")
        print(f" 纯策略      {metrics_gross['总收益率']:6.2%}   "
              f"{metrics_gross['胜率']:5.1%}   "
              f"{metrics_gross['夏普']:5.2f}   "
              f"{metrics_gross['卡尔玛']:5.2f}   "
              f"{metrics_gross['最大回撤']:6.1%}")
        print(f" 含成本+止损  {metrics_net['总收益率']:6.2%}   "
              f"{metrics_net['胜率']:5.1%}   "
              f"{metrics_net['夏普']:5.2f}   "
              f"{metrics_net['卡尔玛']:5.2f}   "
              f"{metrics_net['最大回撤']:6.1%}")
        print(f"{'-'*60}")
        print(f" 买入持有    {bh_return:6.2%}")
        print(f"{'='*60}")

