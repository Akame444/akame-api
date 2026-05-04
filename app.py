import os
import base64
import requests
import uvicorn
import statistics
from fastapi import FastAPI, Request

app = FastAPI()

# --- CONFIGURATION EBAY ---
# Récupérés depuis les variables d'environnement Render
EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")

@app.get("/")
@app.head("/")
async def root():
    return {
        "status": "Moteur eBay Market-Analysis Actif",
        "region": "FR",
        "version": "2.0 (Stable API)"
    }

def get_ebay_token():
    """Génère un token OAuth pour l'API eBay"""
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        return None
    
    auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
    credentials = f"{EBAY_APP_ID}:{EBAY_CERT_ID}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }

    try:
        response = requests.post(auth_url, headers=headers, data=data)
        return response.json().get("access_token")
    except Exception as e:
        print(f"Erreur Token : {e}")
        return None

def get_ebay_market_data(keyword, token):
    """Récupère les annonces et calcule les statistiques de marché"""
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"
    }
    
    # Nettoyage du mot-clé pour éviter les faux positifs (boosters vides, lots, etc.)
    safe_keyword = f"{keyword} -lot -booster -vide -empty"
    
    params = {
        "q": safe_keyword,
        "limit": 20, # On analyse les 20 meilleurs résultats
        "filter": "buyingOptions:{FIXED_PRICE},itemLocationCountry:{FR}",
        "sort": "price" 
    }

    try:
        response = requests.get(search_url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get("itemSummaries", [])
            
            if not items:
                return None

            prices = [float(item['price']['value']) for item in items]
            
            # --- CALCUL DES STATS ---
            avg_price = round(statistics.mean(prices), 2)
            median_price = round(statistics.median(prices), 2)
            
            # Simulation de tendance (comparaison des prix bas vs prix hauts du marché actuel)
            # Utile pour voir si le marché est "tendu" ou "calme"
            low_market = statistics.mean(prices[:5])
            high_market = statistics.mean(prices[-5:])
            spread_trend = round(((high_market - low_market) / low_market) * 100, 2)

            # --- LISTE DES ANNONCES ---
            listings = []
            for item in items[:5]: # On ne renvoie que les 5 meilleures pour l'affichage
                listings.append({
                    "title": item.get('title'),
                    "price": item.get('price', {}).get('value'),
                    "link": item.get('itemWebUrl'),
                    "image": item.get('thumbnailImages', [{}])[0].get('imageUrl', "")
                })

            return {
                "moyenne": avg_price,
                "mediane": median_price,
                "tendance_marche": f"{spread_trend}%",
                "derniere_ventes_estim": listings
            }
    except Exception as e:
        print(f"Erreur API eBay : {e}")
    return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    items = data.get("items", [])
    results = {}
    
    token = get_ebay_token()
    if not token:
        return {"error": "Impossible de se connecter à eBay"}

    for item in items:
        keyword = item.get("ebay_keyword")
        cm_url = item.get("cm_url") # On garde l'URL pour ton bouton admin
        
        market_stats = get_ebay_market_data(keyword, token)
        
        if market_stats:
            results[keyword] = {
                "stats": {
                    "prix_moyen": market_stats["moyenne"],
                    "prix_mediane": market_stats["mediane"],
                    "hausse_baisse": market_stats["tendance_marche"],
                },
                "annonces": market_stats["derniere_ventes_estim"],
                "admin_links": {
                    "cardmarket": cm_url,
                    "ebay_search": f"https://www.ebay.fr/sch/i.html?_nkw={keyword.replace(' ', '+')}"
                }
            }
        else:
            results[keyword] = {"error": "Aucune donnée trouvée"}
            
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
