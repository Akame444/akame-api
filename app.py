import os
import base64
import requests
import uvicorn
import statistics
import numpy as np # Pour les calculs de quartiles
from datetime import datetime, timedelta
from fastapi import FastAPI, Request

app = FastAPI()

EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")

@app.get("/")
@app.head("/")
async def root():
    return {"status": "API eBay Ultra-Précision", "mode": "Filtre IQR Anti-Lots"}

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

def clean_outliers_iqr(prices):
    """Supprime mathématiquement les prix trop hauts (lots) et trop bas (accessoires)"""
    if len(prices) < 4: return prices
    
    # On trie les prix
    data = sorted(prices)
    q1 = np.percentile(data, 25) # 25% des prix les plus bas
    q3 = np.percentile(data, 75) # 75% des prix les plus hauts
    iqr = q3 - q1
    
    # On définit les bornes (1.5 est le standard, on peut baisser à 1.2 pour être plus strict)
    lower_bound = q1 - (1.2 * iqr)
    upper_bound = q3 + (1.2 * iqr)
    
    # On ne garde que ce qui est dans la fourchette normale
    return [p for p in data if p >= lower_bound and p <= upper_bound]

def get_ebay_analytics(keyword, token):
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}

    today = datetime.utcnow()
    one_month_ago = today - timedelta(days=30)
    date_filter = f"lastSoldDate:[{one_month_ago.strftime('%Y-%m-%dT%H:%M:%S.000Z')}..{today.strftime('%Y-%m-%dT%H:%M:%S.000Z')}]"

    # On durcit les mots-clés d'exclusion
    excluded = "-lot -vide -case -display -bundle -pack -bundle -set -x2 -x3 -x4 -x10"
    
    params = {
        "q": f"{keyword} {excluded}",
        "limit": 50,
        "filter": f"conditions:{{NEW}},{date_filter},itemLocationCountry:{{FR}}",
        "sort": "price" 
    }

    try:
        r = requests.get(search_url, headers=headers, params=params)
        items = r.json().get("itemSummaries", [])
        if not items: return {"error": "Aucune vente trouvée"}

        raw_prices = [float(i['price']['value']) for i in items]
        
        # --- ÉTAPE 1 : Nettoyage Statistique (IQR) ---
        filtered_prices = clean_outliers_iqr(raw_prices)

        if not filtered_prices: return {"error": "Données trop instables"}

        # --- ÉTAPE 2 : Calculs ---
        # On utilise la Médiane sur les données filtrées pour une précision chirurgicale
        market_price = round(statistics.median(filtered_prices), 2)
        
        # Calcul de tendance sur les 5 dernières ventes
        recent = statistics.mean(filtered_prices[:5]) if len(filtered_prices) >= 5 else filtered_prices[0]
        older = statistics.mean(filtered_prices[-5:]) if len(filtered_prices) >= 5 else filtered_prices[-1]
        trend = round(((recent - older) / older) * 100, 2)

        return {
            "moyenne": market_price,
            "hausse_30j": f"{trend}%",
            "volume": len(filtered_prices),
            "exemples": [{"t": i.get('title'), "p": i['price']['value']} for i in items[:3]]
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
                }
            }
        else:
            results[kw] = {"error": analysis["error"]}
            
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
