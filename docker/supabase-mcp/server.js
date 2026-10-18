const http = require('http');
const { spawn } = require('child_process');

const PORT = process.env.PORT || 54321;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ service: 'supabase-mcp', status: 'ok' }));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Supabase MCP HTTP bridge listening on port ${PORT}`);

  const child = spawn('mcp-server-supabase', [], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env }
  });

  child.stderr.on('data', (data) => console.error(`mcp: ${data}`));
  child.on('exit', (code) => console.log(`mcp-server exited with code ${code}`));
});
