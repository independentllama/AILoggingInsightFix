import html
import json
from urllib import request

from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import threading
import logging
from error_processor import process_error_log, get_solution_history, client
from kafka_consumer import kafka_consumer_thread
import openai
from config import Config

app = Flask(__name__)
socketio = SocketIO(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define HTML template for rendering
HTML_TEMPLATE = """

<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Enhanced Logging Dashboard</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
    <style>
        body { font-family: 'Open Sans', sans-serif; }
        .error-message { font-weight: bold; color: #d9534f; }
        .solution-message { white-space: pre-line; }
        .accordion-button { text-overflow: ellipsis; overflow: hidden; }
        .timestamp { font-size: 0.8em; color: #6c757d; }
        .search-bar { margin-bottom: 1em; }
    </style>
</head>
<body>
<div class="container mt-4">
    <h1>Error Log Dashboard</h1>
    <div class="search-bar">
        <input type="text" class="form-control" id="searchInput" onkeyup="searchLogs()" placeholder="Search for logs...">
    </div>
    <div class="accordion" id="errorAccordion">
        {% for record in history %}
        <div class="accordion-item">
            <h2 class="accordion-header" id="heading{{ loop.index }}">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse{{ loop.index }}" aria-expanded="false" aria-controls="collapse{{ loop.index }}">
                    <span class="error-message">{{ record['error'] | default('Unknown Error') | truncate(80, true) }}</span>
                    <span class="timestamp">Timestamp: {{ record['timestamp'] }}</span>
                </button>
            </h2>
            <div id="collapse{{ loop.index }}" class="accordion-collapse collapse" aria-labelledby="heading{{ loop.index }}" data-bs-parent="#errorAccordion">
                <div class="accordion-body">
                    <p class="solution-message">{{ record['solution'] | default('No solution available') }}</p>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    <!-- Button to predict trends -->
    <button onclick="predictTrends()">Predict Trends</button>
</div>

<!-- Trend and Summary Modal -->
<div class="modal fade" id="infoModal" tabindex="-1" aria-labelledby="infoModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="infoModalLabel">Information</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <!-- Content will be loaded dynamically -->
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
function searchLogs() {
    var input = document.getElementById('searchInput');
    var filter = input.value.toUpperCase();
    var accordion = document.getElementById("errorAccordion");
    var items = accordion.getElementsByClassName('accordion-item');
    for (var i = 0; i < items.length; i++) {
        var error = items[i].getElementsByClassName("error-message")[0];
        if (error.textContent.toUpperCase().indexOf(filter) > -1) {
            items[i].style.display = "";
        } else {
            items[i].style.display = "none";
        }
    }
}

function summarizeError(encodedError) {
    const errorDetails = JSON.parse(decodeURIComponent(encodedError));
    fetch('/api/summarize-error', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({error_details: errorDetails})
    })
    .then(response => response.json())
    .then(data => {
        showModal('Summary', data.summary);
    })
    .catch(error => console.error('Error summarizing the error:', error));
}


function predictTrends() {
    fetch('/api/predict-trends')
    .then(response => response.json())
    .then(data => {
        showModal('Predictive Trend Analysis', data.trend_analysis);
    })
    .catch(error => {
        console.error('Error predicting trends:', error);
        showModal('Error', 'Failed to load trend analysis. Please try again later.');
    });
}

function showModal(title, content) {
    const modalTitle = document.querySelector('#infoModal .modal-title');
    const modalBody = document.querySelector('#infoModal .modal-body');
    modalTitle.textContent = title;
    modalBody.innerHTML = content;
    var infoModal = new bootstrap.Modal(document.getElementById('infoModal'), {});
    infoModal.show();
}
</script>
</body>
</html>


"""

@app.route('/')
def index():
    history = get_solution_history()
    for record in history:
        record['safe_error'] = json.dumps(record['error'])
    return render_template_string(HTML_TEMPLATE, history=history)

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    emit('status', {'message': 'Connected to server'})

def start_kafka_consumer():
    consumer_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    consumer_thread.start()

@app.route('/api/summarize-error', methods=['POST'])
def summarize_error():
    error_details = request.json['error_details']
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": f"Summarize this error log: {error_details}"},
                {"role": "assistant", "content": "I need a concise summary for a dashboard display."}
            ]
        )
        summary = response.choices[0].message.content
        return jsonify({'summary': summary})
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {str(e)}")
        return jsonify({'error': 'Failed to generate summary', 'details': str(e)}), 500


@app.route('/api/predict-trends', methods=['GET'])
def predict_trends():
    error_logs = get_solution_history()
    error_text = ' '.join([log['error'] for log in error_logs])
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": f"Analyze these error patterns: {error_text}"},
                {"role": "assistant", "content": "Analyze the error patterns provided and predict potential trends or future issues. Offer concise, actionable insights in 2-3 sentences."}
            ]
        )
        analysis = response.choices[0].message.content
        return jsonify({'trend_analysis': analysis})
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {str(e)}")
        return jsonify({'error': 'Failed to analyze trends', 'details': str(e)}), 500



if __name__ == '__main__':
    start_kafka_consumer()
    socketio.run(app, debug=True, host='0.0.0.0', allow_unsafe_werkzeug=True)
