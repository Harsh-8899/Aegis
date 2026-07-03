import logging
import datetime
from typing import Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from src.config import load_config
from src.data.database import Position, PortfolioState, MacroEvent, TradeDirection, SystemAlert
from src.risk.shutdown import EmergencyShutdownManager

logger = logging.getLogger("RiskGate")
cfg = load_config()

class RiskGate:
    """
    Validates fused signals against exposure thresholds, drawdowns, spread widening,
    and event locks. Absolute veto authority to block execution.
    """
    def __init__(self, db: Session):
        self.db = db
        self.shutdown_manager = EmergencyShutdownManager(db)

    def verify_trade(self, direction: str, volume: float, price: float, 
                     spread: float, expected_vol: float, risk_score: float) -> Tuple[bool, str]:
        """
        Runs comprehensive pre-trade validation checks.
        Returns (is_approved, reason).
        """
        # 1. Kill Switch Check
        if self.shutdown_manager.check_system_lockout():
            return False, "KILL_SWITCH_ACTIVE: System is in emergency lockout state"

        # 2. Query PortfolioState
        portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        if not portfolio:
            return False, "NO_PORTFOLIO_STATE: Unable to retrieve account parameters"

        equity = float(portfolio.equity)
        balance = float(portfolio.balance)
        drawdown = float(portfolio.drawdown)

        # 3. Maximum Drawdown Check
        if drawdown >= cfg.risk.max_drawdown_pct:
            return False, f"DRAWDOWN_BREACH: Drawdown is {drawdown:.2%}, limit is {cfg.risk.max_drawdown_pct:.2%}"

        # 4. Volatility Spike Check
        # Block trading if expected volatility exceeds thresholds
        if expected_vol > 0.0022 or risk_score > 85.0:
            return False, f"VOLATILITY_LOCKOUT: Volatility too high (GARCH: {expected_vol:.5f}, Risk: {risk_score:.1f})"

        # 5. Spread Widening Check
        # Gold standard spreads are 0.12 - 0.25 (1.2 - 2.5 pips). Wider than 0.30 (3.0 pips) is blocked.
        if spread > 0.30:
            return False, f"SPREAD_WIDENING: Current spread is {spread:.2f} pips, max allowed is 3.0 pips"

        # 6. Open Positions Limit
        open_positions = self.db.query(Position).filter(Position.closed_at.is_(None)).all()
        if len(open_positions) >= 3:
            return False, f"MAX_POSITIONS_REACHED: {len(open_positions)} positions currently open"

        # 7. Maximum Daily Loss Check
        # Realized + Unrealized P&L for today must not exceed limit (e.g. 2% of equity)
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        closed_today = self.db.query(Position).filter(Position.closed_at >= today_start).all()
        realized_pnl_today = sum(float(p.realized_pnl) for p in closed_today if p.realized_pnl)
        unrealized_pnl_today = sum(float(p.unrealized_pnl) for p in open_positions if p.unrealized_pnl)
        total_pnl_today = realized_pnl_today + unrealized_pnl_today
        
        max_loss_limit = -1.0 * (equity * cfg.risk.max_daily_loss_pct)
        if total_pnl_today <= max_loss_limit:
            return False, f"DAILY_LOSS_BREACH: Today's PnL (${total_pnl_today:.2f}) exceeds loss limit (${max_loss_limit:.2f})"

        # 8. News-Event Block Check
        # Veto trade if there is a HIGH importance macro event within ±15 minutes of now
        now = datetime.datetime.utcnow()
        margin = datetime.timedelta(minutes=15)
        near_event = self.db.query(MacroEvent).filter(
            MacroEvent.importance == "HIGH",
            MacroEvent.timestamp >= now - margin,
            MacroEvent.timestamp <= now + margin
        ).first()

        if near_event:
            return False, f"NEWS_EVENT_LOCKOUT: Near high-impact economic release '{near_event.event_name}' at {near_event.timestamp}"

        # 9. Max Position Size check
        if volume > cfg.broker.max_lot_size or volume < cfg.broker.min_lot_size:
            return False, f"INVALID_VOLUME: Position volume {volume} lots exceeds broker bounds"

        # 10. Max Leverage Check
        nominal_value = price * volume * 100.0  # Gold contract sizing
        current_nominal_exposure = sum(float(p.entry_price) * float(p.volume) * 100.0 for p in open_positions)
        total_exposure = current_nominal_exposure + nominal_value
        effective_leverage = total_exposure / equity

        if effective_leverage > cfg.broker.leverage:
            return False, f"LEVERAGE_BREACH: Effective leverage would be {effective_leverage:.2f}x, max is {cfg.broker.leverage:.2f}x"

        return True, "APPROVED"
