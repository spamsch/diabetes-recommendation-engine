import pytest
import os
import tempfile
from datetime import datetime, timedelta
from src.database import GlucoseDatabase, InsulinEntry, CarbEntry


class TestIOBTrackingFix:
    """Test cases for the IOB tracking datetime comparison fix"""
    
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
    
    def test_active_insulin_datetime_comparison_fix(self):
        """Test that active insulin is found correctly with datetime comparison fix"""
        # Insert insulin entry
        insulin_time = datetime(2025, 8, 25, 20, 40, 4)
        insulin_entry = InsulinEntry(
            timestamp=insulin_time,
            units=0.3,
            insulin_type='rapid',
            duration_minutes=180
        )
        self.db.insert_insulin_entry(insulin_entry)
        
        # Check active insulin 4 minutes later (should be found)
        check_time = datetime(2025, 8, 25, 20, 44, 4)
        active_insulin = self.db.get_active_insulin(check_time)
        
        assert len(active_insulin) == 1
        assert active_insulin[0].units == 0.3
        assert active_insulin[0].insulin_type == 'rapid'
        assert active_insulin[0].timestamp == insulin_time
    
    def test_active_insulin_expired_entry(self):
        """Test that expired insulin entries are not returned"""
        # Insert insulin entry
        insulin_time = datetime(2025, 8, 25, 17, 0, 0)  # 3+ hours ago
        insulin_entry = InsulinEntry(
            timestamp=insulin_time,
            units=0.5,
            insulin_type='rapid',
            duration_minutes=180  # 3 hours
        )
        self.db.insert_insulin_entry(insulin_entry)
        
        # Check active insulin 4 hours later (should NOT be found)
        check_time = datetime(2025, 8, 25, 21, 0, 0)
        active_insulin = self.db.get_active_insulin(check_time)
        
        assert len(active_insulin) == 0
    
    def test_active_carbs_datetime_comparison_fix(self):
        """Test that active carbs tracking also uses correct datetime comparison"""
        # Insert carb entry
        carb_time = datetime(2025, 8, 25, 20, 30, 0)
        carb_entry = CarbEntry(
            timestamp=carb_time,
            grams=45.0,
            carb_type='fast',
            absorption_minutes=90
        )
        self.db.insert_carb_entry(carb_entry)
        
        # Check active carbs 1 hour later (should be found)
        check_time = datetime(2025, 8, 25, 21, 30, 0)
        active_carbs = self.db.get_active_carbs(check_time)
        
        assert len(active_carbs) == 1
        assert active_carbs[0].grams == 45.0
        assert active_carbs[0].carb_type == 'fast'
        assert active_carbs[0].timestamp == carb_time
    
    def test_multiple_insulin_entries_correct_filtering(self):
        """Test that multiple insulin entries are correctly filtered by time"""
        base_time = datetime(2025, 8, 25, 20, 0, 0)
        
        # Insert multiple insulin entries at different times
        entries = [
            InsulinEntry(timestamp=base_time - timedelta(hours=4), units=0.5, insulin_type='rapid', duration_minutes=180),  # Expired
            InsulinEntry(timestamp=base_time - timedelta(minutes=30), units=0.3, insulin_type='rapid', duration_minutes=180),  # Active
            InsulinEntry(timestamp=base_time - timedelta(minutes=10), units=0.2, insulin_type='rapid', duration_minutes=180),  # Active
        ]
        
        for entry in entries:
            self.db.insert_insulin_entry(entry)
        
        # Check active insulin at base_time
        active_insulin = self.db.get_active_insulin(base_time)
        
        # Should find 2 active entries (30 min and 10 min ago)
        assert len(active_insulin) == 2
        
        # Entries should be ordered by timestamp DESC
        assert active_insulin[0].timestamp == base_time - timedelta(minutes=10)  # Most recent first
        assert active_insulin[1].timestamp == base_time - timedelta(minutes=30)
        
        # Should not include the expired entry
        timestamps = [entry.timestamp for entry in active_insulin]
        assert base_time - timedelta(hours=4) not in timestamps
    
    def test_edge_case_exactly_at_expiry_time(self):
        """Test the edge case where we check exactly at insulin expiry time"""
        insulin_time = datetime(2025, 8, 25, 20, 0, 0)
        insulin_entry = InsulinEntry(
            timestamp=insulin_time,
            units=0.4,
            insulin_type='rapid',
            duration_minutes=180  # 3 hours
        )
        self.db.insert_insulin_entry(insulin_entry)
        
        # Check exactly at expiry time (should NOT be found due to > comparison)
        expiry_time = insulin_time + timedelta(minutes=180)
        active_insulin = self.db.get_active_insulin(expiry_time)
        
        assert len(active_insulin) == 0
    
    def test_edge_case_one_second_before_expiry(self):
        """Test that insulin is still active 1 second before expiry"""
        insulin_time = datetime(2025, 8, 25, 20, 0, 0)
        insulin_entry = InsulinEntry(
            timestamp=insulin_time,
            units=0.4,
            insulin_type='rapid',
            duration_minutes=180
        )
        self.db.insert_insulin_entry(insulin_entry)
        
        # Check 1 second before expiry (should still be found)
        almost_expiry = insulin_time + timedelta(minutes=180, seconds=-1)
        active_insulin = self.db.get_active_insulin(almost_expiry)
        
        assert len(active_insulin) == 1
    
    def test_isoformat_timestamp_handling(self):
        """Test that various datetime formats work correctly"""
        # Test with datetime object
        insulin_time = datetime(2025, 8, 25, 20, 40, 4, 123456)  # Include microseconds
        insulin_entry = InsulinEntry(
            timestamp=insulin_time,
            units=0.3,
            insulin_type='rapid',
            duration_minutes=180
        )
        self.db.insert_insulin_entry(insulin_entry)
        
        # Check with different datetime object (should work)
        check_time = datetime(2025, 8, 25, 20, 45, 0)
        active_insulin = self.db.get_active_insulin(check_time)
        
        assert len(active_insulin) == 1
        
        # Verify the microseconds are preserved in storage and retrieval
        stored_entry = active_insulin[0]
        assert stored_entry.timestamp == insulin_time  # Should match exactly