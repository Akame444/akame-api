import os
import re
import asyncio
import uvicorn
import requests
from fastapi import FastAPI, Request
from lxml import html

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "En ligne", "message": "API AkameTCG version ultra-rapide ! 🚀"}

def get_price_free(url):
    # On simule un vrai navigateur avec des Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        print(f"🕵️ Scan rapide : {url}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Erreur Cardmarket : {response.status_code}")
            return None
            
        tree = html.fromstring(response.content)
        
        # On cherche les lignes de prix
        rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
        blacklist = ["rmp", "main propre", "remise", "abim", "abîm", "damage", "enfonc", "déchir"]
        
        for row in rows:
            text_ligne = " ".join(row.xpath('.//text()')).lower()
            if not any(word in text_ligne for word in blacklist):
                price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                if price_element:
                    # Nettoyage du prix (ex: "15,00 €" -> 15.0)
                    price_str = price_element[0]
                    price = float(re.sub(r'[^\d.,]', '', price_str).replace(',', '.'))
                    print(f"💰 PRIX TROUVÉ : {price} €")
                    return price
        
        print("⚠️ Aucun prix valide trouvé sur cette page.")
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
        # Petit délai pour ne pas être banni par Cardmarket
        await asyncio.sleep(1)
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
