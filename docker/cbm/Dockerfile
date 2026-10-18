FROM node:22-slim
RUN npm install -g codebase-memory-mcp
EXPOSE 9749
ENV REPO_PATH=/workspace
ENV MCP_PORT=9749
CMD ["sh", "-c", "while true; do codebase-memory-mcp; sleep 1; done"]
