import asyncio
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
    "endpoint": "/",                      # Endpoint to call - simplified to just one endpoint
    "concurrent_requests": 50,            # Number of simultaneous connections
    "test_duration": 30,                  # Test duration in seconds
    "request_timeout": 5                  # Timeout for each request in seconds
}

# Global state
current_config = DEFAULT_CONFIG.copy()
last_test_results = None
is_test_running = False
test_lock = threading.Lock()

# Core test functionality
async def make_request(session, endpoint, api_url):
    """Make a single request to an endpoint."""
    url = f"{api_url}{endpoint}"
    start_time = time.time()
    
    try:
        async with session.get(url) as response:
            elapsed = time.time() - start_time
            status = response.status
            if status == 200:
                logger.info(f"Success: {url} - {status} - {elapsed:.2f}s")
            else:
                logger.error(f"Failed: {url} - {status} - {elapsed:.2f}s")
            return status
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error: {url} - {str(e)} - {elapsed:.2f}s")
        return None

async def worker(session, request_queue, results, api_url, endpoint):
    """Worker that processes requests from the queue."""
    while True:
        try:
            # Get a task from the queue
            task = await request_queue.get()
            if task is None:  # Sentinel value to stop the worker
                request_queue.task_done()
                break
                
            # Make the request
            status = await make_request(session, endpoint, api_url)
            results["total"] += 1
            if status == 200:
                results["success"] += 1
            else:
                results["failed"] += 1
                
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
    logger.info(f"Target endpoint: {config['endpoint']}")
    
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    async with ClientSession(timeout=timeout, connector=connector) as session:
        # Create worker tasks
        workers = []
        for _ in range(config['concurrent_requests']):
            task = asyncio.create_task(
                worker(session, request_queue, results, config['api_url'], config['endpoint'])
            )
            workers.append(task)
        
        # Start time for the test
        start_time = time.time()
        
        # Generate load until the test duration is reached
        try:
            while time.time() - start_time < config['test_duration']:
                # Add task to queue - simplified to just push a placeholder since we always hit the same endpoint
                await request_queue.put(True)
                # Small delay to avoid overloading the queue
                await asyncio.sleep(0.01)
        
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
            current_config["api_url"] = data.get("api_url", "http://target-api:5000")
            current_config["endpoint"] = data.get("endpoint", "/")  # Simplified to one endpoint
            current_config["test_duration"] = data.get("seconds", 30)
            current_config["concurrent_requests"] = data.get("requests", 50)
            current_config["request_timeout"] = data.get("timeout", 5)
        
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