#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import urllib.parse
import subprocess
import datetime

PORT = 8000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
AGENT_IO_DIR = os.path.join(WORKSPACE_DIR, "agent_io")
CONFIG_HARNESS_DIR = os.path.join(WORKSPACE_DIR, "config_harness")

def read_json_file(file_path, default_val=None):
    if default_val is None:
        default_val = {}
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error reading JSON file at {file_path}: {e}")
    return default_val

def read_raw_text(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        return f"Error reading file: {e}"
    return "File does not exist."

def read_env_config():
    env_path = os.path.join(WORKSPACE_DIR, ".env")
    config = {}
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        parts = line.split("=", 1)
                        key = parts[0].strip()
                        val = parts[1].strip()
                        if val.startswith('"') and val.endsWith('"'): val = val[1:-1]
                        elif val.startswith("'") and val.endswith("'"): val = val[1:-1]
                        config[key] = val
    except Exception as e:
        print(f"Error reading .env file: {e}")
    return config

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging each HTTP request to stdout to keep console clean
        pass

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif path == "/api/status":
            self.handle_api_status()
        elif path == "/api/events":
            self.handle_api_events()
        elif path == "/api/summaries":
            self.handle_api_summaries()
        elif path == "/api/prompts":
            self.handle_api_prompts()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        if path == "/api/prompts":
            self.handle_post_prompts(body)
        elif path == "/api/run-script":
            self.handle_run_script(body)
        else:
            self.send_error(404, "Not Found")

    def send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def handle_api_status(self):
        status_file = os.path.join(AGENT_IO_DIR, "status.json")
        github_status_file = os.path.join(AGENT_IO_DIR, "github_status.json")
        jira_status_file = os.path.join(AGENT_IO_DIR, "jira_status.json")
        scheduler_status_file = os.path.join(AGENT_IO_DIR, "scheduler_status.json")

        system_status = read_json_file(status_file, {"last_ts": "", "mode": "normal"})
        github_status = read_json_file(github_status_file, {"last_id": ""})
        jira_status = read_json_file(jira_status_file, {"last_updated": ""})
        scheduler_status = read_json_file(scheduler_status_file, {"last_run": ""})
        env_config = read_env_config()

        response_data = {
            "orchestrator": {
                "mode": system_status.get("mode", "normal"),
                "last_ts": system_status.get("last_ts", None),
                "loop_interval": env_config.get("LOOP_INTERVAL", "10"),
                "active_interval": env_config.get("ACTIVE_INTERVAL", "7200")
            },
            "integrations": {
                "github": {
                    "repo": env_config.get("GITHUB_REPO", "Not configured"),
                    "last_id": github_status.get("last_id", None)
                },
                "jira": {
                    "project_key": env_config.get("JIRA_PROJECT_KEY", "Not configured"),
                    "domain": env_config.get("JIRA_DOMAIN", "Not configured"),
                    "last_updated": jira_status.get("last_updated", None)
                },
                "slack": {
                    "channel_id": env_config.get("SLACK_CHANNEL_ID", "Not configured"),
                    "has_token": bool(env_config.get("SLACK_BOT_TOKEN"))
                }
            },
            "scheduler": {
                "last_run": scheduler_status.get("last_run", None)
            },
            "raw": {
                "status_json": system_status,
                "github_status_json": github_status,
                "jira_status_json": jira_status,
                "scheduler_status_json": scheduler_status,
                "env_config": {k: ("*" * 8 if "TOKEN" in k or "SECRET" in k or "PASSWORD" in k else v) for k, v in env_config.items()}
            }
        }
        self.send_json(response_data)

    def handle_api_events(self):
        memory_dir = os.path.join(AGENT_IO_DIR, "memory")
        events = []
        raw_lines = []

        try:
            if os.path.exists(memory_dir):
                dates = [d for d in os.listdir(memory_dir) 
                         if os.path.isdir(os.path.join(memory_dir, d)) and len(d) == 10]
                
                # Sort dates descending to get newest files
                dates.sort(reverse=True)
                
                for date in dates:
                    history_file = os.path.join(memory_dir, date, "raw_history.jsonl")
                    if os.path.exists(history_file):
                        with open(history_file, "r", encoding="utf-8") as f:
                            for line in f:
                                stripped = line.strip()
                                if stripped:
                                    raw_lines.append(f"[{date}] {stripped}")
                                    try:
                                        ev = json.loads(stripped)
                                        ev["date"] = date
                                        events.append(ev)
                                    except Exception:
                                        pass
        except Exception as e:
            print(f"Error listing events: {e}")

        # Sorting function based on timestamp (newest first)
        def get_ts(ev):
            try:
                if "ts" in ev: return float(ev["ts"])
                if "event_ts" in ev: return float(ev["event_ts"])
                if "fields" in ev and "updated" in ev["fields"]:
                    dt_str = ev["fields"]["updated"][:19]
                    return datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").timestamp()
            except Exception:
                pass
            return 0.0

        events.sort(key=get_ts, reverse=True)
        
        # Limit raw_lines to latest 100 for token/size limits
        self.send_json({
            "parsed": events[:100],
            "raw": "\n".join(raw_lines[:100]) if raw_lines else "No raw history logs found."
        })

    def handle_api_summaries(self):
        memory_dir = os.path.join(AGENT_IO_DIR, "memory")
        summaries = []

        try:
            if os.path.exists(memory_dir):
                dates = [d for d in os.listdir(memory_dir) 
                         if os.path.isdir(os.path.join(memory_dir, d)) and len(d) == 10]
                
                for date in dates:
                    summary_file = os.path.join(memory_dir, date, "daily_summary.md")
                    if os.path.exists(summary_file):
                        with open(summary_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            summaries.append({
                                "date": date,
                                "content": content
                            })
        except Exception as e:
            print(f"Error listing summaries: {e}")

        summaries.sort(key=lambda x: x["date"], reverse=True)
        self.send_json(summaries)

    def handle_api_prompts(self):
        prompts_dir = os.path.join(CONFIG_HARNESS_DIR, "subagent_prompts")
        prompts = {}

        try:
            if os.path.exists(prompts_dir):
                files = [f for f in os.listdir(prompts_dir) if f.endswith(".txt")]
                for file in files:
                    with open(os.path.join(prompts_dir, file), "r", encoding="utf-8") as f:
                        prompts[file] = f.read()
        except Exception as e:
            print(f"Error reading prompts: {e}")

        self.send_json(prompts)

    def handle_post_prompts(self, body):
        filename = body.get("filename")
        content = body.get("content")

        if not filename or content is None:
            self.send_json({"error": "Filename and content are required"}, 400)
            return

        safe_filename = os.path.basename(filename)
        if not safe_filename.endswith(".txt"):
            self.send_json({"error": "Only .txt files are allowed"}, 400)
            return

        prompts_dir = os.path.join(CONFIG_HARNESS_DIR, "subagent_prompts")
        prompt_file = os.path.join(prompts_dir, safe_filename)

        try:
            os.makedirs(prompts_dir, exist_ok=True)
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(content)

            self.send_json({
                "success": True,
                "message": f"Prompt {safe_filename} updated successfully in the workspace.",
                "syncOutput": "Direct execution mode is active. Changes are applied instantly."
            })
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_run_script(self, body):
        script_key = body.get("script")
        
        if script_key == "sync_configs":
            self.send_json({
                "success": True,
                "cmd": "sync_configs",
                "exit_code": 0,
                "stdout": "이 프로젝트는 2-레포 구조로 개편되어 더 이상 동기화(sync_configs.sh)가 필요 없습니다. 로컬 설정이 즉시 반영됩니다.",
                "stderr": ""
            })
            return

        script_mapping = {
            "slack_client": "app/slack_client.sh",
            "github_client": "app/github_client.sh",
            "jira_client": "app/jira_client.sh",
            "daily_scheduler": "app/daily_scheduler.sh",
            "daily_compressor": "app/daily_compressor.sh",
            "mock_slack": "tests/mock_slack_trigger.sh"
        }

        if not script_key or script_key not in script_mapping:
            self.send_json({"error": "Invalid or missing script key"}, 400)
            return

        rel_path = script_mapping[script_key]
        abs_path = os.path.join(WORKSPACE_DIR, rel_path)

        if not os.path.exists(abs_path):
            self.send_json({"error": f"Script not found at: {rel_path}"}, 404)
            return

        try:
            print(f"[Dashboard Handler] Running script: bash {rel_path}...")
            # Run bash script with workspace dir as cwd
            res = subprocess.run(["bash", abs_path], capture_output=True, text=True, cwd=WORKSPACE_DIR)
            
            self.send_json({
                "success": True,
                "cmd": f"bash {rel_path}",
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            })
        except Exception as e:
            self.send_json({
                "success": False,
                "error": str(e)
            }, 500)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

# Premium responsive single-page visual management console HTML/JS/CSS code
HTML_CONTENT = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>가상 호주 오피스 | 실시간 대시보드</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #060913;
            --text-color: #f8fafc;
            --text-muted: #64748b;
            --border-color: rgba(255, 255, 255, 0.06);
            --card-bg: rgba(15, 23, 42, 0.6);
            --card-hover: rgba(30, 41, 59, 0.8);
            --primary: #6366f1;
            --primary-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --accent: #a855f7;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --font-family: 'Plus Jakarta Sans', sans-serif;
            --font-heading: 'Outfit', sans-serif;
        }

        [data-theme="light"] {
            --bg-color: #f1f5f9;
            --text-color: #0f172a;
            --text-muted: #64748b;
            --border-color: rgba(0, 0, 0, 0.08);
            --card-bg: rgba(255, 255, 255, 0.8);
            --card-hover: rgba(241, 245, 249, 0.9);
            --primary: #4f46e5;
            --primary-gradient: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%);
            --accent: #9333ea;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: var(--font-family);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.05);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        /* Sidebar Styling */
        aside {
            width: 260px;
            background: rgba(8, 12, 24, 0.4);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            padding: 24px;
            position: fixed;
            height: 100vh;
            z-index: 100;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 36px;
        }

        .logo-icon {
            width: 36px;
            height: 36px;
            background: var(--primary-gradient);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.1rem;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .logo-text {
            font-family: var(--font-heading);
            font-weight: 700;
            font-size: 1.1rem;
            letter-spacing: -0.5px;
        }

        .logo-text span {
            color: var(--accent);
        }

        .nav-menu {
            display: flex;
            flex-direction: column;
            gap: 8px;
            list-style: none;
            flex-grow: 1;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            border-radius: 12px;
            color: var(--text-muted);
            text-decoration: none;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .nav-item:hover, .nav-item.active {
            color: var(--text-color);
            background: var(--card-hover);
        }

        .nav-item.active {
            background: var(--primary-gradient);
            color: white;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
        }

        .nav-item svg {
            width: 18px;
            height: 18px;
            stroke: currentColor;
            fill: none;
            stroke-width: 2;
        }

        .theme-toggle-area {
            border-top: 1px solid var(--border-color);
            padding-top: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .theme-toggle-btn {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 6px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.8rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }

        .theme-toggle-btn:hover {
            background: var(--card-hover);
        }

        /* Main View */
        main {
            margin-left: 260px;
            flex-grow: 1;
            padding: 40px;
            min-height: 100vh;
            max-width: 1300px;
            width: calc(100% - 260px);
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }

        .header-title h1 {
            font-family: var(--font-heading);
            font-weight: 700;
            font-size: 1.8rem;
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }

        .header-title p {
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .refresh-btn {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 18px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-color);
            font-weight: 600;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }

        .refresh-btn:hover {
            background: var(--card-hover);
            border-color: rgba(255,255,255,0.15);
        }

        .refresh-btn svg {
            width: 15px;
            height: 15px;
            stroke: currentColor;
            stroke-width: 2.5;
            fill: none;
        }

        /* Views Toggle Buttons */
        .view-toggle-container {
            display: flex;
            gap: 4px;
            background: rgba(0, 0, 0, 0.2);
            padding: 4px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .view-toggle-btn {
            background: none;
            border: none;
            padding: 6px 12px;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-muted);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .view-toggle-btn.active {
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-color);
        }

        /* Status Grid */
        .status-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 28px;
        }

        .status-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            position: relative;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .status-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--primary);
            border-top-left-radius: 16px;
            border-bottom-left-radius: 16px;
        }

        .status-card.active-state::before { background: var(--success); }
        .status-card.idle-state::before { background: var(--warning); }
        .status-card.error-state::before { background: var(--danger); }

        .status-card .card-title {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 700;
        }

        .status-card .card-value {
            font-family: var(--font-heading);
            font-size: 1.3rem;
            font-weight: 700;
        }

        .status-card .card-desc {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        /* Panels */
        .panel {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 28px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            margin-bottom: 28px;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
        }

        .panel-title {
            font-family: var(--font-heading);
            font-weight: 600;
            font-size: 1.15rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel-title svg {
            width: 18px;
            height: 18px;
            stroke: var(--primary);
            fill: none;
            stroke-width: 2;
        }

        /* Raw Text / JSON Preview */
        .raw-preview {
            background: #04060a;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 18px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.82rem;
            color: #38bdf8;
            white-space: pre-wrap;
            overflow-x: auto;
            max-height: 500px;
            display: none;
        }

        .raw-preview.active {
            display: block;
        }

        .parsed-container {
            display: none;
        }

        .parsed-container.active {
            display: block;
        }

        /* Timeline styling */
        .timeline {
            position: relative;
            padding-left: 20px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            max-height: 580px;
            overflow-y: auto;
            padding-right: 8px;
        }

        .timeline::before {
            content: '';
            position: absolute;
            left: 5px;
            top: 8px;
            bottom: 8px;
            width: 2px;
            background: var(--border-color);
        }

        .timeline-item {
            position: relative;
            padding-left: 16px;
        }

        .timeline-dot {
            position: absolute;
            left: -20px;
            top: 6px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--text-muted);
            border: 2px solid var(--bg-color);
            box-shadow: 0 0 0 2px var(--border-color);
        }

        .timeline-item.slack .timeline-dot { background: var(--primary); }
        .timeline-item.github .timeline-dot { background: #3b82f6; }
        .timeline-item.jira .timeline-dot { background: #0ea5e9; }
        .timeline-item.system .timeline-dot { background: var(--success); }

        .timeline-card {
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            transition: all 0.2s ease;
        }

        .timeline-card:hover {
            background: rgba(255, 255, 255, 0.03);
            border-color: rgba(255, 255, 255, 0.1);
        }

        .timeline-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            margin-bottom: 8px;
        }

        .source-tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.65rem;
            text-transform: uppercase;
        }

        .source-tag.slack { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
        .source-tag.github { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
        .source-tag.jira { background: rgba(14, 165, 233, 0.15); color: #38bdf8; }
        .source-tag.system { background: rgba(16, 185, 129, 0.15); color: #34d399; }

        .timeline-time {
            color: var(--text-muted);
        }

        .timeline-user {
            font-weight: 600;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.95rem;
        }

        .bot-avatar {
            font-size: 1.15rem;
        }

        .timeline-text {
            font-size: 0.9rem;
            line-height: 1.5;
            color: var(--text-color);
            word-break: break-word;
        }

        /* Script Panel Grid */
        .script-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }

        .script-card {
            background: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 12px;
            transition: all 0.2s;
        }

        .script-card:hover {
            background: var(--card-hover);
            border-color: rgba(99, 102, 241, 0.25);
        }

        .script-info h3 {
            font-family: var(--font-heading);
            font-size: 1rem;
            margin-bottom: 4px;
        }

        .script-info p {
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.4;
        }

        .run-btn {
            background: var(--primary-gradient);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 700;
            font-family: var(--font-heading);
            font-size: 0.8rem;
            cursor: pointer;
            align-self: flex-start;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 4px 10px rgba(99, 102, 241, 0.2);
            transition: all 0.2s;
        }

        .run-btn:hover {
            opacity: 0.95;
            transform: translateY(-1px);
        }

        .run-btn.running {
            background: #475569;
            cursor: not-allowed;
            pointer-events: none;
            box-shadow: none;
        }

        .run-btn.running span::after {
            content: 'ing...';
        }

        .run-btn.running svg {
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            100% { transform: rotate(360deg); }
        }

        /* Console Display Box */
        .console-box {
            background: #020408;
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.82rem;
            color: #22d3ee;
            height: 350px;
            overflow-y: auto;
            white-space: pre-wrap;
            position: relative;
        }

        .console-box-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            padding-bottom: 10px;
            margin-bottom: 12px;
            color: var(--text-muted);
            font-family: var(--font-family);
            font-size: 0.75rem;
        }

        /* Prompts Configuration Layout */
        .prompts-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        .prompt-card {
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .prompt-card:hover {
            background: var(--card-hover);
            transform: translateY(-2px);
            border-color: rgba(99, 102, 241, 0.3);
        }

        .prompt-card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .prompt-card-avatar {
            width: 40px;
            height: 40px;
            background: rgba(255,255,255,0.03);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            border: 1px solid var(--border-color);
        }

        .prompt-card-name {
            font-family: var(--font-heading);
            font-weight: 700;
            font-size: 1.05rem;
        }

        .prompt-card-role {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .prompt-card-desc {
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.45;
        }

        /* Modal Details */
        .modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(10px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.25s ease;
        }

        .modal.open {
            display: flex;
            opacity: 1;
        }

        .modal-content {
            background: #090e1a;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            width: 100%;
            max-width: 800px;
            padding: 32px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
            transform: scale(0.96);
            transition: transform 0.2s ease;
        }

        .modal.open .modal-content {
            transform: scale(1);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-close:hover {
            color: var(--text-color);
        }

        .form-control {
            width: 100%;
            background: rgba(0, 0, 0, 0.25);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 12px;
            color: var(--text-color);
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
        }

        .form-control:focus {
            border-color: var(--primary);
        }

        /* Daily Summary Layout */
        .summary-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .summary-item {
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
        }

        .summary-header {
            padding: 16px 24px;
            background: rgba(255, 255, 255, 0.03);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            font-weight: 700;
            font-family: var(--font-heading);
        }

        .summary-body {
            padding: 24px;
            border-top: 1px solid var(--border-color);
            line-height: 1.6;
            font-size: 0.9rem;
            display: none;
        }

        .summary-item.open .summary-body {
            display: block;
        }

        .view-section {
            display: none;
        }

        .view-section.active {
            display: block;
        }
    </style>
</head>
<body>

    <!-- Sidebar navigation -->
    <aside>
        <div class="logo-area">
            <div class="logo-icon">🇦🇺</div>
            <div class="logo-text">Virtual<span>Office</span></div>
        </div>

        <nav class="nav-menu">
            <div class="nav-item active" onclick="switchView('dashboard')">
                <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>
                실시간 모니터
            </div>
            <div class="nav-item" onclick="switchView('scripts')">
                <svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                스크립트 수동 실행
            </div>
            <div class="nav-item" onclick="switchView('prompts')">
                <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                프롬프트 관리
            </div>
            <div class="nav-item" onclick="switchView('summaries')">
                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                일일 업무 회고
            </div>
        </nav>

        <div class="theme-toggle-area">
            <span style="font-size: 0.8rem; color: var(--text-muted);">테마 변경</span>
            <button class="theme-toggle-btn" onclick="toggleTheme()" id="themeBtn">🌙 Dark</button>
        </div>
    </aside>

    <!-- Main Container -->
    <main>
        <header>
            <div class="header-title">
                <h1 id="viewTitle">실시간 오피스 대시보드</h1>
                <p id="viewDesc">가상 스타트업 팀원들의 실시간 연동 상태와 피드를 모니터링합니다.</p>
            </div>
            <button class="refresh-btn" onclick="loadAllData()">
                <svg viewBox="0 0 24 24"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                새로고침
            </button>
        </header>

        <!-- 1. VIEW: Dashboard Monitor -->
        <section id="view-dashboard" class="view-section active">
            
            <!-- Views Mode Toggle (Global) -->
            <div style="display:flex; justify-content: flex-end; margin-bottom: 20px;">
                <div class="view-toggle-container">
                    <button class="view-toggle-btn active" id="view-ui-btn" onclick="toggleViewMode('ui')">UI 파싱 뷰</button>
                    <button class="view-toggle-btn" id="view-raw-btn" onclick="toggleViewMode('raw')">Raw JSON 뷰</button>
                </div>
            </div>

            <!-- UI VIEW CONTAINER -->
            <div class="parsed-container active" id="dashboard-ui-container">
                <!-- Status Row -->
                <div class="status-row">
                    <div class="status-card active-state" id="orchestratorCard">
                        <span class="card-title">Loop Mode</span>
                        <span class="card-value" id="status-mode">Loading...</span>
                        <span class="card-desc" id="status-interval">체크 주기: --s</span>
                    </div>
                    <div class="status-card active-state" id="slackCard">
                        <span class="card-title">Slack Client</span>
                        <span class="card-value" id="status-slack-chan">Loading...</span>
                        <span class="card-desc" id="status-slack-last">최신 동기화: None</span>
                    </div>
                    <div class="status-card active-state" id="githubCard">
                        <span class="card-title">GitHub Webhook</span>
                        <span class="card-value" id="status-github-repo">Loading...</span>
                        <span class="card-desc" id="status-github-last">최신 수신 ID: None</span>
                    </div>
                    <div class="status-card active-state" id="jiraCard">
                        <span class="card-title">Jira Sync</span>
                        <span class="card-value" id="status-jira-proj">Loading...</span>
                        <span class="card-desc" id="status-jira-last">최신 업데이트: None</span>
                    </div>
                </div>

                <!-- Event Timeline Panel -->
                <div class="panel">
                    <div class="panel-header">
                        <h2 class="panel-title">
                            <svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                            실시간 오피스 타임라인 피드
                        </h2>
                    </div>
                    <div class="timeline" id="eventTimeline">
                        <div style="text-align: center; color: var(--text-muted); padding: 40px 0;">로딩 중...</div>
                    </div>
                </div>
            </div>

            <!-- RAW JSON VIEW CONTAINER -->
            <div class="raw-preview" id="dashboard-raw-container">
                <!-- Displays the merged json variables -->
                Loading raw json variables...
            </div>
        </section>

        <!-- 2. VIEW: Script manual executor -->
        <section id="view-scripts" class="view-section">
            <div class="panel">
                <div class="panel-header">
                    <h2 class="panel-title">⚙️ 시스템 배치 및 동기화 스크립트 수동 실행</h2>
                </div>
                
                <div class="script-list">
                    <div class="script-card">
                        <div class="script-info">
                            <h3>Slack 메시지 수집 (slack_client.sh)</h3>
                            <p>실시간으로 Slack 채널 API를 호출하여 최신 대화를 확인하고 inbox 폴더에 주입합니다.</p>
                        </div>
                        <button class="run-btn" id="btn-slack_client" onclick="runScript('slack_client')">
                            <span>실행하기</span>
                        </button>
                    </div>

                    <div class="script-card">
                        <div class="script-info">
                            <h3>GitHub 이벤트 동기화 (github_client.sh)</h3>
                            <p>GitHub API를 호출하여 최신 푸시, 이슈, 풀 리퀘스트 변동 내역을 시스템에 가져옵니다.</p>
                        </div>
                        <button class="run-btn" id="btn-github_client" onclick="runScript('github_client')">
                            <span>실행하기</span>
                        </button>
                    </div>

                    <div class="script-card">
                        <div class="script-info">
                            <h3>Jira 이슈 동기화 (jira_client.sh)</h3>
                            <p>Jira API를 연동하여 대상 스프린트 보드의 카드 상태 변경 사항을 확인합니다.</p>
                        </div>
                        <button class="run-btn" id="btn-jira_client" onclick="runScript('jira_client')">
                            <span>실행하기</span>
                        </button>
                    </div>

                    <div class="script-card">
                        <div class="script-info">
                            <h3>스탠업 지시 트리거 (daily_scheduler.sh)</h3>
                            <p>매일 아침 데일리 스크럼 계획과 스탠드업 참여 트리거 메시지를 수동으로 발생시킵니다.</p>
                        </div>
                        <button class="run-btn" id="btn-daily_scheduler" onclick="runScript('daily_scheduler')">
                            <span>실행하기</span>
                        </button>
                    </div>

                    <div class="script-card">
                        <div class="script-info">
                            <h3>가상 Slack 테스트 (mock_slack_trigger.sh)</h3>
                            <p>모의 Slack 메시지를 주입하여 에이전트들의 반응 파이프라인(Router -> Personas -> Validator)을 로컬에서 수동 테스트합니다.</p>
                        </div>
                        <button class="run-btn" id="btn-mock_slack" onclick="runScript('mock_slack')">
                            <span>실행하기</span>
                        </button>
                    </div>

                    <div class="script-card">
                        <div class="script-info">
                            <h3>자정 로그 압축 요약 (daily_compressor.sh)</h3>
                            <p>오늘 하루 대화 로그를 모두 분석하고 압축하여 daily_summary.md 파일로 회고록을 기록합니다.</p>
                        </div>
                        <button class="run-btn" id="btn-daily_compressor" onclick="runScript('daily_compressor')">
                            <span>실행하기</span>
                        </button>
                    </div>

                    <div class="script-card">
                        <div class="script-info">
                            <h3>설정 동기화 (sync_configs.sh)</h3>
                            <p>수정한 에이전트 프롬프트 텍스트 파일들을 실제 활성화된 시스템의 내부 에이전트 디렉토리에 동기화합니다.</p>
                        </div>
                        <button class="run-btn" id="btn-sync_configs" onclick="runScript('sync_configs')">
                            <span>실행하기</span>
                        </button>
                    </div>
                </div>

                <!-- CRT Console Output -->
                <div class="console-box-header">
                    <span>🖥️ 스크립트 실행 실시간 터미널 콘솔 로그</span>
                    <button class="refresh-btn" style="padding: 4px 8px; font-size: 0.75rem;" onclick="clearConsole()">지우기</button>
                </div>
                <div class="console-box" id="scriptTerminal">
[Terminal Status: Ready]
- 상단의 스크립트 실행하기 단추를 누르면 실시간 쉘 출력(stdout/stderr) 결과가 여기에 출력됩니다.
                </div>
            </div>
        </section>

        <!-- 3. VIEW: Prompts management -->
        <section id="view-prompts" class="view-section">
            <div class="panel">
                <div class="panel-header">
                    <h2 class="panel-title">👥 가상 동료 성격 조율 및 프롬프트 관리</h2>
                </div>
                <p style="color: var(--text-muted); margin-bottom: 24px; font-size: 0.85rem;">
                    각 동료의 카드를 선택하여 에이전트의 성격 프롬프트를 확인하고 실시간으로 수정할 수 있습니다.
                </p>
                <div class="prompts-grid" id="promptsContainer">
                    <!-- Loaded dynamically -->
                </div>
            </div>
        </section>

        <!-- 4. VIEW: Daily summaries -->
        <section id="view-summaries" class="view-section">
            <div class="panel">
                <div class="panel-header">
                    <h2 class="panel-title">📅 날짜별 프로젝트 마일스톤 회고록</h2>
                    <div class="view-toggle-container">
                        <button class="view-toggle-btn active" id="sum-ui-btn" onclick="toggleSummaryMode('ui')">UI 마크다운 뷰</button>
                        <button class="view-toggle-btn" id="sum-raw-btn" onclick="toggleSummaryMode('raw')">Raw 마크다운 뷰</button>
                    </div>
                </div>

                <div class="parsed-container active" id="summary-ui-container">
                    <div class="summary-list" id="summariesContainer">
                        <div style="text-align: center; color: var(--text-muted); padding: 40px 0;">요약을 불러오는 중입니다...</div>
                    </div>
                </div>

                <div class="raw-preview" id="summary-raw-container">
                    <!-- Markdown plain content loads here -->
                    Loading raw markdown content...
                </div>
            </div>
        </section>
    </main>

    <!-- Prompt Editor Modal -->
    <div class="modal" id="promptModal" onclick="closePromptModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2 id="modalPromptTitle" class="panel-title">Prompt File Edit</h2>
                <button class="modal-close" onclick="closePromptModal()">&times;</button>
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display:block; margin-bottom: 8px; font-weight:600; font-size: 0.85rem;">System 프롬프트 텍스트 내용</label>
                <textarea id="modalPromptContent" class="form-control" style="font-family: monospace; font-size: 0.8rem; height: 380px; resize: vertical;"></textarea>
            </div>
            <div style="display:flex; justify-content: flex-end; gap: 12px;">
                <button class="refresh-btn" onclick="closePromptModal()">취소</button>
                <button class="run-btn" style="padding: 10px 20px;" onclick="savePromptChanges()">프롬프트 동기화 적용</button>
            </div>
        </div>
    </div>

    <script>
        let currentView = 'dashboard';
        let currentTheme = 'dark';
        let viewMode = 'ui'; // ui or raw for events/status
        let summaryMode = 'ui'; // ui or raw for summaries
        let currentPromptFile = '';
        let promptsData = {};
        let rawEventsData = '';
        let rawStatusData = null;
        let summariesData = [];

        function switchView(viewName) {
            currentView = viewName;
            document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));

            document.getElementById(`view-${viewName}`).classList.add('active');

            const navItems = Array.from(document.querySelectorAll('.nav-item'));
            const matchingNav = navItems.find(item => item.innerText.includes(
                viewName === 'dashboard' ? '실시간 모니터' :
                viewName === 'scripts' ? '스크립트 수동' :
                viewName === 'prompts' ? '프롬프트 관리' : '일일 업무'
            ));
            if (matchingNav) matchingNav.classList.add('active');

            const titles = {
                dashboard: ['실시간 오피스 대시보드', '가상 스타트업 팀원들의 실시간 연동 상태와 피드를 모니터링합니다.'],
                scripts: ['스크립트 수동 실행 콘솔', '가상 오피스의 동기화 쉘 스크립트를 직접 실행하고 실시간 터미널 결과를 확인합니다.'],
                prompts: ['프롬프트 조율 및 관리', '에이전트별 페르소나 및 톤 검증기 프롬프트를 확인하고 실시간 수정 동기화합니다.'],
                summaries: ['일일 업무 마일스톤 회고', '자정 로그 압축 모듈이 요약 보고한 과거 히스토리 파일을 모아봅니다.']
            };

            document.getElementById('viewTitle').innerText = titles[viewName][0];
            document.getElementById('viewDesc').innerText = titles[viewName][1];
        }

        function toggleTheme() {
            const body = document.body;
            const btn = document.getElementById('themeBtn');
            if (currentTheme === 'dark') {
                body.setAttribute('data-theme', 'light');
                btn.innerText = '☀️ Light';
                currentTheme = 'light';
            } else {
                body.removeAttribute('data-theme');
                btn.innerText = '🌙 Dark';
                currentTheme = 'dark';
            }
        }

        function toggleViewMode(mode) {
            viewMode = mode;
            document.getElementById('view-ui-btn').classList.toggle('active', mode === 'ui');
            document.getElementById('view-raw-btn').classList.toggle('active', mode === 'raw');
            
            const uiContainer = document.getElementById('dashboard-ui-container');
            const rawContainer = document.getElementById('dashboard-raw-container');

            if (mode === 'ui') {
                uiContainer.classList.add('active');
                rawContainer.classList.remove('active');
            } else {
                uiContainer.classList.remove('active');
                rawContainer.classList.add('active');
                renderRawStatusAndEvents();
            }
        }

        function toggleSummaryMode(mode) {
            summaryMode = mode;
            document.getElementById('sum-ui-btn').classList.toggle('active', mode === 'ui');
            document.getElementById('sum-raw-btn').classList.toggle('active', mode === 'raw');

            const uiContainer = document.getElementById('summary-ui-container');
            const rawContainer = document.getElementById('summary-raw-container');

            if (mode === 'ui') {
                uiContainer.classList.add('active');
                rawContainer.classList.remove('active');
            } else {
                uiContainer.classList.remove('active');
                rawContainer.classList.add('active');
                renderRawSummaries();
            }
        }

        function formatTs(ts) {
            if(!ts) return 'None';
            try {
                const date = new Date(parseFloat(ts) * 1000);
                return date.toLocaleString('ko-KR', { hour12: false });
            } catch(e) {
                return ts;
            }
        }

        // Fetch Functions
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                rawStatusData = data;

                // UI update
                document.getElementById('status-mode').innerText = data.orchestrator.mode.toUpperCase();
                document.getElementById('status-interval').innerText = `체크 주기: ${data.orchestrator.loop_interval}s`;
                
                document.getElementById('status-slack-chan').innerText = data.integrations.slack.channel_id;
                document.getElementById('status-slack-last').innerText = data.orchestrator.last_ts ? `마지막 TS: ${data.orchestrator.last_ts.slice(0, 10)}` : 'None';

                document.getElementById('status-github-repo').innerText = data.integrations.github.repo.split('/').pop() || 'Not configured';
                document.getElementById('status-github-last').innerText = data.integrations.github.last_id ? `마지막 ID: ${data.integrations.github.last_id}` : 'None';

                document.getElementById('status-jira-proj').innerText = data.integrations.jira.project_key;
                document.getElementById('status-jira-last').innerText = data.integrations.jira.last_updated ? `동기화: ${data.integrations.jira.last_updated.slice(11, 19)}` : 'None';

                if (viewMode === 'raw') renderRawStatusAndEvents();
            } catch (e) {
                console.error("Error loading status:", e);
            }
        }

        async function fetchEvents() {
            try {
                const res = await fetch('/api/events');
                const data = await res.json();
                
                rawEventsData = data.raw;
                const events = data.parsed;
                const container = document.getElementById('eventTimeline');

                if (events.length === 0) {
                    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 40px 0;">대화 내역이 비어 있습니다.</div>`;
                    return;
                }

                const avatars = {
                    'Sarah': '👩‍💼',
                    'Liam': '📋',
                    'Chloe': '💰',
                    'Aiden': '💻'
                };

                container.innerHTML = events.map(ev => {
                    const isBot = ev.subtype === 'bot_message' || (ev.character && ev.character !== 'System');
                    const charName = ev.character || (ev.subtype === 'bot_message' ? ev.text.match(/^\\[([^\\]]+)\\]/)?.[1] : null) || ev.user || 'User';
                    const cleanCharName = charName ? charName.replace(' (CEO)', '').replace(' (PM)', '').replace(' (Sales)', '').replace(' (Tech Lead)', '') : 'System';
                    
                    const avatar = isBot ? (avatars[cleanCharName] || '🤖') : '🧑‍💻';
                    const nameLabel = isBot ? `${cleanCharName} (${cleanCharName === 'Sarah' ? 'CEO' : cleanCharName === 'Liam' ? 'PM' : cleanCharName === 'Aiden' ? 'Tech Lead' : 'Sales'})` : cleanCharName;
                    
                    const text = ev.text || '';
                    const timeStr = formatTs(ev.ts || ev.event_ts);
                    const sourceClass = ev.source || 'slack';

                    return `
                        <div class="timeline-item ${sourceClass}">
                            <div class="timeline-dot"></div>
                            <div class="timeline-card">
                                <div class="timeline-meta">
                                    <span class="source-tag ${sourceClass}">${ev.source || 'slack'}</span>
                                    <span class="timeline-time">${timeStr}</span>
                                </div>
                                <div class="timeline-user">
                                    <span class="bot-avatar">${avatar}</span>
                                    <span>${nameLabel}</span>
                                </div>
                                <div class="timeline-text">${text}</div>
                            </div>
                        </div>
                    `;
                }).join('');

                if (viewMode === 'raw') renderRawStatusAndEvents();
            } catch (e) {
                console.error("Error loading events:", e);
            }
        }

        function renderRawStatusAndEvents() {
            const rawContainer = document.getElementById('dashboard-raw-container');
            const dataToDisplay = {
                "system_status_files": {
                    "status.json": rawStatusData ? rawStatusData.raw.status_json : null,
                    "github_status.json": rawStatusData ? rawStatusData.raw.github_status_json : null,
                    "jira_status.json": rawStatusData ? rawStatusData.raw.jira_status_json : null,
                    "scheduler_status.json": rawStatusData ? rawStatusData.raw.scheduler_status_json : null,
                    ".env_configs": rawStatusData ? rawStatusData.raw.env_config : null
                },
                "raw_history_jsonl": rawEventsData
            };
            rawContainer.innerText = JSON.stringify(dataToDisplay, null, 2);
        }

        async function fetchSummaries() {
            try {
                const res = await fetch('/api/summaries');
                summariesData = await res.json();
                
                const container = document.getElementById('summariesContainer');
                if (summariesData.length === 0) {
                    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 40px 0;">아직 생성된 일일 회고록 파일이 없습니다. 자정에 자동으로 생성됩니다.</div>`;
                    return;
                }

                container.innerHTML = summariesData.map((s, index) => {
                    let bodyHtml = s.content
                        .replace(/#+ (.*)/g, '<h3>$1</h3>')
                        .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                        .replace(/- (.*)/g, '<li>$1</li>')
                        .replace(/\\n/g, '<br>');

                    return `
                        <div class="summary-item" id="summary-item-${index}">
                            <div class="summary-header" onclick="toggleSummaryAccordion(${index})">
                                <span>📅 ${s.date} (일일 회고 아카이브)</span>
                                <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted);">클릭하여 토글 ▾</span>
                            </div>
                            <div class="summary-body">${bodyHtml}</div>
                        </div>
                    `;
                }).join('');

                if (summaryMode === 'raw') renderRawSummaries();
            } catch (e) {
                console.error("Error loading summaries:", e);
            }
        }

        function toggleSummaryAccordion(index) {
            const item = document.getElementById(`summary-item-${index}`);
            item.classList.toggle('open');
        }

        function renderRawSummaries() {
            const container = document.getElementById('summary-raw-container');
            if (summariesData.length === 0) {
                container.innerText = "No raw summaries found.";
                return;
            }
            container.innerText = summariesData.map(s => `--- DATE: ${s.date} ---\n${s.content}\n\n`).join('\n');
        }

        async function fetchPrompts() {
            try {
                const res = await fetch('/api/prompts');
                promptsData = await res.json();
                const container = document.getElementById('promptsContainer');

                const meta = {
                    'persona_sarah.txt': { name: 'Sarah (CEO)', avatar: '👩‍💼', role: 'Chief Executive Officer', color: '#ec4899', desc: '비즈니스 지표에 기여하는가?에 극도로 민감하며 직설적으로 핵심 질문을 던집니다.' },
                    'persona_liam.txt': { name: 'Liam (PM)', avatar: '📋', role: 'Project Manager', color: '#3b82f6', desc: '스프린트 마일스톤과 일정을 철저히 통제하며, 호주 특유의 칠한 톤으로 피드백을 요구합니다.' },
                    'persona_aiden.txt': { name: 'Aiden (Tech Lead)', avatar: '💻', role: 'Technical Lead', color: '#10b981', desc: '코드 퀄리티, 가벼움, DB 커넥션 유실 대책 등 엣지 케이스들을 집요하게 지적합니다.' },
                    'persona_chloe.txt': { name: 'Chloe (Sales / Mkt)', avatar: '💰', role: 'Sales & Marketing', color: '#f59e0b', desc: '고객 반응과 클라이언트 피드백을 냉정하고 단호하게 팀에게 전달합니다.' },
                    'router.txt': { name: 'Router Prompt', avatar: '🚦', role: 'System Router', color: '#818cf8', desc: '유입된 대화 내용을 해석하여 어떤 에이전트들이 답변해야 하는가 결정하는 규칙지시문.' },
                    'validator.txt': { name: 'Tone Validator', avatar: '🛡️', role: 'Tone Guardrail', color: '#f43f5e', desc: '답변 결과물에서 로봇 말투나 한국식 완곡한 격려 표현을 감지해 필터링하는 규칙.' },
                    'active_decision.txt': { name: 'Proactive Brain', avatar: '🧠', role: 'Proactive Trigger', color: '#a855f7', desc: '조용히 채널 상태를 모니터링하다가 적합한 시점에 선제적으로 대화를 거는 판단 로직.' }
                };

                container.innerHTML = Object.keys(promptsData).map(file => {
                    const info = meta[file] || { name: file, avatar: '⚙️', role: 'System prompt file', color: '#64748b', desc: '' };
                    return `
                        <div class="prompt-card" onclick="showPromptModal('${file}')">
                            <div class="prompt-card-header">
                                <div style="display:flex; align-items:center; gap:12px;">
                                    <div class="prompt-card-avatar" style="border-color: ${info.color}">${info.avatar}</div>
                                    <div>
                                        <div class="prompt-card-name">${info.name}</div>
                                        <div class="prompt-card-role" style="color: ${info.color}">${info.role}</div>
                                    </div>
                                </div>
                                <span style="font-size: 0.75rem; text-decoration: underline; color: var(--primary);">수정</span>
                            </div>
                            <div class="prompt-card-desc">${info.desc}</div>
                        </div>
                    `;
                }).join('');
            } catch(e) {
                console.error("Error loading prompts:", e);
            }
        }

        // Edit Modal
        function showPromptModal(file) {
            currentPromptFile = file;
            document.getElementById('modalPromptTitle').innerText = `📝 ${file} 파일 설정 수정`;
            document.getElementById('modalPromptContent').value = promptsData[file] || '';
            document.getElementById('promptModal').classList.add('open');
        }

        function closePromptModal() {
            document.getElementById('promptModal').classList.remove('open');
        }

        async function savePromptChanges() {
            const content = document.getElementById('modalPromptContent').value;
            try {
                const res = await fetch('/api/prompts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: currentPromptFile, content })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`[성공] ${currentPromptFile} 설정이 저장 및 동기화되었습니다.`);
                    closePromptModal();
                    fetchPrompts();
                } else {
                    alert(`[에러] ${data.error}`);
                }
            } catch (e) {
                alert('[에러] 서버 통신 중 오류가 발생했습니다.');
            }
        }

        // Script runner handler
        async function runScript(scriptKey) {
            const btn = document.getElementById(`btn-${scriptKey}`);
            const terminal = document.getElementById('scriptTerminal');
            
            btn.classList.add('running');
            btn.disabled = true;

            const timeStr = new Date().toLocaleTimeString();
            terminal.innerText += `\n\n[${timeStr}] $ Running script manually: ${scriptKey}...\n`;
            terminal.scrollTop = terminal.scrollHeight;

            try {
                const res = await fetch('/api/run-script', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ script: scriptKey })
                });
                const data = await res.json();

                btn.classList.remove('running');
                btn.disabled = false;

                if (data.success) {
                    let log = `Command: ${data.cmd}\nExit Code: ${data.exit_code}\n`;
                    if (data.stdout) log += `=== STDOUT ===\n${data.stdout}\n`;
                    if (data.stderr) log += `=== STDERR ===\n${data.stderr}\n`;
                    terminal.innerText += log;
                } else {
                    terminal.innerText += `Error executing: ${data.error}\n`;
                }

                // Update system variables immediately
                loadAllData();
            } catch (e) {
                btn.classList.remove('running');
                btn.disabled = false;
                terminal.innerText += `Server failure connecting: ${e}\n`;
            }
            terminal.scrollTop = terminal.scrollHeight;
        }

        function clearConsole() {
            document.getElementById('scriptTerminal').innerText = '[Terminal Status: Cleared]\n';
        }

        function loadAllData() {
            fetchStatus();
            fetchEvents();
            fetchPrompts();
            fetchSummaries();
        }

        // Initial Load
        window.onload = function() {
            loadAllData();
            // Pull data every 20 seconds
            setInterval(loadAllData, 20000);
        }
    </script>
</body>
</html>
"""

def run_server():
    server_address = ("", PORT)
    try:
        with ThreadedHTTPServer(server_address, DashboardHandler) as httpd:
            print(f"==================================================")
            print(f"🚀 Dashboard server running at http://localhost:{PORT}")
            print(f"Cwd: {WORKSPACE_DIR}")
            print(f"Press [CTRL+C] to shutdown the dashboard server.")
            print(f"==================================================")
            httpd.serve_forever()
    except Exception as e:
        print(f"Failed to start dashboard server: {e}")

if __name__ == "__main__":
    run_server()
