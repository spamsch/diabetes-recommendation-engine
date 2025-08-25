#!/usr/bin/env python3
"""Test script for IOB shortcut functionality"""

import sys
import os
import re
from typing import Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_iob_number_detection():
    """Test the IOB number detection regex"""
    
    def _is_iob_number(text: str) -> Optional[float]:
        """Check if text is a plain number (IOB shortcut). Supports both comma and dot as decimal separator."""
        # Remove any whitespace
        text = text.strip()
        
        # Pattern matches: digits optionally followed by decimal separator and more digits
        # Or just digits followed by decimal separator
        pattern = r'^(\d+[.,]\d*|\d*[.,]\d+|\d+)$'
        match = re.match(pattern, text)
        
        if match:
            try:
                # Replace comma with dot for float conversion
                number_str = match.group(1).replace(',', '.')
                value = float(number_str)
                
                # Reasonable range check for IOB (0 to 20 units)
                if 0.0 <= value <= 20.0:
                    return value
            except ValueError:
                pass
        
        return None
    
    # Test cases
    test_cases = [
        # Valid IOB numbers
        ("2.4", 2.4),
        ("2,4", 2.4), 
        ("0.2", 0.2),
        ("0,2", 0.2),
        ("10", 10.0),
        ("0", 0.0),
        ("15.5", 15.5),
        ("15,5", 15.5),
        (".5", 0.5),
        (",5", 0.5),
        ("5.", 5.0),
        ("5,", 5.0),  # Valid: comma at end means 5.0
        
        # Invalid cases
        ("abc", None),
        ("/iob 2.4", None),
        ("2.4 units", None),
        ("hello 2.4", None),
        ("25.0", None),  # Too high
        ("-1.0", None),  # Negative
        ("", None),
        (".", None),
        (",", None),
        ("2.4.5", None),  # Multiple decimal points
        ("2,4,5", None),  # Multiple commas
    ]
    
    print("Testing IOB number detection...")
    all_passed = True
    
    for test_input, expected in test_cases:
        result = _is_iob_number(test_input)
        status = "✓" if result == expected else "✗"
        
        if result != expected:
            all_passed = False
            print(f"{status} '{test_input}' -> {result} (expected {expected})")
        else:
            print(f"{status} '{test_input}' -> {result}")
    
    if all_passed:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
    
    # Use assert instead of return for pytest compatibility
    assert all_passed, "Some IOB number detection tests failed"

if __name__ == "__main__":
    test_iob_number_detection()