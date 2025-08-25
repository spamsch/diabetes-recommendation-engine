# Docker Setup Guide

This guide explains how to run the Glucose Monitoring System using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Your Dexcom Share credentials (for real monitoring)
- Optional: Telegram bot token (for notifications)

## Quick Start

### 1. Testing with Mock Data (Safe Default)

```bash
# Start with simulated data (no real credentials needed)
docker-compose up

# Or build and run directly
docker build -t glucose-monitor .
docker run -it glucose-monitor
```

### 2. Production with Real Dexcom Data

Create a `.env` file with your credentials:

```bash
# Copy the example
cp .env.example .env

# Edit with your credentials
nano .env
```

Then start the service:

```bash
# Run in background
docker-compose up -d

# View logs
docker-compose logs -f glucose-monitor
```

### 3. Custom Configuration

Set environment variables directly:

```bash
docker run -e DEXCOM_USERNAME=your_username \
           -e DEXCOM_PASSWORD=your_password \
           -e TELEGRAM_BOT_URL=your_bot_url \
           -e TELEGRAM_CHAT_ID=your_chat_id \
           glucose-monitor python -m src.main --log-level INFO
```

## Docker Commands

### Building and Running

```bash
# Build the image
docker build -t glucose-monitor .

# Run with mock data (default)
docker run -it glucose-monitor

# Run with real monitoring (requires credentials)
docker run -e DEXCOM_USERNAME=user -e DEXCOM_PASSWORD=pass \
           glucose-monitor python -m src.main

# Run in background
docker run -d --name glucose-monitor-service glucose-monitor
```

### Data Management

```bash
# Run with persistent data
docker run -v glucose_data:/app/data \
           -v glucose_logs:/app/logs \
           glucose-monitor

# Backup data
docker run --rm -v glucose_data:/data \
           -v $(pwd):/backup \
           busybox tar czf /backup/glucose_backup.tar.gz -C /data .

# Restore data
docker run --rm -v glucose_data:/data \
           -v $(pwd):/backup \
           busybox tar xzf /backup/glucose_backup.tar.gz -C /data
```

### Utility Commands

```bash
# Generate graphs
docker run glucose-monitor python graph_generator.py --type timeline --hours 24

# Run tests
docker run glucose-monitor python run_monitor.py --test-recs

# Interactive shell
docker run -it glucose-monitor bash

# View database
docker run -it glucose-monitor python -c "
from src.database import GlucoseDatabase
db = GlucoseDatabase('/app/data/glucose_monitor.db')
readings = db.get_latest_readings(5)
for r in readings:
    print(f'{r.timestamp}: {r.value} mg/dL')
"
```

## Docker Compose Services

### Main Service

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f glucose-monitor

# Restart service
docker-compose restart glucose-monitor

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Service Management

```bash
# Scale service (multiple instances)
docker-compose up --scale glucose-monitor=2

# Update service
docker-compose pull
docker-compose up -d

# View service status
docker-compose ps

# Execute command in running service
docker-compose exec glucose-monitor python graph_generator.py --type trend
```

## Environment Variables

Key environment variables you can set:

```bash
# Dexcom credentials (required for real monitoring)
DEXCOM_USERNAME=your_username
DEXCOM_PASSWORD=your_password
DEXCOM_OUS=false  # Set to true for international users

# Telegram notifications (optional)
TELEGRAM_BOT_URL=https://api.telegram.org/bot<your-token>
TELEGRAM_CHAT_ID=your_chat_id

# Monitoring settings
POLL_INTERVAL_MINUTES=5
LOG_LEVEL=INFO
ENABLE_TERMINAL_OUTPUT=false

# Glucose thresholds (mg/dL)
LOW_GLUCOSE_THRESHOLD=70
HIGH_GLUCOSE_THRESHOLD=180
TARGET_GLUCOSE=120

# Analysis settings
ANALYSIS_WINDOW_SIZE=15
PREDICTION_MINUTES_AHEAD=15

# Recommendations
ENABLE_INSULIN_RECOMMENDATIONS=true
ENABLE_CARB_RECOMMENDATIONS=true
```

## Security Best Practices

1. **Never put credentials in Dockerfile or docker-compose.yml**
2. **Use environment variables or mounted .env files**
3. **Run containers as non-root user** (done automatically)
4. **Use persistent volumes for data**
5. **Regularly backup your glucose data**

## Troubleshooting

### Common Issues

```bash
# Check container logs
docker-compose logs glucose-monitor

# Check container health
docker-compose ps

# Restart unhealthy container
docker-compose restart glucose-monitor

# Connect to container shell
docker-compose exec glucose-monitor bash

# Test database connection
docker-compose exec glucose-monitor python -c "
import sqlite3
conn = sqlite3.connect('/app/data/glucose_monitor.db')
print('Database connected successfully')
conn.close()
"

# Test Dexcom connection
docker-compose exec glucose-monitor python -c "
from src.config import Settings
from src.sensors import DexcomClient
settings = Settings()
client = DexcomClient(settings)
print('Testing connection...')
print(f'Connection test: {client.test_connection()}')
"
```

### Volume Issues

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect glucose_data

# Remove volumes (WARNING: deletes data)
docker volume rm glucose_data glucose_logs
```

### Network Issues

```bash
# Check networks
docker network ls

# Inspect network
docker network inspect dexcom-analyze_glucose-network
```

## Production Deployment

### Health Monitoring

The container includes a health check:

```bash
# Check health status
docker-compose ps

# Manual health check
docker-compose exec glucose-monitor python -c "
import sqlite3
conn = sqlite3.connect('/app/data/glucose_monitor.db', timeout=5)
conn.close()
print('Health check passed')
"
```

### Logging

Configure log rotation:

```yaml
# In docker-compose.yml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

### Monitoring

```bash
# View resource usage
docker stats glucose-monitor

# Monitor logs in real-time
docker-compose logs -f --tail=50 glucose-monitor

# Container resource limits (add to docker-compose.yml)
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
```

## Example Production Setup

```bash
# 1. Create production directory
mkdir glucose-monitor-prod
cd glucose-monitor-prod

# 2. Clone or copy files
# (copy Dockerfile, docker-compose.yml, requirements.txt, src/)

# 3. Create production .env
cat > .env << EOF
DEXCOM_USERNAME=your_username
DEXCOM_PASSWORD=your_password
TELEGRAM_BOT_URL=your_bot_url
TELEGRAM_CHAT_ID=your_chat_id
LOG_LEVEL=INFO
ENABLE_TERMINAL_OUTPUT=false
POLL_INTERVAL_MINUTES=5
EOF

# 4. Start service
docker-compose up -d

# 5. Setup log monitoring
docker-compose logs -f glucose-monitor &

# 6. Setup backup cron job
echo "0 2 * * * cd /path/to/glucose-monitor-prod && docker run --rm -v glucose_data:/data -v \$(pwd):/backup busybox tar czf /backup/backup-\$(date +%Y%m%d).tar.gz -C /data ." | crontab -
```

This setup provides a robust, production-ready glucose monitoring system running in Docker containers.