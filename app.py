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

# --- CONFIGURATION (ALLEMAGNE) ---
RAW_PROXY = "iproyaleu.boilingproxies.com:11002:Nh4BaPOY:QzmAQ3Ap-country-de"

def get_formatted_proxy(raw):
    try:
        parts = raw.split(':')
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)
# ---------------------------------

@app.get("/")
async def root():
    return {"status": "En ligne", "region": "Allemagne (DE) ✅"}

def get_price_free(url):
    if not PROXY_URL:
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    # On varie les identités pour ne pas se faire repérer
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    
    for attempt in range(3):
        try:
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,de;q=0.7", # On ajoute un peu de 'de' pour la cohérence
                "Referer": "https://www.google.de/",
                "DNT": "1"
            }
            
            print(f"🕵️ Tentative {attempt+1} (Proxy DE) : {url}")
            
            # Délai aléatoire avant la requête
            time.sleep(random.uniform(2, 5))
            
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            
            if response.status_code == 200:
                tree = html.fromstring(response.content)
                rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
                
                # --- FILTRES MIS À JOUR ---
                blacklist = ["rmp", "main propre", "remise", "abim", "abîm", "damage", "enfonc", "déchir"]
                
                for row in rows:
                    text_ligne = " ".join(row.xpath('.//text()')).lower()
                    if not any(word in text_ligne for word in blacklist):
                        price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                        if price_element:
                            price = float(re.sub(r'[^\d.,]', '', price_element[0]).replace(',', '.'))
                            print(f"💰 VICTOIRE : {price} €")
                            return price
                return None
            
            print(f"❌ Blocage (HTTP {response.status_code})")
                
        except Exception as e:
            print(f"⚠️ Erreur : {e}")
        
        # Si ça rate, on attend 6 secondes pour laisser le pool de proxy tourner
        time.sleep(6)
            
    return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    for link in links:
        results[link] = get_price_free(link)
        # On est TRÈS prudent : 6 secondes entre chaque carte
        await asyncio.sleep(6)
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
