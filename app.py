import os
import re
import asyncio
import uvicorn
import requests
from fastapi import FastAPI, Request
from lxml import html

app = FastAPI()

# --- TA CONFIGURATION PROXY HTTP ---
# Nouvelle ligne Boiling (HTTP)
RAW_PROXY = "iproyaleu.boilingproxies.com:11002:Nh4BaPOY:QzmAQ3Ap-country-fr_session-ttd3pqhy_lifetime-1h_device-ios"

def get_formatted_proxy(raw):
    try:
        parts = raw.split(':')
        # Format HTTP : http://user:pass@host:port
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)
# ------------------------------

@app.get("/")
async def root():
    return {"status": "En ligne", "mode": "HTTP Proxy Résidentiel ✅"}

def get_price_free(url):
    if not PROXY_URL:
        return None

    # Pour le HTTP, on utilise le même URL pour http et https
    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9"
    }
    
    try:
        print(f"🕵️ Scan (HTTP Proxy) : {url}")
        # On désactive la vérification SSL si jamais le proxy fait des siennes (verify=False)
        response = requests.get(url, headers=headers, proxies=proxies, timeout=25)
        
        if response.status_code != 200:
            print(f"❌ Erreur Cardmarket : {response.status_code}")
            return None
            
        tree = html.fromstring(response.content)
        rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
        blacklist = ["rmp", "main propre", "remise", "abim", "abîm", "damage", "enfonc", "déchir"]
        
        for row in rows:
            text_ligne = " ".join(row.xpath('.//text()')).lower()
            if not any(word in text_ligne for word in blacklist):
                price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                if price_element:
                    price = float(re.sub(r'[^\d.,]', '', price_element[0]).replace(',', '.'))
                    print(f"💰 PRIX TROUVÉ : {price} €")
                    return price
        return None
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    for link in links:
        results[link] = get_price_free(link)
        await asyncio.sleep(1.5) # Petit délai pour la sécurité
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
