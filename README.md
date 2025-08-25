# Glucose Monitoring System

A Python application for monitoring glucose levels from Dexcom sensors, providing intelligent analysis, predictions, and recommendations to help manage diabetes. This is a fully vibe coded app and will contain a lot of emojis and other nonsense. But it works for me and has been very helpful.

My use-case is to reduce mental load while handling the glucose levels for my child. I love that a Telegram bot is helping me making decisions.
My goal is to trust this software to alert me and give valid recommendations. I do not want to look at the Omnipod active insulin and the current
value of the Dexcom and think about a solution.

One next step could be to integrate an LLM. But not sure of that really makes sense.

## ⚠️ Important Medical Disclaimer

**This application is for monitoring and educational purposes only. It is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult with qualified healthcare providers before making any medical decisions or changes to diabetes management.**

- Never ignore symptoms even if readings appear normal
- Always have emergency glucose supplies available
- Seek immediate medical attention for severe symptoms
- Follow your healthcare provider's diabetes management plan

## Prerequisites

**Dexcom Follow Required**: This application requires Dexcom Follow to be enabled and configured. It uses the [pydexcom](https://pypi.org/project/pydexcom/) library to connect to Dexcom Share API, which requires:
- A Dexcom G6/G7 sensor system
- Dexcom Follow feature enabled in the Dexcom app
- Valid Dexcom Share credentials

## Features

### 🩸 Continuous Glucose Monitoring
- Real-time data collection from Dexcom sensors every 5 minutes
- Reliable data storage in SQLite database
- Automatic reconnection handling

### 📊 Intelligent Analysis
- **Trend Analysis**: Detects glucose trends with configurable thresholds (down, fast_down, very_fast_down, up, fast_up, very_fast_up, stable)
- **Pattern Recognition**: Identifies critical patterns and approaching thresholds
- **Prediction Engine**: Forecasts glucose levels 15 minutes ahead using multiple algorithms
- **IOB/COB Tracking**: Tracks Insulin on Board and Carbs on Board for accurate predictions

### 💊 Smart Recommendations
- **Insulin Recommendations**: Suggests insulin doses for high, stable glucose levels (considers IOB)
- **Carbohydrate Recommendations**: Recommends fast-acting carbs for low glucose situations
- **IOB Status Recommendations**: Suggests checking current active insulin for better prediction accuracy
- **Monitoring Recommendations**: Advises on increased monitoring frequency
- **Safety-First Approach**: Conservative recommendations with built-in safety checks

### 📱 Telegram Integration
- **Real-time Command Processing**: Full command support via Telegram bot
- **IOB Shortcuts**: Send plain numbers (e.g., "2.4" or "2,4") to set IOB quickly
- **Interactive Commands**: Log insulin, carbs, check status, get history
- **Formatted Notifications**: Rich messages with priority levels and safety notes

#### Available Telegram Commands
- `/status` or `/s` - Current glucose status and IOB/COB
- `/insulin <units> [type] [notes]` or `/i` - Log insulin dose
- `/carbs <grams> [type] [notes]` or `/c` - Log carbohydrate intake
- `/iob <units> [source] [notes]` or `/setiob` - Set current IOB override
- **Plain numbers** - Quick IOB entry (supports both dot and comma: `2.4` or `2,4`)
- `/history [hours]` - Show glucose history
- `/help` - Show available commands

### 📈 Visualization
- Real-time terminal display with trend arrows
- Color-coded glucose values (green/yellow/red based on thresholds)
- IOB/COB status display with impact calculations

### 🧪 Comprehensive Testing
- Mock client for testing recommendations
- Multiple realistic scenarios (approaching low values, post-meal spikes, exercise drops)
- Safety validation for all recommendation algorithms

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd dexcom-analyze
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure the application**
```bash
cp .env.example .env
# Edit .env with your Dexcom credentials and preferences
```

## Configuration

### Required Settings

Edit `.env` file with your information:

```bash
# Dexcom credentials (required)
DEXCOM_USERNAME=your_dexcom_username
DEXCOM_PASSWORD=your_dexcom_password
DEXCOM_OUS=false  # Set to true for non-US accounts

# Optional Telegram notifications
TELEGRAM_BOT_URL=https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage
TELEGRAM_CHAT_ID=your_chat_id
```

### Configuration Settings

| Setting | Description | Default | Notes |
|---------|-------------|---------|-------|
| **Core Settings** |
| `DEXCOM_USERNAME` | Dexcom Share username | *required* | Must have Follow enabled |
| `DEXCOM_PASSWORD` | Dexcom Share password | *required* | |
| `DEXCOM_OUS` | Outside US account | `false` | Set true for non-US |
| `POLL_INTERVAL_MINUTES` | How often to check for new readings | `5` | Dexcom updates every 5min |
| `ANALYSIS_WINDOW_SIZE` | Number of readings to analyze | `15` | 10-20 recommended |
| `PREDICTION_MINUTES_AHEAD` | Prediction timeframe | `15` | Minutes ahead to predict |
| `TREND_CALCULATION_POINTS` | Readings used for trend analysis | `3` | Recent readings for trends |
| **Glucose Thresholds (mg/dL)** |
| `LOW_GLUCOSE_THRESHOLD` | Low glucose alert threshold | `70` | |
| `HIGH_GLUCOSE_THRESHOLD` | High glucose alert threshold | `180` | |
| `CRITICAL_LOW_THRESHOLD` | Critical low threshold | `55` | Emergency level |
| `CRITICAL_HIGH_THRESHOLD` | Critical high threshold | `300` | Emergency level |
| `TARGET_GLUCOSE` | Target glucose for calculations | `120` | Used in insulin recommendations |
| **Trend Classification (mg/dL per minute)** |
| `TREND_DOWN_THRESHOLD` | Minimum rate for "down" trend | `0.5` | Configurable sensitivity |
| `TREND_FAST_DOWN_THRESHOLD` | Rate for "fast_down" trend | `2.0` | |
| `TREND_VERY_FAST_DOWN_THRESHOLD` | Rate for "very_fast_down" trend | `4.0` | |
| `TREND_UP_THRESHOLD` | Minimum rate for "up" trend | `0.5` | |
| `TREND_FAST_UP_THRESHOLD` | Rate for "fast_up" trend | `2.0` | |
| `TREND_VERY_FAST_UP_THRESHOLD` | Rate for "very_fast_up" trend | `4.0` | |
| **Insulin Settings** |
| `ENABLE_INSULIN_RECOMMENDATIONS` | Enable insulin suggestions | `true` | Safety feature |
| `INSULIN_EFFECTIVENESS` | Glucose drop per insulin unit | `40.0` | mg/dL per unit |
| `INSULIN_UNIT_RATIO` | Insulin calculation ratio | `0.2` | Dosing multiplier |
| `INSULIN_DURATION_RAPID` | Rapid insulin duration | `180` | Minutes active |
| `INSULIN_DURATION_LONG` | Long insulin duration | `720` | Minutes active |
| **Carbohydrate Settings** |
| `ENABLE_CARB_RECOMMENDATIONS` | Enable carb suggestions | `true` | Safety feature |
| `CARB_EFFECTIVENESS` | Glucose rise per 15g carbs | `15.0` | mg/dL per 15g |
| `CARB_TO_GLUCOSE_RATIO` | Glucose rise per 1g carb | `3.5` | mg/dL per gram |
| `CARB_ABSORPTION_FAST` | Fast carb absorption time | `90` | Minutes |
| `CARB_ABSORPTION_SLOW` | Slow carb absorption time | `180` | Minutes |
| **IOB/COB Thresholds** |
| `IOB_THRESHOLD_HIGH` | High IOB threshold | `2.0` | Units for warnings |
| `COB_THRESHOLD_HIGH` | High COB threshold | `30.0` | Grams for warnings |
| **System Settings** |
| `DATABASE_PATH` | SQLite database file path | `glucose_monitor.db` | |
| `DATA_RETENTION_DAYS` | Days to keep historical data | `30` | |
| `LOG_LEVEL` | Logging verbosity | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `ENABLE_TERMINAL_OUTPUT` | Show terminal display | `true` | Real-time output |

## Usage

### Basic Monitoring
```bash
# Start monitoring with real Dexcom data
python -m src.main

# Start with mock data for testing
python -m src.main --mock

# Specify custom configuration file
python -m src.main --env-file custom.env
```

### Run Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_recommendations.py -v
pytest tests/test_analysis.py -v

# Run tests with coverage
pytest --cov=src tests/
```

## How It Works

### 1. Data Collection
- Connects to Dexcom Share API using pydexcom library
- Retrieves new glucose readings every 5 minutes + 5 seconds
- Stores readings in SQLite database with timestamp and trend information

### 2. Analysis Engine
The system performs multi-layered analysis:

**Trend Analysis**
- Calculates rate of change (mg/dL per minute) using configurable thresholds
- Determines trend direction and strength with linear regression
- Assesses glucose stability using variance analysis

**IOB/COB Tracking**
- Tracks Insulin on Board using configurable insulin duration curves
- Monitors Carbs on Board with absorption time modeling  
- Supports manual IOB overrides from pump/Omnipod readings
- Calculates glucose impact predictions from active insulin/carbs

**Prediction Algorithms**
- Linear extrapolation for consistent trends
- Polynomial fitting for curved patterns
- Considers IOB/COB effects on future glucose levels
- Ensemble approach selecting best method with confidence scoring

### 3. Recommendation System

**Four Recommendation Types**:
1. **Carbohydrate Recommendations** (Priority 1) - For low/falling glucose
2. **Insulin Recommendations** (Priority 2) - For high/stable glucose  
3. **IOB Status Recommendations** (Priority 4) - To verify active insulin accuracy
4. **Monitoring Recommendations** (Priority 5) - Increased monitoring frequency

**IOB Status Recommendations** trigger when:
- Approaching low glucose without IOB data (High urgency)
- Glucose rising fast with no IOB data (Medium urgency)  
- High IOB (>0.6u) significantly affecting predictions (Medium urgency)
- Approaching low with existing IOB requiring verification (High urgency)

**Safety-First Design**:
- Conservative thresholds with configurable sensitivity
- Multiple safety checks including IOB consideration
- Clear contraindications (e.g., no insulin if trending down rapidly)

### 4. Telegram Integration
- Real-time bidirectional communication
- Plain number shortcuts for quick IOB entry (supports `2.4` and `2,4` formats)
- Rich command processing with parameter validation
- Formatted responses with safety notes and recommendations

## Message Examples

### IOB Status Recommendation
```
🔄 IOB Status Check - 14:30

IMPORTANT: Check current IOB status - approaching low with 0.6u IOB - verify accuracy for safe predictions.

Current IOB: 0.6 units
Expected effect: 0.6u IOB should lower glucose by ~24 mg/dL

💡 Safety Notes:
• Accurate IOB improves prediction accuracy
• Check pump/Omnipod display for current active insulin  
• Update using /iob command or plain number in Telegram
```

### Insulin Recommendation (IOB-Aware)
```
🩸 Glucose Alert - 14:30

Current: 220 mg/dL ⬆️
Trend: Rising
IOB: 0.2 units (minimal impact)

💉 Insulin Recommendation
Consider 0.7 units of rapid-acting insulin. Adjusted for current IOB.
• Suggested: 0.7 units (reduced from 0.9u due to active insulin)

⚠️ Safety reminders:
• Consult healthcare provider before administering insulin
• Monitor glucose closely after insulin administration
```

### Quick IOB Update via Telegram
```
User: 2.4
Bot: ✅ IOB Override Set

IOB updated to 2.4 units from telegram-shortcut
Expected glucose effect: -96 mg/dL over next 60 minutes
Last updated: 14:32
```

## Architecture

```
src/
├── main.py                 # Main application entry point
├── config/                 # Configuration management
├── database/               # SQLite database operations
├── sensors/                # Dexcom and mock data clients  
├── analysis/               # Trend analysis and predictions
│   ├── trend_analyzer.py   # Configurable glucose trend analysis
│   ├── predictor.py        # Future value predictions
│   ├── iob_calculator.py   # IOB/COB tracking and calculations
│   └── recommendations.py  # Four-tier recommendation engine
├── notifications/          # Telegram integration with commands
│   └── telegram_bot.py     # Bidirectional bot with IOB shortcuts
├── commands/               # Command processing and formatting
└── terminal/               # Interactive terminal interface

tests/                      # Comprehensive test suite
```

## Safety Features

### Built-in Safety Checks
- No insulin recommendations for rapidly falling glucose
- IOB consideration in all insulin calculations
- Conservative carb calculations for lows
- Maximum limits on insulin suggestions (0.1-2.0 units)
- Mandatory healthcare provider consultation reminders

### Emergency Protocols  
- Critical alerts for glucose <55 or >300 mg/dL
- Immediate Telegram notifications with IOB context
- Clear action steps with timing and expected effects

### Data Validation
- Realistic glucose range validation (40-400 mg/dL)
- Trend consistency checking with configurable thresholds  
- Prediction reasonableness assessment including IOB effects
- IOB/COB data integrity validation

## Troubleshooting

### Common Issues

**Dexcom Connection Errors**
- Ensure Dexcom Follow is enabled in the Dexcom mobile app
- Verify username/password for Dexcom Share
- Check DEXCOM_OUS setting for non-US accounts
```bash
# Test Dexcom connection  
python -c "from src.sensors import DexcomClient; from src.config import Settings; DexcomClient(Settings()).test_connection()"
```

**Telegram Bot Issues**
- Verify bot token and chat ID are correct
- Check that the bot has permission to send messages
- Test with simple commands first
```bash
# Test Telegram connection
python debug_telegram.py
```

**Configuration Issues**
```bash
# Validate configuration
python -c "from src.config import Settings; print(Settings().to_dict())"
```

## Contributing

1. Fork the repository
2. Create a feature branch  
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a pull request

### Development Setup
```bash
# Install development dependencies
pip install pytest pytest-cov pytest-mock

# Run tests with coverage
pytest --cov=src tests/

# Run specific test scenarios
pytest tests/test_recommendations.py::TestRecommendationScenarios::test_iob_recommendation_approaching_low -v
```

## License

[Add your license here]

## Acknowledgments

- Built with [pydexcom](https://pypi.org/project/pydexcom/) for Dexcom Share integration
- Requires Dexcom Follow to be enabled for API access
- Uses SQLite for reliable data storage
- Telegram Bot API for real-time communication

---

**Remember: This tool is designed to supplement, not replace, proper medical care and monitoring. Always consult with healthcare professionals for diabetes management decisions.**