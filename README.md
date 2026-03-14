# 🍔 WhatsApp AI Receptionist

> A zero-budget AI receptionist for restaurants — takes orders over WhatsApp, notifies the chef and delivery guy via Telegram, and tracks everything on a live dashboard.

---

## What it does

- Customers send a WhatsApp message to the restaurant
- An AI bot replies in French, takes the full order (name, items, delivery/pickup/dine-in, address)
- Once confirmed, the chef gets a Telegram notification instantly
- Chef marks the order as ready → delivery guy gets notified automatically with the address
- Everything is tracked on a live web dashboard with status updates

## Stack

| Layer | Tech | Cost |
|---|---|---|
| AI brain | Groq (Llama 3.3 70B) | Free |
| Messaging | Twilio WhatsApp Sandbox | Free |
| Notifications | Telegram Bot API | Free |
| Backend | Python + Flask | Free |
| Tunnel | Cloudflare Tunnel | Free |
| Database | SQLite | Free |

**Total cost: €0**

---

## Demo

```
Customer:  Bonjour je voudrais commander
Bot:       Bonjour ! Bienvenue chez Chez Yasser 🍔 Puis-je avoir votre nom ?
Customer:  Ahmed
Bot:       Bonjour Ahmed ! Que souhaitez-vous commander ?
Customer:  Un kebab et deux cocas
Bot:       Super ! C'est pour sur place, à emporter ou en livraison ?
Customer:  Livraison au 23 rue Thiers
Bot:       Récapitulatif : 1 Kebab + 2 Coca-Cola → livraison au 23 rue Thiers. Total estimé : 11€. Je confirme ?
Customer:  Oui
Bot:       ✅ Commande enregistrée ! Merci et à bientôt 🙏
```

*Chef receives Telegram notification immediately. Delivery guy notified when order is ready.*

---

## Setup

### Prerequisites

- Python 3.10+
- A [Groq](https://console.groq.com) account (free)
- A [Twilio](https://twilio.com) account (free trial)
- A Telegram account
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) installed

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/whatsapp-ai-receptionist
cd whatsapp-ai-receptionist
```

### 2. Install dependencies

```bash
pip install flask twilio groq requests python-dotenv
```

### 3. Configure environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=your_groq_api_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
CHEF_CHAT_ID=your_telegram_chat_id
DELIVERY_CHAT_ID=delivery_guy_telegram_chat_id
RESTAURANT_NAME=Your Restaurant Name
```

> **How to get each key:**
> - **Groq**: [console.groq.com](https://console.groq.com) → API Keys → Create
> - **Twilio**: [twilio.com/console](https://twilio.com/console) → Account SID + Auth Token
> - **Telegram bot**: message [@BotFather](https://t.me/BotFather) → `/newbot`
> - **Telegram chat ID**: message [@userinfobot](https://t.me/userinfobot) → `/start`

### 4. Join the Twilio WhatsApp Sandbox

Go to Twilio Console → Messaging → Try it out → Send a WhatsApp message.

Send the join code from your WhatsApp to the sandbox number to activate it.

### 5. Start the tunnel

```bash
cloudflared tunnel --url http://localhost:5000
```

Copy the URL (e.g. `https://xyz.trycloudflare.com`).

### 6. Set the Twilio webhook

Go to Twilio Console → Messaging → Try it out → Send a WhatsApp message → Sandbox Settings.

Set **"When a message comes in"** to:
```
https://xyz.trycloudflare.com/whatsapp
```

### 7. Set the Telegram webhook

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://xyz.trycloudflare.com/telegram"
```

### 8. Run

```bash
python3 app.py
```

Dashboard available at: `http://localhost:5000/dashboard`

---

## Project structure

```
.
├── app.py          # Main Flask app
├── .env            # Credentials (never commit this)
├── .env.example    # Template for credentials
├── .gitignore
├── orders.db       # SQLite database (auto-created)
└── README.md
```

---

## Resetting a conversation

If a customer gets stuck, they can send any of these to restart:

```
annuler / reset / recommencer / stop / cancel
```

---

## Roadmap

- [ ] Multi-language support
- [ ] Voice call support (Twilio Voice + Whisper STT)
- [ ] Multi-restaurant support
- [ ] Payment integration
- [ ] WhatsApp Business API (production)

---

## License

MIT
