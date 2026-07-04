"""
MonitorResult — 监控结果
=========================
纯数据结构，平台无关。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Severity(Enum):
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"


@dataclass
class MonitorResult:
    monitor_name: str
    severity: Severity
    message: str
    suggested_action: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""   # UTC ISO8601

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

    @classmethod
    def ok(cls, name: str) -> "MonitorResult":
        return cls(name, Severity.INFO, "正常")

    @classmethod
    def warn(cls, name: str, message: str, **meta) -> "MonitorResult":
        return cls(name, Severity.WARNING, message, metadata=meta)

    @classmethod
    def error(cls, name: str, message: str, **meta) -> "MonitorResult":
        return cls(name, Severity.ERROR, message, metadata=meta)

    @classmethod
    def critical(cls, name: str, message: str,
                 action: str = "", **meta) -> "MonitorResult":
        return cls(name, Severity.CRITICAL, message,
                   suggested_action=action, metadata=meta)
