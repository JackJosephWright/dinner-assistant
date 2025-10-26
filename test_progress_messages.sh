#!/bin/bash
# Test script to see progress messages in action

echo "Testing progress messages..."
echo ""
echo "Sending chat request: 'I need recipes for chicken, tacos, salmon'"
echo "Watch the progress stream below:"
echo "======================================"
echo ""

# Start listening to progress stream in background
curl -N http://localhost:5000/api/progress/test-session &
PROGRESS_PID=$!

# Give it a moment to connect
sleep 1

# Send the chat request
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need recipes for chicken, tacos, salmon", "session_id": "test-session"}' \
  2>/dev/null | python3 -m json.tool

# Let progress messages finish
sleep 2

# Kill the progress listener
kill $PROGRESS_PID 2>/dev/null

echo ""
echo "======================================"
echo "Test complete!"
