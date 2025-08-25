import pytest
from datetime import datetime, timedelta
from src.config import Settings
from src.sensors import MockDexcomClient

class MockSettings:
    """Mock settings for testing"""
    def __init__(self):
        self.poll_interval_minutes = 5
        self.carb_to_glucose_ratio = 3.5

class TestMockDexcomClient:
    
    def setup_method(self):
        self.settings = MockSettings()
        self.client = MockDexcomClient(self.settings)
    
    def test_initialization(self):
        """Test mock client initialization"""
        assert self.client.settings == self.settings
        assert self.client.current_value == 120.0
        assert self.client.trend_direction == "no_change"
        assert self.client.reading_count == 0
        assert "normal" in self.client.scenario_readings
    
    def test_get_current_reading(self):
        """Test getting current reading"""
        reading = self.client.get_current_reading()
        
        assert reading is not None
        assert isinstance(reading.value, float)
        assert reading.value > 0
        assert reading.unit == "mg/dL"
        assert reading.trend is not None
        assert isinstance(reading.timestamp, datetime)
    
    def test_multiple_readings_progression(self):
        """Test that readings progress logically"""
        readings = []
        
        # Get several readings
        for i in range(5):
            reading = self.client.get_current_reading()
            readings.append(reading)
        
        # Check that we got different readings
        values = [r.value for r in readings]
        assert len(set(values)) > 1  # Should have some variation
        
        # Check that all readings have valid ranges
        for reading in readings:
            assert 40 <= reading.value <= 400  # Realistic glucose range
    
    def test_scenario_switching(self):
        """Test different test scenarios"""
        # Test normal scenario
        self.client.set_scenario("normal")
        normal_reading = self.client.get_current_reading()
        assert normal_reading is not None
        
        # Test rapid rise scenario
        self.client.set_scenario("rapid_rise")
        rise_readings = []
        for i in range(3):
            reading = self.client.get_current_reading()
            rise_readings.append(reading.value)
        
        # Should show increasing trend
        assert rise_readings[1] > rise_readings[0]
        assert rise_readings[2] > rise_readings[1]
        
        # Test rapid fall scenario
        self.client.set_scenario("rapid_fall")
        fall_readings = []
        for i in range(3):
            reading = self.client.get_current_reading()
            fall_readings.append(reading.value)
        
        # Should show decreasing trend
        assert fall_readings[1] < fall_readings[0]
        assert fall_readings[2] < fall_readings[1]
    
    def test_low_trending_scenario(self):
        """Test low trending scenario"""
        self.client.set_scenario("low_trending")
        
        readings = []
        for i in range(5):
            reading = self.client.get_current_reading()
            readings.append(reading.value)
        
        # Should trend towards low values
        first_half_avg = sum(readings[:2]) / 2
        second_half_avg = sum(readings[3:]) / 2
        assert second_half_avg < first_half_avg
    
    def test_high_stable_scenario(self):
        """Test high stable scenario"""
        self.client.set_scenario("high_stable")
        
        readings = []
        for i in range(5):
            reading = self.client.get_current_reading()
            readings.append(reading.value)
        
        # Should be consistently high with low variation
        avg_value = sum(readings) / len(readings)
        assert avg_value > 150  # Should be elevated
        
        # Check stability (low variation)
        max_val = max(readings)
        min_val = min(readings)
        variation = max_val - min_val
        assert variation < 20  # Should be relatively stable
    
    def test_get_recent_readings(self):
        """Test getting historical readings"""
        recent_readings = self.client.get_recent_readings(hours=1)
        
        assert len(recent_readings) == 12  # 1 hour * 12 readings per hour (every 5 min)
        
        # Check that readings are in chronological order
        timestamps = [r.timestamp for r in recent_readings]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1]
        
        # Check that all readings have valid data
        for reading in recent_readings:
            assert 50 <= reading.value <= 300
            assert reading.unit == "mg/dL"
            assert reading.trend is not None
    
    def test_connection_methods(self):
        """Test connection-related methods"""
        # These should always succeed for mock client
        assert self.client.test_connection() == True
        assert self.client.reconnect() == True
        assert self.client.is_new_reading_available() == True
        
        # Wait time should be minimal for testing
        wait_time = self.client.wait_for_next_reading()
        assert wait_time == 1.0
    
    def test_realistic_glucose_values(self):
        """Test that generated values are realistic"""
        readings = []
        
        # Generate many readings to test distribution
        for i in range(50):
            reading = self.client.get_current_reading()
            readings.append(reading.value)
        
        # Check realistic bounds
        for value in readings:
            assert 40 <= value <= 400
        
        # Most values should be in typical range
        normal_range_count = sum(1 for v in readings if 70 <= v <= 200)
        assert normal_range_count > len(readings) * 0.5  # At least 50% in normal-ish range
    
    def test_trend_consistency(self):
        """Test that trends are consistent with value changes"""
        self.client.set_scenario("rapid_rise")
        
        prev_reading = self.client.get_current_reading()
        
        for i in range(3):
            current_reading = self.client.get_current_reading()
            
            if current_reading.value > prev_reading.value:
                # Rising glucose should have rising trend
                assert current_reading.trend in ["up", "fast_up", "very_fast_up"]
            elif current_reading.value < prev_reading.value:
                # Falling glucose should have falling trend
                assert current_reading.trend in ["down", "fast_down", "very_fast_down"]
            
            prev_reading = current_reading
    
    def test_unknown_scenario(self):
        """Test handling of unknown scenarios"""
        # Should handle unknown scenario gracefully
        self.client.set_scenario("unknown_scenario")
        
        # Should still generate readings
        reading = self.client.get_current_reading()
        assert reading is not None
        assert reading.value > 0
    
    def test_scenario_data_structure(self):
        """Test that scenario data is properly structured"""
        scenarios = self.client.scenario_readings
        
        # Check that all expected scenarios exist
        expected_scenarios = ["normal", "rapid_rise", "rapid_fall", "low_trending", "high_stable"]
        for scenario in expected_scenarios:
            assert scenario in scenarios
        
        # Check that each scenario has valid data
        for scenario_name, readings_data in scenarios.items():
            assert len(readings_data) > 0
            
            for timestamp, value, trend in readings_data:
                assert isinstance(timestamp, datetime)
                assert isinstance(value, (int, float))
                assert value > 0
                assert isinstance(trend, str)
    
    def test_reading_count_progression(self):
        """Test that reading count progresses correctly"""
        initial_count = self.client.reading_count
        
        # Get some readings
        for i in range(3):
            self.client.get_current_reading()
        
        # Count should have progressed
        assert self.client.reading_count == initial_count + 3

if __name__ == "__main__":
    pytest.main([__file__])