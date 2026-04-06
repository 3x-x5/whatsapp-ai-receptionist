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

GROQ_KEY = os.getenv("GROQ_API_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
WA_NUMBER = "whatsapp:+14155238886"  # sandbox twilio, a changer en prod

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHEF_ID = os.getenv("CHEF_CHAT_ID")
LIVREUR_ID = os.getenv("DELIVERY_CHAT_ID")

RESTO = os.getenv("RESTAURANT_NAME", "Mon Restaurant")

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

# mots qui reset la conversation cote client
RESETS = ["annuler", "reset", "recommencer", "stop", "cancel"]

DB = "orders.db"


def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            type TEXT,
            items TEXT,
            adresse TEXT,
            temps TEXT,
            total TEXT,
            status TEXT DEFAULT 'en attente',
            created_at TEXT
        )
    """)
    con.commit()
    con.close()


def save_order(order):
    try:
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
        oid = cur.lastrowid
        con.commit()
        con.close()
        return oid
    except Exception as e:
        print(f"[db] erreur save_order: {e}")
        return None


def get_orders():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return rows


def set_status(oid, status):
    con = sqlite3.connect(DB)
    con.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    con.commit()
    con.close()


init_db()

PROMPT = f"""Tu es le réceptionniste WhatsApp de {RESTO}.
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

# dict pour garder l'historique par numero whatsapp
# NOTE: si on redémarre le serveur tout est perdu, faudra passer a redis un jour
convos = {}

groq_client = Groq(api_key=GROQ_KEY)


def chat(uid, msg):
    if uid not in convos:
        convos[uid] = []
    convos[uid].append({"role": "user", "content": msg})

    try:
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": PROMPT}] + convos[uid],
            max_tokens=300,
            temperature=0.5,
        )
        reply = res.choices[0].message.content
    except Exception as e:
        print(f"[groq] erreur: {e}")
        return "Désolé, une erreur est survenue. Réessayez dans un instant."

    convos[uid].append({"role": "assistant", "content": reply})
    return reply


def parse_order(text):
    # le modele met le json entre ##ORDER## et ##END##
    m = re.search(r"##ORDER##\s*(.*?)\s*##END##", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        print("[parse] json invalide dans la reponse du modele")
        return None


def strip_json(text):
    # enleve le bloc order du message avant de l'envoyer au client
    return re.sub(r"##ORDER##.*?##END##", "", text, flags=re.DOTALL).strip()


def tg_send(cid, txt, btns=None):
    if not TG_TOKEN or not cid:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    body = {"chat_id": cid, "text": txt, "parse_mode": "HTML"}
    if btns:
        body["reply_markup"] = btns
    try:
        requests.post(url, json=body, timeout=5)
    except Exception as e:
        print(f"[telegram] send failed: {e}")


def tg_ack(cb_id, txt):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": cb_id, "text": txt}, timeout=5)


def tg_edit(cid, mid, txt):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/editMessageText"
    requests.post(url, json={"chat_id": cid, "message_id": mid, "text": txt, "parse_mode": "HTML"}, timeout=5)


def ping_chef(order, oid):
    lignes = "\n".join(f"  - {i}" for i in order["items"])
    addr = f"\nAdresse: {order['adresse']}" if order.get("adresse") else ""
    heure = f"\nHeure souhaitee: {order['temps']}" if order.get("temps") else ""

    msg = (
        f"<b>Commande #{oid}</b>\n"
        f"Client: {order['nom']}\n"
        f"Type: {order['type'].upper()}\n"
        f"Commande:\n{lignes}\n"
        f"Total: {order.get('total_estime', '?')}"
        f"{addr}{heure}"
    )
    btns = {"inline_keyboard": [[{"text": "Marquer comme pret", "callback_data": f"ready:{oid}"}]]}
    tg_send(CHEF_ID, msg, btns)


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    body = request.form.get("Body", "").strip()
    sender = request.form.get("From", "")

    resp = MessagingResponse()

    if not body:
        return str(resp)

    if body.lower() in RESETS:
        convos.pop(sender, None)
        resp.message("Conversation reinitialisee. Bonjour, comment puis-je vous aider ?")
        return str(resp)

    reply = chat(sender, body)
    order = parse_order(reply)
    txt = strip_json(reply)

    if order:
        oid = save_order(order)
        if oid:
            ping_chef(order, oid)
            convos.pop(sender, None)
            txt += "\n\nCommande enregistree, merci !"
        else:
            txt += "\n\n(erreur enregistrement, contactez le restaurant directement)"

    resp.message(txt)
    return str(resp)


@app.route("/telegram", methods=["POST"])
def tg_webhook():
    data = request.get_json(silent=True)
    if not data or "callback_query" not in data:
        return "ok"

    cb = data["callback_query"]
    cb_id = cb["id"]
    chat_id = str(cb["message"]["chat"]["id"])
    mid = cb["message"]["message_id"]
    orig_txt = cb["message"]["text"]

    try:
        action, oid = cb["data"].split(":")
        oid = int(oid)
    except ValueError:
        return "ok"

    if action == "delivered":
        set_status(oid, "livre")
        tg_ack(cb_id, "Marque comme livre")
        tg_edit(chat_id, mid, orig_txt + "\n\n<b>LIVRE</b>")

    elif action == "ready":
        set_status(oid, "pret")
        tg_ack(cb_id, "Marque comme pret")
        tg_edit(chat_id, mid, orig_txt + "\n\n<b>PRET</b>")

        # prevenir le livreur seulement si c'est une livraison
        if LIVREUR_ID and LIVREUR_ID != CHEF_ID:
            try:
                con = sqlite3.connect(DB)
                con.row_factory = sqlite3.Row
                o = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
                con.close()
                if o and o["type"] == "livraison":
                    msg = (
                        f"<b>Livraison #{oid} prete</b>\n"
                        f"Client: {o['nom']}\n"
                        f"Adresse: {o['adresse']}\n"
                        f"Commande: {o['items']}"
                    )
                    btns = {"inline_keyboard": [[{"text": "Marquer comme livre", "callback_data": f"delivered:{oid}"}]]}
                    tg_send(LIVREUR_ID, msg, btns)
            except Exception as e:
                print(f"[tg_webhook] erreur notif livreur: {e}")

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
            <td>{o['adresse'] or '-'}</td>
            <td>{o['temps'] or '-'}</td>
            <td>{o['total'] or '?'}</td>
            <td>
              <select onchange="maj({o['id']}, this.value)">
                <option {'selected' if o['status']=='en attente' else ''}>en attente</option>
                <option {'selected' if o['status']=='en preparation' else ''}>en preparation</option>
                <option {'selected' if o['status']=='pret' else ''}>pret</option>
                <option {'selected' if o['status']=='livre' else ''}>livre</option>
              </select>
            </td>
          </tr>"""
        for o in orders
    ) or "<tr><td colspan='9'>Aucune commande</td></tr>"

    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta http-equiv="refresh" content="15">
<title>{RESTO}</title>
<style>
  body{{font-family:sans-serif;padding:2rem;background:#f9f9f9;font-size:14px}}
  h1{{margin-bottom:1rem}}
  table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden}}
  th{{background:#1D9E75;color:#fff;padding:10px 14px;text-align:left}}
  td{{padding:10px 14px;border-bottom:1px solid #eee}}
  select{{padding:4px 8px;border-radius:4px;border:1px solid #ddd;font-size:13px}}
</style></head><body>
<h1>{RESTO} — commandes</h1>
<table><thead><tr>
  <th>#</th><th>Heure</th><th>Client</th><th>Type</th>
  <th>Commande</th><th>Adresse</th><th>Arrivee</th><th>Total</th><th>Statut</th>
</tr></thead><tbody>{rows}</tbody></table>
<script>
function maj(id, status) {{
  fetch('/status/' + id + '/' + encodeURIComponent(status));
}}
</script>
</body></html>"""


@app.route("/status/<int:oid>/<status>")
def update_status_route(oid, status):
    set_status(oid, status)
    return "ok"


if __name__ == "__main__":
    print(f"{RESTO} — lancement...")
    print("1. ngrok http 5000")
    print("2. coller l'url dans twilio webhook -> /whatsapp")
    print("3. dashboard: http://localhost:5000/dashboard")
    app.run(debug=True, port=5000)
