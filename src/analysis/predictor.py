import logging
import numpy as np
from typing import List, Dict, Optional
from datetime import timedelta
from scipy import stats
from ..database import GlucoseReading
from ..config import Settings

logger = logging.getLogger(__name__)


class GlucosePredictor:
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def predict_future_value(self, readings: List[GlucoseReading]) -> Dict:
        """Predict glucose value at specified time in the future"""
        if len(readings) < 3:
            return {
                'predicted_value': None,
                'confidence': 'low',
                'prediction_time': None,
                'method': 'insufficient_data',
                'warning': 'Need at least 3 readings for prediction'
            }
        
        # Sort readings chronologically (oldest first)
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        
        # Use same time window as trend analyzer for consistency
        # Limit to most recent TREND_CALCULATION_POINTS readings
        analysis_count = min(
            len(sorted_readings),
            self.settings.trend_calculation_points
        )
        # Take most recent readings
        recent_readings = sorted_readings[-analysis_count:]
        
        # Try multiple prediction methods and select the best
        predictions = []
        
        # Method 1: Linear extrapolation
        linear_pred = self._linear_extrapolation(recent_readings)
        if linear_pred:
            predictions.append(linear_pred)
        
        # Method 2: Polynomial fitting (if enough data)
        if len(recent_readings) >= 5:
            poly_pred = self._polynomial_prediction(recent_readings)
            if poly_pred:
                predictions.append(poly_pred)
        
        # Method 3: Exponential smoothing
        exp_pred = self._exponential_smoothing_prediction(recent_readings)
        if exp_pred:
            predictions.append(exp_pred)
        
        # Select best prediction based on confidence and reasonableness
        best_prediction = self._select_best_prediction(predictions, recent_readings)
        
        return best_prediction
    
    def _linear_extrapolation(
            self, readings: List[GlucoseReading]
    ) -> Optional[Dict]:
        """Predict using linear extrapolation"""
        try:
            values = [r.value for r in readings]
            timestamps = [r.timestamp for r in readings]
            
            # Convert timestamps to minutes from most recent reading
            reference_time = timestamps[-1]
            time_minutes = [
                (ts - reference_time).total_seconds() / 60.0
                for ts in timestamps
            ]
            
            # Check if all timestamps are identical
            if all(t == time_minutes[0] for t in time_minutes):
                logger.debug(
                    "All timestamps identical, using current value as prediction"
                )
                current_time = timestamps[-1]
                future_time = current_time + timedelta(
                    minutes=self.settings.prediction_minutes_ahead
                )
                return {
                    'predicted_value': round(values[-1], 1),
                    'confidence': 'high',
                    'prediction_time': future_time,
                    'method': 'stable_value',
                    'r_squared': 1.0,
                    'slope': 0.0,
                    'std_error': 0.0
                }
            
            # Fit linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(time_minutes, values)
            
            # Predict future value
            current_time = timestamps[-1]
            future_time = current_time + timedelta(minutes=self.settings.prediction_minutes_ahead)
            future_time_minutes = (future_time - reference_time).total_seconds() / 60.0
            
            predicted_value = slope * future_time_minutes + intercept
            
            # Calculate confidence based on R-squared and standard error
            r_squared = r_value ** 2
            confidence = self._calculate_confidence(r_squared, std_err, len(readings))
            
            return {
                'predicted_value': round(predicted_value, 1),
                'confidence': confidence,
                'prediction_time': future_time,
                'method': 'linear_extrapolation',
                'r_squared': round(r_squared, 3),
                'slope': round(slope, 2),
                'std_error': round(std_err, 2)
            }
            
        except Exception as e:
            logger.warning(f"Linear extrapolation failed: {e}")
            return None
    
    def _polynomial_prediction(self, readings: List[GlucoseReading]) -> Optional[Dict]:
        """Predict using polynomial fitting"""
        try:
            values = [r.value for r in readings]
            timestamps = [r.timestamp for r in readings]
            
            # Convert timestamps to minutes from most recent reading
            reference_time = timestamps[-1]  # Use most recent reading as reference
            time_minutes = np.array([(ts - reference_time).total_seconds() / 60.0 for ts in timestamps])
            values_array = np.array(values)
            
            # Check if all timestamps are identical
            if np.all(time_minutes == time_minutes[0]):
                logger.debug("All timestamps are identical, cannot fit polynomial")
                return None
            
            # Check if we have enough unique time points
            unique_times = np.unique(time_minutes)
            if len(unique_times) < 3:
                logger.debug("Not enough unique time points for polynomial fitting")
                return None
            
            # Fit quadratic polynomial
            coeffs = np.polyfit(time_minutes, values_array, deg=2)
            poly = np.poly1d(coeffs)
            
            # Calculate R-squared for polynomial fit
            y_pred_train = poly(time_minutes)
            ss_res = np.sum((values_array - y_pred_train) ** 2)
            ss_tot = np.sum((values_array - np.mean(values_array)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Predict future value
            current_time = timestamps[-1]
            future_time = current_time + timedelta(minutes=self.settings.prediction_minutes_ahead)
            future_time_minutes = (future_time - reference_time).total_seconds() / 60.0
            
            predicted_value = poly(future_time_minutes)
            
            # Calculate standard error
            residuals = values_array - y_pred_train
            std_err = np.sqrt(np.sum(residuals**2) / (len(residuals) - 3))  # 3 parameters
            
            confidence = self._calculate_confidence(r_squared, std_err, len(readings))
            
            return {
                'predicted_value': round(predicted_value, 1),
                'confidence': confidence,
                'prediction_time': future_time,
                'method': 'polynomial_fit',
                'r_squared': round(r_squared, 3),
                'coefficients': [round(c, 4) for c in coeffs],
                'std_error': round(std_err, 2)
            }
            
        except Exception as e:
            logger.warning(f"Polynomial prediction failed: {e}")
            return None
    
    def _exponential_smoothing_prediction(self, readings: List[GlucoseReading]) -> Optional[Dict]:
        """Predict using exponential smoothing"""
        try:
            values = [r.value for r in readings]
            
            # Simple exponential smoothing
            alpha = 0.3  # Smoothing parameter
            smoothed_values = []
            
            # Initialize with first value
            smoothed_values.append(values[0])
            
            # Apply exponential smoothing
            for i in range(1, len(values)):
                smoothed = alpha * values[i] + (1 - alpha) * smoothed_values[i-1]
                smoothed_values.append(smoothed)
            
            # Predict next value
            predicted_value = smoothed_values[-1]
            
            # Calculate trend component
            if len(smoothed_values) >= 2:
                trend = smoothed_values[-1] - smoothed_values[-2]
                # Apply trend to prediction
                steps_ahead = self.settings.prediction_minutes_ahead / 5  # Assuming 5-minute intervals
                predicted_value += trend * steps_ahead
            
            # Calculate confidence based on recent variance
            recent_errors = [abs(values[i] - smoothed_values[i]) for i in range(1, len(values))]
            avg_error = np.mean(recent_errors) if recent_errors else 0
            
            if avg_error < 5:
                confidence = 'high'
            elif avg_error < 15:
                confidence = 'medium'
            else:
                confidence = 'low'
            
            current_time = readings[-1].timestamp
            future_time = current_time + timedelta(minutes=self.settings.prediction_minutes_ahead)
            
            return {
                'predicted_value': round(predicted_value, 1),
                'confidence': confidence,
                'prediction_time': future_time,
                'method': 'exponential_smoothing',
                'avg_error': round(avg_error, 2),
                'trend_component': round(trend if 'trend' in locals() else 0, 2)
            }
            
        except Exception as e:
            logger.warning(f"Exponential smoothing failed: {e}")
            return None
    
    def _calculate_confidence(self, r_squared: float, std_err: float, sample_size: int) -> str:
        """Calculate confidence level for prediction"""
        # Base confidence on R-squared
        r_squared_score = 0
        if r_squared >= 0.8:
            r_squared_score = 3
        elif r_squared >= 0.6:
            r_squared_score = 2
        elif r_squared >= 0.4:
            r_squared_score = 1
        
        # Adjust for standard error
        error_score = 0
        if std_err < 5:
            error_score = 3
        elif std_err < 10:
            error_score = 2
        elif std_err < 20:
            error_score = 1
        
        # Adjust for sample size
        size_score = 0
        if sample_size >= 10:
            size_score = 2
        elif sample_size >= 5:
            size_score = 1
        
        total_score = r_squared_score + error_score + size_score
        
        if total_score >= 7:
            return 'high'
        elif total_score >= 4:
            return 'medium'
        else:
            return 'low'
    
    def _select_best_prediction(self, predictions: List[Dict], 
                               readings: List[GlucoseReading]) -> Dict:
        """Select the best prediction from multiple methods"""
        if not predictions:
            return {
                'predicted_value': None,
                'confidence': 'low',
                'prediction_time': None,
                'method': 'no_valid_predictions',
                'warning': 'All prediction methods failed'
            }
        
        # Score each prediction
        scored_predictions = []
        current_value = readings[-1].value
        
        for pred in predictions:
            score = 0
            
            # Confidence score
            if pred['confidence'] == 'high':
                score += 3
            elif pred['confidence'] == 'medium':
                score += 2
            elif pred['confidence'] == 'low':
                score += 1
            
            # Reasonableness check (predicted value shouldn't be too extreme)
            predicted_val = pred['predicted_value']
            if predicted_val is not None:
                change_from_current = abs(predicted_val - current_value)
                
                # Penalize extreme changes
                if change_from_current > 100:  # Very extreme change
                    score -= 2
                elif change_from_current > 50:  # Moderate extreme change
                    score -= 1
                
                # Penalize biologically impossible values
                if predicted_val < 20 or predicted_val > 600:
                    score -= 3
            
            # Method preference (linear is most interpretable)
            if pred['method'] == 'linear_extrapolation':
                score += 1
            
            scored_predictions.append((score, pred))
        
        # Select highest scoring prediction
        best_prediction = max(scored_predictions, key=lambda x: x[0])[1]
        
        # Add ensemble information if multiple methods available
        if len(predictions) > 1:
            pred_values = [p['predicted_value'] for p in predictions if p['predicted_value'] is not None]
            if pred_values:
                best_prediction['ensemble_avg'] = round(np.mean(pred_values), 1)
                best_prediction['ensemble_std'] = round(np.std(pred_values), 1)
                best_prediction['method_count'] = len(predictions)
        
        return best_prediction
    
    def assess_prediction_risk(self, prediction: Dict, current_reading: GlucoseReading) -> Dict:
        """Assess risk factors for the prediction"""
        if prediction['predicted_value'] is None:
            return {'risk_level': 'unknown', 'risk_factors': []}
        
        predicted_value = prediction['predicted_value']
        current_value = current_reading.value
        risk_factors = []
        risk_level = 'low'
        
        # Check for predicted low values
        if predicted_value <= self.settings.critical_low_threshold:
            risk_factors.append(f"Predicted critical low: {predicted_value} mg/dL")
            risk_level = 'critical'
        elif predicted_value <= self.settings.low_glucose_threshold:
            risk_factors.append(f"Predicted low glucose: {predicted_value} mg/dL")
            risk_level = 'high' if risk_level != 'critical' else risk_level
        
        # Check for predicted high values
        elif predicted_value >= self.settings.critical_high_threshold:
            risk_factors.append(f"Predicted critical high: {predicted_value} mg/dL")
            risk_level = 'critical'
        elif predicted_value >= self.settings.high_glucose_threshold:
            risk_factors.append(f"Predicted high glucose: {predicted_value} mg/dL")
            risk_level = 'high' if risk_level != 'critical' else risk_level
        
        # Check for rapid changes
        change = predicted_value - current_value
        if abs(change) > 50:
            risk_factors.append(f"Large predicted change: {change:+.1f} mg/dL")
            if risk_level == 'low':
                risk_level = 'medium'
        
        # Check prediction confidence
        if prediction['confidence'] == 'low':
            risk_factors.append("Low prediction confidence")
            if risk_level == 'low':
                risk_level = 'medium'
        
        return {
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'predicted_change': round(change, 1),
            'time_to_threshold': self._estimate_time_to_threshold(
                current_value, predicted_value, prediction
            )
        }
    
    def _estimate_time_to_threshold(self, current: float, predicted: float, 
                                   prediction: Dict) -> Optional[Dict]:
        """Estimate time to reach critical thresholds"""
        if prediction.get('slope') is None:
            return None
        
        slope = prediction['slope']
        if abs(slope) < 0.1:  # Very slow change
            return None
        
        thresholds = {
            'low': self.settings.low_glucose_threshold,
            'critical_low': self.settings.critical_low_threshold,
            'high': self.settings.high_glucose_threshold,
            'critical_high': self.settings.critical_high_threshold
        }
        
        estimates = {}
        for name, threshold in thresholds.items():
            if slope > 0 and current < threshold and 'high' in name:
                time_to_threshold = (threshold - current) / slope
                if 0 < time_to_threshold <= 120:  # Within 2 hours
                    estimates[name] = round(time_to_threshold, 1)
            elif slope < 0 and current > threshold and 'low' in name:
                time_to_threshold = (current - threshold) / abs(slope)
                if 0 < time_to_threshold <= 120:  # Within 2 hours
                    estimates[name] = round(time_to_threshold, 1)
        
        return estimates if estimates else None