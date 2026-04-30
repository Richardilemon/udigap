#!/usr/bin/env python3
"""
UDIGAP Feature Engineering Module

Extracts features from PostGIS database for ML model training.
Calculates spatial metrics like distance to fiber, coverage ratios, etc.

Usage:
    python -m ml.feature_engineering
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

from .utils import get_db_connection, execute_query, logger


class FeatureEngineer:
    """Feature engineering for fiber priority prediction"""

    def __init__(self):
        self.features = None
        self.feature_names = [
            'population',
            'population_density',
            'fiber_count',
            'fiber_per_100k',
            'distance_to_fiber_km',
            'area_sqkm',
            'economic_index'
        ]

    def extract_features(self) -> pd.DataFrame:
        """
        Extract features from PostGIS database.

        Returns:
            DataFrame with features for each LGA/area
        """
        logger.info("Starting feature extraction...")

        # Query to extract features
        # We'll use coverage_gaps view and calculate additional metrics
        query = """
            WITH fiber_distances AS (
                -- Calculate minimum distance to fiber for each population grid
                SELECT
                    pg.state_name,
                    pg.lga_name,
                    pg.population,
                    pg.population_density,
                    ST_Centroid(pg.geom) as centroid,
                    MIN(
                        ST_Distance(
                            ST_Centroid(pg.geom)::geography,
                            fi.geom::geography
                        ) / 1000
                    ) as min_distance_km
                FROM population_grid pg
                LEFT JOIN fiber_infrastructure fi ON 1=1
                WHERE fi.id IS NOT NULL
                GROUP BY pg.state_name, pg.lga_name, pg.population, pg.population_density, pg.geom
            ),
            state_fiber AS (
                -- Get fiber count by state for fallback
                SELECT
                    state_name,
                    COUNT(*) as fiber_count
                FROM fiber_infrastructure
                GROUP BY state_name
            ),
            lga_data AS (
                -- Combine with admin boundaries for LGA-level features
                SELECT
                    ab.state_name,
                    ab.name as lga_name,
                    ab.population,
                    ab.area_sqkm,
                    CASE
                        WHEN ab.area_sqkm > 0 THEN ab.population / ab.area_sqkm
                        ELSE 0
                    END as population_density,
                    ST_Centroid(ab.geom) as centroid
                FROM admin_boundaries ab
                WHERE ab.level = 'lga'
            ),
            combined AS (
                -- First try to get from population_grid
                SELECT
                    fd.state_name,
                    fd.lga_name,
                    fd.population,
                    fd.population_density,
                    COALESCE(sf.fiber_count, 0) as fiber_count,
                    CASE
                        WHEN fd.population > 0 THEN (COALESCE(sf.fiber_count, 0)::float / fd.population) * 100000
                        ELSE 0
                    END as fiber_per_100k,
                    COALESCE(fd.min_distance_km, 100) as distance_to_fiber_km,
                    0 as area_sqkm,
                    fd.centroid
                FROM fiber_distances fd
                LEFT JOIN state_fiber sf ON fd.state_name = sf.state_name

                UNION ALL

                -- Also get state-level data where we don't have LGA data
                SELECT
                    ab.state_name,
                    'State-Wide' as lga_name,
                    ab.population,
                    CASE
                        WHEN ab.area_sqkm > 0 THEN ab.population / ab.area_sqkm
                        ELSE 0
                    END as population_density,
                    COALESCE(sf.fiber_count, 0) as fiber_count,
                    CASE
                        WHEN ab.population > 0 THEN (COALESCE(sf.fiber_count, 0)::float / ab.population) * 100000
                        ELSE 0
                    END as fiber_per_100k,
                    50 as distance_to_fiber_km,  -- Default for state level
                    ab.area_sqkm,
                    ST_Centroid(ab.geom) as centroid
                FROM admin_boundaries ab
                LEFT JOIN state_fiber sf ON ab.state_name = sf.state_name
                WHERE ab.level = 'state'
            )
            SELECT
                state_name,
                lga_name,
                population,
                ROUND(population_density::numeric, 2) as population_density,
                fiber_count,
                ROUND(fiber_per_100k::numeric, 4) as fiber_per_100k,
                ROUND(distance_to_fiber_km::numeric, 2) as distance_to_fiber_km,
                ROUND(area_sqkm::numeric, 2) as area_sqkm,
                ST_Y(centroid) as latitude,
                ST_X(centroid) as longitude
            FROM combined
            WHERE population > 0
            ORDER BY state_name, lga_name;
        """

        try:
            results = execute_query(query)
            df = pd.DataFrame(results)

            if df.empty:
                logger.warning("No data returned from query. Using fallback method.")
                df = self._fallback_feature_extraction()

            logger.info(f"Extracted features for {len(df)} areas")
            return df

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            logger.info("Using fallback feature extraction...")
            return self._fallback_feature_extraction()

    def _fallback_feature_extraction(self) -> pd.DataFrame:
        """
        Fallback feature extraction using simpler queries.
        Used when the main query fails or returns no data.
        """
        logger.info("Running fallback feature extraction...")

        # Get state summary data
        state_query = """
            SELECT
                state_name,
                'State-Wide' as lga_name,
                population,
                fiber_features as fiber_count,
                ROUND(COALESCE(features_per_million, 0) * 0.1, 4) as fiber_per_100k,
                ST_Y(ST_Centroid(geom)) as latitude,
                ST_X(ST_Centroid(geom)) as longitude
            FROM state_summary
            WHERE population > 0;
        """

        results = execute_query(state_query)
        df = pd.DataFrame(results)

        if df.empty:
            logger.error("No data available for feature extraction")
            return pd.DataFrame()

        # Calculate additional features
        df['population_density'] = df['population'] / 1000  # Approximate
        df['distance_to_fiber_km'] = np.where(
            df['fiber_count'] > 0,
            np.maximum(5, 50 - df['fiber_count'] * 2),
            100
        )
        df['area_sqkm'] = df['population'] / df['population_density']

        # Also get LGA-level data from coverage_gaps if available
        lga_query = """
            SELECT
                state_name,
                lga_name,
                population,
                fiber_count,
                ROUND(COALESCE(fiber_per_100k, 0)::numeric, 4) as fiber_per_100k
            FROM coverage_gaps
            WHERE population > 0;
        """

        try:
            lga_results = execute_query(lga_query)
            if lga_results:
                lga_df = pd.DataFrame(lga_results)
                # Get coordinates from state data
                state_coords = df.set_index('state_name')[['latitude', 'longitude']].to_dict('index')

                lga_df['latitude'] = lga_df['state_name'].apply(
                    lambda x: state_coords.get(x, {}).get('latitude', 9.0820)
                )
                lga_df['longitude'] = lga_df['state_name'].apply(
                    lambda x: state_coords.get(x, {}).get('longitude', 8.6753)
                )

                # Add random offset for LGAs
                np.random.seed(42)
                lga_df['latitude'] += np.random.uniform(-0.3, 0.3, len(lga_df))
                lga_df['longitude'] += np.random.uniform(-0.3, 0.3, len(lga_df))

                # Calculate additional features
                lga_df['population_density'] = lga_df['population'] / 100
                lga_df['distance_to_fiber_km'] = np.where(
                    lga_df['fiber_count'] > 0,
                    np.maximum(2, 30 - lga_df['fiber_count'] * 5),
                    50
                )
                lga_df['area_sqkm'] = 500  # Approximate

                # Combine state and LGA data
                df = pd.concat([df, lga_df], ignore_index=True)
        except Exception as e:
            logger.warning(f"Could not get LGA data: {e}")

        return df

    def create_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create target labels for supervised learning.

        Labeling logic:
        - HIGH priority (needs_fiber=1): population > 100k AND fiber_per_100k < 10
        - MEDIUM-HIGH priority (needs_fiber=1): population > 50k AND fiber_per_100k < 20
        - LOW priority (needs_fiber=0): otherwise

        Args:
            df: DataFrame with features

        Returns:
            DataFrame with 'needs_fiber' and 'priority_category' columns added
        """
        logger.info("Creating target labels...")

        df = df.copy()

        # Create binary target
        df['needs_fiber'] = 0

        # High priority areas
        high_priority = (df['population'] > 100000) & (df['fiber_per_100k'] < 10)
        df.loc[high_priority, 'needs_fiber'] = 1

        # Medium-high priority areas
        medium_priority = (df['population'] > 50000) & (df['fiber_per_100k'] < 20)
        df.loc[medium_priority, 'needs_fiber'] = 1

        # Also consider distance to fiber
        far_from_fiber = df['distance_to_fiber_km'] > 30
        df.loc[far_from_fiber & (df['population'] > 20000), 'needs_fiber'] = 1

        # Create priority score (0-100)
        df['priority_score'] = self._calculate_priority_score(df)

        # Create priority category
        df['priority_category'] = df['priority_score'].apply(
            lambda x: 'HIGH' if x >= 70 else ('MEDIUM' if x >= 40 else 'LOW')
        )

        logger.info(f"Labels created: {df['needs_fiber'].sum()} high priority areas out of {len(df)}")
        logger.info(f"Priority distribution: {df['priority_category'].value_counts().to_dict()}")

        return df

    def _calculate_priority_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate priority score (0-100) based on multiple factors.

        Factors:
        - Population size (more people = higher priority)
        - Current fiber coverage (less coverage = higher priority)
        - Distance to fiber (farther = higher priority)
        """
        # Normalize each factor to 0-1 scale
        pop_score = df['population'] / df['population'].max()
        coverage_score = 1 - (df['fiber_per_100k'] / (df['fiber_per_100k'].max() + 1))
        distance_score = df['distance_to_fiber_km'] / (df['distance_to_fiber_km'].max() + 1)

        # Weighted combination
        weights = {
            'population': 0.30,
            'coverage': 0.45,
            'distance': 0.25
        }

        priority_score = (
            weights['population'] * pop_score +
            weights['coverage'] * coverage_score +
            weights['distance'] * distance_score
        ) * 100

        return priority_score.clip(0, 100).round(1)

    def add_economic_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add economic index proxy based on available data.

        Uses population density as a proxy for economic activity.
        In production, this would use actual economic data.
        """
        df = df.copy()

        # Normalize population density as economic proxy
        if 'population_density' in df.columns:
            max_density = df['population_density'].max()
            if max_density > 0:
                df['economic_index'] = (df['population_density'] / max_density * 100).clip(0, 100).round(2)
            else:
                df['economic_index'] = 50.0
        else:
            df['economic_index'] = 50.0

        return df

    def prepare_training_data(self) -> pd.DataFrame:
        """
        Full pipeline to prepare training data.

        Returns:
            DataFrame ready for model training
        """
        logger.info("Preparing training data...")

        # Extract features
        df = self.extract_features()

        if df.empty:
            raise ValueError("No features extracted. Check database connection and data.")

        # Add economic index
        df = self.add_economic_index(df)

        # Create labels
        df = self.create_labels(df)

        # Fill any missing values
        df = df.fillna({
            'population_density': 0,
            'fiber_per_100k': 0,
            'distance_to_fiber_km': 50,
            'area_sqkm': 100,
            'economic_index': 50
        })

        # Save to CSV for reference
        output_path = os.path.join(os.path.dirname(__file__), 'models', 'training_data.csv')
        df.to_csv(output_path, index=False)
        logger.info(f"Training data saved to {output_path}")

        self.features = df
        return df


def main():
    """Run feature engineering pipeline"""
    print("=" * 60)
    print("UDIGAP Feature Engineering")
    print("=" * 60)

    engineer = FeatureEngineer()
    df = engineer.prepare_training_data()

    print(f"\nExtracted {len(df)} samples with {len(df.columns)} features")
    print(f"\nFeature columns: {list(df.columns)}")
    print(f"\nSample data:")
    print(df.head(10).to_string())

    print(f"\nLabel distribution:")
    print(df['priority_category'].value_counts())

    print(f"\n✅ Feature engineering complete!")


if __name__ == "__main__":
    main()
