import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List
from pydexcom import Dexcom
from ..database import GlucoseReading
from ..config import Settings

logger = logging.getLogger(__name__)

class DexcomClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.dexcom = None
        self.last_reading_time = None
        self.last_reading_value = None
        self.next_expected_reading_time = None  # When next reading should be available (timestamp + 305s)
        self._connect()
    
    def _connect(self):
        try:
            self.dexcom = Dexcom(
                username=self.settings.dexcom_username,
                password=self.settings.dexcom_password,
                ous=self.settings.dexcom_ous
            )
            logger.info("Successfully connected to Dexcom")
        except Exception as e:
            logger.error(f"Failed to connect to Dexcom: {e}")
            raise
    
    def get_current_reading(self) -> Optional[GlucoseReading]:
        try:
            bg = self.dexcom.get_current_glucose_reading()
            if bg is None:
                logger.warning("No current glucose reading available")
                return None
            
            # Use correct pydexcom attribute names
            timestamp = bg.time
            value = bg.value  # or bg.mg_dl (same thing)
            trend_desc = bg.trend_description
            
            if value is None:
                logger.warning("No glucose value in reading")
                return None
            
            reading = GlucoseReading(
                timestamp=timestamp,
                value=float(value),
                trend=self._map_trend(trend_desc),
                unit="mg/dL"
            )
            
            # Check if this is the same reading we already processed
            if (self.last_reading_time == timestamp and 
                self.last_reading_value == float(value)):
                logger.info("Same reading already retrieved, will retry in 20 seconds")
                # For duplicate readings, wait only 20 seconds before retrying
                # instead of the full interval (sensor hasn't updated yet)
                self.next_expected_reading_time = datetime.now() + timedelta(seconds=20)
                return None
            
            self.last_reading_time = timestamp
            self.last_reading_value = float(value)
            
            # Calculate next expected reading time: timestamp + configured interval
            self.next_expected_reading_time = timestamp + timedelta(seconds=self.settings.sensor_reading_interval_seconds)
            logger.info(f"Next reading expected at: {self.next_expected_reading_time.strftime('%H:%M:%S')} (timestamp + {self.settings.sensor_reading_interval_seconds}s)")
            
            logger.info(f"Retrieved glucose reading: {reading.value} {reading.unit}, trend: {reading.trend}, timestamp: {reading.timestamp}")
            return reading
            
        except Exception as e:
            logger.error(f"Error retrieving glucose reading: {e}")
            logger.debug(f"Available attributes in bg object: {dir(bg) if 'bg' in locals() else 'bg not available'}")
            return None
    
    def get_recent_readings(self, hours: int = 3) -> List[GlucoseReading]:
        try:
            readings = self.dexcom.get_glucose_readings(minutes=hours * 60)
            glucose_readings = []
            
            for bg in readings:
                # Use correct pydexcom attribute names
                timestamp = bg.time
                value = bg.value
                trend_desc = bg.trend_description
                
                if value is not None:
                    reading = GlucoseReading(
                        timestamp=timestamp,
                        value=float(value),
                        trend=self._map_trend(trend_desc),
                        unit="mg/dL"
                    )
                    glucose_readings.append(reading)
            
            logger.info(f"Retrieved {len(glucose_readings)} recent readings")
            return glucose_readings
            
        except Exception as e:
            logger.error(f"Error retrieving recent readings: {e}")
            return []
    
    def _map_trend(self, trend_description: str) -> str:
        trend_mapping = {
            "rising quickly": "very_fast_up",
            "rising": "fast_up", 
            "rising slightly": "up",
            "steady": "no_change",
            "falling slightly": "down",
            "falling": "fast_down",
            "falling quickly": "very_fast_down"
        }
        
        if trend_description:
            trend_lower = trend_description.lower()
            return trend_mapping.get(trend_lower, "no_change")
        
        return "no_change"
    
    def is_new_reading_available(self) -> bool:
        # Always allow first reading
        if self.next_expected_reading_time is None:
            return True
        
        # Check if we've reached the expected next reading time
        now = datetime.now()
        if now >= self.next_expected_reading_time:
            logger.info(f"Expected reading time reached ({self.next_expected_reading_time.strftime('%H:%M:%S')})")
            return True
        
        time_until_next = (self.next_expected_reading_time - now).total_seconds()
        logger.info(f"Next reading not due for {time_until_next:.0f} seconds")
        return False
    
    def wait_for_next_reading(self) -> float:
        # If no expected time set, don't wait
        if self.next_expected_reading_time is None:
            return 0.0
        
        now = datetime.now()
        if now >= self.next_expected_reading_time:
            return 0.0
        
        wait_seconds = (self.next_expected_reading_time - now).total_seconds()
        logger.info(f"Waiting {wait_seconds:.0f} seconds for next reading (based on sensor timestamp + {self.settings.sensor_reading_interval_seconds}s)")
        return wait_seconds
    
    
    def reconnect(self):
        logger.info("Attempting to reconnect to Dexcom...")
        try:
            self._connect()
            return True
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        try:
            test_reading = self.dexcom.get_current_glucose_reading()
            logger.info("Dexcom connection test successful")
            return True
        except Exception as e:
            logger.error(f"Dexcom connection test failed: {e}")
            return False