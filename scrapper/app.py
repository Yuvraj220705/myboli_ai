"""Flask REST API for Maayboli Malvani News Chatbot Microservice."""

import logging
from typing import Tuple

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

from gemini_service import generate_answer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health_check() -> Tuple[Response, int]:
    """Simple health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/chatbot/ask", methods=["POST"])
def ask() -> Tuple[Response, int]:
    """Primary chat endpoint for user questions.

    Accepts JSON body:
    {
        "question": "...",
        "session_id": "..." (optional)
    }

    Returns JSON response:
    {
        "answer": "...",
        "sources": [...]
    }
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid request payload or non-JSON input."}), 400

    question = data.get("question")
    if not question or not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Question is required."}), 400

    session_id = data.get("session_id")
    logger.info(
        "Received question: '%s' (session_id=%s)",
        question.strip()[:80],
        session_id,
    )

    try:
        result = generate_answer(question.strip())
        return jsonify(result), 200
    except Exception as e:
        logger.error("Unhandled exception in ask endpoint: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error."}), 500


@app.route("/chat", methods=["POST"])
def chat() -> Tuple[Response, int]:
    """Legacy chat endpoint alias for backward compatibility."""
    return ask()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )

