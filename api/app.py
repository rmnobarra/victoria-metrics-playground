from flask import Flask, request, jsonify
from prometheus_client import Counter, Gauge, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY
import psutil

app = Flask(__name__)

# Métricas de requisições HTTP
REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições', ['method', 'endpoint'])

# Métricas de uso de CPU e Memória
PROCESS = psutil.Process()
CPU_USAGE = Gauge('python_process_cpu_percent', 'Uso de CPU pelo processo (%)')
MEMORY_USAGE = Gauge('python_process_memory_bytes', 'Uso de memória pelo processo (bytes)')
THREAD_COUNT = Gauge('python_process_threads', 'Número de threads do processo')

@app.route('/')
def index():
    REQUEST_COUNT.labels(method='GET', endpoint='/').inc()
    return "Hello, World!"

@app.route('/status')
def status():
    REQUEST_COUNT.labels(method='GET', endpoint='/status').inc()
    return jsonify({"status": "OK", "message": "Serviço em funcionamento"}), 200

@app.route('/submit', methods=['POST'])
def submit():
    REQUEST_COUNT.labels(method='POST', endpoint='/submit').inc()
    data = request.get_json()
    return jsonify({"message": "Dados recebidos", "data": data}), 201

@app.route('/metrics')
def metrics():
    CPU_USAGE.set(PROCESS.cpu_percent(interval=0.1))
    MEMORY_USAGE.set(PROCESS.memory_info().rss)
    THREAD_COUNT.set(PROCESS.num_threads())
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
