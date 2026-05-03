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
    return {"status": "En ligne", "mode": "Filtres personnalisés 🚀"}

def get_price_free(url):
    if not PROXY_URL:
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    
    # --- FILTRES ÉCHANGÉS ---
    blacklist = ["rmp", "main propre", "remise", "abim", "abîm", "damage", "enfonc", "déchir"]

    for attempt in range(3):
        try:
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,de;q=0.7",
                "Referer": "https://www.google.de/",
            }
            
            print(f"🕵️ Analyse (Essai {attempt+1}) : {url}")
            time.sleep(random.uniform(1.5, 3))
            response = requests.get(url, headers=headers, proxies=proxies, timeout=25)
            
            if response.status_code == 200:
                tree = html.fromstring(response.content)
                rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
                
                for row in rows:
                    text_ligne = " ".join(row.xpath('.//text()')).lower()
                    
                    if any(word in text_ligne for word in blacklist):
                        continue
                    
                    price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                    if price_element:
                        price = float(re.sub(r'[^\d.,]', '', price_element[0]).replace(',', '.'))
                        print(f"💰 PRIX TROUVÉ : {price} €")
                        return price
                
                print("⚠️ Aucun vendeur valide trouvé sur cette tentative.")
            
        except Exception as e:
            print(f"⚠️ Erreur : {e}")
        time.sleep(4)
            
    return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    for link in links:
        results[link] = get_price_free(link)
        await asyncio.sleep(4) 
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
