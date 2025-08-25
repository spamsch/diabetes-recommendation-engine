"""
Test to demonstrate how recommendations change after entering IOB.
Only mocks Telegram - uses real database, settings, and analysis components.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta

from src.database import GlucoseDatabase, GlucoseReading
from src.config import Settings
from src.commands import CommandProcessor
from src.analysis import TrendAnalyzer, GlucosePredictor, IOBCalculator
from src.analysis.recommendations import RecommendationEngine


class TestRecommendationChangeAfterIOB:
    """Test that demonstrates recommendation changes after IOB entry"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def settings(self):
        """Create test settings"""
        # Save original environment
        original_env = {}
        env_vars = [
            'DB_PATH', 'DEXCOM_USERNAME', 'DEXCOM_PASSWORD',
            'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'POLL_INTERVAL_MINUTES',
            'TARGET_GLUCOSE_MIN', 'TARGET_GLUCOSE_MAX',
            'INSULIN_SENSITIVITY_FACTOR', 'INSULIN_DURATION_RAPID',
            'CARB_ABSORPTION_FAST', 'CARB_ABSORPTION_SLOW',
            'ANALYSIS_WINDOW_SIZE', 'PREDICTION_MINUTES_AHEAD'
        ]

        for var in env_vars:
            if var in os.environ:
                original_env[var] = os.environ[var]

        # Set test environment variables
        test_env = {
            'POLL_INTERVAL_MINUTES': '5',
            'TARGET_GLUCOSE_MIN': '70',
            'TARGET_GLUCOSE_MAX': '180',
            'INSULIN_SENSITIVITY_FACTOR': '50',
            'INSULIN_DURATION_RAPID': '180',
            'CARB_ABSORPTION_FAST': '60',
            'CARB_ABSORPTION_SLOW': '180',
            'ANALYSIS_WINDOW_SIZE': '6',
            'PREDICTION_MINUTES_AHEAD': '30'
        }

        for key, value in test_env.items():
            os.environ[key] = value

        yield Settings()

        # Restore original environment
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]
        for var, value in original_env.items():
            os.environ[var] = value

    def test_recommendation_changes_after_iob_entry(self, temp_db, settings):
        """Test that insulin recommendations change after entering IOB"""
        # Initialize database and command processor
        db = GlucoseDatabase(temp_db)
        command_processor = CommandProcessor(db, settings)

        # Initialize analysis components
        trend_analyzer = TrendAnalyzer(settings)
        predictor = GlucosePredictor(settings)
        iob_calculator = IOBCalculator(settings)
        recommendation_engine = RecommendationEngine(settings)

        def get_current_recommendations():
            """Helper function to get current recommendations"""
            current_time = datetime.now()
            window_size = settings.analysis_window_size
            recent_readings = db.get_latest_readings(window_size)

            if len(recent_readings) < 2:
                return []

            # Analyze trend
            trend_analysis = trend_analyzer.analyze_trend(recent_readings)

            # Get current IOB/COB data
            active_insulin = db.get_active_insulin(current_time)
            active_carbs = db.get_active_carbs(current_time)
            iob_override_entry = db.get_latest_iob_override(current_time)
            iob_override_value = (iob_override_entry.iob_value
                                  if iob_override_entry else None)

            iob_cob_data = None
            if (active_insulin or active_carbs or
                    iob_override_value is not None):
                iob_cob_data = iob_calculator.get_iob_cob_summary(
                    current_time, active_insulin, active_carbs,
                    recent_readings[0].value, iob_override_value
                )

            # Generate predictions and recommendations
            prediction = predictor.predict_future_value(recent_readings)
            recommendations = recommendation_engine.get_recommendations(
                recent_readings, trend_analysis, prediction, iob_cob_data
            )

            return recommendations, iob_cob_data

        # Create high glucose scenario that would trigger insulin rec
        base_time = datetime.now()
        high_glucose_readings = []

        # Create readings showing sustained high glucose (220+ mg/dL)
        for i in range(6):  # 6 readings for analysis window
            # 25, 20, 15, 10, 5, 0 minutes ago
            reading_time = base_time - timedelta(minutes=5 * (5-i))
            glucose_value = 225 + i  # Rising glucose: 225->230

            reading = GlucoseReading(
                timestamp=reading_time,
                value=glucose_value,
                trend='up'
            )
            high_glucose_readings.append(reading)
            db.insert_reading(reading)

        print("\n=== SCENARIO SETUP ===")
        print(f"Created {len(high_glucose_readings)} glucose readings")
        latest_glucose = high_glucose_readings[-1].value
        print(f"Latest glucose: {latest_glucose} mg/dL (trending up)")
        print("No active insulin entries in database")

        # Get initial recommendations (should include insulin recommendation)
        print("\n=== STEP 1: GET INITIAL RECOMMENDATIONS ===")
        initial_recs, initial_iob_cob = get_current_recommendations()
        print(f"Initial recommendations count: {len(initial_recs)}")

        # Find insulin recommendation
        insulin_recs = [r for r in initial_recs
                        if r.get('type') == 'insulin']
        print(f"Insulin recommendations found: {len(insulin_recs)}")

        for i, rec in enumerate(insulin_recs):
            print(f"  {i+1}. {rec.get('message', 'No message')}")

        # Verify we have at least one insulin recommendation
        expected_msg = "Expected at least one insulin recommendation"
        assert len(insulin_recs) > 0, expected_msg
        initial_insulin_rec = insulin_recs[0]
        initial_msg = initial_insulin_rec.get('message')
        print(f"Primary insulin recommendation: {initial_msg}")

        # Step 2: Enter IOB that should affect recommendations
        print("\n=== STEP 2: ENTER IOB OVERRIDE ===")
        # Set IOB to a value that should reduce or eliminate insulin rec
        # For glucose of 230 mg/dL and ISF of 50, we'd normally need
        # ~1.2 units to get to 170. Setting IOB to 1.0 should reduce it
        iob_value = 1.0

        # Execute IOB override
        iob_result = command_processor.execute_iob_override(
            iob_value=iob_value,
            source='omnipod',
            notes='test iob entry'
        )

        assert iob_result.success, f"Failed to set IOB: {iob_result.error}"
        print(f"IOB set to {iob_value} units from omnipod")

        # Get updated recommendations after IOB entry
        print("\n=== STEP 3: GET UPDATED RECOMMENDATIONS ===")
        updated_recs, updated_iob_cob = get_current_recommendations()
        updated_insulin_recs = [r for r in updated_recs
                                if r.get('type') == 'insulin']

        print(f"Updated recommendations count: {len(updated_recs)}")
        print(f"Updated insulin recommendations: {len(updated_insulin_recs)}")

        for i, rec in enumerate(updated_insulin_recs):
            print(f"  {i+1}. {rec.get('message', 'No message')}")

        # Verify the recommendations changed
        if len(updated_insulin_recs) == 0:
            print("✅ SUCCESS: Insulin recommendation eliminated after IOB")
            change_type = "eliminated"
        else:
            # Compare recommendation messages to see if they changed
            updated_insulin_rec = updated_insulin_recs[0]
            initial_message = initial_insulin_rec.get('message', '')
            updated_message = updated_insulin_rec.get('message', '')

            if initial_message != updated_message:
                print("✅ SUCCESS: Insulin recommendation changed after IOB")
                print(f"  Before: {initial_message}")
                print(f"  After:  {updated_message}")
                change_type = "modified"
            else:
                print("⚠️  WARNING: Insulin recommendation unchanged")
                print(f"  Message: {initial_message}")
                change_type = "unchanged"

        # Verify IOB is now reflected in status
        if updated_iob_cob:
            current_iob = updated_iob_cob.get('iob', {}).get('total_iob', 0)
            is_override = updated_iob_cob.get('iob', {}).get('is_override',
                                                              False)
        else:
            current_iob = 0
            is_override = False

        print("\n=== FINAL STATUS VERIFICATION ===")
        print(f"Current IOB: {current_iob:.1f}u (override: {is_override})")
        print(f"Expected IOB: {iob_value} units")

        # Assertions to verify the test worked correctly
        expected_iob_msg = f"Expected IOB {iob_value}, got {current_iob}"
        assert current_iob == iob_value, expected_iob_msg
        assert is_override, "Expected IOB to be marked as override"
        expected_change_msg = (f"Expected recommendation to change, "
                               f"but it was {change_type}")
        assert change_type in ["eliminated", "modified"], expected_change_msg

        print("✅ TEST PASSED: Recommendations properly changed after IOB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])