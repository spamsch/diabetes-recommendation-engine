import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import datetime
from ..database import GlucoseReading
from ..config import Settings

logger = logging.getLogger(__name__)

class RecommendationBase(ABC):
    """Base class for all recommendation engines"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = self.__class__.__name__
    
    @abstractmethod
    def analyze(self, readings: List[GlucoseReading], 
                trend_analysis: Dict, prediction: Dict,
                iob_cob_data: Optional[Dict] = None) -> Optional[Dict]:
        """Analyze readings and return recommendation if applicable"""
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """Return priority level (1=highest, 10=lowest)"""
        pass
    
    def is_enabled(self) -> bool:
        """Check if this recommendation type is enabled"""
        return True

class InsulinRecommendation(RecommendationBase):
    """Recommendation for insulin administration"""
    
    def get_priority(self) -> int:
        return 2  # High priority but not critical
    
    def is_enabled(self) -> bool:
        return self.settings.enable_insulin_recommendations
    
    def analyze(self, readings: List[GlucoseReading], 
                trend_analysis: Dict, prediction: Dict,
                iob_cob_data: Optional[Dict] = None) -> Optional[Dict]:
        
        if not readings or not self.is_enabled():
            return None
        
        current_reading = readings[0]  # Most recent
        current_value = current_reading.value
        
        # Check IOB - don't recommend if high IOB
        current_iob = 0.0
        if iob_cob_data and iob_cob_data.get('iob', {}).get('total_iob', 0) > 0:
            current_iob = iob_cob_data['iob']['total_iob']
            
            # High IOB threshold check
            if current_iob > self.settings.iob_threshold_high:
                return None  # Too much active insulin already
        
        # Don't recommend insulin if glucose is not elevated or trending down rapidly
        if current_value < self.settings.high_glucose_threshold:
            return None
        
        # Block insulin for rapidly falling glucose
        if trend_analysis.get('trend') in ['fast_down', 'very_fast_down']:
            return None
        
        # For slow downward trends, allow small insulin if glucose is very high
        trend = trend_analysis.get('trend')
        rate_of_change = trend_analysis.get('rate_of_change', 0)
        
        if trend == 'down':
            # Only allow insulin for slow down trends with very high glucose
            if not self._is_safe_slow_correction(current_value, rate_of_change, readings):
                return None
        
        # Check if values have been stable and elevated for several readings
        if not self._is_stable_elevated_pattern(readings):
            return None
        
        # Calculate recommended insulin units using target glucose
        target_glucose = self.settings.target_glucose
        excess_glucose = current_value - target_glucose
        
        # Adjust for IOB - reduce recommendation if there's active insulin
        iob_adjustment = current_iob * self.settings.insulin_effectiveness
        adjusted_excess = excess_glucose - iob_adjustment
        
        if adjusted_excess <= 0:
            return None  # IOB should handle current glucose level
        
        insulin_units = (adjusted_excess / self.settings.insulin_effectiveness) * self.settings.insulin_unit_ratio
        
        # For slow correction scenarios, reduce dose by 50% since glucose is already falling
        if trend_analysis.get('trend') == 'down':
            insulin_units *= 0.5
        
        # Safety limits
        insulin_units = max(0.1, min(2.0, insulin_units))  # Between 0.1 and 2.0 units
        
        message = self._generate_insulin_message(current_value, insulin_units, trend_analysis, current_iob)
        
        # Determine safety notes based on scenario
        is_slow_correction = trend_analysis.get('trend') == 'down'
        
        if is_slow_correction:
            safety_notes = [
                "This is not professional advice - use your own judgment",
                "SLOW CORRECTION: Monitor glucose every 30-60 minutes after insulin",
                "Glucose is falling slowly - small dose to accelerate correction safely",
                "Stop if glucose drops faster than -1.5 mg/dL/min after insulin"
            ]
        else:
            safety_notes = [
                "This is not professional advice - use your own judgment", 
                "Monitor glucose closely after insulin administration",
                "Consider current IOB in decision making"
            ]
        
        return {
            'type': 'insulin',
            'priority': self.get_priority(),
            'message': message,
            'parameters': {
                'recommended_units': round(insulin_units, 1),
                'current_glucose': current_value,
                'target_glucose': target_glucose,
                'excess_glucose': round(excess_glucose, 1),
                'adjusted_excess': round(adjusted_excess, 1),
                'current_iob': round(current_iob, 1),
                'iob_adjustment': round(iob_adjustment, 1),
                'calculation_basis': f"Target: {target_glucose} mg/dL, IOB adjusted",
                'correction_type': 'slow_correction' if is_slow_correction else 'standard'
            },
            'safety_notes': safety_notes
        }
    
    def _is_stable_elevated_pattern(self, readings: List[GlucoseReading]) -> bool:
        """Check if glucose has been stable and elevated"""
        if len(readings) < 4:
            return False
        
        recent_values = [r.value for r in readings[:4]]
        avg_value = sum(recent_values) / len(recent_values)
        
        # Must be elevated
        if avg_value < self.settings.high_glucose_threshold:
            return False
        
        # Must be relatively stable (not varying too much)
        max_val = max(recent_values)
        min_val = min(recent_values)
        if (max_val - min_val) > 40:  # Too much variation
            return False
        
        # Check if glucose is consistently falling (unsafe for insulin)
        # readings[0] is most recent, readings[-1] is oldest in the recent_values
        # If most recent < oldest - 10, it's falling significantly
        if recent_values[0] < recent_values[-1] - 10:  # Falling >10 mg/dL over 4 readings
            return False
        
        return True
    
    def _is_safe_slow_correction(self, current_value: float, rate_of_change: float, 
                               readings: List[GlucoseReading]) -> bool:
        """Check if it's safe to give insulin during slow downward trend"""
        
        # Safety threshold 1: Glucose must be significantly high for safety margin
        high_safety_threshold = 220.0  # Much higher than normal high threshold (180)
        if current_value < high_safety_threshold:
            return False
        
        # Safety threshold 2: Rate must be slow enough that insulin won't cause rapid drop
        # Allow rates between -0.1 and -0.8 mg/dL/min (slow but not too slow)
        min_rate = -0.8  # Slower than this is too slow (might not need insulin)
        max_rate = -0.1  # Faster than this is too fast (approaching dangerous territory)
        
        if rate_of_change > max_rate or rate_of_change < min_rate:
            return False
        
        # Safety threshold 3: Pattern must be sustained (consistent slow decline)
        if len(readings) < 4:
            return False
            
        recent_values = [r.value for r in readings[:4]]
        
        # Check that all recent values are high (sustained high glucose)
        if min(recent_values) < high_safety_threshold:
            return False
            
        # Check that trend is consistently downward but not too steep
        # Values should be decreasing but slowly
        for i in range(len(recent_values) - 1):
            if recent_values[i] >= recent_values[i + 1]:  # Not consistently down
                return False
        
        # Check that the total drop over 4 readings is reasonable for slow correction
        total_drop = recent_values[-1] - recent_values[0]  # Oldest - newest
        max_reasonable_drop = 20.0  # Max 20 mg/dL drop over ~15 minutes for "slow"
        
        if abs(total_drop) > max_reasonable_drop:
            return False
            
        return True
    
    def _generate_insulin_message(self, current_value: float, 
                                 insulin_units: float, trend_analysis: Dict,
                                 current_iob: float = 0.0) -> str:
        trend = trend_analysis.get('trend', 'no_change')
        rate_of_change = trend_analysis.get('rate_of_change', 0)
        
        base_msg = f"Consider {insulin_units:.1f} units of insulin. "
        base_msg += f"Current glucose: {current_value:.0f} mg/dL"
        
        if trend == 'up' or trend == 'fast_up':
            base_msg += " (rising)"
        elif trend == 'no_change':
            base_msg += " (stable)"
        elif trend == 'down':
            # Special message for slow correction scenario
            base_msg += f" (slowly falling at {abs(rate_of_change):.1f} mg/dL/min - safe to accelerate correction)"
        
        if current_iob > 0.1:
            base_msg += f", IOB: {current_iob:.1f}u"
        
        return base_msg

class CarbRecommendation(RecommendationBase):
    """Recommendation for carbohydrate intake"""
    
    def get_priority(self) -> int:
        return 1  # Highest priority - safety critical
    
    def is_enabled(self) -> bool:
        return self.settings.enable_carb_recommendations
    
    def analyze(self, readings: List[GlucoseReading], 
                trend_analysis: Dict, prediction: Dict,
                iob_cob_data: Optional[Dict] = None) -> Optional[Dict]:
        
        if not readings or not self.is_enabled():
            return None
        
        current_reading = readings[0]
        current_value = current_reading.value
        
        # Only recommend carbs for low or rapidly falling glucose
        needs_carbs = False
        urgency = 'low'
        
        if current_value <= self.settings.critical_low_threshold:
            needs_carbs = True
            urgency = 'critical'
        elif current_value <= self.settings.low_glucose_threshold:
            needs_carbs = True
            urgency = 'high'
        elif (current_value <= self.settings.low_glucose_threshold * 1.2 and 
              trend_analysis.get('trend') in ['fast_down', 'very_fast_down']):
            needs_carbs = True
            urgency = 'medium'
        
        if not needs_carbs:
            return None
        
        # Check if prediction also indicates low values
        predicted_value = prediction.get('predicted_value')
        if predicted_value and predicted_value <= self.settings.low_glucose_threshold:
            urgency = 'high' if urgency != 'critical' else urgency
        
        # Calculate recommended carbs
        glucose_deficit = self.settings.low_glucose_threshold - current_value
        if glucose_deficit < 0:
            glucose_deficit = 0
        
        # Base carbs needed
        carb_grams = max(15, glucose_deficit / self.settings.carb_effectiveness * 15)
        carb_grams = min(carb_grams, 30)  # Safety limit
        
        message = self._generate_carb_message(current_value, carb_grams, urgency, trend_analysis)
        
        return {
            'type': 'carbohydrate',
            'priority': self.get_priority(),
            'urgency': urgency,
            'message': message,
            'parameters': {
                'recommended_carbs': round(carb_grams, 0),
                'current_glucose': current_value,
                'glucose_deficit': round(glucose_deficit, 1),
                'suggested_foods': self._get_suggested_foods(carb_grams)
            },
            'safety_notes': [
                "Act quickly for low glucose",
                "Re-check glucose in 15 minutes",
                "Call emergency services if severe symptoms"
            ]
        }
    
    def _generate_carb_message(self, current_value: float, carb_grams: float, 
                              urgency: str, trend_analysis: Dict) -> str:
        trend = trend_analysis.get('trend', 'no_change')
        
        if urgency == 'critical':
            msg = f"URGENT: Take {carb_grams:.0f}g fast-acting carbs NOW! "
        elif urgency == 'high':
            msg = f"LOW GLUCOSE: Take {carb_grams:.0f}g carbs immediately. "
        else:
            msg = f"Consider {carb_grams:.0f}g carbs. "
        
        msg += f"Current: {current_value:.0f} mg/dL"
        
        if trend in ['fast_down', 'very_fast_down']:
            msg += " (falling rapidly)"
        elif trend == 'down':
            msg += " (falling)"
        
        return msg
    
    def _get_suggested_foods(self, carb_grams: float) -> List[str]:
        """Suggest appropriate foods for the carb amount"""
        if carb_grams <= 15:
            return ["4 glucose tablets", "1/2 cup fruit juice", "1 tbsp honey"]
        elif carb_grams <= 20:
            return ["5-6 glucose tablets", "2/3 cup fruit juice", "1 tube glucose gel"]
        else:
            return ["8 glucose tablets", "1 cup fruit juice", "2 tubes glucose gel", "1 banana + crackers"]

class MonitoringRecommendation(RecommendationBase):
    """Recommendation for increased monitoring"""
    
    def get_priority(self) -> int:
        return 5  # Medium priority
    
    def analyze(self, readings: List[GlucoseReading], 
                trend_analysis: Dict, prediction: Dict,
                iob_cob_data: Optional[Dict] = None) -> Optional[Dict]:
        
        if not readings:
            return None
        
        current_reading = readings[0]
        current_value = current_reading.value
        
        # Recommend increased monitoring for various conditions
        monitoring_reasons = []
        frequency_minutes = 60  # Default check every hour
        
        # Rapid changes
        if trend_analysis.get('trend') in ['very_fast_up', 'very_fast_down', 'fast_up', 'fast_down']:
            monitoring_reasons.append("rapid glucose changes detected")
            frequency_minutes = 15
        
        # Approaching thresholds
        if (self.settings.low_glucose_threshold * 1.1 >= current_value >= 
            self.settings.low_glucose_threshold * 0.9):
            monitoring_reasons.append("approaching low threshold")
            frequency_minutes = 30
        
        if (self.settings.high_glucose_threshold * 1.1 >= current_value >= 
            self.settings.high_glucose_threshold * 0.9):
            monitoring_reasons.append("approaching high threshold")
            frequency_minutes = 30
        
        # High prediction uncertainty
        if prediction.get('confidence') == 'low' and len(readings) >= 3:
            monitoring_reasons.append("unpredictable glucose pattern")
            frequency_minutes = 45
        
        # Nighttime considerations
        current_hour = datetime.now().hour
        if 22 <= current_hour or current_hour <= 6:  # 10 PM to 6 AM
            if current_value < 100 or current_value > 200:
                monitoring_reasons.append("nighttime out-of-range values")
                frequency_minutes = 30
        
        if not monitoring_reasons:
            return None
        
        message = self._generate_monitoring_message(monitoring_reasons, frequency_minutes)
        
        return {
            'type': 'monitoring',
            'priority': self.get_priority(),
            'message': message,
            'parameters': {
                'check_frequency_minutes': frequency_minutes,
                'reasons': monitoring_reasons,
                'next_check_time': datetime.now().replace(
                    minute=(datetime.now().minute + frequency_minutes) % 60
                ).strftime('%H:%M')
            }
        }
    
    def _generate_monitoring_message(self, reasons: List[str], 
                                   frequency_minutes: int) -> str:
        reasons_text = ", ".join(reasons)
        
        if frequency_minutes <= 15:
            urgency = "frequently (every 15 min)"
        elif frequency_minutes <= 30:
            urgency = "closely (every 30 min)"
        else:
            urgency = f"every {frequency_minutes} minutes"
        
        return f"Monitor glucose {urgency} due to: {reasons_text}."

class IOBStatusRecommendation(RecommendationBase):
    """Recommendation to check IOB (Insulin on Board) status for better prediction accuracy"""
    
    def get_priority(self) -> int:
        return 4  # Medium priority - helps with accuracy but not urgent
    
    def analyze(self, readings: List[GlucoseReading], 
                trend_analysis: Dict, prediction: Dict,
                iob_cob_data: Optional[Dict] = None) -> Optional[Dict]:
        
        if not readings:
            return None
        
        current_reading = readings[0]
        current_value = current_reading.value
        predicted_value = prediction.get('predicted_value')
        
        # Check if we have IOB data
        has_iob_data = iob_cob_data and 'iob' in iob_cob_data
        current_iob = iob_cob_data['iob']['total_iob'] if has_iob_data else 0.0
        
        recommend_iob_check = False
        urgency = 'low'
        reasons = []
        
        # Scenario 1: Approaching low - need accurate IOB for prediction
        is_approaching_low = (current_value <= self.settings.low_glucose_threshold * 1.2 or  # Within 20% of low threshold
                            (predicted_value and predicted_value <= self.settings.low_glucose_threshold))
        
        # Scenario 2: Going high fast - need IOB to understand if insulin is working
        is_going_high_fast = (trend_analysis.get('trend') in ['fast_up', 'very_fast_up'] or
                            trend_analysis.get('rate_of_change', 0) > 2.0)
        
        if not has_iob_data or current_iob == 0.0:
            if is_approaching_low:
                recommend_iob_check = True
                urgency = 'high'
                reasons.append("approaching low glucose - need accurate IOB for predictions")
            elif is_going_high_fast:
                recommend_iob_check = True
                urgency = 'medium'
                reasons.append("glucose rising fast - check if insulin was taken")
            elif current_value > self.settings.high_glucose_threshold:
                recommend_iob_check = True
                urgency = 'medium' 
                reasons.append("high glucose without IOB data")
        
        # Scenario 3: Have IOB data but need verification in critical situations
        else:  # We have IOB data
            if is_approaching_low and current_iob > 0.3:
                recommend_iob_check = True
                urgency = 'high' 
                reasons.append(f"approaching low with {current_iob:.1f}u IOB - verify accuracy for safe predictions")
            elif is_going_high_fast and current_iob < 0.2:
                recommend_iob_check = True
                urgency = 'medium'
                reasons.append("glucose rising fast with low IOB - confirm no recent insulin")
            elif current_iob > 0.6:  # High IOB
                recommend_iob_check = True
                urgency = 'medium'
                reasons.append(f"high IOB ({current_iob:.1f}u) significantly affecting predictions")
                
                # If high IOB and glucose isn't dropping as expected
                if (current_iob > 1.0 and 
                    trend_analysis.get('trend') not in ['down', 'fast_down', 'very_fast_down']):
                    urgency = 'high'
                    reasons.append("high IOB but glucose not falling as expected")
        
            # Also check for potentially stale IOB override data
            elif has_iob_data and iob_cob_data['iob'].get('is_override') and current_iob > 0.2:
                recommend_iob_check = True
                urgency = 'low'
                reasons.append("IOB override may need updating")
        
        if not recommend_iob_check:
            return None
        
        message = self._generate_iob_message(current_iob, reasons, urgency)
        
        return {
            'type': 'iob_status',
            'priority': self.get_priority(),
            'urgency': urgency,
            'message': message,
            'parameters': {
                'current_iob': current_iob,
                'reasons': reasons,
                'suggested_action': 'Check pump/Omnipod for current IOB' if not has_iob_data else 'Update IOB reading',
                'expected_effect': self._calculate_expected_glucose_effect(current_iob) if current_iob > 0 else None
            },
            'safety_notes': [
                "Accurate IOB improves prediction accuracy",
                "Check pump/Omnipod display for current active insulin",
                "Update using /iob command or plain number in Telegram"
            ]
        }
    
    def _generate_iob_message(self, current_iob: float, reasons: List[str], urgency: str) -> str:
        """Generate IOB status check message"""
        reasons_text = ", ".join(reasons)
        
        if urgency == 'high':
            msg = f"IMPORTANT: Check current IOB status - {reasons_text}. "
        elif urgency == 'medium':
            msg = f"Check current IOB (active insulin) - {reasons_text}. "
        else:
            msg = f"Consider checking IOB status - {reasons_text}. "
        
        if current_iob > 0:
            msg += f"Current IOB: {current_iob:.1f} units. "
        
        msg += "Check pump/Omnipod for accurate reading."
        return msg
    
    def _calculate_expected_glucose_effect(self, iob: float) -> Dict:
        """Calculate expected glucose effect from IOB"""
        if iob <= 0:
            return None
        
        expected_drop = iob * self.settings.insulin_effectiveness
        return {
            'expected_glucose_drop': round(expected_drop, 1),
            'timeframe_minutes': 60,  # Approximate time for significant effect
            'note': f'{iob:.1f}u IOB should lower glucose by ~{expected_drop:.0f} mg/dL'
        }

class RecommendationEngine:
    """Main recommendation engine that coordinates all recommendation types"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.recommenders = [
            CarbRecommendation(settings),
            InsulinRecommendation(settings),
            MonitoringRecommendation(settings),
            IOBStatusRecommendation(settings)
        ]
    
    def get_recommendations(self, readings: List[GlucoseReading], 
                          trend_analysis: Dict, prediction: Dict,
                          iob_cob_data: Optional[Dict] = None) -> List[Dict]:
        """Get all applicable recommendations"""
        recommendations = []
        
        for recommender in self.recommenders:
            try:
                rec = recommender.analyze(readings, trend_analysis, prediction, iob_cob_data)
                if rec:
                    rec['timestamp'] = datetime.now()
                    rec['recommender'] = recommender.name
                    recommendations.append(rec)
            except Exception as e:
                logger.error(f"Error in {recommender.name}: {e}")
        
        # Sort by priority (lower number = higher priority)
        recommendations.sort(key=lambda x: x['priority'])
        
        return recommendations
    
    def get_critical_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """Filter for only critical recommendations"""
        return [r for r in recommendations if r.get('urgency') == 'critical' or r['priority'] <= 2]