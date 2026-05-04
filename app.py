import os
import base64
import requests
import uvicorn
import statistics
from datetime import datetime, timedelta
from fastapi import FastAPI, Request

app = FastAPI()

# --- CONFIGURATION EBAY ---
EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")

@app.get("/")
@app.head("/")
async def root():
    return {"status": "API eBay Officielle Active", "mode": "Sold Items / Market Insights"}

def get_ebay_token():
    """Génère le token OAuth officiel"""
    auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        return None
    
    credentials = f"{EBAY_APP_ID}:{EBAY_CERT_ID}"
    encoded_creds = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_creds}"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }

    try:
        r = requests.post(auth_url, headers=headers, data=data)
        return r.json().get("access_token")
    except:
        return None

def get_ebay_analytics(keyword, token):
    """Analyse les ventes réelles sur les 30 derniers jours"""
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"
    }

    # Calcul des dates pour le filtre (30 derniers jours)
    today = datetime.utcnow()
    one_month_ago = today - timedelta(days=30)
    date_filter = f"lastSoldDate:[{one_month_ago.strftime('%Y-%m-%dT%H:%M:%S.000Z')}..{today.strftime('%Y-%m-%dT%H:%M:%S.000Z')}]"

    # Filtre strict : Neuf, Vendu en France, Dernier mois
    params = {
        "q": f"{keyword} -lot -vide",
        "limit": 50,
        "filter": f"conditions:{{NEW}},{date_filter},itemLocationCountry:{{FR}}",
        "sort": "newlyListed"
    }

    try:
        r = requests.get(search_url, headers=headers, params=params)
        if r.status_code != 200:
            return {"error": f"API Error {r.status_code}"}

        items = r.json().get("itemSummaries", [])
        if not items:
            return {"error": "Aucune vente trouvée sur 30j"}

        prices = [float(i['price']['value']) for i in items]
        
        # --- CALCULS STATISTIQUES ---
        avg_price = round(statistics.mean(prices), 2)
        median_price = round(statistics.median(prices), 2)

        # Calcul de tendance : Comparaison 10 derniers vs 10 premiers (du mois)
        if len(prices) >= 10:
            recent_avg = statistics.mean(prices[:5])
            older_avg = statistics.mean(prices[-5:])
            trend = round(((recent_avg - older_avg) / older_avg) * 100, 2)
        else:
            trend = 0

        # Annonces pour l'affichage (les 3 plus récentes)
        listings = []
        for i in items[:3]:
            listings.append({
                "t": i.get('title'),
                "p": i.get('price', {}).get('value'),
                "l": i.get('itemWebUrl')
            })

        return {
            "moyenne": avg_price,
            "mediane": median_price,
            "hausse_30j": f"{trend}%",
            "ventes_count": len(prices),
            "exemples": listings
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    items = data.get("items", [])
    results = {}
    
    token = get_ebay_token()
    if not token:
        return {"error": "Problème de credentials eBay"}

    for item in items:
        keyword = item.get("ebay_keyword")
        analysis = get_ebay_analytics(keyword, token)
        
        if "error" not in analysis:
            results[keyword] = {
                "stats": {
                    "prix_moyen": analysis["mediane"], # On utilise la médiane (plus fiable)
                    "moyenne_brute": analysis["moyenne"],
                    "evolution": analysis["hausse_30j"],
                    "volume": analysis["ventes_count"]
                },
                "annonces": analysis["exemples"]
            }
        else:
            results[keyword] = {"error": analysis["error"]}
            
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
