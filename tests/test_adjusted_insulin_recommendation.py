"""Test for adjusted insulin recommendation parameters"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.database.glucose_db import GlucoseReading
from src.analysis.recommendations import InsulinRecommendation


class TestAdjustedInsulinRecommendation:
    """Test insulin recommendations with adjusted parameters"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create mock settings
        self.settings = Mock()
        self.settings.high_glucose_threshold = 180
        self.settings.target_glucose = 120
        self.settings.insulin_effectiveness = 40
        self.settings.insulin_unit_ratio = 0.2
        self.settings.iob_threshold_high = 2.0
        self.settings.carb_to_glucose_ratio = 3.5
        self.settings.enable_insulin_recommendations = True
        
        self.insulin_recommender = InsulinRecommendation(self.settings)

    def test_insufficient_insulin_scenario_reduced_recommendation(self):
        """Test that insufficient insulin scenario now recommends half the previous amount"""
        # Create scenario similar to user's case:
        # Glucose 211, IOB 2.9, COB 16.4, fast rising at 2.5 mg/dL/min
        current_time = datetime.now()
        
        readings = [
            GlucoseReading(current_time, 211, "fast_up"),
            GlucoseReading(current_time - timedelta(minutes=5), 200, "up"),
            GlucoseReading(current_time - timedelta(minutes=10), 182, "up"),
            GlucoseReading(current_time - timedelta(minutes=15), 145, "up"),
        ]
        
        trend_analysis = {
            'trend': 'fast_up',
            'rate_of_change': 2.5
        }
        
        prediction = {'predicted_value': 250}
        
        # IOB/COB data that triggers insufficient insulin scenario
        iob_cob_data = {
            'iob': {'total_iob': 2.9},
            'cob': {'total_cob': 16.4}
        }
        
        # Analyze recommendation
        result = self.insulin_recommender.analyze(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should get a recommendation (not None)
        assert result is not None
        assert result['type'] == 'insulin'
        
        # Calculate expected insulin with new parameters
        # carb_effect = 16.4 * 3.5 = 57.4
        # additional_insulin_needed = 57.4 * 0.075 = 4.305
        # insulin_units = min(4.305, 0.5) = 0.5
        expected_insulin = 0.5
        
        actual_insulin = result['parameters']['recommended_units']
        assert actual_insulin == expected_insulin, (
            f"Expected {expected_insulin} units, got {actual_insulin} units. "
            f"This should be half the previous recommendation of ~1.0 units."
        )
        
        # Verify it's marked as insufficient insulin scenario
        assert 'carbs may be overwhelming current insulin' in result['message']

    def test_standard_correction_unchanged(self):
        """Test that standard correction calculations are not affected"""
        # Create scenario with high glucose, low IOB, no COB
        current_time = datetime.now()
        
        readings = [
            GlucoseReading(current_time, 250, "up"),
            GlucoseReading(current_time - timedelta(minutes=5), 240, "up"),
            GlucoseReading(current_time - timedelta(minutes=10), 235, "stable"),
            GlucoseReading(current_time - timedelta(minutes=15), 230, "stable"),
        ]
        
        trend_analysis = {
            'trend': 'up',
            'rate_of_change': 1.0
        }
        
        prediction = {'predicted_value': 280}
        
        # Low IOB/COB - should use standard calculation
        iob_cob_data = {
            'iob': {'total_iob': 0.5},  # Low IOB
            'cob': {'total_cob': 2.0}   # Low COB
        }
        
        # Analyze recommendation
        result = self.insulin_recommender.analyze(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should get a recommendation
        assert result is not None
        assert result['type'] == 'insulin'
        
        # Standard calculation:
        # target_glucose = 120
        # excess_glucose = 250 - 120 = 130
        # iob_adjustment = 0.5 * 40 = 20
        # adjusted_excess = 130 - 20 = 110
        # insulin_units = (110 / 40) * 0.2 = 0.55
        # Capped between 0.1 and 2.0
        expected_insulin = 0.6  # Rounded to 1 decimal place
        
        actual_insulin = result['parameters']['recommended_units']
        assert abs(actual_insulin - expected_insulin) < 0.1, (
            f"Standard correction calculation changed unexpectedly. "
            f"Expected ~{expected_insulin}, got {actual_insulin}"
        )
        
        # Should NOT contain insufficient insulin message
        assert 'carbs may be overwhelming current insulin' not in result['message']

    def test_no_recommendation_with_sufficient_iob(self):
        """Test that no recommendation is given when IOB should handle the situation"""
        current_time = datetime.now()
        
        readings = [
            GlucoseReading(current_time, 200, "up"),
            GlucoseReading(current_time - timedelta(minutes=5), 190, "up"),
            GlucoseReading(current_time - timedelta(minutes=10), 185, "stable"),
            GlucoseReading(current_time - timedelta(minutes=15), 180, "stable"),
        ]
        
        trend_analysis = {
            'trend': 'up',
            'rate_of_change': 1.0
        }
        
        prediction = {'predicted_value': 220}
        
        # High IOB with some COB but not fast rising - should not recommend
        iob_cob_data = {
            'iob': {'total_iob': 2.5},  # High IOB
            'cob': {'total_cob': 10.0}  # Some COB
        }
        
        # Analyze recommendation  
        result = self.insulin_recommender.analyze(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should not get recommendation - IOB should handle this
        assert result is None

    def test_calculation_with_different_carb_ratio(self):
        """Test that carb_to_glucose_ratio setting is used correctly"""
        # Create mock settings with different carb ratio
        mock_settings = Mock()
        mock_settings.high_glucose_threshold = 180
        mock_settings.target_glucose = 120
        mock_settings.insulin_effectiveness = 40
        mock_settings.insulin_unit_ratio = 0.2
        mock_settings.iob_threshold_high = 2.0
        mock_settings.carb_to_glucose_ratio = 4.0  # Different ratio
        mock_settings.enable_insulin_recommendations = True
        
        insulin_recommender = InsulinRecommendation(mock_settings)
        
        current_time = datetime.now()
        readings = [
            GlucoseReading(current_time, 211, "fast_up"),
            GlucoseReading(current_time - timedelta(minutes=5), 200, "up"),
            GlucoseReading(current_time - timedelta(minutes=10), 182, "up"),
            GlucoseReading(current_time - timedelta(minutes=15), 145, "up"),
        ]
        
        trend_analysis = {
            'trend': 'fast_up',
            'rate_of_change': 2.5
        }
        
        prediction = {'predicted_value': 250}
        
        iob_cob_data = {
            'iob': {'total_iob': 2.9},
            'cob': {'total_cob': 16.4}
        }
        
        result = insulin_recommender.analyze(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should get a recommendation
        assert result is not None
        
        # With carb_to_glucose_ratio = 4.0:
        # carb_effect = 16.4 * 4.0 = 65.6
        # additional_insulin_needed = 65.6 * 0.075 = 4.92
        # insulin_units = min(4.92, 0.5) = 0.5
        assert result['parameters']['recommended_units'] == 0.5