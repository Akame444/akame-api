import os
import base64
import requests
import uvicorn
import statistics
import re
from datetime import datetime, timedelta
from fastapi import FastAPI, Request

app = FastAPI()

EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")

@app.get("/")
@app.head("/")
async def root():
    return {"status": "API eBay Master (Anti-Lots)", "mode": "Calcul de précision"}

def get_ebay_token():
    auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
    if not EBAY_APP_ID or not EBAY_CERT_ID: return None
    credentials = f"{EBAY_APP_ID}:{EBAY_CERT_ID}"
    encoded_creds = base64.b64encode(credentials.encode()).decode()
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {encoded_creds}"}
    data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
    try:
        r = requests.post(auth_url, headers=headers, data=data)
        return r.json().get("access_token")
    except: return None

def is_garbage_lot(title, price):
    """Détecte si c'est un lot d'articles ou un accessoire en fonction du titre et du prix"""
    t = title.lower()
    # Mots-clés indiquant une quantité multiple
    lot_keywords = ["x2", "x3", "x4", "x5", "x6", "x10", "lot de", "set of", "case", "scellé x", "pack de"]
    if any(k in t for k in lot_keywords):
        return True
    return False

def get_ebay_analytics(keyword, token):
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}

    today = datetime.utcnow()
    one_month_ago = today - timedelta(days=30)
    date_filter = f"lastSoldDate:[{one_month_ago.strftime('%Y-%m-%dT%H:%M:%S.000Z')}..{today.strftime('%Y-%m-%dT%H:%M:%S.000Z')}]"

    # On demande 100 résultats pour avoir de la matière à filtrer
    params = {
        "q": f"{keyword} -lot -vide -case -display",
        "limit": 100,
        "filter": f"conditions:{{NEW}},{date_filter},itemLocationCountry:{{FR}}",
        "sort": "newlyListed"
    }

    try:
        r = requests.get(search_url, headers=headers, params=params)
        items = r.json().get("itemSummaries", [])
        if not items: return {"error": "Rien trouvé"}

        clean_prices = []
        valid_listings = []

        for i in items:
            title = i.get('title', '')
            price = float(i['price']['value'])
            
            # 1. On vire les lots évidents au titre
            if is_garbage_lot(title, price):
                continue
                
            clean_prices.append(price)
            valid_listings.append({"t": title, "p": price, "l": i.get('itemWebUrl')})

        if len(clean_prices) < 3:
            return {"error": "Pas assez de données valides"}

        # 2. FILTRE STATISTIQUE : On ignore les extrêmes (Outliers)
        # On trie et on enlève les 15% les plus bas et les 15% les plus hauts
        clean_prices.sort()
        cut = int(len(clean_prices) * 0.15)
        filtered_prices = clean_prices[cut:-cut] if len(clean_prices) > 6 else clean_prices

        # 3. CALCULS FINAUX
        avg_price = round(statistics.mean(filtered_prices), 2)
        median_price = round(statistics.median(filtered_prices), 2)

        # Tendance
        recent_avg = statistics.mean(filtered_prices[:3]) if len(filtered_prices) >= 3 else filtered_prices[0]
        older_avg = statistics.mean(filtered_prices[-3:]) if len(filtered_prices) >= 3 else filtered_prices[-1]
        trend = round(((recent_avg - older_avg) / older_avg) * 100, 2)

        return {
            "moyenne": median_price, # On utilise la médiane car c'est la plus juste
            "hausse_30j": f"{trend}%",
            "volume": len(filtered_prices),
            "exemples": valid_listings[:3]
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    items = data.get("items", [])
    results = {}
    token = get_ebay_token()
    
    if not token: return {"error": "Token Error"}

    for item in items:
        kw = item.get("ebay_keyword")
        analysis = get_ebay_analytics(kw, token)
        
        if "error" not in analysis:
            results[kw] = {
                "stats": {
                    "prix_moyen": analysis["moyenne"],
                    "evolution": analysis["hausse_30j"],
                    "volume": analysis["volume"]
                },
                "annonces": analysis["exemples"]
            }
        else:
            results[kw] = {"error": analysis["error"]}
            
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
