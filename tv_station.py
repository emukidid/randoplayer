import os
import random
import json
import threading
import subprocess
import time
import re
from flask import Flask, render_template_string, jsonify, Markup
from datetime import datetime, timedelta

# === CONFIGURATION ===
MEDIA_ROOT = "/mnt/tvdrive/tv"
SCHEDULE_FILE = "/home/sdplayer/schedule.json"
STATE_FILE = "/home/sdplayer/current.json"
DURATION_CACHE = "/home/sdplayer/durations.json"
PORT = 8080

# === HTML TEMPLATE ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Pi TV Station</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: sans-serif; background: #111; color: #eee; padding: 2em; position: relative; }
        h1 { color: #f90; }
        .now { font-size: 1.5em; margin-bottom: 1em; }
        .upnext { font-size: 1.2em; margin-bottom: 2em; }
        .clock { position: absolute; top: 20px; right: 20px; font-size: 1.2em; color: #0f0; }
        .timeline { display: flex; align-items: center; margin-bottom: 2em; overflow-x: auto; padding: 1em; background: #222; }
        .block { margin-right: 10px; text-align: center; }
        .bar { height: 20px; background: #4caf50; margin-bottom: 5px; }
        .nowbar { background: #2196f3; }
        .uplater { margin-top: 2em; }
        ul { list-style: none; padding: 0; }
        li { margin: 0.3em 0; }
    </style>
</head>
<body>
    <div class="clock">{{ current_time }}</div>
    <h1>📺 Pi TV Station</h1>
    <div class="now"><strong>Now Playing:</strong> {{ show }}<br><em>{{ now }}</em></div>
    <div class="upnext"><strong>Up Next:</strong> {{ upnext }}</div>

	<h2>Timeline</h2>
	<div style="position: relative; height: 30px; background: #333; margin-bottom: 10px;">
		{% for tick in hour_ticks %}
			<div style="position: absolute; left: {{ tick.position }}; top: 0; height: 100%; border-left: 1px solid #888; font-size: 12px; padding-left: 2px; color: #ccc;">
				{{ tick.label }}
			</div>
		{% endfor %}
		<div style="position: absolute; left: {{ now_percent }}; top: 0; height: 100%; width: 2px; background: #f00; box-shadow: 0 0 5px #f00;"></div>
	</div>

	<div class="timeline">
		{% for item in timeline %}
			<div class="block">
				<div class="bar" style="width:{{ item.width }}px; background:{{ item.color }};"></div>
				<div>{{ item.label }}</div>
			</div>
		{% endfor %}
	</div>

    {% if uplater %}
    <div class="uplater">
        <h2>Up Later</h2>
        <ul>
            {% for item in uplater %}
                <li>{{ item }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}
</body>
</html>
"""

# === SCHEDULE GENERATION ===
def format_episode(path):
    folder = os.path.basename(os.path.dirname(path))
    file = os.path.basename(path)

    # Remove extension
    file = os.path.splitext(file)[0]

    # Remove folder name prefix if present
    if file.lower().startswith(folder.lower()):
        file = file[len(folder):].lstrip(" -_")

    # Remove junk tags like Bluray-1080p, x264, etc.
    file = re.sub(r'\b(bluray|1080p|720p|x264|x265|webrip|dvdrip|hdtv|aac|mp3|hdrip|xvid|lol|vtv|sdtv|sickbeard)\b', '', file, flags=re.IGNORECASE)
    file = re.sub(r'[\[\]\(\)\-_]+', ' ', file)  # Clean up leftover symbols
    file = re.sub(r'\s{2,}', ' ', file).strip()  # Collapse multiple spaces
    # Remove trailing dots and spaces
    file = re.sub(r'[.\s]+$', '', file)
    # Remove leading dots/spaces
    file = re.sub(r'^[.\s]+', '', file)

    return f"{folder} - {file}"

def get_duration(filepath):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except:
        return None

def update_duration_cache(schedule, current_index):
    try:
        with open(DURATION_CACHE) as f:
            durations = json.load(f)
    except:
        durations = {}

    next_batch = schedule[current_index + 1 : current_index + 6]
    for path in next_batch:
        base = os.path.basename(path)
        if base not in durations:
            dur = get_duration(path)
            if dur:
                durations[base] = dur

    with open(DURATION_CACHE, "w") as f:
        json.dump(durations, f, indent=2)


def get_commercials():
    commercials_dir = os.path.join(MEDIA_ROOT, "commercials")
    if not os.path.isdir(commercials_dir):
        return []
    return [os.path.join(commercials_dir, f) for f in os.listdir(commercials_dir)
            if f.lower().endswith(('.mp4', '.avi', '.mkv'))]

def generate_schedule():
    schedule = []
    for show in os.listdir(MEDIA_ROOT):
        show_path = os.path.join(MEDIA_ROOT, show)
        if os.path.isdir(show_path) and show != "commercials":
            episodes = [os.path.join(show_path, ep) for ep in os.listdir(show_path)
                        if ep.lower().endswith(('.mp4', '.avi', '.mkv'))]
            schedule.extend(episodes)

    random.shuffle(schedule)
    commercials = get_commercials()

    # Interleave commercials
    final_schedule = []
    for episode in schedule:
        final_schedule.append(episode)
        if commercials:
            final_schedule.append(random.choice(commercials))

    with open(SCHEDULE_FILE, "w") as f:
        json.dump(final_schedule, f)
    return final_schedule

# === PLAYER THREAD ===
def play_schedule():
    while True:
        with open(SCHEDULE_FILE) as f:
            schedule = json.load(f)
        for i, episode in enumerate(schedule):
            now = os.path.basename(episode)
            show = os.path.basename(os.path.dirname(episode))
            upnext = os.path.basename(schedule[i+1]) if i + 1 < len(schedule) else os.path.basename(schedule[0])
            start_time = datetime.now().isoformat()
            with open(STATE_FILE, "w") as f:
                json.dump({"now": now, "upnext": upnext, "show": show, "start_time": start_time}, f)
            update_duration_cache(schedule, i)
            subprocess.run(["cvlc", "--aspect-ratio=16:9", "--aout", "alsa", "--play-and-exit", "--fullscreen", episode])

# === FLASK SERVER ===
app = Flask(__name__)

@app.route("/")
def index():
    try:
        with open(SCHEDULE_FILE) as f:
            full_schedule = json.load(f)
        with open(STATE_FILE) as f:
            state = json.load(f)
        try:
            with open(DURATION_CACHE) as f:
                duration_map = json.load(f)
        except:
            duration_map = {}

        now_file = state.get("now")
        now_start_str = state.get("start_time")
        now_start = datetime.fromisoformat(now_start_str) if now_start_str else datetime.now()
        current_time = datetime.now().strftime("%H:%M:%S")

        try:
            current_index = full_schedule.index(
                next(ep for ep in full_schedule if os.path.basename(ep) == now_file)
            )
        except StopIteration:
            current_index = 0

        rotated = full_schedule[current_index:] + full_schedule[:current_index]
        timeline = []
        uplater = []

        cursor = now_start
        for i, ep in enumerate(rotated[:10]):
            base = os.path.basename(ep)
            dur = duration_map.get(base)
            if dur:
                width = int(dur // 6)  # scale factor for visual width
                color = "#2196f3" if i == 0 else "#4caf50"
                label = format_episode(ep) + f" ({int(dur // 60)} min)"
                timeline.append({"width": width, "color": color, "label": label})
                cursor += timedelta(seconds=dur)
            else:
                uplater.append(format_episode(ep))

        # Calculate total timeline duration
        total_seconds = sum(block["width"] * 6 for block in timeline)  # width = dur // 6
        timeline_start = now_start
        timeline_end = timeline_start + timedelta(seconds=total_seconds)
        
        # Generate hour ticks
        hour_ticks = []
        tick_cursor = timeline_start.replace(minute=0, second=0, microsecond=0)
        while tick_cursor <= timeline_end:
            seconds_from_start = (tick_cursor - timeline_start).total_seconds()
            percent = (seconds_from_start / total_seconds) * 100
            hour_ticks.append({
                "label": tick_cursor.strftime("%H:%M"),
                "position": f"{percent:.2f}%"
            })
            tick_cursor += timedelta(hours=1)

        # Current time marker
        now_seconds = (datetime.now() - timeline_start).total_seconds()
        now_percent = max(0, min(100, (now_seconds / total_seconds) * 100))

        now_dur = duration_map.get(now_file)
        if now_dur and now_start:
            now_end = now_start + timedelta(seconds=now_dur)
            time_until_next = (now_end - datetime.now()).total_seconds()
            countdown = str(timedelta(seconds=int(time_until_next))) if time_until_next > 0 else "Starting soon"
            now_display = Markup(f"{format_episode(now_file)}")
        else:
            now_display = state["now"]
            countdown = "Unknown"

        upnext_display = Markup(f"{format_episode(state['upnext'])} (in {countdown})")

    except Exception as e:
        timeline = []
        uplater = []
        now_display = "Loading..."
        upnext_display = "Loading..."
        current_time = "Unknown"
        state = {"show": "Unknown"}

    return render_template_string(
        HTML_TEMPLATE,
        now=now_display,
        upnext=upnext_display,
        show=state.get("show", "Unknown"),
        timeline=timeline,
        uplater=uplater,
        current_time=current_time,
        hour_ticks=hour_ticks,
        now_percent=f"{now_percent:.2f}%"
    )

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

