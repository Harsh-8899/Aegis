import logging
import datetime
import random
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from src.data.database import Order, Position, OrderStatus, TradeDirection, PortfolioState, SystemAlert
from src.config import load_config
from src.risk.gate import RiskGate

logger = logging.getLogger("PaperExecution")
cfg = load_config()

# Global setting - live trading MUST be disabled for safety
LIVE_TRADING_ENABLED = False

class PaperExecutionEngine:
    """
    High-fidelity simulated paper trading engine.
    Executes trades at the bid/ask price with dynamic slippage and commission/spread checks.
    Manages stop-loss/take-profit hit triggers on every tick update.
    Tracks running statistics: Total trades, Win Rate, P&L.
    """
    def __init__(self, db: Session):
        self.db = db
        self.risk_gate = RiskGate(db)
        
        # Telemetry stats cached in memory for quick streaming
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_realized_pnl: float = 0.0
        self.win_rate: float = 0.0
        self.signal_history: List[Dict[str, Any]] = []

    def run_tick_checks(self, current_price: float):
        """
        Runs checks against all open positions to verify if SL or TP are hit.
        Should be called every second when a new price update occurs.
        """
        open_positions = self.db.query(Position).filter(Position.closed_at.is_(None)).all()
        
        for pos in open_positions:
            is_hit = False
            exit_reason = ""
            
            # SL / TP check
            if pos.direction == TradeDirection.BUY:
                if current_price <= float(pos.stop_loss):
                    is_hit = True
                    exit_reason = "STOP_LOSS"
                elif current_price >= float(pos.take_profit):
                    is_hit = True
                    exit_reason = "TAKE_PROFIT"
            else: # SELL
                if current_price >= float(pos.stop_loss):
                    is_hit = True
                    exit_reason = "STOP_LOSS"
                elif current_price <= float(pos.take_profit):
                    is_hit = True
                    exit_reason = "TAKE_PROFIT"

            if is_hit:
                self.close_position(pos, current_price, reason=exit_reason)

    def process_fused_signal(self, fusion_output: Dict[str, Any], tick_data: Dict[str, Any]) -> str:
        """
        Processes a new signal. Checks the risk gate, closes opposite positions,
        and opens new paper positions if approved.
        """
        signal = fusion_output["signal"]
        price = tick_data["price"]
        spread = tick_data["spread"]
        bid = tick_data["bid"]
        ask = tick_data["ask"]
        expected_vol = fusion_output["risk_score"] / 1000.0  # normalize
        risk_score = fusion_output["risk_score"]
        reason = fusion_output["reason"]

        # Run tick checks for SL/TP first
        self.run_tick_checks(price)

        # Get open positions
        open_pos = self.db.query(Position).filter(Position.closed_at.is_(None)).first()

        # Update P&L metrics for running stats
        self._sync_stats()

        if signal == "HOLD":
            return "HOLD"

        direction = TradeDirection.BUY if signal == "BUY" else TradeDirection.SELL

        # 1. Close opposite position if it exists
        if open_pos:
            if open_pos.direction != direction:
                self.close_position(open_pos, price, reason="SIGNAL_REVERSAL")
            else:
                # Already in the correct position, hold it
                return "HOLD_POSITION"

        # 2. Risk Gate Vetting
        # Sizing risk parity calculation
        atr_val = tick_data.get("atr_14", 1.5)
        # Sizing target 1% of equity
        portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        equity = float(portfolio.equity) if portfolio else 100000.0
        risk_cash = equity * 0.01
        volume = round(risk_cash / (atr_val * 100.0), 2)
        volume = max(cfg.broker.min_lot_size, min(volume, cfg.broker.max_lot_size))

        approved, risk_reason = self.risk_gate.verify_trade(
            direction=direction.value,
            volume=volume,
            price=price,
            spread=spread,
            expected_vol=expected_vol,
            risk_score=risk_score
        )

        if not approved:
            alert = SystemAlert(
                agent_name="RiskGate",
                severity="WARN",
                message=f"TRADE BLOCKED: {direction.value} {volume} lots blocked at {price:.2f}. Reason: {risk_reason}"
            )
            self.db.add(alert)
            self.db.commit()
            logger.warning(f"Risk gate vetoed trade: {risk_reason}")
            return f"TRADE BLOCKED: {risk_reason}"

        # 3. Simulate Execution order filling
        latency_ms = int(random.uniform(50, 180))
        slippage_pips = random.expovariate(3.0) + cfg.risk.slippage_buffer_pips
        slippage_val = slippage_pips * 0.10 # 1 pip = $0.10 in gold
        
        if direction == TradeDirection.BUY:
            fill_price = ask + slippage_val
        else:
            fill_price = bid - slippage_val

        # Create Order
        order = Order(
            strategy_id="REALTIME_LIVE_FUSION",
            direction=direction,
            volume=volume,
            limit_price=price,
            status=OrderStatus.FILLED,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            filled_at=datetime.datetime.now(datetime.timezone.utc),
            fill_price=fill_price,
            slippage=slippage_pips,
            latency_ms=latency_ms
        )
        self.db.add(order)
        self.db.flush()

        # Set SL and TP ranges
        sl_diff = 2.0 * atr_val
        tp_diff = 4.0 * atr_val
        if direction == TradeDirection.BUY:
            sl = fill_price - sl_diff
            tp = fill_price + tp_diff
        else:
            sl = fill_price + sl_diff
            tp = fill_price - tp_diff

        # Create Position
        pos = Position(
            order_id=order.order_id,
            direction=direction,
            entry_price=fill_price,
            volume=volume,
            stop_loss=sl,
            take_profit=tp,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        self.db.add(pos)
        self.db.commit()

        logger.info(f"Paper Trade Executed: {direction.value} {volume} lots filled at ${fill_price:.2f} (SL: ${sl:.2f}, TP: ${tp:.2f})")
        return f"EXECUTED_{direction.value}"

    def close_position(self, pos: Position, price: float, reason: str):
        """Closes a single position, calculates realized PnL, and commits to DB."""
        try:
            pos.closed_at = datetime.datetime.now(datetime.timezone.utc)
            pos.exit_price = price
            
            # Realized P&L: 1 lot = 100 ounces.
            # Buy P&L: (Exit - Entry) * volume * 100
            # Sell P&L: (Entry - Exit) * volume * 100
            if pos.direction == TradeDirection.BUY:
                pnl = (price - float(pos.entry_price)) * float(pos.volume) * 100.0
            else:
                pnl = (float(pos.entry_price) - price) * float(pos.volume) * 100.0
                
            pos.realized_pnl = pnl
            
            # Log in system alerts
            alert = SystemAlert(
                agent_name="PaperExecution",
                severity="INFO",
                message=f"Paper Position Closed: {pos.direction.value} at {price:.2f} due to {reason}. P&L: ${pnl:.2f}"
            )
            self.db.add(alert)
            
            # Sync balance in PortfolioState
            portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
            if portfolio:
                new_balance = float(portfolio.balance) + pnl
                portfolio.balance = new_balance
                portfolio.equity = new_balance # reset equity to match
                
            self.db.commit()
            logger.info(f"Paper position closed ({reason}): P&L ${pnl:.2f}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error closing paper position {pos.position_id}: {e}")

    def _sync_stats(self):
        """Synchronizes performance statistics from DB."""
        try:
            closed_trades = self.db.query(Position).filter(Position.closed_at.is_not(None)).all()
            self.total_trades = len(closed_trades)
            self.winning_trades = sum(1 for t in closed_trades if float(t.realized_pnl or 0.0) > 0.0)
            self.total_realized_pnl = sum(float(t.realized_pnl or 0.0) for t in closed_trades)
            
            if self.total_trades > 0:
                self.win_rate = round((self.winning_trades / self.total_trades) * 100, 2)
            else:
                self.win_rate = 0.0
        except Exception as e:
            logger.error(f"Failed to sync paper trading stats: {e}")


class BrokerExecutionModule:
    """
    Safeguarded broker execution module prepared for production API routing.
    Enforces LIVE_TRADING_ENABLED=false checks before routing orders.
    """
    def __init__(self):
        self.live_enabled = LIVE_TRADING_ENABLED

    def route_live_order(self, direction: str, volume: float, price: float) -> Dict[str, Any]:
        """Routes orders to institutional brokers when enabled."""
        if not self.live_enabled:
            logger.error("CRITICAL: Live trading routing blocked. LIVE_TRADING_ENABLED is set to FALSE.")
            return {
                "status": "BLOCKED",
                "error": "Live trading disabled. Sandbox and paper trading verification required."
            }
            
        # Placeholder for real production endpoints (e.g. FIX protocol API calls)
        logger.warning(f"Live order routed (Bypassed!): {direction} {volume} lots.")
        return {
            "status": "SUBMITTED",
            "order_id": "live_mock_12345",
            "routed_at": datetime.datetime.utcnow().isoformat()
        }
