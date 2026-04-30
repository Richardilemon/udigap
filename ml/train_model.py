#!/usr/bin/env python3
"""
UDIGAP Model Training Module

Trains RandomForest classifier for fiber priority prediction.
Saves model, metrics, and feature importance to ml/models/

Usage:
    python -m ml.train_model
"""

import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

from .utils import logger, get_model_path, get_metrics_path, get_feature_importance_path
from .feature_engineering import FeatureEngineer


class PriorityModelTrainer:
    """Trains and evaluates the fiber priority prediction model"""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'population',
            'population_density',
            'fiber_per_100k',
            'distance_to_fiber_km',
            'economic_index'
        ]
        self.metrics = {}
        self.feature_importance = {}

    def prepare_data(self, df: pd.DataFrame):
        """
        Prepare data for training.

        Args:
            df: DataFrame with features and labels

        Returns:
            X_train, X_test, y_train, y_test
        """
        logger.info("Preparing data for training...")

        # Ensure all feature columns exist
        for col in self.feature_columns:
            if col not in df.columns:
                logger.warning(f"Missing column {col}, filling with default")
                df[col] = 0

        # Extract features and target
        X = df[self.feature_columns].copy()
        y = df['needs_fiber'].copy()

        # Handle any remaining NaN values
        X = X.fillna(0)

        # Log class distribution
        logger.info(f"Class distribution: {y.value_counts().to_dict()}")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=0.2,
            random_state=42,
            stratify=y if y.nunique() > 1 else None
        )

        logger.info(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        return X_train_scaled, X_test_scaled, y_train, y_test, X_train, X_test

    def train(self, X_train, y_train):
        """
        Train RandomForest classifier.

        Args:
            X_train: Training features (scaled)
            y_train: Training labels
        """
        logger.info("Training RandomForest classifier...")

        # Initialize model with tuned hyperparameters
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'  # Handle imbalanced classes
        )

        # Train model
        self.model.fit(X_train, y_train)

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train, y_train, cv=5)
        logger.info(f"Cross-validation scores: {cv_scores}")
        logger.info(f"Mean CV score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

        self.metrics['cv_scores'] = cv_scores.tolist()
        self.metrics['cv_mean'] = float(cv_scores.mean())
        self.metrics['cv_std'] = float(cv_scores.std())

    def evaluate(self, X_test, y_test):
        """
        Evaluate model performance.

        Args:
            X_test: Test features (scaled)
            y_test: Test labels
        """
        logger.info("Evaluating model...")

        # Predictions
        y_pred = self.model.predict(X_test)
        y_prob = self.model.predict_proba(X_test)[:, 1] if len(self.model.classes_) == 2 else None

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        logger.info(f"Accuracy: {accuracy:.4f}")
        logger.info(f"Precision: {precision:.4f}")
        logger.info(f"Recall: {recall:.4f}")
        logger.info(f"F1 Score: {f1:.4f}")

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        logger.info(f"Confusion Matrix:\n{cm}")

        # Classification report
        report = classification_report(y_test, y_pred, output_dict=True)
        logger.info(f"Classification Report:\n{classification_report(y_test, y_pred)}")

        # Store metrics
        self.metrics.update({
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'confusion_matrix': cm.tolist(),
            'classification_report': report,
            'test_samples': len(y_test),
            'training_date': datetime.now().isoformat()
        })

    def calculate_feature_importance(self, feature_names):
        """
        Calculate and store feature importance.

        Args:
            feature_names: List of feature column names
        """
        logger.info("Calculating feature importance...")

        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1]

        self.feature_importance = {
            'features': []
        }

        for idx in indices:
            self.feature_importance['features'].append({
                'feature': feature_names[idx],
                'importance': float(importances[idx]),
                'rank': int(np.where(indices == idx)[0][0] + 1)
            })

        logger.info("Feature importance ranking:")
        for feat in self.feature_importance['features']:
            logger.info(f"  {feat['rank']}. {feat['feature']}: {feat['importance']:.4f}")

    def save_model(self):
        """Save trained model and artifacts"""
        logger.info("Saving model and artifacts...")

        # Create models directory if needed
        models_dir = os.path.dirname(get_model_path())
        os.makedirs(models_dir, exist_ok=True)

        # Save model with scaler
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'version': '1.0.0',
            'trained_at': datetime.now().isoformat()
        }

        with open(get_model_path(), 'wb') as f:
            pickle.dump(model_data, f)
        logger.info(f"Model saved to {get_model_path()}")

        # Save metrics
        self.metrics['model_type'] = 'RandomForestClassifier'
        self.metrics['n_estimators'] = 100
        self.metrics['max_depth'] = 10
        self.metrics['features_used'] = len(self.feature_columns)
        self.metrics['feature_columns'] = self.feature_columns

        with open(get_metrics_path(), 'w') as f:
            json.dump(self.metrics, f, indent=2)
        logger.info(f"Metrics saved to {get_metrics_path()}")

        # Save feature importance
        self.feature_importance['model_version'] = '1.0.0'
        self.feature_importance['calculated_at'] = datetime.now().isoformat()

        with open(get_feature_importance_path(), 'w') as f:
            json.dump(self.feature_importance, f, indent=2)
        logger.info(f"Feature importance saved to {get_feature_importance_path()}")

    def train_pipeline(self, df: pd.DataFrame = None):
        """
        Full training pipeline.

        Args:
            df: Optional pre-prepared DataFrame. If None, will extract features.

        Returns:
            dict: Training results including metrics
        """
        logger.info("Starting training pipeline...")

        # Get training data
        if df is None:
            engineer = FeatureEngineer()
            df = engineer.prepare_training_data()

        if df.empty:
            raise ValueError("No training data available")

        # Store training info
        self.metrics['training_samples'] = len(df)

        # Prepare data
        X_train, X_test, y_train, y_test, X_train_raw, X_test_raw = self.prepare_data(df)

        # Train model
        self.train(X_train, y_train)

        # Evaluate
        self.evaluate(X_test, y_test)

        # Feature importance
        self.calculate_feature_importance(self.feature_columns)

        # Save artifacts
        self.save_model()

        logger.info("Training pipeline complete!")

        return {
            'metrics': self.metrics,
            'feature_importance': self.feature_importance
        }


def main():
    """Run the training pipeline"""
    print("=" * 60)
    print("UDIGAP Model Training")
    print("=" * 60)

    trainer = PriorityModelTrainer()

    try:
        results = trainer.train_pipeline()

        print("\n" + "=" * 60)
        print("TRAINING COMPLETE")
        print("=" * 60)

        print(f"\nModel Performance:")
        print(f"  Accuracy:  {results['metrics']['accuracy']:.1%}")
        print(f"  Precision: {results['metrics']['precision']:.1%}")
        print(f"  Recall:    {results['metrics']['recall']:.1%}")
        print(f"  F1 Score:  {results['metrics']['f1_score']:.1%}")

        print(f"\nCross-Validation:")
        print(f"  Mean: {results['metrics']['cv_mean']:.1%}")
        print(f"  Std:  {results['metrics']['cv_std']:.4f}")

        print(f"\nFeature Importance:")
        for feat in results['feature_importance']['features']:
            print(f"  {feat['rank']}. {feat['feature']}: {feat['importance']:.4f}")

        print(f"\nArtifacts saved to ml/models/")
        print("  - priority_model.pkl")
        print("  - model_metrics.json")
        print("  - feature_importance.json")

        print("\n✅ Model training successful!")

    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
