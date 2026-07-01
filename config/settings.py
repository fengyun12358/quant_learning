"""
统一配置文件 — 所有实验共享
============================
修改参数只需改这里，不用每个实验脚本各改一遍。
"""

from backtest.BacktestEngine import BacktestEngine
from analysis.PerformanceAnalyzer import PerformanceAnalyzer

# ===== ETF 数据清单 =====
ETF_FILES = {
    "510330 沪深300": "data/510330.xls",
    "510500 中证500": "data/510500.xls",
    "588000 科创50":  "data/588000.xls",
    "513100 纳指":    "data/513100.xls",
}

# ===== 策略默认参数 =====
MA_SHORT = 5
MA_LONG = 20
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
STOP_PCT = 0.03

# ===== 仓位管理默认参数 =====
FIXED_RATIO = 0.6
RISK_PER_TRADE = 0.02
VOL_WINDOW = 20
VOL_MULTIPLE = 2.0

# ===== 组合默认参数 =====
PORTFOLIO_WEIGHTS = {
    "510330 沪深300": 0.25,
    "510500 中证500": 0.25,
    "588000 科创50":  0.25,
    "513100 纳指":    0.25,
}

# ===== 交易成本 =====
COST_RATE = 0.0011           # 单边 0.11% (佣金万1 + 滑点 0.1%)
RISK_FREE_RATE = 0.02        # 无风险利率 2%

# ===== 全局复用的引擎 & 分析器 =====
engine_raw = BacktestEngine(cost_rate=0)           # 纯策略
engine_real = BacktestEngine(cost_rate=COST_RATE)  # 含成本+止损
analyzer = PerformanceAnalyzer()
