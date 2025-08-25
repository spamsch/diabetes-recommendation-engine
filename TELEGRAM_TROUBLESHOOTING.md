# Telegram Bot Troubleshooting Guide

This guide helps diagnose issues with Telegram message reading functionality.

## Quick Diagnosis

### 1. Run the Debug Tool
```bash
python debug_telegram.py
```

This will:
- ✅ Check your configuration
- ✅ Test bot connectivity
- ✅ Check for webhook conflicts
- ✅ Test manual message retrieval
- 🎮 Offer interactive debugging mode

### 2. Check Logs
Set logging to DEBUG level and check for:
```bash
# Enable debug logging by setting in your script:
import logging
logging.basicConfig(level=logging.DEBUG)

# Or check the telegram_debug.log file after running debug tool
tail -f telegram_debug.log
```

## Common Issues & Solutions

### Issue 1: Bot Not Responding to Messages

**Symptoms:**
- Messages sent to bot are ignored
- No debug logs showing message receipt
- `/ping` command doesn't respond

**Diagnosis:**
```python
# Run debug tool and look for:
python debug_telegram.py

# Check these in the output:
- Bot info retrieval: Should show bot username/ID
- Webhook status: Should be empty or show error if set
- Manual updates: Should show your sent messages
```

**Solutions:**

1. **Check Bot Token:**
   ```bash
   # Verify your .env file has correct format:
   TELEGRAM_BOT_URL=https://api.telegram.org/bot<YOUR_ACTUAL_TOKEN>/sendMessage
   ```

2. **Check Chat ID:**
   ```bash
   # Get your chat ID by messaging the bot, then visiting:
   # https://api.telegram.org/bot<TOKEN>/getUpdates
   # Look for "chat":{"id":<NUMBER>}
   TELEGRAM_CHAT_ID=<YOUR_ACTUAL_CHAT_ID>
   ```

3. **Clear Webhook (Common Issue):**
   - If you previously used webhooks, they interfere with polling
   - Run debug tool and choose 'y' when asked to clear webhook
   - Or manually visit: `https://api.telegram.org/bot<TOKEN>/setWebhook?url=`

### Issue 2: Wrong Chat ID

**Symptoms:**
- Bot works in direct messages but not groups/channels (or vice versa)
- Debug logs show "unauthorized chat_id" messages
- Messages are sent but never processed

**Diagnosis:**
```python
# Use /debug command in the chat to see:
# - Current message chat ID
# - Configured chat ID  
# - Chat type (private/group/supergroup/channel)
# - Update type (message vs channel_post)
```

**Solutions:**

1. **For Private Chats:**
   - Message @BotFather: `/mybots` → Select bot → Delete Bot
   - Recreate bot and start fresh conversation
   - Get chat ID from first message

2. **For Groups:**
   - Add bot to group
   - Make bot admin (required for message reading in some cases)
   - Send a message, then check `getUpdates` for the group chat ID
   - Group IDs are usually negative numbers

3. **For Channels:**
   - Add bot as admin to the channel with "Post Messages" permission
   - Post a message or command in the channel
   - Check `getUpdates` for `channel_post` with the channel ID
   - Channel IDs are large negative numbers (e.g., -1002909682479)
   - Make sure your `TELEGRAM_CHAT_ID` matches exactly

### Issue 3: Messages Arrive but Commands Don't Work

**Symptoms:**
- Debug logs show messages received
- But `/insulin`, `/carbs` commands return errors
- `/ping` works but other commands fail

**Diagnosis:**
```python
# Use these commands to test:
/ping          # Should respond immediately
/test          # Should show system status
/debug         # Should show configuration
/help          # Should list all commands
```

**Solutions:**

1. **Database Issues:**
   ```python
   # Check /test command output for database errors
   # Make sure database file is writable
   # Check file permissions
   ```

2. **Import Issues:**
   ```python
   # Check if all required modules load:
   python -c "from src.database import InsulinEntry, CarbEntry, IOBOverride"
   ```

### Issue 4: Intermittent Message Loss

**Symptoms:**
- Some messages work, others don't
- Polling stops and restarts
- Connection timeout errors

**Diagnosis:**
```python
# Enable debug logging and look for:
# - "Request error getting Telegram updates"
# - "Error polling Telegram messages" 
# - Frequent reconnection attempts
```

**Solutions:**

1. **Network Issues:**
   - Check internet connectivity stability
   - Consider increasing timeout values in code
   - Monitor for rate limiting (429 errors)

2. **Bot Token Issues:**
   - Regenerate bot token from @BotFather
   - Update .env file
   - Restart application

## Debug Commands Reference

Once your bot is working, use these commands for ongoing troubleshooting:

### `/ping`
Simple connectivity test - should respond immediately.

### `/debug`
Shows detailed diagnostic information:
- Bot configuration (API URL, chat ID)
- Message polling status
- Current message details (chat ID, user info)
- Registered commands count

### `/test`
Runs system tests:
- Database connectivity
- Settings loading  
- Message processing verification

### Example Debug Session

```
User: /debug
Bot: 🔧 Debug Information
     ==============================
     Bot enabled: True
     API URL: https://api.telegram.org/bot123456:ABC...
     Configured chat ID: 987654321
     Message polling: True

     📨 Current Message
     Message ID: 123
     Chat ID: 987654321
     Chat type: private
     User ID: 987654321
     Username: @yourname
     
     🤖 Bot State
     Last update ID: 123456789
     Registered commands: 16
     Commands: c, carbs, debug, help, history, ...

User: /test  
Bot: 🧪 System Tests
     ====================
     ✅ Database: Connected
        Active insulin entries: 0
     ✅ Settings: Loaded
        Poll interval: 5min
        Prediction window: 15min
     ✅ Message processing: Working
        This message processed successfully

User: /ping
Bot: 🏓 Pong! 14:23:45
     
     Bot is responsive and processing messages.
```

## Advanced Debugging

### Manual API Testing

Test your bot token directly:

```bash
# Get bot info
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Get updates
curl "https://api.telegram.org/bot<TOKEN>/getUpdates"

# Clear webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" -d "url="

# Send test message
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"<CHAT_ID>","text":"Test message"}'
```

### Log Analysis

Enable debug logging and look for these patterns:

```
# Good - Messages being received:
✅ Received message from username (ID: 123): '/ping'
Processing command: /ping

# Bad - Wrong chat ID:
Ignoring message from unauthorized chat_id: 555 (expected: 123)

# Bad - API errors:
Failed to get Telegram updates: 401
Response text: {"ok":false,"error_code":401,"description":"Unauthorized"}

# Bad - Network issues:
Request error getting Telegram updates: HTTPSConnectionPool
```

## When All Else Fails

1. **Delete and recreate the bot:**
   - Message @BotFather: `/mybots`
   - Delete current bot
   - Create new bot with `/newbot`
   - Update token in .env

2. **Check Telegram API status:**
   - Visit https://telegram.org
   - Check for service outages

3. **Test with minimal setup:**
   ```python
   # Create a simple test script with just:
   python debug_telegram.py
   # Use interactive mode to isolate the issue
   ```

4. **Enable maximum debugging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   # Run your application and send messages
   ```

The debugging tools should help identify exactly where the message reading is failing.