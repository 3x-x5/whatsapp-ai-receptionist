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

## Where this is going

This started as a prototype to validate the idea. The goal is to turn it into a proper product that any restaurant can plug into in under 10 minutes.

The commercial version will use real phone calls — customers call a number, the AI picks up and talks to them — in addition to WhatsApp. Orders will sync across devices in real time. The dashboard will be a proper web app with analytics: peak hours, most ordered items, average order value. Restaurants will be able to customize their menu, bot personality, and working hours from a simple interface.

The AI layer will be upgraded to handle edge cases better — customers who change their mind mid-order, unclear addresses, items that are temporarily unavailable. The bot should feel like a real person took the call, not a form you're filling out over chat.

The infrastructure will move from a local machine to a proper hosted backend, with each restaurant getting their own isolated instance. Onboarding will be automated — a restaurant owner fills in a form, connects their WhatsApp number, and the bot is live within minutes.

The end goal is a system that any small restaurant owner can afford and actually use, without needing a developer on call.

---

## License

MIT
