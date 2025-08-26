"""
Test insufficient insulin scenario where glucose is rising fast despite high IOB+COB.
This should generate a low-priority insulin recommendation for supplemental coverage.
Requires glucose >180 mg/dL to trigger the recommendation.
"""
import pytest
import os
from datetime import datetime, timedelta

from src.database import GlucoseReading
from src.analysis.recommendations import RecommendationEngine
from src.config import Settings


class TestInsufficientInsulinScenario:
    """Test insufficient insulin for carbs scenarios"""
    
    @pytest.fixture
    def settings(self):
        """Create test settings"""
        original_env = {}
        test_vars = [
            'DEXCOM_USERNAME', 'DEXCOM_PASSWORD', 'HIGH_GLUCOSE_THRESHOLD',
            'LOW_GLUCOSE_THRESHOLD', 'INSULIN_EFFECTIVENESS',
            'IOB_THRESHOLD_HIGH', 'TARGET_GLUCOSE', 'INSULIN_UNIT_RATIO'
        ]
        
        for var in test_vars:
            if var in os.environ:
                original_env[var] = os.environ[var]
        
        test_env = {
            'DEXCOM_USERNAME': 'test',
            'DEXCOM_PASSWORD': 'test',
            'HIGH_GLUCOSE_THRESHOLD': '180',
            'LOW_GLUCOSE_THRESHOLD': '70',
            'INSULIN_EFFECTIVENESS': '40.0',
            'IOB_THRESHOLD_HIGH': '2.0',
            'TARGET_GLUCOSE': '120',
            'INSULIN_UNIT_RATIO': '0.2'
        }
        
        for key, value in test_env.items():
            os.environ[key] = value
        
        yield Settings()
        
        # Restore environment
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        for var, value in original_env.items():
            os.environ[var] = value
    
    def create_fast_rising_readings(self, current_glucose=162):
        """Create glucose readings showing fast upward trend"""
        base_time = datetime.now()
        readings = []
        
        # Create readings for fast rising trend (most recent first)
        values = [current_glucose - i for i in range(6)]  # 162, 161, 160, 159, 158, 157
        
        for i, value in enumerate(values):
            reading_time = base_time - timedelta(minutes=i * 5)  
            reading = GlucoseReading(
                timestamp=reading_time,
                value=value,
                trend='fast_up'
            )
            readings.append(reading)
        
        return readings
    
    def test_insufficient_insulin_for_carbs(self, settings):
        """Test that insufficient insulin scenario generates supplemental insulin rec
        
        Scenario: High glucose (>180) rising fast despite high IOB+COB
        Expected: Low-priority additional insulin recommendation
        """
        engine = RecommendationEngine(settings)
        
        # Create scenario: 190 mg/dL rising fast despite high IOB+COB  
        readings = self.create_fast_rising_readings(190)
        
        trend_analysis = {
            'trend': 'fast_up',
            'rate_of_change': 2.4,  # Fast rise
            'confidence': 'high'
        }
        
        prediction = {
            'predicted_value': 188.7,
            'confidence': 'medium',
            'method': 'linear_extrapolation'
        }
        
        # High IOB + COB scenario - carbs overwhelming insulin
        iob_cob_data = {
            'iob': {'total_iob': 3.9, 'is_override': True},
            'cob': {'total_cob': 21.5},
            'impact': {'net_effect': -78.8, 'predicted_glucose': 83}
        }
        
        recommendations = engine.get_recommendations(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        print(f"\n=== INSUFFICIENT INSULIN TEST ===")
        print(f"Glucose: {readings[0].value} mg/dL (fast up, +{trend_analysis['rate_of_change']} mg/dL/min)")
        print(f"IOB: {iob_cob_data['iob']['total_iob']}u, COB: {iob_cob_data['cob']['total_cob']}g")
        print(f"Recommendations: {len(recommendations)}")
        
        # Find insulin recommendation
        insulin_recs = [r for r in recommendations if r['type'] == 'insulin']
        
        if insulin_recs:
            insulin_rec = insulin_recs[0]
            print(f"✅ Insulin rec: {insulin_rec['parameters']['recommended_units']}u")
            print(f"   Priority: {insulin_rec['priority']}")
            print(f"   Message: {insulin_rec['message'][:80]}...")
            
            # Validate recommendation
            assert insulin_rec['priority'] == 3, "Should be low priority (3)"
            assert 'additional' in insulin_rec['message'], "Should mention additional insulin"
            assert insulin_rec['parameters']['recommended_units'] <= 1.0, "Should be small dose"
            
        else:
            print("❌ No insulin recommendation generated")
            
            # Print details for debugging
            for i, rec in enumerate(recommendations):
                print(f"  {i+1}. [{rec['type']}] {rec.get('urgency', rec.get('priority', 'N/A'))}")
            
            # This should generate an insulin recommendation
            assert len(insulin_recs) > 0, "Expected insulin recommendation for insufficient insulin scenario"
    
    def test_no_insulin_with_stable_iob_cob(self, settings):
        """Test that stable glucose with IOB+COB doesn't generate insulin rec"""
        engine = RecommendationEngine(settings)
        
        # Create stable glucose scenario
        readings = []
        base_time = datetime.now()
        
        for i in range(6):
            reading_time = base_time - timedelta(minutes=i * 5)
            reading = GlucoseReading(
                timestamp=reading_time,
                value=140,  # Stable
                trend='no_change'
            )
            readings.append(reading)
        
        trend_analysis = {
            'trend': 'no_change',
            'rate_of_change': 0.1,
            'confidence': 'high'
        }
        
        prediction = {'predicted_value': 140, 'confidence': 'high'}
        
        iob_cob_data = {
            'iob': {'total_iob': 3.9, 'is_override': True},
            'cob': {'total_cob': 21.5},
            'impact': {'net_effect': -78.8, 'predicted_glucose': 61}
        }
        
        recommendations = engine.get_recommendations(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should NOT have insulin recommendations
        insulin_recs = [r for r in recommendations if r['type'] == 'insulin']
        assert len(insulin_recs) == 0, "Should not recommend insulin for stable glucose with IOB+COB"
        
        print(f"✅ No insulin recommended for stable glucose with IOB+COB balance")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])