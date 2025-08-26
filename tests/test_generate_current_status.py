import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os
import tempfile

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import GlucoseMonitor
from src.database import GlucoseReading, InsulinEntry, CarbEntry, IOBOverride


class TestGenerateCurrentStatus(unittest.TestCase):
    """Test the _generate_current_status_with_recommendations method"""

    def setUp(self):
        """Set up test fixtures"""
        # Create test data
        self.current_time = datetime.now()
        self.test_readings = [
            GlucoseReading(
                value=120.0,
                timestamp=self.current_time - timedelta(minutes=5),
                trend="up"
            ),
            GlucoseReading(
                value=115.0,
                timestamp=self.current_time - timedelta(minutes=10),
                trend="up"
            ),
            GlucoseReading(
                value=110.0,
                timestamp=self.current_time - timedelta(minutes=15),
                trend="no_change"
            )
        ]

    def create_fresh_monitor(self):
        """Create a fresh monitor instance with temporary database"""
        # Create a temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        with patch('src.main.TelegramNotifier') as mock_telegram:
            mock_telegram.return_value.enabled = False
            with patch('src.main.TelegramCommandBridge'):
                with patch('src.config.Settings') as mock_settings:
                    mock_settings.return_value.database_path = temp_db.name
                    mock_settings.return_value.analysis_window_size = 20
                    mock_settings.return_value.prediction_minutes_ahead = 15
                    mock_settings.return_value.trend_calculation_points = 10
                    mock_settings.return_value.low_glucose_threshold = 70
                    mock_settings.return_value.high_glucose_threshold = 180
                    mock_settings.return_value.critical_low_threshold = 55
                    mock_settings.return_value.critical_high_threshold = 250
                    mock_settings.return_value.enable_terminal_output = False
                    mock_settings.return_value.data_retention_days = 30
                    
                    monitor = GlucoseMonitor(use_mock=True, env_file=".env")
                    
        return monitor, temp_db.name

    def cleanup_monitor(self, monitor):
        """Clean up monitor resources"""
        if hasattr(monitor, 'user_input_handler'):
            monitor.user_input_handler.stop()
        if hasattr(monitor, 'telegram_bridge'):
            monitor.telegram_bridge.stop()

    def test_generate_status_with_no_readings(self):
        """Test status generation when no readings are available"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Mock the database to return no readings
            with patch.object(monitor.db, 'get_latest_readings', return_value=[]):
                result = monitor._generate_current_status_with_recommendations()

                self.assertFalse(result['success'])
                self.assertIn('No recent glucose readings available', result['message'])
                self.assertEqual(result['data'], {})
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_generate_status_with_basic_readings(self):
        """Test status generation with basic glucose readings"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Mock database methods to return only our test data
            with patch.object(monitor.db, 'get_latest_readings', return_value=self.test_readings):
                with patch.object(monitor.db, 'get_active_insulin', return_value=[]):
                    with patch.object(monitor.db, 'get_active_carbs', return_value=[]):
                        with patch.object(monitor.db, 'get_latest_iob_override', return_value=None):
                            result = monitor._generate_current_status_with_recommendations()

                            self.assertTrue(result['success'])
                            self.assertEqual(result['message'], 'Current status with updated recommendations')

                            # Check glucose data structure
                            glucose_data = result['data']['glucose']
                            self.assertIsInstance(glucose_data['value'], (int, float))
                            self.assertGreater(glucose_data['value'], 0)  # Should be a positive glucose value
                            self.assertIn('trend', glucose_data)
                            self.assertIn('timestamp', glucose_data)
                            self.assertIn('rate_of_change', glucose_data)
                            self.assertIsInstance(glucose_data['rate_of_change'], (int, float))

                            # Check prediction exists
                            self.assertIn('prediction', result['data'])

                            # Check recommendations exist
                            self.assertIn('recommendations', result['data'])

                            # IOB/COB should be None since no insulin/carbs logged
                            self.assertIsNone(result['data']['iob_cob'])
                            self.assertIsNone(result['data']['iob_source'])
            
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_generate_status_with_insulin_entries(self):
        """Test status generation with active insulin entries"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            # Add insulin entry
            insulin_entry = InsulinEntry(
                timestamp=self.current_time - timedelta(minutes=30),
                units=5.0,
                insulin_type="rapid",
                notes="Test insulin"
            )
            monitor.db.insert_insulin_entry(insulin_entry)

            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            # Should now have IOB/COB data
            self.assertIsNotNone(result['data']['iob_cob'])
            iob_cob = result['data']['iob_cob']

            # Check IOB data structure
            self.assertIn('iob', iob_cob)
            self.assertIn('cob', iob_cob)
            self.assertIn('impact', iob_cob)

            # IOB should be greater than 0
            self.assertGreater(iob_cob['iob']['total_iob'], 0)
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_generate_status_with_carb_entries(self):
        """Test status generation with active carb entries"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            # Add carb entry
            carb_entry = CarbEntry(
                timestamp=self.current_time - timedelta(minutes=30),
                grams=30.0,
                carb_type="meal",
                notes="Test carbs"
            )
            monitor.db.insert_carb_entry(carb_entry)

            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            # Should have IOB/COB data
            self.assertIsNotNone(result['data']['iob_cob'])
            iob_cob = result['data']['iob_cob']

            # COB should be greater than 0
            self.assertGreater(iob_cob['cob']['total_cob'], 0)
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_generate_status_with_iob_override(self):
        """Test status generation with IOB override"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            # Add IOB override entry very recent to ensure it's picked up
            iob_override = IOBOverride(
                timestamp=self.current_time - timedelta(seconds=30),
                iob_value=3.5,
                source="manual",
                notes="Test override"
            )
            monitor.db.insert_iob_override(iob_override)

            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            # Should have IOB/COB data
            self.assertIsNotNone(result['data']['iob_cob'])
            iob_cob = result['data']['iob_cob']

            # IOB should reflect the override value (within small tolerance for timing)
            self.assertAlmostEqual(iob_cob['iob']['total_iob'], 3.5, places=1)
            self.assertTrue(iob_cob['iob']['is_override'])

            # Should have IOB source
            self.assertEqual(result['data']['iob_source'], "manual")
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_generate_status_with_all_data_types(self):
        """Test status generation with insulin, carbs, and IOB override"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            # Add insulin entry
            insulin_entry = InsulinEntry(
                timestamp=self.current_time - timedelta(minutes=60),
                units=4.0,
                insulin_type="rapid",
                notes="Test insulin"
            )
            monitor.db.insert_insulin_entry(insulin_entry)

            # Add carb entry
            carb_entry = CarbEntry(
                timestamp=self.current_time - timedelta(minutes=45),
                grams=25.0,
                carb_type="snack",
                notes="Test carbs"
            )
            monitor.db.insert_carb_entry(carb_entry)

            # Add IOB override (should take precedence over calculated IOB)
            iob_override = IOBOverride(
                timestamp=self.current_time - timedelta(seconds=30),
                iob_value=2.8,
                source="omnipod",
                notes="From pump"
            )
            monitor.db.insert_iob_override(iob_override)

            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            # Should have comprehensive IOB/COB data
            self.assertIsNotNone(result['data']['iob_cob'])
            iob_cob = result['data']['iob_cob']

            # IOB should use override value (within tolerance for timing)
            self.assertAlmostEqual(iob_cob['iob']['total_iob'], 2.8, places=1)
            self.assertTrue(iob_cob['iob']['is_override'])

            # COB should still be calculated from carb entries
            self.assertGreater(iob_cob['cob']['total_cob'], 0)

            # Should have IOB source
            self.assertEqual(result['data']['iob_source'], "omnipod")

            # Should have impact calculations
            self.assertIn('impact', iob_cob)
            impact = iob_cob['impact']
            self.assertIn('net_effect', impact)
            self.assertIn('predicted_glucose', impact)
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_generate_status_handles_exceptions(self):
        """Test that method handles exceptions gracefully"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Force an exception by mocking a method to fail
            with patch.object(monitor.db, 'get_latest_readings',
                              side_effect=Exception("Database error")):
                result = monitor._generate_current_status_with_recommendations()

                self.assertFalse(result['success'])
                self.assertIn('Error generating current status', result['message'])
                self.assertIn('Database error', result['message'])
                self.assertEqual(result['data'], {})
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_prediction_integration(self):
        """Test that predictions are properly integrated"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            prediction = result['data']['prediction']
            self.assertIsNotNone(prediction)

            # Prediction should have required fields
            if prediction.get('predicted_value') is not None:
                self.assertIn('confidence', prediction)
                self.assertIn('method', prediction)
                self.assertIn('prediction_time', prediction)
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_recommendations_integration(self):
        """Test that recommendations are properly generated"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            recommendations = result['data']['recommendations']
            self.assertIsNotNone(recommendations)
            self.assertIsInstance(recommendations, list)

            # Each recommendation should have required fields
            for rec in recommendations:
                self.assertIn('type', rec)
                self.assertIn('message', rec)
                self.assertIn('timestamp', rec)
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)

    def test_trend_analysis_integration(self):
        """Test that trend analysis is properly performed"""
        monitor, temp_db_path = self.create_fresh_monitor()
        
        try:
            # Insert test readings first
            for reading in self.test_readings:
                monitor.db.insert_reading(reading)
                
            result = monitor._generate_current_status_with_recommendations()

            self.assertTrue(result['success'])

            glucose_data = result['data']['glucose']
            self.assertIn('trend', glucose_data)
            self.assertIn('rate_of_change', glucose_data)

            # Trend should be one of the expected values
            valid_trends = [
                'very_fast_up', 'fast_up', 'up', 'no_change',
                'down', 'fast_down', 'very_fast_down'
            ]
            self.assertIn(glucose_data['trend'], valid_trends)

            # Rate of change should be a number
            self.assertIsInstance(glucose_data['rate_of_change'], (int, float))
        finally:
            self.cleanup_monitor(monitor)
            os.unlink(temp_db_path)


if __name__ == '__main__':
    unittest.main()