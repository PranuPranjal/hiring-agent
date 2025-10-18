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

from score import main as score_main

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# Allow requests from the frontend dev server during development
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})


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

            result = score_main(tmp_path, role_description=role_description)

            # cleanup
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        else:
            data = request.get_json(force=True)
            pdf_path = data.get("pdf_path")
            role_description = data.get("role_description")

            if not pdf_path:
                return jsonify({"error": "pdf_path or file upload required"}), 400

            if not os.path.exists(pdf_path):
                return jsonify({"error": f"File not found: {pdf_path}"}), 404

            result = score_main(pdf_path, role_description=role_description)

        # The scoring pipeline returns a pydantic model (EvaluationData) or None
        if result is None:
            return jsonify({"error": "Scoring failed"}), 500

        # Convert to JSON-serializable dict if pydantic BaseModel
        try:
            payload = result.model_dump() if hasattr(result, "model_dump") else result
        except Exception:
            payload = str(result)

        return jsonify({"result": payload}), 200

    except Exception as e:
        logger.exception("Error in /score")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
