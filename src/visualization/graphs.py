import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from ..database import GlucoseReading
from ..config import Settings

logger = logging.getLogger(__name__)

class GlucoseGrapher:
    """Creates graphs and visualizations for glucose data"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        plt.style.use('seaborn-v0_8')  # Use a clean style
        
    def create_glucose_timeline(self, readings: List[GlucoseReading], 
                              prediction: Optional[Dict] = None,
                              save_path: Optional[str] = None) -> str:
        """Create a timeline graph of glucose readings"""
        if len(readings) < 2:
            logger.warning("Not enough readings to create graph")
            return None
        
        # Sort readings by timestamp
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        
        # Extract data
        timestamps = [r.timestamp for r in sorted_readings]
        values = [r.value for r in sorted_readings]
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Plot glucose line
        ax.plot(timestamps, values, 'b-', linewidth=2, marker='o', 
                markersize=4, label='Glucose', alpha=0.8)
        
        # Add target ranges
        self._add_target_ranges(ax, timestamps[0], timestamps[-1])
        
        # Add prediction if available
        if prediction and prediction.get('predicted_value'):
            self._add_prediction(ax, timestamps[-1], prediction)
        
        # Customize the plot
        self._customize_plot(ax, "Glucose Timeline")
        
        # Add trend annotations
        self._add_trend_annotations(ax, sorted_readings)
        
        # Save or display
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Graph saved to {save_path}")
            return save_path
        else:
            plt.show()
            return "displayed"
    
    def create_trend_analysis_graph(self, readings: List[GlucoseReading],
                                  trend_analysis: Dict,
                                  save_path: Optional[str] = None) -> str:
        """Create a graph showing trend analysis"""
        if len(readings) < 3:
            return None
        
        sorted_readings = sorted(readings, key=lambda r: r.timestamp)
        timestamps = [r.timestamp for r in sorted_readings]
        values = [r.value for r in sorted_readings]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), 
                                      height_ratios=[3, 1], sharex=True)
        
        # Main glucose plot
        ax1.plot(timestamps, values, 'b-', linewidth=2, marker='o', 
                markersize=4, alpha=0.8)
        
        # Add trend line if available
        if trend_analysis.get('rate_of_change'):
            self._add_trend_line(ax1, timestamps, values, trend_analysis)
        
        # Add target ranges
        self._add_target_ranges(ax1, timestamps[0], timestamps[-1])
        
        self._customize_plot(ax1, "Glucose with Trend Analysis")
        ax1.set_xlabel('')  # Remove x-label for top plot
        
        # Rate of change plot
        if len(readings) > 1:
            rates = self._calculate_rates_of_change(sorted_readings)
            rate_times = timestamps[1:]  # One fewer rate than readings
            
            ax2.bar(rate_times, rates, width=timedelta(minutes=2), 
                   alpha=0.7, color='green')
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax2.set_ylabel('Rate of Change\n(mg/dL/min)')
            ax2.set_xlabel('Time')
            ax2.grid(True, alpha=0.3)
            
            # Format x-axis for bottom plot
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            return save_path
        else:
            plt.show()
            return "displayed"
    
    def create_daily_summary(self, readings: List[GlucoseReading],
                           save_path: Optional[str] = None) -> str:
        """Create a daily summary graph"""
        if not readings:
            return None
        
        # Group readings by day
        daily_data = self._group_readings_by_day(readings)
        
        if len(daily_data) < 1:
            return None
        
        fig, axes = plt.subplots(len(daily_data), 1, 
                               figsize=(12, 4 * len(daily_data)),
                               squeeze=False)
        
        for idx, (date_str, day_readings) in enumerate(daily_data.items()):
            ax = axes[idx, 0]
            
            timestamps = [r.timestamp for r in day_readings]
            values = [r.value for r in day_readings]
            
            # Plot glucose line
            ax.plot(timestamps, values, 'b-', linewidth=2, marker='o', 
                   markersize=3, alpha=0.8)
            
            # Add target ranges
            self._add_target_ranges(ax, timestamps[0], timestamps[-1])
            
            # Calculate daily statistics
            avg_glucose = np.mean(values)
            min_glucose = np.min(values)
            max_glucose = np.max(values)
            
            # Set title with statistics
            ax.set_title(f"{date_str} - Avg: {avg_glucose:.0f}, "
                        f"Range: {min_glucose:.0f}-{max_glucose:.0f} mg/dL")
            
            # Customize axis
            ax.set_ylabel('Glucose (mg/dL)')
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
            
            if idx == len(daily_data) - 1:  # Last subplot
                ax.set_xlabel('Time')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            return save_path
        else:
            plt.show()
            return "displayed"
    
    def _add_target_ranges(self, ax, start_time: datetime, end_time: datetime):
        """Add colored target ranges to the plot"""
        # Target range (70-180 mg/dL)
        ax.axhspan(self.settings.low_glucose_threshold, 
                  self.settings.high_glucose_threshold,
                  alpha=0.2, color='green', label='Target Range')
        
        # Low range (55-70 mg/dL)
        ax.axhspan(self.settings.critical_low_threshold,
                  self.settings.low_glucose_threshold,
                  alpha=0.2, color='yellow', label='Low')
        
        # Critical low (<55 mg/dL)
        ax.axhspan(0, self.settings.critical_low_threshold,
                  alpha=0.2, color='red', label='Critical Low')
        
        # High range (180-300 mg/dL)
        ax.axhspan(self.settings.high_glucose_threshold,
                  self.settings.critical_high_threshold,
                  alpha=0.2, color='orange', label='High')
        
        # Critical high (>300 mg/dL)
        ax.axhspan(self.settings.critical_high_threshold, 500,
                  alpha=0.2, color='red', label='Critical High')
    
    def _add_prediction(self, ax, last_timestamp: datetime, prediction: Dict):
        """Add prediction to the plot"""
        pred_time = last_timestamp + timedelta(
            minutes=self.settings.prediction_minutes_ahead
        )
        pred_value = prediction['predicted_value']
        
        # Draw prediction line
        ax.plot([last_timestamp, pred_time], 
               [ax.get_ylim()[0], pred_value], 
               'r--', linewidth=2, alpha=0.7, label='Prediction')
        
        # Add prediction point
        ax.plot(pred_time, pred_value, 'ro', markersize=8, alpha=0.7)
        
        # Add text annotation
        confidence = prediction.get('confidence', 'unknown')
        ax.annotate(f'Pred: {pred_value:.0f}\n({confidence})',
                   xy=(pred_time, pred_value),
                   xytext=(10, 10), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    def _add_trend_line(self, ax, timestamps: List[datetime], 
                       values: List[float], trend_analysis: Dict):
        """Add trend line to the plot"""
        if len(timestamps) < 2:
            return
        
        # Calculate trend line
        rate = trend_analysis['rate_of_change']  # mg/dL per minute
        last_time = timestamps[-1]
        last_value = values[-1]
        
        # Extend trend line backwards and forwards
        extend_minutes = 30
        start_time = last_time - timedelta(minutes=extend_minutes)
        end_time = last_time + timedelta(minutes=extend_minutes)
        
        start_value = last_value - (rate * extend_minutes)
        end_value = last_value + (rate * extend_minutes)
        
        ax.plot([start_time, end_time], [start_value, end_value],
               'g--', linewidth=2, alpha=0.6, label='Trend Line')
    
    def _add_trend_annotations(self, ax, readings: List[GlucoseReading]):
        """Add trend arrows and annotations"""
        if len(readings) < 2:
            return
        
        # Add arrows for significant changes
        for i in range(1, len(readings)):
            prev_reading = readings[i-1]
            curr_reading = readings[i]
            
            change = curr_reading.value - prev_reading.value
            
            if abs(change) > 20:  # Significant change
                arrow_color = 'red' if change > 0 else 'blue'
                ax.annotate('', xy=(curr_reading.timestamp, curr_reading.value),
                          xytext=(prev_reading.timestamp, prev_reading.value),
                          arrowprops=dict(arrowstyle='->', color=arrow_color, 
                                        lw=2, alpha=0.7))
    
    def _customize_plot(self, ax, title: str):
        """Apply standard customization to plot"""
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_ylabel('Glucose (mg/dL)', fontsize=12)
        ax.set_xlabel('Time', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Set y-axis limits
        ax.set_ylim(40, 350)
    
    def _calculate_rates_of_change(self, readings: List[GlucoseReading]) -> List[float]:
        """Calculate rates of change between consecutive readings"""
        rates = []
        for i in range(1, len(readings)):
            prev_reading = readings[i-1]
            curr_reading = readings[i]
            
            time_diff = (curr_reading.timestamp - prev_reading.timestamp).total_seconds() / 60.0
            value_diff = curr_reading.value - prev_reading.value
            
            if time_diff > 0:
                rate = value_diff / time_diff
                rates.append(rate)
            else:
                rates.append(0.0)
        
        return rates
    
    def _group_readings_by_day(self, readings: List[GlucoseReading]) -> Dict:
        """Group readings by day"""
        daily_data = {}
        
        for reading in readings:
            date_str = reading.timestamp.strftime('%Y-%m-%d')
            if date_str not in daily_data:
                daily_data[date_str] = []
            daily_data[date_str].append(reading)
        
        # Sort readings within each day
        for date_str in daily_data:
            daily_data[date_str].sort(key=lambda r: r.timestamp)
        
        return daily_data
    
    def create_statistics_summary(self, readings: List[GlucoseReading]) -> Dict:
        """Create statistical summary of glucose data"""
        if not readings:
            return {}
        
        values = [r.value for r in readings]
        
        stats = {
            'count': len(values),
            'mean': np.mean(values),
            'median': np.median(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'time_range': {
                'start': min(r.timestamp for r in readings),
                'end': max(r.timestamp for r in readings)
            },
            'target_range_percentage': self._calculate_time_in_range(
                values, self.settings.low_glucose_threshold, 
                self.settings.high_glucose_threshold
            ),
            'low_percentage': self._calculate_time_below_threshold(
                values, self.settings.low_glucose_threshold
            ),
            'high_percentage': self._calculate_time_above_threshold(
                values, self.settings.high_glucose_threshold
            )
        }
        
        return stats
    
    def _calculate_time_in_range(self, values: List[float], 
                               low_threshold: float, high_threshold: float) -> float:
        """Calculate percentage of time in target range"""
        in_range = sum(1 for v in values if low_threshold <= v <= high_threshold)
        return (in_range / len(values)) * 100 if values else 0
    
    def _calculate_time_below_threshold(self, values: List[float], 
                                      threshold: float) -> float:
        """Calculate percentage of time below threshold"""
        below = sum(1 for v in values if v < threshold)
        return (below / len(values)) * 100 if values else 0
    
    def _calculate_time_above_threshold(self, values: List[float], 
                                      threshold: float) -> float:
        """Calculate percentage of time above threshold"""
        above = sum(1 for v in values if v > threshold)
        return (above / len(values)) * 100 if values else 0