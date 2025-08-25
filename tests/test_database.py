import pytest
import os
import tempfile
import sqlite3
from datetime import datetime, timedelta
from src.database import GlucoseDatabase, GlucoseReading

class TestGlucoseDatabase:
    
    def setup_method(self):
        # Create a temporary database for each test
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db = GlucoseDatabase(self.db_path)
    
    def teardown_method(self):
        # Clean up the temporary database
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_initialization(self):
        """Test that database and tables are created properly"""
        # Check that database file exists
        assert os.path.exists(self.db_path)
        
        # Check that tables exist
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check glucose_readings table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='glucose_readings'")
            assert cursor.fetchone() is not None
            
            # Check recommendations table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recommendations'")
            assert cursor.fetchone() is not None
            
            # Check index exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_glucose_timestamp'")
            assert cursor.fetchone() is not None
    
    def test_insert_reading(self):
        """Test inserting glucose readings"""
        reading = GlucoseReading(
            timestamp=datetime.now(),
            value=120.5,
            trend="up",
            unit="mg/dL"
        )
        
        reading_id = self.db.insert_reading(reading)
        
        assert reading_id is not None
        assert reading_id > 0
        
        # Verify the reading was inserted
        readings = self.db.get_latest_readings(1)
        assert len(readings) == 1
        assert readings[0].value == 120.5
        assert readings[0].trend == "up"
        assert readings[0].unit == "mg/dL"
    
    def test_get_latest_readings(self):
        """Test retrieving latest readings"""
        # Insert multiple readings
        base_time = datetime.now()
        readings_data = [
            (base_time - timedelta(minutes=10), 100.0, "down"),
            (base_time - timedelta(minutes=5), 110.0, "up"),
            (base_time, 120.0, "no_change")
        ]
        
        for timestamp, value, trend in readings_data:
            reading = GlucoseReading(
                timestamp=timestamp,
                value=value,
                trend=trend
            )
            self.db.insert_reading(reading)
        
        # Get latest 2 readings
        latest = self.db.get_latest_readings(2)
        
        assert len(latest) == 2
        # Should be in reverse chronological order (most recent first)
        assert latest[0].value == 120.0
        assert latest[1].value == 110.0
    
    def test_get_readings_since(self):
        """Test retrieving readings since a specific time"""
        base_time = datetime.now()
        since_time = base_time - timedelta(minutes=7)
        
        readings_data = [
            (base_time - timedelta(minutes=15), 90.0, "down"),   # Before since_time
            (base_time - timedelta(minutes=5), 110.0, "up"),    # After since_time
            (base_time, 120.0, "no_change")                     # After since_time
        ]
        
        for timestamp, value, trend in readings_data:
            reading = GlucoseReading(
                timestamp=timestamp,
                value=value,
                trend=trend
            )
            self.db.insert_reading(reading)
        
        recent_readings = self.db.get_readings_since(since_time)
        
        # Should only get the 2 readings after since_time
        assert len(recent_readings) == 2
        values = [r.value for r in recent_readings]
        assert 90.0 not in values
        assert 110.0 in values
        assert 120.0 in values
    
    def test_insert_recommendation(self):
        """Test inserting recommendations"""
        timestamp = datetime.now()
        rec_id = self.db.insert_recommendation(
            timestamp=timestamp,
            rec_type="insulin",
            message="Consider 2.0 units of rapid-acting insulin",
            glucose_value=200.0,
            parameters='{"units": 2.0, "reason": "high_glucose"}'
        )
        
        assert rec_id is not None
        assert rec_id > 0
        
        # Verify recommendation was inserted
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[2] == "insulin"  # recommendation_type
            assert row[3] == "Consider 2.0 units of rapid-acting insulin"  # message
            assert row[4] == 200.0  # glucose_value
    
    def test_mark_recommendation_sent(self):
        """Test marking recommendations as sent"""
        timestamp = datetime.now()
        rec_id = self.db.insert_recommendation(
            timestamp=timestamp,
            rec_type="carbohydrate",
            message="Take 15g carbs immediately",
            glucose_value=60.0
        )
        
        # Initially should not be marked as sent
        unsent = self.db.get_unsent_recommendations()
        assert len(unsent) == 1
        assert unsent[0][0] == rec_id
        
        # Mark as sent
        self.db.mark_recommendation_sent(rec_id)
        
        # Should no longer appear in unsent
        unsent_after = self.db.get_unsent_recommendations()
        assert len(unsent_after) == 0
    
    def test_get_unsent_recommendations(self):
        """Test retrieving unsent recommendations"""
        timestamp = datetime.now()
        
        # Insert multiple recommendations
        rec_id1 = self.db.insert_recommendation(
            timestamp=timestamp,
            rec_type="insulin",
            message="Message 1",
            glucose_value=200.0
        )
        
        rec_id2 = self.db.insert_recommendation(
            timestamp=timestamp,
            rec_type="carbohydrate", 
            message="Message 2",
            glucose_value=70.0
        )
        
        # Mark one as sent
        self.db.mark_recommendation_sent(rec_id1)
        
        # Should only get the unsent one
        unsent = self.db.get_unsent_recommendations()
        assert len(unsent) == 1
        assert unsent[0][0] == rec_id2
        assert unsent[0][2] == "carbohydrate"
        assert unsent[0][3] == "Message 2"
    
    def test_cleanup_old_data(self):
        """Test cleaning up old data"""
        base_time = datetime.now()
        
        # Insert old and new glucose readings
        old_reading = GlucoseReading(
            timestamp=base_time - timedelta(days=35),  # Older than default 30 days
            value=100.0,
            trend="no_change"
        )
        new_reading = GlucoseReading(
            timestamp=base_time - timedelta(days=5),   # Within 30 days
            value=120.0,
            trend="up"
        )
        
        old_id = self.db.insert_reading(old_reading)
        new_id = self.db.insert_reading(new_reading)
        
        # Insert old and new recommendations
        old_rec_id = self.db.insert_recommendation(
            timestamp=base_time - timedelta(days=35),
            rec_type="insulin",
            message="Old recommendation",
            glucose_value=100.0
        )
        new_rec_id = self.db.insert_recommendation(
            timestamp=base_time - timedelta(days=5),
            rec_type="carbohydrate",
            message="New recommendation", 
            glucose_value=120.0
        )
        
        # Mark old recommendation as sent (so it can be cleaned up)
        self.db.mark_recommendation_sent(old_rec_id)
        
        # Run cleanup
        self.db.cleanup_old_data(days_to_keep=30)
        
        # Check that old data was removed
        all_readings = self.db.get_latest_readings(100)
        reading_ids = [r.id for r in all_readings]
        assert old_id not in reading_ids
        assert new_id in reading_ids
        
        # Check recommendations
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM recommendations")
            remaining_rec_ids = [row[0] for row in cursor.fetchall()]
            
            assert old_rec_id not in remaining_rec_ids  # Should be cleaned up
            assert new_rec_id in remaining_rec_ids      # Should remain
    
    def test_reading_with_id_assignment(self):
        """Test that readings get proper ID assignment"""
        reading = GlucoseReading(
            timestamp=datetime.now(),
            value=150.0,
            trend="fast_up"
        )
        
        # Initially should have no ID
        assert reading.id is None
        
        # Insert reading
        reading_id = self.db.insert_reading(reading)
        
        # Retrieve the reading
        readings = self.db.get_latest_readings(1)
        retrieved_reading = readings[0]
        
        # Should have the assigned ID
        assert retrieved_reading.id == reading_id
        assert retrieved_reading.id is not None
    
    def test_multiple_database_operations(self):
        """Test multiple operations in sequence"""
        base_time = datetime.now()
        
        # Insert readings and recommendations in a mixed sequence
        for i in range(5):
            timestamp = base_time - timedelta(minutes=i*5)
            
            # Insert reading
            reading = GlucoseReading(
                timestamp=timestamp,
                value=100 + i*10,
                trend="up" if i % 2 == 0 else "down"
            )
            reading_id = self.db.insert_reading(reading)
            
            # Insert recommendation every other time
            if i % 2 == 0:
                rec_id = self.db.insert_recommendation(
                    timestamp=timestamp,
                    rec_type="monitoring",
                    message=f"Check glucose in {i*5} minutes",
                    glucose_value=100 + i*10
                )
        
        # Verify all data is present
        all_readings = self.db.get_latest_readings(10)
        assert len(all_readings) == 5
        
        unsent_recs = self.db.get_unsent_recommendations()
        assert len(unsent_recs) == 3  # Should have 3 recommendations (i=0,2,4)
        
        # Verify readings are in correct order (most recent first)
        values = [r.value for r in all_readings]
        expected_values = [100, 110, 120, 130, 140]  # Most recent first
        assert values == expected_values

if __name__ == "__main__":
    pytest.main([__file__])