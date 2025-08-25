import logging
import requests
import json
import threading
import time
import re
from typing import Dict, List, Optional, Callable
from datetime import datetime
from ..config import Settings
from ..commands import CommandProcessor
from ..commands.formatters import TelegramFormatter

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles sending notifications to Telegram and processing incoming messages"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bot_url = settings.telegram_bot_url
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.bot_url and self.chat_id)
        
        # Message handling
        self.running = False
        self.polling_thread = None
        self.last_update_id = None
        self.command_handlers = {}
        self.message_handler = None
        
        # Status message tracking
        self.last_message_time = None
        
        # Extract bot token from URL for API calls
        if self.bot_url:
            # URL format: https://api.telegram.org/bot<TOKEN>/sendMessage
            self.bot_token = self.bot_url.split('/bot')[1].split('/')[0] if '/bot' in self.bot_url else None
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        else:
            self.bot_token = None
            self.api_url = None
        
        if not self.enabled:
            logger.info("Telegram notifications disabled - missing bot URL or chat ID")
        else:
            logger.info("Telegram notifications enabled")
    
    def send_recommendations(self, recommendations: List[Dict], 
                           current_reading: Dict, trend_analysis: Dict) -> bool:
        """Send recommendations to Telegram"""
        if not self.enabled:
            return False
        
        if not recommendations:
            return True  # No recommendations to send
        
        try:
            message = self._format_recommendations_message(
                recommendations, current_reading, trend_analysis
            )
            
            success = self._send_message(message)
            if success:
                logger.info(f"Sent {len(recommendations)} recommendations to Telegram")
            else:
                logger.error("Failed to send recommendations to Telegram")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending Telegram recommendations: {e}")
            return False
    
    def send_alert(self, alert_type: str, message: str, 
                   current_value: float = None, urgency: str = 'medium') -> bool:
        """Send urgent alert to Telegram"""
        if not self.enabled:
            return False
        
        try:
            formatted_message = self._format_alert_message(
                alert_type, message, current_value, urgency
            )
            
            success = self._send_message(formatted_message)
            if success:
                logger.info(f"Sent {alert_type} alert to Telegram")
            else:
                logger.error(f"Failed to send {alert_type} alert to Telegram")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False
    
    def should_send_status_message(self) -> bool:
        """Check if a periodic status message should be sent"""
        if not self.enabled:
            return False
            
        # Check if status messages are disabled (interval = 0)
        if self.settings.telegram_status_interval_minutes == 0:
            return False
            
        # Check time window first
        if not self._is_within_status_hours():
            return False
            
        # Check if enough time has passed since last message
        if self.last_message_time is None:
            return True
            
        time_since_last = (datetime.now() - self.last_message_time).total_seconds()
        interval_seconds = self.settings.telegram_status_interval_minutes * 60
        
        return time_since_last >= interval_seconds
    
    def _is_within_status_hours(self) -> bool:
        """Check if current time is within configured status message hours"""
        now = datetime.now()
        current_hour = now.hour
        
        start_hour = self.settings.telegram_status_start_hour
        end_hour = self.settings.telegram_status_end_hour
        
        # Handle case where end_hour is before start_hour (crosses midnight)
        if end_hour < start_hour:
            # Status hours span midnight (e.g., 22:00 to 07:00)
            return current_hour >= start_hour or current_hour <= end_hour
        else:
            # Normal case (e.g., 07:00 to 22:00)
            return start_hour <= current_hour <= end_hour
    
    def send_status_update(self, glucose_value: float, trend: str, 
                          prediction: Optional[Dict] = None) -> bool:
        """Send routine status update"""
        if not self.enabled:
            return False
        
        try:
            message = self._format_status_message(glucose_value, trend, prediction)
            success = self._send_message(message)
            
            if success:
                logger.info("Sent status update to Telegram")
            else:
                logger.error("Failed to send status update to Telegram")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending Telegram status update: {e}")
            return False
    
    def _format_recommendations_message(self, recommendations: List[Dict], 
                                      current_reading: Dict, 
                                      trend_analysis: Dict) -> str:
        """Format recommendations into a Telegram message"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Header with current status
        message = f"*Glucose Alert* - {timestamp}\n\n"
        
        current_value = current_reading.get('value', 'Unknown')
        trend = trend_analysis.get('trend', 'no_change')
        trend_emoji = self._get_trend_emoji(trend)
        
        message += f"Current: *{current_value} mg/dL* {trend_emoji}\n"
        message += f"Trend: {self._format_trend_text(trend)}\n\n"
        
        # Add each recommendation
        for i, rec in enumerate(recommendations, 1):
            priority_emoji = self._get_priority_emoji(rec)
            rec_type = rec.get('type', 'general').title()
            
            message += f"{priority_emoji} *{rec_type} Recommendation*\n"
            message += f"{rec['message']}\n"
            
            # Add parameters if available
            if 'parameters' in rec:
                params = rec['parameters']
                if rec['type'] == 'insulin' and 'recommended_units' in params:
                    message += f"\nSuggested: {params['recommended_units']} units\n"
                elif rec['type'] == 'carbohydrate' and 'recommended_carbs' in params:
                    message += f"\nSuggested: {params['recommended_carbs']}g carbs\n"
                    if 'suggested_foods' in params:
                        foods = params['suggested_foods'][:2]  # Limit to 2 suggestions
                        message += f"• Options: {', '.join(foods)}\n"
            
            message += "\n"
        
        # Footer
        message += "📱 *Glucose Monitoring System*"
        
        return message
    
    def _format_alert_message(self, alert_type: str, alert_message: str, 
                             current_value: float, urgency: str) -> str:
        """Format alert message"""
        timestamp = datetime.now().strftime("%H:%M")
        
        if urgency == 'critical':
            emoji = "[CRITICAL]"
            header = "CRITICAL ALERT"
        elif urgency == 'high':
            emoji = "[HIGH]"
            header = "HIGH PRIORITY ALERT"
        else:
            emoji = "[INFO]"
            header = "ALERT"
        
        message = f"{emoji} *{header}* - {timestamp}\n\n"
        
        if current_value:
            message += f"Current glucose: *{current_value} mg/dL*\n\n"
        
        message += f"{alert_message}\n\n"
        message += "📱 *Glucose Monitoring System*"
        
        return message
    
    def _format_status_message(self, glucose_value: float, trend: str, 
                              prediction: Optional[Dict]) -> str:
        """Format routine status message"""
        timestamp = datetime.now().strftime("%H:%M")
        trend_emoji = self._get_trend_emoji(trend)
        
        message = f"📊 *Status Update* - {timestamp}\n\n"
        message += f"Current: *{glucose_value} mg/dL* {trend_emoji}\n"
        message += f"Trend: {self._format_trend_text(trend)}\n"
        
        if prediction and prediction.get('predicted_value'):
            pred_time = self.settings.prediction_minutes_ahead
            pred_value = prediction['predicted_value']
            confidence = prediction.get('confidence', 'unknown')
            
            message += f"Predicted ({pred_time}min): {pred_value} mg/dL\n"
            message += f"Confidence: {confidence.title()}\n"
        
        message += "\n_This is a routine status update - no action needed._"
        
        return message
    
    def _send_message(self, message: str) -> bool:
        """Send message to Telegram"""
        if not self.bot_url or not self.chat_id:
            return False
        
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        try:
            response = requests.post(
                self.bot_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.last_message_time = datetime.now()
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error sending to Telegram: {e}")
            return False
    
    def _get_trend_emoji(self, trend: str) -> str:
        """Get emoji for trend"""
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
    
    def _get_priority_emoji(self, recommendation: Dict) -> str:
        """Get priority indicator based on recommendation priority"""
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
    
    def test_connection(self) -> bool:
        """Test Telegram connection"""
        if not self.enabled:
            return False
        
        # Test connection without sending message
        try:
            url = f"{self.api_url}/getMe"
            response = requests.get(url, timeout=10)
            return response.status_code == 200 and response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False
    
    def get_bot_info(self) -> Dict:
        """Get information about the bot (for debugging)"""
        if not self.api_url:
            return {"error": "No API URL configured"}
        
        try:
            url = f"{self.api_url.replace('/sendMessage', '')}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                return {"error": f"HTTP {response.status_code}", "response": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def get_webhook_info(self) -> Dict:
        """Get webhook information (for debugging)"""
        if not self.api_url:
            return {"error": "No API URL configured"}
        
        try:
            url = f"{self.api_url.replace('/sendMessage', '')}/getWebhookInfo"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                return {"error": f"HTTP {response.status_code}", "response": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def clear_webhook(self) -> Dict:
        """Clear webhook to enable polling"""
        if not self.api_url:
            return {"error": "No API URL configured"}
        
        try:
            url = f"{self.api_url.replace('/sendMessage', '')}/setWebhook"
            data = {"url": ""}  # Empty URL clears the webhook
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}", "response": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def start_message_polling(self):
        """Start polling for incoming messages"""
        if not self.enabled or not self.api_url:
            logger.warning("Cannot start message polling - Telegram not properly configured")
            logger.debug(f"enabled: {self.enabled}, api_url: {self.api_url}")
            return
        
        if self.running:
            logger.debug("Message polling already running")
            return
        
        self.running = True
        self.polling_thread = threading.Thread(target=self._poll_messages, daemon=True)
        self.polling_thread.start()
        logger.info(f"Started Telegram message polling for chat_id: {self.chat_id}")
        logger.debug(f"Polling URL: {self.api_url}/getUpdates")
    
    def stop_message_polling(self):
        """Stop polling for messages"""
        self.running = False
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=2.0)
        logger.info("Stopped Telegram message polling")
    
    def register_command_handler(self, command: str, handler: Callable):
        """Register a handler for a specific command"""
        self.command_handlers[command.lower()] = handler
        logger.info(f"Registered handler for command: /{command}")
    
    def register_message_handler(self, handler: Callable):
        """Register a general message handler"""
        self.message_handler = handler
    
    def _poll_messages(self):
        """Poll for messages in a separate thread"""
        poll_count = 0
        logger.info("Starting message polling loop")
        
        while self.running:
            try:
                poll_count += 1
                logger.debug(f"Polling attempt #{poll_count}")
                
                updates = self._get_updates()
                if updates:
                    logger.info(f"Received {len(updates)} update(s)")
                    for update in updates:
                        logger.debug(f"Processing update: {update.get('update_id')}")
                        self._process_update(update)
                else:
                    logger.debug("No updates received")
                
                # Log periodic status
                if poll_count % 30 == 0:  # Every 30 polls (30 seconds)
                    logger.info(f"Message polling active - {poll_count} polls completed")
                
                # Sleep between polls
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error polling Telegram messages: {e}")
                logger.exception("Full exception details:")
                time.sleep(5)  # Longer sleep on error
        
        logger.info("Message polling loop stopped")
    
    def _get_updates(self) -> List[Dict]:
        """Get updates from Telegram API"""
        if not self.api_url:
            logger.debug("No API URL configured")
            return []
        
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                'timeout': 10,
                'allowed_updates': ['message', 'channel_post']
            }
            
            if self.last_update_id:
                params['offset'] = self.last_update_id + 1
                logger.debug(f"Polling with offset: {self.last_update_id + 1}")
            else:
                logger.debug("First poll - no offset")
            
            logger.debug(f"Making request to: {url} with params: {params}")
            
            response = requests.get(url, params=params, timeout=15)
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Response data keys: {data.keys()}")
                logger.debug(f"Response ok: {data.get('ok')}")
                
                if data.get('ok') and data.get('result'):
                    updates = data['result']
                    logger.debug(f"Raw updates received: {len(updates)}")
                    
                    if updates:
                        # Update last_update_id to avoid processing same messages
                        old_update_id = self.last_update_id
                        self.last_update_id = max(update['update_id'] for update in updates)
                        logger.info(f"Updated last_update_id: {old_update_id} -> {self.last_update_id}")
                        
                        # Log each update for debugging
                        for i, update in enumerate(updates):
                            logger.debug(f"Update {i}: {json.dumps(update, indent=2)}")
                    
                    return updates
                elif data.get('ok') and not data.get('result'):
                    logger.debug("API returned ok=true but empty result")
                else:
                    logger.error(f"API returned ok=false: {data.get('description', 'unknown error')}")
            else:
                logger.error(f"Failed to get Telegram updates: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting Telegram updates: {e}")
        except Exception as e:
            logger.error(f"Error getting Telegram updates: {e}")
            logger.exception("Full exception details:")
        
        return []
    
    def _process_update(self, update: Dict):
        """Process a single update from Telegram"""
        logger.info(f"Processing update: {update}")
        
        # Handle both regular messages and channel posts
        message = None
        update_type = None
        
        if 'message' in update:
            message = update['message']
            update_type = 'message'
        elif 'channel_post' in update:
            message = update['channel_post']
            update_type = 'channel_post'
        else:
            logger.warning("Update has no 'message' or 'channel_post' field, skipping")
            return
        
        chat_id = str(message.get('chat', {}).get('id', ''))
        message_id = message.get('message_id', 'unknown')
        
        logger.debug(f"Update type: {update_type}")
        logger.debug(f"Message chat_id: '{chat_id}', configured chat_id: '{self.chat_id}'")
        logger.debug(f"Message ID: {message_id}")
        
        # Only process messages from our configured chat
        if chat_id != self.chat_id:
            logger.warning(f"Ignoring {update_type} from unauthorized chat_id: {chat_id} (expected: {self.chat_id})")
            return
        
        text = message.get('text', '').strip()
        if not text:
            logger.warning(f"{update_type} has no text content")
            return
        
        # Handle user info differently for channel posts vs regular messages
        if update_type == 'channel_post':
            # Channel posts don't have a 'from' field, use sender_chat or chat info
            sender_chat = message.get('sender_chat', {})
            username = sender_chat.get('title', message.get('chat', {}).get('title', 'Channel'))
            user_id = sender_chat.get('id', message.get('chat', {}).get('id', 'unknown'))
        else:
            # Regular message from a user
            user = message.get('from', {})
            username = user.get('username', user.get('first_name', 'Unknown'))
            user_id = user.get('id', 'unknown')
        
        logger.info(f"Received {update_type} from {username} (ID: {user_id}): '{text}'")
        
        # Handle commands (starting with /)
        if text.startswith('/'):
            logger.info(f"Processing command: {text.split()[0]}")
            self._handle_command(text, message)
        else:
            # Check if message is a plain number (IOB shortcut)
            iob_match = self._is_iob_number(text)
            if iob_match:
                logger.info(f"Processing IOB shortcut: {text}")
                self._handle_iob_shortcut(iob_match, message)
            else:
                # Handle regular messages
                logger.info(f"Processing regular message: {text[:50]}...")
                if self.message_handler:
                    try:
                        self.message_handler(text, message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
                        self._send_message(f"Error processing message: {e}")
                else:
                    logger.debug("No general message handler registered")
    
    def _handle_command(self, text: str, message: Dict):
        """Handle a command message"""
        parts = text.split()
        command = parts[0][1:].lower()  # Remove / prefix
        args = parts[1:] if len(parts) > 1 else []
        
        if command in self.command_handlers:
            try:
                result = self.command_handlers[command](args, message)
                if result:
                    # Send the command response
                    success = self._send_message(result)
                    if success:
                        logger.info(f"Successfully handled command /{command} and sent response")
                    else:
                        logger.error(f"Command /{command} executed but failed to send response")
                else:
                    # Command executed but returned no response - send confirmation
                    confirmation = f"Command /{command} executed successfully"
                    self._send_message(confirmation)
                    logger.info(f"Successfully handled command /{command} (no response returned)")
            except Exception as e:
                logger.error(f"Error handling command /{command}: {e}")
                error_response = f"Error executing command /{command}: {e}"
                self._send_message(error_response)
        else:
            # Unknown command
            available_commands = list(self.command_handlers.keys())
            if available_commands:
                commands_text = ', '.join(f"/{cmd}" for cmd in available_commands)
                response = f"Unknown command: /{command}\n\nAvailable commands: {commands_text}"
            else:
                response = f"Unknown command: /{command}\n\nNo commands are currently registered."
            
            self._send_message(response)
    
    def _is_iob_number(self, text: str) -> Optional[float]:
        """Check if text is a plain number (IOB shortcut). Supports both comma and dot as decimal separator."""
        # Remove any whitespace
        text = text.strip()
        
        # Pattern matches: digits optionally followed by decimal separator and more digits
        # Or just digits followed by decimal separator
        pattern = r'^(\d+[.,]\d*|\d*[.,]\d+|\d+)$'
        match = re.match(pattern, text)
        
        if match:
            try:
                # Replace comma with dot for float conversion
                number_str = match.group(1).replace(',', '.')
                value = float(number_str)
                
                # Reasonable range check for IOB (0 to 20 units)
                if 0.0 <= value <= 20.0:
                    return value
            except ValueError:
                pass
        
        return None
    
    def _handle_iob_shortcut(self, iob_value: float, message: Dict):
        """Handle IOB shortcut - treat plain number as IOB override"""
        try:
            # Get the command bridge to access the IOB handler
            # This assumes the TelegramCommandBridge is available
            # We need to find a way to call the IOB handler with the parsed value
            
            # For now, we'll construct a fake command and process it
            fake_command = f"/iob {iob_value} telegram-shortcut"
            self._handle_command(fake_command, message)
            
        except Exception as e:
            logger.error(f"Error handling IOB shortcut: {e}")
            self._send_message(f"Error setting IOB: {e}")


class TelegramCommandBridge:
    """Bridges Telegram commands to shell commands"""
    
    def __init__(self, telegram_notifier: TelegramNotifier, user_input_handler, db, settings: Settings):
        self.telegram = telegram_notifier
        self.user_input = user_input_handler
        self.db = db
        self.settings = settings
        
        # Initialize command processor and formatter
        self.command_processor = CommandProcessor(db, settings)
        self.formatter = TelegramFormatter(settings)
        
        # Pass callbacks from user input handler to command processor
        if hasattr(user_input_handler, 'callbacks'):
            for event, callback in user_input_handler.callbacks.items():
                self.command_processor.register_callback(event, callback)
        
        # Register command handlers
        self._register_commands()
        
        # Start message polling if Telegram is enabled
        if self.telegram.enabled:
            self.telegram.start_message_polling()
    
    def _register_commands(self):
        """Register all available commands"""
        commands = {
            'insulin': self._handle_insulin,
            'i': self._handle_insulin,
            'carbs': self._handle_carbs,
            'c': self._handle_carbs,
            'iob': self._handle_iob,
            'setiob': self._handle_iob,
            'status': self._handle_status,
            's': self._handle_status,
            'history': self._handle_history,
            'help': self._handle_help,
            'start': self._handle_start,
            'next': self._handle_next,
            'n': self._handle_next,
            # Diagnostic commands
            'debug': self._handle_debug,
            'test': self._handle_test,
            'ping': self._handle_ping,
            # Sensor reading command
            'reading': self._handle_reading,
            'r': self._handle_reading,
        }
        
        for command, handler in commands.items():
            self.telegram.register_command_handler(command, handler)
    
    def _handle_insulin(self, args: List[str], message: Dict) -> str:
        """Handle insulin command via Telegram"""
        if not args:
            return ("Log insulin dose\n"
                   "Usage: /insulin <units> [type] [notes]\n"
                   "       /i <units> [type] [notes]\n"
                   "Example: /insulin 2.5 rapid correction dose\n"
                   "Types: rapid (default), long, intermediate")
        
        try:
            units = float(args[0])
            insulin_type = args[1] if len(args) > 1 else 'rapid'
            notes = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = self.command_processor.execute_insulin(units, insulin_type, notes)
            return self.formatter.format_insulin_result(result)
            
        except (ValueError, IndexError):
            return "Invalid format. Usage: /insulin <units> [type] [notes]\nExample: /insulin 2.5 rapid"
        except Exception as e:
            return f"Error logging insulin: {e}"
    
    def _handle_carbs(self, args: List[str], message: Dict) -> str:
        """Handle carbs command via Telegram"""
        if not args:
            return ("Log carbohydrate intake\n"
                   "Usage: /carbs <grams> [type] [notes]\n"
                   "       /c <grams> [type] [notes]\n"
                   "Example: /carbs 45 fast orange juice\n"
                   "Types: fast, slow, mixed (default)")
        
        try:
            grams = float(args[0])
            carb_type = args[1] if len(args) > 1 else 'mixed'
            notes = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = self.command_processor.execute_carbs(grams, carb_type, notes)
            return self.formatter.format_carbs_result(result)
            
        except (ValueError, IndexError):
            return "Invalid format. Usage: /carbs <grams> [type] [notes]\nExample: /carbs 30 fast"
        except Exception as e:
            return f"Error logging carbs: {e}"
    
    def _handle_iob(self, args: List[str], message: Dict) -> str:
        """Handle IOB override command via Telegram"""
        if not args:
            return ("Set current IOB from pump/Omnipod\n"
                   "Usage: /iob <units> [source] [notes]\n"
                   "       /setiob <units> [source] [notes]\n"
                   "Example: /iob 0.2 omnipod\n"
                   "Sources: omnipod, pump, manual (default)")
        
        try:
            iob_value = float(args[0])
            source = args[1] if len(args) > 1 else 'manual'
            notes = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = self.command_processor.execute_iob_override(iob_value, source, notes)
            return self.formatter.format_iob_override_result(result)
            
        except (ValueError, IndexError):
            return "Invalid format. Usage: /iob <units> [source] [notes]\nExample: /iob 0.2 omnipod"
        except Exception as e:
            return f"Error setting IOB override: {e}"
    
    def _handle_status(self, args: List[str], message: Dict) -> str:
        """Handle status command via Telegram"""
        try:
            result = self.command_processor.execute_status()
            return self.formatter.format_status_result(result)
        except Exception as e:
            return f"Error getting status: {e}"
    
    def _handle_history(self, args: List[str], message: Dict) -> str:
        """Handle history command via Telegram"""
        try:
            hours = 6
            if args:
                try:
                    hours = int(args[0])
                except ValueError:
                    hours = 6
            
            result = self.command_processor.execute_history(hours)
            return self.formatter.format_history_result(result)
            
        except Exception as e:
            return f"Error getting history: {e}"
    
    def _handle_next(self, args: List[str], message: Dict) -> str:
        """Handle next reading command via Telegram"""
        try:
            result = self.command_processor.execute_next_reading()
            if result.success:
                return self.formatter.format_next_reading_result(result)
            else:
                return ("Next sensor reading information\n"
                       "This feature requires integration with the sensor client\n"
                       "Use the terminal interface for real-time sensor information")
        except Exception as e:
            return f"Error getting next reading time: {e}"
    
    
    def _handle_reading(self, args: List[str], message: Dict) -> str:
        """Handle reading command - show latest sensor reading and recommendations"""
        try:
            result = self.command_processor.execute_reading()
            return self.formatter.format_reading_result(result)
        except Exception as e:
            return f"Error getting latest reading: {e}"
    
    
    def _handle_help(self, args: List[str], message: Dict) -> str:
        """Handle help command via Telegram"""
        return self.formatter.format_help()
    
    def _handle_start(self, args: List[str], message: Dict) -> str:
        """Handle start command (standard Telegram bot command)"""
        return self.formatter.format_start()
    
    def _handle_debug(self, args: List[str], message: Dict) -> str:
        """Handle debug command - show diagnostic information"""
        try:
            # Prepare telegram config data
            telegram_config = {
                'enabled': self.telegram.enabled,
                'api_url': self.telegram.api_url,
                'chat_id': self.telegram.chat_id,
                'running': self.telegram.running,
                'last_update_id': self.telegram.last_update_id,
                'command_count': len(self.telegram.command_handlers)
            }
            
            result = self.command_processor.execute_debug(telegram_config, message)
            return self.formatter.format_debug_result(result)
            
        except Exception as e:
            return f"Error getting debug information: {e}"
    
    def _handle_test(self, args: List[str], message: Dict) -> str:
        """Handle test command - test various functionality"""
        try:
            result = self.command_processor.execute_test()
            return self.formatter.format_test_result(result)
        except Exception as e:
            return f"Error running system tests: {e}"
    
    def _handle_ping(self, args: List[str], message: Dict) -> str:
        """Handle ping command - simple connectivity test"""
        return self.formatter.format_ping()
    
    def stop(self):
        """Stop the Telegram command bridge"""
        if self.telegram.enabled:
            self.telegram.stop_message_polling()