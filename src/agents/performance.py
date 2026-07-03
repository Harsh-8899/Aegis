import logging
from sqlalchemy.orm import Session
from src.data.database import Position, PortfolioState

logger = logging.getLogger("PerformanceAgent")

class PerformanceAgent:
    """
    Computes key performance indicators, draws attribution metrics, 
    and updates historical equity logs.
    """
    def __init__(self, db: Session):
        self.db = db

    def calculate_performance_dashboard(self) -> dict:
        """
        Calculates all key metrics for dashboard views.
        """
        closed_trades = self.db.query(Position).filter(Position.closed_at.is_not(None)).all()
        
        if not closed_trades:
            return {
                "win_rate": 0.0,
                "profit_factor": 1.0,
                "total_trades": 0,
                "win_count": 0,
                "loss_count": 0,
                "average_pnl": 0.0,
                "max_drawdown": 0.0,
                "sharpe": 0.0
            }

        pnls = [float(t.realized_pnl) for t in closed_trades if t.realized_pnl is not None]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_count = len(wins)
        loss_count = len(losses)
        total_trades = len(pnls)
        
        win_rate = (win_count / total_trades) if total_trades > 0 else 0.0
        
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 1.0
        average_pnl = sum(pnls) / total_trades if total_trades > 0 else 0.0

        # Calculate max drawdown from PortfolioState records
        portfolio_history = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.asc()).all()
        max_dd = 0.0
        if portfolio_history:
            max_dd = max(float(p.drawdown) for p in portfolio_history)

        return {
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "average_pnl": round(average_pnl, 2),
            "max_drawdown": round(max_dd, 4),
            "total_net_profit": round(sum(pnls), 2)
        }
        
    def log_portfolio_state(self, balance: float, equity: float, margin_used: float, free_margin: float, 
                            leverage: float, var_95: float, drawdown: float) -> PortfolioState:
        """
        Logs a snapshot of the current portfolio state.
        """
        import datetime
        state = PortfolioState(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            balance=balance,
            equity=equity,
            margin_used=margin_used,
            free_margin=free_margin,
            leverage=leverage,
            var_95=var_95,
            drawdown=drawdown
        )
        self.db.add(state)
        self.db.commit()
        return state
