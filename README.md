# Vestaboard Local Automation

Automate your Vestaboard over your local network. Schedule messages, display weather, stocks, calendar events, and trigger messages from smart home systems.

## Features

- **Local API** - Communicate directly with your Vestaboard on your LAN
- **Web Control Panel** - Easy-to-use interface for sending messages
- **Scheduled Messages** - Cron-based scheduling for automated content
- **Data Integrations**:
  - Weather (OpenWeatherMap)
  - Stock prices (Yahoo Finance)
  - Calendar events (Google Calendar ICS)
  - News headlines (NewsAPI)
- **Webhook Endpoint** - Trigger messages from Home Assistant, IFTTT, etc.
- **Docker Support** - Easy deployment on NAS or home server

## Quick Start

### 1. Get Your Vestaboard API Info

From the Vestaboard app, find your:
- **Local API URL** (e.g., `http://192.168.1.100:7000`)
- **Local API Key**

### 2. Deploy with Docker

```bash
# Clone the repo
git clone https://github.com/seattlekxg/vestaboard-local.git
cd vestaboard-local

# Create your .env file
cp .env.example .env
# Edit .env with your Vestaboard credentials

# Start with Docker Compose
docker-compose up -d
```

### 3. Access the Control Panel

Open `http://your-nas-ip:8080` in your browser.

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `VESTABOARD_LOCAL_URL` | Your Vestaboard's local API URL |
| `VESTABOARD_LOCAL_KEY` | Your Vestaboard's local API key |

### Optional Integrations

| Variable | Description |
|----------|-------------|
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key for weather |
| `WEATHER_LOCATION` | Location for weather (default: Seattle,WA,US) |
| `STOCK_SYMBOLS` | Comma-separated stock symbols (default: SPY,QQQ) |
| `CALENDAR_URL` | Google Calendar ICS URL |
| `NEWS_API_KEY` | NewsAPI key for news headlines |

## API Endpoints

### Send Messages

```bash
# Send text message
curl -X POST http://localhost:8080/api/message \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World!"}'

# Send weather
curl -X POST http://localhost:8080/api/message/weather

# Send stocks
curl -X POST http://localhost:8080/api/message/stocks

# Clear the board
curl -X POST http://localhost:8080/api/clear
```

### Webhook (for smart home integration)

```bash
# From Home Assistant, IFTTT, etc.
curl -X POST http://localhost:8080/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"type": "text", "text": "Someone is at the door!"}'
```

### Schedule Management

```bash
# Get all schedules
curl http://localhost:8080/api/schedules

# Create a schedule
curl -X POST http://localhost:8080/api/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Morning Greeting",
    "message_type": "text",
    "content": "Good Morning!",
    "cron_expression": "0 7 * * *"
  }'
```

## Cron Expression Examples

| Expression | Description |
|------------|-------------|
| `0 7 * * *` | Every day at 7:00 AM |
| `30 9 * * 1-5` | Weekdays at 9:30 AM |
| `0 */2 * * *` | Every 2 hours |
| `0 8,12,18 * * *` | At 8 AM, 12 PM, and 6 PM |

## Home Assistant Integration

Add a REST command to your `configuration.yaml`:

```yaml
rest_command:
  vestaboard_message:
    url: "http://your-nas-ip:8080/api/webhook"
    method: POST
    content_type: "application/json"
    payload: '{"type": "text", "text": "{{ message }}"}'
```

Then use in automations:

```yaml
automation:
  - alias: "Doorbell notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.doorbell
        to: "on"
    action:
      - service: rest_command.vestaboard_message
        data:
          message: "Someone is at the door!"
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp .env.example .env

# Test connection
python -m src.main test

# Send a test message
python -m src.main hello

# Start the server
python -m src.main
```

## License

MIT
