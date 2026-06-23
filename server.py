import sys
import os
import random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, render_template, Response, send_file
from logger import ExecutionLogger
from presence_module import register_presence_routes

JAVA_APPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'java_apps')

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

ExecutionLogger.initialize_server_session()


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route('/voice-app')
def voice_app():
    return render_template('static_recorder.html')


@app.route('/logs-viewer')
def logs_viewer():
    return render_template('logs_viewer.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# ── Logs API ───────────────────────────────────────────────────────────────────

@app.route('/api/logs')
def get_logs_json():
    """Return in-memory execution logs as JSON"""
    json_string = ExecutionLogger.logs_to_json_string(ExecutionLogger.global_logs)
    return Response(json_string, mimetype='application/json')


@app.route('/api/logs/sessions')
def get_server_sessions():
    """Return the current in-memory server session"""
    session_id = ExecutionLogger.server_session_id
    sessions = [{"server_session_id": session_id}] if session_id else []
    return jsonify({
        "regular_count": len(sessions),
        "saved_count": 0,
        "total_count": len(sessions),
        "regular_sessions": sessions,
        "saved_sessions": [],
        "count": len(sessions),
        "sessions": sessions
    })


@app.route('/api/logs/clear', methods=['POST'])
def clear_in_memory_logs():
    """Clear in-memory logs and start a fresh server session"""
    logger = ExecutionLogger()
    try:
        count = len(ExecutionLogger.global_logs)
        old_session_id = ExecutionLogger.server_session_id

        ExecutionLogger.global_logs.clear()
        ExecutionLogger.execution_counts.clear()
        ExecutionLogger.server_session_id = None
        ExecutionLogger.initialize_server_session()

        new_session_id = ExecutionLogger.server_session_id

        logger.log("New execution log session initialized", log_data={
            "new_session_id": new_session_id,
            "cleared_count": count
        })

        return jsonify({
            "status": "success",
            "message": f"Started new session (cleared {count} logs)",
            "old_session_id": old_session_id,
            "new_session_id": new_session_id,
            "cleared_count": count
        })

    except Exception as e:
        logger.log("Failed to clear logs", log_type="ERROR", log_data=str(e))
        return jsonify({"error": str(e)}), 500

    finally:
        logger.commit()


@app.route('/api/logs/save', methods=['POST'])
def save_session_logs():
    """No-op without database — acknowledges request without persisting"""
    data = request.get_json()
    if not data or 'server_session_id' not in data:
        return jsonify({"error": "server_session_id is required"}), 400

    return jsonify({
        "status": "success",
        "message": "Save is a no-op in this export (no database configured)",
        "server_session_id": data.get('server_session_id')
    })


@app.route('/api/logs/<execution_key>/<int:log_index>/data')
def get_log_data(execution_key, log_index):
    """Serve individual log entry data as JSON"""
    try:
        if execution_key not in ExecutionLogger.global_logs:
            return jsonify({"error": "Execution not found"}), 404

        execution = ExecutionLogger.global_logs[execution_key]

        if 'log_entries' not in execution or log_index >= len(execution['log_entries']):
            return jsonify({"error": "Log entry not found"}), 404

        log_entry = execution['log_entries'][log_index]

        if 'data' in log_entry and log_entry['data'] is not None:
            return jsonify(log_entry['data'])
        else:
            return jsonify({"message": "No data in this log entry"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Java Apps ──────────────────────────────────────────────────────────────────

@app.route('/java-app')
def random_java_app():
    if not os.path.isdir(JAVA_APPS_DIR):
        return jsonify({"error": "java_apps folder not found"}), 404

    html_files = [f for f in os.listdir(JAVA_APPS_DIR) if f.endswith('.html')]

    if not html_files:
        return jsonify({"error": "No HTML files found in java_apps folder"}), 404

    chosen = random.choice(html_files)
    file_path = os.path.join(JAVA_APPS_DIR, chosen)

    if not os.path.isfile(file_path):
        return jsonify({"error": f"File '{chosen}' could not be read"}), 500

    return send_file(file_path, mimetype='text/html')


# ── Health ─────────────────────────────────────────────────────────────────────

@app.route('/health')
def health_check():
    return jsonify({
        "status": "ok",
        "session_id": ExecutionLogger.server_session_id,
        "log_count": len(ExecutionLogger.global_logs),
        "endpoints": [
            "GET  /voice-app",
            "GET  /logs-viewer",
            "GET  /api/logs",
            "GET  /api/logs/sessions",
            "POST /api/logs/clear",
            "POST /api/logs/save",
            "GET  /api/logs/<key>/<index>/data",
            "POST /api/upload/audio",
            "GET  /java-app",
            "GET  /health"
        ]
    })


# ── Register audio upload routes ───────────────────────────────────────────────

register_presence_routes(app)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
