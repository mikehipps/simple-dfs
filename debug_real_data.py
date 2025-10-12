#!/usr/bin/env python3
"""
Debug script to test SmartRandomStrategy with real CSV data
"""

import pandas as pd
import numpy as np
import logging
from smart_random import SmartRandomStrategy
from pydfs_lineup_optimizer import get_optimizer, Site, Sport
from pydfs_lineup_optimizer.fantasy_points_strategy import ProgressiveFantasyPointsStrategy

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_real_data():
    """Load the real CSV data that's causing issues"""
    try:
        df = pd.read_csv('NFL-DIRTY2.csv')
        logger.info(f"Loaded CSV with {len(df)} players")
        
        # Check for problematic data
        logger.info("Checking for problematic FPPG values:")
        logger.info(f"  FPPG range: {df['FPPG'].min():.2f} to {df['FPPG'].max():.2f}")
        logger.info(f"  FPPG mean: {df['FPPG'].mean():.2f}")
        logger.info(f"  FPPG median: {df['FPPG'].median():.2f}")
        
        # Check for NaN/inf values
        nan_count = df['FPPG'].isna().sum()
        inf_count = np.isinf(df['FPPG']).sum()
        logger.info(f"  NaN FPPG values: {nan_count}")
        logger.info(f"  Infinite FPPG values: {inf_count}")
        
        # Check for zero/negative values
        zero_count = (df['FPPG'] == 0).sum()
        negative_count = (df['FPPG'] < 0).sum()
        logger.info(f"  Zero FPPG values: {zero_count}")
        logger.info(f"  Negative FPPG values: {negative_count}")
        
        return df
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        return None

def test_smart_random_with_real_data():
    """Test SmartRandomStrategy with real player data"""
    logger.info("Testing SmartRandomStrategy with real data")
    logger.info("=" * 50)
    
    df = load_real_data()
    if df is None:
        return False
    
    try:
        # Create player FPPG dictionary
        player_fppg_dict = {}
        for _, row in df.iterrows():
            player_id = f"{row['Name']}_{row['Position']}"
            player_fppg_dict[player_id] = row['FPPG']
        
        # Create random values dictionary
        random_values_dict = {}
        for player_id in player_fppg_dict.keys():
            random_values_dict[player_id] = np.random.random()
        
        # Test SmartRandomStrategy
        logger.info("Creating SmartRandomStrategy...")
        strategy = SmartRandomStrategy(player_fppg_dict, random_values_dict)
        
        logger.info("✓ Strategy created successfully")
        logger.info(f"  Player count: {len(strategy.player_percentiles)}")
        logger.info(f"  MEDIAN_RANDOM: {strategy.median_random}")
        logger.info(f"  RANDOM_FACTOR: {strategy.random_factor}")
        
        # Test percentile calculation
        logger.info("Testing percentile calculation...")
        percentiles = list(strategy.player_percentiles.values())
        logger.info(f"  Percentile range: {min(percentiles):.3f} to {max(percentiles):.3f}")
        logger.info(f"  Percentile mean: {np.mean(percentiles):.3f}")
        
        # Test scaled factors
        logger.info("Testing scaled factors...")
        scaled_factors = []
        for percentile in percentiles:
            scaled_factor = strategy._get_scaled_random_factor(percentile)
            scaled_factors.append(scaled_factor)
        
        logger.info(f"  Scaled factor range: {min(scaled_factors):.3f} to {max(scaled_factors):.3f}")
        logger.info(f"  Scaled factor mean: {np.mean(scaled_factors):.3f}")
        
        # Test deviations
        logger.info("Testing deviations...")
        deviations = []
        for i, (player_id, percentile) in enumerate(list(strategy.player_percentiles.items())[:50]):  # Test first 50
            base_random = random_values_dict[player_id]
            scaled_factor = strategy._get_scaled_random_factor(percentile)
            deviation = strategy._get_skewed_random_value(base_random, scaled_factor)
            deviations.append(deviation)
            
            if i < 10:  # Log first 10 for debugging
                logger.debug(f"  {player_id}: base={base_random:.3f}, scaled={scaled_factor:.3f}, dev={deviation:.3f}")
        
        logger.info(f"  Deviation range: {min(deviations):.3f} to {max(deviations):.3f}")
        logger.info(f"  Deviation mean: {np.mean(deviations):.3f}")
        
        # Check for problematic deviations
        extreme_positive = sum(1 for d in deviations if d > 1.0)
        extreme_negative = sum(1 for d in deviations if d < -0.95)
        logger.info(f"  Deviations > 1.0: {extreme_positive}")
        logger.info(f"  Deviations < -0.95: {extreme_negative}")
        
        # Test with actual optimizer
        logger.info("Testing with actual optimizer...")
        try:
            optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
            optimizer.load_players_from_csv('NFL-DIRTY2.csv')
            
            # Test SmartRandomStrategy
            logger.info("Testing lineup generation with SmartRandomStrategy...")
            lineups = optimizer.optimize(n=1, randomness=True)
            logger.info("✓ SmartRandomStrategy lineup generation successful")
            
        except Exception as e:
            logger.error(f"✗ SmartRandomStrategy lineup generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error in SmartRandomStrategy test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_progressive_with_real_data():
    """Test ProgressiveFantasyPointsStrategy with real data for comparison"""
    logger.info("\nTesting ProgressiveFantasyPointsStrategy with real data")
    logger.info("=" * 50)
    
    try:
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
        optimizer.load_players_from_csv('NFL-DIRTY2.csv')
        
        # Test Progressive strategy
        logger.info("Testing lineup generation with ProgressiveFantasyPointsStrategy...")
        lineups = optimizer.optimize(n=1)
        logger.info("✓ ProgressiveFantasyPointsStrategy lineup generation successful")
        return True
        
    except Exception as e:
        logger.error(f"✗ ProgressiveFantasyPointsStrategy lineup generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("SmartRandomStrategy Real Data Debug")
    logger.info("=" * 50)
    
    # Test both strategies
    smart_random_success = test_smart_random_with_real_data()
    progressive_success = test_progressive_with_real_data()
    
    logger.info("\n" + "=" * 50)
    logger.info("SUMMARY:")
    logger.info(f"  SmartRandomStrategy: {'✓ SUCCESS' if smart_random_success else '✗ FAILED'}")
    logger.info(f"  ProgressiveFantasyPointsStrategy: {'✓ SUCCESS' if progressive_success else '✗ FAILED'}")
    
    if smart_random_success and progressive_success:
        logger.info("✓ Both strategies working correctly")
    elif progressive_success and not smart_random_success:
        logger.info("⚠️ Progressive works but SmartRandom fails - this is the issue to fix")
    else:
        logger.info("✗ Both strategies failing - check CSV data")