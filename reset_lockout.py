import datetime
import logging
from src.data.database import SessionLocal, SystemAlert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ResetLockout")

def reset_lockout():
    db = SessionLocal()
    try:
        yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        # Query active critical alerts causing system lockout
        critical_alerts = db.query(SystemAlert).filter(
            SystemAlert.severity == "CRITICAL",
            SystemAlert.timestamp >= yesterday
        ).all()
        
        count = len(critical_alerts)
        if count == 0:
            logger.info("No active emergency lockout alerts found in the database. Platform is already unlocked.")
            return

        for alert in critical_alerts:
            # Demote severity to INFO to clear the block, preserving audit logs
            alert.severity = "INFO"
            alert.message = f"[RESOLVED] {alert.message}"
            
        db.commit()
        logger.info(f"Successfully resolved {count} emergency lockout alerts. Platform is now unlocked!")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reset lockout: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_lockout()
