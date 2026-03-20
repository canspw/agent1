# agent1
# created 20Mar2026



docker build -t data-access-agent .
docker build --no-cache -t data-access-agent .

docker run -p 8001:8000 data-access-agent
docker run --rm -p 8000:8000 data-access-agent

http://localhost:8000

curl -X POST http://localhost:8000/ingest-email \
-H "Content-Type: application/json" \
-d '{
  "sender": "alex@company.com",
  "subject": "Need customer data",
  "body": "I need customer data for a marketing campaign and want to download a sample."
}'

docker run --rm -p 8000:8000 -v $(pwd):/app data-access-agent-dev uvicorn app:app --host 0.0.0.0 --port 8000 --reload

#How to run within docker engine:
docker run --rm -it data-access-agent sh
then, "ls"

