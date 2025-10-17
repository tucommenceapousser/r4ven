import os
import re
import sys
import json
import requests

CONFIG_FILE = "telegram_config.json"

if sys.stdout.isatty():
    R = '\033[31m'  # Red
    G = '\033[32m'  # Green
    C = '\033[36m'  # Cyan
    W = '\033[0m'   # Reset
    Y = '\033[33m'  # Yellow
    M = '\033[35m'  # Magenta
    B = '\033[34m'  # Blue
else:
    R = G = C = W = Y = M = B = ''

# ─────────────────────────────
# Utils
# ─────────────────────────────

def get_file_data(file_path):
    """Lit le contenu d'un fichier."""
    with open(file_path, 'r') as open_file:
        return open_file.read()


# ─────────────────────────────
# Telegram
# ─────────────────────────────

def send_telegram_message(token, chat_id, text):
    """Envoie un message texte à Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"{R}[!] Telegram Error: {r.text}{W}")
    except Exception as e:
        print(f"{R}[!] Failed to send Telegram message: {e}{W}")


def send_telegram_photo(token, chat_id, photo_path, caption=None):
    """Envoie une image à Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption or '', 'parse_mode': 'HTML'}
            r = requests.post(url, files=files, data=data, timeout=10)
            if r.status_code != 200:
                print(f"{R}[!] Telegram Photo Error: {r.text}{W}")
    except Exception as e:
        print(f"{R}[!] Failed to send photo to Telegram: {e}{W}")


# ─────────────────────────────
# Compatibilité avec le script principal
# ─────────────────────────────

def update_webhook(webhook, webhook_data: dict):
    """
    Remplace l'ancien envoi Discord par Telegram.
    `webhook` ici contient en réalité le token + chat_id.
    """
    if not webhook or not isinstance(webhook, dict):
        print(f"{R}[!] Invalid Telegram config.{W}")
        return

    token = webhook.get("token")
    chat_id = webhook.get("chat_id")

    text = json.dumps(webhook_data, indent=2)
    send_telegram_message(token, chat_id, f"<b>📡 New Data Received:</b>\n<pre>{text}</pre>")


def check_and_get_webhook_url(folder_name):
    """
    Vérifie/configure le bot Telegram et renvoie un dict {token, chat_id}.
    """
    config_path = os.path.join(folder_name, CONFIG_FILE)

    def ask_for_config():
        print(f"\n{B}[+] {C}Enter your Telegram bot token:{W}")
        token = input("> ").strip()
        print(f"\n{B}[+] {C}Enter your Telegram chat ID (or channel ID):{W}")
        chat_id = input("> ").strip()

        config = {"token": token, "chat_id": chat_id}
        with open(config_path, 'w') as f:
            json.dump(config, f)
        print(f"{G}[✓] Telegram configuration saved to {config_path}{W}")
        return config

    if not os.path.exists(config_path):
        return ask_for_config()
    else:
        with open(config_path, 'r') as f:
            try:
                config = json.load(f)
                if "token" in config and "chat_id" in config:
                    print(f"{G}[✓] Telegram config loaded successfully.{W}")
                    return config
                else:
                    print(f"{R}[!] Invalid config file format.{W}")
                    return ask_for_config()
            except Exception:
                print(f"{R}[!] Error reading Telegram config file.{W}")
                return ask_for_config()
