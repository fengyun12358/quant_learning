"""
BrokerReconcile — 券商对账模块
===============================
平台无关。纯 Python。

职责: 券商持仓 ↔ 本地 SQLite 持仓 → Diff → 审计日志 → 同步。

PaperBroker / MiniQMT / 其他券商全部复用。
"""

from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BrokerReconcile:
    """
    券商持仓与本地数据库对账。
    原则: 券商永远为 Source of Truth。
    """

    def __init__(self, persistence, strategy_id: str = "default"):
        """
        persistence: SQLitePersistence 实例
        """
        self._persistence = persistence
        self._strategy_id = strategy_id
        self._audit_log: list[dict] = []

    def reconcile(self, broker_positions: dict[str, tuple[int, float]]
                  ) -> dict:
        """
        与券商对账。返回 {"updated": [...], "deleted": [...], "unchanged": [...]}。
        """
        local = self._persistence.load_positions(self._strategy_id)
        updated, deleted, unchanged = [], [], []

        # 券商有 → 更新或确认本地
        for symbol, (b_size, b_cost) in broker_positions.items():
            if symbol not in local or local[symbol] != (b_size, b_cost):
                self._persistence.save_position(
                    symbol, b_size, b_cost, self._strategy_id
                )
                updated.append(symbol)
                self._audit(symbol, "UPDATE",
                            old=local.get(symbol), new=(b_size, b_cost))
            else:
                unchanged.append(symbol)

        # 券商没有但本地有 → 删除本地
        for symbol in local:
            if symbol not in broker_positions:
                deleted.append(symbol)
                self._audit(symbol, "DELETE", old=local[symbol], new=None)

        # 实际删除在 SQLitePersistence 的 reconcile_positions 中
        to_update, to_delete = {}, deleted
        for symbol in updated:
            to_update[symbol] = broker_positions[symbol]
        self._persistence.reconcile_positions(
            broker_positions, self._strategy_id
        )

        return {"updated": updated, "deleted": deleted, "unchanged": unchanged}

    def audit_log(self) -> list[dict]:
        return self._audit_log

    def _audit(self, symbol: str, action: str,
               old: Optional[tuple] = None,
               new: Optional[tuple] = None):
        self._audit_log.append({
            "timestamp": _utc_now(),
            "symbol": symbol,
            "action": action,
            "old": f"{old}" if old else "",
            "new": f"{new}" if new else "",
        })
