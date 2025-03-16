import asyncio
import random
import time
import aiohttp
from aiohttp import ClientSession, ClientTimeout
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration - can be modified directly in this file
API_URL = "http://target-api:5000"  # Docker service name
ENDPOINTS = ["/", "/metrics"]       # Endpoints to call
CONCURRENT_REQUESTS = 50            # Number of simultaneous connections
TEST_DURATION = 30                  # Test duration in seconds
REQUEST_TIMEOUT = 5                 # Timeout for each request in seconds

async def make_request(session, endpoint):
    """Make a single request to an endpoint."""
    url = f"{API_URL}{endpoint}"
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

async def worker(session, request_queue, results):
    """Worker that processes requests from the queue."""
    while True:
        endpoint = await request_queue.get()
        if endpoint is None:  # Sentinel value to stop the worker
            request_queue.task_done()
            break
            
        status = await make_request(session, endpoint)
        results["total"] += 1
        if status == 200:
            results["success"] += 1
        else:
            results["failed"] += 1
            
        request_queue.task_done()

async def generate_load():
    """Generate load by pushing requests to the queue."""
    results = {"total": 0, "success": 0, "failed": 0}
    request_queue = asyncio.Queue()
    timeout = ClientTimeout(total=REQUEST_TIMEOUT)
    
    logger.info(f"Starting stress test with {CONCURRENT_REQUESTS} concurrent connections")
    logger.info(f"Test will run for {TEST_DURATION} seconds")
    logger.info(f"Target API URL: {API_URL}")
    
    async with ClientSession(timeout=timeout) as session:
        # Create worker tasks
        workers = []
        for _ in range(CONCURRENT_REQUESTS):
            task = asyncio.create_task(worker(session, request_queue, results))
            workers.append(task)
        
        # Start time for the test
        start_time = time.time()
        
        # Generate load until the test duration is reached
        try:
            while time.time() - start_time < TEST_DURATION:
                endpoint = random.choice(ENDPOINTS)
                await request_queue.put(endpoint)
                # Small delay to avoid overloading the queue
                await asyncio.sleep(0.01)
        
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        
        # Send sentinel values to stop workers
        for _ in range(CONCURRENT_REQUESTS):
            await request_queue.put(None)
        
        # Wait for all workers to finish
        await asyncio.gather(*workers)
    
    # Calculate and log results
    total_time = time.time() - start_time
    requests_per_second = results["total"] / total_time
    success_rate = (results["success"] / results["total"]) * 100 if results["total"] > 0 else 0
    
    logger.info(f"Test completed in {total_time:.2f} seconds")
    logger.info(f"Total requests: {results['total']}")
    logger.info(f"Successful requests: {results['success']}")
    logger.info(f"Failed requests: {results['failed']}")
    logger.info(f"Requests per second: {requests_per_second:.2f}")
    logger.info(f"Success rate: {success_rate:.2f}%")

if __name__ == "__main__":
    asyncio.run(generate_load()) 