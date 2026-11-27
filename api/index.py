import html
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import create_app
    app = create_app()
except Exception:
    _error = traceback.format_exc()
    print(_error, flush=True)                      # also shows up in Vercel > Logs
    from flask import Flask
    app = Flask("boot_error")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def boot_error(path):
        # With SHOW_BOOT_ERRORS=1 the real reason is shown here instead of a blank error page.
        if os.environ.get("SHOW_BOOT_ERRORS") == "1":
            return ("<pre style='white-space:pre-wrap;padding:16px;font-size:14px'>"
                    + html.escape(_error) + "</pre>"), 500
        return "The site could not start. Open Vercel > Logs for the reason.", 500
