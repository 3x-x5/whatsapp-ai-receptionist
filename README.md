# WhatsApp AI Receptionist

A self-hosted AI receptionist for restaurants. Customers order via WhatsApp, the kitchen gets notified on Telegram, and the delivery guy gets pinged automatically when the order is ready. Built to run at zero cost.

---

## The idea

Most small restaurants still take orders by phone. It's slow, it's error-prone, and it ties up staff. This project replaces that with a WhatsApp bot that handles the full order flow — from greeting the customer to confirming the order and routing it to the right person.

No cloud bills. No subscriptions. Runs on your own machine.

---

## How it works

A customer messages the restaurant on WhatsApp. The bot asks for their name, takes their order from the menu, asks if it's delivery, pickup or dine-in, and if delivery — gets the address. Once the customer confirms, the order is saved and the chef gets a Telegram notification with a single tap to mark it as ready. When the chef marks it ready, the delivery guy gets notified automatically with the full address. Everything shows up on a local dashboard that auto-refreshes.

---

## Stack

- **AI** — Groq (Llama 3.3 70B) — free tier
- **Messaging** — Twilio WhatsApp Sandbox — free tier
- **Notifications** — Telegram Bot API — free
- **Backend** — Python + Flask
- **Tunnel** — Cloudflare Tunnel — free
- **Database** — SQLite

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/3x-x5/whatsapp-ai-receptionist
cd whatsapp-ai-receptionist
pip install flask twilio groq requests python-dotenv
```

### 2. Configure

```bash
cp env.example .env
```

Fill in your `.env`:

```env
GROQ_API_KEY=your_groq_api_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
CHEF_CHAT_ID=chef_telegram_chat_id
DELIVERY_CHAT_ID=delivery_telegram_chat_id
RESTAURANT_NAME=Your Restaurant Name
```

Where to get each:
- **Groq key** → [console.groq.com](https://console.groq.com) → API Keys
- **Twilio credentials** → [twilio.com/console](https://twilio.com/console)
- **Telegram bot token** → message @BotFather on Telegram → `/newbot`
- **Telegram chat ID** → message @userinfobot on Telegram → `/start`

### 3. Join the Twilio WhatsApp sandbox

Twilio Console → Messaging → Try it out → Send a WhatsApp message → follow the join instructions.

### 4. Start the tunnel

```bash
cloudflared tunnel --url http://localhost:5000
```

Copy the URL it gives you.

### 5. Set webhooks

In Twilio sandbox settings, set the incoming message webhook to:
```
https://your-tunnel-url/whatsapp
```

For Telegram button callbacks:
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-tunnel-url/telegram"
```

### 6. Run

```bash
python3 app.py
```

Dashboard: `http://localhost:5000/dashboard`

---

## Conversation reset

If a customer wants to start over, they can send: `annuler`, `reset`, `recommencer`, `stop`, or `cancel`.

---

## Roadmap

The current version is a functional prototype built to validate the core concept. The production version is planned around a more robust and scalable architecture.

**AI layer** — migrate from Groq/Llama to the Claude API (Anthropic) for significantly better instruction-following, context retention across long conversations, and handling of ambiguous or incomplete orders. Claude's tool use feature will be used to structure order extraction more reliably instead of relying on prompt-injected JSON parsing.

**Voice channel** — integrate Twilio Programmable Voice with a speech-to-text pipeline so customers can call a real phone number and speak their order. The AI processes the transcription in real time and responds via Twilio's TTS engine, making the interaction feel like a natural phone call.

**Messaging** — move from the Twilio WhatsApp Sandbox to the official WhatsApp Business API for production use, enabling outbound messages, order status updates sent back to the customer, and multi-agent inbox management.

**Backend** — replace Flask + SQLite with a proper stack: PostgreSQL for persistence, Redis for session management, and a background task queue (Celery) for handling notifications asynchronously. The server moves from a local machine to a VPS, with each restaurant getting an isolated deployment.

**Dashboard** — rebuild as a React SPA with real-time order updates over WebSocket, per-restaurant analytics (peak hours, most ordered items, average ticket), and a configuration panel where restaurant owners manage their menu, opening hours, and bot behavior without touching code.

**Onboarding** — fully automated provisioning pipeline: a restaurant fills out a form, connects their WhatsApp Business number, and gets a live bot within minutes. No developer involvement required after initial setup.

---

## License

MIT
