"""
app.py
------
Flask application entry point for MasterHub.

Run with:
    python app.py

Or with the Flask CLI:
    set FLASK_APP=app.py   (Windows)
    flask run --host=0.0.0.0 --port=5000
"""
import os
from flask import Flask, jsonify, render_template, Response
from cortex.dashboard import cortex_bp
from api.routes import api_bp
from api.jiosaavn import jiosaavn_bp
from services.logger_service import get_logger
from services.mqtt_service import mqtt_service
from services.web_security import reject_cross_origin_mutation

log = get_logger("app")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.before_request(reject_cross_origin_mutation)

    app.register_blueprint(api_bp)
    app.register_blueprint(jiosaavn_bp)
    app.register_blueprint(cortex_bp)

    @app.route("/")
    def index():
        return jsonify({
            "name": "MasterHub",
            "description": "BCI + IoT + Desktop Automation + AI Command Router",
            "endpoints": {
                "POST /api/command": "Main command endpoint (gesture | command | eeg_window)",
                "GET /api/state": "Current FSM state snapshot",
                "GET /api/commands": "List of all recognized commands",
                "GET /api/health": "Health check",
                "GET /dashboard": "Live HTML control console (templates/dashboard.html)",
            },
        })

    @app.route("/dashboard")
    def dashboard():
        # Keep a cached stylesheet/script from mismatching an updated template.
        paths = [os.path.join(app.root_path, folder, name) for folder, name in (
            ('templates', 'dashboard.html'), ('static', 'masterhub.css'),
            ('static', 'masterhub.js'), ('static', 'bci-panel.js'))]
        version = str(max(os.stat(path).st_mtime_ns for path in paths))
        return Response(render_template("dashboard.html", dashboard_asset_version=version),
                        headers={"Cache-Control": "no-cache"}, mimetype="text/html")

    @app.route("/docs/guide")
    @app.route("/docs/user-guide.md")
    def user_guide_doc():
        guide_path = os.path.join(os.path.dirname(__file__), "docs", "USER_GUIDE.md")
        if os.path.exists(guide_path):
            with open(guide_path, "r", encoding="utf-8") as f:
                content = f.read()
            return Response(content, mimetype="text/markdown; charset=utf-8")
        return Response("# MasterHub User Guide\nDocumentation not found.", mimetype="text/plain; charset=utf-8")

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"success": False, "error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    return app


app = create_app()


if __name__ == "__main__":
    # Pre-connect MQTT at startup so the first IoT command isn't slowed
    # down by connection setup. Non-fatal if the broker is unreachable —
    # publish() will retry the connection lazily on first use.
    try:
        mqtt_service.connect()
    except Exception as exc:
        log.warning(f"Could not pre-connect to MQTT broker at startup: {exc}")

    log.info("Starting MasterHub Flask server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
