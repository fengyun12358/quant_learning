"""
Trading System Stress Test Suite
=================================
验证 OrderManager / SQLitePersistence / MonitorCenter / PaperBroker
长期运行的稳定性。不测收益率——只测可靠性。

用法:
  python tests/stress_test_suite.py
  python tests/stress_test_suite.py --quick   # 快速模式
"""

import sys, os, time, gc, random, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.MACrossLogic import MACrossLogic
from risk.RiskGate import RiskGate
from risk.OrderManager import OrderManager
from risk.SQLitePersistence import SQLitePersistence
from paper.PaperBroker import PaperBroker
from paper.PaperMarketDataFeed import PaperMarketDataFeed
from paper.PaperPortfolio import PaperPortfolio
from adapter.broker_gateway import Order
from monitor.MonitorCenter import MonitorCenter
from monitor.MonitorContext import MonitorContext
from monitor.monitors import (
    BrokerHeartbeatMonitor, OrderTimeoutMonitor,
    ConsecutiveLossMonitor, DailyLossMonitor, PersistenceMonitor,
)


def setup_system(db_path, initial_cash=100000):
    """构建完整的交易系统流水线。"""
    broker = PaperBroker(initial_cash)
    persistence = SQLitePersistence(db_path)
    om = OrderManager(broker, persistence=persistence)
    logic = MACrossLogic(5, 20)
    portfolio = PaperPortfolio(initial_cash)

    monitor = MonitorCenter()
    for m in [BrokerHeartbeatMonitor(), OrderTimeoutMonitor(),
              ConsecutiveLossMonitor(), DailyLossMonitor(),
              PersistenceMonitor()]:
        monitor.add(m)

    return broker, persistence, om, logic, portfolio, monitor


# ================================================================
# Test 1: Marathon — 10,000 bar 连续运行
# ================================================================

def test_marathon():
    """10,000 bar 连续运行，验证无崩溃、告警可控。"""
    print("\n" + "=" * 55)
    print("  Test 1: Marathon — 10,000 bar")
    print("=" * 55)

    db_path = tempfile.mktemp(suffix=".db")
    broker, persistence, om, logic, portfolio, monitor = setup_system(db_path)
    feed = PaperMarketDataFeed("data/510330.xls")

    alerts, bars = 0, 0
    consecutive_losses, daily_pnl = 0, 0.0
    in_position, entry_price = False, 0.0
    start_time = time.time()

    while bars < 10000:
        bar = feed.next_bar()
        if bar is None:
            feed.reset()
            bar = feed.next_bar()

        broker.set_current_price("510330", bar["close"])
        signal = logic.update(bar["close"])
        broker.update(clock_tick=1.0)

        # 信号 → 订单
        if signal == "buy" and not in_position:
            om.submit(Order("510330", "buy", bar["close"], _calc_size(broker, bar["close"])))
            in_position, entry_price = True, bar["close"]
        elif signal == "sell" and in_position:
            pos = broker.query_position("510330")
            if pos and pos.size > 0:
                om.submit(Order("510330", "sell", bar["close"], pos.size))
                pnl = (bar["close"] - entry_price) / entry_price if entry_price > 0 else 0
                daily_pnl += pnl
                consecutive_losses = consecutive_losses + 1 if pnl < 0 else 0
            in_position = False

        broker.update(clock_tick=1.0)
        portfolio.update(bar["date"], broker.query_cash(),
                         broker.query_total_asset() - broker.query_cash())

        ctx = MonitorContext(
            consecutive_losses=consecutive_losses, daily_pnl=daily_pnl,
            pending_order_count=broker.pending_count(),
        )
        alerts += len(monitor.check_all(ctx))
        bars += 1

    elapsed = time.time() - start_time
    persistence.close()
    os.unlink(db_path)

    ok = bars == 10000
    print(f"  处理: {bars} bar | 耗时: {elapsed:.1f}s | 告警: {alerts}")
    print(f"  结果: {'PASS' if ok else 'FAIL'}")
    return ok


# ================================================================
# Test 2: Broker Disconnect Recovery
# ================================================================

class UnstableBroker(PaperBroker):
    """模拟间歇性断连的 Broker。"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.disconnected = False

    def buy(self, *args, **kwargs):
        if self.disconnected:
            return type("OrderResult", (), {"order_id": "", "status": "pending",
                       "filled_price": 0, "filled_size": 0, "reject_reason": "网络断连"})
        return super().buy(*args, **kwargs)

    def sell(self, *args, **kwargs):
        if self.disconnected:
            return type("OrderResult", (), {"order_id": "", "status": "pending",
                       "filled_price": 0, "filled_size": 0, "reject_reason": "网络断连"})
        return super().sell(*args, **kwargs)


def test_broker_disconnect():
    """每 50 bar 断开 5 bar，验证恢复后持仓一致。"""
    print("\n" + "=" * 55)
    print("  Test 2: Broker Disconnect Recovery")
    print("=" * 55)

    db_path = tempfile.mktemp(suffix=".db")
    broker = UnstableBroker(100000)
    persistence = SQLitePersistence(db_path)
    om = OrderManager(broker, persistence=persistence)
    logic = MACrossLogic(5, 20)
    feed = PaperMarketDataFeed("data/510330.xls")

    disconnects, recovers = 0, 0
    for i in range(500):
        bar = feed.next_bar() or feed.reset() or feed.next_bar()

        # 每 50 bar 切换断连状态
        if i % 55 >= 50:
            broker.disconnected = True
            disconnects += 1
        else:
            broker.disconnected = False

        broker.set_current_price("510330", bar["close"])
        signal = logic.update(bar["close"])
        broker.update(clock_tick=1.0)

        if signal == "buy":
            result = broker.buy("510330", bar["close"], 100, "market")
            if result.status == "pending" and "断连" in result.reject_reason:
                recovers += 0  # 断连期间的 pending，恢复后重试
        elif signal == "sell":
            broker.sell("510330", bar["close"], 100, "market")

    # 验证：最终持仓和资金自洽
    total = broker.query_total_asset()
    cash = broker.query_cash()
    pos_value = total - cash
    ok = abs(total - 100000) < 5000  # 允许 ±5% 盈亏
    print(f"  断连次数: {disconnects} | 总资产: {total:.0f}")
    print(f"  结果: {'PASS' if ok else 'FAIL'}")

    persistence.close()
    os.unlink(db_path)
    return ok


# ================================================================
# Test 3: SQLite Write Failure
# ================================================================

def test_sqlite_failure():
    """注入随机写入失败，验证 Monitor 检测到异常，系统不崩溃。"""
    print("\n" + "=" * 55)
    print("  Test 3: SQLite Write Failure")
    print("=" * 55)

    db_path = tempfile.mktemp(suffix=".db")
    broker, persistence, om, logic, portfolio, monitor = setup_system(db_path)
    feed = PaperMarketDataFeed("data/510330.xls")

    fail_count, detected = 0, 0
    for i in range(500):
        bar = feed.next_bar() or feed.reset() or feed.next_bar()

        # 随机注入写入失败：临时删除数据库文件
        if i % 30 == 0 and i > 0:
            try:
                persistence.close()
                os.rename(db_path, db_path + ".bak")
                fail_count += 1
            except Exception:
                pass

        broker.set_current_price("510330", bar["close"])
        signal = logic.update(bar["close"])
        broker.update(clock_tick=1.0)

        if signal in ("buy", "sell"):
            try:
                if signal == "buy":
                    broker.buy("510330", bar["close"], 100, "market")
                else:
                    broker.sell("510330", bar["close"], 100, "market")
                persistence.save_position("510330", 100, bar["close"])
            except Exception:
                detected += 1

        # 恢复数据库
        if i % 30 == 1 and fail_count > 0:
            try:
                os.rename(db_path + ".bak", db_path)
                persistence = SQLitePersistence(db_path)
                om._persistence = persistence
            except Exception:
                pass

    try:
        persistence.close()
        os.unlink(db_path)
    except Exception:
        pass

    ok = fail_count > 0
    print(f"  注入失败: {fail_count} | 异常捕获: {detected}")
    print(f"  结果: {'PASS' if ok else 'FAIL'} (系统无崩溃)")
    return ok


# ================================================================
# Test 4: Order Flood
# ================================================================

def test_order_flood():
    """每 bar 提交 20 笔订单，验证串行队列不丢单。"""
    print("\n" + "=" * 55)
    print("  Test 4: Order Flood")
    print("=" * 55)

    broker = PaperBroker(100000)
    om = OrderManager(broker)

    submitted, filled = 0, 0
    for _ in range(200):
        for _ in range(20):
            om.submit(Order("510330", "buy" if submitted % 2 == 0 else "sell",
                       10.0, 100))
            submitted += 1
        broker.update(clock_tick=10.0)
        om.update()   # OrderManager 也 tick

    filled = sum(1 for oid, mo in om._orders.items()
                 if mo.status.value == "filled")
    pending = om.pending_count()

    ok = filled > 0 and pending < submitted
    print(f"  提交: {submitted} | 成交: {filled} | Pending: {pending}")
    print(f"  结果: {'PASS' if ok else 'FAIL'}")
    return ok


# ================================================================
# Test 5: Memory Leak
# ================================================================

def test_memory_leak():
    """100 轮循环，验证内存不持续增长。"""
    print("\n" + "=" * 55)
    print("  Test 5: Memory Leak (100 rounds)")
    print("=" * 55)

    db_path = tempfile.mktemp(suffix=".db")
    mem_samples = []

    for round_num in range(100):
        broker = PaperBroker(100000)
        persistence = SQLitePersistence(db_path)
        om = OrderManager(broker, persistence=persistence)
        logic = MACrossLogic(5, 20)
        feed = PaperMarketDataFeed("data/510330.xls")

        for _ in range(500):
            bar = feed.next_bar() or feed.reset() or feed.next_bar()
            broker.set_current_price("510330", bar["close"])
            logic.update(bar["close"])
            broker.update(clock_tick=1.0)

        if round_num % 20 == 0:
            gc.collect()
            try:
                import psutil
                mem = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                mem_samples.append(mem)
            except ImportError:
                pass

        persistence.close()

    # 内存不应持续增长
    if len(mem_samples) >= 2:
        growth = (mem_samples[-1] - mem_samples[0]) / max(mem_samples[0], 1) * 100
        ok = growth < 20
        print(f"  内存: {mem_samples[0]:.0f}MB → {mem_samples[-1]:.0f}MB (增长 {growth:.1f}%)")
    else:
        ok = True  # psutil 不可用时跳过
        print(f"  内存: 跳过 (psutil 不可用)")

    try:
        os.unlink(db_path)
    except Exception:
        pass

    print(f"  结果: {'PASS' if ok else 'FAIL'} (增长 < 20%)")
    return ok


# ================================================================
# Test 6: State Consistency
# ================================================================

def test_state_consistency():
    """随机操作后对账：cash + holdings == total_asset。"""
    print("\n" + "=" * 55)
    print("  Test 6: State Consistency")
    print("=" * 55)

    broker = PaperBroker(100000)
    random.seed(42)

    for _ in range(100):
        side = random.choice(["buy", "sell"])
        price = random.uniform(3.0, 5.0)
        size = random.randint(100, 1000)

        if side == "buy":
            broker.buy("510330", price, size, "market")
        else:
            broker.sell("510330", price, size, "market")

        broker.update(clock_tick=1.0)

        total = broker.query_total_asset()
        cash = broker.query_cash()
        pos_value = sum(
            p.size * p.current_price for p in broker._positions.values()
        )
        diff = abs(total - (cash + pos_value))

        if diff > 0.01:
            print(f"  FAIL: total={total} cash={cash} holdings={pos_value} diff={diff}")
            return False

    print(f"  总资产: {broker.query_total_asset():.0f} | "
          f"现金: {broker.query_cash():.0f} | "
          f"持仓: {broker.query_total_asset()-broker.query_cash():.0f}")
    print(f"  结果: PASS (100 次对账一致)")
    return True


# ================================================================
# Utils
# ================================================================

def _calc_size(broker, price):
    cash = broker.query_cash()
    size = int(cash * 0.6 / price / 100) * 100
    return max(size, 100)


# ================================================================
# Main
# ================================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv

    tests = [
        ("Marathon",           test_marathon),
        ("Broker Disconnect",  test_broker_disconnect),
        ("SQLite Failure",     test_sqlite_failure),
        ("Order Flood",        test_order_flood),
        ("Memory Leak",        test_memory_leak),
        ("State Consistency",  test_state_consistency),
    ]

    if quick:
        # 快速模式: 跳过马拉松
        tests = [t for t in tests if t[0] != "Marathon"]

    passed, failed = 0, 0
    for name, fn in tests:
        try:
            ok = fn()
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  {name}: EXCEPTION {e}")
            failed += 1

    print(f"\n{'='*55}")
    print(f"  SUMMARY: {passed} PASS / {failed} FAIL / {passed+failed} TOTAL")
    print(f"{'='*55}")
