"""
AI Receptionist — WhatsApp version (stable prototype)
Stack: Flask + Groq + Twilio WhatsApp Sandbox + Telegram + SQLite
Cost: €0
"""

import json
import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP    = "whatsapp:+14155238886"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHEF_CHAT_ID       = os.getenv("CHEF_CHAT_ID")
DELIVERY_CHAT_ID   = os.getenv("DELIVERY_CHAT_ID")

RESTAURANT_NAME    = os.getenv("RESTAURANT_NAME", "Mon Restaurant")

MENU = """
- Burger classique : 8€
- Burger double : 11€
- Kebab : 7€
- Pizza margherita : 9€
- Pizza 4 fromages : 11€
- Frites : 3€
- Salade : 4€
- Coca-Cola : 2€
- Eau : 1€
"""

RESET_COMMANDS = ["annuler", "reset", "recommencer", "stop", "cancel"]

# ─── DATABASE ─────────────────────────────────────────────────────────────────

DB = "orders.db"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nom       TEXT,
            type      TEXT,
            items     TEXT,
            adresse   TEXT,
            temps     TEXT,
            total     TEXT,
            status    TEXT DEFAULT 'en attente',
            created_at TEXT
        )
    """)
    con.commit()
    con.close()

def save_order(order: dict) -> int:
    con = sqlite3.connect(DB)
    cur = con.execute(
        "INSERT INTO orders (nom, type, items, adresse, temps, total, created_at) VALUES (?,?,?,?,?,?,?)",
        (
            order.get("nom"),
            order.get("type"),
            ", ".join(order.get("items", [])),
            order.get("adresse"),
            order.get("temps"),
            order.get("total_estime"),
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
    )
    order_id = cur.lastrowid
    con.commit()
    con.close()
    return order_id

def get_orders():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return rows

def update_status(order_id: int, status: str):
    con = sqlite3.connect(DB)
    con.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    con.commit()
    con.close()

init_db()

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""Tu es le réceptionniste WhatsApp de {RESTAURANT_NAME}.
Réponds toujours en français, ton chaleureux et professionnel.
Tes messages sont courts car c'est WhatsApp.

MENU:
{MENU}

RÈGLES IMPORTANTES:
- Ne propose QUE les plats du menu ci-dessus, rien d'autre
- Si le client demande quelque chose qui n'est pas au menu, dis-lui poliment que ce n'est pas disponible

ÉTAPES:
1. Accueil + demander le nom si pas donné
2. Prendre la commande
3. Demander: sur place / à emporter / livraison
4. Si livraison: demander l'adresse complète
5. Si à emporter: demander l'heure d'arrivée
6. Récapituler et demander confirmation

Quand le client confirme sa commande, ajoute ce bloc JSON à la fin:
##ORDER##
{{"nom":"...","type":"livraison|emporter|surplace","temps":"... ou null","items":["..."],"adresse":"... ou null","total_estime":"...€"}}
##END##

Ne génère le JSON QUE quand le client dit explicitement oui/confirme.
"""

# ─── SESSION STORE ────────────────────────────────────────────────────────────

sessions = {}

# ─── GROQ ─────────────────────────────────────────────────────────────────────

groq_client = Groq(api_key=GROQ_API_KEY)

def ask_groq(user_id: str, message: str) -> str:
    if user_id not in sessions:
        sessions[user_id] = []
    sessions[user_id].append({"role": "user", "content": message})
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + sessions[user_id],
        max_tokens=300,
        temperature=0.5,
    )
    reply = response.choices[0].message.content
    sessions[user_id].append({"role": "assistant", "content": reply})
    return reply

# ─── ORDER PARSING ────────────────────────────────────────────────────────────

def extract_order(text: str):
    match = re.search(r"##ORDER##\s*(.*?)\s*##END##", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

def clean_reply(text: str) -> str:
    return re.sub(r"##ORDER##.*?##END##", "", text, flags=re.DOTALL).strip()

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(chat_id: str, message: str, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def answer_callback(callback_query_id: str, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id, "text": text})

def edit_telegram_message(chat_id: str, message_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    requests.post(url, json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"})

def notify_order(order: dict, order_id: int):
    items_str  = "\n".join(f"  • {item}" for item in order["items"])
    addr_line  = f"\n📍 <b>Adresse:</b> {order['adresse']}" if order.get("adresse") else ""
    temps_line = f"\n⏰ <b>Heure:</b> {order['temps']}" if order.get("temps") else ""
    type_emoji = {"livraison": "🛵", "emporter": "🥡", "surplace": "🍽️"}.get(order["type"], "📦")

    msg_chef = (
        f"🔔 <b>Nouvelle commande #{order_id}</b>\n"
        f"👤 <b>Client:</b> {order['nom']}\n"
        f"{type_emoji} <b>Type:</b> {order['type'].upper()}\n"
        f"🍔 <b>Commande:</b>\n{items_str}\n"
        f"💶 <b>Total estimé:</b> {order.get('total_estime', '?')}"
        f"{addr_line}{temps_line}"
    )
    # Chef gets a "mark as ready" button
    chef_markup = {"inline_keyboard": [[
        {"text": "✅ Marquer comme prêt", "callback_data": f"ready:{order_id}"}
    ]]}
    send_telegram(CHEF_CHAT_ID, msg_chef, reply_markup=chef_markup)

    # Delivery guy gets notified only when chef marks order as ready

# ─── WHATSAPP WEBHOOK ─────────────────────────────────────────────────────────

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.form.get("Body", "").strip()
    sender   = request.form.get("From", "")

    # Reset command
    if incoming.lower() in RESET_COMMANDS:
        sessions.pop(sender, None)
        resp = MessagingResponse()
        resp.message("Conversation réinitialisée. Bonjour, comment puis-je vous aider ?")
        return str(resp)

    ai_reply = ask_groq(sender, incoming)
    order    = extract_order(ai_reply)
    text     = clean_reply(ai_reply)

    if order:
        order_id = save_order(order)
        notify_order(order, order_id)
        sessions.pop(sender, None)
        text += "\n\n✅ Commande enregistrée ! Merci et à bientôt 🙏"

    resp = MessagingResponse()
    resp.message(text)
    return str(resp)

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route("/telegram", methods=["POST"])
def telegram_callback():
    data = request.get_json()
    if "callback_query" not in data:
        return "ok"

    cb         = data["callback_query"]
    cb_id      = cb["id"]
    cb_data    = cb["data"]
    chat_id    = str(cb["message"]["chat"]["id"])
    message_id = cb["message"]["message_id"]

    action, order_id = cb_data.split(":")
    order_id = int(order_id)

    if action == "delivered":
        update_status(order_id, "livré")
        answer_callback(cb_id, "Commande marquée comme livrée ✅")
        edit_telegram_message(chat_id, message_id,
            cb["message"]["text"] + "\n\n✅ <b>LIVRÉ</b>")

    elif action == "ready":
        update_status(order_id, "prêt")
        answer_callback(cb_id, "Commande marquée comme prête ✅")
        edit_telegram_message(chat_id, message_id,
            cb["message"]["text"] + "\n\n✅ <b>PRÊT</b>")

        # Now notify delivery guy if it's a delivery order
        if DELIVERY_CHAT_ID and DELIVERY_CHAT_ID != CHEF_CHAT_ID:
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            con.close()
            if order and order["type"] == "livraison":
                msg_delivery = (
                    f"🛵 <b>Livraison #{order_id} — PRÊTE</b>\n"
                    f"👤 <b>Client:</b> {order['nom']}\n"
                    f"📍 <b>Adresse:</b> {order['adresse']}\n"
                    f"🍔 <b>Commande:</b> {order['items']}"
                )
                delivery_markup = {"inline_keyboard": [[
                    {"text": "✅ Marquer comme livré", "callback_data": f"delivered:{order_id}"}
                ]]}
                send_telegram(DELIVERY_CHAT_ID, msg_delivery, reply_markup=delivery_markup)

    return "ok"



@app.route("/dashboard")
def dashboard():
    orders = get_orders()
    rows = "".join(
        f"""<tr>
            <td>{o['id']}</td>
            <td>{o['created_at']}</td>
            <td>{o['nom']}</td>
            <td>{o['type']}</td>
            <td>{o['items']}</td>
            <td>{o['adresse'] or '—'}</td>
            <td>{o['temps'] or '—'}</td>
            <td>{o['total'] or '?'}</td>
            <td>
              <select onchange="updateStatus({o['id']}, this.value)">
                <option {'selected' if o['status']=='en attente' else ''}>en attente</option>
                <option {'selected' if o['status']=='en préparation' else ''}>en préparation</option>
                <option {'selected' if o['status']=='prêt' else ''}>prêt</option>
                <option {'selected' if o['status']=='livré' else ''}>livré</option>
              </select>
            </td>
          </tr>"""
        for o in orders
    ) or "<tr><td colspan='9'>Aucune commande</td></tr>"

    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta http-equiv="refresh" content="15">
<title>{RESTAURANT_NAME} — Commandes</title>
<style>
  body{{font-family:sans-serif;padding:2rem;background:#f9f9f9;font-size:14px}}
  h1{{margin-bottom:1rem}}
  table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden}}
  th{{background:#1D9E75;color:#fff;padding:10px 14px;text-align:left}}
  td{{padding:10px 14px;border-bottom:1px solid #eee}}
  select{{padding:4px 8px;border-radius:4px;border:1px solid #ddd;font-size:13px}}
</style></head><body>
<h1>🍔 {RESTAURANT_NAME} — Commandes</h1>
<table><thead><tr>
  <th>#</th><th>Heure</th><th>Client</th><th>Type</th>
  <th>Commande</th><th>Adresse</th><th>Arrivée</th><th>Total</th><th>Statut</th>
</tr></thead><tbody>{rows}</tbody></table>
<script>
function updateStatus(id, status) {{
  fetch('/status/' + id + '/' + encodeURIComponent(status));
}}
</script>
</body></html>"""

@app.route("/status/<int:order_id>/<status>")
def set_status(order_id, status):
    update_status(order_id, status)
    return "ok"

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print(f"  {RESTAURANT_NAME} — Réceptionniste WhatsApp")
    print("=" * 50)
    print("  1. Run ngrok:      ngrok http 5000")
    print("  2. Twilio webhook: https://<ngrok-url>/whatsapp")
    print("  3. Dashboard:      http://localhost:5000/dashboard")
    print("  Reset command:     customer sends 'annuler'")
    print("=" * 50)
    app.run(debug=True, port=5000)
