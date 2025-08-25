#!/usr/bin/env python3
"""
Test script for Telegram command functionality
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Check if running under pytest
RUNNING_IN_PYTEST = 'pytest' in sys.modules

from src.config import Settings
from src.database import GlucoseDatabase
from src.notifications import TelegramNotifier, TelegramCommandBridge
from src.terminal import UserInputHandler

def test_telegram_commands():
    """Test Telegram command functionality"""
    # Initialize components (these will use mock if no real credentials)
    settings = Settings()
    db = GlucoseDatabase(":memory:")  # Use in-memory database for testing
    
    # Initialize notifier (will be disabled if no credentials)
    telegram_notifier = TelegramNotifier(settings)
    
    # Initialize user input handler
    user_input_handler = UserInputHandler(db, settings)
    
    # Initialize Telegram command bridge
    telegram_bridge = TelegramCommandBridge(
        telegram_notifier, user_input_handler, db, settings
    )
    
    print("✅ Telegram command bridge initialized successfully")
    
    # Test that components are properly initialized
    assert telegram_bridge is not None, "Telegram bridge should be initialized"
    assert telegram_notifier is not None, "Telegram notifier should be initialized"
    assert user_input_handler is not None, "User input handler should be initialized"
    
    if telegram_notifier.enabled:
        print("✅ Telegram is enabled and configured")
        print("📱 The bot is now listening for messages in your configured chat")
        print("\nAvailable commands:")
        print("  /start - Get welcome message")
        print("  /help - Show all commands")
        print("  /i 2.5 - Log 2.5 units of insulin")
        print("  /c 30 - Log 30g of carbs")
        print("  /status - Show current IOB/COB")
        print("  /history - Show recent entries")
        print("\nSend messages to your Telegram bot to test!")
        
        # Keep the bridge running for testing (only when not in pytest)
        if not RUNNING_IN_PYTEST:
            try:
                input("\nPress Enter to stop the test...")
            except KeyboardInterrupt:
                pass
        else:
            print("(Interactive test skipped in pytest mode)")
    else:
        print("ℹ️  Telegram is not configured (missing TELEGRAM_BOT_URL or TELEGRAM_CHAT_ID)")
        print("   The bridge was created but won't process messages")
    
    # Cleanup
    telegram_bridge.stop()
    print("✅ Test completed successfully")

if __name__ == "__main__":
    print("🧪 Testing Telegram Command Bridge")
    print("=" * 40)
    
    try:
        test_telegram_commands()
        print("\n🎉 All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Tests failed: {e}")
        sys.exit(1)