"""
BrokerHeartbeatMonitor — 券商连接存活检测
"""
import time
from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult


class BrokerHeartbeatMonitor(Monitor):
    def check(self, ctx: MonitorContext) -> MonitorResult:
        if ctx.broker_connected:
            return MonitorResult.ok(self.name)

        disconnected_sec = time.time() - ctx.broker_last_heartbeat

        if disconnected_sec < 10:
            return MonitorResult.warn(
                self.name, f"券商断连 {disconnected_sec:.0f}s",
            )
        elif disconnected_sec < 60:
            return MonitorResult.error(
                self.name, f"券商断连 {disconnected_sec:.0f}s，请检查网络",
            )
        else:
            return MonitorResult.critical(
                self.name, f"券商断连 {disconnected_sec:.0f}s，需立即人工介入",
                action="检查网络连接，必要时联系券商技术支持",
            )
