"""Web API and control panel for Vestaboard automation."""

from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from typing import Optional

from .client import VestaboardClient
from .config import config
from .fetchers import WeatherFetcher, StockFetcher, CalendarFetcher, NewsFetcher, CountdownFetcher
from .scheduler import MessageScheduler
from .storage import Storage, ScheduledMessage, Countdown

app = Flask(__name__)

# Global instances (initialized in create_app)
client: Optional[VestaboardClient] = None
storage: Optional[Storage] = None
scheduler: Optional[MessageScheduler] = None


def create_app() -> Flask:
    """Create and configure the Flask app."""
    global client, storage, scheduler

    storage = Storage()
    client = VestaboardClient()
    scheduler = MessageScheduler(client=client, storage=storage)

    # Add default schedules if none exist
    scheduler.add_default_schedules()

    # Start the scheduler
    scheduler.start()

    return app


# ========== HTML Templates ==========

CONTROL_PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Vestaboard Control Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .card h2 { margin-top: 0; color: #444; }
        input, textarea, select, button {
            font-size: 16px;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
            width: 100%;
            margin: 5px 0;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        button.secondary { background: #6c757d; }
        button.danger { background: #dc3545; }
        .btn-group { display: flex; gap: 10px; }
        .btn-group button { flex: 1; }
        .schedule-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .schedule-item:last-child { border-bottom: none; }
        .toggle {
            width: 50px;
            height: 26px;
            background: #ccc;
            border-radius: 13px;
            position: relative;
            cursor: pointer;
        }
        .toggle.active { background: #28a745; }
        .toggle::after {
            content: '';
            position: absolute;
            width: 22px;
            height: 22px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: 0.2s;
        }
        .toggle.active::after { left: 26px; }
        .log-entry { font-size: 14px; padding: 5px 0; border-bottom: 1px solid #eee; }
        .log-entry.success { color: #28a745; }
        .log-entry.fail { color: #dc3545; }
        .status { padding: 5px 10px; border-radius: 4px; font-size: 14px; }
        .status.ok { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>Vestaboard Control</h1>

    <div class="card">
        <h2>Send Message</h2>
        <textarea id="message" rows="4" placeholder="Type your message..."></textarea>
        <button onclick="sendMessage()">Send to Vestaboard</button>
    </div>

    <div class="card">
        <h2>Quick Actions</h2>
        <div class="btn-group">
            <button onclick="sendWeather()">Weather</button>
            <button onclick="sendStocks()">Stocks</button>
            <button onclick="sendCountdowns()">Countdowns</button>
            <button onclick="clearBoard()" class="secondary">Clear</button>
        </div>
    </div>

    <div class="card">
        <h2>Countdowns</h2>
        <div id="countdowns">Loading...</div>
        <hr>
        <h3>Add New Countdown</h3>
        <input type="text" id="countdownName" placeholder="Event name (e.g., Vacation)">
        <input type="date" id="countdownDate">
        <button onclick="addCountdown()">Add Countdown</button>
    </div>

    <div class="card">
        <h2>Scheduled Messages</h2>
        <div id="schedules">Loading...</div>
        <hr>
        <h3>Add New Schedule</h3>
        <input type="text" id="newName" placeholder="Name (e.g., Morning Greeting)">
        <select id="newType">
            <option value="text">Text Message</option>
            <option value="weather">Weather</option>
            <option value="stocks">Stocks</option>
            <option value="calendar">Calendar</option>
            <option value="news">News</option>
            <option value="countdowns">Countdowns</option>
        </select>
        <input type="text" id="newContent" placeholder="Message content (for text type)">
        <input type="text" id="newCron" placeholder="Cron expression (e.g., 0 8 * * *)">
        <button onclick="addSchedule()">Add Schedule</button>
    </div>

    <div class="card">
        <h2>Recent Messages</h2>
        <div id="logs">Loading...</div>
    </div>

    <script>
        async function api(method, endpoint, data = null) {
            const opts = { method, headers: { 'Content-Type': 'application/json' } };
            if (data) opts.body = JSON.stringify(data);
            const res = await fetch('/api' + endpoint, opts);
            return res.json();
        }

        async function sendMessage() {
            const msg = document.getElementById('message').value;
            if (!msg) return;
            const res = await api('POST', '/message', { text: msg });
            alert(res.success ? 'Sent!' : 'Failed: ' + res.error);
            document.getElementById('message').value = '';
            loadLogs();
        }

        async function sendWeather() {
            const res = await api('POST', '/message/weather');
            alert(res.success ? 'Weather sent!' : 'Failed');
            loadLogs();
        }

        async function sendStocks() {
            const res = await api('POST', '/message/stocks');
            alert(res.success ? 'Stocks sent!' : 'Failed');
            loadLogs();
        }

        async function sendCalendar() {
            const res = await api('POST', '/message/calendar');
            alert(res.success ? 'Calendar sent!' : 'Failed');
            loadLogs();
        }

        async function sendCountdowns() {
            const res = await api('POST', '/message/countdowns');
            alert(res.success ? 'Countdowns sent!' : 'Failed');
            loadLogs();
        }

        async function clearBoard() {
            const res = await api('POST', '/clear');
            alert(res.success ? 'Cleared!' : 'Failed');
        }

        async function loadCountdowns() {
            const res = await api('GET', '/countdowns');
            const div = document.getElementById('countdowns');
            if (!res.countdowns || res.countdowns.length === 0) {
                div.innerHTML = '<p>No countdowns configured.</p>';
                return;
            }
            div.innerHTML = res.countdowns.map(c => `
                <div class="schedule-item">
                    <div>
                        <strong>${c.name}</strong><br>
                        <small>${c.target_date} (${c.days_remaining} days)</small>
                    </div>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <div class="toggle ${c.enabled ? 'active' : ''}"
                             onclick="toggleCountdown(${c.id}, ${!c.enabled})"></div>
                        <button onclick="deleteCountdown(${c.id})" class="danger"
                                style="width:auto;padding:5px 10px;">X</button>
                    </div>
                </div>
            `).join('');
        }

        async function toggleCountdown(id, enabled) {
            await api('PUT', '/countdowns/' + id, { enabled });
            loadCountdowns();
        }

        async function deleteCountdown(id) {
            if (!confirm('Delete this countdown?')) return;
            await api('DELETE', '/countdowns/' + id);
            loadCountdowns();
        }

        async function addCountdown() {
            const name = document.getElementById('countdownName').value;
            const target_date = document.getElementById('countdownDate').value;
            if (!name || !target_date) {
                alert('Name and date are required');
                return;
            }
            await api('POST', '/countdowns', { name, target_date });
            document.getElementById('countdownName').value = '';
            document.getElementById('countdownDate').value = '';
            loadCountdowns();
        }

        async function loadSchedules() {
            const res = await api('GET', '/schedules');
            const div = document.getElementById('schedules');
            if (!res.schedules || res.schedules.length === 0) {
                div.innerHTML = '<p>No schedules configured.</p>';
                return;
            }
            div.innerHTML = res.schedules.map(s => `
                <div class="schedule-item">
                    <div>
                        <strong>${s.name}</strong><br>
                        <small>${s.message_type} | ${s.cron_expression}</small>
                    </div>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <div class="toggle ${s.enabled ? 'active' : ''}"
                             onclick="toggleSchedule(${s.id}, ${!s.enabled})"></div>
                        <button onclick="deleteSchedule(${s.id})" class="danger"
                                style="width:auto;padding:5px 10px;">X</button>
                    </div>
                </div>
            `).join('');
        }

        async function toggleSchedule(id, enabled) {
            await api('PUT', '/schedules/' + id, { enabled });
            loadSchedules();
        }

        async function deleteSchedule(id) {
            if (!confirm('Delete this schedule?')) return;
            await api('DELETE', '/schedules/' + id);
            loadSchedules();
        }

        async function addSchedule() {
            const data = {
                name: document.getElementById('newName').value,
                message_type: document.getElementById('newType').value,
                content: document.getElementById('newContent').value,
                cron_expression: document.getElementById('newCron').value
            };
            if (!data.name || !data.cron_expression) {
                alert('Name and cron expression are required');
                return;
            }
            await api('POST', '/schedules', data);
            document.getElementById('newName').value = '';
            document.getElementById('newContent').value = '';
            document.getElementById('newCron').value = '';
            loadSchedules();
        }

        async function loadLogs() {
            const res = await api('GET', '/logs');
            const div = document.getElementById('logs');
            if (!res.logs || res.logs.length === 0) {
                div.innerHTML = '<p>No messages sent yet.</p>';
                return;
            }
            div.innerHTML = res.logs.slice(0, 10).map(l => `
                <div class="log-entry ${l.success ? 'success' : 'fail'}">
                    ${l.sent_at} - ${l.message_type}
                    ${l.success ? '✓' : '✗'}
                </div>
            `).join('');
        }

        // Load data on page load
        loadSchedules();
        loadCountdowns();
        loadLogs();
    </script>
</body>
</html>
"""


# ========== Routes ==========

@app.route("/")
def index():
    """Render the control panel."""
    return render_template_string(CONTROL_PANEL_HTML)


@app.route("/api/status")
def api_status():
    """Get system status."""
    connected = client.test_connection() if client else False
    return jsonify({
        "connected": connected,
        "scheduler_running": scheduler._running if scheduler else False
    })


@app.route("/api/message", methods=["POST"])
def api_send_message():
    """Send a text message to the Vestaboard."""
    data = request.get_json() or {}
    text = data.get("text", "")

    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400

    success = client.send_message(text)
    storage.log_message("text", text, success)

    return jsonify({"success": success})


@app.route("/api/message/weather", methods=["POST"])
def api_send_weather():
    """Send weather to the Vestaboard."""
    fetcher = WeatherFetcher()
    weather = fetcher.fetch()

    if not weather:
        return jsonify({"success": False, "error": "Could not fetch weather"})

    lines = fetcher.format_for_board(weather)
    success = client.send_lines(lines)
    storage.log_message("weather", "\n".join(lines), success)

    return jsonify({"success": success})


@app.route("/api/message/stocks", methods=["POST"])
def api_send_stocks():
    """Send stock prices to the Vestaboard."""
    fetcher = StockFetcher()
    stocks = fetcher.fetch_multiple()

    if not stocks:
        return jsonify({"success": False, "error": "Could not fetch stocks"})

    lines = fetcher.format_for_board(stocks)
    success = client.send_lines(lines)
    storage.log_message("stocks", "\n".join(lines), success)

    return jsonify({"success": success})


@app.route("/api/message/calendar", methods=["POST"])
def api_send_calendar():
    """Send calendar events to the Vestaboard."""
    fetcher = CalendarFetcher()
    events = fetcher.fetch_today()
    lines = fetcher.format_for_board(events)
    success = client.send_lines(lines)
    storage.log_message("calendar", "\n".join(lines), success)

    return jsonify({"success": success})


@app.route("/api/message/countdowns", methods=["POST"])
def api_send_countdowns():
    """Send countdowns to the Vestaboard."""
    fetcher = CountdownFetcher(storage=storage)
    lines = fetcher.format_for_board()
    success = client.send_lines(lines)
    storage.log_message("countdowns", "\n".join(lines), success)

    return jsonify({"success": success})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Clear the Vestaboard."""
    success = client.clear()
    storage.log_message("clear", "", success)
    return jsonify({"success": success})


# ========== Webhook Endpoint ==========

@app.route("/api/webhook", methods=["POST"])
def api_webhook():
    """Webhook endpoint for smart home triggers.

    Accepts JSON with:
    - text: Message to display
    - type: Optional message type (text, weather, stocks, calendar)
    """
    data = request.get_json() or {}

    msg_type = data.get("type", "text")
    text = data.get("text", "")

    if msg_type == "text" and text:
        success = client.send_message(text)
    elif msg_type == "weather":
        fetcher = WeatherFetcher()
        weather = fetcher.fetch()
        if weather:
            lines = fetcher.format_for_board(weather)
            success = client.send_lines(lines)
        else:
            success = False
    elif msg_type == "stocks":
        fetcher = StockFetcher()
        stocks = fetcher.fetch_multiple()
        if stocks:
            lines = fetcher.format_for_board(stocks)
            success = client.send_lines(lines)
        else:
            success = False
    elif msg_type == "clear":
        success = client.clear()
    else:
        return jsonify({"success": False, "error": "Invalid request"}), 400

    storage.log_message(f"webhook:{msg_type}", text, success)
    return jsonify({"success": success})


# ========== Schedule Management ==========

@app.route("/api/schedules", methods=["GET"])
def api_get_schedules():
    """Get all scheduled messages."""
    messages = storage.get_scheduled_messages()
    return jsonify({
        "schedules": [
            {
                "id": m.id,
                "name": m.name,
                "message_type": m.message_type,
                "content": m.content,
                "cron_expression": m.cron_expression,
                "enabled": m.enabled,
                "last_run": m.last_run.isoformat() if m.last_run else None
            }
            for m in messages
        ]
    })


@app.route("/api/schedules", methods=["POST"])
def api_create_schedule():
    """Create a new scheduled message."""
    data = request.get_json() or {}

    msg = ScheduledMessage(
        id=None,
        name=data.get("name", "Untitled"),
        message_type=data.get("message_type", "text"),
        content=data.get("content"),
        cron_expression=data.get("cron_expression", "0 * * * *"),
        enabled=data.get("enabled", True)
    )

    msg_id = storage.save_scheduled_message(msg)
    return jsonify({"success": True, "id": msg_id})


@app.route("/api/schedules/<int:schedule_id>", methods=["PUT"])
def api_update_schedule(schedule_id: int):
    """Update a scheduled message."""
    data = request.get_json() or {}

    msg = storage.get_scheduled_message(schedule_id)
    if not msg:
        return jsonify({"success": False, "error": "Not found"}), 404

    if "name" in data:
        msg.name = data["name"]
    if "message_type" in data:
        msg.message_type = data["message_type"]
    if "content" in data:
        msg.content = data["content"]
    if "cron_expression" in data:
        msg.cron_expression = data["cron_expression"]
    if "enabled" in data:
        msg.enabled = data["enabled"]

    storage.save_scheduled_message(msg)
    return jsonify({"success": True})


@app.route("/api/schedules/<int:schedule_id>", methods=["DELETE"])
def api_delete_schedule(schedule_id: int):
    """Delete a scheduled message."""
    deleted = storage.delete_scheduled_message(schedule_id)
    return jsonify({"success": deleted})


@app.route("/api/schedules/<int:schedule_id>/run", methods=["POST"])
def api_run_schedule(schedule_id: int):
    """Manually run a scheduled message."""
    msg = storage.get_scheduled_message(schedule_id)
    if not msg:
        return jsonify({"success": False, "error": "Not found"}), 404

    success = scheduler.execute_message(msg)
    return jsonify({"success": success})


# ========== Countdown Management ==========

@app.route("/api/countdowns", methods=["GET"])
def api_get_countdowns():
    """Get all countdowns."""
    from datetime import date
    countdowns = storage.get_countdowns(include_past=False)
    today = date.today()
    return jsonify({
        "countdowns": [
            {
                "id": c.id,
                "name": c.name,
                "target_date": c.target_date.isoformat(),
                "enabled": c.enabled,
                "days_remaining": (c.target_date - today).days
            }
            for c in countdowns
        ]
    })


@app.route("/api/countdowns", methods=["POST"])
def api_create_countdown():
    """Create a new countdown."""
    from datetime import date
    data = request.get_json() or {}

    try:
        target_date = date.fromisoformat(data.get("target_date", ""))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format"}), 400

    countdown = Countdown(
        id=None,
        name=data.get("name", "Untitled"),
        target_date=target_date,
        enabled=data.get("enabled", True)
    )

    countdown_id = storage.save_countdown(countdown)
    return jsonify({"success": True, "id": countdown_id})


@app.route("/api/countdowns/<int:countdown_id>", methods=["PUT"])
def api_update_countdown(countdown_id: int):
    """Update a countdown."""
    from datetime import date
    data = request.get_json() or {}

    countdown = storage.get_countdown(countdown_id)
    if not countdown:
        return jsonify({"success": False, "error": "Not found"}), 404

    if "name" in data:
        countdown.name = data["name"]
    if "target_date" in data:
        try:
            countdown.target_date = date.fromisoformat(data["target_date"])
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format"}), 400
    if "enabled" in data:
        countdown.enabled = data["enabled"]

    storage.save_countdown(countdown)
    return jsonify({"success": True})


@app.route("/api/countdowns/<int:countdown_id>", methods=["DELETE"])
def api_delete_countdown(countdown_id: int):
    """Delete a countdown."""
    deleted = storage.delete_countdown(countdown_id)
    return jsonify({"success": deleted})


# ========== Logs ==========

@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    """Get recent message logs."""
    logs = storage.get_message_log(limit=50)
    return jsonify({
        "logs": [
            {
                "id": l.id,
                "message_type": l.message_type,
                "content": l.content[:100] if l.content else "",
                "sent_at": l.sent_at.strftime("%Y-%m-%d %H:%M"),
                "success": l.success
            }
            for l in logs
        ]
    })


def run_server():
    """Run the web server."""
    create_app()
    app.run(host=config.web_host, port=config.web_port)


if __name__ == "__main__":
    run_server()
