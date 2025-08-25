import pytest
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.notifications.telegram_bot import TelegramNotifier
from src.config.settings import Settings


class TestStatusMessages:
    
    def setup_method(self):
        # Create a temporary environment for testing
        self.temp_env = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
        self.temp_env.write("""DEXCOM_USERNAME=test_user
DEXCOM_PASSWORD=test_pass
TELEGRAM_BOT_URL=https://api.telegram.org/bot123456:TEST/sendMessage
TELEGRAM_CHAT_ID=123456789
TELEGRAM_STATUS_INTERVAL_MINUTES=30
TELEGRAM_STATUS_START_HOUR=7
TELEGRAM_STATUS_END_HOUR=22
""")
        self.temp_env.close()
        
        # Create settings instance
        self.settings = Settings(self.temp_env.name)
        
        # Mock the requests.post method to avoid actual API calls
        self.mock_requests_patcher = patch('src.notifications.telegram_bot.requests.post')
        self.mock_requests = self.mock_requests_patcher.start()
        
        # Configure the mock to return a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'ok': True}
        self.mock_requests.return_value = mock_response
        
        # Create TelegramNotifier instance
        self.telegram_notifier = TelegramNotifier(self.settings)
    
    def teardown_method(self):
        # Clean up temporary environment file
        if os.path.exists(self.temp_env.name):
            os.unlink(self.temp_env.name)
        
        # Stop the mock
        self.mock_requests_patcher.stop()
    
    def test_telegram_notifier_initialization(self):
        """Test that TelegramNotifier is initialized with correct settings"""
        assert self.telegram_notifier.enabled is True
        assert self.telegram_notifier.settings.telegram_status_interval_minutes == 30
        assert self.telegram_notifier.settings.telegram_status_start_hour == 7
        assert self.telegram_notifier.settings.telegram_status_end_hour == 22
        assert self.telegram_notifier.last_message_time is None
    
    @patch('src.notifications.telegram_bot.datetime')
    def test_should_send_status_message_when_disabled(self, mock_datetime):
        """Test that status messages are not sent when interval is 0"""
        # Create settings with disabled status messages
        temp_env_disabled = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
        temp_env_disabled.write("""DEXCOM_USERNAME=test_user
DEXCOM_PASSWORD=test_pass
TELEGRAM_BOT_URL=https://api.telegram.org/bot123456:TEST/sendMessage
TELEGRAM_CHAT_ID=123456789
TELEGRAM_STATUS_INTERVAL_MINUTES=0
TELEGRAM_STATUS_START_HOUR=7
TELEGRAM_STATUS_END_HOUR=22
""")
        temp_env_disabled.close()
        
        try:
            # Mock current time to be within status hours
            mock_now = Mock()
            mock_now.hour = 12
            mock_datetime.now.return_value = mock_now
            
            # Save and clear existing environment variables before loading new ones
            import os
            saved_env = {}
            for key in ['TELEGRAM_STATUS_INTERVAL_MINUTES', 'TELEGRAM_STATUS_START_HOUR', 'TELEGRAM_STATUS_END_HOUR']:
                if key in os.environ:
                    saved_env[key] = os.environ[key]
                    del os.environ[key]
                    
            settings_disabled = Settings(temp_env_disabled.name)
            
            # Use the same mocked requests from setup_method
            with patch('src.notifications.telegram_bot.requests.post', self.mock_requests):
                telegram_disabled = TelegramNotifier(settings_disabled)
                assert telegram_disabled.should_send_status_message() is False
                
            # Restore environment variables
            for key, value in saved_env.items():
                os.environ[key] = value
        finally:
            os.unlink(temp_env_disabled.name)
    
    @patch('src.notifications.telegram_bot.datetime')
    def test_is_within_status_hours_normal_range(self, mock_datetime):
        """Test status hour checking for normal range (7:00 to 22:00)"""
        # Test within range (12:00)
        mock_now = Mock()
        mock_now.hour = 12
        mock_datetime.now.return_value = mock_now
        
        assert self.telegram_notifier._is_within_status_hours() is True
        
        # Test outside range (23:00)
        mock_now.hour = 23
        assert self.telegram_notifier._is_within_status_hours() is False
        
        # Test outside range (6:00)
        mock_now.hour = 6
        assert self.telegram_notifier._is_within_status_hours() is False
        
        # Test at boundaries
        mock_now.hour = 7
        assert self.telegram_notifier._is_within_status_hours() is True
        
        mock_now.hour = 22
        assert self.telegram_notifier._is_within_status_hours() is True
    
    @patch('src.notifications.telegram_bot.datetime')
    def test_is_within_status_hours_crossing_midnight(self, mock_datetime):
        """Test status hour checking when range crosses midnight (22:00 to 7:00)"""
        # Create settings with midnight-crossing hours
        temp_env_midnight = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
        temp_env_midnight.write("""DEXCOM_USERNAME=test_user
DEXCOM_PASSWORD=test_pass
TELEGRAM_BOT_URL=https://api.telegram.org/bot123456:TEST/sendMessage
TELEGRAM_CHAT_ID=123456789
TELEGRAM_STATUS_INTERVAL_MINUTES=30
TELEGRAM_STATUS_START_HOUR=22
TELEGRAM_STATUS_END_HOUR=7
""")
        temp_env_midnight.close()
        
        try:
            # Save and clear existing environment variables before loading new ones
            import os
            saved_env = {}
            for key in ['TELEGRAM_STATUS_INTERVAL_MINUTES', 'TELEGRAM_STATUS_START_HOUR', 'TELEGRAM_STATUS_END_HOUR']:
                if key in os.environ:
                    saved_env[key] = os.environ[key]
                    del os.environ[key]
                    
            settings_midnight = Settings(temp_env_midnight.name)
            
            # Use the same mocked requests from setup_method
            with patch('src.notifications.telegram_bot.requests.post', self.mock_requests):
                telegram_midnight = TelegramNotifier(settings_midnight)
                
                mock_now = Mock()
                mock_datetime.now.return_value = mock_now
                
                # Test within range (23:00)
                mock_now.hour = 23
                assert telegram_midnight._is_within_status_hours() is True
                
                # Test within range (2:00)
                mock_now.hour = 2
                assert telegram_midnight._is_within_status_hours() is True
                
                # Test outside range (12:00)
                mock_now.hour = 12
                assert telegram_midnight._is_within_status_hours() is False
                
                # Test at boundaries
                mock_now.hour = 22
                assert telegram_midnight._is_within_status_hours() is True
                
                mock_now.hour = 7
                assert telegram_midnight._is_within_status_hours() is True
                
            # Restore environment variables
            for key, value in saved_env.items():
                os.environ[key] = value
        finally:
            os.unlink(temp_env_midnight.name)
    
    @patch('src.notifications.telegram_bot.datetime')
    def test_should_send_status_message_timing(self, mock_datetime):
        """Test timing logic for sending status messages"""
        base_time = datetime(2023, 8, 25, 12, 0, 0)
        
        # Mock current time to be within status hours
        mock_now = Mock()
        mock_now.hour = 12
        mock_datetime.now.return_value = mock_now
        
        # Reset state to ensure clean test
        self.telegram_notifier.last_message_time = None
        
        # Test: no previous message - should send
        assert self.telegram_notifier.should_send_status_message() is True
        
        # Test: previous message 10 minutes ago - should not send (interval is 30 min)
        self.telegram_notifier.last_message_time = base_time - timedelta(minutes=10)
        mock_datetime.now.return_value = base_time
        assert self.telegram_notifier.should_send_status_message() is False
        
        # Test: previous message 35 minutes ago - should send
        self.telegram_notifier.last_message_time = base_time - timedelta(minutes=35)
        mock_datetime.now.return_value = base_time
        assert self.telegram_notifier.should_send_status_message() is True
        
        # Test: previous message exactly 30 minutes ago - should send
        self.telegram_notifier.last_message_time = base_time - timedelta(minutes=30)
        mock_datetime.now.return_value = base_time
        assert self.telegram_notifier.should_send_status_message() is True
    
    @patch('src.notifications.telegram_bot.datetime')
    def test_should_send_status_message_outside_hours(self, mock_datetime):
        """Test that status messages are not sent outside configured hours"""
        # Mock current time to be outside status hours
        mock_now = Mock()
        mock_now.hour = 23  # Outside 7-22 range
        mock_datetime.now.return_value = mock_now
        
        # Reset state to ensure clean test
        self.telegram_notifier.last_message_time = None
        
        # Even with no previous message, should not send outside hours
        assert self.telegram_notifier.should_send_status_message() is False
        
        # Even with old previous message, should not send outside hours
        self.telegram_notifier.last_message_time = datetime.now() - timedelta(hours=2)
        assert self.telegram_notifier.should_send_status_message() is False
    
    def test_send_status_update_message_format(self):
        """Test the format of status update messages"""
        # Send a status update
        success = self.telegram_notifier.send_status_update(
            glucose_value=144.0,
            trend='fast_up',
            prediction={'predicted_value': 164.8, 'confidence': 'medium'}
        )
        
        assert success is True
        
        # Verify that requests.post was called
        assert self.mock_requests.called
        
        # Get the call arguments
        call_args = self.mock_requests.call_args
        payload = call_args[1]['json']
        
        # Check message structure
        assert payload['chat_id'] == '123456789'
        assert payload['parse_mode'] == 'Markdown'
        
        message = payload['text']
        assert 'Status Update' in message
        assert '144.0 mg/dL' in message
        assert '⬆️⬆️' in message  # fast_up trend emoji
        assert 'Rising Rapidly' in message
        assert '164.8 mg/dL' in message
        assert 'Medium' in message
        assert 'routine status update - no action needed' in message.lower()
    
    def test_send_status_update_without_prediction(self):
        """Test status update without prediction data"""
        success = self.telegram_notifier.send_status_update(
            glucose_value=120.0,
            trend='no_change'
        )
        
        assert success is True
        
        # Get the message content
        call_args = self.mock_requests.call_args
        payload = call_args[1]['json']
        message = payload['text']
        
        assert 'Status Update' in message
        assert '120.0 mg/dL' in message
        assert '➡️' in message  # no_change trend emoji
        assert 'Stable' in message
        assert 'routine status update - no action needed' in message.lower()
        # Should not contain prediction information
        assert 'Predicted' not in message
    
    def test_last_message_time_tracking(self):
        """Test that last message time is properly tracked"""
        assert self.telegram_notifier.last_message_time is None
        
        # Send a message
        self.telegram_notifier.send_status_update(glucose_value=120.0, trend='no_change')
        
        # Check that last message time was set
        assert self.telegram_notifier.last_message_time is not None
        assert isinstance(self.telegram_notifier.last_message_time, datetime)
        
        # Check that time is recent (within last few seconds)
        time_diff = datetime.now() - self.telegram_notifier.last_message_time
        assert time_diff.total_seconds() < 5
    
    def test_telegram_disabled_behavior(self):
        """Test behavior when Telegram is disabled"""
        # Create settings without Telegram configuration
        temp_env_disabled = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
        temp_env_disabled.write("""DEXCOM_USERNAME=test_user
DEXCOM_PASSWORD=test_pass
TELEGRAM_BOT_URL=
TELEGRAM_CHAT_ID=
""")
        temp_env_disabled.close()
        
        try:
            # Save and clear existing environment variables before loading new ones
            import os
            saved_env = {}
            for key in ['TELEGRAM_BOT_URL', 'TELEGRAM_CHAT_ID']:
                if key in os.environ:
                    saved_env[key] = os.environ[key]
                    del os.environ[key]
                    
            settings_disabled = Settings(temp_env_disabled.name)
            
            # Don't need to mock requests since Telegram should be disabled
            telegram_disabled = TelegramNotifier(settings_disabled)
            
            assert telegram_disabled.enabled is False
            assert telegram_disabled.should_send_status_message() is False
            
            # Sending status update should return False but not crash
            success = telegram_disabled.send_status_update(120.0, 'no_change')
            assert success is False
            
            # Restore environment variables
            for key, value in saved_env.items():
                os.environ[key] = value
        finally:
            os.unlink(temp_env_disabled.name)
    
    def test_api_error_handling(self):
        """Test handling of API errors"""
        # Configure mock to return an error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        self.mock_requests.return_value = mock_response
        
        # Attempt to send status update
        success = self.telegram_notifier.send_status_update(glucose_value=120.0, trend='no_change')
        
        # Should return False on API error
        assert success is False
        
        # Last message time should not be updated on failure
        assert self.telegram_notifier.last_message_time is None