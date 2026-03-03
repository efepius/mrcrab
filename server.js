const path = require('path');
const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = Number(process.env.PORT || 3000);

app.use(cors());
app.use(express.json({ limit: '1mb' }));

app.use(express.static(__dirname));
app.use('/kimmy', express.static(path.join(__dirname, 'kimmy')));

app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'kimmy-server',
    ts: Date.now(),
    hasAnthropicKey: Boolean(process.env.ANTHROPIC_API_KEY)
  });
});

// Backward-compatible status endpoint used by older UI.
app.get('/api/lodoclaw/status', (req, res) => {
  res.json({
    ok: true,
    status: 'online',
    service: 'kimmy-server',
    ts: Date.now()
  });
});

app.post('/api/connect', async (req, res) => {
  if (!process.env.ANTHROPIC_API_KEY) {
    return res.status(400).json({
      ok: false,
      error: 'ANTHROPIC_API_KEY is missing in environment.'
    });
  }

  const model = req.body?.model || 'claude-sonnet-4-20250514';
  return res.json({
    ok: true,
    message: 'Server reachable and API key configured.',
    model
  });
});

// === Kimmy: Claude AI Proxy ===
const https = require('https');
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY || '';

app.post('/api/kimmy/chat', (req, res) => {
  if (!ANTHROPIC_KEY) {
    return res.status(503).json({ error: 'ANTHROPIC_API_KEY not set in .env' });
  }

  const { messages, system, max_tokens, temperature, stream } = req.body;
  if (!messages || !Array.isArray(messages)) {
    return res.status(400).json({ error: 'messages array required' });
  }

  const payload = JSON.stringify({
    model: req.body.model || 'claude-sonnet-4-20250514',
    max_tokens: max_tokens || 1024,
    temperature: temperature ?? 0.6,
    system: system || '',
    messages,
    stream: !!stream,
  });

  const options = {
    hostname: 'api.anthropic.com',
    path: '/v1/messages',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': ANTHROPIC_KEY,
      'anthropic-version': '2023-06-01',
      'Content-Length': Buffer.byteLength(payload),
    },
  };

  const proxyReq = https.request(options, (proxyRes) => {
    if (stream) {
      res.writeHead(proxyRes.statusCode, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      });
      proxyRes.pipe(res);
    } else {
      let body = '';
      proxyRes.on('data', (chunk) => body += chunk);
      proxyRes.on('end', () => {
        try {
          res.status(proxyRes.statusCode).json(JSON.parse(body));
        } catch (e) {
          res.status(502).json({ error: 'Bad response from Claude API', detail: body.slice(0, 500) });
        }
      });
    }
  });

  proxyReq.on('error', (e) => {
    res.status(502).json({ error: 'Claude API unreachable', detail: e.message });
  });

  proxyReq.write(payload);
  proxyReq.end();
});

app.get('/api/kimmy/status', (req, res) => {
  res.json({ active: !!ANTHROPIC_KEY, model: 'claude-sonnet-4-20250514' });
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

function startServer(port) {
  const server = app.listen(port, () => {
    console.log(`Kimmy server running on http://localhost:${port}`);
  });

  server.on('error', (err) => {
    if (err && err.code === 'EADDRINUSE' && !process.env.PORT && port === 3000) {
      console.warn('Port 3000 is busy, falling back to port 3001...');
      startServer(3001);
      return;
    }
    throw err;
  });
}

startServer(PORT);
