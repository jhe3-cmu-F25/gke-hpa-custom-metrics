"""
Flask web application for the Inverted Index Search Engine.
Communicates with the backend via Kafka — no heavy processing here.
"""

import json
import uuid
from flask import Flask, render_template, request, jsonify, session
from kafka_client import KafkaClient
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
# Secret key for session management (change in production)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

# Initialize Kafka client
kafka = KafkaClient()


@app.route("/")
def index():
    """Home screen: URL input form."""
    return render_template("index.html", page="home")


@app.route("/index-papers", methods=["POST"])
def index_papers():
    """
    Receive a Google Scholar URL from the user,
    produce a message to 'search-request' Kafka topic,
    then wait (blocking) for a response on 'search-response'.
    Returns JSON so the frontend can poll or receive the result.
    """
    scholar_url = request.form.get("scholar_url", "").strip()
    if not scholar_url:
        return jsonify({"error": "No URL provided"}), 400

    # Unique correlation ID so we can match the response to this request
    correlation_id = str(uuid.uuid4())

    # Send the indexing request to Kafka
    message = {
        "correlation_id": correlation_id,
        "scholar_url": scholar_url,
    }
    kafka.produce(
        topic=os.getenv("KAFKA_TOPIC_SEARCH_REQUEST", "search-request"),
        message=message,
    )

    # Wait for the backend to finish indexing and respond
    response = kafka.consume_one(
        topic=os.getenv("KAFKA_TOPIC_SEARCH_RESPONSE", "search-response"),
        correlation_id=correlation_id,
        timeout=int(os.getenv("KAFKA_RESPONSE_TIMEOUT", "120")),
    )

    if response is None:
        return jsonify({"error": "Timed out waiting for indexing response"}), 504

    # Store correlation_id in session so subsequent screens can use it
    session["correlation_id"] = correlation_id
    return jsonify({"status": "ok"})


@app.route("/search", methods=["GET", "POST"])
def search():
    """Search Term screen."""
    if request.method == "GET":
        return render_template("index.html", page="search")

    term = request.form.get("term", "").strip()
    if not term:
        return jsonify({"error": "No search term provided"}), 400

    correlation_id = str(uuid.uuid4())

    message = {
        "correlation_id": correlation_id,
        "term": term,
    }
    kafka.produce(
        topic=os.getenv("KAFKA_TOPIC_SEARCH_TERM_REQUEST", "search-term-request"),
        message=message,
    )

    response = kafka.consume_one(
        topic=os.getenv("KAFKA_TOPIC_SEARCH_TERM_RESPONSE", "search-term-response"),
        correlation_id=correlation_id,
        timeout=int(os.getenv("KAFKA_RESPONSE_TIMEOUT", "120")),
    )

    if response is None:
        return jsonify({"error": "Timed out waiting for search response"}), 504

    # Expected response shape:
    # {
    #   "results": [
    #     {"doc_id": "...", "url": "...", "citations": 5,
    #      "doc_name": "...", "frequency": 3},
    #     ...
    #   ],
    #   "execution_time": 0.42
    # }
    return jsonify(response)


@app.route("/topn", methods=["GET", "POST"])
def topn():
    """Top-N Most Frequent Terms screen."""
    if request.method == "GET":
        return render_template("index.html", page="topn")

    try:
        n = int(request.form.get("n", 10))
    except ValueError:
        return jsonify({"error": "N must be an integer"}), 400

    correlation_id = str(uuid.uuid4())

    message = {
        "correlation_id": correlation_id,
        "n": n,
    }
    kafka.produce(
        topic=os.getenv("KAFKA_TOPIC_TOPN_REQUEST", "topn-request"),
        message=message,
    )

    response = kafka.consume_one(
        topic=os.getenv("KAFKA_TOPIC_TOPN_RESPONSE", "topn-response"),
        correlation_id=correlation_id,
        timeout=int(os.getenv("KAFKA_RESPONSE_TIMEOUT", "120")),
    )

    if response is None:
        return jsonify({"error": "Timed out waiting for top-N response"}), 504

    # Expected response shape:
    # {
    #   "results": [
    #     {"term": "machine learning", "total_frequency": 42},
    #     ...
    #   ]
    # }
    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")), debug=False)
