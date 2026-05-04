import os
import base64
import requests
import uvicorn
import statistics
from fastapi import FastAPI, Request

# --- LA LIGNE QUE RENDER CHERCHE (NE PAS SUPPRIMER) ---
app = FastAPI()

# --- CONFIGURATION EBAY ---
EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")

@app.get("/")
@app.head("/")
async def root():
    return {
        "status": "Moteur eBay Actif",
        "region": "Europe Pool",
        "condition": "Strict NEW only"
    }

def get_ebay_market_data(keyword, token):
    """Récupère uniquement les annonces NEUVES et calcule les stats"""
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"
    }
    
    # Filtre strict : on vire l'occasion et les boosters vides
    safe_keyword = f"{keyword} -lot -booster -vide -empty -occasion -used -abîmé -damaged"
    
    params = {
        "q": safe_keyword,
        "limit": 15,
        # FILTRE : conditions:{NEW} force les objets neufs/scellés
        "filter": "conditions:{NEW},buyingOptions:{FIXED_PRICE},itemLocationCountry:{FR}",
        "sort": "price" 
    }

    try:
        response = requests.get(search_url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get("itemSummaries", [])
            if not items:
                return None

            prices = [float(item['price']['value']) for item in items]
            
            # Calcul des statistiques de marché
            avg_price = round(statistics.mean(prices), 2)
            median_price = round(statistics.median(prices), 2)
            
            # Spread de marché (Tendance)
            low_market = statistics.mean(prices[:3]) if len(prices) >= 3 else prices[0]
            high_market = statistics.mean(prices[-3:]) if len(prices) >= 3 else prices[-1]
            spread = round(((high_market - low_market) / low_market) * 100, 2)

            listings = []
            for item in items[:5]:
                listings.append({
                    "title": item.get('title'),
                    "price": item.get('price', {}).get('value'),
                    "link": item.get('itemWebUrl'),
                    "image": item.get('thumbnailImages', [{}])[0].get('imageUrl', "")
                })

            return {
                "moyenne": avg_price,
                "mediane": median_price,
                "tendance": f"{spread}%",
                "annonces": listings
            }
    except Exception as e:
        print(f"Erreur eBay : {e}")
    return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    items = data.get("items", [])
    results = {}
    
    token = get_ebay_token()
    if not token:
        return {"error": "Token eBay manquant"}

    for item in items:
        keyword = item.get("ebay_keyword")
        cm_url = item.get("cm_url")
        
        market_stats = get_ebay_market_data(keyword, token)
        
        if market_stats:
            results[keyword] = {
                "stats": {
                    "prix_moyen": market_stats["moyenne"],
                    "prix_mediane": market_stats["mediane"],
                    "hausse_baisse": market_stats["tendance"],
                },
                "annonces": market_stats["annonces"],
                "admin_links": {
                    "cardmarket": cm_url
                }
            }
        else:
            results[keyword] = {"error": "Aucun produit neuf trouvé"}
            
    return results

def get_ebay_token():
    auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        return None
    credentials = f"{EBAY_APP_ID}:{EBAY_CERT_ID}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded}"
    }
    data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
    try:
        r = requests.post(auth_url, headers=headers, data=data)
        return r.json().get("access_token")
    except:
        return None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
