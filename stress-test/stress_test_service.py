import asyncio
import random
import time
import aiohttp
import threading
import json
import logging
from aiohttp import ClientSession, ClientTimeout
from flask import Flask, request, jsonify, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "api_url": "http://target-api:5000",  # URL of the API
    "endpoints": [
        {"path": "/", "method": "GET", "weight": 10},
        {"path": "/status", "method": "GET", "weight": 5},
        {"path": "/submit", "method": "POST", "data": {"name": "John Doe", "email": "john@example.com"}, "weight": 8}
    ],
    "concurrent_requests": 50,            # Number of simultaneous connections
    "test_duration": 30,                  # Test duration in seconds
    "request_timeout": 5,                 # Timeout for each request in seconds
    "use_weights": True                   # Whether to use endpoint weights for distribution
}

# Global state
current_config = DEFAULT_CONFIG.copy()
last_test_results = None
is_test_running = False
test_lock = threading.Lock()

# Core test functionality
async def make_request(session, endpoint_config, api_url):
    """Make a single request to an endpoint."""
    path = endpoint_config["path"]
    method = endpoint_config["method"]
    data = endpoint_config.get("data")
    
    url = f"{api_url}{path}"
    start_time = time.time()
    
    try:
        if method == "GET":
            async with session.get(url) as response:
                elapsed = time.time() - start_time
                status = response.status
                if status == 200:
                    logger.info(f"Success: GET {url} - {status} - {elapsed:.2f}s")
                else:
                    logger.error(f"Failed: GET {url} - {status} - {elapsed:.2f}s")
                return status
        elif method == "POST":
            async with session.post(url, json=data) as response:
                elapsed = time.time() - start_time
                status = response.status
                if status == 200:
                    logger.info(f"Success: POST {url} - {status} - {elapsed:.2f}s")
                else:
                    logger.error(f"Failed: POST {url} - {status} - {elapsed:.2f}s")
                return status
        else:
            logger.error(f"Unsupported method: {method}")
            return None
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error: {method} {url} - {str(e)} - {elapsed:.2f}s")
        return None

async def worker(session, request_queue, results, api_url):
    """Worker that processes requests from the queue."""
    while True:
        try:
            # Get a task from the queue
            endpoint_config = await request_queue.get()
            if endpoint_config is None:  # Sentinel value to stop the worker
                request_queue.task_done()
                break
                
            # Make the request
            status = await make_request(session, endpoint_config, api_url)
            
            # Update overall results
            results["total"] += 1
            if status == 200:
                results["success"] += 1
            else:
                results["failed"] += 1
            
            # Update per-endpoint statistics if not already tracking
            endpoint_key = f"{endpoint_config['method']}:{endpoint_config['path']}"
            if "endpoint_stats" not in results:
                results["endpoint_stats"] = {}
                
            if endpoint_key not in results["endpoint_stats"]:
                results["endpoint_stats"][endpoint_key] = {"total": 0, "success": 0, "failed": 0}
                
            results["endpoint_stats"][endpoint_key]["total"] += 1
            if status == 200:
                results["endpoint_stats"][endpoint_key]["success"] += 1
            else:
                results["endpoint_stats"][endpoint_key]["failed"] += 1
                
            request_queue.task_done()
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            request_queue.task_done()

async def run_load_test(config):
    """Execute the load test with the given configuration."""
    results = {"total": 0, "success": 0, "failed": 0}
    request_queue = asyncio.Queue()
    timeout = ClientTimeout(total=config["request_timeout"])
    
    logger.info(f"Starting stress test with {config['concurrent_requests']} concurrent connections")
    logger.info(f"Test will run for {config['test_duration']} seconds")
    logger.info(f"Target API: {config['api_url']}")
    
    # Fixed f-string syntax
    endpoint_list = [f"{e['method']} {e['path']} (weight: {e.get('weight', 1)})" for e in config['endpoints']]
    logger.info(f"Target endpoints: {endpoint_list}")
    
    # Prepare weighted distribution if enabled
    use_weights = config.get("use_weights", True)
    if use_weights:
        # Create weighted distribution for endpoint selection
        endpoints = config['endpoints']
        weights = [endpoint.get('weight', 1) for endpoint in endpoints]
        total_weight = sum(weights)
        logger.info(f"Using weighted distribution with total weight: {total_weight}")
    
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    async with ClientSession(timeout=timeout, connector=connector) as session:
        # Create worker tasks
        workers = []
        for _ in range(config['concurrent_requests']):
            task = asyncio.create_task(
                worker(session, request_queue, results, config['api_url'])
            )
            workers.append(task)
        
        # Start time for the test
        start_time = time.time()
        
        # Generate load until the test duration is reached
        try:
            while time.time() - start_time < config['test_duration']:
                # Select an endpoint configuration based on weights or randomly
                if use_weights and total_weight > 0:
                    # Weighted random selection
                    r = random.uniform(0, total_weight)
                    cumulative_weight = 0
                    selected_endpoint = config['endpoints'][0]
                    
                    for i, endpoint in enumerate(config['endpoints']):
                        cumulative_weight += endpoint.get('weight', 1)
                        if r <= cumulative_weight:
                            selected_endpoint = endpoint
                            break
                else:
                    # Simple random selection (equal probability)
                    selected_endpoint = random.choice(config['endpoints'])
                
                await request_queue.put(selected_endpoint)
                
                # Add randomness to request timing
                await asyncio.sleep(random.uniform(0.001, 0.02))
        
        except Exception as e:
            logger.error(f"Test error during request generation: {str(e)}")
        
        # Send sentinel values to stop workers
        for _ in range(config['concurrent_requests']):
            await request_queue.put(None)
        
        # Wait for all workers to finish
        await asyncio.gather(*workers)
    
    # Calculate and log results
    total_time = time.time() - start_time
    requests_per_second = results["total"] / total_time if total_time > 0 else 0
    success_rate = (results["success"] / results["total"]) * 100 if results["total"] > 0 else 0
    
    # Add additional metrics to results
    results["total_time"] = round(total_time, 2)
    results["requests_per_second"] = round(requests_per_second, 2)
    results["success_rate"] = round(success_rate, 2)
    
    # Track per-endpoint statistics
    if "endpoint_stats" in results:
        for endpoint, stats in results["endpoint_stats"].items():
            if stats["total"] > 0:
                stats["success_rate"] = round((stats["success"] / stats["total"]) * 100, 2)
    
    logger.info(f"Test completed in {total_time:.2f} seconds")
    logger.info(f"Total requests: {results['total']}")
    logger.info(f"Successful requests: {results['success']}")
    logger.info(f"Failed requests: {results['failed']}")
    logger.info(f"Requests per second: {requests_per_second:.2f}")
    logger.info(f"Success rate: {success_rate:.2f}%")
    
    return results

# Thread management
def execute_test_in_thread():
    """Execute the test in a background thread."""
    global is_test_running, last_test_results, current_config
    
    with test_lock:
        if is_test_running:
            logger.warning("Test already running, ignoring request")
            return False
        is_test_running = True
    
    def run():
        global is_test_running, last_test_results
        
        # Create new event loop for the thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Use a thread-local copy of the configuration
            with test_lock:
                config = current_config.copy()
            
            # Run the test
            results = loop.run_until_complete(run_load_test(config))
            
            # Store results
            with test_lock:
                last_test_results = results
        except Exception as e:
            logger.error(f"Error in test thread: {str(e)}")
        finally:
            with test_lock:
                is_test_running = False
            loop.close()
    
    # Start the test in a new thread
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    return True

# Flask application
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with service information."""
    return jsonify({
        "service": "API Load Test Service",
        "status": "running",
        "endpoints": {
            "/config": "GET/POST - View or update test configuration",
            "/start-test": "POST - Start a load test with current configuration",
            "/status": "GET - Check test status and results",
            "/run-test": "POST - Run a test with specified duration and concurrency"
        }
    })

@app.route('/config', methods=['GET', 'POST'])
def config():
    """Get or update the test configuration."""
    global current_config
    
    if request.method == 'POST':
        try:
            new_config = request.get_json()
            if not new_config:
                return jsonify({"status": "error", "message": "Invalid JSON data"}), 400
            
            with test_lock:
                if is_test_running:
                    return jsonify({"status": "error", "message": "Cannot update config while test is running"}), 400
                
                # Update only valid configuration parameters
                for key, value in new_config.items():
                    if key in current_config:
                        current_config[key] = value
            
            return jsonify({"status": "success", "config": current_config})
        except Exception as e:
            logger.error(f"Error updating config: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # GET request - return current configuration
    return jsonify(current_config)

@app.route('/start-test', methods=['POST'])
def start_test():
    """Start a load test with the current configuration."""
    with test_lock:
        if is_test_running:
            return jsonify({"status": "error", "message": "A test is already running"}), 400
    
    try:
        # Start the test
        success = execute_test_in_thread()
        
        if success:
            return jsonify({
                "status": "success", 
                "message": "Test started", 
                "config": current_config
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Failed to start test, another test may be running"
            }), 400
    except Exception as e:
        logger.error(f"Error starting test: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def test_status():
    """Get the current test status and results."""
    with test_lock:
        if is_test_running:
            return jsonify({
                "status": "running",
                "config": current_config
            })
        elif last_test_results:
            return jsonify({
                "status": "completed",
                "results": last_test_results,
                "config": current_config
            })
        else:
            return jsonify({
                "status": "idle",
                "config": current_config
            })

@app.route('/run-test', methods=['POST'])
def run_test():
    """Run a test with specified parameters."""
    global current_config
    
    with test_lock:
        if is_test_running:
            return jsonify({"status": "error", "message": "A test is already running"}), 400
    
    try:
        # Get test parameters
        data = request.get_json() or {}
        
        # Configure the test
        with test_lock:
            # Update basic configuration
            current_config["api_url"] = data.get("api_url", "http://target-api:5000")
            current_config["test_duration"] = data.get("seconds", 30)
            current_config["concurrent_requests"] = data.get("requests", 50)
            current_config["request_timeout"] = data.get("timeout", 5)
            current_config["use_weights"] = data.get("use_weights", True)
            
            # If custom endpoints are provided, use them
            if "endpoints" in data:
                current_config["endpoints"] = data["endpoints"]
            # Otherwise, use the default set
            elif "reset_endpoints" in data and data["reset_endpoints"]:
                current_config["endpoints"] = DEFAULT_CONFIG["endpoints"]
        
        # Start the test
        success = execute_test_in_thread()
        
        if success:
            return jsonify({
                "status": "success", 
                "message": "Test started", 
                "config": current_config
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Failed to start test"
            }), 500
    except Exception as e:
        logger.error(f"Error starting test: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for Docker."""
    return Response("OK", status=200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)