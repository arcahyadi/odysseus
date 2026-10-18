# Graphify MCP — Knowledge Graph service
# Pre-installs heavy dependencies to avoid startup delay
FROM python:3.12-slim

LABEL com.agentos.role=knowledge-graph
LABEL com.agentos.description="Graphify MCP — Knowledge Graph generation and query"

# Install graphifyy with MCP v1.x (v2 breaks list_tools API)
RUN pip install --no-cache-dir "mcp<2" graphifyy

# Required by graphify for graph operations
RUN pip install --no-cache-dir networkx pyvis

# Create non-root user
RUN useradd -m -s /bin/bash graphify
USER graphify
WORKDIR /home/graphify

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "/workspace/mcp_servers/graphify_mcp.py"]
