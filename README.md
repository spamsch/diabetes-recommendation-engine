# Glucose Monitoring System

A comprehensive Python application for monitoring glucose levels from Dexcom sensors, providing intelligent analysis, predictions, and recommendations to help parents manage their children's diabetes.

## ⚠️ Important Medical Disclaimer

**This application is for monitoring and educational purposes only. It is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult with qualified healthcare providers before making any medical decisions or changes to diabetes management.**

- Never ignore symptoms even if readings appear normal
- Always have emergency glucose supplies available
- Seek immediate medical attention for severe symptoms
- Follow your healthcare provider's diabetes management plan

## Features

### 🩸 Continuous Glucose Monitoring
- Real-time data collection from Dexcom sensors every 5 minutes
- Reliable data storage in SQLite database
- Automatic reconnection handling

### 📊 Intelligent Analysis
- **Trend Analysis**: Detects glucose trends (very fast down/up, fast down/up, down/up, stable)
- **Pattern Recognition**: Identifies critical patterns and approaching thresholds
- **Prediction Engine**: Forecasts glucose levels 15 minutes ahead using multiple algorithms
- **Risk Assessment**: Evaluates prediction confidence and identifies risk factors

### 💊 Smart Recommendations
- **Insulin Recommendations**: Suggests insulin doses for high, stable glucose levels
- **Carbohydrate Recommendations**: Recommends fast-acting carbs for low glucose
- **Monitoring Recommendations**: Advises on increased monitoring frequency
- **Safety-First Approach**: Conservative recommendations with built-in safety checks

### 📱 Telegram Integration
- Real-time alerts for critical situations
- Formatted recommendations with emojis and priority levels
- Status updates and system notifications

### 📈 Visualization
- Real-time terminal display with trend arrows
- Glucose timeline graphs with target ranges
- Trend analysis charts with rate of change
- Daily summary reports with statistics

### 🧪 Comprehensive Testing
- Mock client for testing recommendations
- Multiple realistic scenarios (dawn phenomenon, post-meal spikes, exercise drops)
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

# Optional Telegram notifications
TELEGRAM_BOT_URL=https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage
TELEGRAM_CHAT_ID=your_chat_id
```

### Key Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `ANALYSIS_WINDOW_SIZE` | Number of readings to analyze | 15 |
| `LOW_GLUCOSE_THRESHOLD` | Low glucose threshold (mg/dL) | 70 |
| `HIGH_GLUCOSE_THRESHOLD` | High glucose threshold (mg/dL) | 180 |
| `INSULIN_EFFECTIVENESS` | Glucose drop per insulin unit | 40.0 |
| `CARB_EFFECTIVENESS` | Glucose rise per 15g carbs | 15.0 |

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

### Generate Graphs
```bash
# Create timeline graph for last 24 hours
python graph_generator.py --hours 24 --type timeline

# Generate trend analysis with statistics
python graph_generator.py --hours 12 --type trend --stats

# Save graph to file
python graph_generator.py --hours 6 --type daily --output glucose_report.png
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
- Calculates rate of change (mg/dL per minute)
- Determines trend direction and strength
- Assesses glucose stability using variance

**Pattern Detection**
- Identifies rapid changes (>3 mg/dL per reading)
- Detects approaching critical thresholds
- Recognizes stable patterns

**Prediction Algorithms**
- Linear extrapolation for consistent trends
- Polynomial fitting for curved patterns
- Exponential smoothing for noisy data
- Ensemble approach selecting best method

### 3. Recommendation System

**Pluggable Architecture**: Easy to add new recommendation types

**Safety-First Design**:
- Conservative thresholds
- Multiple safety checks
- Clear contraindications (e.g., no insulin if trending down)

**Intelligent Prioritization**:
- Critical situations get highest priority
- Recommendations sorted by urgency
- Clear action items with safety reminders

### 4. Notification System
- Immediate alerts for critical situations
- Formatted messages with context
- Priority-based delivery

## Architecture

```
src/
├── main.py                 # Main application entry point
├── config/                 # Configuration management
├── database/               # SQLite database operations
├── sensors/                # Dexcom and mock data clients
├── analysis/               # Trend analysis and predictions
│   ├── trend_analyzer.py   # Glucose trend analysis
│   ├── predictor.py        # Future value predictions
│   └── recommendations.py  # Recommendation engine
├── notifications/          # Telegram integration
└── visualization/          # Graphing and charts

tests/                      # Comprehensive test suite
graph_generator.py          # Standalone graph generator
```

## Recommendation Examples

### Insulin Recommendation
```
🩸 Glucose Alert - 14:30

Current: 220 mg/dL ⬆️
Trend: Rising

💉 Insulin Recommendation
Consider 0.9 units of rapid-acting insulin. Current glucose: 220 mg/dL (stable). Always consult your healthcare provider.
• Suggested: 0.9 units

⚠️ Safety reminders:
• Consult healthcare provider before administering insulin
• Monitor glucose closely after insulin administration
```

### Low Glucose Alert
```
🚨 CRITICAL ALERT - 02:15

Current glucose: 50 mg/dL

URGENT: Take 20g fast-acting carbs NOW! Current: 50 mg/dL (falling rapidly)
• Suggested: 20g carbs
• Options: 8 glucose tablets, 1 cup fruit juice

⚠️ Safety reminders:
• Act quickly for low glucose
• Re-check glucose in 15 minutes
```

## Safety Features

### Built-in Safety Checks
- No insulin recommendations for falling glucose
- Conservative carb calculations for lows
- Maximum limits on insulin suggestions
- Mandatory healthcare provider consultation reminders

### Emergency Protocols
- Critical alerts for glucose <55 or >300 mg/dL
- Immediate Telegram notifications
- Clear action steps with timing

### Data Validation
- Realistic glucose range validation (40-400 mg/dL)
- Trend consistency checking
- Prediction reasonableness assessment

## Testing

The application includes comprehensive tests covering:

### Recommendation Algorithms
- Normal glucose scenarios (no recommendations)
- Critical low/high situations
- Stable high glucose (insulin recommendations)
- Trending low glucose (carb recommendations)
- Edge cases and safety validations

### Analysis Engine
- Trend detection accuracy
- Prediction algorithm performance
- Pattern recognition validation
- Statistical analysis verification

### Realistic Scenarios
- Dawn phenomenon (morning glucose rise)
- Post-meal spikes
- Exercise-induced glucose drops
- Overnight stability patterns

Run tests to validate recommendation safety:
```bash
pytest tests/test_recommendations.py -v
```

## Extending the System

### Adding New Recommendations
```python
from src.analysis.recommendations import RecommendationBase

class CustomRecommendation(RecommendationBase):
    def get_priority(self) -> int:
        return 3  # Medium priority
    
    def analyze(self, readings, trend_analysis, prediction):
        # Your custom logic here
        return {
            'type': 'custom',
            'message': 'Your recommendation message',
            'priority': self.get_priority()
        }
```

### Custom Analysis Modules
- Inherit from base classes
- Add to configuration system
- Include in test suite

## Troubleshooting

### Common Issues

**Connection Errors**
```bash
# Test Dexcom connection
python -c "from src.sensors import DexcomClient; from src.config import Settings; DexcomClient(Settings()).test_connection()"

# Use mock client for development
python -m src.main --mock
```

**Configuration Issues**
```bash
# Validate configuration
python -c "from src.config import Settings; print(Settings().to_dict())"
```

**Database Problems**
```bash
# Reset database
rm glucose_monitor.db
python -m src.main  # Will recreate database
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
pytest tests/test_recommendations.py::TestRecommendationScenarios::test_dawn_phenomenon -v
```

## License

[Add your license here]

## Acknowledgments

- Built with [pydexcom](https://pypi.org/project/pydexcom/) for Dexcom integration
- Uses matplotlib for visualization
- Telegram Bot API for notifications

---

**Remember: This tool is designed to supplement, not replace, proper medical care and monitoring. Always consult with healthcare professionals for diabetes management decisions.**