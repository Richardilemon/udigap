#!/usr/bin/env python3
"""
UDIGAP Priority Prediction Module

Generates predictions for all areas and stores them in PostGIS.
Creates the fiber_priority_zones table with spatial data.

Usage:
    python -m ml.predict_priorities
"""

import os
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

from .utils import get_db_connection, execute_query, logger, get_model_path
from .feature_engineering import FeatureEngineer


class PriorityPredictor:
    """Generates fiber priority predictions"""

    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = None

    def load_model(self):
        """Load trained model from disk"""
        model_path = get_model_path()

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Run 'python -m ml.train_model' first."
            )

        logger.info(f"Loading model from {model_path}")

        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_columns = model_data['feature_columns']

        logger.info(f"Model loaded (version: {model_data.get('version', 'unknown')})")

    def prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Prepare features for prediction.

        Args:
            df: DataFrame with feature columns

        Returns:
            Scaled feature array
        """
        # Ensure all feature columns exist
        for col in self.feature_columns:
            if col not in df.columns:
                logger.warning(f"Missing column {col}, filling with 0")
                df[col] = 0

        X = df[self.feature_columns].fillna(0)
        X_scaled = self.scaler.transform(X)

        return X_scaled

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate predictions for all areas.

        Args:
            df: DataFrame with features

        Returns:
            DataFrame with predictions added
        """
        logger.info(f"Generating predictions for {len(df)} areas...")

        # Prepare features
        X = self.prepare_features(df)

        # Get predictions
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)

        # Add predictions to dataframe
        df = df.copy()
        df['needs_fiber_pred'] = predictions

        # Get probability of needing fiber (class 1)
        if len(self.model.classes_) == 2:
            df['priority_probability'] = probabilities[:, 1]
        else:
            df['priority_probability'] = probabilities.max(axis=1)

        # Calculate priority score (0-100)
        df['priority_score'] = (df['priority_probability'] * 100).round(1)

        # Assign category based on score
        df['priority_category'] = df['priority_score'].apply(
            lambda x: 'HIGH' if x >= 70 else ('MEDIUM' if x >= 40 else 'LOW')
        )

        logger.info(f"Predictions complete. Distribution: {df['priority_category'].value_counts().to_dict()}")

        return df

    def create_priority_table(self):
        """Create the fiber_priority_zones table in PostGIS"""
        logger.info("Creating fiber_priority_zones table...")

        create_table_sql = """
            DROP TABLE IF EXISTS fiber_priority_zones CASCADE;

            CREATE TABLE fiber_priority_zones (
                id SERIAL PRIMARY KEY,
                state_name VARCHAR(100),
                lga_name VARCHAR(100),
                population INTEGER,
                population_density DECIMAL(12, 2),
                fiber_count INTEGER,
                fiber_per_100k DECIMAL(12, 4),
                distance_to_fiber_km DECIMAL(10, 2),
                economic_index DECIMAL(10, 2),
                priority_score DECIMAL(5, 1),
                priority_category VARCHAR(20),
                priority_probability DECIMAL(5, 4),
                geom GEOMETRY(Point, 4326),
                created_at TIMESTAMP DEFAULT NOW(),
                model_version VARCHAR(20) DEFAULT '1.0.0'
            );

            CREATE INDEX idx_priority_zones_geom ON fiber_priority_zones USING GIST(geom);
            CREATE INDEX idx_priority_zones_state ON fiber_priority_zones(state_name);
            CREATE INDEX idx_priority_zones_category ON fiber_priority_zones(priority_category);
            CREATE INDEX idx_priority_zones_score ON fiber_priority_zones(priority_score DESC);
        """

        conn = get_db_connection(dict_cursor=False)
        cur = conn.cursor()

        try:
            cur.execute(create_table_sql)
            conn.commit()
            logger.info("Table fiber_priority_zones created successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create table: {e}")
            raise
        finally:
            cur.close()
            conn.close()

    def save_predictions(self, df: pd.DataFrame):
        """
        Save predictions to PostGIS table.

        Args:
            df: DataFrame with predictions
        """
        logger.info(f"Saving {len(df)} predictions to database...")

        conn = get_db_connection(dict_cursor=False)
        cur = conn.cursor()

        insert_sql = """
            INSERT INTO fiber_priority_zones (
                state_name, lga_name, population, population_density,
                fiber_count, fiber_per_100k, distance_to_fiber_km,
                economic_index, priority_score, priority_category,
                priority_probability, geom
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            );
        """

        try:
            for _, row in df.iterrows():
                cur.execute(insert_sql, (
                    row.get('state_name', 'Unknown'),
                    row.get('lga_name', 'Unknown'),
                    int(row.get('population', 0)),
                    float(row.get('population_density', 0)),
                    int(row.get('fiber_count', 0)),
                    float(row.get('fiber_per_100k', 0)),
                    float(row.get('distance_to_fiber_km', 0)),
                    float(row.get('economic_index', 0)),
                    float(row.get('priority_score', 0)),
                    row.get('priority_category', 'LOW'),
                    float(row.get('priority_probability', 0)),
                    float(row.get('longitude', 8.6753)),
                    float(row.get('latitude', 9.0820))
                ))

            conn.commit()
            logger.info(f"Successfully saved {len(df)} predictions")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save predictions: {e}")
            raise
        finally:
            cur.close()
            conn.close()

    def create_priority_view(self):
        """Create a view for easy querying of priority zones"""
        logger.info("Creating priority zones view...")

        view_sql = """
            DROP VIEW IF EXISTS priority_zones_summary CASCADE;

            CREATE VIEW priority_zones_summary AS
            SELECT
                state_name,
                COUNT(*) as total_areas,
                SUM(CASE WHEN priority_category = 'HIGH' THEN 1 ELSE 0 END) as high_priority,
                SUM(CASE WHEN priority_category = 'MEDIUM' THEN 1 ELSE 0 END) as medium_priority,
                SUM(CASE WHEN priority_category = 'LOW' THEN 1 ELSE 0 END) as low_priority,
                ROUND(AVG(priority_score)::numeric, 1) as avg_priority_score,
                SUM(population) as total_population,
                ROUND(AVG(fiber_per_100k)::numeric, 2) as avg_fiber_coverage
            FROM fiber_priority_zones
            GROUP BY state_name
            ORDER BY avg_priority_score DESC;

            DROP VIEW IF EXISTS top_priority_zones CASCADE;

            CREATE VIEW top_priority_zones AS
            SELECT
                id,
                state_name,
                lga_name,
                population,
                fiber_per_100k,
                distance_to_fiber_km,
                priority_score,
                priority_category,
                ST_Y(geom) as latitude,
                ST_X(geom) as longitude
            FROM fiber_priority_zones
            WHERE priority_category IN ('HIGH', 'MEDIUM')
            ORDER BY priority_score DESC;
        """

        conn = get_db_connection(dict_cursor=False)
        cur = conn.cursor()

        try:
            cur.execute(view_sql)
            conn.commit()
            logger.info("Views created successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create views: {e}")
        finally:
            cur.close()
            conn.close()

    def run_prediction_pipeline(self):
        """
        Full prediction pipeline.

        1. Load trained model
        2. Extract features for all areas
        3. Generate predictions
        4. Save to PostGIS
        5. Create views
        """
        logger.info("Starting prediction pipeline...")

        # Load model
        self.load_model()

        # Extract features
        engineer = FeatureEngineer()
        df = engineer.extract_features()

        if df.empty:
            raise ValueError("No data available for prediction")

        # Add economic index
        df = engineer.add_economic_index(df)

        # Generate predictions
        df = self.predict(df)

        # Create table
        self.create_priority_table()

        # Save predictions
        self.save_predictions(df)

        # Create views
        self.create_priority_view()

        logger.info("Prediction pipeline complete!")

        return df

    def get_predictions(self, state: str = None, limit: int = None) -> list:
        """
        Retrieve predictions from database.

        Args:
            state: Optional state filter
            limit: Optional result limit

        Returns:
            List of prediction dictionaries
        """
        query = """
            SELECT
                id,
                state_name,
                lga_name,
                population,
                ROUND(population_density::numeric, 2) as population_density,
                fiber_count,
                ROUND(fiber_per_100k::numeric, 2) as fiber_per_100k,
                ROUND(distance_to_fiber_km::numeric, 2) as distance_to_fiber_km,
                ROUND(priority_score::numeric, 1) as priority_score,
                priority_category,
                ST_Y(geom) as latitude,
                ST_X(geom) as longitude,
                created_at
            FROM fiber_priority_zones
        """

        conditions = []
        if state and state != 'All':
            conditions.append(f"state_name = '{state}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY priority_score DESC"

        if limit:
            query += f" LIMIT {limit}"

        return execute_query(query)


def main():
    """Run the prediction pipeline"""
    print("=" * 60)
    print("UDIGAP Priority Prediction")
    print("=" * 60)

    predictor = PriorityPredictor()

    try:
        df = predictor.run_prediction_pipeline()

        print("\n" + "=" * 60)
        print("PREDICTION COMPLETE")
        print("=" * 60)

        print(f"\nGenerated predictions for {len(df)} areas")

        print(f"\nPriority Distribution:")
        print(df['priority_category'].value_counts().to_string())

        print(f"\nTop 10 Priority Areas:")
        top_10 = df.nlargest(10, 'priority_score')[
            ['state_name', 'lga_name', 'population', 'priority_score', 'priority_category']
        ]
        print(top_10.to_string(index=False))

        print(f"\nData saved to PostGIS table: fiber_priority_zones")
        print(f"Views created: priority_zones_summary, top_priority_zones")

        print("\nQuery examples:")
        print("  SELECT * FROM priority_zones_summary;")
        print("  SELECT * FROM top_priority_zones LIMIT 10;")
        print("  SELECT * FROM fiber_priority_zones WHERE priority_category = 'HIGH';")

        print("\n✅ Prediction pipeline successful!")

    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\nRun the training pipeline first:")
        print("  python -m ml.train_model")

    except Exception as e:
        print(f"\n❌ Prediction failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
