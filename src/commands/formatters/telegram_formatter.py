import logging
from datetime import datetime
from typing import Dict, Any
from ..command_processor import CommandResult

logger = logging.getLogger(__name__)


class TelegramFormatter:
    """Formats command results for Telegram display"""
    
    def __init__(self, settings):
        self.settings = settings
    
    def format_insulin_result(self, result: CommandResult) -> str:
        """Format insulin command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [f"Logged {data['units']} units of {data['insulin_type']} insulin"]
        
        if data.get('notes'):
            output.append(f"Notes: {data['notes']}")
        
        output.append(f"Duration: {data['duration']} minutes")
        return "\n".join(output)
    
    def format_carbs_result(self, result: CommandResult) -> str:
        """Format carbs command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [f"Logged {data['grams']}g of {data['carb_type']} carbs"]
        
        if data.get('notes'):
            output.append(f"Notes: {data['notes']}")
        
        output.append(f"Absorption time: {data['absorption_time']} minutes")
        return "\n".join(output)
    
    def format_iob_override_result(self, result: CommandResult) -> str:
        """Format IOB override command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [f"✅ Set IOB to *{data['iob_value']:.1f} units* (from {data['source']})"]
        
        if data.get('notes'):
            output.append(f"📝 Notes: {data['notes']}")
        
        # Check if we have enhanced status with current glucose and recommendations
        if 'current_status' in data:
            status = data['current_status']
            glucose_data = status.get('glucose', {})
            iob_cob_data = status.get('iob_cob', {})
            recommendations = status.get('recommendations', [])
            
            # Add current glucose status
            output.extend([
                "",
                "📊 *Current Status:*"
            ])
            
            if glucose_data:
                trend_emoji = self._get_trend_arrow(glucose_data.get('trend', 'no_change'))
                output.append(f"🩸 Glucose: *{glucose_data['value']:.0f} mg/dL* {trend_emoji}")
                
                trend_text = self._format_trend_text(glucose_data.get('trend', 'no_change'))
                if trend_text != "Stable":
                    rate = glucose_data.get('rate_of_change', 0)
                    output.append(f"📈 Trend: {trend_text} ({rate:.1f} mg/dL/min)")
            
            # Add IOB/COB information
            if iob_cob_data:
                iob_total = iob_cob_data.get('iob', {}).get('total_iob', 0)
                cob_total = iob_cob_data.get('cob', {}).get('total_cob', 0)
                is_override = iob_cob_data.get('iob', {}).get('is_override', False)
                
                iob_text = f"💉 IOB: *{iob_total:.1f}u*"
                if is_override:
                    iob_text += f" (from {data['source']})"
                output.append(iob_text)
                
                if cob_total > 0:
                    output.append(f"🍎 COB: *{cob_total:.1f}g*")
            
            # Add recommendations
            if recommendations:
                output.extend(["", "💡 *Updated Recommendations:*"])
                for i, rec in enumerate(recommendations, 1):
                    rec_type = rec.get('type', 'unknown').upper()
                    message = rec.get('message', 'No message')
                    urgency = rec.get('urgency', 'normal')
                    
                    # Add urgency emojis
                    urgency_emoji = ""
                    if urgency == 'critical':
                        urgency_emoji = "🚨 "
                    elif urgency == 'high':
                        urgency_emoji = "⚠️ "
                    elif urgency == 'medium':
                        urgency_emoji = "ℹ️ "
                    
                    output.append(f"{i}. {urgency_emoji}*[{rec_type}]* {message}")
            else:
                output.extend(["", "✅ No current recommendations."])
        else:
            # Fallback to simple message if no enhanced status
            output.extend([
                "",
                "⏱ This will be used for next 30 minutes",
                "🔄 This overrides calculated IOB from logged insulin"
            ])
        
        return "\n".join(output)
    
    def format_status_result(self, result: CommandResult) -> str:
        """Format status command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        output = [
            "*Current Status*",
            "=" * 40,
            ""
        ]
        
        if data['active_insulin']:
            output.append(f"*Active Insulin (IOB)*: {data['total_iob']:.1f} units")
            for entry in data['active_insulin'][:3]:  # Show top 3
                output.append(f"   • {entry['units']:.1f}u {entry['insulin_type']} ({entry['minutes_ago']}min ago)")
        else:
            output.append("No active insulin")
        
        output.append("")
        
        if data['active_carbs']:
            output.append(f"*Active Carbs (COB)*: {data['total_cob']:.1f}g")
            for entry in data['active_carbs'][:3]:  # Show top 3
                output.append(f"   • {entry['grams']:.1f}g {entry['carb_type']} ({entry['minutes_ago']}min ago)")
        else:
            output.append("No active carbs")
        
        return "\n".join(output)
    
    def format_history_result(self, result: CommandResult) -> str:
        """Format history command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        hours = data['hours']
        entries = data['entries']
        
        output = [
            f"*History (last {hours} hours)*",
            "=" * 40,
            ""
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
            output.append("")
        
        return "\n".join(output)
    
    def format_reading_result(self, result: CommandResult) -> str:
        """Format reading command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        reading = data['reading']
        
        output = [
            "*Latest Sensor Reading*",
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
        
        output.append(f"*Glucose*: {reading['value']} mg/dL")
        output.append(f"*Time*: {reading['timestamp'].strftime('%H:%M:%S')} ({time_str})")
        
        # Show trend if available
        if 'trend' in data:
            trend = data['trend']
            trend_arrow = self._get_trend_arrow(trend['trend'])
            output.append(f"*Trend*: {self._format_trend_text(trend['trend'])} {trend_arrow}")
            output.append(f"*Rate*: {trend['rate_of_change']:.1f} mg/dL/min")
            output.append("")
        
        # Show IOB/COB if available
        if 'iob_cob' in data:
            iob_cob = data['iob_cob']
            output.append("*Active Factors*")
            
            if iob_cob['iob']['total_iob'] > 0.1:
                iob_source = ""
                if iob_cob['iob'].get('is_override') and data.get('iob_override_entry'):
                    iob_source = f" (from {data['iob_override_entry'].source})"
                output.append(f"   IOB: {iob_cob['iob']['total_iob']:.1f}u{iob_source}")
            
            if iob_cob['cob']['total_cob'] > 1.0:
                output.append(f"   COB: {iob_cob['cob']['total_cob']:.1f}g")
            
            output.append("")
        
        # Show prediction if available
        if 'prediction' in data:
            prediction = data['prediction']
            pred_time = self.settings.prediction_minutes_ahead
            output.append(f"*Prediction ({pred_time}min)*: {prediction['predicted_value']} mg/dL")
            output.append(f"   Confidence: {prediction['confidence'].title()}")
            output.append("")
        
        # Show recommendations if available
        if 'recommendations' in data:
            recommendations = data['recommendations']
            output.append("*Current Recommendations*")
            for i, rec in enumerate(recommendations, 1):
                priority_text = self._get_priority_text(rec)
                rec_type = rec.get('type', 'general').title()
                
                output.append(f"{priority_text} *{rec_type}*: {rec['message']}")
                
                # Add specific parameters
                if 'parameters' in rec:
                    params = rec['parameters']
                    if rec['type'] == 'insulin' and 'recommended_units' in params:
                        output.append(f"   Suggested: {params['recommended_units']} units")
                    elif rec['type'] == 'carbohydrate' and 'recommended_carbs' in params:
                        output.append(f"   Suggested: {params['recommended_carbs']}g carbs")
                
                # Add urgency info for critical recommendations
                if rec.get('urgency') in ['critical', 'high']:
                    output.append(f"   {rec['urgency'].upper()} priority")
                
                if i < len(recommendations):
                    output.append("")
        elif 'trend' in data:
            output.append("*No recommendations at this time*")
            output.append("Current glucose levels appear stable")
        else:
            output.append("*Trend*: Not enough data for analysis")
            output.append("Need at least 2 readings for trend and recommendations")
        
        return "\n".join(output)
    
    def format_next_reading_result(self, result: CommandResult) -> str:
        """Format next reading command result for Telegram"""
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
            output.append(f"Last reading: {last_reading_time.strftime('%H:%M:%S')}")
        
        return "\n".join(output)
    
    def format_help(self) -> str:
        """Format help text for Telegram"""
        return ("*Available Commands*\n"
               "*Insulin Commands:*\n"
               "   /insulin <units> [type] [notes] - Log insulin dose\n"
               "   /i <units> [type] [notes] - Short form\n"
               "   Types: rapid (default), long, intermediate\n\n"
               "*Carbohydrate Commands:*\n"
               "   /carbs <grams> [type] [notes] - Log carb intake\n"
               "   /c <grams> [type] [notes] - Short form\n"
               "   Types: fast, slow, mixed (default)\n\n"
               "*IOB Override Commands:*\n"
               "   /iob <units> [source] [notes] - Set IOB from pump/Omnipod\n"
               "   /setiob <units> [source] [notes] - Same as iob\n"
               "   Sources: omnipod, pump, manual (default)\n\n"
               "*Information Commands:*\n"
               "   /reading or /r - Latest sensor reading + recommendations\n"
               "   /status or /s - Show current IOB/COB\n"
               "   /history [hours] - Show recent entries\n"
               "   /next or /n - Time until next sensor reading\n"
               "   /help - Show this help\n\n"
               "*Debug Commands:*\n"
               "   /ping - Test bot responsiveness\n"
               "   /test - Run system tests\n"
               "   /debug - Show diagnostic information\n\n"
               "*Examples:*\n"
               "   /reading - Get latest glucose + recommendations\n"
               "   /insulin 2.5 rapid - Log insulin dose\n"
               "   /carbs 30 fast - Log carbs\n"
               "   /status - Show IOB/COB\n"
               "   /iob 0.2 omnipod - Set IOB from pump")
    
    def format_start(self) -> str:
        """Format start message for Telegram"""
        return ("*Glucose Monitor Telegram Bot*\n\n"
               "Welcome! This bot helps you monitor glucose and log treatments.\n\n"
               "Use /help to see all available commands.\n\n"
               "Quick start:\n"
               "• /r - Get latest reading + recommendations\n"
               "• /i 2.5 - Log 2.5 units insulin\n"
               "• /c 30 - Log 30g carbs\n"
               "• /s - Check current IOB/COB status")
    
    def format_ping(self) -> str:
        """Format ping response for Telegram"""
        return f"Pong! {datetime.now().strftime('%H:%M:%S')}\n\nBot is responsive and processing messages."
    
    def format_debug_result(self, result: CommandResult) -> str:
        """Format debug command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        telegram_config = data['telegram_config']
        message_info = data['message_info']
        
        debug_info = []
        debug_info.append("*Debug Information*")
        debug_info.append("=" * 30)
        
        # Telegram configuration
        debug_info.append(f"Bot enabled: {telegram_config.get('enabled', 'Unknown')}")
        api_url = telegram_config.get('api_url', '')
        if api_url:
            debug_info.append(f"API URL: {api_url[:50] + '...' if len(api_url) > 50 else api_url}")
        debug_info.append(f"Configured chat ID: {telegram_config.get('chat_id', 'Unknown')}")
        debug_info.append(f"Message polling: {telegram_config.get('running', 'Unknown')}")
        
        # Current message info
        debug_info.append("")
        debug_info.append("*Current Message*")
        debug_info.append(f"Message ID: {message_info.get('message_id', 'N/A')}")
        
        chat_info = message_info.get('chat', {})
        debug_info.append(f"Chat ID: {chat_info.get('id', 'N/A')}")
        debug_info.append(f"Chat type: {chat_info.get('type', 'N/A')}")
        debug_info.append(f"Chat title: {chat_info.get('title', 'N/A')}")
        
        # Show user info if available (regular messages)
        user_info = message_info.get('from', {})
        if user_info:
            debug_info.append(f"User ID: {user_info.get('id', 'N/A')}")
            debug_info.append(f"Username: @{user_info.get('username', 'N/A')}")
            debug_info.append(f"First name: {user_info.get('first_name', 'N/A')}")
        
        # Show sender_chat info if available (channel posts)
        sender_chat = message_info.get('sender_chat', {})
        if sender_chat:
            debug_info.append(f"Sender chat ID: {sender_chat.get('id', 'N/A')}")
            debug_info.append(f"Sender chat title: {sender_chat.get('title', 'N/A')}")
            debug_info.append(f"Sender chat type: {sender_chat.get('type', 'N/A')}")
        
        # Bot state
        debug_info.append("")
        debug_info.append("*Bot State*")
        debug_info.append(f"Last update ID: {telegram_config.get('last_update_id', 'N/A')}")
        debug_info.append(f"Registered commands: {telegram_config.get('command_count', 'N/A')}")
        
        return "\n".join(debug_info)
    
    def format_test_result(self, result: CommandResult) -> str:
        """Format test command result for Telegram"""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        test_results = []
        test_results.append("*System Tests*")
        test_results.append("=" * 20)
        
        # Database test
        db_result = data.get('database', {})
        if db_result.get('status') == 'connected':
            test_results.append("Database: Connected")
            test_results.append(f"   Active insulin entries: {db_result.get('active_insulin_count', 0)}")
            test_results.append(f"   Active carb entries: {db_result.get('active_carbs_count', 0)}")
        else:
            test_results.append(f"Database: {db_result.get('error', 'Error')}")
        
        # Settings test
        settings_result = data.get('settings', {})
        if settings_result.get('status') == 'loaded':
            test_results.append("Settings: Loaded")
            test_results.append(f"   Poll interval: {settings_result.get('poll_interval', 'N/A')}min")
            test_results.append(f"   Prediction window: {settings_result.get('prediction_window', 'N/A')}min")
        else:
            test_results.append(f"Settings: {settings_result.get('error', 'Error')}")
        
        # Message processing test
        msg_result = data.get('message_processing', {})
        if msg_result.get('status') == 'working':
            test_results.append("Message processing: Working")
            test_results.append("   This message processed successfully")
        
        return "\n".join(test_results)
    
    def _get_trend_arrow(self, trend: str) -> str:
        """Get arrow symbol for trend (only place emojis are allowed)"""
        trend_emojis = {
            'very_fast_up': '⬆️⬆️⬆️',
            'fast_up': '⬆️⬆️',
            'up': '⬆️',
            'no_change': '➡️',
            'down': '⬇️',
            'fast_down': '⬇️⬇️',
            'very_fast_down': '⬇️⬇️⬇️'
        }
        return trend_emojis.get(trend, '➡️')
    
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
    
    def _get_priority_text(self, recommendation: Dict) -> str:
        """Get priority indicator for recommendation"""
        urgency = recommendation.get('urgency', '')
        priority = recommendation.get('priority', 5)
        
        if urgency == 'critical' or priority == 1:
            return '[CRITICAL]'
        elif urgency == 'high' or priority == 2:
            return '[HIGH]'
        elif urgency == 'medium' or priority <= 3:
            return '[MEDIUM]'
        else:
            return '[INFO]'
    
    def format_note_result(self, result: Dict) -> str:
        """Format note addition result"""
        if not result['success']:
            return f"❌ {result.get('error', 'Unknown error adding note')}"
        
        data = result['data']
        note_icon = {'observation': '📝', 'trend': '📈', 'recommendation-note': '💡'}.get(data['note_type'], '📝')
        
        output = [f"{note_icon} *Note Added*"]
        output.append(f"Text: {data['note_text']}")
        output.append(f"Type: {data['note_type'].title()}")
        
        if data.get('glucose_value'):
            output.append(f"Glucose: {data['glucose_value']:.0f} mg/dL")
        
        output.append(f"Time: {data['timestamp'].strftime('%H:%M:%S')}")
        
        return "\n".join(output)
    
    def format_notes_result(self, result: Dict) -> str:
        """Format notes list result"""
        if not result['success']:
            return f"❌ {result.get('error', 'Unknown error retrieving notes')}"
        
        data = result['data']
        notes = data['notes']
        
        if not notes:
            filter_text = f" ({data['note_type']})" if data.get('note_type') else ""
            return f"📝 No notes found from last {data['hours']} hours{filter_text}"
        
        output = [f"📝 *Recent Notes* (last {data['hours']}h)"]
        output.append("")
        
        for note in notes:
            note_icon = {'observation': '📝', 'trend': '📈', 'recommendation-note': '💡'}.get(note['note_type'], '📝')
            
            # Format time
            if note['minutes_ago'] < 1:
                time_str = "Just now"
            elif note['minutes_ago'] == 1:
                time_str = "1 min ago"
            elif note['minutes_ago'] < 60:
                time_str = f"{note['minutes_ago']} mins ago"
            else:
                hours = note['minutes_ago'] // 60
                time_str = f"{hours}h ago"
            
            glucose_text = f" ({note['glucose_value']:.0f} mg/dL)" if note.get('glucose_value') else ""
            output.append(f"{note_icon} {note['note_text']}{glucose_text}")
            output.append(f"   {time_str} • {note['note_type']}")
            output.append("")
        
        if len(notes) < data['total_notes']:
            output.append(f"... and {data['total_notes'] - len(notes)} more")
        
        return "\n".join(output)