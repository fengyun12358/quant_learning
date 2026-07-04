"""
SQLitePersistence — 状态持久化层
=================================
平台无关。不依赖 Backtrader / MiniQMT。

三张表: positions / orders / risk_state
时间格式: UTC ISO8601 (2026-07-04T12:35:21Z)
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from risk.OrderManager import ManagedOrder, OrderStatus


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SQLitePersistence:
    """订单、持仓、风控状态的本地持久化。"""

    def __init__(self, db_path: str = "data/trading.db"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                strategy_id TEXT NOT NULL DEFAULT 'default',
                symbol      TEXT NOT NULL,
                size        INTEGER NOT NULL,
                avg_cost    REAL NOT NULL,
                updated_at  TEXT NOT NULL,
                PRIMARY KEY (strategy_id, symbol)
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id      TEXT PRIMARY KEY,
                strategy_id   TEXT NOT NULL DEFAULT 'default',
                symbol        TEXT NOT NULL,
                side          TEXT NOT NULL,
                price         REAL NOT NULL,
                size          INTEGER NOT NULL,
                order_type    TEXT DEFAULT 'market',
                status        TEXT NOT NULL,
                filled_price  REAL DEFAULT 0,
                filled_size   INTEGER DEFAULT 0,
                reject_reason TEXT DEFAULT '',
                retry_count   INTEGER DEFAULT 0,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS risk_state (
                scope      TEXT NOT NULL DEFAULT 'GLOBAL',
                key        TEXT NOT NULL,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (scope, key)
            );
        """)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ================================================================
    # Positions
    # ================================================================

    def save_position(self, symbol: str, size: int, avg_cost: float,
                      strategy_id: str = "default"):
        self._conn.execute(
            """INSERT OR REPLACE INTO positions
               (strategy_id, symbol, size, avg_cost, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (strategy_id, symbol, size, avg_cost, _utc_now()),
        )
        self._conn.commit()

    def load_positions(self, strategy_id: str = None
                       ) -> dict[str, tuple[int, float]]:
        """
        返回 {symbol: (size, avg_cost)}。
        strategy_id=None 返回所有策略的合并结果。
        """
        if strategy_id:
            rows = self._conn.execute(
                "SELECT symbol, size, avg_cost FROM positions WHERE strategy_id=?",
                (strategy_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT symbol, size, avg_cost FROM positions"
            ).fetchall()
        return {r["symbol"]: (r["size"], r["avg_cost"]) for r in rows}

    # ================================================================
    # Orders
    # ================================================================

    def save_order(self, mo: ManagedOrder, strategy_id: str = "default"):
        self._conn.execute(
            """INSERT OR REPLACE INTO orders
               (order_id, strategy_id, symbol, side, price, size, order_type,
                status, filled_price, filled_size, reject_reason, retry_count,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mo.order_id,
                strategy_id,
                mo.order.symbol,
                mo.order.side,
                mo.order.price,
                mo.order.size,
                mo.order.order_type,
                mo.status.value,
                mo.filled_price,
                mo.filled_size,
                mo.reject_reason,
                mo.retry_count,
                _utc_now() if mo.created_at == 0 else
                    datetime.fromtimestamp(mo.created_at, tz=timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                _utc_now(),
            ),
        )
        self._conn.commit()

    def load_pending_orders(self, strategy_id: str = None
                            ) -> list[dict]:
        """返回未完成订单（pending / partial / created）。"""
        base = """SELECT * FROM orders
                  WHERE status IN ('pending','partial','created')"""
        if strategy_id:
            rows = self._conn.execute(
                base + " AND strategy_id=?", (strategy_id,)
            ).fetchall()
        else:
            rows = self._conn.execute(base).fetchall()
        return [dict(r) for r in rows]

    # ================================================================
    # Risk State
    # ================================================================

    def save_risk_state(self, key: str, value,
                        scope: str = "GLOBAL"):
        self._conn.execute(
            """INSERT OR REPLACE INTO risk_state (scope, key, value, updated_at)
               VALUES (?, ?, ?, ?)""",
            (scope, key, str(value), _utc_now()),
        )
        self._conn.commit()

    def load_risk_state(self, scope: str = None) -> dict[str, str]:
        """
        返回 {key: value}。
        scope=None 返回所有 scope 的合并结果（GLOBAL 优先）。
        """
        if scope:
            rows = self._conn.execute(
                "SELECT key, value FROM risk_state WHERE scope=?",
                (scope,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT key, value FROM risk_state"
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ================================================================
    # Broker Reconcile — 实盘以券商为 Source of Truth
    # ================================================================

    def reconcile_positions(self, broker_positions: dict[str, tuple[int, float]],
                            strategy_id: str = "default"):
        """
        与券商持仓对账。返回 (to_update, to_delete)。
          to_update: 券商有但本地不一致的 → 更新本地
          to_delete: 本地有但券商没有的 → 删除本地

        原则: 券商永远正确。
        """
        local = self.load_positions(strategy_id)
        to_update = {}
        to_delete = []

        for symbol, (b_size, b_cost) in broker_positions.items():
            if symbol not in local or local[symbol] != (b_size, b_cost):
                to_update[symbol] = (b_size, b_cost)

        for symbol in local:
            if symbol not in broker_positions:
                to_delete.append(symbol)

        # 执行更新
        for symbol, (size, cost) in to_update.items():
            self.save_position(symbol, size, cost, strategy_id)

        for symbol in to_delete:
            self._conn.execute(
                "DELETE FROM positions WHERE strategy_id=? AND symbol=?",
                (strategy_id, symbol),
            )
            self._conn.commit()

        return to_update, to_delete
