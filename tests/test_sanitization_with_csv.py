"""
Test script for CSV sanitization with real data

This script tests the sanitization functions with actual CSV files
to ensure they handle various input formats correctly.
"""

import pandas as pd
import logging
import sys
import os

# Add the parent directory to Python path to import sanitization module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sanitization import (
    sanitize_player_row,
    sanitize_percentage,
    sanitize_salary,
    sanitize_position,
    sanitize_fppg,
    sanitize_random,
    sanitize_player_id
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_csv_sanitization(csv_file_path):
    """
    Test sanitization functions with a real CSV file.
    
    Args:
        csv_file_path (str): Path to the CSV file to test
    """
    logger.info(f"Testing sanitization with CSV file: {csv_file_path}")
    
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file_path)
        logger.info(f"Original CSV shape: {df.shape}")
        logger.info(f"Original columns: {list(df.columns)}")
        
        # Check for required columns
        required_columns = ['B_Id', 'B_Position', 'B_Nickname', 'B_Salary', 'A_ppg_projection', 'B_Team', 'B_Opponent', 'Random']
        available_columns = [col for col in required_columns if col in df.columns]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        logger.info(f"Available required columns: {available_columns}")
        if missing_columns:
            logger.warning(f"Missing required columns: {missing_columns}")
        
        # Test sanitization on first few rows
        test_rows = min(5, len(df))
        logger.info(f"Testing sanitization on first {test_rows} rows...")
        
        for i in range(test_rows):
            row = df.iloc[i].to_dict()
            logger.info(f"\n--- Row {i+1} ---")
            logger.info(f"Original data:")
            for col in available_columns:
                if col in row:
                    logger.info(f"  {col}: {row[col]} (type: {type(row[col])})")
            
            # Apply sanitization
            sanitized_row = sanitize_player_row(row)
            
            logger.info(f"Sanitized data:")
            for col in available_columns:
                if col in sanitized_row:
                    logger.info(f"  {col}: {sanitized_row[col]} (type: {type(sanitized_row[col])})")
        
        # Test specific column conversions
        logger.info("\n--- Testing specific column conversions ---")
        
        # Test Random column (percentage strings)
        if 'Random' in df.columns:
            random_values = df['Random'].head(3)
            logger.info("Random column conversions:")
            for i, value in enumerate(random_values):
                original = value
                sanitized = sanitize_random(value)
                logger.info(f"  {original} -> {sanitized} (type: {type(sanitized)})")
        
        # Test Position column
        if 'B_Position' in df.columns:
            position_values = df['B_Position'].head(3)
            logger.info("Position column conversions:")
            for i, value in enumerate(position_values):
                original = value
                sanitized = sanitize_position(value)
                logger.info(f"  {original} -> {sanitized} (type: {type(sanitized)})")
        
        # Test Salary column
        if 'B_Salary' in df.columns:
            salary_values = df['B_Salary'].head(3)
            logger.info("Salary column conversions:")
            for i, value in enumerate(salary_values):
                original = value
                sanitized = sanitize_salary(value)
                logger.info(f"  {original} -> {sanitized} (type: {type(sanitized)})")
        
        # Test FPPG column
        if 'A_ppg_projection' in df.columns:
            fppg_values = df['A_ppg_projection'].head(3)
            logger.info("FPPG column conversions:")
            for i, value in enumerate(fppg_values):
                original = value
                sanitized = sanitize_fppg(value)
                logger.info(f"  {original} -> {sanitized} (type: {type(sanitized)})")
        
        logger.info(f"✅ CSV sanitization test completed successfully for {csv_file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing CSV sanitization: {str(e)}")
        return False

def compare_csv_files(original_file, processed_file):
    """
    Compare original and processed CSV files to verify sanitization.
    
    Args:
        original_file (str): Path to original CSV file
        processed_file (str): Path to processed CSV file
    """
    logger.info(f"Comparing original and processed CSV files...")
    
    try:
        # Read both files
        original_df = pd.read_csv(original_file)
        processed_df = pd.read_csv(processed_file)
        
        logger.info(f"Original file shape: {original_df.shape}")
        logger.info(f"Processed file shape: {processed_df.shape}")
        
        # Compare key columns
        key_columns = ['B_Id', 'B_Position', 'B_Salary', 'A_ppg_projection', 'Random']
        
        for col in key_columns:
            if col in original_df.columns and col in processed_df.columns:
                logger.info(f"\n--- {col} column comparison ---")
                
                # Sample first few values
                original_sample = original_df[col].head(3).tolist()
                processed_sample = processed_df[col].head(3).tolist()
                
                for i, (orig, proc) in enumerate(zip(original_sample, processed_sample)):
                    logger.info(f"  Row {i+1}: {orig} -> {proc}")
        
        logger.info("✅ CSV comparison completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error comparing CSV files: {str(e)}")
        return False

def main():
    """Main function to run CSV sanitization tests."""
    logger.info("Starting CSV sanitization tests...")
    
    # Test with different CSV files
    test_files = [
        "NFL-DIRTY2.csv",
        "NFL6-CLEAN2.csv", 
        "processed_lineup_data.csv"
    ]
    
    for test_file in test_files:
        try:
            test_csv_sanitization(test_file)
            logger.info(f"✅ Successfully tested {test_file}")
        except FileNotFoundError:
            logger.warning(f"⚠️  File not found: {test_file}")
        except Exception as e:
            logger.error(f"❌ Error testing {test_file}: {str(e)}")
    
    logger.info("CSV sanitization tests completed!")

if __name__ == "__main__":
    main()