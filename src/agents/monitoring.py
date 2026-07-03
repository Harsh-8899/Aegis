import psutil
import datetime
import logging
from sqlalchemy.orm import Session
from src.data.database import SystemAlert, MarketData

logger = logging.getLogger("MonitoringAgent")

class MonitoringAgent:
    """
    Monitors host resource usage (CPU, Memory), API/Broker disconnections,
    and logs critical notifications.
    """
    def __init__(self, db: Session):
        self.db = db

    def check_system_health(self) -> dict:
        """
        Gathers system statistics and generates warnings if resources are constrained.
        """
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent

        health_status = "HEALTHY"
        alerts = []

        if cpu_usage > 90.0:
            health_status = "WARNING"
            alerts.append(self.log_alert("CPU load exceeds 90%", "WARN"))
        
        if memory_usage > 90.0:
            health_status = "WARNING"
            alerts.append(self.log_alert("Memory usage exceeds 90%", "WARN"))

        # Verify market connection: check if we got a candle in the last 15 minutes
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        # Convert timezone-naive lookup standard to database representation
        cutoff_naive = cutoff.replace(tzinfo=None)
        
        latest_tick = (
            self.db.query(MarketData)
            .order_by(MarketData.timestamp.desc())
            .first()
        )
        
        if not latest_tick or latest_tick.timestamp.replace(tzinfo=None) < cutoff_naive:
            health_status = "CRITICAL"
            alerts.append(self.log_alert("Market data feed connection down or frozen", "CRITICAL"))

        return {
            "status": health_status,
            "cpu_usage_pct": cpu_usage,
            "memory_usage_pct": memory_usage,
            "active_alerts": alerts
        }

    def log_alert(self, message: str, severity: str = "INFO") -> dict:
        """
        Creates and saves a system alert log.
        """
        alert = SystemAlert(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            agent_name="MonitoringAgent",
            severity=severity,
            message=message
        )
        self.db.add(alert)
        self.db.commit()
        
        logger.warning(f"ALERT [{severity}]: {message}")
        return {
            "timestamp": alert.timestamp.isoformat(),
            "severity": severity,
            "message": message
        }
