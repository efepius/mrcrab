# LodoClaw System

Complete LodoClaw system with 2-pass verification and 4-tier safety.

## Features
- **LodoClaw Protocol**: 2-pass verification (base64 + SHA256)
- **4-Tier Safety**: Input validation, rate limiting, sanitization, output verification
- **Celebration System**: Visual feedback on every success
- **JSON Storage**: Fast, simple persistence

## Quick Start
npm start
Then open http://localhost:3000

## API
- POST /api/lodoclaw/verify - Verify with LodoClaw 2-pass
- GET /api/lodoclaw/status - System status
- GET /api/celebrations - Celebration events
- GET /api/safety/status - Safety tier status
