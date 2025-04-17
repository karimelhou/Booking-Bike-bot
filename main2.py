import streamlit as st
import requests
import json
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
import re

# Charger la config
def load_config():
    with open("config.json") as f:
        return json.load(f)

# Login
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
        return session
    else:
        return None

# Vérifier réservation active
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
                return expiration_dt.strftime('%Y-%m-%d %H:%M:%S'), remaining
            except ValueError:
                return None, None
    return None, None

def has_active_reservation(session):
    url = "https://www.mobility-parc.net/m/welcome.do"
    response = session.get(url, verify=False)
    if "réservation en cours" in response.text.lower():
        return extract_expiration_time(response.text)
    return None, None

# Réserver
def book_bike(cfg, session):
    headers = {
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0",
        "referer": "https://www.mobility-parc.net/m/welcome.do"
    }
    now = int(datetime.now().timestamp() * 1000)
    params = {
        "communityId": cfg["community_id"],
        "cmd": "book",
        "stationId": cfg["station_id"],
        "terminalId": cfg["terminal_id"],
        "locationId": "",
        "userGPSCoord": cfg["gps_coord"],
        "userGPSCoordTime": f"{now};{now - 3000};-1"
    }
    response = session.get("https://www.mobility-parc.net/m/welcomeLoggedBGUpdate.do", headers=headers, params=params, verify=False)
    return "réservation" in response.text.lower()

# Interface Streamlit
st.title("🚲 Mobility Parc - Réservation Bot")

cfg = load_config()

if st.button("🔑 Connexion et Vérifier réservation"):
    session = login(cfg)
    if session:
        exp, mins = has_active_reservation(session)
        if exp:
            st.success(f"✅ Réservation en cours jusqu'à {exp} ({mins} min restantes)")
        else:
            st.info("🚫 Aucune réservation active.")
    else:
        st.error("❌ Connexion échouée")

if st.button("📌 Réserver maintenant"):
    session = login(cfg)
    if session:
        if book_bike(cfg, session):
            st.success("✔️ Réservation effectuée !")
        else:
            st.warning("❌ Réservation échouée ou déjà prise.")
    else:
        st.error("❌ Connexion échouée")
