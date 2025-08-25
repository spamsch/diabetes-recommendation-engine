import pytest
import numpy as np
from datetime import datetime, timedelta
from src.config import Settings, settings
from src.database import GlucoseReading
from src.analysis import TrendAnalyzer, GlucosePredictor

class MockSettings:
    """Mock settings for testing"""
    def __init__(self):
        self.trend_calculation_points = 3
        self.stable_variance_threshold = 10.0
        self.rapid_rise_threshold = 3.0
        self.rapid_fall_threshold = -3.0
        self.low_glucose_threshold = 70
        self.high_glucose_threshold = 180
        self.critical_low_threshold = 55
        self.carb_to_glucose_ratio = 3.5
        self.critical_high_threshold = 300
        self.prediction_minutes_ahead = 15
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
    
    return readings

class TestTrendAnalyzer:
    
    def test_stable_glucose_trend(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Stable glucose readings
        readings = create_mock_readings([120, 118, 122, 119, 121])
        
        result = analyzer.analyze_trend(readings)
        
        assert result['trend'] == 'no_change'
        assert abs(result['rate_of_change']) < 1.0
        assert result['is_stable'] == True
        assert result['direction'] == 'stable'
        assert result['trend_strength'] in ['weak', 'moderate']
    
    def test_rising_glucose_trend(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Rising glucose readings
        readings = create_mock_readings([100, 110, 120, 130, 140])
        
        result = analyzer.analyze_trend(readings)
        
        assert result['trend'] in ['up', 'fast_up', 'very_fast_up']
        assert result['rate_of_change'] > 1.0
        assert result['direction'] == 'rising'
        assert result['is_stable'] == False
    
    def test_falling_glucose_trend(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Falling glucose readings
        readings = create_mock_readings([200, 180, 160, 140, 120])
        
        result = analyzer.analyze_trend(readings)
        
        assert result['trend'] in ['down', 'fast_down', 'very_fast_down']
        assert result['rate_of_change'] < -1.0
        assert result['direction'] == 'falling'
        assert result['is_stable'] == False
    
    def test_rapid_changes_detection(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Very rapid rise
        readings = create_mock_readings([100, 120, 145, 175])  # ~25 mg/dL per 5 min
        
        result = analyzer.analyze_trend(readings)
        
        assert result['trend'] == 'very_fast_up'
        assert result['rate_of_change'] >= 5.0
    
    def test_insufficient_data(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Single reading
        readings = create_mock_readings([120])
        
        result = analyzer.analyze_trend(readings)
        
        assert result['trend'] == 'no_change'
        assert result['rate_of_change'] == 0.0
        assert result['is_stable'] == True
    
    def test_pattern_detection_rapid_rise(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Readings with rapid changes
        readings = create_mock_readings([100, 130, 160, 190])  # 30 mg/dL jumps
        
        patterns = analyzer.detect_patterns(readings)
        
        assert patterns['pattern_count'] > 0
        rapid_patterns = [p for p in patterns['patterns'] if p['type'] == 'rapid_rise']
        assert len(rapid_patterns) > 0
        assert rapid_patterns[0]['severity'] in ['medium', 'high']
    
    def test_pattern_detection_approaching_threshold(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Approaching low threshold
        readings = create_mock_readings([85, 80, 75, 73])
        
        patterns = analyzer.detect_patterns(readings)
        
        approaching_patterns = [p for p in patterns['patterns'] 
                               if p['type'] == 'approaching_low']
        assert len(approaching_patterns) > 0
    
    def test_pattern_detection_critical_values(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Critical low values
        readings = create_mock_readings([60, 55, 50, 45])
        
        patterns = analyzer.detect_patterns(readings)
        
        critical_patterns = [p for p in patterns['patterns'] 
                            if p['type'] == 'critical_low']
        assert len(critical_patterns) > 0
        assert critical_patterns[0]['severity'] == 'critical'
    
    def test_stability_pattern(self):
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        
        # Very stable readings
        readings = create_mock_readings([120, 121, 119, 122, 118, 120])
        
        patterns = analyzer.detect_patterns(readings)
        
        stable_patterns = [p for p in patterns['patterns'] 
                          if p['type'] == 'stable_pattern']
        assert len(stable_patterns) > 0

class TestGlucosePredictor:
    
    def test_linear_extrapolation_stable(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Stable trend
        readings = create_mock_readings([120, 121, 119, 122, 118])
        
        prediction = predictor.predict_future_value(readings)
        
        assert prediction['predicted_value'] is not None
        assert 110 <= prediction['predicted_value'] <= 130  # Should be close to current values
        assert prediction['method'] in ['linear_extrapolation', 'exponential_smoothing']
        assert prediction['confidence'] in ['low', 'medium', 'high']
    
    def test_linear_extrapolation_rising(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Rising trend
        readings = create_mock_readings([100, 110, 120, 130, 140])
        
        prediction = predictor.predict_future_value(readings)
        
        assert prediction['predicted_value'] is not None
        # Should predict higher value
        assert prediction['predicted_value'] > 140
        assert prediction['confidence'] in ['low', 'medium', 'high']
    
    def test_linear_extrapolation_falling(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Falling trend
        readings = create_mock_readings([200, 180, 160, 140, 120])
        
        prediction = predictor.predict_future_value(readings)
        
        assert prediction['predicted_value'] is not None
        # Should predict lower value
        assert prediction['predicted_value'] < 120
        assert prediction['confidence'] in ['low', 'medium', 'high']
    
    def test_polynomial_prediction(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Curved trend (quadratic pattern)
        readings = create_mock_readings([100, 105, 115, 130, 150, 175])
        
        prediction = predictor.predict_future_value(readings)
        
        assert prediction['predicted_value'] is not None
        # For accelerating rise, should predict high value
        assert prediction['predicted_value'] > 175
    
    def test_exponential_smoothing(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Noisy but trending data
        readings = create_mock_readings([120, 115, 125, 118, 128, 122])
        
        prediction = predictor.predict_future_value(readings)
        
        assert prediction['predicted_value'] is not None
        assert 115 <= prediction['predicted_value'] <= 135
    
    def test_insufficient_data(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Too few readings
        readings = create_mock_readings([120, 125])
        
        prediction = predictor.predict_future_value(readings)
        
        assert prediction['predicted_value'] is None
        assert prediction['method'] == 'insufficient_data'
        assert 'warning' in prediction
    
    def test_prediction_confidence_calculation(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Very linear, predictable data
        readings = create_mock_readings([100, 105, 110, 115, 120, 125, 130])
        
        prediction = predictor.predict_future_value(readings)
        
        # Linear data should have high confidence
        assert prediction['confidence'] in ['medium', 'high']
        assert 'r_squared' in prediction or 'avg_error' in prediction
    
    def test_risk_assessment_critical_low(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Predicting critical low
        current_reading = GlucoseReading(
            timestamp=datetime.now(),
            value=65,
            trend="down"
        )
        
        prediction = {
            'predicted_value': 45,
            'confidence': 'high',
            'slope': -2.0
        }
        
        risk = predictor.assess_prediction_risk(prediction, current_reading)
        
        assert risk['risk_level'] == 'critical'
        assert len(risk['risk_factors']) > 0
        assert 'critical low' in risk['risk_factors'][0].lower()
        assert risk['predicted_change'] < 0
    
    def test_risk_assessment_critical_high(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Predicting critical high
        current_reading = GlucoseReading(
            timestamp=datetime.now(),
            value=280,
            trend="up"
        )
        
        prediction = {
            'predicted_value': 320,
            'confidence': 'medium',
            'slope': 3.0
        }
        
        risk = predictor.assess_prediction_risk(prediction, current_reading)
        
        assert risk['risk_level'] == 'critical'
        assert 'critical high' in risk['risk_factors'][0].lower()
    
    def test_risk_assessment_low_confidence(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        current_reading = GlucoseReading(
            timestamp=datetime.now(),
            value=150,
            trend="no_change"
        )
        
        prediction = {
            'predicted_value': 155,
            'confidence': 'low',
            'slope': 0.5
        }
        
        risk = predictor.assess_prediction_risk(prediction, current_reading)
        
        assert risk['risk_level'] in ['medium', 'low']
        low_conf_factors = [f for f in risk['risk_factors'] 
                           if 'confidence' in f.lower()]
        assert len(low_conf_factors) > 0
    
    def test_time_to_threshold_estimation(self):
        settings = MockSettings()
        predictor = GlucosePredictor(settings)
        
        # Falling towards low threshold
        current_reading = GlucoseReading(
            timestamp=datetime.now(),
            value=90,
            trend="down"
        )
        
        prediction = {
            'predicted_value': 60,
            'confidence': 'high',
            'slope': -2.0  # 2 mg/dL per minute decline
        }
        
        risk = predictor.assess_prediction_risk(prediction, current_reading)
        
        if risk['time_to_threshold']:
            # Should estimate time to reach 70 mg/dL threshold
            # (90 - 70) / 2 = 10 minutes
            assert 'low' in risk['time_to_threshold']
            assert risk['time_to_threshold']['low'] == 10.0

class TestIntegrationScenarios:
    """Test realistic scenarios combining trend analysis and prediction"""
    
    def test_dawn_phenomenon_analysis(self):
        """Test morning glucose rise (dawn phenomenon)"""
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        predictor = GlucosePredictor(settings)
        
        # Typical dawn phenomenon: gradual rise
        morning_time = datetime.now().replace(hour=6, minute=0)
        readings = create_mock_readings([120, 135, 150, 165, 180], 
                                       start_time=morning_time, 
                                       interval_minutes=10)
        
        trend_result = analyzer.analyze_trend(readings)
        prediction_result = predictor.predict_future_value(readings)
        
        assert trend_result['trend'] in ['up', 'fast_up']
        assert trend_result['direction'] == 'rising'
        assert prediction_result['predicted_value'] > 180
    
    def test_post_meal_spike_analysis(self):
        """Test post-meal glucose spike"""
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        predictor = GlucosePredictor(settings)
        
        # Post-meal spike pattern
        readings = create_mock_readings([110, 140, 180, 220, 240])
        
        trend_result = analyzer.analyze_trend(readings)
        prediction_result = predictor.predict_future_value(readings)
        patterns = analyzer.detect_patterns(readings)
        
        assert trend_result['trend'] in ['fast_up', 'very_fast_up']
        assert prediction_result['predicted_value'] > 240
        
        # Should detect rapid rise patterns
        rapid_patterns = [p for p in patterns['patterns'] 
                         if p['type'] == 'rapid_rise']
        assert len(rapid_patterns) > 0

    def test_approaching_low_value(self):
        """Test approaching low glucose value"""
        settings = MockSettings()
        settings.trend_calculation_points = 6
        analyzer = TrendAnalyzer(settings)
        predictor = GlucosePredictor(settings)

        # Simulate readings approaching a low value
        readings = create_mock_readings([92, 90, 88, 86, 85, 84, 80, 75, 72])

        trend_result = analyzer.analyze_trend(readings)
        prediction_result = predictor.predict_future_value(readings)

        assert trend_result['trend'] == 'down'
        assert prediction_result['predicted_value'] < 70  # Approaching low threshold

    def test_exercise_induced_drop(self):
        """Test exercise-induced glucose drop"""
        settings = MockSettings()
        analyzer = TrendAnalyzer(settings)
        predictor = GlucosePredictor(settings)
        
        # Exercise drop pattern
        readings = create_mock_readings([150, 130, 110, 90, 75])
        
        trend_result = analyzer.analyze_trend(readings)
        prediction_result = predictor.predict_future_value(readings)
        risk_assessment = predictor.assess_prediction_risk(
            prediction_result, readings[0]
        )
        
        assert trend_result['trend'] in ['fast_down', 'very_fast_down']
        assert prediction_result['predicted_value'] < 75
        assert risk_assessment['risk_level'] in ['high', 'critical']

if __name__ == "__main__":
    pytest.main([__file__])