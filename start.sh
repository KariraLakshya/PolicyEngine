#!/bin/bash
if [ "$SERVICE_TYPE" = "mcp" ]; then
    python -m mcp_server.server
else
    uvicorn api.server:app --host 0.0.0.0 --port $PORT
fi
