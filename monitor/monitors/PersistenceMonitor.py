"""
PersistenceMonitor — 数据库状态检测
"""
from monitor.Monitor import Monitor
from monitor.MonitorContext import MonitorContext
from monitor.MonitorResult import MonitorResult


class PersistenceMonitor(Monitor):
    def check(self, ctx: MonitorContext) -> MonitorResult:
        if not ctx.db_writable:
            if ctx.db_write_fail_count >= 3:
                return MonitorResult.critical(
                    self.name,
                    f"数据库写入连续失败 {ctx.db_write_fail_count} 次",
                    action="检查磁盘空间和文件权限",
                )
            return MonitorResult.error(
                self.name,
                f"数据库写入失败 {ctx.db_write_fail_count} 次",
            )

        if ctx.db_disk_free_mb < 200:
            return MonitorResult.warn(
                self.name,
                f"磁盘剩余 {ctx.db_disk_free_mb:.0f}MB，建议清理",
            )

        return MonitorResult.ok(self.name)
