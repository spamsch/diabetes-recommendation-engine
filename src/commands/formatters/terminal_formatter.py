import logging
from datetime import datetime
from typing import Dict, Any
from ..command_processor import CommandResult

logger = logging.getLogger(__name__)


class TerminalFormatter:
    """Formats command results for terminal display"""
    
    def __init__(self, settings):
        self.settings = settings
    
    def format_insulin_result(self, result: CommandResult) -> str:
        """Format insulin command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [f"Logged {data['units']} units of {data['insulin_type']} insulin"]
        
        if data.get('notes'):
            output.append(f"   Notes: {data['notes']}")
        
        output.append(f"   Duration: {data['duration']} minutes")
        return "\n".join(output)
    
    def format_carbs_result(self, result: CommandResult) -> str:
        """Format carbs command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [f"Logged {data['grams']}g of {data['carb_type']} carbs"]
        
        if data.get('notes'):
            output.append(f"   Notes: {data['notes']}")
        
        output.append(f"   Absorption time: {data['absorption_time']} minutes")
        return "\n".join(output)
    
    def format_iob_override_result(self, result: CommandResult) -> str:
        """Format IOB override command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [f"Set IOB to {data['iob_value']:.1f} units (from {data['source']})"]
        
        if data.get('notes'):
            output.append(f"   Notes: {data['notes']}")
        
        # Check if we have enhanced status with current glucose and recommendations
        if 'current_status' in data:
            status = data['current_status']
            glucose_data = status.get('glucose', {})
            iob_cob_data = status.get('iob_cob', {})
            recommendations = status.get('recommendations', [])
            
            # Add current glucose status
            output.extend([
                "",
                "Current Status After IOB Update:",
                "=" * 35
            ])
            
            if glucose_data:
                trend_arrow = self._get_trend_arrow(glucose_data.get('trend', 'no_change'))
                output.append(f"Glucose: {glucose_data['value']:.0f} mg/dL {trend_arrow}")
                
                trend_text = self._format_trend_text(glucose_data.get('trend', 'no_change'))
                if trend_text != "Stable":
                    rate = glucose_data.get('rate_of_change', 0)
                    output.append(f"Trend: {trend_text} ({rate:.1f} mg/dL/min)")
            
            # Add IOB/COB information
            if iob_cob_data:
                iob_total = iob_cob_data.get('iob', {}).get('total_iob', 0)
                cob_total = iob_cob_data.get('cob', {}).get('total_cob', 0)
                is_override = iob_cob_data.get('iob', {}).get('is_override', False)
                
                iob_text = f"IOB: {iob_total:.1f}u"
                if is_override:
                    iob_text += f" (from {data['source']})"
                output.append(iob_text)
                
                if cob_total > 0:
                    output.append(f"COB: {cob_total:.1f}g")
            
            # Add recommendations
            if recommendations:
                output.extend(["", "Updated Recommendations:"])
                for i, rec in enumerate(recommendations, 1):
                    rec_type = rec.get('type', 'unknown').upper()
                    message = rec.get('message', 'No message')
                    output.append(f"{i}. [{rec_type}] {message}")
            else:
                output.extend(["", "No current recommendations."])
        else:
            # Fallback to simple message if no enhanced status
            output.extend([
                "   This will be used for next 30 minutes",
                "   This overrides calculated IOB from logged insulin"
            ])
        
        return "\n".join(output)
    
    def format_status_result(self, result: CommandResult) -> str:
        """Format status command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [
            "\nCurrent Status",
            "=" * 40
        ]
        
        if data['active_insulin']:
            output.append(f"Active Insulin (IOB): {data['total_iob']:.1f} units")
            for entry in data['active_insulin'][:3]:  # Show top 3
                output.append(f"   • {entry['units']:.1f}u {entry['insulin_type']} ({entry['minutes_ago']}min ago)")
        else:
            output.append("No active insulin")
        
        if data['active_carbs']:
            output.append(f"Active Carbs (COB): {data['total_cob']:.1f}g")
            for entry in data['active_carbs'][:3]:  # Show top 3
                output.append(f"   • {entry['grams']:.1f}g {entry['carb_type']} ({entry['minutes_ago']}min ago)")
        else:
            output.append("No active carbs")
        
        return "\n".join(output)
    
    def format_history_result(self, result: CommandResult) -> str:
        """Format history command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        hours = data['hours']
        entries = data['entries']
        
        output = [
            f"\nHistory (last {hours} hours)",
            "=" * 40
        ]
        
        if not entries:
            output.append(f"No entries found in the last {hours} hours")
            return "\n".join(output)
        
        for entry in entries:
            time_str = entry['timestamp'].strftime("%H:%M")
            if entry['type'] == 'insulin':
                output.append(f"Insulin {time_str} - {entry['units']:.1f}u {entry['insulin_type']}")
                if entry.get('notes'):
                    output.append(f"     Notes: {entry['notes']}")
            else:  # carbs
                output.append(f"Carbs {time_str} - {entry['grams']:.1f}g {entry['carb_type']}")
                if entry.get('notes'):
                    output.append(f"     Notes: {entry['notes']}")
        
        return "\n".join(output)
    
    def format_reading_result(self, result: CommandResult) -> str:
        """Format reading command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        reading = data['reading']
        
        output = [
            "\nLatest Sensor Reading",
            "=" * 30,
            ""
        ]
        
        # Show the reading with time info
        minutes_ago = reading['minutes_ago']
        if minutes_ago < 1:
            time_str = "Just now"
        elif minutes_ago == 1:
            time_str = "1 minute ago"
        else:
            time_str = f"{minutes_ago} minutes ago"
        
        output.append(f"Glucose: {reading['value']} mg/dL")
        output.append(f"Time: {reading['timestamp'].strftime('%H:%M:%S')} ({time_str})")
        
        # Show trend if available
        if 'trend' in data:
            trend = data['trend']
            trend_arrow = self._get_trend_arrow(trend['trend'])
            output.append(f"Trend: {self._format_trend_text(trend['trend'])} {trend_arrow}")
            output.append(f"Rate: {trend['rate_of_change']:.1f} mg/dL/min")
            output.append("")
        
        # Show IOB/COB if available
        if 'iob_cob' in data:
            iob_cob = data['iob_cob']
            output.append("Active Factors:")
            
            if iob_cob['iob']['total_iob'] > 0.1:
                iob_source = ""
                if iob_cob['iob'].get('is_override') and data.get('iob_override_entry'):
                    iob_source = f" (from {data['iob_override_entry'].source})"
                output.append(f"  Insulin on Board: {iob_cob['iob']['total_iob']:.1f} units{iob_source}")
            
            if iob_cob['cob']['total_cob'] > 1.0:
                output.append(f"  Carbs on Board: {iob_cob['cob']['total_cob']:.1f}g")
            
            if iob_cob['iob']['total_iob'] > 0.1 or iob_cob['cob']['total_cob'] > 1.0:
                impact = iob_cob['impact']
                output.append(f"  Net Effect: {impact['net_effect']:+.1f} mg/dL")
                output.append(f"  Predicted: {impact['predicted_glucose']:.0f} mg/dL")
            
            output.append("")
        
        # Show prediction if available
        if 'prediction' in data:
            prediction = data['prediction']
            pred_time = self.settings.prediction_minutes_ahead
            output.append(f"Prediction ({pred_time} min):")
            output.append(f"  Value: {prediction['predicted_value']} mg/dL")
            output.append(f"  Confidence: {prediction['confidence'].title()}")
            output.append(f"  Method: {prediction['method'].replace('_', ' ').title()}")
            output.append("")
        
        # Show recommendations if available
        if 'recommendations' in data:
            recommendations = data['recommendations']
            output.append(f"Recommendations ({len(recommendations)}):")
            for i, rec in enumerate(recommendations, 1):
                urgency = rec.get('urgency', 'normal')
                output.append(f"  {i}. [{rec['type'].upper()}] {rec['message']}")
                if urgency in ['critical', 'high']:
                    output.append(f"     {urgency.upper()} priority")
        elif 'trend' in data:
            output.append("No recommendations at this time")
        else:
            output.append("Trend: Not enough data for analysis")
            output.append("Need at least 2 readings for trend and recommendations")
        
        return "\n".join(output)
    
    def format_next_reading_result(self, result: CommandResult) -> str:
        """Format next reading command result for terminal"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        wait_seconds = data.get('wait_seconds', 0)
        last_reading_time = data.get('last_reading_time')
        
        output = []
        
        if wait_seconds > 0:
            minutes = int(wait_seconds // 60)
            seconds = int(wait_seconds % 60)
            output.append(f"Next sensor reading in: {minutes}m {seconds}s")
        else:
            output.append("Next sensor reading: Available now")
        
        if last_reading_time:
            output.append(f"   Last reading: {last_reading_time.strftime('%H:%M:%S')}")
        
        return "\n".join(output)
    
    def format_help(self) -> str:
        """Format help text for terminal"""
        return """
Available Commands
==================================================
Insulin Commands:
   insulin <units> [type] [notes]  - Log insulin dose
   i <units> [type] [notes]        - Short form
   Types: rapid (default), long, intermediate

Carbohydrate Commands:
   carbs <grams> [type] [notes]    - Log carb intake
   c <grams> [type] [notes]        - Short form
   Types: fast, slow, mixed (default)

IOB Override Commands:
   iob <units> [source] [notes]    - Set IOB from pump/Omnipod
   setiob <units> [source] [notes] - Same as iob
   Sources: omnipod, pump, manual (default)

Information Commands:
   reading                         - Latest sensor reading + recommendations
   status / s                      - Show current IOB/COB
   history [hours]                 - Show recent entries
   next / n                        - Time until next sensor reading
   help                            - Show this help

Control Commands:
   quit / q                        - Exit the application

Examples:
   insulin 2.5 rapid               - Log 2.5 units rapid insulin
   i 1.0 long 'bedtime dose'       - Log 1 unit long-acting insulin
   carbs 30 fast                   - Log 30g fast carbs
   c 45 mixed 'pasta dinner'       - Log 45g mixed carbs
   iob 0.2 omnipod                 - Set IOB to 0.2u from Omnipod
   reading                         - Show latest glucose + recommendations
"""
    
    def _get_trend_arrow(self, trend: str) -> str:
        """Get arrow symbol for trend (only place emojis are allowed)"""
        arrows = {
            'very_fast_up': '↑↑↑',
            'fast_up': '↑↑',
            'up': '↑',
            'no_change': '→',
            'down': '↓',
            'fast_down': '↓↓',
            'very_fast_down': '↓↓↓'
        }
        return arrows.get(trend, '→')
    
    def _format_trend_text(self, trend: str) -> str:
        """Format trend text for display"""
        trend_text = {
            'very_fast_up': 'Rising Very Rapidly',
            'fast_up': 'Rising Rapidly',
            'up': 'Rising',
            'no_change': 'Stable',
            'down': 'Falling',
            'fast_down': 'Falling Rapidly',
            'very_fast_down': 'Falling Very Rapidly'
        }
        return trend_text.get(trend, 'Unknown')