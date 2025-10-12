#!/usr/bin/env python3
"""
Analyze the CSV data to identify potential issues
"""

import pandas as pd
import numpy as np
from inputs import PROGRESSIVE_FACTOR, MEDIAN_RANDOM, RANDOM_FACTOR

print("Data Analysis for SmartRandomStrategy Issues")
print("=" * 50)

# Load the CSV data
df = pd.read_csv('NFL-DIRTY2.csv')

print(f"CSV data shape: {df.shape}")
print(f"Configuration: PROGRESSIVE_FACTOR={PROGRESSIVE_FACTOR}, MEDIAN_RANDOM={MEDIAN_RANDOM}, RANDOM_FACTOR={RANDOM_FACTOR}")

# Analyze FPPG data
print("\nFPPG Analysis:")
print(f"  Range: {df['A_ppg_projection'].min():.2f} to {df['A_ppg_projection'].max():.2f}")
print(f"  Mean: {df['A_ppg_projection'].mean():.2f}")
print(f"  Median: {df['A_ppg_projection'].median():.2f}")
print(f"  Std Dev: {df['A_ppg_projection'].std():.2f}")

# Check for problematic FPPG values
zero_fppg = (df['A_ppg_projection'] == 0).sum()
negative_fppg = (df['A_ppg_projection'] < 0).sum()
nan_fppg = df['A_ppg_projection'].isna().sum()

print(f"  Zero values: {zero_fppg}")
print(f"  Negative values: {negative_fppg}")
print(f"  NaN values: {nan_fppg}")

# Analyze Random values
print("\nRandom Values Analysis:")
print(f"  Range: {df['Random'].min():.4f} to {df['Random'].max():.4f}")
print(f"  Mean: {df['Random'].mean():.4f}")
print(f"  Median: {df['Random'].median():.4f}")

# Check for problematic Random values
zero_random = (df['Random'] == 0).sum()
negative_random = (df['Random'] < 0).sum()
nan_random = df['Random'].isna().sum()
out_of_range_random = ((df['Random'] < 0) | (df['Random'] > 1)).sum()

print(f"  Zero values: {zero_random}")
print(f"  Negative values: {negative_random}")
print(f"  NaN values: {nan_random}")
print(f"  Out of range (not 0-1): {out_of_range_random}")

# Test SmartRandomStrategy with this data
print("\nTesting SmartRandomStrategy with actual data...")
from smart_random import SmartRandomStrategy

# Create dictionaries for the strategy
player_fppg_dict = {}
random_values_dict = {}

for _, row in df.iterrows():
    player_id = str(row['B_Id'])
    player_fppg_dict[player_id] = row['A_ppg_projection']
    random_values_dict[player_id] = row['Random']

print(f"  Player FPPG dict size: {len(player_fppg_dict)}")
print(f"  Random values dict size: {len(random_values_dict)}")

# Test the strategy
try:
    strategy = SmartRandomStrategy(player_fppg_dict, random_values_dict)
    print("  ✓ Strategy created successfully")
    
    # Test percentile calculation
    percentiles = list(strategy.player_percentiles.values())
    print(f"  Percentile range: {min(percentiles):.3f} to {max(percentiles):.3f}")
    
    # Test scaled factors
    scaled_factors = []
    for percentile in percentiles:
        scaled_factor = strategy._get_scaled_random_factor(percentile)
        scaled_factors.append(scaled_factor)
    
    print(f"  Scaled factor range: {min(scaled_factors):.3f} to {max(scaled_factors):.3f}")
    
    # Test deviations
    deviations = []
    for player_id, percentile in list(strategy.player_percentiles.items())[:20]:  # Test first 20
        base_random = random_values_dict[player_id]
        scaled_factor = strategy._get_scaled_random_factor(percentile)
        deviation = strategy._get_skewed_random_value(base_random, scaled_factor)
        deviations.append(deviation)
    
    print(f"  Deviation range: {min(deviations):.3f} to {max(deviations):.3f}")
    print(f"  Deviation mean: {np.mean(deviations):.3f}")
    
    # Check for extreme deviations
    extreme_positive = sum(1 for d in deviations if d > 1.0)
    extreme_negative = sum(1 for d in deviations if d < -0.95)
    print(f"  Deviations > 1.0: {extreme_positive}")
    print(f"  Deviations < -0.95: {extreme_negative}")
    
except Exception as e:
    print(f"  ✗ Error in SmartRandomStrategy: {e}")
    import traceback
    traceback.print_exc()

print("\nAnalysis complete!")