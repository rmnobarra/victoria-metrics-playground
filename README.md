# victoria metrics playground

1. build project

docker compose up -d --build 

Configure the test parameters (optional):

curl -X POST http://localhost:8081/config -H "Content-Type: application/json" -d '{"test_duration": 120, "concurrent_requests": 1000}'

Start a test:

curl -X POST http://localhost:8081/start

Or start with custom parameters for this test only:

Check test status:

curl http://localhost:8081/status

Reset configuration to defaults:

curl -X POST http://localhost:8081/reset

This service allows you to:
Configure test parameters via API
Start tests on demand
Check test status and results
Run multiple tests with different configurations
The service will help you generate load on your target API so you can explore Victoria Metrics and analyze the performance metrics.

Run stress test:

curl -X POST http://localhost:8081/run-test \
  -H "Content-Type: application/json" \
  -d '{
    "seconds": 120,
    "requests": 1000
  }'

curl -X POST http://localhost:8081/run-test \
  -H "Content-Type: application/json" \
  -d '{
    "seconds": 60,
    "requests": 100,
    "endpoints": [
      {"path": "/", "method": "GET"},
      {"path": "/status", "method": "GET"},
      {"path": "/submit", "method": "POST", "data": {"name": "Test User", "email": "test@example.com"}}
    ]
  }'

Check the test status and results:
curl http://localhost:8081/status

View or update the configuration:
curl http://localhost:8081/config

make stress-test

make stress-test-custom SECONDS=60 REQUESTS=500