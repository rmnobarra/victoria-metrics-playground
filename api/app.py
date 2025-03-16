from flask import Flask, request, jsonify
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY
import psutil
import time

app = Flask(__name__)

# Métricas de requisições HTTP
REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições', ['method', 'endpoint'])
# Histograma para medir a latência das requisições
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Duração das requisições HTTP', 
                           ['method', 'endpoint'],
                           buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10])

# Métricas de uso de CPU e Memória
PROCESS = psutil.Process()
CPU_USAGE = Gauge('python_process_cpu_percent', 'Uso de CPU pelo processo (%)')
MEMORY_USAGE = Gauge('python_process_memory_bytes', 'Uso de memória pelo processo (bytes)')
THREAD_COUNT = Gauge('python_process_threads', 'Número de threads do processo')

# Decorator para medir a latência das requisições
def track_request_metrics(endpoint):
    def decorator(func):
        def wrapper(*args, **kwargs):
            method = request.method
            # Incrementa o contador de requisições
            REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
            
            # Mede o tempo de execução
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Registra a duração no histograma
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            
            return result
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

@app.route('/')
@track_request_metrics('/')
def index():
    return "Hello, World!"

@app.route('/status')
@track_request_metrics('/status')
def status():
    return jsonify({"status": "OK", "message": "Serviço em funcionamento"}), 200

@app.route('/submit', methods=['POST'])
@track_request_metrics('/submit')
def submit():
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
