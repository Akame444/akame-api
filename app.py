import os
import re
import asyncio
import uvicorn
import requests
from fastapi import FastAPI, Request
from lxml import html

app = FastAPI()

# --- TA CONFIGURATION PROXY ---
# Ta ligne IPRoyal formatée pour Python
RAW_PROXY = "iproyalsockseu.boilingproxies.com:11005:Nh4BaPOY:QzmAQ3Ap-country-fr_session-4dv1luoq_lifetime-1h_device-ios"

def get_formatted_proxy(raw):
    try:
        # On découpe l'adresse : ip, port, user, pass
        parts = raw.split(':')
        host = parts[0]
        port = parts[1]
        user = parts[2]
        password = parts[3]
        return f"socks5h://{user}:{password}@{host}:{port}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)
# ------------------------------

@app.get("/")
async def root():
    return {"status": "En ligne", "info": "Proxy IPRoyal (France/iOS) configuré ✅"}

def get_price_free(url):
    if not PROXY_URL:
        print("❌ Erreur de formatage du proxy.")
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    # User-Agent iPhone pour matcher avec ton réglage "iOS" de Boiling
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    }
    
    try:
        print(f"🕵️ Scan via iPhone Proxy : {url}")
        # On passe par ton proxy résidentiel
        response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
        
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
        print(f"❌ Erreur technique : {e}")
        return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    for link in links:
        results[link] = get_price_free(link)
        # On attend 1s entre les cartes pour être discret
        await asyncio.sleep(1)
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
