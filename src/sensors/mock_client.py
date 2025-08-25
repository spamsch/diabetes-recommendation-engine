import logging
import math
import random
from datetime import datetime, timedelta
from typing import Optional, List
from ..database import GlucoseReading
from ..config import Settings

logger = logging.getLogger(__name__)

class MockDexcomClient:
    """Mock Dexcom client for testing purposes"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.last_reading_time = None
        self.current_value = 120.0  # Starting glucose value
        self.trend_direction = "no_change"
        self.reading_count = 0
        
        # Simulate various scenarios for testing
        self.scenario_readings = self._generate_test_scenarios()
        self.current_scenario = "normal"
        
        logger.info("Mock Dexcom client initialized for testing")
    
    def _generate_test_scenarios(self) -> dict:
        """Generate different test scenarios"""
        base_time = datetime.now() - timedelta(hours=2)
        
        scenarios = {
            "normal": [
                (base_time + timedelta(minutes=i*5), 100 + random.gauss(0, 10), "no_change")
                for i in range(24)
            ],
            "rapid_rise": [
                (base_time + timedelta(minutes=i*5), 80 + i*8, "fast_up" if i < 10 else "very_fast_up")
                for i in range(20)
            ],
            "rapid_fall": [
                (base_time + timedelta(minutes=i*5), 180 - i*8, "fast_down" if i < 10 else "very_fast_down")
                for i in range(20)
            ],
            "low_trending": [
                (base_time + timedelta(minutes=i*5), 85 - i*2, "down")
                for i in range(15)
            ],
            "high_stable": [
                (base_time + timedelta(minutes=i*5), 200 + random.gauss(0, 5), "no_change")
                for i in range(12)
            ]
        }
        
        return scenarios
    
    def set_scenario(self, scenario: str):
        """Set the test scenario"""
        if scenario in self.scenario_readings:
            self.current_scenario = scenario
            self.reading_count = 0
            logger.info(f"Switched to test scenario: {scenario}")
        else:
            logger.warning(f"Unknown scenario: {scenario}")
    
    def get_current_reading(self) -> Optional[GlucoseReading]:
        """Simulate getting current glucose reading"""
        try:
            # Use scenario data if available
            if (self.current_scenario in self.scenario_readings and 
                self.reading_count < len(self.scenario_readings[self.current_scenario])):
                
                timestamp, value, trend = self.scenario_readings[self.current_scenario][self.reading_count]
                self.reading_count += 1
                
            else:
                # Generate realistic random data
                timestamp = datetime.now()
                value = self._generate_realistic_value()
                trend = self._determine_trend(value)
            
            reading = GlucoseReading(
                timestamp=timestamp,
                value=value,
                trend=trend,
                unit="mg/dL"
            )
            
            self.last_reading_time = reading.timestamp
            self.current_value = value
            
            logger.info(f"Mock reading: {reading.value} {reading.unit}, trend: {reading.trend}")
            return reading
            
        except Exception as e:
            logger.error(f"Error generating mock reading: {e}")
            return None
    
    def _generate_realistic_value(self) -> float:
        """Generate realistic glucose values with some variation"""
        # Add some randomness but keep within reasonable bounds
        change = random.gauss(0, 5)  # Small random changes
        
        # Apply trend-based changes
        if self.trend_direction == "very_fast_up":
            change += random.uniform(8, 15)
        elif self.trend_direction == "fast_up":
            change += random.uniform(4, 8)
        elif self.trend_direction == "up":
            change += random.uniform(1, 4)
        elif self.trend_direction == "down":
            change -= random.uniform(1, 4)
        elif self.trend_direction == "fast_down":
            change -= random.uniform(4, 8)
        elif self.trend_direction == "very_fast_down":
            change -= random.uniform(8, 15)
        
        new_value = self.current_value + change
        
        # Keep within realistic bounds
        new_value = max(40, min(400, new_value))
        
        return round(new_value, 1)
    
    def _determine_trend(self, current_value: float) -> str:
        """Determine trend based on current and previous values"""
        if self.current_value is None:
            return "no_change"
        
        diff = current_value - self.current_value
        
        if diff > 10:
            self.trend_direction = "very_fast_up"
        elif diff > 5:
            self.trend_direction = "fast_up"
        elif diff > 2:
            self.trend_direction = "up"
        elif diff < -10:
            self.trend_direction = "very_fast_down"
        elif diff < -5:
            self.trend_direction = "fast_down"
        elif diff < -2:
            self.trend_direction = "down"
        else:
            self.trend_direction = "no_change"
        
        return self.trend_direction
    
    def get_recent_readings(self, hours: int = 3) -> List[GlucoseReading]:
        """Simulate getting recent glucose readings"""
        readings = []
        current_time = datetime.now()
        
        # Generate readings for the past few hours
        for i in range(hours * 12):  # Every 5 minutes
            timestamp = current_time - timedelta(minutes=i*5)
            value = self._generate_historical_value(i)
            trend = self._generate_historical_trend(i)
            
            reading = GlucoseReading(
                timestamp=timestamp,
                value=value,
                trend=trend,
                unit="mg/dL"
            )
            readings.append(reading)
        
        readings.reverse()  # Chronological order
        logger.info(f"Generated {len(readings)} mock historical readings")
        return readings
    
    def _generate_historical_value(self, minutes_ago: int) -> float:
        """Generate historical glucose value"""
        base_value = 120
        # Add some realistic variation over time
        time_factor = minutes_ago * 5  # Convert to minutes
        variation = 20 * (1 + 0.5 * math.sin(time_factor / 60.0))  # Hourly cycles
        noise = random.gauss(0, 8)
        
        value = base_value + variation + noise
        return max(50, min(300, round(value, 1)))
    
    def _generate_historical_trend(self, minutes_ago: int) -> str:
        """Generate historical trend"""
        trends = ["no_change", "up", "down", "fast_up", "fast_down"]
        return random.choice(trends)
    
    def is_new_reading_available(self) -> bool:
        """Always return True for testing"""
        return True
    
    def wait_for_next_reading(self) -> float:
        """Return minimal wait time for testing"""
        return 1.0
    
    def reconnect(self) -> bool:
        """Always succeed for testing"""
        logger.info("Mock reconnection successful")
        return True
    
    def test_connection(self) -> bool:
        """Always succeed for testing"""
        logger.info("Mock connection test successful")
        return True