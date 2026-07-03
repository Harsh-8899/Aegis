import datetime
import logging
import numpy as np
from sqlalchemy.orm import Session

from src.data.database import TradeDirection, PortfolioState
from src.features.store import FeatureStore
from src.models.registry import ModelRegistryManager
from src.risk.evaluator import RiskEvaluator
from src.risk.shutdown import EmergencyShutdownManager
from src.agents.execution import ExecutionAgent
from src.agents.performance import PerformanceAgent
from src.agents.monitoring import MonitoringAgent
from src.strategies.base_strategy import (
    TrendFollowingStrategy, MeanReversionStrategy, VolatilityBreakoutStrategy
)
from src.models.math_models import (
    KalmanFilterPriceTracker, GARCHVolatilityForecaster, 
    HiddenMarkovModel, AutoRegressiveModel
)

logger = logging.getLogger("CEOAgent")

class CEOAgent:
    """
    Main orchestrator of the quantitative platform.
    Coordinates feature generation, model inferences, strategy calculations,
    risk vetting, trade execution, and health telemetry.
    """
    def __init__(self, db: Session):
        self.db = db
        self.feature_store = FeatureStore(db)
        self.model_manager = ModelRegistryManager(db)
        self.risk_evaluator = RiskEvaluator(db)
        self.shutdown_manager = EmergencyShutdownManager(db)
        self.execution_agent = ExecutionAgent(db)
        self.performance_agent = PerformanceAgent(db)
        self.monitoring_agent = MonitoringAgent(db)

        # Register trading strategies
        self.strategies = {
            "trend_following": TrendFollowingStrategy("trend_following", {}),
            "mean_reversion": MeanReversionStrategy("mean_reversion", {}),
            "breakout": VolatilityBreakoutStrategy("breakout", {})
        }

        # Initialize mathematical model trackers
        self.kalman_tracker = KalmanFilterPriceTracker()
        self.garch_forecaster = GARCHVolatilityForecaster()
        self.hmm_regime_detector = HiddenMarkovModel()
        self.ar_forecaster = AutoRegressiveModel()

    def execute_trading_cycle(self) -> dict:
        """
        Runs one step of the trading cycle:
        Collects latest features -> Predicts direction -> Gets strategy signals ->
        Checks risk -> Executes orders -> Logs states.
        """
        # 1. Emergency Check
        if self.shutdown_manager.check_system_lockout():
            return {"status": "HALTED", "reason": "System is locked out due to emergency shutdown state."}

        # 2. Get latest complete feature row
        feat_vector = self.feature_store.get_latest_feature_vector(symbol="XAUUSD", timeframe="1m")
        if not feat_vector:
            return {"status": "NO_DATA", "reason": "Insufficient candles in feature store to trade."}

        price = feat_vector["close"]
        atr = feat_vector.get("atr_14", 15.0)

        # 3. Model Inference (Confidence estimate)
        model = self.model_manager.get_active_model()
        model_prediction = 0
        if model:
            # Reconstruct list matching feature cols
            X = [feat_vector.get(c, 0.0) for c in model.feature_cols]
            import numpy as np
            model_prediction = int(model.predict(np.array([X]))[0])

        # 4. Generate Strategy Signals
        # Load complete df for indicator arrays
        df = self.feature_store.get_features(symbol="XAUUSD", timeframe="1m", limit=200)
        
        signals = {}
        for name, strat in self.strategies.items():
            signals[name] = strat.generate_signal(df)

        # 4b. Extract price series and run mathematical models
        prices = np.array([float(row["close"]) for row in df.tail(100).to_dicts()])
        returns = np.diff(np.log(prices)) if len(prices) > 1 else np.array([0.0])

        # Kalman true price tracker
        filtered_price = self.kalman_tracker.update(price)
        kalman_trend = 1 if price > filtered_price else -1

        # GARCH volatility forecast
        garch_var = self.garch_forecaster.forecast_next_variance(returns)
        garch_vol = np.sqrt(garch_var)

        # HMM regime state classification (0: low vol/bullish, 1: high vol/bearish)
        hmm_states = self.hmm_regime_detector.predict_regime_states(returns)
        current_regime = int(hmm_states[-1]) if len(hmm_states) > 0 else 0

        # AR returns forecaster
        ar_predicted_return = self.ar_forecaster.predict_next_return(returns)
        ar_signal = 1 if ar_predicted_return > 0.0001 else -1 if ar_predicted_return < -0.0001 else 0

        # 4c. Meta-Signal Ensemble weighting consensus voting
        # BUY = +1, SELL = -1, FLAT = 0
        aggregated_score = 0.0
        
        # Strategies contribution
        aggregated_score += 0.3 * signals["trend_following"]
        aggregated_score += 0.25 * signals["mean_reversion"]
        aggregated_score += 0.25 * signals["breakout"]
        
        # Advanced mathematical models overlay
        aggregated_score += 0.10 * kalman_trend
        aggregated_score += 0.10 * ar_signal
        
        # ML recommendation weighting (multiplier / support)
        if model_prediction != 0:
            aggregated_score += 0.4 * model_prediction

        # HMM regime defense: reduce risk factor if in High Vol / Bearish regime
        if current_regime == 1:
            logger.info("Hidden Markov Model detected High-Volatility / Bearish regime. Sizing down scores.")
            aggregated_score *= 0.5

        # Decision threshold
        decision_direction = TradeDirection.BUY if aggregated_score >= 0.45 else None
        if aggregated_score <= -0.45:
            decision_direction = TradeDirection.SELL

        # 5. Position sizing (Risk Parity, adjusted down by GARCH volatility forecast)
        # Sizing is inversely proportional to predicted GARCH volatility
        vol_scalar = 1.0 / (garch_vol / 0.002) if garch_vol > 0 else 1.0
        vol_scalar = max(0.1, min(1.5, vol_scalar)) # clamp scaling
        
        base_volume = self.risk_evaluator.calculate_position_size_risk_parity(price, atr, target_risk_pct=0.01)
        volume = float(np.round(base_volume * vol_scalar, 2))
        if volume <= 0:
            volume = 0.01

        # 6. Execute direction changes
        # Query open positions
        from src.data.database import Position
        open_pos = self.db.query(Position).filter(Position.closed_at.is_(None)).first()

        cycle_action = "NO_ACTION"
        rejection_reason = ""

        if decision_direction is not None:
            # Check if we already have this position open
            if open_pos:
                if open_pos.direction != decision_direction:
                    # Close out current opposite trade
                    self.execution_agent.close_all_positions(price)
                    # Proceed with new trade check
                    is_approved, reason = self.risk_evaluator.verify_pre_trade_limits(decision_direction, volume, price)
                    if is_approved:
                        self.execution_agent.execute_order("CEO_ORCHESTRATOR", decision_direction, volume, price)
                        cycle_action = f"REVERSED_TO_{decision_direction.value}"
                    else:
                        cycle_action = "REJECTED_BY_RISK"
                        rejection_reason = reason
                else:
                    cycle_action = "HOLD_POSITION"
            else:
                # Open new trade
                is_approved, reason = self.risk_evaluator.verify_pre_trade_limits(decision_direction, volume, price)
                if is_approved:
                    self.execution_agent.execute_order("CEO_ORCHESTRATOR", decision_direction, volume, price)
                    cycle_action = f"OPENED_{decision_direction.value}"
                else:
                    cycle_action = "REJECTED_BY_RISK"
                    rejection_reason = reason
        else:
            # Go FLAT / close if we have signals recommending FLAT and position exists
            if open_pos:
                self.execution_agent.close_all_positions(price)
                cycle_action = "CLOSED_FLAT"

        # 7. Telemetry & Performance Sync
        portfolio = self.db.query(PortfolioState).order_by(PortfolioState.timestamp.desc()).first()
        if portfolio:
            # Update equity logs periodically
            # Realized PNL updates are calculated by execution agent, we update unrealized here
            open_positions = self.db.query(Position).filter(Position.closed_at.is_(None)).all()
            total_unrealized = 0.0
            for pos in open_positions:
                if pos.direction == TradeDirection.BUY:
                    pnl = (price - float(pos.entry_price)) * 100.0 * float(pos.volume)
                else:
                    pnl = (float(pos.entry_price) - price) * 100.0 * float(pos.volume)
                pos.unrealized_pnl = pnl
                total_unrealized += pnl
                
            equity = float(portfolio.balance) + total_unrealized
            portfolio.equity = equity
            
            # Recalculate drawdown
            # Using $100k starting capital default for simplicity
            starting_cap = 100000.0
            drawdown = max(0.0, (starting_cap - equity) / starting_cap)
            portfolio.drawdown = drawdown
            self.db.commit()

        # Gather health indicators
        health = self.monitoring_agent.check_system_health()

        return {
            "status": "SUCCESS",
            "action": cycle_action,
            "rejection_reason": rejection_reason,
            "current_price": price,
            "signals": signals,
            "model_prediction": model_prediction,
            "score": aggregated_score,
            "system_health": health["status"]
        }
