#!/usr/bin/env python3
"""
Debug script for Telegram bot functionality
Helps diagnose message reading issues
"""
import sys
import os
import json
import logging
import time
sys.path.insert(0, os.path.abspath('.'))

from src.config import Settings
from src.database import GlucoseDatabase
from src.notifications import TelegramNotifier, TelegramCommandBridge
from src.terminal import UserInputHandler

def setup_debug_logging():
    """Setup detailed logging for debugging"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('telegram_debug.log')
        ]
    )

def test_telegram_config():
    """Test Telegram configuration"""
    print("🔧 Testing Telegram Configuration")
    print("=" * 50)
    
    try:
        settings = Settings()
        
        print(f"Bot URL: {settings.telegram_bot_url}")
        print(f"Chat ID: {settings.telegram_chat_id}")
        print(f"Enabled: {bool(settings.telegram_bot_url and settings.telegram_chat_id)}")
        
        if not settings.telegram_bot_url:
            print("❌ TELEGRAM_BOT_URL is not set")
            return False
            
        if not settings.telegram_chat_id:
            print("❌ TELEGRAM_CHAT_ID is not set")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
        return False

def test_bot_info(telegram_notifier):
    """Test bot information retrieval"""
    print("\n🤖 Testing Bot Information")
    print("=" * 30)
    
    bot_info = telegram_notifier.get_bot_info()
    print(f"Bot info response: {json.dumps(bot_info, indent=2)}")
    
    if "error" not in bot_info and bot_info.get("ok"):
        result = bot_info.get("result", {})
        print(f"✅ Bot username: @{result.get('username', 'unknown')}")
        print(f"✅ Bot first name: {result.get('first_name', 'unknown')}")
        print(f"✅ Bot ID: {result.get('id', 'unknown')}")
        return True
    else:
        print(f"❌ Bot info failed: {bot_info}")
        return False

def test_webhook_info(telegram_notifier):
    """Test webhook information"""
    print("\n🔗 Testing Webhook Information")
    print("=" * 30)
    
    webhook_info = telegram_notifier.get_webhook_info()
    print(f"Webhook info: {json.dumps(webhook_info, indent=2)}")
    
    if "error" not in webhook_info and webhook_info.get("ok"):
        result = webhook_info.get("result", {})
        webhook_url = result.get("url", "")
        
        if webhook_url:
            print(f"⚠️  Webhook is set to: {webhook_url}")
            print("   This might interfere with polling.")
            
            response = input("   Clear webhook? (y/n): ")
            if response.lower() == 'y':
                clear_result = telegram_notifier.clear_webhook()
                if clear_result.get("ok"):
                    print("✅ Webhook cleared successfully")
                else:
                    print(f"❌ Failed to clear webhook: {clear_result}")
        else:
            print("✅ No webhook configured - polling should work")
        
        return True
    else:
        print(f"❌ Webhook info failed: {webhook_info}")
        return False

def test_manual_updates(telegram_notifier):
    """Manually test getting updates"""
    print("\n📨 Testing Manual Update Retrieval")
    print("=" * 40)
    
    print("Attempting to get updates manually...")
    
    try:
        # Get a few updates manually
        updates = telegram_notifier._get_updates()
        print(f"Received {len(updates)} updates")
        
        if updates:
            for i, update in enumerate(updates):
                print(f"\nUpdate {i+1}:")
                print(json.dumps(update, indent=2))
        else:
            print("No updates received")
            print("\n💡 Try sending a message to your bot now, then check again")
        
        return len(updates) > 0
        
    except Exception as e:
        print(f"❌ Error getting updates: {e}")
        return False

def interactive_debug():
    """Run interactive debugging session"""
    print("\n🎮 Interactive Debug Mode")
    print("=" * 30)
    
    setup_debug_logging()
    
    try:
        # Initialize components
        settings = Settings()
        db = GlucoseDatabase(":memory:")
        telegram_notifier = TelegramNotifier(settings)
        user_input_handler = UserInputHandler(db, settings)
        
        if not telegram_notifier.enabled:
            print("❌ Telegram is not enabled - check your configuration")
            return
        
        print("✅ Components initialized")
        
        # Start polling
        telegram_notifier.start_message_polling()
        print("✅ Started message polling")
        
        print("\n📱 Send messages to your bot now...")
        print("   Available test commands:")
        print("   - Any text message")
        print("   - /ping")  
        print("   - /debug")
        print("   - /test")
        
        try:
            while True:
                command = input("\nPress Enter to check for updates, 'q' to quit: ")
                if command.lower() == 'q':
                    break
                
                # Manual check
                updates = telegram_notifier._get_updates()
                if updates:
                    print(f"Found {len(updates)} new updates!")
                    for update in updates:
                        telegram_notifier._process_update(update)
                else:
                    print("No new updates")
                    
        except KeyboardInterrupt:
            print("\nStopping...")
        
        telegram_notifier.stop_message_polling()
        print("✅ Stopped polling")
        
    except Exception as e:
        print(f"❌ Error in interactive mode: {e}")
        logging.exception("Full error details:")

def main():
    """Main debugging function"""
    print("🔍 Telegram Bot Debug Tool")
    print("=" * 40)
    
    # Test configuration
    if not test_telegram_config():
        print("\n💡 Fix your .env file with proper TELEGRAM_BOT_URL and TELEGRAM_CHAT_ID")
        return
    
    # Initialize notifier for testing
    settings = Settings()
    telegram_notifier = TelegramNotifier(settings)
    
    if not telegram_notifier.enabled:
        print("❌ Telegram notifier is not enabled")
        return
    
    # Run tests
    tests_passed = 0
    total_tests = 0
    
    # Test bot info
    total_tests += 1
    if test_bot_info(telegram_notifier):
        tests_passed += 1
    
    # Test webhook info  
    total_tests += 1
    if test_webhook_info(telegram_notifier):
        tests_passed += 1
    
    # Test manual updates
    total_tests += 1  
    if test_manual_updates(telegram_notifier):
        tests_passed += 1
    
    print(f"\n📊 Test Results: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed!")
        
        # Offer interactive mode
        response = input("\nRun interactive debug mode? (y/n): ")
        if response.lower() == 'y':
            interactive_debug()
    else:
        print("❌ Some tests failed - check the output above")
        
        # Still offer interactive mode for debugging
        response = input("\nTry interactive debug mode anyway? (y/n): ")
        if response.lower() == 'y':
            interactive_debug()

if __name__ == "__main__":
    main()