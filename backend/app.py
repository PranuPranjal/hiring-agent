from __future__ import annotations

import os
import io
import json
import tempfile
import logging
from pathlib import Path
from typing import Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
import contextlib
import sys

from score import main as score_main

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# For local development allow all origins (change in production)
CORS(app)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"}), 200


def _save_upload(file_storage) -> str:
    """Save uploaded file to a temp location and return the path."""
    suffix = Path(file_storage.filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="resume_") as tf:
        file_bytes = file_storage.read()
        tf.write(file_bytes)
        tmp_path = tf.name
    return tmp_path


@app.route("/score", methods=["POST"])
def score_route():
    """Score a resume. Accepts multipart form with `file` (PDF) and optional `role_description`.

    Alternatively accepts JSON: {"pdf_path": "<path on server>", "role_description": "..."}
    """
    try:
        role_description = None

        # Prefer multipart file upload
        if "file" in request.files:
            uploaded = request.files["file"]
            tmp_path = _save_upload(uploaded)
            if "role_description" in request.form:
                role_description = request.form.get("role_description")
            target_path = tmp_path
        else:
            data = request.get_json(force=True)
            pdf_path = data.get("pdf_path")
            role_description = data.get("role_description")

            if not pdf_path:
                return jsonify({"error": "pdf_path or file upload required"}), 400

            if not os.path.exists(pdf_path):
                return jsonify({"error": f"File not found: {pdf_path}"}), 404

            target_path = pdf_path

        # Capture stdout/stderr and logging output while running the scoring pipeline
        log_buffer = io.StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            with contextlib.redirect_stdout(log_buffer), contextlib.redirect_stderr(log_buffer):
                result = score_main(target_path, role_description=role_description)
        except Exception as e:
            # Ensure logs include the exception traceback
            logger.exception("Exception while running score_main")
            # read logs and return error
            handler.flush()
            logs = log_buffer.getvalue()
            return (
                jsonify({"error": str(e), "logs": logs}),
                500,
            )
        finally:
            root_logger.removeHandler(handler)

        # cleanup uploaded temp file if present
        if "file" in request.files:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # The scoring pipeline returns a pydantic model (EvaluationData) or None
        if result is None:
            handler.flush()
            logs = log_buffer.getvalue()
            return jsonify({"error": "Scoring failed", "logs": logs}), 500

        # Convert to JSON-serializable dict if pydantic BaseModel
        try:
            payload = result.model_dump() if hasattr(result, "model_dump") else result
        except Exception:
            payload = str(result)

        handler.flush()
        logs = log_buffer.getvalue()

        return jsonify({"result": payload, "logs": logs}), 200

    except Exception as e:
        logger.exception("Error in /score")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
