#!/usr/bin/env python3
"""
create_test_data.py — 生成模拟 ETF 行情数据
===============================================
学习目标:
  1. 理解为什么模拟数据需要"交易日历"（跳过周末）
  2. 掌握 OHLC 四价之间的数学约束关系 (High ≥ Open/Close ≥ Low)
  3. 学会用 NumPy 随机数生成符合金融特征的序列
  4. 用 Pandas DataFrame 组装表格并导出 CSV

概念铺垫 (先看这里!):
  - ETF: 交易所交易基金，价格通常在几元到几十元，波动小于个股
  - OHLC: Open(开盘) / High(最高) / Low(最低) / Close(收盘)
  - 随机游走: 价格 = 昨天价格 + 随机扰动，是量化建模的基础假设
  - 对数收益率: r_t = ln(P_t / P_{t-1})，比简单收益率更适合金融建模
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
import os


# ============================================================================
# 第 1 步: 生成交易日序列
# ============================================================================
# 为什么不能直接用 pd.date_range 生成连续日期？
# → 真实市场只在周一到周五交易。如果包含周末，策略回测时会出现
#   "周末价格不动"的假象，影响均线计算和信号生成。
#
# 要理解的概念:
#   date.weekday() 返回值: 0=周一, 1=周二, ... 5=周六, 6=周日

def generate_trading_days(start: date, count: int) -> list:
    """
    从 start 日期开始，向后取 count 个交易日。

    为什么用 while 循环而不是固定步长？
    → 因为每周都要跳过 2 天，无法用统一步长。while 循环逐个检查最直观。

    参数:
        start: 起始日期 (建议选周一，避免第一周就不完整)
        count: 需要的交易日数量
    返回:
        list[date]: 仅包含周一至周五的日期列表
    """
    days = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:  # 周一=0, ..., 周五=4
            days.append(current)
        current += timedelta(days=1)
    return days


# ============================================================================
# 第 2 步: 模拟收盘价 (随机游走模型)
# ============================================================================
# 为什么用"对数收益率"而不是直接用价格加减？
# → 1. 价格不能为负，对数收益率累加后 exp() 还原天然保证正数
#   2. 对数收益率近似等于百分比收益率（在小幅波动时）
#   3. 正态分布假设在对数空间比在价格空间更合理
#
# 模型: log(P_t) = log(P_{t-1}) + ε_t
#   ε_t ~ N(μ, σ²)  即每日对数收益率服从正态分布
#   μ (drift): 日均期望收益，代表趋势方向
#   σ (volatility): 日均波动率，代表随机性大小
#
# 思考题: 如果 μ=0.0002, σ=0.015, 年化收益大约是多少？
#   → μ × 250 ≈ 5% (假设一年250个交易日)

def simulate_close_prices(days: int, start_price: float,
                          annual_return: float = 0.05,
                          annual_volatility: float = 0.24) -> np.ndarray:
    """
    用几何布朗运动 (GBM) 模拟收盘价序列。

    为什么是 GBM？
    → 这是金融学最基础的资产价格模型，Black-Scholes 期权定价也基于它。
      虽然真实市场远比 GBM 复杂（有尖峰厚尾、波动率聚集），
      但作为学习起点足够了——先把简单的搞懂，再学复杂的。

    参数:
        days:            模拟天数
        start_price:     初始价格 (ETF 通常 1~5 元)
        annual_return:   年化收益率 (5% 代表慢牛)
        annual_volatility: 年化波动率 (24% 代表中等波动)
    返回:
        np.ndarray: shape (days,) 的收盘价序列
    """
    # 年化 → 日化转换 (假设 250 个交易日/年)
    # 为什么要√250？因为波动率按标准差的平方根法则缩放
    daily_drift = annual_return / 250
    daily_vol = annual_volatility / np.sqrt(250)

    # 生成对数收益率: 500个独立正态随机数
    # np.random.normal(loc=均值, scale=标准差, size=数量)
    log_returns = np.random.normal(loc=daily_drift, scale=daily_vol, size=days)

    # cumsum: 累加 → 得到对数价格路径
    # 这是随机游走的核心: 下一位置 = 当前位置 + 随机步长
    log_prices = np.log(start_price) + np.cumsum(log_returns)

    # exp 还原为实际价格，round 保留3位小数 (A股最小变动0.001元)
    return np.round(np.exp(log_prices), 3)


# ============================================================================
# 第 3 步: 从收盘价推导 O/H/L 三价
# ============================================================================
# 为什么不是独立生成四个价格？
# → 否则 High 可能小于 Close，这在现实中不可能。O/H/L/C 之间存在
#   严格的数学约束:
#     High  ≥ max(Open, Close)
#     Low   ≤ min(Open, Close)
#     Open  ≈ 昨收 × (1 + 隔夜信息)
#
# 真实日内价格形成逻辑 (帮助你理解):
#   09:25 集合竞价 → 产生开盘价 (市场对隔夜信息的反应)
#   09:30~15:00   → 价格波动，产生最高价和最低价
#   15:00         → 收盘价 (最后3分钟集合竞价)

def derive_ohlc(close: np.ndarray, initial_open: float,
                overnight_vol_ratio: float = 0.4,
                intraday_vol_ratio: float = 0.5) -> tuple:
    """
    基于收盘价反推开盘价、最高价、最低价。

    参数:
        close:                 收盘价序列 (shape: days,)
        initial_open:          第一天的开盘价
        overnight_vol_ratio:   隔夜波动占日波动的比例 (通常更小)
        intraday_vol_ratio:    日内振幅占日波动的比例
    返回:
        (open_prices, high_prices, low_prices) 三个 np.ndarray
    """
    days = len(close)
    daily_vol = 0.015  # 与 simulate_close_prices 中的日波动率对应

    # --- 开盘价: 昨收 + 隔夜跳空 ---
    # 为什么隔夜波动设为日内的一半？
    # → 实证研究发现，隔夜波动通常小于日内波动。
    #   大量信息在交易时段释放，而非休市期间。
    overnight_noise = np.random.normal(0, daily_vol * overnight_vol_ratio, size=days)

    open_prices = np.zeros(days)
    open_prices[0] = initial_open * (1 + overnight_noise[0])
    for i in range(1, days):
        # 今天的开盘 ≈ 昨天收盘 × (1 + 隔夜收益率)
        open_prices[i] = close[i - 1] * (1 + overnight_noise[i])

    open_prices = np.round(open_prices, 3)

    # --- 最高价 & 最低价: 在开盘和收盘的基础上扩展 ---
    # 核心约束:
    #   High = max(Open, Close) × (1 + 上行幅度)   ← 价格在日内最高点
    #   Low  = min(Open, Close) × (1 - 下行幅度)   ← 价格在日内最低点
    #
    # 为什么用 max/min 作为基准？
    # → 如果开盘高于收盘(下跌日)，最低价往往出现在盘中而不是开盘
    #   如果开盘低于收盘(上涨日)，最高价往往在盘中而不是开盘
    #   所以以 "两个端点中较大的那个" 为基准向上扩展才是合理的

    intraday_range = np.abs(
        np.random.normal(0, daily_vol * intraday_vol_ratio, size=days)
    )

    # np.maximum / np.minimum: 逐元素取大/取小，不生成中间数组
    high_prices = np.round(
        np.maximum(open_prices, close) * (1 + intraday_range), 3
    )
    low_prices = np.round(
        np.minimum(open_prices, close) * (1 - intraday_range), 3
    )

    return open_prices, high_prices, low_prices


# ============================================================================
# 第 4 步: 生成成交量
# ============================================================================
# 为什么要让成交量与价格波动相关？
# → 实证规律: 大跌或大涨的日子，成交量通常更大。
#   "价量齐升"涨得稳，"无量空涨"容易跌。
#   这是技术分析中最基本的量价关系。

def simulate_volume(close: np.ndarray) -> np.ndarray:
    """根据涨跌幅生成模拟成交量"""
    days = len(close)

    # 涨跌幅的绝对值 → 波动越大，交投越活跃
    pct_change = np.abs(np.diff(close, prepend=close[0])) / close

    # 对数正态分布噪声 (成交量不能为负，所以不用正态)
    noise = np.random.lognormal(mean=0, sigma=0.6, size=days)

    # 基础量 500万 + 活跃度加成 + 噪声
    volume = 5_000_000 + 30_000_000 * pct_change + (noise * 2_000_000).astype(int)

    # 保底: 即使最冷清的日子也有 50 万成交量
    return np.maximum(volume, 500_000).astype(int)


# ============================================================================
# 主流程
# ============================================================================
if __name__ == "__main__":
    # 设置随机种子 — 每次运行得到相同结果，方便教学对比
    np.random.seed(42)

    # ---- 配置参数 (可以自己改着玩) ----
    DAYS = 500                       # 模拟 500 个交易日 (~2年)
    START_PRICE = 2.50               # ETF 初始价格
    INITIAL_OPEN = 2.50              # 第一天开盘价
    ANNUAL_RETURN = 0.06             # 年化 6% 预期收益
    ANNUAL_VOL = 0.22                # 年化 22% 波动率

    # ---- 执行 ----
    print("=" * 55)
    print("  生成模拟 ETF 行情数据")
    print("=" * 55)

    # Step 1: 交易日历
    trading_days = generate_trading_days(date(2024, 6, 3), DAYS)
    print(f"[1/4] 交易日: {trading_days[0]} ~ {trading_days[-1]} "
          f"(共 {len(trading_days)} 天)")

    # Step 2: 收盘价
    close = simulate_close_prices(DAYS, START_PRICE, ANNUAL_RETURN, ANNUAL_VOL)
    print(f"[2/4] 收盘价: {close[0]} → {close[-1]:.3f} "
          f"(涨跌幅 {(close[-1]/close[0]-1)*100:.1f}%)")

    # Step 3: OHLC
    open_p, high_p, low_p = derive_ohlc(close, INITIAL_OPEN)
    print(f"[3/4] 四价生成完毕")

    # Step 4: 成交量
    volume = simulate_volume(close)
    print(f"[4/4] 成交量: 均值 {volume.mean():,.0f}, 范围 [{volume.min():,}, {volume.max():,}]")

    # ---- 组装 DataFrame ----
    df = pd.DataFrame({
        "日期":   trading_days,
        "开盘":   open_p,
        "最高":   high_p,
        "最低":   low_p,
        "收盘":   close,
        "成交量": volume,
    })

    # ---- 数据完整性校验 ----
    # 这是写数据代码的必备习惯: 永远不要相信"肉眼看起来没错"
    ok_high = (df["最高"] >= df[["开盘", "收盘"]].max(axis=1)).all()
    ok_low  = (df["最低"] <= df[["开盘", "收盘"]].min(axis=1)).all()
    ok_hl   = (df["最高"] >= df["最低"]).all()

    if ok_high and ok_low and ok_hl:
        print("\n[OK] OHLC 约束校验通过 (High>=O/C>=Low)")
    else:
        print(f"\n[FAIL] 校验失败! High={ok_high}, Low={ok_low}, H>=L={ok_hl}")
        raise ValueError("数据不满足 OHLC 约束！")

    # ---- 保存 ----
    os.makedirs("data", exist_ok=True)
    output_path = "data/test_etf.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"[OK] 已保存: {output_path}  ({len(df)}行 x {len(df.columns)}列)")

    # ---- 预览 ----
    print("\n" + "-" * 55)
    print("前 5 行预览:")
    print("-" * 55)
    print(df.head().to_string(index=False))

    print("\n" + "-" * 55)
    print("后 3 行预览:")
    print("-" * 55)
    print(df.tail(3).to_string(index=False))
