"""
MonitorContext — 系统状态快照
=============================
Monitor 只读此结构，不访问任何系统内部对象。
"""

from dataclasses import dataclass, field


@dataclass
class MonitorContext:
    """系统当前状态的只读快照。所有字段有默认值，便于构造。"""

    # 连接状态
    broker_connected: bool = True
    broker_last_heartbeat: float = 0.0   # time.time() 的时间戳

    # 订单状态
    pending_order_count: int = 0
    oldest_pending_seconds: float = 0.0
    total_orders_today: int = 0

    # 风控状态
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    is_risk_halted: bool = False

    # 持久化状态
    db_writable: bool = True
    db_disk_free_mb: float = 1000.0
    db_write_fail_count: int = 0

    # 系统状态
    uptime_seconds: float = 0.0

    # 行情状态
    last_bar_time: str = ""
    seconds_since_last_bar: float = 0.0
