import numpy as np
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from src.config import load_config
from src.data.database import Order, Position, PortfolioState, TradeDirection

logger = logging.getLogger("RiskEvaluator")
cfg = load_config()

class RiskEvaluator:
    """
    Independent Risk Management Agent with veto authority.
    Verifies drawdowns, calculates Value at Risk (VaR), checks exposure limits,
    and handles emergency shutdowns.
    """
    def __init__(self, db: Session):
        self.db = db

    def calculate_var_95(self, returns: List[float], confidence: float = 0.95) -> float:
        """
        Calculates Value at Risk (VaR) using historical simulation.
        Returns the expected loss threshold (amount) at the given confidence level.
        """
        if not returns or len(returns) < 5:
            # Fallback placeholder if no historical returns exist
            return 500.0
        
        # Sort returns
        sorted_ret = sorted(returns)
        idx = int(len(sorted_ret) * (1 - confidence))
        var_pct = sorted_ret[idx]
        
        # Translate to nominal value based on latest equity
        latest_portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        equity = float(latest_portfolio.equity) if latest_portfolio else 100000.0
        
        # VaR as positive loss amount
        return abs(var_pct * equity)

    def calculate_cvar_95(self, returns: List[float], confidence: float = 0.95) -> float:
        """
        Calculates Conditional Value at Risk (CVaR / Expected Shortfall).
        """
        if not returns or len(returns) < 5:
            return 800.0
            
        sorted_ret = np.sort(returns)
        cutoff_idx = int(len(sorted_ret) * (1 - confidence))
        
        # Average of returns worse than the VaR threshold
        cvar_pct = np.mean(sorted_ret[:cutoff_idx])
        
        latest_portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        equity = float(latest_portfolio.equity) if latest_portfolio else 100000.0
        
        return abs(cvar_pct * equity)

    def verify_pre_trade_limits(self, direction: TradeDirection, volume: float, price: float) -> tuple[bool, str]:
        """
        Evaluates a candidate order against risk controls.
        Returns (is_approved, reason).
        """
        # 1. Fetch current portfolio metrics
        portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        if not portfolio:
            return False, "No portfolio record found to validate balance"

        equity = float(portfolio.equity)
        balance = float(portfolio.balance)
        drawdown = float(portfolio.drawdown)

        # 2. Check system-wide drawdown
        if drawdown >= cfg.risk.max_drawdown_pct:
            return False, f"VETO: Maximum drawdown limit exceeded ({drawdown:.2%} >= {cfg.risk.max_drawdown_pct:.2%})"

        # 3. Check exposure limit
        # Gold Contract details: 1 lot = 100 ounces. Nominal value = price * volume * 100
        nominal_value = price * volume * 100.0
        max_exposure = equity * cfg.risk.max_position_exposure_pct
        
        if nominal_value > max_exposure:
            return False, f"VETO: Order exposure (${nominal_value:,.2f}) exceeds maximum limits (${max_exposure:,.2f})"

        # 4. Check position limits (Leverage check)
        open_positions = self.db.query(Position).filter(Position.closed_at.is_(None)).all()
        current_nominal_exposure = sum(float(p.entry_price) * float(p.volume) * 100.0 for p in open_positions)
        new_nominal_exposure = current_nominal_exposure + nominal_value
        
        effective_leverage = new_nominal_exposure / equity
        if effective_leverage > cfg.broker.leverage:
            return False, f"VETO: Leverage threshold breach ({effective_leverage:.2f}x > {cfg.broker.leverage:.2f}x)"

        # 5. Check daily loss limit
        # Query trades closed today and check realized PnL + current unrealized PnL
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        closed_today = self.db.query(Position).filter(Position.closed_at >= today_start).all()
        realized_today = sum(float(p.realized_pnl) for p in closed_today if p.realized_pnl)
        
        unrealized_today = sum(float(p.unrealized_pnl) for p in open_positions if p.unrealized_pnl)
        total_pnl_today = realized_today + unrealized_today
        
        max_daily_loss = -1.0 * (equity * cfg.risk.max_daily_loss_pct)
        if total_pnl_today <= max_daily_loss:
            return False, f"VETO: Daily loss limit exceeded (${total_pnl_today:,.2f} <= ${max_daily_loss:,.2f})"

        return True, "Approved"

    def calculate_position_size_risk_parity(self, price: float, atr: float, target_risk_pct: float = 0.01) -> float:
        """
        Calculates safe trade volume (lot sizes) scaled by asset volatility (ATR).
        Known as Risk Parity sizing.
        Formula: Lot Size = (Equity * target_risk) / (ATR * 100)
        """
        portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        equity = float(portfolio.equity) if portfolio else 100000.0
        
        # Safe loss amount in USD
        risk_cash = equity * target_risk_pct
        
        # Price movement representation: ATR represents the daily average price movement.
        # We size position such that a 1 ATR move equals the risk budget.
        if atr <= 0:
            atr = 10.0 # safety default
            
        lots = risk_cash / (atr * 100.0)
        
        # Clamp to bounds
        lots = max(cfg.broker.min_lot_size, min(lots, cfg.broker.max_lot_size))
        return round(lots, 2)
        
import datetime
