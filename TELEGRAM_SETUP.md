# Telegram Bot Setup for Glucose Monitor

The Telegram bot now supports reading messages and executing shell commands through chat messages.

## Features

### Message Reading
- The bot polls for new messages from your configured Telegram chat or channel
- Only processes messages from the authorized chat/channel ID
- Supports both regular private/group messages and channel posts
- Supports both commands (starting with `/`) and regular messages

### Available Commands

#### Insulin Logging
- `/insulin <units> [type] [notes]` - Log insulin dose
- `/i <units> [type] [notes]` - Short form
- Types: `rapid` (default), `long`, `intermediate`
- Example: `/insulin 2.5 rapid correction dose`

#### Carbohydrate Logging  
- `/carbs <grams> [type] [notes]` - Log carb intake
- `/c <grams> [type] [notes]` - Short form
- Types: `fast`, `slow`, `mixed` (default)
- Example: `/carbs 45 fast orange juice`

#### IOB Override
- `/iob <units> [source] [notes]` - Set IOB from pump/Omnipod
- `/setiob <units> [source] [notes]` - Same as iob
- Sources: `omnipod`, `pump`, `manual` (default)
- Example: `/iob 0.2 omnipod`

#### Information Commands
- `/reading` or `/r` - Latest sensor reading + recommendations
- `/status` or `/s` - Show current IOB/COB
- `/history [hours]` - Show recent entries (default: 6 hours)
- `/next` or `/n` - Time until next sensor reading
- `/help` - Show all commands
- `/start` - Welcome message

## Configuration

### Environment Variables
Make sure you have these in your `.env` file:

```env
# Required for Telegram functionality
TELEGRAM_BOT_URL=https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage
TELEGRAM_CHAT_ID=<YOUR_CHAT_ID>

# Standard Dexcom credentials
DEXCOM_USERNAME=your_username
DEXCOM_PASSWORD=your_password
```

### Getting Bot Token and Chat ID

1. **Create a Bot:**
   - Message @BotFather on Telegram
   - Use `/newbot` command
   - Follow the prompts to create your bot
   - Save the bot token

2. **Get Chat ID:**
   
   **For Private Chats:**
   - Start a chat with your bot
   - Send any message to the bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Look for `"chat":{"id":...}` in the response
   
   **For Channels:**
   - Add your bot as an admin to the channel
   - Post a message in the channel (or forward a message to the channel)
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Look for `"channel_post":{"chat":{"id":...}}` in the response
   - Channel IDs are usually negative numbers (e.g., -1002909682479)

3. **Set up URL:**
   - Your bot URL should be: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage`

## Usage

### Starting the System
When you run the glucose monitor, it will automatically:
1. Initialize the Telegram bot with message polling
2. Register all shell commands as Telegram commands
3. Start listening for messages in your configured chat

### Example Commands
```
/start
→ 🩸 Glucose Monitor Telegram Bot
  Welcome! This bot helps you monitor glucose and log treatments.

/r
→ 🩸 Latest Sensor Reading
  ==============================
  
  📊 Glucose: 145 mg/dL
  🕐 Time: 15:42:30 (2 minutes ago)
  📈 Trend: Rising ⬆️
  📉 Rate: 1.2 mg/dL/min
  
  💊 Active Factors
     💉 IOB: 1.8u
     🍎 COB: 25.0g
  
  🔮 Prediction (15min): 158 mg/dL
     Confidence: Medium
  
  💡 Current Recommendations
  📋 General: Monitor rising trend closely
  ⚠️ Insulin: Consider small correction if trend continues
     Suggested: 0.5 units

/i 2.5 rapid
→ ✅ Logged 2.5 units of rapid insulin
  ⏰ Duration: 180 minutes

/status
→ 📊 Current Status
  ========================================
  💉 Active Insulin (IOB): 2.1 units
     • 2.5u rapid (15min ago)
  🍎 Active Carbs (COB): 30.0g
     • 30.0g fast (5min ago)
```

### Error Handling
- Invalid command formats return usage instructions
- Database errors are caught and reported
- Unknown commands show available command list

## Security

- Only processes messages from your configured `TELEGRAM_CHAT_ID`
- All database operations use the same validation as terminal commands
- Bot token should be kept secure (don't share publicly)

## Testing

Run the test script to verify functionality:
```bash
python test_telegram_commands.py
```

This will:
1. Initialize all components
2. Test the Telegram bridge setup
3. Show available commands
4. Allow you to test with real messages (if configured)

## Troubleshooting

### Bot Not Responding
- Check bot token and chat ID are correct
- Verify bot is not muted/blocked
- Check logs for connection errors

### Commands Not Working
- Ensure commands start with `/`
- Check command format matches examples
- Verify database connectivity

### Message Polling Issues
- Bot polls every 1 second for new messages
- Long polling timeout is 10 seconds
- Errors trigger 5-second retry delay

## Architecture

The system adds these components:

1. **Message Polling:** `TelegramNotifier` polls Telegram API for updates
2. **Command Routing:** Maps `/command` to handler functions
3. **Command Bridge:** `TelegramCommandBridge` translates Telegram commands to shell commands
4. **Database Integration:** Uses same database operations as terminal interface

All Telegram commands execute the same logic as their terminal counterparts, ensuring consistent behavior across interfaces.