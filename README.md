# Quant Learning — 量化交易研究框架

从零搭建的量化策略研究平台。支持向量化回测与事件驱动回测，已完成向 Backtrader 和 MiniQMT 的架构迁移准备。

---

## 项目结构

```
quant_learning/
│
├── main.py                          # 调度入口  python main.py --exp 1~6
├── config/settings.py               # 统一配置（ETF列表、参数、引擎实例）
├── requirements.txt
├── README.md
│
├── data/                            # 数据层
│   └── DataLoader.py                #   统一数据加载（CSV / 券商xls）
│
├── strategy/                        # 策略层（纯算法，平台无关）
│   ├── MACrossLogic.py              #   双均线信号算法（Backtrader/QMT共用）
│   ├── MACrossStrategy.py           #   向量化版双均线交叉
│   ├── RSIStrategy.py               #   RSI超买超卖
│   ├── RegimeDetector.py            #   市场状态识别（Efficiency Ratio）
│   └── StrategySelector.py          #   策略切换（ER→MA / ER→RSI）
│
├── backtest/                        # 向量化回测引擎
│   └── BacktestEngine.py            #   撮合、止损、成本、仓位缩放
│
├── risk/                            # 风险管理（纯Python，平台无关）
│   ├── RiskGate.py                  #   风控门：RiskContext/RiskResult/RiskRule/RiskGate
│   │                                #   内置 4 条规则 + ContextBuilder 抽象
│   └── PositionSizer.py             #   仓位管理：Fixed/FixedRisk/Volatility
│
├── adapter/                         # 交易平台适配器（每平台一个子目录）
│   ├── broker_gateway.py            #   券商网关抽象接口（BrokerGateway ABC）
│   ├── mock_broker.py               #   Mock 券商（架构验证用）
│   └── qmt/
│       └── MACrossQMT.py            #   MiniQMT 适配器（Logic→RiskGate→Broker）
│
├── portfolio/                       # 投资组合
│   ├── PortfolioEngine.py           #   多资产组合合成 + 净值追踪
│   └── Rebalancer.py                #   月度/季度/阈值再平衡 + 成本计算
│
├── analysis/                        # 绩效分析
│   └── PerformanceAnalyzer.py       #   7指标（收益、胜率、夏普、卡尔玛、回撤）
│
├── experiments/                     # 独立实验（每个可单独运行）
│   ├── exp01_smoke_test.py          #   模拟数据冒烟测试
│   ├── exp02_sizer_comparison.py    #   真实ETF仓位管理对比
│   ├── exp03_portfolio.py           #   等权投资组合
│   ├── exp04_rebalancing.py         #   再平衡方式对比
│   ├── exp05_backtrader_ma.py       #   Backtrader 事件驱动回测
│   └── exp06_qmt_verify.py          #   QMT 适配器架构验证
│
├── config/                          # 统一配置
│   └── settings.py
│
├── research/                        # 研究结论存档
│   ├── StrategyResearchTemplate.md
│   └── run_results.txt
│
└── scripts/                         # 数据工具
    ├── create_test_data.py
    └── fetch_etf_data.py
```

---

## 快速开始

```bash
pip install -r requirements.txt

python main.py              # 查看实验菜单
python main.py --exp 1      # 跑冒烟测试
python main.py --exp 5      # Backtrader 回测
python main.py --exp 6      # QMT 架构验证
python main.py --exp all    # 全量 + 自动存档 research/
```

---

## 三层架构 (HAL Pattern)

平台无关代码占总量的 70%，平台相关代码只占 30%。

```
┌──────────────────────────────────────┐
│         MACrossLogic (信号算法)        │  ← 平台无关
│         RiskGate (风控门)             │  ← 平台无关
├──────────────────────────────────────┤
│  MACrossBT / MACrossQMT  (适配器)     │  ← 平台相关
│  BtContextBuilder / QmtContextBuilder │  ← 平台相关
├──────────────────────────────────────┤
│  Backtrader / MockBroker / MiniQMT   │  ← 平台相关
└──────────────────────────────────────┘
```

| 操作 | 改动范围 |
|------|------|
| 换策略逻辑 | 只改 MACrossLogic |
| 加风控规则 | `gate.add_rule(NewRule())` 一行 |
| 换交易平台 | 新建 Adapter + ContextBuilder |
| 换券商 | 新建 BrokerGateway 实现类 |

---

## 已实现的策略

| 策略 | 类型 | 信号逻辑 | 适用市场 |
|------|------|---------|------|
| MACrossLogic(5,20) | 趋势跟踪 | MA5 上穿 MA20 → buy | ER > 0.6 趋势市 |
| RSIStrategy(14,30,70) | 均值回归 | RSI 上穿 30 → buy | ER < 0.3 震荡市 |
| StrategySelector | 状态切换 | ER 高→MA, ER低→RSI | 全市场 |

---

## 风险管理

### PositionSizer（仓位管理）

| Sizer | 逻辑 | 适用场景 |
|------|------|------|
| FixedPositionSizer(0.6) | 固定 60% 仓位 | 最简单 |
| FixedRiskSizer(0.02, 0.03) | 每笔最多亏 2% | 严格风控 |
| VolatilitySizer | 波动大→自动降仓 | 自适应 |

### RiskGate（风控门）

策略信号必须通过风控门才能下单。内置 4 条规则：

| 规则 | 拦截条件 |
|------|------|
| PositionLimitRule | 单策略仓位 > 30% |
| DailyLossRule | 当日累计亏损 > 5% |
| ConsecutiveLossRule | 连续亏损 ≥ 3 笔 |
| MarketStatusRule | 涨停/跌停/非交易时段 |

新增规则 = 继承 `RiskRule`，实现 `check(context)`，一行 `gate.add_rule()` 注册。

---

## 绩效指标

| 指标 | 含义 |
|------|------|
| 总收益率 | 复利累乘 |
| 胜率 | 盈利交易占比 |
| 夏普比率 | 每单位波动换取的超额收益 |
| 卡尔玛比率 | 每单位回撤换取的收益 |
| 最大回撤 | 峰值到谷底的最大跌幅 |

---

## 核心研究结论

> 详见 `research/StrategyResearchTemplate.md`

1. **不存在长期有效的单一策略** — MA 在趋势市跑赢 RSI，震荡市反之
2. **训练集最优 ≠ 未来最优** — 时间切分后排名反转
3. **Efficiency Ratio 能预测策略胜负** — 但 ER(50) 滞后 30 天，无法切换
4. **仓位管理不改变策略质量** — 只缩放风险敞口
5. **四只 A 股 ETF 走势高度同质** — ER 加权和再平衡未产生 alpha
6. **平台无关架构可行** — 290 行 Logic + Risk 代码被 Backtrader 和 QMT 复用

---

## 研究方法论

1. **获取多份数据集** — 单一数据上的结论不可推广
2. **时间切分（Train/Test）** — 杜绝过拟合
3. **跨标的验证** — 排除幸存者偏差
4. **不同时间切片回测** — 最严格的过拟合检测
5. **与买入持有对比** — 择时不如死拿时，承认策略无效

---

## 开发环境

- Python 3.11+
- 核心：pandas, numpy, backtrader
- 可选：akshare, matplotlib
