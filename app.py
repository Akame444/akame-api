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

RAW_PROXY = "iproyaleu.boilingproxies.com:11002:Nh4BaPOY:QzmAQ3Ap-country-de"

def get_formatted_proxy(raw):
    try:
        parts = raw.split(':')
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)

@app.get("/")
async def root():
    return {"status": "En ligne", "mode": "Sécurité Maximale 🛡️"}

def get_price_free(url):
    if not PROXY_URL:
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    
    # --- GROSSE LISTE NOIRE (Blacklist) ---
    blacklist = [
        # État et défauts (FR)
        "abim", "abîm", "defaut", "défaut", "damage", "enfonc", "déchir", "trou", "pli", "griff", 
        "tache", "poussiere", "poussière", "griffe", "rayure", "rayé", "usé", "usure", "poc", 
        "impact", "corne", "blanchi", "frotté", "pliure", "scellé abimé", "boite abimée",
        # État et défauts (EN/DE)
        "poor", "played", "heavy", "lightly", "played", "lp", "gd", "good", "damaged", "skratched", 
        "whitening", "cloudy", "crease", "dent", "worn", "wear", "defect", "edge", "corner", 
        "stain", "dust", "nick", "scuff", "beschädigt", "knick", "kratzer", "flecken",
        # Logistique et divers
        "rmp", "main propre", "remise", "mains propres", "ebay", "vinted", "vendu", "photo", 
        "voir", "regarder", "check", "details", "détails", "info", "lire", "read", "description"
    ]

    for attempt in range(3):
        try:
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,de;q=0.7",
                "Referer": "https://www.google.de/",
            }
            
            print(f"🕵️ Analyse de la page : {url}")
            time.sleep(random.uniform(2, 4))
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            
            if response.status_code == 200:
                tree = html.fromstring(response.content)
                rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
                
                valid_prices = []
                
                for row in rows:
                    text_ligne = " ".join(row.xpath('.//text()')).lower()
                    
                    # On ignore si un mot de la liste est présent
                    if any(word in text_ligne for word in blacklist):
                        continue
                    
                    price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                    if price_element:
                        price = float(re.sub(r'[^\d.,]', '', price_element[0]).replace(',', '.'))
                        valid_prices.append(price)

                # --- LOGIQUE ANTI-ERREUR ---
                # Si on a trouvé des prix valides
                if valid_prices:
                    # Si on a plusieurs fois le même prix le moins cher (ex: 140e)
                    # Mais qu'on a peur que le premier soit quand même un truc louche
                    # On prend le prix s'il apparaît sur une ligne "sûre"
                    if len(valid_prices) > 1:
                        print(f"✅ Plusieurs options trouvées : {valid_prices[:3]}")
                        return valid_prices[0] # On renvoie le premier qui a passé tous les filtres
                    else:
                        return valid_prices[0]
                
                return None
            
        except Exception as e:
            print(f"⚠️ Erreur : {e}")
        time.sleep(5)
            
    return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    for link in links:
        results[link] = get_price_free(link)
        await asyncio.sleep(5)
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
