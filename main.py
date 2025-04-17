import requests
import json
import time
import os
from datetime import datetime
import logging
import re
from bs4 import BeautifulSoup
import pytz

# 🔄 Supprimer l'ancien log à chaque exécution
log_file = "bot_reservation.log"
if os.path.exists(log_file):
    os.remove(log_file)

# ⚙️ Logger propre
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def load_config():
    with open("config.json") as f:
        return json.load(f)

def get_check_interval(minutes_left):
    if minutes_left > 30:
        return 300  # 5 minutes
    elif minutes_left > 15:
        return 180  # 3 minutes
    elif minutes_left > 10:
        return 120  # 2 minutes
    elif minutes_left > 5:
        return 60   # 1 minute
    elif minutes_left > 2:
        return 15   # 15 secondes
    elif minutes_left > 1:
        return 2    # 2 secondes
    else:
        return 1    # chaque seconde

def extract_expiration_time(html):
    soup = BeautifulSoup(html, 'html.parser')
    alert_div = soup.find("div", class_="alert alert-warning fade in")
    if alert_div:
        match = re.search(r"valide jusqu'à\s*<strong>([^<]+)</strong>", str(alert_div))
        if match:
            date_str = match.group(1).strip()
            try:
                paris = pytz.timezone("Europe/Paris")
                expiration_naive = datetime.strptime(date_str, "%d/%m/%Y %H:%M:%S")
                expiration_dt = paris.localize(expiration_naive)
                now = datetime.now(paris)
                remaining = int((expiration_dt - now).total_seconds() / 60)
                return expiration_dt, remaining
            except ValueError:
                return None
    return None

def has_active_reservation(session):
    url = "https://www.mobility-parc.net/m/welcome.do"
    response = session.get(url, verify=False)
    if "réservation en cours" in response.text.lower():
        result = extract_expiration_time(response.text)
        if result:
            expiration, minutes_left = result
            logging.info(f"⏳ Réservation jusqu'à {expiration} ({minutes_left} min restantes).")
            return True, minutes_left
        else:
            logging.info("⏳ Réservation active, mais l'heure d'expiration n'a pas pu être extraite.")
            return True, None
    return False, None

def login(cfg):
    session = requests.Session()
    login_url = "https://www.mobility-parc.net/j_spring_security_check"
    payload = {
        "j_username": cfg["username"],
        "j_password": cfg["password"],
        "Submit": "",
        "loginStr": cfg["username"],
        "captchaInvisibleType": "true",
        "loginFieldPhone": "false",
        "myDataStr": "",
        "device_id": "",
        "run_id": "",
        "oneAppVersion": "",
        "oneAppExtLinkSupport": ""
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.mobility-parc.net/loginForm.do?communityId=254&lfe=fc3"
    }

    response = session.post(login_url, data=payload, headers=headers, allow_redirects=True, verify=False)

    if "welcome.do" in response.url:
        logging.info("🔓 Connexion réussie.")
        return session
    else:
        logging.error("❌ Connexion échouée.")
        logging.debug(response.text[:300])
        return None

def build_params(cfg):
    now = int(time.time() * 1000)
    return {
        "communityId": cfg["community_id"],
        "cmd": "book",
        "stationId": cfg["station_id"],
        "terminalId": cfg["terminal_id"],
        "locationId": "",
        "userGPSCoord": cfg["gps_coord"],
        "userGPSCoordTime": f"{now};{now - 3000};-1"
    }

def book_bike(cfg, session):
    logging.info("📤 Tentative de réservation...")

    headers = {
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0",
        "referer": "https://www.mobility-parc.net/m/welcome.do"
    }

    response = session.get(
        "https://www.mobility-parc.net/m/welcomeLoggedBGUpdate.do",
        headers=headers,
        params=build_params(cfg),
        verify=False
    )

    if "réservation" in response.text.lower():
        logging.info("✔️ Réservation effectuée ou déjà active.")
    else:
        logging.warning("❌ Échec de la réservation.")
        logging.debug(response.text[:300])

def start_loop():
    cfg = load_config()
    while True:
        session = login(cfg)
        if not session:
            time.sleep(60)
            continue

        active, minutes_left = has_active_reservation(session)

        if not active:
            book_bike(cfg, session)
            interval = 1
        else:
            if minutes_left is not None:
                interval = get_check_interval(minutes_left)
                logging.info(f"⏲️ Prochaine vérification dans {interval} secondes.")
            else:
                interval = 60  # valeur par défaut si on ne peut pas extraire l'heure

        time.sleep(interval)

if __name__ == "__main__":
    start_loop()
