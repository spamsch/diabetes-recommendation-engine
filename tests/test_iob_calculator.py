import pytest
from datetime import datetime, timedelta
from src.config import Settings
from src.database import InsulinEntry, CarbEntry
from src.analysis.iob_calculator import IOBCalculator

class MockSettings:
    """Mock settings for testing"""
    def __init__(self):
        self.insulin_effectiveness = 40.0
        self.carb_to_glucose_ratio = 3.5
        self.target_glucose = 120.0

class TestIOBCalculator:
    
    def setup_method(self):
        self.settings = MockSettings()
        self.calculator = IOBCalculator(self.settings)
    
    def test_fresh_insulin_entry(self):
        """Test IOB calculation for fresh insulin entry"""
        current_time = datetime.now()
        
        # Insulin given 30 minutes ago
        entries = [
            InsulinEntry(
                timestamp=current_time - timedelta(minutes=30),
                units=2.0,
                insulin_type='rapid',
                duration_minutes=180
            )
        ]
        
        iob_data = self.calculator.calculate_iob(entries, current_time)
        
        # Should have significant IOB remaining for fresh insulin
        assert iob_data['total_iob'] > 1.5
        assert iob_data['entries_count'] == 1
        assert len(iob_data['breakdown']) == 1
        
        breakdown = iob_data['breakdown'][0]
        assert breakdown['original_units'] == 2.0
        assert breakdown['insulin_type'] == 'rapid'
        assert breakdown['minutes_ago'] == 30
    
    def test_old_insulin_entry(self):
        """Test IOB calculation for old insulin entry"""
        current_time = datetime.now()
        
        # Insulin given 4 hours ago (past duration)
        entries = [
            InsulinEntry(
                timestamp=current_time - timedelta(minutes=240),
                units=2.0,
                insulin_type='rapid',
                duration_minutes=180
            )
        ]
        
        iob_data = self.calculator.calculate_iob(entries, current_time)
        
        # Should have no IOB remaining
        assert iob_data['total_iob'] == 0.0
        assert iob_data['entries_count'] == 0
    
    def test_multiple_insulin_entries(self):
        """Test IOB calculation with multiple insulin entries"""
        current_time = datetime.now()
        
        entries = [
            InsulinEntry(
                timestamp=current_time - timedelta(minutes=30),
                units=1.5,
                insulin_type='rapid',
                duration_minutes=180
            ),
            InsulinEntry(
                timestamp=current_time - timedelta(minutes=90),
                units=2.0,
                insulin_type='rapid',
                duration_minutes=180
            )
        ]
        
        iob_data = self.calculator.calculate_iob(entries, current_time)
        
        # Should have IOB from both entries
        assert iob_data['total_iob'] > 1.0
        assert iob_data['entries_count'] == 2
    
    def test_carb_absorption_fresh(self):
        """Test COB calculation for fresh carb entry"""
        current_time = datetime.now()
        
        entries = [
            CarbEntry(
                timestamp=current_time - timedelta(minutes=30),
                grams=45.0,
                carb_type='mixed',
                absorption_minutes=120
            )
        ]
        
        cob_data = self.calculator.calculate_cob(entries, current_time)
        
        # Should have significant COB remaining
        assert cob_data['total_cob'] > 20.0
        assert cob_data['entries_count'] == 1
        
        breakdown = cob_data['breakdown'][0]
        assert breakdown['original_grams'] == 45.0
        assert breakdown['carb_type'] == 'mixed'
    
    def test_carb_absorption_complete(self):
        """Test COB calculation for fully absorbed carbs"""
        current_time = datetime.now()
        
        entries = [
            CarbEntry(
                timestamp=current_time - timedelta(minutes=150),
                grams=30.0,
                carb_type='fast',
                absorption_minutes=90
            )
        ]
        
        cob_data = self.calculator.calculate_cob(entries, current_time)
        
        # Should have no COB remaining
        assert cob_data['total_cob'] == 0.0
        assert cob_data['entries_count'] == 0
    
    def test_glucose_impact_calculation(self):
        """Test glucose impact estimation from IOB/COB"""
        current_glucose = 150.0
        
        # Mock IOB and COB data
        iob_data = {'total_iob': 1.5}
        cob_data = {'total_cob': 30.0}
        
        impact = self.calculator.estimate_glucose_impact(
            iob_data, cob_data, current_glucose
        )
        
        # IOB should lower glucose, COB should raise it
        assert impact['iob_effect'] < 0  # Negative = lowering
        assert impact['cob_effect'] > 0  # Positive = raising
        assert 'net_effect' in impact
        assert 'predicted_glucose' in impact
        
        # Check calculation accuracy
        expected_iob_effect = -1.5 * 40.0  # -60 mg/dL
        expected_cob_effect = 30.0 * 3.5   # +105 mg/dL
        
        assert abs(impact['iob_effect'] - expected_iob_effect) < 1.0
        assert abs(impact['cob_effect'] - expected_cob_effect) < 1.0
    
    def test_iob_cob_summary(self):
        """Test complete IOB/COB summary"""
        current_time = datetime.now()
        current_glucose = 160.0
        
        insulin_entries = [
            InsulinEntry(
                timestamp=current_time - timedelta(minutes=45),
                units=1.0,
                insulin_type='rapid',
                duration_minutes=180
            )
        ]
        
        carb_entries = [
            CarbEntry(
                timestamp=current_time - timedelta(minutes=20),
                grams=25.0,
                carb_type='fast',
                absorption_minutes=90
            )
        ]
        
        summary = self.calculator.get_iob_cob_summary(
            current_time, insulin_entries, carb_entries, current_glucose
        )
        
        # Check structure
        assert 'iob' in summary
        assert 'cob' in summary
        assert 'impact' in summary
        assert 'summary' in summary
        
        # Check summary flags
        assert summary['summary']['has_active_insulin'] is True
        assert summary['summary']['has_active_carbs'] is True
        assert 'net_glucose_trend' in summary['summary']
        assert 'recommendation_adjustment' in summary['summary']
    
    def test_recommendation_adjustments(self):
        """Test recommendation adjustment messages"""
        # High IOB scenario
        iob_data = {'total_iob': 2.5}
        cob_data = {'total_cob': 5.0}
        impact_data = {'net_effect': -80.0}
        
        adjustment = self.calculator._get_recommendation_adjustment(
            iob_data, cob_data, impact_data
        )
        
        assert 'High IOB' in adjustment
        assert 'avoid' in adjustment.lower()
        
        # High COB scenario
        iob_data = {'total_iob': 0.2}
        cob_data = {'total_cob': 40.0}
        impact_data = {'net_effect': 120.0}
        
        adjustment = self.calculator._get_recommendation_adjustment(
            iob_data, cob_data, impact_data
        )
        
        assert 'High COB' in adjustment
        assert 'rise' in adjustment.lower()

class TestInsulinActionCurves:
    """Test insulin action curve calculations"""
    
    def setup_method(self):
        self.settings = MockSettings()
        self.calculator = IOBCalculator(self.settings)
    
    def test_rapid_insulin_action_curve(self):
        """Test rapid-acting insulin action curve"""
        original_units = 2.0
        duration = 180
        
        # Test at different time points
        test_points = [0, 30, 60, 90, 120, 150, 180]
        
        for minutes in test_points:
            remaining = self.calculator._calculate_insulin_action(
                original_units, minutes, duration, 'rapid'
            )
            
            if minutes == 0:
                assert remaining == original_units
            elif minutes >= duration:
                assert remaining == 0.0
            else:
                assert 0 < remaining < original_units
    
    def test_long_acting_insulin(self):
        """Test long-acting insulin absorption"""
        original_units = 10.0
        duration = 720  # 12 hours
        
        # Should absorb more slowly than rapid
        remaining_2h = self.calculator._calculate_insulin_action(
            original_units, 120, duration, 'long_acting'
        )
        
        # After 2 hours, should still have most insulin remaining
        assert remaining_2h > original_units * 0.7

if __name__ == "__main__":
    pytest.main([__file__])