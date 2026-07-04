# Quant Learning — 量化交易系统

从零搭建的量化交易平台。双引擎（向量化 + 事件驱动），三层架构（Logic / Adapter / Broker），完整基础设施。

**当前阶段：基础设施就绪，待接入 MiniQMT 仿真盘。**

---

## 系统流水线

```
MarketData (CSV 回放 / 未来 MiniQMT)
    ↓
MACrossLogic (纯信号, 平台无关)
    ↓
RiskGate (4 条风控规则)
    ↓
OrderManager (订单生命周期, 超时重试, 串行队列)
    ↓
SQLitePersistence (3 张表, Broker Reconcile)
    ↓                    ↓
MonitorCenter (5 条监控)    BrokerGateway
    ↓                       ├── MockBroker (立即成交)
PaperPortfolio              ├── PaperBroker (延迟/滑点/部分成交)
                            └── MiniQMTGateway (仿真盘, 设计完成)
```

---

## 项目结构

```
quant_learning/
│
├── main.py                          # 调度入口  python main.py --exp 1~6
├── config/settings.py               # 统一配置
├── README.md
│
├── strategy/                        # 策略层（纯算法, 平台无关）
│   ├── MACrossLogic.py              #   双均线信号 (Backtrader/QMT 共用同一份)
│   ├── MACrossStrategy.py           #   向量化版 (委托 MACrossLogic)
│   ├── RSIStrategy.py               #   RSI 超买超卖
│   ├── RegimeDetector.py            #   市场状态识别 (Efficiency Ratio)
│   └── StrategySelector.py          #   策略切换
│
├── risk/                            # 风控 + 订单 + 持久化 (纯 Python, 平台无关)
│   ├── RiskGate.py                  #   风控门: RiskContext/RiskResult/4 Rules + ContextBuilder
│   ├── PositionSizer.py             #   仓位管理: Fixed/FixedRisk/Volatility
│   ├── OrderManager.py              #   订单生命周期: 7 种状态, 超时重试, 串行队列
│   └── SQLitePersistence.py         #   positions/orders/risk_state 3 表 + Broker Reconcile
│
├── monitor/                         # 监控中心 (只读, 不修改系统状态)
│   ├── MonitorCenter.py             #   协调器: add() + check_all()
│   ├── MonitorContext.py            #   系统快照 (12 字段)
│   ├── MonitorResult.py             #   4 级 Severity + suggested_action
│   └── monitors/
│       ├── BrokerHeartbeatMonitor.py
│       ├── OrderTimeoutMonitor.py
│       ├── ConsecutiveLossMonitor.py
│       ├── DailyLossMonitor.py
│       └── PersistenceMonitor.py
│
├── adapter/                         # 交易平台适配器
│   ├── broker_gateway.py            #   BrokerGateway ABC
│   ├── mock_broker.py               #   Mock 券商 (立即成交)
│   └── qmt/
│       └── MACrossQMT.py            #   QMT 适配器
│
├── paper/                           # Paper Trading (模拟真实撮合)
│   ├── PaperBroker.py               #   事件驱动延迟 + 随机滑点 + 部分成交
│   ├── PaperMarketDataFeed.py       #   CSV 逐行推送 K 线
│   ├── PaperPortfolio.py            #   净值追踪 (cash/market_value/drawdown)
│   ├── ReplayEngine.py              #   回放引擎 (串联全系统)
│   └── SlippageModel.py             #   滑点模型 (RandomSlippage / NoSlippage)
│
├── portfolio/                       # 投资组合
│   ├── PortfolioEngine.py           #   多资产组合 + 净值追踪
│   └── Rebalancer.py                #   月度/阈值再平衡
│
├── backtest/                        # 向量化回测
│   └── BacktestEngine.py
│
├── analysis/                        # 绩效分析
│   └── PerformanceAnalyzer.py       #   7 指标
│
├── tests/                           # 压力测试
│   └── stress_test_suite.py         #   6 场景 (马拉松/断连/磁盘/洪水/内存/对账)
│
├── experiments/                     # 独立实验
│   ├── exp01_smoke_test.py
│   ├── exp02_sizer_comparison.py
│   ├── exp03_portfolio.py
│   ├── exp04_rebalancing.py
│   ├── exp05_backtrader_ma.py
│   └── exp06_qmt_verify.py
│
├── research/                        # 研究存档
├── scripts/                         # 数据工具
└── config/
```

---

## 快速开始

```bash
pip install -r requirements.txt

python main.py                # 菜单
python main.py --exp 1        # 冒烟测试
python main.py --exp all      # 全量 + 自动存档
python tests/stress_test_suite.py    # 压力测试
python tests/stress_test_suite.py --quick  # 快速模式
```

---

## 基础设施模块

### OrderManager

| 状态 | 含义 |
|------|------|
| CREATED → PENDING → FILLED | 正常成交 |
| PENDING → TIMEOUT → 重试 | 超时自动重试 (默认 5s × 2 次) |
| PENDING → REJECTED | 被券商拒单 |
| 串行保证 | 同一标的前一单未完成, 后一单排队 |

### SQLitePersistence

3 张表: `positions(strategy_id, symbol)`, `orders`, `risk_state(scope, key, value)`.
支持 Broker Reconcile: 券商为 Source of Truth, 本地自动同步。UTC ISO8601 时间。

### MonitorCenter

5 条监控规则。新增 = 继承 `Monitor`, 一行 `add()`。默认只返回非 INFO 告警。

### PaperBroker

事件驱动撮合 (不阻塞主循环), 随机滑点 ±0.3%, 10% 概率部分成交, 涨跌停拒单。

---

## Stress Test Suite — 6/6 PASS

| # | 测试 | 指标 | 结果 |
|---|------|------|:---:|
| 1 | Marathon | 10,000 bar 连续运行 | PASS |
| 2 | Broker Disconnect | 45 次断连恢复 | PASS |
| 3 | SQLite Failure | 16 次磁盘故障注入 | PASS |
| 4 | Order Flood | 4,000 笔订单洪水 | PASS |
| 5 | Memory Leak | 100 轮循环 | PASS |
| 6 | State Consistency | 100 次随机对账 | PASS |

---

## 三层架构 (HAL Pattern)

```
┌──────────────────────────────────────┐
│  MACrossLogic (信号算法)              │  ← 平台无关
│  RiskGate + RiskRule (风控)          │  ← 平台无关
│  OrderManager (订单管理)              │  ← 平台无关
│  MonitorCenter (监控)                │  ← 平台无关
├──────────────────────────────────────┤
│  MACrossBT / MACrossQMT (适配器)      │  ← 平台适配
│  ContextBuilder (状态翻译)            │  ← 平台适配
├──────────────────────────────────────┤
│  Mock / Paper / MiniQMT Broker       │  ← 券商实现
│  Backtrader / CSV Replay             │  ← 数据源
└──────────────────────────────────────┘
```

| 操作 | 改动范围 |
|------|------|
| 换策略 | 只改 MACrossLogic |
| 加风控 | `gate.add_rule(NewRule())` |
| 加监控 | `monitor.add(NewMonitor())` |
| 换平台 | 新建 Adapter + ContextBuilder |
| 换券商 | 新建 BrokerGateway 实现类 |

---

## 核心结论

1. **不存在长期有效的单一策略** — MA 在趋势市跑赢 RSI, 震荡市反之
2. **训练集最优 ≠ 未来最优** — 时间切分后排名反转
3. **仓位管理不改变策略质量** — 只缩放风险敞口
4. **策略失败是有效数据** — 证伪一个假设 = 排除一条死胡同
5. **三层架构可行** — 平台无关代码 ~70%, 平台相关 ~30%

---

## 开发环境

- Python 3.11+
- 核心: pandas, numpy, backtrader
- MiniQMT: xtquant (待安装)
- 测试: pytest (可选)
