import datetime
import random
import logging
from sqlalchemy.orm import Session
from src.data.database import Order, Position, OrderStatus, TradeDirection
from src.config import load_config

logger = logging.getLogger("ExecutionAgent")
cfg = load_config()

class ExecutionAgent:
    """
    Responsible for smart order routing, slippage estimation, execution latency,
    and managing trade persistence.
    """
    def __init__(self, db: Session):
        self.db = db

    def execute_order(self, strategy_id: str, direction: TradeDirection, volume: float, price: float) -> Order | None:
        """
        Executes a trade order, simulating connection latency and price slippage.
        """
        # 1. Latency simulation (milliseconds)
        latency_ms = int(random.uniform(80, 220)) # typical institutional ECN latency
        
        # 2. Slippage calculation (scaled by current volatility or fixed buffer)
        slippage_pips = random.expovariate(2.0) + cfg.risk.slippage_buffer_pips
        slippage_val = slippage_pips * 0.10 # Gold: 1 pip = $0.10
        
        # Actual execution price adjusted for direction
        if direction == TradeDirection.BUY:
            fill_price = price + slippage_val
        else:
            fill_price = price - slippage_val

        try:
            # 3. Create database Order entry
            order = Order(
                strategy_id=strategy_id,
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
            self.db.flush() # Populate order_id
            
            # 4. Open a corresponding position
            # Determine Stop-Loss and Take-Profit bounds (e.g. 3 ATR on Stop, 6 ATR on Target)
            atr_buffer = 15.0 # default Gold buffer equivalent
            if direction == TradeDirection.BUY:
                stop_loss = fill_price - atr_buffer
                take_profit = fill_price + (2.0 * atr_buffer)
            else:
                stop_loss = fill_price + atr_buffer
                take_profit = fill_price - (2.0 * atr_buffer)

            position = Position(
                order_id=order.order_id,
                direction=direction,
                entry_price=fill_price,
                volume=volume,
                stop_loss=stop_loss,
                take_profit=take_profit,
                created_at=datetime.datetime.now(datetime.timezone.utc)
            )
            self.db.add(position)
            self.db.commit()
            
            logger.info(f"Order FILLED: {direction.value} {volume} XAUUSD at {fill_price:.2f} (Slip: {slippage_pips:.2f} pips, Latency: {latency_ms}ms)")
            return order
        except Exception as e:
            self.db.rollback()
            logger.error(f"Execution order failed to commit: {e}")
            return None

    def close_all_positions(self, current_price: float) -> list[Position]:
        """
        Closes all open positions at the current price.
        """
        open_positions = self.db.query(Position).filter(Position.closed_at.is_(None)).all()
        closed_list = []
        
        for pos in open_positions:
            try:
                pos.closed_at = datetime.datetime.now(datetime.timezone.utc)
                pos.exit_price = current_price
                
                # Calculate realized PnL
                if pos.direction == TradeDirection.BUY:
                    pnl = (current_price - float(pos.entry_price)) * 100.0 * float(pos.volume)
                else:
                    pnl = (float(pos.entry_price) - current_price) * 100.0 * float(pos.volume)
                    
                pos.realized_pnl = pnl
                closed_list.append(pos)
                logger.info(f"Position CLOSED: {pos.direction.value} {pos.volume} at exit {current_price:.2f}. Realized PnL: ${pnl:.2f}")
            except Exception as e:
                logger.error(f"Failed to close position {pos.position_id}: {e}")
                
        if closed_list:
            self.db.commit()
            
        return closed_list
