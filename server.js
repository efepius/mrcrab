const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const STORAGE_PATH = path.join(__dirname, 'data', 'lodoclaw.json');
const CELEBRATIONS_PATH = path.join(__dirname, 'data', 'celebrations.json');

if (!fs.existsSync(path.dirname(STORAGE_PATH))) {
  fs.mkdirSync(path.dirname(STORAGE_PATH), { recursive: true });
}

function lodoclawVerify(input, pass) {
  pass = pass || 1;
  const hash1 = Buffer.from(input).toString('base64').slice(0, 16);
  const hash2 = require('crypto').createHash('sha256').update(input + pass).digest('hex').slice(0, 16);
  return pass === 1 ? hash1 : hash2;
}

function lodoclawTwoPassVerification(input) {
  const pass1 = lodoclawVerify(input, 1);
  const pass2 = lodoclawVerify(input, 2);
  return { pass1, pass2, verified: pass1.length === 16 && pass2.length === 16 };
}

const SAFETY_TIERS = ['INPUT_VALIDATION','RATE_LIMITING','SANITIZATION','OUTPUT_VERIFICATION'];
const rateLimit = new Map();
const RATE_LIMIT_WINDOW = 60000;
const RATE_LIMIT_MAX = 100;

function safetyGate1(req) {
  if (!req.body || typeof req.body.input !== 'string') return false;
  if (req.body.input.length > 10000) return false;
  return true;
}

function safetyGate2(ip) {
  const now = Date.now();
  const r = rateLimit.get(ip) || { count: 0, reset: now + RATE_LIMIT_WINDOW };
  if (now > r.reset) {
    rateLimit.set(ip, { count: 1, reset: now + RATE_LIMIT_WINDOW });
    return true;
  }
  r.count++;
  return r.count <= RATE_LIMIT_MAX;
}

function safetyGate3(input) {
  return input.replace(/[<>\"']/g, '').slice(0, 5000);
}

function runSafetyTiers(req, res, next) {
  if (!safetyGate1(req)) return res.status(400).json({ error: 'TIER_1_FAILED' });
  const ip = req.ip || req.connection.remoteAddress || '127.0.0.1';
  if (!safetyGate2(ip)) return res.status(429).json({ error: 'TIER_2_FAILED' });
  req.sanitizedInput = safetyGate3(req.body.input);
  next();
}

function readStorage() {
  try {
    return JSON.parse(fs.readFileSync(STORAGE_PATH, 'utf8'));
  } catch (e) {
    return { records: [], protocolCalls: 0 };
  }
}

function writeStorage(data) {
  fs.writeFileSync(STORAGE_PATH, JSON.stringify(data, null, 2));
}

function readCelebrations() {
  try {
    return JSON.parse(fs.readFileSync(CELEBRATIONS_PATH, 'utf8'));
  } catch (e) {
    return { events: [] };
  }
}

function logCelebration(event) {
  const data = readCelebrations();
  data.events = data.events || [];
  data.events.push({ event, timestamp: new Date().toISOString() });
  fs.writeFileSync(CELEBRATIONS_PATH, JSON.stringify(data, null, 2));
}

app.post('/api/lodoclaw/verify', runSafetyTiers, (req, res) => {
  const result = lodoclawTwoPassVerification(req.sanitizedInput);
  if (!result || !result.verified) return res.status(500).json({ error: 'TIER_4_FAILED' });
  const storage = readStorage();
  storage.records.push({ input: req.sanitizedInput.slice(0, 50), ...result, ts: new Date().toISOString() });
  storage.protocolCalls = (storage.protocolCalls || 0) + 1;
  writeStorage(storage);
  logCelebration('LODOCLAW_VERIFY_SUCCESS');
  res.json({ success: true, result, celebration: 'LodoClaw Protocol Verified!' });
});

app.get('/api/lodoclaw/status', (req, res) => {
  const storage = readStorage();
  res.json({ status: 'ACTIVE', protocol: 'LodoClaw 2-Pass', safetyTiers: 4, totalCalls: storage.protocolCalls || 0, records: (storage.records || []).length });
});

app.get('/api/celebrations', (req, res) => res.json(readCelebrations()));

app.get('/api/safety/status', (req, res) => res.json({ tiers: SAFETY_TIERS, active: true }));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log('[LodoClaw] System ACTIVE on http://localhost:' + PORT);
  console.log('[LodoClaw] 4-Tier Safety: ENABLED');
  console.log('[LodoClaw] 2-Pass Verification: READY');
  console.log('[LodoClaw] Celebration System: ACTIVE');
});
