import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from ..database import InsulinEntry, CarbEntry
from ..config import Settings

logger = logging.getLogger(__name__)

class IOBCalculator:
    """Calculates Insulin on Board (IOB) and Carbs on Board (COB)"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def calculate_iob(self, insulin_entries: List[InsulinEntry], 
                     current_time: datetime, iob_override: float = None) -> Dict:
        """Calculate total insulin on board and detailed breakdown"""
        
        # If IOB override is provided (e.g., from Omnipod), use that instead
        if iob_override is not None:
            return {
                'total_iob': round(iob_override, 2),
                'breakdown': [{
                    'timestamp': current_time,
                    'original_units': iob_override,
                    'remaining_units': iob_override,
                    'insulin_type': 'override',
                    'minutes_ago': 0,
                    'notes': 'Manual/Omnipod override'
                }],
                'calculation_time': current_time,
                'entries_count': 1,
                'is_override': True
            }
        
        total_iob = 0.0
        iob_breakdown = []
        
        for entry in insulin_entries:
            time_since_dose = (current_time - entry.timestamp).total_seconds() / 60.0  # minutes
            
            if time_since_dose >= entry.duration_minutes:
                # Insulin has been fully absorbed
                remaining_iob = 0.0
            else:
                # Calculate remaining IOB based on insulin action curve
                remaining_iob = self._calculate_insulin_action(
                    entry.units, 
                    time_since_dose, 
                    entry.duration_minutes,
                    entry.insulin_type
                )
            
            if remaining_iob > 0.01:  # Only include significant amounts
                iob_breakdown.append({
                    'timestamp': entry.timestamp,
                    'original_units': entry.units,
                    'remaining_units': round(remaining_iob, 2),
                    'insulin_type': entry.insulin_type,
                    'minutes_ago': round(time_since_dose, 0),
                    'notes': entry.notes
                })
                
                total_iob += remaining_iob
        
        return {
            'total_iob': round(total_iob, 2),
            'breakdown': iob_breakdown,
            'calculation_time': current_time,
            'entries_count': len(iob_breakdown),
            'is_override': False
        }
    
    def calculate_cob(self, carb_entries: List[CarbEntry], 
                     current_time: datetime) -> Dict:
        """Calculate carbohydrates on board"""
        total_cob = 0.0
        cob_breakdown = []
        
        for entry in carb_entries:
            time_since_carbs = (current_time - entry.timestamp).total_seconds() / 60.0  # minutes
            
            if time_since_carbs >= entry.absorption_minutes:
                # Carbs have been fully absorbed
                remaining_cob = 0.0
            else:
                # Calculate remaining COB based on absorption curve
                remaining_cob = self._calculate_carb_absorption(
                    entry.grams,
                    time_since_carbs,
                    entry.absorption_minutes,
                    entry.carb_type
                )
            
            if remaining_cob > 0.5:  # Only include significant amounts
                cob_breakdown.append({
                    'timestamp': entry.timestamp,
                    'original_grams': entry.grams,
                    'remaining_grams': round(remaining_cob, 1),
                    'carb_type': entry.carb_type or 'mixed',
                    'minutes_ago': round(time_since_carbs, 0),
                    'notes': entry.notes
                })
                
                total_cob += remaining_cob
        
        return {
            'total_cob': round(total_cob, 1),
            'breakdown': cob_breakdown,
            'calculation_time': current_time,
            'entries_count': len(cob_breakdown)
        }
    
    def _calculate_insulin_action(self, original_units: float, 
                                 minutes_elapsed: float,
                                 duration_minutes: int,
                                 insulin_type: str) -> float:
        """Calculate remaining insulin based on action curve"""
        
        if minutes_elapsed >= duration_minutes:
            return 0.0
        
        # Fraction of time elapsed
        time_fraction = minutes_elapsed / duration_minutes
        
        if insulin_type == 'rapid':
            # Rapid-acting insulin: exponential decay with peak at ~60 minutes
            # Using Walsh/Roberts exponential insulin action curve
            if minutes_elapsed <= 0:
                return original_units
            
            # Peak action around 75 minutes, then exponential decay
            peak_time = 75.0  # minutes
            if minutes_elapsed <= peak_time:
                # Rising to peak
                action_fraction = (minutes_elapsed / peak_time) * 0.15  # 15% absorbed at peak
            else:
                # Exponential decay after peak
                decay_rate = 0.025  # Decay rate
                time_after_peak = minutes_elapsed - peak_time
                remaining_fraction = 1.0 - 0.15 - (0.85 * (1 - math.exp(-decay_rate * time_after_peak)))
                action_fraction = max(0, remaining_fraction)
            
            return original_units * (1 - min(action_fraction * (duration_minutes / 180), 1.0))
        
        elif insulin_type == 'long_acting':
            # Long-acting insulin: very slow, steady absorption
            # Linear absorption over much longer duration
            absorbed_fraction = time_fraction * 0.8  # 80% absorbed linearly
            return original_units * (1 - absorbed_fraction)
        
        else:  # intermediate or unknown
            # Simple linear absorption
            absorbed_fraction = time_fraction
            return original_units * (1 - absorbed_fraction)
    
    def _calculate_carb_absorption(self, original_grams: float,
                                  minutes_elapsed: float,
                                  absorption_minutes: int,
                                  carb_type: str) -> float:
        """Calculate remaining carbs based on absorption curve"""
        
        if minutes_elapsed >= absorption_minutes:
            return 0.0
        
        time_fraction = minutes_elapsed / absorption_minutes
        
        if carb_type == 'fast':
            # Fast carbs: quick absorption, mostly done in first half of duration
            # Exponential absorption curve
            absorbed_fraction = 1 - math.exp(-3.0 * time_fraction)
            
        elif carb_type == 'slow':
            # Slow carbs: linear absorption
            absorbed_fraction = time_fraction
            
        else:  # mixed or unknown
            # Mixed carbs: combination of fast and slow
            # 40% fast absorption, 60% slow
            fast_component = 0.4 * (1 - math.exp(-2.0 * time_fraction))
            slow_component = 0.6 * time_fraction
            absorbed_fraction = fast_component + slow_component
        
        return original_grams * (1 - absorbed_fraction)
    
    def estimate_glucose_impact(self, iob_data: Dict, cob_data: Dict,
                               current_glucose: float) -> Dict:
        """Estimate glucose impact from IOB and COB"""
        
        # Calculate IOB effect (lowering glucose)
        iob_effect = 0.0
        if iob_data['total_iob'] > 0:
            iob_effect = -(iob_data['total_iob'] * self.settings.insulin_effectiveness)
        
        # Calculate COB effect (raising glucose)
        cob_effect = 0.0
        # Define carb_ratio outside the if block to ensure it's always available
        carb_ratio = getattr(self.settings, 'carb_to_glucose_ratio', 3.5)
        if cob_data['total_cob'] > 0:
            # Estimate glucose rise: typically 3-4 mg/dL per gram of carb
            cob_effect = cob_data['total_cob'] * carb_ratio
        
        # Net effect and predicted glucose
        net_effect = iob_effect + cob_effect
        predicted_glucose = current_glucose + net_effect
        
        return {
            'iob_effect': round(iob_effect, 1),
            'cob_effect': round(cob_effect, 1),
            'net_effect': round(net_effect, 1),
            'predicted_glucose': round(predicted_glucose, 1),
            'current_glucose': current_glucose,
            'factors': {
                'active_insulin': iob_data['total_iob'],
                'active_carbs': cob_data['total_cob'],
                'insulin_effectiveness': self.settings.insulin_effectiveness,
                'carb_ratio': carb_ratio
            }
        }
    
    def get_iob_cob_summary(self, current_time: datetime,
                           insulin_entries: List[InsulinEntry],
                           carb_entries: List[CarbEntry],
                           current_glucose: float,
                           iob_override: float = None) -> Dict:
        """Get complete IOB/COB summary"""
        
        iob_data = self.calculate_iob(insulin_entries, current_time, iob_override)
        cob_data = self.calculate_cob(carb_entries, current_time)
        impact_estimate = self.estimate_glucose_impact(iob_data, cob_data, current_glucose)
        
        return {
            'iob': iob_data,
            'cob': cob_data,
            'impact': impact_estimate,
            'summary': {
                'has_active_insulin': iob_data['total_iob'] > 0.1,
                'has_active_carbs': cob_data['total_cob'] > 1.0,
                'net_glucose_trend': 'falling' if impact_estimate['net_effect'] < -10 else 
                                   'rising' if impact_estimate['net_effect'] > 10 else 'stable',
                'recommendation_adjustment': self._get_recommendation_adjustment(
                    iob_data, cob_data, impact_estimate
                )
            }
        }
    
    def _get_recommendation_adjustment(self, iob_data: Dict, cob_data: Dict, 
                                     impact_estimate: Dict) -> str:
        """Get recommendation for how IOB/COB should adjust treatment decisions"""
        
        iob = iob_data['total_iob']
        cob = cob_data['total_cob']
        net_effect = impact_estimate['net_effect']
        
        if iob > 2.0:
            return "High IOB - avoid additional insulin, monitor closely"
        elif iob > 1.0 and net_effect < -20:
            return "Significant IOB - reduce insulin recommendations"
        elif cob > 30.0:
            return "High COB - glucose may rise, consider early intervention"
        elif cob > 15.0 and net_effect > 20:
            return "Moderate COB - expect glucose rise"
        elif iob > 0.5 and cob < 5.0:
            return "Active insulin with minimal carbs - monitor for lows"
        else:
            return "Normal IOB/COB levels"