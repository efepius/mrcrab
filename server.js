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
