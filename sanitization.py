
"""
Input Sanitization and Format Conversion for DFS Optimizer

This module provides robust input sanitization functions to handle various CSV input formats
and ensure they match the pydfs-lineup-optimizer's expected formats.

Key Features:
- Percentage string conversion ("75%" → 0.75)
- Number formatting with commas ("1,000" → 1000)
- Position name standardization and mapping
- Type validation and conversion
- Range checking for numeric values
- Graceful handling of missing/invalid data
- Comprehensive logging for format conversions
"""

import logging
import re
from typing import Any, Optional, Union, Dict, List
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

# Position mapping for NFL FanDuel Classic format
POSITION_MAPPING = {
    # Standard position codes (case-insensitive)
    'qb': 'QB', 'quarterback': 'QB', 'passer': 'QB',
    'rb': 'RB', 'runningback': 'RB', 'running back': 'RB', 'rusher': 'RB',
    'wr': 'WR', 'widereceiver': 'WR', 'wide receiver': 'WR', 'receiver': 'WR',
    'te': 'TE', 'tightend': 'TE', 'tight end': 'TE',
    'flex': 'FLEX', 'flexible': 'FLEX',
    # FanDuel expects 'D' for defense, not 'DEF'
    'def': 'D', 'defense': 'D', 'd': 'D', 'dst': 'D', 'def': 'D',
    
    # Position combinations (handle flexible positions)
    'wr/flex': 'WR/FLEX', 'wr-flex': 'WR/FLEX', 'wr_flex': 'WR/FLEX',
    'rb/flex': 'RB/FLEX', 'rb-flex': 'RB/FLEX', 'rb_flex': 'RB/FLEX',
    'te/flex': 'TE/FLEX', 'te-flex': 'TE/FLEX', 'te_flex': 'TE/FLEX',
}

# Valid FanDuel NFL positions - FanDuel expects 'D' for defense
VALID_POSITIONS = {'QB', 'RB', 'WR', 'TE', 'FLEX', 'D'}


def sanitize_percentage(value: Any) -> float:
    """
    Convert percentage strings to decimal floats.
    
    Args:
        value: Input value (string, float, int, etc.)
        
    Returns:
        float: Decimal representation (e.g., "7.50%" → 0.075, "0.75" → 0.75)
        
    Examples:
        >>> sanitize_percentage("7.50%")
        0.075
        >>> sanitize_percentage("0.75")
        0.75
        >>> sanitize_percentage(0.0825)
        0.0825
    """
    if pd.isna(value) or value is None:
        logger.warning("Empty percentage value encountered, using 0.0 as fallback")
        return 0.0
    
    original_value = value
    
    try:
        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            
            # Remove percentage sign and convert
            if '%' in value:
                value = value.replace('%', '')
                # Convert to float and divide by 100
                result = float(value) / 100.0
                logger.debug(f"Converted percentage string '{original_value}' to decimal {result}")
                return result
            else:
                # Already a decimal string
                result = float(value)
                logger.debug(f"Converted decimal string '{original_value}' to float {result}")
                return result
        
        # Handle numeric values directly
        elif isinstance(value, (int, float)):
            # If it's a large number (likely percentage without % sign), assume it's a percentage
            if value > 1.0:
                result = value / 100.0
                logger.debug(f"Converted large number {original_value} to percentage decimal {result}")
                return result
            else:
                # Already a decimal
                return float(value)
        
        else:
            logger.warning(f"Unexpected percentage value type: {type(value)} for value '{original_value}', converting to float")
            return float(value)
            
    except (ValueError, TypeError) as e:
        logger.error(f"Error converting percentage value '{original_value}': {str(e)}, using 0.0 as fallback")
        return 0.0


def sanitize_salary(value: Any) -> int:
    """
    Convert salary values to integers, handling various formats.
    
    Args:
        value: Input value (string with commas, float, int, etc.)
        
    Returns:
        int: Integer salary value
        
    Examples:
        >>> sanitize_salary("1,000")
        1000
        >>> sanitize_salary(1500.0)
        1500
        >>> sanitize_salary("$1,500")
        1500
    """
    if pd.isna(value) or value is None:
        logger.warning("Empty salary value encountered, using 0 as fallback")
        return 0
    
    original_value = value
    
    try:
        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            
            # Remove currency symbols and commas
            value = re.sub(r'[\$,]', '', value)
            
            # Convert to float first to handle decimal points, then to int
            result = int(float(value))
            logger.debug(f"Converted salary string '{original_value}' to integer {result}")
            return result
        
        # Handle numeric values directly
        elif isinstance(value, (int, float)):
            result = int(value)
            logger.debug(f"Converted numeric salary {original_value} to integer {result}")
            return result
        
        else:
            logger.warning(f"Unexpected salary value type: {type(value)} for value '{original_value}', converting to int")
            return int(value)
            
    except (ValueError, TypeError) as e:
        logger.error(f"Error converting salary value '{original_value}': {str(e)}, using 0 as fallback")
        return 0


def sanitize_fppg(value: Any) -> float:
    """
    Convert FPPG (Fantasy Points Per Game) values to floats.
    
    Args:
        value: Input value (string, float, int, etc.)
        
    Returns:
        float: FPPG value
        
    Examples:
        >>> sanitize_fppg("15.5")
        15.5
        >>> sanitize_fppg(12.0)
        12.0
        >>> sanitize_fppg("10")
        10.0
    """
    if pd.isna(value) or value is None:
        logger.warning("Empty FPPG value encountered, using 0.0 as fallback")
        return 0.0
    
    original_value = value
    
    try:
        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            result = float(value)
            logger.debug(f"Converted FPPG string '{original_value}' to float {result}")
            return result
        
        # Handle numeric values directly
        elif isinstance(value, (int, float)):
            result = float(value)
            logger.debug(f"Converted numeric FPPG {original_value} to float {result}")
            return result
        
        else:
            logger.warning(f"Unexpected FPPG value type: {type(value)} for value '{original_value}', converting to float")
            return float(value)
            
    except (ValueError, TypeError) as e:
        logger.error(f"Error converting FPPG value '{original_value}': {str(e)}, using 0.0 as fallback")
        return 0.0


def sanitize_position(value: Any) -> str:
    """
    Convert position values to standardized FanDuel format.
    
    Args:
        value: Input value (string with various position formats)
        
    Returns:
        str: Standardized position string
        
    Examples:
        >>> sanitize_position("qb")
        'QB'
        >>> sanitize_position("Quarterback")
        'QB'
        >>> sanitize_position("WR/FLEX")
        'WR/FLEX'
    """
    if pd.isna(value) or value is None:
        logger.warning("Empty position value encountered, using 'FLEX' as fallback")
        return 'FLEX'
    
    original_value = value
    
    try:
        # Handle string values
        if isinstance(value, str):
            value = value.strip().lower()
            
            # Check if it's already a valid position
            if value.upper() in VALID_POSITIONS:
                result = value.upper()
                logger.debug(f"Position '{original_value}' is already valid: {result}")
                return result
            
            # Check position mapping
            if value in POSITION_MAPPING:
                result = POSITION_MAPPING[value]
                logger.debug(f"Mapped position '{original_value}' to standard format: {result}")
                return result
            
            # Handle position combinations (e.g., "WR/FLEX")
            if '/' in value or '-' in value or '_' in value:
                # Split and map each part
                separator = '/' if '/' in value else ('-' if '-' in value else '_')
                parts = [part.strip().lower() for part in value.split(separator)]
                mapped_parts = [POSITION_MAPPING.get(part, part.upper()) for part in parts]
                result = '/'.join(mapped_parts)
                logger.debug(f"Converted position combination '{original_value}' to: {result}")
                return result
            
            # If no mapping found, try to capitalize and validate
            result = value.upper()
            if result in VALID_POSITIONS:
                logger.debug(f"Capitalized position '{original_value}' to valid format: {result}")
                return result
            else:
                logger.warning(f"Unknown position format '{original_value}', using 'FLEX' as fallback")
                return 'FLEX'
        
        # Handle non-string values
        else:
            logger.warning(f"Non-string position value: {type(value)} for value '{original_value}', converting to string")
            return sanitize_position(str(value))
            
    except Exception as e:
        logger.error(f"Error converting position value '{original_value}': {str(e)}, using 'FLEX' as fallback")
        return 'FLEX'


def sanitize_random(value: Any) -> float:
    """
    Convert random values to floats between 0 and 1.
    
    Args:
        value: Input value (percentage string, float, int, etc.)
        
    Returns:
        float: Random value between 0 and 1
        
    Examples:
        >>> sanitize_random("7.50%")
        0.075
        >>> sanitize_random(0.0825)
        0.0825
        >>> sanitize_random("0.1")
        0.1
    """
    if pd.isna(value) or value is None:
        logger.warning("Empty random value encountered, using 0.0 as fallback")
        return 0.0
    
    original_value = value
    
    try:
        # Use percentage sanitization since random values are often percentages
        result = sanitize_percentage(value)
        
        # Ensure the result is between 0 and 1
        if result < 0:
            logger.warning(f"Random value {result} is negative, clamping to 0")
            result = 0.0
        elif result > 1:
            logger.warning(f"Random value {result} is greater than 1, clamping to 1")
            result = 1.0
            
        logger.debug(f"Converted random value '{original_value}' to: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error converting random value '{original_value}': {str(e)}, using 0.0 as fallback")
        return 0.0


def sanitize_player_id(value: Any) -> str:
    """
    Convert player ID values to strings.
    
    Args:
        value: Input value (int, float, string, etc.)
        
    Returns:
        str: String representation of player ID
        
    Examples:
        >>> sanitize_player_id(12345)
        '12345'
        >>> sanitize_player_id("12345")
        '12345'
        >>> sanitize_player_id(123.0)
        '123'
    """
    if pd.isna(value) or value is None:
        logger.warning("Empty player ID value encountered, using '0' as fallback")
        return '0'
    
    original_value = value
    
    try:
        # Handle float values by converting to int first to remove decimal
        if isinstance(value, float):
            if value.is_integer():
                result = str(int(value))
            else:
                result = str(value)
        else:
            # Convert to string and strip whitespace
            result = str(value).strip()
        
        logger.debug(f"Converted player ID '{original_value}' to string: '{result}'")
        return result
        
    except Exception as e:
        logger.error(f"Error converting player ID '{original_value}': {str(e)}, using '0' as fallback")
        return '0'


def sanitize_name(value: Any) -> str:
    """
    Convert name values to cleaned strings.
    
    Args:
        value: Input value (string with potential whitespace issues)
        
    Returns:
        str: Cleaned name string
        
    Examples:
        >>> sanitize_name("  John Smith  ")
        'John Smith'
        >>> sanitize_name(None)
        ''
    """
    if pd.isna(value) or value is None:
        logger.debug("Empty name value encountered, using empty string as fallback")
        return ''
    
    original_value = value
    
    try:
        # Convert to string and strip whitespace
        result = str(value).strip()
        logger.debug(f"Cleaned name '{original_value}' to: '{result}'")
        return result
        
    except Exception as e:
        logger.error(f"Error converting name value '{original_value}': {str(e)}, using empty string as fallback")
        return ''


def validate_numeric_range(value: float, min_val: float = None, max_val: float = None, field_name: str = "value") -> bool:
    """
    Validate that a numeric value is within specified range.
    
    Args:
        value: Numeric value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Name of the field for logging
        
    Returns:
        bool: True if value is within range, False otherwise
    """
    if min_val is not None and value < min_val:
        logger.warning(f"{field_name} value {value} is below minimum {min_val}")
        return False
    
    if max_val is not None and value > max_val:
        logger.warning(f"{field_name} value {value} is above maximum {max_val}")
        return False
    
    return True


def sanitize_player_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply comprehensive sanitization to a player data row.
    
    Args:
        row: Dictionary containing player data
        
    Returns:
        Dict[str, Any]: Sanitized player data
    """
    sanitized_row = row.copy()
    
    # Apply sanitization to each field
    if 'B_Id' in sanitized_row:
        sanitized_row['B_Id'] = sanitize_player_id(sanitized_row['B_Id'])
    
    if 'B_Position' in sanitized_row:
        sanitized_row['B_Position'] = sanitize_position(sanitized_row['B_Position'])
    
    if 'B_Nickname' in sanitized_row:
        sanitized_row['B_Nickname'] = sanitize_name(sanitized_row['B_Nickname'])
    
    if 'B_Salary' in sanitized_row:
        sanitized_row['B_Salary'] = sanitize_salary(sanitized_row['B_Salary'])
    
    if 'A_ppg_projection' in sanitized_row:
        sanitized_row['A_ppg_projection'] = sanitize_fppg(sanitized_row['A_ppg_projection'])
    
    if 'B_Team' in sanitized_row:
        sanitized_row['B_Team'] = sanitize_name(sanitized_row['B_Team'])
    
    if 'B_Opponent' in sanitized_row:
        sanitized_row['B_Opponent'] = sanitize_name(sanitized_row['B_Opponent'])
    
    if 'Random' in sanitized_row:
        sanitized_row['Random'] = sanitize_random(sanitized_row['Random'])
    
    logger.debug(f"Sanitized player row: ID={sanitized_row.get('B_Id', 'Unknown')}")
    return sanitized_row


def get_sanitization_summary() -> Dict[str, int]:
    """
    Get summary statistics for sanitization operations.
    
    Returns:
        Dict[str, int]: Dictionary with sanitization statistics
    """
    # This would track sanitization operations in a production environment
    # For now, return a placeholder structure
    return {
        'total_sanitizations': 0,
        'percentage_conversions': 0,
        'salary_conversions': 0,
        'position_mappings': 0,
        'fallback_used': 0
    }


# Convenience function for testing
def test_sanitization():
    """Test the sanitization functions with various input formats."""
    test_cases = [
        # Percentage conversions
        ("7.50%", sanitize_percentage, 0.075),
        ("0.75", sanitize_percentage, 0.75),
        (0.0825, sanitize_percentage, 0.0825),
        
        # Salary conversions
        ("1,000", sanitize_salary, 1000),
        ("$1,500", sanitize_salary, 1500),
        (1500.0, sanitize_salary, 1500),
        
        # Position conversions
        ("qb", sanitize_position, "QB"),
        ("Quarterback", sanitize_position, "QB"),
        ("WR/FLEX", sanitize_position, "WR/FLEX"),
        ("wr-flex", sanitize_position, "WR/FLEX"),
        
        # FPPG conversions
        ("15.5", sanitize_fppg, 15.5),
        (12.0, sanitize_fppg, 12.0),
        ("10", sanitize_fppg, 10.0),
        
        # Random value conversions
        ("7.50%", sanitize_random, 0.075),
        (0.0825, sanitize_random, 0.0825),
        ("0.1", sanitize_random, 0.1),
        
        # Player ID conversions
        (12345, sanitize_player_id, "12345"),
        ("12345", sanitize_player_id, "12345"),
        (123.0, sanitize_player_id, "123"),
    ]
    
    print("Running sanitization tests...")
    passed = 0
    failed = 0
    
    for input_value, sanitize_func, expected in test_cases:
        try:
            result = sanitize_func(input_value)
            if result == expected:
                print(f"✓ PASS: {sanitize_func.__name__}({input_value!r}) = {result}")
                passed += 1
            else:
                print(f"✗ FAIL: {sanitize_func.__name__}({input_value!r}) = {result} (expected {expected})")
                failed += 1
        except Exception as e:
            print(f"✗ ERROR: {sanitize_func.__name__}({input_value!r}) raised {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\nTest Results: {passed} passed, {failed} failed")
    return passed, failed


if __name__ == "__main__":
    test_sanitization()
