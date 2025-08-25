import logging
import numpy as np
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from scipy import stats
from ..database import GlucoseReading
from ..config import Settings

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def analyze_trend(self, readings: List[GlucoseReading]) -> dict:
        """Analyze glucose trend from recent readings"""
        if len(readings) < 2:
            return {
                'trend': 'no_change',
                'rate_of_change': 0.0,
                'trend_strength': 'weak',
                'direction': 'stable',
                'variance': 0.0,
                'is_stable': True,
                'analysis_points': len(readings)
            }
        
        # Sort readings by timestamp (most recent first)
        sorted_readings = sorted(readings, key=lambda r: r.timestamp, reverse=True)
        
        # Use only the most recent readings for trend calculation
        analysis_count = min(
            len(sorted_readings), 
            self.settings.trend_calculation_points
        )
        recent_readings = sorted_readings[:analysis_count]
        
        values = [r.value for r in recent_readings]
        timestamps = [r.timestamp for r in recent_readings]
        
        # Calculate rate of change (mg/dL per minute)
        rate_of_change = self._calculate_rate_of_change(values, timestamps)
        
        # Determine trend direction and strength
        trend = self._classify_trend(rate_of_change)
        trend_strength = self._calculate_trend_strength(values)
        direction = self._get_direction(rate_of_change)
        
        # Calculate variance and stability
        variance = np.var(values) if len(values) > 1 else 0.0
        is_stable = variance < self.settings.stable_variance_threshold
        
        return {
            'trend': trend,
            'rate_of_change': round(rate_of_change, 2),
            'trend_strength': trend_strength,
            'direction': direction,
            'variance': round(variance, 2),
            'is_stable': is_stable,
            'analysis_points': len(recent_readings),
            'current_value': recent_readings[0].value if recent_readings else None,
            'previous_value': recent_readings[1].value if len(recent_readings) > 1 else None
        }
    
    def _calculate_rate_of_change(self, values: List[float], 
                                 timestamps: List[datetime]) -> float:
        """Calculate rate of change in mg/dL per minute"""
        if len(values) < 2:
            return 0.0
        
        # Convert timestamps to minutes from the earliest reading
        time_minutes = []
        earliest = min(timestamps)
        for ts in timestamps:
            time_minutes.append((ts - earliest).total_seconds() / 60.0)
        
        # Check if all timestamps are identical
        if all(t == time_minutes[0] for t in time_minutes):
            logger.debug("All timestamps are identical, cannot calculate rate of change")
            return 0.0
        
        # Reverse to have chronological order for regression
        time_minutes.reverse()
        values_chrono = values[::-1]
        
        # Calculate linear regression to get rate of change
        if len(values_chrono) >= 2:
            try:
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    time_minutes, values_chrono
                )
                return slope
            except Exception as e:
                logger.warning(f"Error calculating regression: {e}")
                # Fallback to simple difference
                time_diff = (timestamps[0] - timestamps[1]).total_seconds() / 60.0
                if time_diff > 0:
                    return (values[0] - values[1]) / time_diff
        
        return 0.0
    
    def _classify_trend(self, rate_of_change: float) -> str:
        """Classify trend based on rate of change"""
        abs_rate = abs(rate_of_change)
        
        if rate_of_change > 0:
            if abs_rate >= self.settings.trend_very_fast_up_threshold:
                return "very_fast_up"
            elif abs_rate >= self.settings.trend_fast_up_threshold:
                return "fast_up"
            elif abs_rate >= self.settings.trend_up_threshold:
                return "up"
        elif rate_of_change < 0:
            if abs_rate >= self.settings.trend_very_fast_down_threshold:
                return "very_fast_down"
            elif abs_rate >= self.settings.trend_fast_down_threshold:
                return "fast_down"
            elif abs_rate >= self.settings.trend_down_threshold:
                return "down"
        
        return "no_change"
    
    def _calculate_trend_strength(self, values: List[float]) -> str:
        """Calculate the strength of the trend"""
        if len(values) < 3:
            return "weak"
        
        # Calculate correlation with time sequence
        time_sequence = list(range(len(values)))
        try:
            correlation, _ = stats.pearsonr(time_sequence, values)
            abs_correlation = abs(correlation)
            
            if abs_correlation >= 0.8:
                return "very_strong"
            elif abs_correlation >= 0.6:
                return "strong"
            elif abs_correlation >= 0.4:
                return "moderate"
            else:
                return "weak"
        except Exception:
            return "weak"
    
    def _get_direction(self, rate_of_change: float) -> str:
        """Get simplified direction"""
        if rate_of_change > 1.0:
            return "rising"
        elif rate_of_change < -1.0:
            return "falling"
        else:
            return "stable"
    
    def detect_patterns(self, readings: List[GlucoseReading]) -> dict:
        """Detect specific patterns in glucose readings"""
        if len(readings) < 4:
            return {'patterns': []}
        
        patterns = []
        values = [r.value for r in sorted(readings, key=lambda r: r.timestamp)]
        
        # Detect rapid changes
        patterns.extend(self._detect_rapid_changes(values))
        
        # Detect approaching thresholds
        patterns.extend(self._detect_threshold_approaches(values))
        
        # Detect stability patterns
        patterns.extend(self._detect_stability_patterns(values))
        
        return {
            'patterns': patterns,
            'pattern_count': len(patterns)
        }
    
    def _detect_rapid_changes(self, values: List[float]) -> List[dict]:
        """Detect rapid changes in glucose values"""
        patterns = []
        
        for i in range(1, len(values)):
            change = values[i] - values[i-1]
            
            if change >= self.settings.rapid_rise_threshold:
                patterns.append({
                    'type': 'rapid_rise',
                    'severity': 'high' if change >= self.settings.rapid_rise_threshold * 1.5 else 'medium',
                    'change_amount': round(change, 1),
                    'description': f"Rapid rise of {change:.1f} mg/dL detected"
                })
            
            elif change <= self.settings.rapid_fall_threshold:
                patterns.append({
                    'type': 'rapid_fall',
                    'severity': 'high' if change <= self.settings.rapid_fall_threshold * 1.5 else 'medium',
                    'change_amount': round(change, 1),
                    'description': f"Rapid fall of {abs(change):.1f} mg/dL detected"
                })
        
        return patterns
    
    def _detect_threshold_approaches(self, values: List[float]) -> List[dict]:
        """Detect when approaching critical thresholds"""
        patterns = []
        current_value = values[-1]
        
        # Check approaching low threshold
        if (current_value <= self.settings.low_glucose_threshold * 1.2 and 
            current_value > self.settings.low_glucose_threshold):
            patterns.append({
                'type': 'approaching_low',
                'severity': 'medium',
                'current_value': current_value,
                'threshold': self.settings.low_glucose_threshold,
                'description': f"Approaching low threshold ({self.settings.low_glucose_threshold} mg/dL)"
            })
        
        # Check critical low
        elif current_value <= self.settings.critical_low_threshold:
            patterns.append({
                'type': 'critical_low',
                'severity': 'critical',
                'current_value': current_value,
                'threshold': self.settings.critical_low_threshold,
                'description': f"Critical low glucose level detected"
            })
        
        # Check approaching high threshold
        elif (current_value >= self.settings.high_glucose_threshold * 0.9 and 
              current_value < self.settings.high_glucose_threshold):
            patterns.append({
                'type': 'approaching_high',
                'severity': 'medium',
                'current_value': current_value,
                'threshold': self.settings.high_glucose_threshold,
                'description': f"Approaching high threshold ({self.settings.high_glucose_threshold} mg/dL)"
            })
        
        # Check critical high
        elif current_value >= self.settings.critical_high_threshold:
            patterns.append({
                'type': 'critical_high',
                'severity': 'critical',
                'current_value': current_value,
                'threshold': self.settings.critical_high_threshold,
                'description': f"Critical high glucose level detected"
            })
        
        return patterns
    
    def _detect_stability_patterns(self, values: List[float]) -> List[dict]:
        """Detect stability patterns"""
        patterns = []
        
        if len(values) >= 4:
            recent_variance = np.var(values[-4:])
            
            if recent_variance < self.settings.stable_variance_threshold:
                avg_value = np.mean(values[-4:])
                patterns.append({
                    'type': 'stable_pattern',
                    'severity': 'low',
                    'variance': round(recent_variance, 2),
                    'average_value': round(avg_value, 1),
                    'description': f"Stable glucose pattern detected (avg: {avg_value:.1f} mg/dL)"
                })
        
        return patterns