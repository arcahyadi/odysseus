FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN npm install -g @supabase/mcp-server-supabase express cors
COPY server.js /server.js
EXPOSE 54321
ENV SUPABASE_URL=http://localhost:54321
ENV SUPABASE_ANON_KEY=placeholder
CMD ["node", "/server.js"]
