"""Flask REST API for Retrieval-Augmented News Chatbot."""

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


@app.route("/chat", methods=["POST"])
def chat() -> Tuple[Response, int]:
    """Chat endpoint to process user questions via Gemini service."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Question is required."}), 400

    question = data.get("question")
    if not question or not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Question is required."}), 400

    question = question.strip()
    logger.info("Incoming chat request: %s", question[:80])

    try:
        answer = generate_answer(question)
        logger.info("Generated response: %s", answer[:80])
        return jsonify({"answer": answer}), 200
    except Exception as e:
        logger.error("Error processing chat request: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error."}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
