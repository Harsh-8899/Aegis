import os
import pickle
import numpy as np
import polars as pl
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sqlalchemy.orm import Session

from src.config import load_config
from src.data.database import ModelRegistry

cfg = load_config()

class EnsembleModel:
    """
    Ensemble model combining Random Forest, Gradient Boosting, and Extra Trees
    to predict XAU/USD market direction and estimate prediction confidence.
    """
    def __init__(self):
        self.rf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
        self.gb = GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42)
        self.et = ExtraTreesClassifier(n_estimators=100, max_depth=8, random_state=42)
        self.feature_cols = []

    def fit(self, X: np.ndarray, y: np.ndarray, feature_cols: list[str]):
        self.feature_cols = feature_cols
        # Train base estimators
        self.rf.fit(X, y)
        self.gb.fit(X, y)
        self.et.fit(X, y)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Returns average probabilities from all base estimators.
        """
        p_rf = self.rf.predict_proba(X)
        p_gb = self.gb.predict_proba(X)
        p_et = self.et.predict_proba(X)
        return (p_rf + p_gb + p_et) / 3.0

    def predict(self, X: np.ndarray, confidence_threshold: float = 0.55) -> np.ndarray:
        """
        Predicts 1 (UP), -1 (DOWN), or 0 (FLAT / LOW CONFIDENCE) based on probability margins.
        """
        probas = self.predict_proba(X)
        predictions = np.zeros(len(X))
        
        for idx, prob in enumerate(probas):
            max_class = np.argmax(prob)
            max_prob = prob[max_class]
            
            if max_prob >= confidence_threshold:
                if max_class == 2: # mapped from +1 (UP)
                    predictions[idx] = 1
                elif max_class == 0: # mapped from -1 (DOWN)
                    predictions[idx] = -1
                else:
                    predictions[idx] = 0
            else:
                predictions[idx] = 0
                
        return predictions

    def get_feature_importances(self) -> dict[str, float]:
        """
        Returns average feature importance mapping.
        """
        imp = (self.rf.feature_importances_ + self.gb.feature_importances_ + self.et.feature_importances_) / 3.0
        return dict(zip(self.feature_cols, imp.tolist()))


class ModelTrainer:
    """
    Handles model training, evaluation, validation, and drift detection.
    """
    def __init__(self, db: Session):
        self.db = db
        os.makedirs(cfg.ml_registry.model_dir, exist_ok=True)

    def prepare_data(self, df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """
        Strips targets and cleans features for modeling.
        """
        # Exclude target and metadata columns
        exclude_cols = ["timestamp", "open", "high", "low", "close", "volume", "bid", "ask", 
                        "target_return_5p", "target_direction_5p", "true_range"]
        
        feature_cols = [c for c in df.columns if c not in exclude_cols]
        
        # Fill nulls
        df_clean = df.fill_nan(0.0).fill_null(0.0)
        
        X = df_clean.select(feature_cols).to_numpy()
        
        # Shift target to class labels: -1 -> 0, 0 -> 1, 1 -> 2
        y = df_clean["target_direction_5p"].to_numpy()
        y_classes = y + 1 # Converts to 0, 1, 2
        
        return X, y_classes, feature_cols

    def detect_drift(self, reference_features: np.ndarray, current_features: np.ndarray) -> bool:
        """
        Performs Kolmogorov-Smirnov test to identify statistical feature drift.
        Returns True if drift threshold is exceeded on any major features.
        """
        drift_count = 0
        num_features = reference_features.shape[1]
        
        for i in range(num_features):
            ref_col = reference_features[:, i]
            cur_col = current_features[:, i]
            
            # KS test
            stat, p_value = ks_2samp(ref_col, cur_col)
            # If p-value is extremely small, distributions are statistically different
            if p_value < cfg.ml_registry.drift_threshold_ks:
                drift_count += 1
                
        # If more than 15% of features exhibit drift, flag system drift
        drift_ratio = drift_count / num_features
        return drift_ratio > 0.15

    def train_and_register(self, train_df: pl.DataFrame, val_df: pl.DataFrame, version_name: str) -> bool:
        """
        Trains model ensemble, checks performance against thresholds, and registers model.
        """
        X_train, y_train, feature_cols = self.prepare_data(train_df)
        X_val, y_val, _ = self.prepare_data(val_df)

        model = EnsembleModel()
        model.fit(X_train, y_train, feature_cols)

        # Validate performance
        val_preds = model.predict(X_val)
        # Map class levels back: 0 -> -1, 1 -> 0, 2 -> 1
        y_val_mapped = y_val - 1
        
        acc = accuracy_score(y_val_mapped, val_preds)
        
        # Binary target for positive returns (up direction precision check)
        y_val_up = (y_val_mapped == 1).astype(int)
        preds_up = (val_preds == 1).astype(int)
        
        precision = precision_score(y_val_up, preds_up, zero_division=0)
        recall = recall_score(y_val_up, preds_up, zero_division=0)

        # Performance Check for Rollback Guard
        if precision < cfg.ml_registry.min_precision:
            # Model rejected because it did not meet target precision constraint
            print(f"Model validation failed: precision {precision:.4f} < threshold {cfg.ml_registry.min_precision}")
            return False

        # Save model state
        filepath = os.path.join(cfg.ml_registry.model_dir, f"model_{version_name}.pkl")
        with open(filepath, "wb") as f:
            pickle.dump(model, f)

        # Save record in Database
        metrics = {
            "accuracy": float(acc),
            "precision": float(precision),
            "recall": float(recall),
            "feature_importance": model.get_feature_importances()
        }

        # Check for active model to replace
        active_model = self.db.query(ModelRegistry).filter_by(is_active=True).first()
        
        # Deactivate old models if validation checks succeed
        if active_model:
            active_model.is_active = False

        new_reg = ModelRegistry(
            model_version=version_name,
            model_type="Ensemble_RF_GB_ET",
            metrics=metrics,
            filepath=filepath,
            is_active=True
        )
        self.db.add(new_reg)
        self.db.commit()
        return True
