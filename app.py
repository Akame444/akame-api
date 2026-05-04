import os
import re
import uvicorn
import statistics
import random
import time
from fastapi import FastAPI, Request
from lxml import html
from curl_cffi import requests as curl_requests

app = FastAPI()

@app.get("/")
@app.head("/")
async def root():
    return {"status": "Analyseur de Ventes Réussies eBay", "mode": "Sold Items Only"}

def get_sold_prices_ebay(keyword):
    """Scrape les ventes terminées et réussies sur eBay FR"""
    # Nettoyage des mots-clés
    banned = "-lot -vide -empty -code -online -tcgl -sleeves -pochette -energy -energie"
    query = f"{keyword} {banned}".replace(" ", "+")
    
    # URL magique : LH_Sold=1 (Vendu) + LH_Complete=1 (Terminé) + LH_ItemCondition=3 (Neuf)
    url = f"https://www.ebay.fr/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1&LH_ItemCondition=3&_ipg=60"

    try:
        # On imite un vrai navigateur Chrome pour ne pas être bloqué
        response = curl_requests.get(url, impersonate="chrome110", timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erreur eBay : {response.status_code}")
            return None

        tree = html.fromstring(response.content)
        
        # On cherche les blocs d'annonces vendues
        items = tree.xpath('//div[contains(@class, "s-item__info")]')
        
        valid_prices = []
        listings_data = []

        for item in items:
            # Extraction du titre
            title_el = item.xpath('.//div[@class="s-item__title"]//span[@role="heading"]/text()')
            if not title_el: continue
            title = title_el[0].lower()

            # On vérifie encore une fois qu'on ne prend pas de l'occasion ou des accessoires
            if any(x in title for x in ["occasion", "used", "abîmé", "damaged", "vide", "empty", "boite seule"]):
                continue

            # Extraction du prix (il peut y avoir "vendu pour" ou des dates, on nettoie)
            price_el = item.xpath('.//span[@class="s-item__price"]//text()')
            if price_el:
                # Nettoyage du prix : on garde que les chiffres et la virgule
                raw_price = "".join(re.findall(r'[0-9.,]', price_el[0])).replace(',', '.')
                try:
                    price = float(raw_price)
                    
                    # --- SÉCURITÉ ANTI-POLLUANTS ---
                    # Si c'est une ETB ou une UPC, on ignore les ventes < 50€ (boosters, etc.)
                    if "etb" in keyword.lower() or "upc" in keyword.lower() or "coffret" in keyword.lower():
                        if price < 50: continue
                    
                    valid_prices.append(price)
                    
                    # On garde les 5 premiers pour l'affichage
                    if len(listings_data) < 5:
                        listings_data.append({
                            "title": title_el[0],
                            "price": price,
                            "date": "Vendu"
                        })
                except:
                    continue

        if not valid_prices:
            return None

        # --- CALCULS STATISTIQUES ---
        # Médiane : beaucoup plus précis pour le TCG car ignore les ventes aberrantes
        median_sold = round(statistics.median(valid_prices), 2)
        avg_sold = round(statistics.mean(valid_prices), 2)
        
        return {
            "prix_moyen_vendu": median_sold,
            "nb_ventes_analysees": len(valid_prices),
            "annonces": listings_data
        }

    except Exception as e:
        print(f"⚠️ Erreur Scraping Sold : {e}")
        return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    items = data.get("items", [])
    results = {}

    for item in items:
        keyword = item.get("ebay_keyword")
        
        # On lance l'analyse des ventes réussies
        market_data = get_sold_prices_ebay(keyword)
        
        if market_data:
            results[keyword] = {
                "stats": {
                    "prix_moyen": market_data["prix_moyen_vendu"], # On renvoie la médiane ici
                    "nb_ventes": market_data["nb_ventes_analysees"]
                },
                "annonces": market_data["annonces"]
            }
        else:
            results[keyword] = {"error": "Aucune vente réussie trouvée"}
            
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
