import os
import re
import asyncio
import uvicorn
import requests
import time
import random
from fastapi import FastAPI, Request
from lxml import html

app = FastAPI()

# --- CONFIGURATION FINALE ---
# Utilisation du pool Allemagne (DE) pour une discrétion maximale
RAW_PROXY = "iproyaleu.boilingproxies.com:11002:Nh4BaPOY:QzmAQ3Ap-country-de"

def get_formatted_proxy(raw):
    try:
        parts = raw.split(':')
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)
# ----------------------------

@app.get("/")
async def root():
    return {"status": "En ligne", "region": "Allemagne (DE)", "filtres": "Actifs ✅"}

def get_price_free(url):
    if not PROXY_URL:
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    # Rotation d'identités pour simuler différents navigateurs
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ]
    
    # Liste noire étendue pour ne prendre que du "Propre"
    blacklist = [
        "rmp", "main propre", "remise", "abim", "abîm", "damage", "enfonc", 
        "déchir", "trou", "defect", "poor", "played", "heavy", "lightly", 
        "pli", "scratch", "griff", "poussiere", "poussière", "tache", "task",
        "worn", "whitening", "cloudy", "crease", "dent", "scratched"
    ]
    
    for attempt in range(3):
        try:
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,de;q=0.7",
                "Referer": "https://www.google.de/",
                "DNT": "1"
            }
            
            print(f"🕵️ Scan (Essai {attempt+1}) : {url}")
            
            # Délai aléatoire pour simuler un humain qui réfléchit
            time.sleep(random.uniform(2, 4))
            
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            
            if response.status_code == 200:
                tree = html.fromstring(response.content)
                # On cible les lignes de vendeurs
                rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
                
                for row in rows:
                    # On scanne tout le texte de la ligne (commentaires + état de la carte)
                    text_ligne = " ".join(row.xpath('.//text()')).lower()
                    
                    # Vérification de la blacklist
                    if any(word in text_ligne for word in blacklist):
                        continue # On ignore cette ligne si un défaut est mentionné
                    
                    # Extraction du prix
                    price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                    if price_element:
                        price_raw = price_element[0]
                        # Nettoyage pour transformer "170,00 €" en 170.0
                        price = float(re.sub(r'[^\d.,]', '', price_raw).replace(',', '.'))
                        print(f"💰 PRIX TROUVÉ : {price} €")
                        return price
                
                print("⚠️ Page lue mais tous les vendeurs sont filtrés (abîmés/défauts).")
                return None
            
            print(f"❌ Erreur HTTP {response.status_code} sur l'essai {attempt+1}")
                
        except Exception as e:
            print(f"⚠️ Échec technique essai {attempt+1} : {e}")
        
        # Pause avant le prochain essai (nouvelle IP via Rotating Proxy)
        time.sleep(5)
            
    return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    
    for link in links:
        results[link] = get_price_free(link)
        # PAUSE CRUCIALE : on attend 5 secondes entre chaque carte pour rester discret
        await asyncio.sleep(5)
        
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
