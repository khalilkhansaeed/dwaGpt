from flask import Flask, request
import requests
import os
import base64
from openai import OpenAI
import datetime

# ==== Setup ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("❌ OPENAI_API_KEY is missing from environment!")
else:
    print("✅ OPENAI_API_KEY loaded successfully.")
print("🔑 OpenAI Key Loaded:", bool(openai.api_key))
client = OpenAI(api_key=OPENAI_API_KEY)

    
ACCESS_TOKEN = "EAAJYudkKwPIBOxCvbAZBIgQTudwZBfzlkyCVT5KeXw80IfJRZAum7csuZAdZCYmb018CcQnO7jxnSQfh2Sl5AnJPDzMPmcilCkq1H6S8aZCBekR7QTeCr3vXZB12OCNF5TLWKq6qJopENXZAOnVz4xd0t1VzS1RBxqm3jQbzQjVlsXCfcIG1GEfWbZBpt5QEtwZBDOJgUK2t35PAZDZD"
PHONE_NUMBER_ID = "700453763142801"
VERIFY_TOKEN = "dwaGPTtoken2025"

user_histories = {}

# ==== Logging ====

def log_message(user_id, message, response):
    with open("chat_logs.txt", "a", encoding="utf-8") as f:
        f.write(f"\n--- {datetime.datetime.now()} ---\n")
        f.write(f"User ID: {user_id}\n")
        f.write(f"Message: {message}\n")
        f.write(f"Response: {response}\n")

# ==== ChatGPT ====

def ask_chatgpt_with_context(user_id, new_message):
    history = user_histories.get(user_id, [])

    system_prompt = {
        "role": "system",
        "content": (
            "You are a smart, kind medical assistant replying on WhatsApp. "
            "Always reply in a short, clear, friendly way. Use bold to highlight key info. "
            "Use line breaks (\\n\\n) to make answers easy to read. Reply like a human, not a robot. "
            "Add 1 or 2 emoji if it helps, and never overexplain unless asked."
        )
    }

    context = [system_prompt] + history[-5:]
    context.append({"role": "user", "content": new_message})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=context,
        max_tokens=150,
        temperature=0.8,
    )

    answer = response['choices'][0]['message']['content'].strip()
    history.append({"role": "user", "content": new_message})
    history.append({"role": "assistant", "content": answer})
    user_histories[user_id] = history

    log_message(user_id, new_message, answer)
    return answer

# ==== Medicine DB ====

medicine_db = {
    "panadol": {
        "name": "Panadol",
        "formula": "Paracetamol 500mg",
        "price": "Rs. 30",
        "store": "Wadan Pharmacy, Kabul"
    },
    "ibuprofen": {
        "name": "Ibuprofen",
        "formula": "Ibuprofen 200mg",
        "price": "Rs. 50",
        "store": "Sehat Drug Store, Peshawar"
    },
    # Add more...
}

def lookup_medicine_info(text):
    text = text.lower()
    for med_key in medicine_db:
        if med_key in text:
            return medicine_db[med_key]
    return None

# ==== WhatsApp Handlers ====

def send_message(to, message):
    url = f"https://graph.facebook.com/v15.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    print(f"Sending message to {to}: {message}")
    print("Response status:", response.status_code)
    print("Response body:", response.text)
    return response

# ==== Flask App ====

app = Flask(__name__)

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Incoming message:", data)

    try:
        changes = data['entry'][0]['changes'][0]['value']

        if 'messages' not in changes:
            print("No message content found.")
            return "ok", 200

        msg = changes['messages'][0]
        sender = msg['from']
        user_message_or_ocr_text = ""

        if msg.get("type") == "text":
            user_message_or_ocr_text = msg['text']['body']

        elif msg.get("type") == "image":
            media_id = msg['image']['id']
            image_bytes = download_image(media_id)
            user_message_or_ocr_text = extract_text_from_image_bytes(image_bytes)

        med_info = lookup_medicine_info(user_message_or_ocr_text)

        if med_info:
            reply = (
                f"💊 *{med_info['name']}*\n"
                f"🧪 Formula: {med_info['formula']}\n"
                f"💰 Price: {med_info['price']}\n"
                f"🏪 Store: {med_info['store']}\n\n"
                f"Ask if you want pros, cons, or alternatives 😊"
            )
        else:
            reply = ask_chatgpt_with_context(sender, user_message_or_ocr_text)

        send_message(sender, reply)

    except Exception as e:
        print("Error:", e)

    return "ok", 200

# ==== OCR Functions ====

def get_image_url(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.json()['url']

def download_image(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    res = requests.get(url, headers=headers).json()
    image_url = res['url']
    image_response = requests.get(image_url, headers=headers)
    return image_response.content

def extract_text_from_image_bytes(image_bytes):
    api_key = "K85664849288957"
    base64_img = base64.b64encode(image_bytes).decode()

    payload = {
        'base64Image': f'data:image/jpeg;base64,{base64_img}',
        'apikey': api_key,
        'language': 'eng',
        'OCREngine': 2
    }

    response = requests.post("https://api.ocr.space/parse/image", data=payload)
    print("OCR API response:", response.json())

    try:
        return response.json()['ParsedResults'][0]['ParsedText'].strip()
    except:
        return "OCR failed or no text found."

# ==== Run ====

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

