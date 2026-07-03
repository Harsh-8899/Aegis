import pickle
import logging
from sqlalchemy.orm import Session
from src.data.database import ModelRegistry
from src.models.train import EnsembleModel

logger = logging.getLogger("ModelRegistry")

class ModelRegistryManager:
    """
    Manages loading, activation, and rollbacks of trained ML ensembles from DB and disk.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_active_model(self) -> EnsembleModel | None:
        """
        Loads the active model ensemble from disk.
        """
        reg_entry = self.db.query(ModelRegistry).filter_by(is_active=True).first()
        if not reg_entry:
            logger.warning("No active model found in the registry.")
            return None
            
        try:
            with open(reg_entry.filepath, "rb") as f:
                model = pickle.load(f)
            return model
        except Exception as e:
            logger.error(f"Failed to load model file at {reg_entry.filepath}: {e}")
            return None

    def rollback_model(self) -> bool:
        """
        Deactivates current model and rolls back to the previous version based on creation order.
        """
        active_model = self.db.query(ModelRegistry).filter_by(is_active=True).first()
        if not active_model:
            logger.info("No active model to rollback.")
            return False

        # Find the previous model
        previous_model = (
            self.db.query(ModelRegistry)
            .filter(ModelRegistry.model_version != active_model.model_version)
            .order_by(ModelRegistry.created_at.desc())
            .first()
        )

        if not previous_model:
            logger.warning("No previous model version found to rollback to.")
            return False

        try:
            active_model.is_active = False
            previous_model.is_active = True
            self.db.commit()
            logger.info(f"Successfully rolled back model from {active_model.model_version} to {previous_model.model_version}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Rollback failed in database: {e}")
            return False
            
    def get_all_models(self) -> list[dict]:
        """
        Lists all registered models and their performance metrics.
        """
        entries = self.db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc()).all()
        return [
            {
                "version": e.model_version,
                "type": e.model_type,
                "metrics": e.metrics,
                "is_active": e.is_active,
                "created_at": e.created_at.isoformat()
            }
            for e in entries
        ]
