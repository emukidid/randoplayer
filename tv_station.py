import os
import random
import json
import threading
import subprocess
import time
from flask import Flask, render_template_string, jsonify

# === CONFIGURATION ===
MEDIA_ROOT = "/mnt/tvdrive/tv"
SCHEDULE_FILE = "/home/sdplayer/schedule.json"
STATE_FILE = "/home/sdplayer/current.json"
PORT = 8080

# === HTML TEMPLATE ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Pi TV Station</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: sans-serif; background: #111; color: #eee; padding: 2em; }
        h1 { color: #f90; }
        .now { font-size: 1.5em; margin-bottom: 1em; }
        .upnext { font-size: 1.2em; margin-bottom: 2em; }
        ul { list-style: none; padding: 0; }
        li { margin: 0.3em 0; }
    </style>
</head>
<body>
    <h1>📺 Pi TV Station</h1>
    <div class="now"><strong>Now Playing:</strong> {{ show }}<br><em>{{ now }}</em></div>
    <div class="upnext"><strong>Up Next:</strong> {{ upnext }}</div>
    <h2>Schedule</h2>
    <ul>
        {% for item in schedule %}
            <li>{{ item }}</li>
        {% endfor %}
    </ul>
</body>
</html>
"""

# === SCHEDULE GENERATION ===
def generate_schedule():
    schedule = []
    for show in os.listdir(MEDIA_ROOT):
        show_path = os.path.join(MEDIA_ROOT, show)
        if os.path.isdir(show_path):
            episodes = [os.path.join(show_path, ep) for ep in os.listdir(show_path) if ep.lower().endswith(('.mp4', '.avi', '.mkv'))]
            schedule.extend(episodes)
    random.shuffle(schedule)
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f)
    return schedule

# === PLAYER THREAD ===
def play_schedule():
    while True:
        with open(SCHEDULE_FILE) as f:
            schedule = json.load(f)
        for i, episode in enumerate(schedule):
            now = os.path.basename(episode)
            show = os.path.basename(os.path.dirname(episode))
            upnext = os.path.basename(schedule[i+1]) if i + 1 < len(schedule) else "End of Schedule"
            with open(STATE_FILE, "w") as f:
                json.dump({"now": now, "upnext": upnext, "show": show}, f)
            subprocess.run(["cvlc", "--aspect-ratio=16:9", "--aout", "alsa", "--play-and-exit", "--fullscreen", episode])

# === FLASK SERVER ===
app = Flask(__name__)

@app.route("/")
def index():
    try:
        with open(SCHEDULE_FILE) as f:
            schedule = [os.path.basename(ep) for ep in json.load(f)]
        with open(STATE_FILE) as f:
            state = json.load(f)
    except:
        schedule = []
        state = {"now": "Loading...", "upnext": "Loading..."}
    return render_template_string(HTML_TEMPLATE, now=state["now"], upnext=state["upnext"], show=state.get("show", "Unknown"), schedule=schedule)

@app.route("/now")
def now():
    try:
        with open(STATE_FILE) as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"now": "Unknown", "upnext": "Unknown"})

# === MAIN ===
if __name__ == "__main__":
    schedule = generate_schedule()
    threading.Thread(target=play_schedule, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)

