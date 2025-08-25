import os
import logging
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Settings:
    def __init__(self, env_file: str = ".env"):
        load_dotenv(env_file)
        self._validate_required_settings()
    
    def _validate_required_settings(self):
        required_settings = [
            "DEXCOM_USERNAME",
            "DEXCOM_PASSWORD"
        ]
        
        missing = []
        for setting in required_settings:
            if not os.getenv(setting):
                missing.append(setting)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    @property
    def dexcom_username(self) -> str:
        return os.getenv("DEXCOM_USERNAME")
    
    @property
    def dexcom_password(self) -> str:
        return os.getenv("DEXCOM_PASSWORD")
    
    @property
    def dexcom_ous(self) -> bool:
        return os.getenv("DEXCOM_OUS", "false").lower() == "true"
    
    @property
    def poll_interval_minutes(self) -> int:
        return int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
    
    @property
    def analysis_window_size(self) -> int:
        return int(os.getenv("ANALYSIS_WINDOW_SIZE", "15"))
    
    @property
    def prediction_minutes_ahead(self) -> int:
        return int(os.getenv("PREDICTION_MINUTES_AHEAD", "15"))
    
    @property
    def low_glucose_threshold(self) -> float:
        return float(os.getenv("LOW_GLUCOSE_THRESHOLD", "70"))
    
    @property
    def high_glucose_threshold(self) -> float:
        return float(os.getenv("HIGH_GLUCOSE_THRESHOLD", "180"))
    
    @property
    def critical_low_threshold(self) -> float:
        return float(os.getenv("CRITICAL_LOW_THRESHOLD", "55"))
    
    @property
    def critical_high_threshold(self) -> float:
        return float(os.getenv("CRITICAL_HIGH_THRESHOLD", "300"))
    
    @property
    def insulin_effectiveness(self) -> float:
        return float(os.getenv("INSULIN_EFFECTIVENESS", "40.0"))
    
    @property
    def insulin_unit_ratio(self) -> float:
        return float(os.getenv("INSULIN_UNIT_RATIO", "0.2"))
    
    @property
    def rapid_rise_threshold(self) -> float:
        return float(os.getenv("RAPID_RISE_THRESHOLD", "3.0"))
    
    @property
    def rapid_fall_threshold(self) -> float:
        return float(os.getenv("RAPID_FALL_THRESHOLD", "-3.0"))
    
    @property
    def stable_variance_threshold(self) -> float:
        return float(os.getenv("STABLE_VARIANCE_THRESHOLD", "10.0"))
    
    @property
    def telegram_bot_url(self) -> Optional[str]:
        return os.getenv("TELEGRAM_BOT_URL")
    
    @property
    def telegram_chat_id(self) -> Optional[str]:
        return os.getenv("TELEGRAM_CHAT_ID")
    
    @property
    def database_path(self) -> str:
        return os.getenv("DATABASE_PATH", "glucose_monitor.db")
    
    @property
    def enable_terminal_output(self) -> bool:
        return os.getenv("ENABLE_TERMINAL_OUTPUT", "true").lower() == "true"
    
    @property
    def enable_graphing(self) -> bool:
        return os.getenv("ENABLE_GRAPHING", "true").lower() == "true"
    
    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()
    
    @property
    def data_retention_days(self) -> int:
        return int(os.getenv("DATA_RETENTION_DAYS", "30"))
    
    @property
    def trend_calculation_points(self) -> int:
        return int(os.getenv("TREND_CALCULATION_POINTS", "3"))
    
    @property
    def enable_insulin_recommendations(self) -> bool:
        return os.getenv("ENABLE_INSULIN_RECOMMENDATIONS", "true").lower() == "true"
    
    @property
    def enable_carb_recommendations(self) -> bool:
        return os.getenv("ENABLE_CARB_RECOMMENDATIONS", "true").lower() == "true"
    
    @property
    def carb_effectiveness(self) -> float:
        return float(os.getenv("CARB_EFFECTIVENESS", "15.0"))
    
    @property
    def target_glucose(self) -> float:
        return float(os.getenv("TARGET_GLUCOSE", "120.0"))
    
    @property
    def insulin_duration_rapid(self) -> int:
        return int(os.getenv("INSULIN_DURATION_RAPID", "180"))
    
    @property
    def insulin_duration_long(self) -> int:
        return int(os.getenv("INSULIN_DURATION_LONG", "720"))
    
    @property
    def carb_absorption_fast(self) -> int:
        return int(os.getenv("CARB_ABSORPTION_FAST", "90"))
    
    @property
    def carb_absorption_slow(self) -> int:
        return int(os.getenv("CARB_ABSORPTION_SLOW", "180"))
    
    @property
    def carb_to_glucose_ratio(self) -> float:
        return float(os.getenv("CARB_TO_GLUCOSE_RATIO", "3.5"))
    
    @property
    def iob_threshold_high(self) -> float:
        return float(os.getenv("IOB_THRESHOLD_HIGH", "2.0"))
    
    @property
    def cob_threshold_high(self) -> float:
        return float(os.getenv("COB_THRESHOLD_HIGH", "30.0"))
    
    @property
    def trend_down_threshold(self) -> float:
        return float(os.getenv("TREND_DOWN_THRESHOLD", "0.5"))
    
    @property
    def trend_fast_down_threshold(self) -> float:
        return float(os.getenv("TREND_FAST_DOWN_THRESHOLD", "2.0"))
    
    @property
    def trend_very_fast_down_threshold(self) -> float:
        return float(os.getenv("TREND_VERY_FAST_DOWN_THRESHOLD", "4.0"))
    
    @property
    def trend_up_threshold(self) -> float:
        return float(os.getenv("TREND_UP_THRESHOLD", "0.5"))
    
    @property
    def trend_fast_up_threshold(self) -> float:
        return float(os.getenv("TREND_FAST_UP_THRESHOLD", "2.0"))
    
    @property
    def trend_very_fast_up_threshold(self) -> float:
        return float(os.getenv("TREND_VERY_FAST_UP_THRESHOLD", "4.0"))
    
    def to_dict(self) -> dict:
        return {
            "dexcom_username": self.dexcom_username,
            "dexcom_ous": self.dexcom_ous,
            "poll_interval_minutes": self.poll_interval_minutes,
            "analysis_window_size": self.analysis_window_size,
            "prediction_minutes_ahead": self.prediction_minutes_ahead,
            "low_glucose_threshold": self.low_glucose_threshold,
            "high_glucose_threshold": self.high_glucose_threshold,
            "critical_low_threshold": self.critical_low_threshold,
            "critical_high_threshold": self.critical_high_threshold,
            "insulin_effectiveness": self.insulin_effectiveness,
            "insulin_unit_ratio": self.insulin_unit_ratio,
            "rapid_rise_threshold": self.rapid_rise_threshold,
            "rapid_fall_threshold": self.rapid_fall_threshold,
            "stable_variance_threshold": self.stable_variance_threshold,
            "telegram_bot_url": self.telegram_bot_url,
            "telegram_chat_id": self.telegram_chat_id,
            "database_path": self.database_path,
            "enable_terminal_output": self.enable_terminal_output,
            "enable_graphing": self.enable_graphing,
            "log_level": self.log_level,
            "data_retention_days": self.data_retention_days,
            "trend_calculation_points": self.trend_calculation_points,
            "enable_insulin_recommendations": self.enable_insulin_recommendations,
            "enable_carb_recommendations": self.enable_carb_recommendations,
            "carb_effectiveness": self.carb_effectiveness
        }