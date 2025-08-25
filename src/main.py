import logging
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional
import argparse

from .config import Settings
from .database import GlucoseDatabase, GlucoseReading
from .sensors import DexcomClient, MockDexcomClient
from .analysis import TrendAnalyzer, GlucosePredictor, IOBCalculator
from .analysis.recommendations import RecommendationEngine
from .notifications import TelegramNotifier, TelegramCommandBridge
from .terminal import UserInputHandler

logger = logging.getLogger(__name__)

class GlucoseMonitor:
    """Main glucose monitoring application"""
    
    def __init__(self, use_mock: bool = False, env_file: str = ".env"):
        self.running = True
        self.use_mock = use_mock
        self.last_processed_reading = None  # Track last processed reading to avoid duplicates
        
        # Initialize components
        self.settings = Settings(env_file)
        self.db = GlucoseDatabase(self.settings.database_path)
        
        # Initialize sensor client
        if use_mock:
            self.sensor_client = MockDexcomClient(self.settings)
            logger.info("Using mock Dexcom client for testing")
        else:
            self.sensor_client = DexcomClient(self.settings)
            logger.info("Using real Dexcom client")
        
        # Initialize analyzers
        self.trend_analyzer = TrendAnalyzer(self.settings)
        self.predictor = GlucosePredictor(self.settings)
        self.iob_calculator = IOBCalculator(self.settings)
        self.recommendation_engine = RecommendationEngine(self.settings)
        
        # Initialize notifier
        self.telegram_notifier = TelegramNotifier(self.settings)
        
        # Initialize user input handler
        self.user_input_handler = UserInputHandler(self.db, self.settings)
        
        # Initialize Telegram command bridge
        self.telegram_bridge = TelegramCommandBridge(
            self.telegram_notifier, self.user_input_handler, self.db, self.settings
        )
        
        # Register callbacks with both user input handler and telegram bridge
        callbacks = {
            'insulin_logged': self._on_insulin_logged,
            'carbs_logged': self._on_carbs_logged,
            'iob_override_set': self._on_iob_override_set,
            'quit_requested': self._on_quit_requested,
            'get_next_reading_time': self._get_next_reading_time
        }
        
        for event, callback in callbacks.items():
            self.user_input_handler.register_callback(event, callback)
            # Also register with telegram bridge's command processor
            if hasattr(self.telegram_bridge, 'command_processor'):
                self.telegram_bridge.command_processor.register_callback(event, callback)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Performance tracking
        self.last_cleanup_time = datetime.now()
        self.readings_processed = 0
        
        logger.info("Glucose monitor initialized successfully")
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Starting glucose monitoring...")
        
        # Test connections
        if not self._test_connections():
            logger.error("Connection tests failed. Exiting.")
            return
        
        # Start user input handler
        self.user_input_handler.start()
        
        while self.running:
            try:
                self._monitoring_cycle()
                self._wait_for_next_cycle()
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                self._handle_error(e)
        
        self._cleanup()
        logger.info("Glucose monitoring stopped")
    
    def _monitoring_cycle(self):
        """Execute one monitoring cycle"""
        logger.info("Starting monitoring cycle...")
        
        # Get current glucose reading
        reading = self._get_current_reading()
        if not reading:
            return
        
        # Check if this is the same reading we already processed
        if (self.last_processed_reading and 
            reading.timestamp == self.last_processed_reading.timestamp and 
            reading.value == self.last_processed_reading.value):
            logger.debug("Same reading already processed, skipping")
            return
        
        # Store reading in database
        reading_id = self.db.insert_reading(reading)
        self.readings_processed += 1
        self.last_processed_reading = reading
        
        # Get recent readings for analysis
        recent_readings = self.db.get_latest_readings(self.settings.analysis_window_size)
        
        if len(recent_readings) < 2:
            logger.info("Not enough readings for analysis yet")
            return
        
        # Perform trend analysis
        trend_analysis = self.trend_analyzer.analyze_trend(recent_readings)
        logger.info(f"Trend analysis: {trend_analysis['trend']} "
                   f"({trend_analysis['rate_of_change']:.1f} mg/dL/min)")
        
        # Detect patterns
        patterns = self.trend_analyzer.detect_patterns(recent_readings)
        if patterns['patterns']:
            logger.info(f"Detected patterns: {[p['type'] for p in patterns['patterns']]}")
        
        # Make prediction
        prediction = self.predictor.predict_future_value(recent_readings)
        if prediction['predicted_value']:
            logger.info(f"Prediction: {prediction['predicted_value']} mg/dL "
                       f"in {self.settings.prediction_minutes_ahead} min "
                       f"(confidence: {prediction['confidence']})")
        
        # Get IOB/COB data
        current_time = reading.timestamp
        active_insulin = self.db.get_active_insulin(current_time)
        active_carbs = self.db.get_active_carbs(current_time)
        
        # Check for IOB override (from Omnipod/pump)
        iob_override_entry = self.db.get_latest_iob_override(current_time)
        iob_override_value = iob_override_entry.iob_value if iob_override_entry else None
        
        iob_cob_data = None
        if active_insulin or active_carbs or iob_override_value is not None:
            iob_cob_data = self.iob_calculator.get_iob_cob_summary(
                current_time, active_insulin, active_carbs, reading.value, iob_override_value
            )
            
            iob_source = ""
            if iob_cob_data['iob'].get('is_override'):
                iob_source = f" (from {iob_override_entry.source})"
            
            logger.info(f"IOB: {iob_cob_data['iob']['total_iob']:.1f}u{iob_source}, "
                       f"COB: {iob_cob_data['cob']['total_cob']:.1f}g")
        
        # Generate recommendations with IOB/COB context
        recommendations = self.recommendation_engine.get_recommendations(
            recent_readings, trend_analysis, prediction, iob_cob_data
        )
        
        if recommendations:
            logger.info(f"Generated {len(recommendations)} recommendations")
            
            # Store recommendations in database
            for rec in recommendations:
                self.db.insert_recommendation(
                    timestamp=rec['timestamp'],
                    rec_type=rec['type'],
                    message=rec['message'],
                    glucose_value=reading.value,
                    parameters=str(rec.get('parameters', {}))
                )
            
            # Send critical recommendations immediately
            critical_recs = self.recommendation_engine.get_critical_recommendations(recommendations)
            if critical_recs:
                self.telegram_notifier.send_recommendations(
                    critical_recs,
                    {'value': reading.value, 'timestamp': reading.timestamp},
                    trend_analysis
                )
        else:
            # No recommendations - check if we should send a periodic status update
            if self.telegram_notifier.should_send_status_message():
                logger.info("Sending periodic status update to Telegram")
                self.telegram_notifier.send_status_update(
                    reading.value,
                    trend_analysis.get('trend', 'no_change'),
                    prediction
                )
        
        # Terminal output if enabled
        if self.settings.enable_terminal_output:
            self._display_terminal_output(reading, trend_analysis, prediction, recommendations, iob_cob_data)
        
        # Periodic cleanup
        self._periodic_cleanup()
        
        logger.info(f"Monitoring cycle completed. Total readings: {self.readings_processed}")
    
    def _get_current_reading(self) -> Optional[GlucoseReading]:
        """Get current glucose reading from sensor"""
        try:
            # Check if new reading is available
            if not self.sensor_client.is_new_reading_available():
                logger.info("No new reading available yet")
                return None
            
            reading = self.sensor_client.get_current_reading()
            if reading:
                logger.info(f"New reading: {reading.value} mg/dL at {reading.timestamp}")
                return reading
            else:
                logger.warning("Failed to get current reading")
                return None
                
        except Exception as e:
            logger.error(f"Error getting glucose reading: {e}")
            # Try to reconnect
            if self.sensor_client.reconnect():
                logger.info("Sensor reconnection successful")
            return None
    
    def _wait_for_next_cycle(self):
        """Wait for the next monitoring cycle"""
        wait_seconds = self.sensor_client.wait_for_next_reading()
        
        if wait_seconds > 0:
            logger.info(f"Waiting {wait_seconds:.0f} seconds for next reading...")
            
            # Sleep in small intervals to allow for graceful shutdown
            sleep_interval = min(2, wait_seconds)  # Sleep max 2 seconds at a time
            total_slept = 0
            
            while total_slept < wait_seconds and self.running:
                time.sleep(min(sleep_interval, wait_seconds - total_slept))
                total_slept += sleep_interval
    
    def _test_connections(self) -> bool:
        """Test all connections"""
        logger.info("Testing connections...")
        
        # Test sensor connection
        if not self.sensor_client.test_connection():
            logger.error("Sensor connection test failed")
            return False
        
        # Test Telegram connection (optional)
        if self.telegram_notifier.enabled:
            if not self.telegram_notifier.test_connection():
                logger.warning("Telegram connection test failed (continuing anyway)")
        
        logger.info("All connection tests passed")
        return True
    
    def _display_terminal_output(self, reading: GlucoseReading, 
                               trend_analysis: dict, prediction: dict, 
                               recommendations: list, iob_cob_data: dict = None):
        """Display current status in terminal"""
        print("\n" + "="*60)
        print(f"GLUCOSE MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Current reading
        trend_arrow = self._get_trend_arrow(trend_analysis.get('trend', 'no_change'))
        print(f"Current Glucose: {reading.value} mg/dL {trend_arrow}")
        print(f"Timestamp: {reading.timestamp.strftime('%H:%M:%S')}")
        print(f"Trend: {trend_analysis.get('trend', 'unknown').replace('_', ' ').title()}")
        print(f"Rate of Change: {trend_analysis.get('rate_of_change', 0):.1f} mg/dL/min")
        
        # IOB/COB information
        if iob_cob_data:
            print(f"\nActive Factors:")
            iob = iob_cob_data['iob']['total_iob']
            cob = iob_cob_data['cob']['total_cob']
            if iob > 0.1:
                print(f"  💉 Insulin on Board: {iob:.1f} units")
            if cob > 1.0:
                print(f"  🍎 Carbs on Board: {cob:.1f}g")
            if iob > 0.1 or cob > 1.0:
                impact = iob_cob_data['impact']
                print(f"  📊 Net Effect: {impact['net_effect']:+.1f} mg/dL")
                print(f"  🎯 Predicted: {impact['predicted_glucose']:.0f} mg/dL")
        
        # Prediction
        if prediction.get('predicted_value'):
            print(f"\nPrediction ({self.settings.prediction_minutes_ahead} min):")
            print(f"  Value: {prediction['predicted_value']} mg/dL")
            print(f"  Confidence: {prediction['confidence'].title()}")
            print(f"  Method: {prediction['method'].replace('_', ' ').title()}")
        
        # Recommendations
        if recommendations:
            print(f"\nRecommendations ({len(recommendations)}):")
            for i, rec in enumerate(recommendations, 1):
                urgency = rec.get('urgency', 'normal')
                print(f"  {i}. [{rec['type'].upper()}] {rec['message']}")
                if urgency in ['critical', 'high']:
                    print(f"     {urgency.upper()} priority")
        else:
            print("\nNo recommendations at this time")
        
        print("="*60)
    
    def _get_trend_arrow(self, trend: str) -> str:
        """Get arrow symbol for trend"""
        arrows = {
            'very_fast_up': '↑↑↑',
            'fast_up': '↑↑',
            'up': '↑',
            'no_change': '→',
            'down': '↓',
            'fast_down': '↓↓',
            'very_fast_down': '↓↓↓'
        }
        return arrows.get(trend, '→')
    
    def _periodic_cleanup(self):
        """Perform periodic cleanup tasks"""
        now = datetime.now()
        
        # Cleanup old data daily
        if (now - self.last_cleanup_time).total_seconds() > 24 * 60 * 60:
            logger.info("Performing database cleanup...")
            self.db.cleanup_old_data(self.settings.data_retention_days)
            self.last_cleanup_time = now
    
    def _handle_error(self, error: Exception):
        """Handle errors during monitoring"""
        logger.error(f"Monitoring error: {error}")
        
        # Send error notification for critical errors
        if "connection" in str(error).lower() or "timeout" in str(error).lower():
            self.telegram_notifier.send_alert(
                "error",
                f"Monitoring system error: {str(error)[:100]}",
                urgency='medium'
            )
        
        # Wait before retrying
        time.sleep(30)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _on_insulin_logged(self, entry):
        """Callback when insulin is logged"""
        logger.info(f"Insulin logged via terminal: {entry.units}u {entry.insulin_type}")
    
    def _on_carbs_logged(self, entry):
        """Callback when carbs are logged"""
        logger.info(f"Carbs logged via terminal: {entry.grams}g {entry.carb_type}")
    
    def _on_iob_override_set(self, entry):
        """Callback when IOB override is set"""
        logger.info(f"IOB override set via terminal: {entry.iob_value:.1f}u from {entry.source}")
    
    def _get_next_reading_time(self):
        """Callback to get next reading time info"""
        try:
            wait_seconds = self.sensor_client.wait_for_next_reading()
            return {
                'wait_seconds': wait_seconds,
                'last_reading_time': self.sensor_client.last_reading_time,
                'next_expected_time': self.sensor_client.next_expected_reading_time
            }
        except Exception as e:
            logger.error(f"Error getting next reading time: {e}")
            return None
    
    
    def _on_quit_requested(self):
        """Callback when user requests quit"""
        logger.info("Quit requested via terminal")
        self.running = False
    
    def _cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources...")
        
        # Stop user input handler and Telegram bridge
        self.user_input_handler.stop()
        self.telegram_bridge.stop()
        
        # Send shutdown notification
        self.telegram_notifier.send_alert(
            "shutdown",
            f"Glucose monitoring system stopped. Processed {self.readings_processed} readings.",
            urgency='low'
        )
        
        # Final database cleanup
        self._periodic_cleanup()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Glucose Monitoring System')
    parser.add_argument('--mock', action='store_true', 
                       help='Use mock Dexcom client for testing')
    parser.add_argument('--env-file', default='.env',
                       help='Environment file path')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('glucose_monitor.log')
        ]
    )
    
    try:
        monitor = GlucoseMonitor(
            use_mock=args.mock,
            env_file=args.env_file
        )
        monitor.run()
    except Exception as e:
        logger.error(f"Failed to start glucose monitor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()