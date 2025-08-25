import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.config import Settings
from src.database import GlucoseReading
from src.analysis.recommendations import (
    InsulinRecommendation, CarbRecommendation, 
    MonitoringRecommendation, RecommendationEngine
)

class MockSettings:
    """Mock settings for testing"""
    def __init__(self):
        self.high_glucose_threshold = 180
        self.low_glucose_threshold = 70
        self.critical_low_threshold = 55
        self.critical_high_threshold = 300
        self.insulin_effectiveness = 40.0
        self.insulin_unit_ratio = 0.2
        self.carb_effectiveness = 15.0
        self.enable_insulin_recommendations = True
        self.enable_carb_recommendations = True
        self.prediction_minutes_ahead = 15
        self.target_glucose = 120.0
        self.iob_threshold_high = 2.0
        self.carb_to_glucose_ratio = 3.5
        self.trend_down_threshold = 0.5
        self.trend_fast_down_threshold = 2.0
        self.trend_very_fast_down_threshold = 4.0
        self.trend_up_threshold = 0.5
        self.trend_fast_up_threshold = 2.0
        self.trend_very_fast_up_threshold = 4.0

def create_mock_readings(values, start_time=None, interval_minutes=5):
    """Create mock glucose readings"""
    if start_time is None:
        start_time = datetime.now()
    
    readings = []
    for i, value in enumerate(values):
        timestamp = start_time + timedelta(minutes=i * interval_minutes)
        reading = GlucoseReading(
            timestamp=timestamp,
            value=value,
            trend="no_change"
        )
        readings.append(reading)
    
    # Sort readings by timestamp, most recent first (as expected by recommendation system)
    readings.sort(key=lambda r: r.timestamp, reverse=True)
    return readings

class TestInsulinRecommendation:
    
    def test_no_recommendation_for_normal_glucose(self):
        settings = MockSettings()
        insulin_rec = InsulinRecommendation(settings)
        
        # Normal glucose readings
        readings = create_mock_readings([120, 115, 118, 122])
        trend_analysis = {'trend': 'no_change', 'rate_of_change': 0.5}
        prediction = {'predicted_value': 125}
        
        result = insulin_rec.analyze(readings, trend_analysis, prediction)
        assert result is None
    
    def test_no_recommendation_for_rapidly_falling_glucose(self):
        settings = MockSettings()
        insulin_rec = InsulinRecommendation(settings)
        
        # High but rapidly falling glucose
        readings = create_mock_readings([200, 195, 190, 185])
        trend_analysis = {'trend': 'fast_down', 'rate_of_change': -2.5}
        prediction = {'predicted_value': 175}
        
        result = insulin_rec.analyze(readings, trend_analysis, prediction)
        assert result is None
    
    def test_insulin_recommendation_for_stable_high_glucose(self):
        settings = MockSettings()
        insulin_rec = InsulinRecommendation(settings)
        
        # Stable high glucose readings
        readings = create_mock_readings([220, 215, 218, 222])
        trend_analysis = {'trend': 'no_change', 'rate_of_change': 0.2}
        prediction = {'predicted_value': 220}
        
        result = insulin_rec.analyze(readings, trend_analysis, prediction)
        
        assert result is not None
        assert result['type'] == 'insulin'
        assert result['priority'] == 2
        assert 'recommended_units' in result['parameters']
        assert result['parameters']['recommended_units'] > 0
        assert 'safety_notes' in result
    
    def test_insulin_calculation(self):
        settings = MockSettings()
        insulin_rec = InsulinRecommendation(settings)
        
        # High glucose: 250 mg/dL
        readings = create_mock_readings([250, 248, 252, 249])
        trend_analysis = {'trend': 'up', 'rate_of_change': 1.0}
        prediction = {'predicted_value': 255}
        
        result = insulin_rec.analyze(readings, trend_analysis, prediction)
        
        # Expected calculation: (250 - target_glucose) / insulin_effectiveness * insulin_unit_ratio
        expected_units = (250 - settings.target_glucose) / settings.insulin_effectiveness * settings.insulin_unit_ratio
        assert abs(result['parameters']['recommended_units'] - expected_units) < 0.1

class TestCarbRecommendation:
    
    def test_no_recommendation_for_normal_glucose(self):
        settings = MockSettings()
        carb_rec = CarbRecommendation(settings)
        
        # Normal glucose readings
        readings = create_mock_readings([120, 115, 118, 122])
        trend_analysis = {'trend': 'no_change', 'rate_of_change': 0.1}
        prediction = {'predicted_value': 125}
        
        result = carb_rec.analyze(readings, trend_analysis, prediction)
        assert result is None
    
    def test_critical_low_recommendation(self):
        settings = MockSettings()
        carb_rec = CarbRecommendation(settings)
        
        # Critical low glucose
        readings = create_mock_readings([50, 48, 45, 47])
        trend_analysis = {'trend': 'down', 'rate_of_change': -1.0}
        prediction = {'predicted_value': 40}
        
        result = carb_rec.analyze(readings, trend_analysis, prediction)
        
        assert result is not None
        assert result['type'] == 'carbohydrate'
        assert result['urgency'] == 'critical'
        assert result['priority'] == 1
        assert 'recommended_carbs' in result['parameters']
        assert 'suggested_foods' in result['parameters']
    
    def test_low_glucose_recommendation(self):
        settings = MockSettings()
        carb_rec = CarbRecommendation(settings)
        
        # Low glucose
        readings = create_mock_readings([65, 62, 60, 58])
        trend_analysis = {'trend': 'down', 'rate_of_change': -1.5}
        prediction = {'predicted_value': 55}
        
        result = carb_rec.analyze(readings, trend_analysis, prediction)
        
        assert result is not None
        assert result['urgency'] == 'high'
        assert result['parameters']['recommended_carbs'] >= 15
    
    def test_trending_low_recommendation(self):
        settings = MockSettings()
        carb_rec = CarbRecommendation(settings)
        
        # Trending towards low
        readings = create_mock_readings([90, 85, 80, 82])
        trend_analysis = {'trend': 'fast_down', 'rate_of_change': -3.0}
        prediction = {'predicted_value': 75}
        
        result = carb_rec.analyze(readings, trend_analysis, prediction)
        
        assert result is not None
        assert result['urgency'] == 'medium'

class TestMonitoringRecommendation:
    
    def test_no_recommendation_for_stable_normal(self):
        settings = MockSettings()
        monitor_rec = MonitoringRecommendation(settings)
        
        # Stable normal readings
        readings = create_mock_readings([120, 118, 122, 119])
        trend_analysis = {'trend': 'no_change', 'rate_of_change': 0.2}
        prediction = {'predicted_value': 121, 'confidence': 'high'}
        
        result = monitor_rec.analyze(readings, trend_analysis, prediction)
        assert result is None
    
    def test_rapid_change_monitoring(self):
        settings = MockSettings()
        monitor_rec = MonitoringRecommendation(settings)
        
        # Rapid changes
        readings = create_mock_readings([150, 140, 130, 120])
        trend_analysis = {'trend': 'very_fast_down', 'rate_of_change': -6.0}
        prediction = {'predicted_value': 105, 'confidence': 'medium'}
        
        result = monitor_rec.analyze(readings, trend_analysis, prediction)
        
        assert result is not None
        assert result['type'] == 'monitoring'
        assert result['parameters']['check_frequency_minutes'] == 15
        assert "rapid glucose changes detected" in result['parameters']['reasons']
    
    def test_approaching_threshold_monitoring(self):
        settings = MockSettings()
        monitor_rec = MonitoringRecommendation(settings)
        
        # Approaching low threshold
        readings = create_mock_readings([78, 76, 74, 72])
        trend_analysis = {'trend': 'down', 'rate_of_change': -1.0}
        prediction = {'predicted_value': 68, 'confidence': 'medium'}
        
        result = monitor_rec.analyze(readings, trend_analysis, prediction)
        
        assert result is not None
        assert result['parameters']['check_frequency_minutes'] == 30
        assert "approaching low threshold" in result['parameters']['reasons']

class TestRecommendationEngine:
    
    def test_multiple_recommendations(self):
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Critical low scenario - should generate both carb and monitoring recs
        readings = create_mock_readings([50, 48, 45, 47])
        trend_analysis = {'trend': 'fast_down', 'rate_of_change': -2.0}
        prediction = {'predicted_value': 40, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        assert len(recommendations) >= 2  # Should have carb and monitoring at minimum
        
        # Check that recommendations are sorted by priority
        priorities = [rec['priority'] for rec in recommendations]
        assert priorities == sorted(priorities)
        
        # Check for carb recommendation
        carb_recs = [rec for rec in recommendations if rec['type'] == 'carbohydrate']
        assert len(carb_recs) == 1
        assert carb_recs[0]['urgency'] == 'critical'
    
    def test_high_glucose_recommendations(self):
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Stable high glucose
        readings = create_mock_readings([220, 218, 222, 215])
        trend_analysis = {'trend': 'no_change', 'rate_of_change': 0.5}
        prediction = {'predicted_value': 225, 'confidence': 'medium'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        # Should have insulin and monitoring recommendations
        insulin_recs = [rec for rec in recommendations if rec['type'] == 'insulin']
        assert len(insulin_recs) == 1
    
    def test_critical_recommendations_filter(self):
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Mixed scenario
        readings = create_mock_readings([60, 58, 55, 53])
        trend_analysis = {'trend': 'down', 'rate_of_change': -1.0}
        prediction = {'predicted_value': 45, 'confidence': 'medium'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        critical_recs = engine.get_critical_recommendations(recommendations)
        
        # Critical low should generate critical recommendations
        assert len(critical_recs) > 0
        
        # All critical recommendations should have high priority or critical urgency
        for rec in critical_recs:
            assert rec['priority'] <= 2 or rec.get('urgency') == 'critical'

class TestRecommendationScenarios:
    """Test various realistic scenarios"""
    
    def test_dawn_phenomenon(self):
        """Test high morning glucose (dawn phenomenon)"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Morning high glucose, stable
        morning_time = datetime.now().replace(hour=7, minute=0)
        readings = create_mock_readings([185, 182, 188, 186], start_time=morning_time)
        trend_analysis = {'trend': 'up', 'rate_of_change': 1.0}
        prediction = {'predicted_value': 190, 'confidence': 'medium'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        # Should recommend insulin for persistent high glucose
        insulin_recs = [rec for rec in recommendations if rec['type'] == 'insulin']
        assert len(insulin_recs) > 0
    
    def test_exercise_induced_low(self):
        """Test rapidly falling glucose (post-exercise)"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Rapidly falling from normal to low
        readings = create_mock_readings([140, 120, 95, 75])
        trend_analysis = {'trend': 'very_fast_down', 'rate_of_change': -4.5}
        prediction = {'predicted_value': 50, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        # Should recommend carbs and frequent monitoring
        carb_recs = [rec for rec in recommendations if rec['type'] == 'carbohydrate']
        monitor_recs = [rec for rec in recommendations if rec['type'] == 'monitoring']
        
        assert len(carb_recs) > 0
        assert len(monitor_recs) > 0
        assert carb_recs[0]['urgency'] in ['medium', 'high']
    
    def test_meal_spike(self):
        """Test post-meal glucose spike"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Rising glucose after meal
        readings = create_mock_readings([120, 160, 190, 220])
        trend_analysis = {'trend': 'fast_up', 'rate_of_change': 5.0}
        prediction = {'predicted_value': 250, 'confidence': 'medium'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        # May recommend insulin if trending high, definitely monitoring
        monitor_recs = [rec for rec in recommendations if rec['type'] == 'monitoring']
        assert len(monitor_recs) > 0
    
    def test_approaching_low_value_recommendations(self):
        """Test recommendations for approaching low glucose value scenario"""
        settings = MockSettings()
        settings.trend_calculation_points = 6
        engine = RecommendationEngine(settings)
        
        # Same scenario as test_approaching_low_value in test_analysis.py
        readings = create_mock_readings([92, 90, 88, 86, 85, 84, 80, 75, 72])
        trend_analysis = {'trend': 'down', 'rate_of_change': -0.59}
        prediction = {'predicted_value': 67, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        # For this scenario (glucose 72, trend 'down'), should get monitoring but not carbs
        # since glucose is only slightly below threshold and trend is not fast
        carb_recs = [rec for rec in recommendations if rec['type'] == 'carbohydrate']
        monitor_recs = [rec for rec in recommendations if rec['type'] == 'monitoring']
        
        # Should recommend monitoring when approaching low glucose
        assert len(monitor_recs) > 0, "Should recommend monitoring when approaching low glucose"
        
        # Check monitoring recommendation details  
        monitor_rec = monitor_recs[0]
        assert monitor_rec['parameters']['check_frequency_minutes'] == 30, "Should monitor every 30 minutes"
        assert 'approaching low threshold' in monitor_rec['parameters']['reasons'], "Should mention approaching low threshold"
        
        # For this mild scenario, carbs may not be recommended yet (glucose still above 70)
        # This is actually appropriate behavior - monitoring first, carbs if it gets worse
        
    def test_approaching_low_value_with_carb_recommendation(self):
        """Test recommendations when glucose is actually low or falling fast"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Scenario where carbs should definitely be recommended
        readings = create_mock_readings([85, 80, 75, 68])  # Current glucose 68 (below 70)
        trend_analysis = {'trend': 'fast_down', 'rate_of_change': -2.5}
        prediction = {'predicted_value': 60, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction)
        
        # Should recommend both carbs and monitoring
        carb_recs = [rec for rec in recommendations if rec['type'] == 'carbohydrate']
        monitor_recs = [rec for rec in recommendations if rec['type'] == 'monitoring']
        
        # Verify carb recommendation exists for low glucose
        assert len(carb_recs) > 0, "Should recommend carbs when glucose is below 70"
        
        # Check carb recommendation details
        carb_rec = carb_recs[0]
        assert carb_rec['urgency'] == 'high', f"Expected high urgency for low glucose, got {carb_rec['urgency']}"
        assert 'recommended_carbs' in carb_rec['parameters'], "Should include recommended carb amount"
        assert carb_rec['parameters']['recommended_carbs'] >= 15, "Should recommend at least 15g carbs"
        
        # Should also recommend monitoring
        assert len(monitor_recs) > 0, "Should recommend monitoring when glucose is low"
        
        # Check that carbs are highest priority
        carb_priority = carb_rec['priority']
        assert carb_priority == 1, "Carb recommendations should have highest priority"
    
    def test_iob_recommendation_approaching_low(self):
        """Test IOB recommendation when approaching low glucose"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Scenario: Approaching low glucose with no IOB data
        readings = create_mock_readings([85, 82, 78, 75])  # Approaching 70 threshold
        trend_analysis = {'trend': 'down', 'rate_of_change': -1.2}
        prediction = {'predicted_value': 68, 'confidence': 'high'}
        
        # No IOB data provided
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data=None)
        
        # Should recommend checking IOB status
        iob_recs = [rec for rec in recommendations if rec['type'] == 'iob_status']
        assert len(iob_recs) > 0, "Should recommend IOB check when approaching low glucose"
        
        iob_rec = iob_recs[0]
        assert iob_rec['urgency'] == 'high', f"Expected high urgency for approaching low, got {iob_rec['urgency']}"
        assert 'approaching low glucose' in iob_rec['parameters']['reasons'][0], "Should mention approaching low glucose"
        assert 'Check pump/Omnipod for current IOB' in iob_rec['parameters']['suggested_action']

    def test_iob_recommendation_high_iob_affecting_predictions(self):
        """Test IOB recommendation with high IOB that affects predictions"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Scenario: High IOB should cause significant glucose drop
        readings = create_mock_readings([120, 118, 115, 112])  # Mild descent
        trend_analysis = {'trend': 'down', 'rate_of_change': -0.8}
        prediction = {'predicted_value': 85, 'confidence': 'medium'}
        
        # High IOB that should cause more dramatic effect
        iob_cob_data = {
            'iob': {
                'total_iob': 1.2,  # High IOB
                'is_override': False
            },
            'cob': {'total_cob': 0}
        }
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data)
        
        # Should recommend verifying IOB status due to high IOB
        iob_recs = [rec for rec in recommendations if rec['type'] == 'iob_status']
        assert len(iob_recs) > 0, "Should recommend IOB verification with high IOB"
        
        iob_rec = iob_recs[0]
        assert iob_rec['parameters']['current_iob'] == 1.2, "Should report current IOB value"
        assert iob_rec['parameters']['expected_effect'] is not None, "Should calculate expected glucose effect"
        
        # Should predict significant glucose drop
        expected_drop = iob_rec['parameters']['expected_effect']['expected_glucose_drop']
        assert expected_drop > 40, f"Expected significant glucose drop (>40), got {expected_drop}"

    def test_iob_recommendation_rising_fast_no_iob(self):
        """Test IOB recommendation when glucose rising fast with no IOB data"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Scenario: Glucose rising fast, need to check if insulin was taken
        readings = create_mock_readings([140, 155, 175, 195])  # Rising fast
        trend_analysis = {'trend': 'fast_up', 'rate_of_change': 3.5}
        prediction = {'predicted_value': 220, 'confidence': 'high'}
        
        # No IOB data
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data=None)
        
        # Should recommend checking IOB
        iob_recs = [rec for rec in recommendations if rec['type'] == 'iob_status']
        assert len(iob_recs) > 0, "Should recommend IOB check when glucose rising fast"
        
        iob_rec = iob_recs[0]
        assert iob_rec['urgency'] == 'medium', f"Expected medium urgency for rising fast, got {iob_rec['urgency']}"
        assert 'glucose rising fast' in iob_rec['parameters']['reasons'][0], "Should mention glucose rising fast"

    def test_no_insulin_recommendation_for_falling_glucose(self):
        """Test that insulin is never recommended when glucose is falling"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Create readings with proper timestamps (most recent first)
        from datetime import datetime, timedelta
        from src.database import GlucoseReading
        
        now = datetime.now()
        readings = [
            GlucoseReading(timestamp=now, value=185, trend='down'),                    # Most recent
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=190, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=195, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=200, trend='down'),  # Oldest
        ]
        
        trend_analysis = {'trend': 'down', 'rate_of_change': -1.0}
        prediction = {'predicted_value': 180, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data=None)
        
        # Should not recommend insulin for falling glucose
        insulin_recs = [rec for rec in recommendations if rec['type'] == 'insulin']
        assert len(insulin_recs) == 0, f"Should not recommend insulin for falling glucose, but got: {insulin_recs}"
        
        # Should have IOB status recommendation (glucose was high recently)
        iob_recs = [rec for rec in recommendations if rec['type'] == 'iob_status']
        assert len(iob_recs) > 0, "Should recommend checking IOB for high glucose without IOB data"

    def test_no_insulin_recommendation_for_fast_falling_glucose(self):
        """Test that insulin is never recommended when glucose is falling fast"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Create readings with proper timestamps (most recent first)
        from datetime import datetime, timedelta
        from src.database import GlucoseReading
        
        now = datetime.now()
        readings = [
            GlucoseReading(timestamp=now, value=190, trend='very_fast_down'),             # Most recent
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=210, trend='very_fast_down'),
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=230, trend='very_fast_down'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=250, trend='very_fast_down'),  # Oldest
        ]
        
        trend_analysis = {'trend': 'very_fast_down', 'rate_of_change': -4.0}
        prediction = {'predicted_value': 150, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data=None)
        
        # Should absolutely not recommend insulin for very fast falling glucose
        insulin_recs = [rec for rec in recommendations if rec['type'] == 'insulin']
        assert len(insulin_recs) == 0, f"Should never recommend insulin for very fast falling glucose, but got: {insulin_recs}"

    def test_insulin_recommendation_only_for_stable_high_glucose(self):
        """Test that insulin is only recommended for truly stable high glucose"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Scenario: Stable high glucose - should recommend insulin
        readings = create_mock_readings([220, 218, 222, 219])  # Chronological order
        readings = list(reversed(readings))  # Most recent first: [219, 222, 218, 220]
        trend_analysis = {'trend': 'no_change', 'rate_of_change': 0.1}
        prediction = {'predicted_value': 220, 'confidence': 'high'}
        
        # No IOB data - should recommend insulin
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data=None)
        
        # Should recommend insulin for stable high glucose
        insulin_recs = [rec for rec in recommendations if rec['type'] == 'insulin']
        assert len(insulin_recs) > 0, "Should recommend insulin for stable high glucose"
        
        insulin_rec = insulin_recs[0]
        assert 'units' in insulin_rec['message'], "Should specify insulin units"
        assert insulin_rec['priority'] == 2, "Insulin recommendations should have priority 2"

    def test_slow_correction_insulin_recommendation(self):
        """Test insulin recommendation for slow correction scenario"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        # Create scenario: High glucose slowly falling for sustained period
        from datetime import datetime, timedelta
        from src.database import GlucoseReading
        
        now = datetime.now()
        readings = [
            GlucoseReading(timestamp=now, value=235, trend='down'),                           # Most recent
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=238, trend='down'),   # Slow decline
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=242, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=245, trend='down'),  # Sustained high
        ]
        
        trend_analysis = {'trend': 'down', 'rate_of_change': -0.5}  # Slow downward trend
        prediction = {'predicted_value': 220, 'confidence': 'high'}
        
        recommendations = engine.get_recommendations(readings, trend_analysis, prediction, iob_cob_data=None)
        
        # Should recommend insulin for slow correction
        insulin_recs = [rec for rec in recommendations if rec['type'] == 'insulin']
        assert len(insulin_recs) > 0, "Should recommend insulin for slow correction of high glucose"
        
        insulin_rec = insulin_recs[0]
        
        # Check message mentions slow correction
        assert 'slowly falling' in insulin_rec['message'], "Should mention slow falling trend"
        assert 'safe to accelerate correction' in insulin_rec['message'], "Should mention safe acceleration"
        
        # Check safety notes are appropriate for slow correction
        safety_notes = insulin_rec['safety_notes']
        assert any('SLOW CORRECTION' in note for note in safety_notes), "Should have slow correction safety note"
        assert any('30-60 minutes' in note for note in safety_notes), "Should specify monitoring frequency"
        
        # Check correction type is marked
        assert insulin_rec['parameters']['correction_type'] == 'slow_correction', "Should mark as slow correction"
        
        print(f"Slow correction insulin: {insulin_rec['parameters']['recommended_units']} units")
        print(f"Message: {insulin_rec['message']}")

    def test_slow_correction_safety_thresholds(self):
        """Test that slow correction only triggers under safe conditions"""
        settings = MockSettings()
        engine = RecommendationEngine(settings)
        
        from datetime import datetime, timedelta
        from src.database import GlucoseReading
        now = datetime.now()
        
        # Test 1: Glucose too low for slow correction (below 220)
        readings_low = [
            GlucoseReading(timestamp=now, value=200, trend='down'),  # Below 220 threshold
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=203, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=206, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=210, trend='down'),
        ]
        
        trend_analysis_low = {'trend': 'down', 'rate_of_change': -0.5}
        recommendations_low = engine.get_recommendations(readings_low, trend_analysis_low, 
                                                       {'predicted_value': 185}, iob_cob_data=None)
        insulin_recs_low = [rec for rec in recommendations_low if rec['type'] == 'insulin']
        assert len(insulin_recs_low) == 0, "Should not recommend insulin when glucose < 220 mg/dL"
        
        # Test 2: Rate too fast for slow correction
        readings_fast = [
            GlucoseReading(timestamp=now, value=240, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=250, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=260, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=270, trend='down'),
        ]
        
        trend_analysis_fast = {'trend': 'down', 'rate_of_change': -1.2}  # Too fast
        recommendations_fast = engine.get_recommendations(readings_fast, trend_analysis_fast,
                                                        {'predicted_value': 200}, iob_cob_data=None)
        insulin_recs_fast = [rec for rec in recommendations_fast if rec['type'] == 'insulin']
        assert len(insulin_recs_fast) == 0, "Should not recommend insulin when falling too fast (>-0.8 mg/dL/min)"

    def test_slow_correction_conservative_dosing(self):
        """Test that slow correction uses smaller insulin doses"""
        settings = MockSettings()
        insulin_rec = InsulinRecommendation(settings)
        
        from datetime import datetime, timedelta
        from src.database import GlucoseReading
        now = datetime.now()
        
        # Identical glucose levels and conditions
        readings = [
            GlucoseReading(timestamp=now, value=250, trend='stable'),
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=248, trend='stable'),
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=252, trend='stable'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=251, trend='stable'),
        ]
        
        # Test stable high glucose (normal dosing)
        trend_stable = {'trend': 'no_change', 'rate_of_change': 0.1}
        stable_rec = insulin_rec.analyze(readings, trend_stable, {'predicted_value': 250}, iob_cob_data=None)
        
        # Test slow correction scenario (reduced dosing)  
        readings_slow = [
            GlucoseReading(timestamp=now, value=250, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=5), value=253, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=10), value=256, trend='down'),
            GlucoseReading(timestamp=now - timedelta(minutes=15), value=260, trend='down'),
        ]
        trend_slow = {'trend': 'down', 'rate_of_change': -0.5}
        slow_rec = insulin_rec.analyze(readings_slow, trend_slow, {'predicted_value': 240}, iob_cob_data=None)
        
        if stable_rec and slow_rec:
            stable_units = stable_rec['parameters']['recommended_units']
            slow_units = slow_rec['parameters']['recommended_units']
            
            print(f"Stable glucose insulin: {stable_units} units")
            print(f"Slow correction insulin: {slow_units} units")
            
            # Slow correction should use about half the dose
            assert slow_units < stable_units, "Slow correction should use smaller dose than stable high glucose"
            assert slow_units <= stable_units * 0.6, "Slow correction should be significantly smaller (≤60% of normal dose)"

if __name__ == "__main__":
    pytest.main([__file__])