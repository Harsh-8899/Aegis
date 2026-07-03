import logging
import datetime
from sqlalchemy.orm import Session
from src.data.database import Order, Position, PortfolioState, OrderStatus, TradeDirection, SystemAlert

logger = logging.getLogger("EmergencyShutdown")

class EmergencyShutdownManager:
    """
    Executes immediate position liquidation and system lockouts.
    """
    def __init__(self, db: Session):
        self.db = db

    def trigger_emergency_shutdown(self, reason: str) -> dict:
        """
        Executes immediate market-order liquidation on all open positions,
        cancels all pending orders, and records emergency status.
        """
        logger.critical(f"EMERGENCY SHUTDOWN TRIGGERED: {reason}")
        
        try:
            # 1. Log System Alert
            alert = SystemAlert(
                agent_name="RiskManagementAgent",
                severity="CRITICAL",
                message=f"EMERGENCY SHUTDOWN ACTIVATED. Reason: {reason}"
            )
            self.db.add(alert)
            
            # 2. Cancel all pending orders in database
            pending_orders = self.db.query(Order).filter_by(status=OrderStatus.PENDING).all()
            cancelled_count = len(pending_orders)
            for order in pending_orders:
                order.status = OrderStatus.CANCELLED
                order.filled_at = datetime.datetime.now(datetime.timezone.utc)
            
            # 3. Liquidate all open positions
            open_positions = self.db.query(Position).filter(Position.closed_at.is_(None)).all()
            liquidated_count = len(open_positions)
            total_realized_pnl = 0.0
            
            for pos in open_positions:
                # In real scenario, would place a market order to close position.
                # Here we simulate immediate execution.
                # Assume closing at current entry price (just flatting out to prevent further exposure)
                pos.closed_at = datetime.datetime.now(datetime.timezone.utc)
                pos.exit_price = pos.entry_price # assuming zero slippage for simple liquidation record
                pos.realized_pnl = pos.unrealized_pnl
                total_realized_pnl += float(pos.realized_pnl)
                
            # 4. Update Portfolio Balance
            portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
            if portfolio:
                portfolio.balance = float(portfolio.balance) + total_realized_pnl
                portfolio.equity = portfolio.balance
                portfolio.margin_used = 0.0
                portfolio.free_margin = portfolio.balance
                portfolio.drawdown = 0.0
            
            self.db.commit()
            
            return {
                "status": "SHUTDOWN_COMPLETE",
                "cancelled_orders": cancelled_count,
                "liquidated_positions": liquidated_count,
                "total_liquidated_pnl": total_realized_pnl
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to execute emergency shutdown safely: {e}")
            return {
                "status": "SHUTDOWN_FAILED",
                "error": str(e)
            }
        
    def check_system_lockout(self) -> bool:
        """
        Returns True if the system is currently locked due to emergency shutdown alerts.
        """
        # Look for critical alerts in the last 24 hours
        yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        critical_alerts = (
            self.db.query(SystemAlert)
            .filter(SystemAlert.severity == "CRITICAL", SystemAlert.timestamp >= yesterday)
            .first()
        )
        return critical_alerts is not None
