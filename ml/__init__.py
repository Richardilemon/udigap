#!/usr/bin/env python3
"""
UDIGAP Machine Learning Module

Provides ML-powered fiber deployment priority prediction.

Components:
- feature_engineering: Extract features from PostGIS
- train_model: Train RandomForest classifier
- predict_priorities: Generate and store predictions
- utils: Common utilities

Usage:
    # Train model
    python -m ml.train_model

    # Generate predictions
    python -m ml.predict_priorities

    # Or use programmatically
    from ml.train_model import PriorityModelTrainer
    from ml.predict_priorities import PriorityPredictor
"""

from .utils import get_db_connection, logger
from .feature_engineering import FeatureEngineer
from .train_model import PriorityModelTrainer
from .predict_priorities import PriorityPredictor

__all__ = [
    'FeatureEngineer',
    'PriorityModelTrainer',
    'PriorityPredictor',
    'get_db_connection',
    'logger'
]
