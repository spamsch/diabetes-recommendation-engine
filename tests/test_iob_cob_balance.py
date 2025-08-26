"""
Test IOB/COB balance scenarios to ensure proper recommendations.
When insulin and carbs are both active, the system should recommend monitoring
for stability rather than panic about glucose not falling.
"""
import pytest
import os
from datetime import datetime, timedelta

from src.database import GlucoseReading
from src.analysis.recommendations import RecommendationEngine
from src.config import Settings


class TestIOBCOBBalance:
    """Test IOB and COB balance recommendation scenarios"""
    
    @pytest.fixture
    def settings(self):
        """Create test settings"""
        # Save original environment
        original_env = {}
        test_vars = [
            'DEXCOM_USERNAME', 'DEXCOM_PASSWORD', 'HIGH_GLUCOSE_THRESHOLD',
            'LOW_GLUCOSE_THRESHOLD', 'INSULIN_EFFECTIVENESS',
            'IOB_THRESHOLD_HIGH', 'TARGET_GLUCOSE', 'INSULIN_UNIT_RATIO'
        ]
        
        for var in test_vars:
            if var in os.environ:
                original_env[var] = os.environ[var]
        
        # Set test environment
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
    
    def create_readings(self, base_value=139, trend='up', num_readings=6):
        """Create test glucose readings"""
        base_time = datetime.now()
        readings = []
        
        for i in range(num_readings):
            reading_time = base_time - timedelta(minutes=5 * (num_readings-1-i))
            # Create slight variation around base value
            variation = (i - num_readings//2) * 0.5
            glucose_value = base_value + variation
            
            reading = GlucoseReading(
                timestamp=reading_time,
                value=glucose_value,
                trend=trend
            )
            readings.append(reading)
        
        return readings
    
    def test_balanced_iob_cob_monitoring(self, settings):
        """Test that high IOB with high COB generates monitoring recommendation"""
        engine = RecommendationEngine(settings)
        readings = self.create_readings(139, 'up')
        
        trend_analysis = {
            'trend': 'up',
            'rate_of_change': 0.9,
            'confidence': 'medium'
        }
        
        prediction = {
            'predicted_value': 143.5,
            'confidence': 'medium',
            'method': 'linear_extrapolation'
        }
        
        # High IOB + High COB scenario
        iob_cob_data = {
            'iob': {'total_iob': 3.9, 'is_override': True},
            'cob': {'total_cob': 23.0},
            'impact': {'net_effect': -73.5, 'predicted_glucose': 66}
        }
        
        recommendations = engine.get_recommendations(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should have monitoring and IOB status recommendations
        assert len(recommendations) >= 2
        
        # Find IOB status recommendation
        iob_rec = next((r for r in recommendations if r['type'] == 'iob_status'),
                       None)
        assert iob_rec is not None
        assert iob_rec['urgency'] == 'low'
        assert 'balancing' in iob_rec['message']
        assert 'expect stability' in iob_rec['message']
        
        # Find monitoring recommendation  
        monitor_rec = next((r for r in recommendations 
                           if r['type'] == 'monitoring'), None)
        assert monitor_rec is not None
        assert 'insulin' in monitor_rec['message']
        assert 'carbs' in monitor_rec['message']
        
        print(f"✅ IOB+COB Balance Test Passed")
        print(f"   IOB Status: {iob_rec['urgency']} - {iob_rec['message']}")
        print(f"   Monitoring: {monitor_rec['message']}")
    
    def test_high_iob_no_cob_warning(self, settings):
        """Test that high IOB without COB generates warning"""
        engine = RecommendationEngine(settings)
        readings = self.create_readings(139, 'no_change')
        
        trend_analysis = {
            'trend': 'no_change', 
            'rate_of_change': 0.1,
            'confidence': 'medium'
        }
        
        prediction = {
            'predicted_value': 140,
            'confidence': 'medium'
        }
        
        # High IOB + Low COB scenario
        iob_cob_data = {
            'iob': {'total_iob': 3.9, 'is_override': True},
            'cob': {'total_cob': 2.0},  # Low COB
            'impact': {'net_effect': -150, 'predicted_glucose': -11}
        }
        
        recommendations = engine.get_recommendations(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Find IOB status recommendation
        iob_rec = next((r for r in recommendations if r['type'] == 'iob_status'),
                       None)
        assert iob_rec is not None
        assert iob_rec['urgency'] == 'high'
        assert 'not falling as expected' in iob_rec['message']
        
        print(f"✅ High IOB No COB Test Passed")
        print(f"   IOB Status: {iob_rec['urgency']} - {iob_rec['message']}")
    
    def test_no_insulin_recommendations_with_balance(self, settings):
        """Test that insulin recommendations are suppressed with IOB/COB balance"""
        engine = RecommendationEngine(settings)
        readings = self.create_readings(200, 'up')  # High glucose
        
        trend_analysis = {
            'trend': 'up',
            'rate_of_change': 1.2,
            'confidence': 'high'
        }
        
        prediction = {
            'predicted_value': 205,
            'confidence': 'high'
        }
        
        # Balanced IOB + COB scenario with high glucose
        iob_cob_data = {
            'iob': {'total_iob': 2.5, 'is_override': True},
            'cob': {'total_cob': 30.0},
            'impact': {'net_effect': -50, 'predicted_glucose': 150}
        }
        
        recommendations = engine.get_recommendations(
            readings, trend_analysis, prediction, iob_cob_data
        )
        
        # Should NOT have insulin recommendations due to high IOB
        insulin_recs = [r for r in recommendations if r['type'] == 'insulin']
        assert len(insulin_recs) == 0, "Should not recommend insulin with high IOB"
        
        print(f"✅ No Insulin with Balance Test Passed")
        print(f"   Insulin recommendations suppressed due to high IOB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])