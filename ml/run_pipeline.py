#!/usr/bin/env python3
"""
UDIGAP ML Pipeline Runner

Runs the complete ML pipeline:
1. Feature engineering
2. Model training
3. Generate predictions
4. Store in PostGIS

Usage:
    python -m ml.run_pipeline
    # or
    python ml/run_pipeline.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.feature_engineering import FeatureEngineer
from ml.train_model import PriorityModelTrainer
from ml.predict_priorities import PriorityPredictor
from ml.utils import logger


def run_full_pipeline():
    """Run the complete ML pipeline"""

    print("=" * 70)
    print("UDIGAP ML PIPELINE")
    print("Machine Learning for Fiber Deployment Priority Prediction")
    print("=" * 70)

    try:
        # Step 1: Feature Engineering
        print("\n" + "=" * 70)
        print("STEP 1: FEATURE ENGINEERING")
        print("=" * 70)

        engineer = FeatureEngineer()
        training_data = engineer.prepare_training_data()

        print(f"\n✅ Extracted {len(training_data)} samples")
        print(f"   Features: {engineer.feature_names}")

        # Step 2: Model Training
        print("\n" + "=" * 70)
        print("STEP 2: MODEL TRAINING")
        print("=" * 70)

        trainer = PriorityModelTrainer()
        results = trainer.train_pipeline(training_data)

        print(f"\n✅ Model trained successfully")
        print(f"   Accuracy:  {results['metrics']['accuracy']:.1%}")
        print(f"   Precision: {results['metrics']['precision']:.1%}")
        print(f"   Recall:    {results['metrics']['recall']:.1%}")
        print(f"   F1 Score:  {results['metrics']['f1_score']:.1%}")

        # Step 3: Generate Predictions
        print("\n" + "=" * 70)
        print("STEP 3: GENERATE PREDICTIONS")
        print("=" * 70)

        predictor = PriorityPredictor()
        predictions = predictor.run_prediction_pipeline()

        print(f"\n✅ Generated {len(predictions)} predictions")
        print(f"   Priority Distribution:")
        print(f"   {predictions['priority_category'].value_counts().to_string()}")

        # Summary
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)

        print("\n📊 Artifacts saved:")
        print("   - ml/models/priority_model.pkl")
        print("   - ml/models/model_metrics.json")
        print("   - ml/models/feature_importance.json")
        print("   - ml/models/training_data.csv")

        print("\n🗄️ Database tables updated:")
        print("   - fiber_priority_zones (predictions)")
        print("   - priority_zones_summary (view)")
        print("   - top_priority_zones (view)")

        print("\n🌐 API endpoints available at http://localhost:8000:")
        print("   - GET /analytics/fiber_priorities")
        print("   - GET /analytics/feature_importance")
        print("   - GET /analytics/model_metrics")
        print("   - GET /analytics/priority_summary")
        print("   - GET /analytics/predictions/geojson")
        print("   - POST /analytics/retrain_model")

        print("\n📈 Top 5 Priority Areas:")
        top_5 = predictions.nlargest(5, 'priority_score')[
            ['state_name', 'lga_name', 'population', 'priority_score', 'priority_category']
        ]
        print(top_5.to_string(index=False))

        print("\n" + "=" * 70)
        print("✅ ML PIPELINE COMPLETED SUCCESSFULLY!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_full_pipeline()
    sys.exit(0 if success else 1)
