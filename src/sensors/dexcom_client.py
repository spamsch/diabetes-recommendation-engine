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
        self.last_processed_time = None  # When we last processed a reading
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
                logger.debug("Same reading already retrieved, returning None")
                return None
            
            self.last_reading_time = timestamp
            self.last_reading_value = float(value)
            self.last_processed_time = datetime.now()
            logger.info(f"Retrieved glucose reading: {reading.value} {reading.unit}, trend: {reading.trend}")
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
        if self.last_processed_time is None:
            return True
        
        # Check if enough time has passed since we last processed a reading
        time_since_last_processed = datetime.now() - self.last_processed_time
        expected_interval = timedelta(minutes=self.settings.poll_interval_minutes)
        
        # Only consider a new reading available if enough time has passed since processing
        # This prevents multiple identical readings from being processed
        logger.info(f"Time since last processed: {time_since_last_processed}, expected interval: {expected_interval}")
        return time_since_last_processed >= expected_interval
    
    def wait_for_next_reading(self) -> float:
        if self.last_processed_time is None:
            return 0.0
        
        expected_next_time = (
            self.last_processed_time + 
            timedelta(minutes=self.settings.poll_interval_minutes)
        )
        
        now = datetime.now()
        if now >= expected_next_time:
            return 0.0
        
        wait_seconds = (expected_next_time - now).total_seconds()
        logger.info(f"Waiting {wait_seconds:.0f} seconds for next reading")
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