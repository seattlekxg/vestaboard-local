"""Web API and control panel for Vestaboard automation."""

from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from typing import Optional

from .client import VestaboardClient
from .config import config
from .fetchers import WeatherFetcher, StockFetcher, CalendarFetcher, NewsFetcher, CountdownFetcher, FlightFetcher
from .scheduler import MessageScheduler
from .storage import Storage, ScheduledMessage, Countdown, TrackedFlight

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
        .day-picker { display: flex; gap: 5px; margin: 10px 0; }
        .day-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 2px solid #ddd;
            background: white;
            cursor: pointer;
            font-size: 12px;
            font-weight: bold;
            color: #666;
        }
        .day-btn.active {
            background: #007bff;
            border-color: #007bff;
            color: white;
        }
        .day-btn:hover { border-color: #007bff; }
        .time-row { display: flex; gap: 10px; align-items: center; }
        .time-row input[type="time"] { flex: 1; }
        .schedule-days { font-size: 12px; color: #666; }

        /* Vestaboard Preview */
        .board-preview {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 15px;
            margin: 15px 0;
            display: inline-block;
        }
        .board-grid {
            display: grid;
            grid-template-columns: repeat(22, 1fr);
            gap: 3px;
        }
        .board-cell {
            width: 24px;
            height: 32px;
            background: #2a2a2a;
            border-radius: 3px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            font-size: 14px;
            font-weight: bold;
            color: #ffd700;
        }
        .board-cell.color-red { background: #ff4444; color: #fff; }
        .board-cell.color-orange { background: #ff8c00; color: #fff; }
        .board-cell.color-yellow { background: #ffd700; color: #1a1a1a; }
        .board-cell.color-green { background: #44aa44; color: #fff; }
        .board-cell.color-blue { background: #4488ff; color: #fff; }
        .board-cell.color-violet { background: #9944ff; color: #fff; }
        .board-cell.color-white { background: #ffffff; color: #1a1a1a; }
        .board-cell.filled { background: #ffd700; }
        @media (max-width: 600px) {
            .board-cell { width: 12px; height: 16px; font-size: 8px; }
            .board-preview { padding: 8px; }
            .board-grid { gap: 2px; }
        }
    </style>
</head>
<body>
    <h1>Vestaboard Control</h1>

    <div class="card">
        <h2>Send Message</h2>
        <textarea id="message" rows="4" placeholder="Type your message..." oninput="updatePreview()"></textarea>
        <div class="board-preview">
            <div class="board-grid" id="boardPreview"></div>
        </div>
        <button onclick="sendMessage()">Send to Vestaboard</button>
    </div>

    <div class="card">
        <h2>Quick Actions</h2>
        <div class="btn-group">
            <button onclick="sendWeather()">Weather</button>
            <button onclick="sendStocks()">Stocks</button>
            <button onclick="sendCountdowns()">Countdowns</button>
            <button onclick="sendFlights()">Flights</button>
        </div>
        <div class="btn-group" style="margin-top:10px;">
            <button onclick="clearBoard()" class="secondary">Clear Board</button>
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
        <h2>Flight Tracker</h2>
        <div id="flights">Loading...</div>
        <hr>
        <h3>Track a Flight</h3>
        <input type="text" id="flightNumber" placeholder="Flight number (e.g., AA100)">
        <input type="date" id="flightDate">
        <button onclick="addFlight()">Track Flight</button>
    </div>

    <div class="card">
        <h2>Scheduled Messages</h2>
        <div id="schedules">Loading...</div>
        <hr>
        <h3 id="scheduleFormTitle">Add New Schedule</h3>
        <input type="hidden" id="editScheduleId" value="">
        <input type="text" id="newName" placeholder="Name (e.g., Morning Weather)">
        <select id="newType">
            <option value="weather">Weather</option>
            <option value="stocks">Stocks</option>
            <option value="countdowns">Countdowns</option>
            <option value="flights">Flights</option>
            <option value="calendar">Calendar</option>
            <option value="news">News</option>
            <option value="text">Text Message</option>
        </select>
        <input type="text" id="newContent" placeholder="Message content (for text type)" style="display:none;">
        <div class="time-row">
            <label>Time:</label>
            <input type="time" id="newTime" value="08:00">
        </div>
        <label>Days:</label>
        <div class="day-picker" id="newDays">
            <button type="button" class="day-btn active" data-day="1">Mon</button>
            <button type="button" class="day-btn active" data-day="2">Tue</button>
            <button type="button" class="day-btn active" data-day="3">Wed</button>
            <button type="button" class="day-btn active" data-day="4">Thu</button>
            <button type="button" class="day-btn active" data-day="5">Fri</button>
            <button type="button" class="day-btn active" data-day="6">Sat</button>
            <button type="button" class="day-btn active" data-day="0">Sun</button>
        </div>
        <div class="btn-group">
            <button onclick="saveSchedule()">Save Schedule</button>
            <button onclick="cancelEdit()" class="secondary" id="cancelEditBtn" style="display:none;">Cancel</button>
        </div>
    </div>

    <div class="card">
        <h2>Recent Messages</h2>
        <div id="logs">Loading...</div>
    </div>

    <script>
        // Character code mapping (matches Python characters.py)
        const CHAR_CODES = {
            ' ': 0,
            'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9,
            'J': 10, 'K': 11, 'L': 12, 'M': 13, 'N': 14, 'O': 15, 'P': 16, 'Q': 17,
            'R': 18, 'S': 19, 'T': 20, 'U': 21, 'V': 22, 'W': 23, 'X': 24, 'Y': 25,
            'Z': 26,
            '1': 27, '2': 28, '3': 29, '4': 30, '5': 31, '6': 32, '7': 33, '8': 34,
            '9': 35, '0': 36,
            '!': 37, '@': 38, '#': 39, '$': 40, '(': 41, ')': 42,
            '-': 44, '+': 46, '&': 47, '=': 48, ';': 49, ':': 50,
            "'": 52, '"': 53, '%': 54, ',': 55, '.': 56,
            '/': 59, '?': 60, '°': 62
        };

        const CODE_TO_CHAR = {};
        for (const [char, code] of Object.entries(CHAR_CODES)) {
            CODE_TO_CHAR[code] = char;
        }

        const ROWS = 6;
        const COLS = 22;

        function wrapText(text, width = COLS) {
            const words = text.split(/\s+/).filter(w => w);
            const lines = [];
            let currentLine = [];
            let currentLength = 0;

            for (const word of words) {
                const wordLength = word.length;
                const spaceNeeded = currentLine.length > 0 ? 1 : 0;

                if (currentLength + wordLength + spaceNeeded <= width) {
                    currentLine.push(word);
                    currentLength += wordLength + spaceNeeded;
                } else {
                    if (currentLine.length > 0) {
                        lines.push(currentLine.join(' '));
                    }
                    currentLine = [word.substring(0, width)];
                    currentLength = Math.min(word.length, width);
                }
            }

            if (currentLine.length > 0) {
                lines.push(currentLine.join(' '));
            }

            return lines;
        }

        function textToBoard(text) {
            const board = Array(ROWS).fill(null).map(() => Array(COLS).fill(0));
            const lines = wrapText(text.toUpperCase());

            // Vertical centering
            const startRow = Math.floor((ROWS - Math.min(lines.length, ROWS)) / 2);

            for (let i = 0; i < Math.min(lines.length, ROWS); i++) {
                const line = lines[i].substring(0, COLS);
                const padding = Math.floor((COLS - line.length) / 2);

                for (let j = 0; j < line.length; j++) {
                    const char = line[j];
                    const code = CHAR_CODES[char] !== undefined ? CHAR_CODES[char] : 0;
                    board[startRow + i][padding + j] = code;
                }
            }

            return board;
        }

        function renderBoard(board, containerId) {
            const container = document.getElementById(containerId);
            container.innerHTML = '';

            for (let row = 0; row < ROWS; row++) {
                for (let col = 0; col < COLS; col++) {
                    const cell = document.createElement('div');
                    cell.className = 'board-cell';

                    const code = board[row][col];
                    const char = CODE_TO_CHAR[code] || '';

                    // Handle special color codes
                    if (code >= 63 && code <= 70) {
                        const colors = ['red', 'orange', 'yellow', 'green', 'blue', 'violet', 'white', 'black'];
                        cell.classList.add('color-' + colors[code - 63]);
                    } else if (code === 71) {
                        cell.classList.add('filled');
                    } else {
                        cell.textContent = char;
                    }

                    container.appendChild(cell);
                }
            }
        }

        function updatePreview() {
            const text = document.getElementById('message').value;
            const board = textToBoard(text);
            renderBoard(board, 'boardPreview');
        }

        // Initialize empty board
        function initBoard() {
            const emptyBoard = Array(ROWS).fill(null).map(() => Array(COLS).fill(0));
            renderBoard(emptyBoard, 'boardPreview');
        }

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

        async function sendFlights() {
            const res = await api('POST', '/message/flights');
            alert(res.success ? 'Flight info sent!' : 'Failed: ' + (res.error || 'Unknown error'));
            loadLogs();
        }

        async function loadFlights() {
            const res = await api('GET', '/flights');
            const div = document.getElementById('flights');
            if (!res.flights || res.flights.length === 0) {
                div.innerHTML = '<p>No flights being tracked.</p>';
                return;
            }
            div.innerHTML = res.flights.map(f => `
                <div class="schedule-item">
                    <div>
                        <strong>${f.flight_number}</strong><br>
                        <small>${f.flight_date} | ${f.status || 'Unknown'}</small>
                    </div>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <div class="toggle ${f.enabled ? 'active' : ''}"
                             onclick="toggleFlight(${f.id}, ${!f.enabled})"></div>
                        <button onclick="deleteFlight(${f.id})" class="danger"
                                style="width:auto;padding:5px 10px;">X</button>
                    </div>
                </div>
            `).join('');
        }

        async function toggleFlight(id, enabled) {
            await api('PUT', '/flights/' + id, { enabled });
            loadFlights();
        }

        async function deleteFlight(id) {
            if (!confirm('Delete this flight?')) return;
            await api('DELETE', '/flights/' + id);
            loadFlights();
        }

        async function addFlight() {
            const flight_number = document.getElementById('flightNumber').value;
            const flight_date = document.getElementById('flightDate').value;
            if (!flight_number || !flight_date) {
                alert('Flight number and date are required');
                return;
            }
            await api('POST', '/flights', { flight_number, flight_date });
            document.getElementById('flightNumber').value = '';
            document.getElementById('flightDate').value = '';
            loadFlights();
        }

        // Parse cron expression to human-readable format
        function parseCron(cron) {
            const parts = cron.split(' ');
            if (parts.length < 5) return cron;

            const minute = parts[0];
            const hour = parts[1];
            const dayOfWeek = parts[4];

            // Format time
            let h = parseInt(hour);
            const ampm = h >= 12 ? 'PM' : 'AM';
            h = h % 12 || 12;
            const timeStr = `${h}:${minute.padStart(2, '0')} ${ampm}`;

            // Format days
            const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            let daysStr = '';
            if (dayOfWeek === '*') {
                daysStr = 'Every day';
            } else if (dayOfWeek === '1-5') {
                daysStr = 'Weekdays';
            } else if (dayOfWeek === '0,6') {
                daysStr = 'Weekends';
            } else {
                const days = dayOfWeek.split(',').map(d => dayNames[parseInt(d)]);
                daysStr = days.join(', ');
            }

            return `${timeStr} · ${daysStr}`;
        }

        // Parse cron to get time and days for editing
        function parseCronForEdit(cron) {
            const parts = cron.split(' ');
            if (parts.length < 5) return { time: '08:00', days: ['0','1','2','3','4','5','6'] };

            const minute = parts[0].padStart(2, '0');
            const hour = parts[1].padStart(2, '0');
            const dayOfWeek = parts[4];

            const time = `${hour}:${minute}`;
            let days;
            if (dayOfWeek === '*') {
                days = ['0','1','2','3','4','5','6'];
            } else {
                days = dayOfWeek.split(',');
            }

            return { time, days };
        }

        // Edit a schedule
        function editSchedule(schedule) {
            document.getElementById('editScheduleId').value = schedule.id;
            document.getElementById('newName').value = schedule.name;
            document.getElementById('newType').value = schedule.message_type;
            document.getElementById('newContent').value = schedule.content || '';

            // Show/hide content field
            updateContentVisibility();

            // Parse cron and set time/days
            const { time, days } = parseCronForEdit(schedule.cron_expression);
            document.getElementById('newTime').value = time;

            // Set day buttons
            document.querySelectorAll('#newDays .day-btn').forEach(btn => {
                if (days.includes(btn.dataset.day)) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            // Update UI
            document.getElementById('scheduleFormTitle').textContent = 'Edit Schedule';
            document.getElementById('cancelEditBtn').style.display = 'block';

            // Scroll to form
            document.getElementById('scheduleFormTitle').scrollIntoView({ behavior: 'smooth' });
        }

        function cancelEdit() {
            document.getElementById('editScheduleId').value = '';
            document.getElementById('newName').value = '';
            document.getElementById('newType').value = 'weather';
            document.getElementById('newContent').value = '';
            document.getElementById('newTime').value = '08:00';

            // Reset all day buttons to active
            document.querySelectorAll('#newDays .day-btn').forEach(btn => btn.classList.add('active'));

            document.getElementById('scheduleFormTitle').textContent = 'Add New Schedule';
            document.getElementById('cancelEditBtn').style.display = 'none';
            updateContentVisibility();
        }

        function updateContentVisibility() {
            const type = document.getElementById('newType').value;
            const contentField = document.getElementById('newContent');
            contentField.style.display = type === 'text' ? 'block' : 'none';
        }

        async function loadSchedules() {
            const res = await api('GET', '/schedules');
            const div = document.getElementById('schedules');
            if (!res.schedules || res.schedules.length === 0) {
                div.innerHTML = '<p>No schedules configured. Add one below!</p>';
                return;
            }
            // Store schedules for editing
            window.schedulesData = res.schedules;

            div.innerHTML = res.schedules.map((s, idx) => `
                <div class="schedule-item">
                    <div onclick="editSchedule(window.schedulesData[${idx}])" style="cursor:pointer;flex:1;">
                        <strong>${s.name}</strong><br>
                        <small>${s.message_type} · ${parseCron(s.cron_expression)}</small>
                    </div>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <div class="toggle ${s.enabled ? 'active' : ''}"
                             onclick="event.stopPropagation();toggleSchedule(${s.id}, ${!s.enabled})"></div>
                        <button onclick="event.stopPropagation();deleteSchedule(${s.id})" class="danger"
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

        async function saveSchedule() {
            const editId = document.getElementById('editScheduleId').value;
            const name = document.getElementById('newName').value;
            const messageType = document.getElementById('newType').value;
            const content = document.getElementById('newContent').value;
            const time = document.getElementById('newTime').value;

            if (!name) {
                alert('Name is required');
                return;
            }
            if (!time) {
                alert('Time is required');
                return;
            }

            // Get selected days
            const dayBtns = document.querySelectorAll('#newDays .day-btn.active');
            const days = Array.from(dayBtns).map(btn => btn.dataset.day);

            if (days.length === 0) {
                alert('Select at least one day');
                return;
            }

            // Build cron expression: minute hour * * days
            const [hour, minute] = time.split(':');
            let dayExpr;
            if (days.length === 7) {
                dayExpr = '*';
            } else {
                dayExpr = days.sort().join(',');
            }
            const cronExpression = `${parseInt(minute)} ${parseInt(hour)} * * ${dayExpr}`;

            const data = {
                name,
                message_type: messageType,
                content: messageType === 'text' ? content : null,
                cron_expression: cronExpression
            };

            if (editId) {
                // Update existing
                await api('PUT', '/schedules/' + editId, data);
            } else {
                // Create new
                await api('POST', '/schedules', data);
            }

            // Reset form
            cancelEdit();
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

        // Day button click handlers
        document.querySelectorAll('#newDays .day-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                btn.classList.toggle('active');
            });
        });

        // Show/hide content field based on message type
        document.getElementById('newType').addEventListener('change', updateContentVisibility);

        // Load data on page load
        initBoard();
        loadSchedules();
        loadCountdowns();
        loadFlights();
        loadLogs();
        updateContentVisibility();
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


# ========== Flight Tracking ==========

@app.route("/api/message/flights", methods=["POST"])
def api_send_flights():
    """Send flight status to the Vestaboard."""
    from datetime import date
    fetcher = FlightFetcher(storage=storage)
    flights = storage.get_flights(enabled_only=True, include_past=False)

    if not flights:
        return jsonify({"success": False, "error": "No flights being tracked"})

    # Get the first tracked flight
    tracked_flight = flights[0]
    today = date.today()

    # Check if flight is in the future (API won't have data)
    if tracked_flight.flight_date > today:
        days_until = (tracked_flight.flight_date - today).days
        lines = [
            "FLIGHT TRACKER",
            "",
            tracked_flight.flight_number,
            "",
            f"DEPARTS IN {days_until} DAYS",
            tracked_flight.flight_date.strftime("%b %d").upper()
        ]
        success = client.send_lines(lines)
        storage.log_message("flights", "\n".join(lines), success)
        return jsonify({"success": success})

    # Today's flight - fetch live status
    flight_status = fetcher.fetch(tracked_flight.flight_number, tracked_flight.flight_date)

    if not flight_status:
        return jsonify({"success": False, "error": "Could not fetch flight status"})

    lines = fetcher.format_for_board(flight_status, tracked_flight)
    success = client.send_lines(lines)
    storage.log_message("flights", "\n".join(lines), success)

    return jsonify({"success": success})


@app.route("/api/flights", methods=["GET"])
def api_get_flights():
    """Get all tracked flights with their current status."""
    from datetime import date
    flights = storage.get_flights(include_past=False)
    today = date.today()

    # Optionally fetch live status for each flight
    fetcher = FlightFetcher(storage=storage)

    result = []
    for f in flights:
        flight_data = {
            "id": f.id,
            "flight_number": f.flight_number,
            "flight_date": f.flight_date.isoformat(),
            "enabled": f.enabled,
            "status": None
        }

        # Try to get live status (only for today's flights - API doesn't have future data)
        if f.enabled:
            if f.flight_date > today:
                # Future flight - API won't have data yet
                days_until = (f.flight_date - today).days
                flight_data["status"] = f"Upcoming ({days_until}d)"
            else:
                status = fetcher.fetch(f.flight_number, f.flight_date)
                if status:
                    flight_data["status"] = status.status.title()
                else:
                    flight_data["status"] = "Not found"

        result.append(flight_data)

    return jsonify({"flights": result})


@app.route("/api/flights", methods=["POST"])
def api_create_flight():
    """Create a new tracked flight."""
    from datetime import date
    data = request.get_json() or {}

    try:
        flight_date = date.fromisoformat(data.get("flight_date", ""))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format"}), 400

    flight = TrackedFlight(
        id=None,
        flight_number=data.get("flight_number", "").upper(),
        flight_date=flight_date,
        enabled=data.get("enabled", True)
    )

    flight_id = storage.save_flight(flight)
    return jsonify({"success": True, "id": flight_id})


@app.route("/api/flights/<int:flight_id>", methods=["PUT"])
def api_update_flight(flight_id: int):
    """Update a tracked flight."""
    from datetime import date
    data = request.get_json() or {}

    flight = storage.get_flight(flight_id)
    if not flight:
        return jsonify({"success": False, "error": "Not found"}), 404

    if "flight_number" in data:
        flight.flight_number = data["flight_number"].upper()
    if "flight_date" in data:
        try:
            flight.flight_date = date.fromisoformat(data["flight_date"])
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format"}), 400
    if "enabled" in data:
        flight.enabled = data["enabled"]

    storage.save_flight(flight)
    return jsonify({"success": True})


@app.route("/api/flights/<int:flight_id>", methods=["DELETE"])
def api_delete_flight(flight_id: int):
    """Delete a tracked flight."""
    deleted = storage.delete_flight(flight_id)
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
