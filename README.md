# Quant Learning — 量化交易研究框架

从零搭建的量化策略研究平台，支持数据加载、策略开发、回测引擎、仓位管理、投资组合、再平衡和绩效分析。已完成 **MA 趋势跟踪** 和 **RSI 均值回归** 两类策略，在 **4 只真实 ETF** 上进行了回测验证。

---

## 项目结构

```
quant_learning/
│
├── main.py                          # 调度入口  python main.py --exp 1~4
├── config/settings.py               # 统一配置（ETF列表、参数、引擎实例）
├── requirements.txt                 # 依赖
├── README.md
│
├── data/                            # 数据层
│   ├── DataLoader.py                #   统一数据加载（CSV / 券商xls）
│   ├── test_etf.csv                 #   模拟数据（500条，随机游走）
│   ├── 510330.xls                   #   沪深300ETF 真实数据
│   ├── 510500.xls                   #   中证500ETF
│   ├── 588000.xls                   #   科创50ETF
│   └── 513100.xls                   #   纳指ETF
│
├── strategy/                        # 策略层
│   ├── MACrossStrategy.py           #   双均线交叉（趋势跟踪）
│   ├── RSIStrategy.py               #   RSI超买超卖（均值回归）
│   ├── RegimeDetector.py            #   市场状态识别（Efficiency Ratio）
│   └── StrategySelector.py          #   策略切换（ER→MA / ER→RSI）
│
├── backtest/                        # 回测引擎
│   └── BacktestEngine.py            #   撮合、止损、成本、仓位缩放
│
├── risk/                            # 仓位管理
│   └── PositionSizer.py             #   FixedPosition / FixedRisk / Volatility
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
│   └── exp04_rebalancing.py         #   再平衡方式对比
│
├── config/                          # 统一配置
│   └── settings.py                  #   ETF列表、默认参数、复用引擎实例
│
├── research/                        # 研究结论存档
│   ├── StrategyResearchTemplate.md  #   策略研究模板（假设→验证→结论）
│   └── run_results.txt              #   最近一次全量实验结果
│
└── scripts/                         # 数据工具
    ├── create_test_data.py          #   生成模拟ETF数据
    └── fetch_etf_data.py            #   拉取真实ETF数据（akshare）
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 跑冒烟测试

```bash
python main.py --exp 1
```

### 3. 跑全部实验

```bash
python main.py --exp all
```

结果自动保存到 `research/run_results.txt`。

### 4. 单独调试某个实验

```bash
python experiments/exp01_smoke_test.py
```

每个实验脚本首行 `sys.path.insert(...)` 保证了从任意目录运行都能正确导入模块。

---

## 已实现的策略

| 策略 | 类型 | 信号逻辑 | 市场适用 |
|------|------|---------|------|
| MACrossStrategy(5,20) | 趋势跟踪 | MA5 上穿 MA20 → 买入 | ER > 0.6 的趋势市 |
| RSIStrategy(14,30,70) | 均值回归 | RSI 上穿 30 → 买入 | ER < 0.3 的震荡市 |
| StrategySelector | 状态切换 | ER 高→MA, ER低→RSI | 全市场 |

---

## 仓位管理

| Sizer | 逻辑 | 适用场景 |
|------|------|------|
| FixedPositionSizer(0.6) | 固定 60% 仓位 | 最简单，永不变 |
| FixedRiskSizer(0.02, 0.03) | 每笔最多亏 2% | 严格风控 |
| VolatilitySizer(0.02, 2.0, 20) | 波动大→自动降仓 | 自适应市场 |

---

## 绩效指标

`PerformanceAnalyzer` 输出 7 项指标：

| 指标 | 含义 |
|------|------|
| 总收益率 | 复利累乘 |
| 胜率 | 盈利交易占比 |
| 最大盈利 / 最大亏损 | 单笔极值 |
| 夏普比率 | 每单位波动换取的超额收益 |
| 卡尔玛比率 | 每单位回撤换取的收益 |
| 最大回撤 | 峰值到谷底的最大跌幅 |

---

## 核心研究结论

> 详见 `research/StrategyResearchTemplate.md`

1. **不存在长期有效的单一策略** — MA 在趋势市跑赢 RSI，震荡市反之
2. **训练集最优 ≠ 未来最优** — 时间切分后排名反转
3. **Efficiency Ratio 能预测策略胜负** — 但 ER(50) 滞后 30 天，无法实时切换
4. **仓位管理不改变策略质量** — 只缩放风险敞口
5. **四只 A 股 ETF 走势高度同质** — ER 加权和再平衡未产生显著 alpha
6. **"策略失败"是有效数据** — 证伪一个假设 = 排除一条死胡同

---

## 研究方法论

每个新策略想法按以下 5 步验证：

1. **获取多份数据集** — 单一数据上的结论不可推广
2. **时间切分（Train/Test）** — 杜绝过拟合
3. **跨标的验证** — 排除幸存者偏差
4. **不同时间切片回测** — 最严格的过拟合检测
5. **与买入持有对比** — 择时如果用更少的精力赚更少的钱，不如不动

---

## 架构设计原则

| 原则 | 实现 |
|------|------|
| 策略与引擎解耦 | 策略产出 `buy_signal/sell_signal`，引擎不关心来源 |
| 统一接口 | 所有策略遵循 `fit(df) → df` |
| 实验隔离 | 每个实验独立脚本，互不影响 |
| 配置集中 | `config/settings.py` 一处修改，全局生效 |
| 可扩展 | 新增实验只需新建文件 + 在 main.py 注册一行 |
| Backtrader 兼容 | 策略逻辑不变，换壳即可接入事件驱动引擎 |

---

## 开发环境

- Python 3.11+
- Windows 11 / macOS / Linux
- 依赖：pandas, numpy, pillow（可选：akshare, matplotlib）
