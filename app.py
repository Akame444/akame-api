import os
import re
import asyncio
import uvicorn
import requests
import time
import random
import base64
from fastapi import FastAPI, Request
from lxml import html

app = FastAPI()

# --- CONFIGURATION (ALLEMAGNE) ---
RAW_PROXY = "iproyaleu.boilingproxies.com:11002:Nh4BaPOY:QzmAQ3Ap-country-de"

def get_formatted_proxy(raw):
    try:
        parts = raw.split(':')
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)

# --- CONFIGURATION EBAY (SÉCURISÉE) ---
EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")
# ---------------------------------

@app.get("/")
async def root():
    return {"status": "En ligne", "region": "Allemagne (DE) ✅", "mode": "Hybride CM (Headers originaux) + eBay FR Strict"}

def get_price_cardmarket(url):
    if not PROXY_URL:
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    # RETOUR AUX SOURCES : Tes User-Agents d'origine
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    
    for attempt in range(3):
        try:
            # RETOUR AUX SOURCES : Tes Headers d'origine qui ne faisaient pas d'erreur 403
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,de;q=0.7",
                "Referer": "https://www.google.de/",
                "DNT": "1"
            }
            
            print(f"🕵️ CM Tentative {attempt+1} : {url}")
            time.sleep(random.uniform(2, 5))
            
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            
            if response.status_code == 200:
                tree = html.fromstring(response.content)
                rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
                
                blacklist = ["rmp", "main propre", "remise", "bimé", "bime", "abim", "abîm", "damage", "enfonc", "déchir", "trou", "petit", "coté", "defaut", "défaut", "non", "léger", "leger", "photo"]
                
                for row in rows:
                    text_ligne = " ".join(row.xpath('.//text()')).lower()
                    if not any(word in text_ligne for word in blacklist):
                        price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                        if price_element:
                            price = float(re.sub(r'[^\d.,]', '', price_element[0]).replace(',', '.'))
                            print(f"💰 CM VICTOIRE : {price} €")
                            return price
                return None
            
            print(f"❌ CM Blocage (HTTP {response.status_code})")
                
        except Exception as e:
            print(f"⚠️ Erreur CM : {e}")
        
        time.sleep(6)
            
    return None

def get_ebay_token():
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        print("❌ Clés eBay manquantes dans l'environnement !")
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
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"❌ Erreur Auth eBay: {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ Exception Auth eBay: {e}")
        return None

def get_ebay_average_price(keyword, token):
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"
    }
    
    safe_keyword = f"{keyword} -lot -display -booster -psa -pca -bgs -cgc -gradé -grade -vide"
    
    # NOUVEAU FILTRE : On force la recherche à cibler UNIQUEMENT des articles situés en France
    params = {
        "q": safe_keyword,
        "limit": 5,
        "filter": "buyingOptions:{FIXED_PRICE},itemLocationCountry:{FR}"
    }

    try:
        response = requests.get(search_url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get("itemSummaries", [])
            if not items:
                print(f"⚠️ Aucun résultat eBay pour : {keyword}")
                return None
            
            total_price = 0
            count = 0
            for item in items:
                price_str = item.get("price", {}).get("value")
                if price_str:
                    total_price += float(price_str)
                    count += 1
            
            if count > 0:
                average = round(total_price / count, 2)
                print(f"💰 EBAY MOYENNE (sur {count} ventes en FR) : {average} € pour '{keyword}'")
                return average
            return None
            
        else:
             print(f"❌ Erreur Recherche eBay: {response.text}")
             return None
             
    except Exception as e:
        print(f"⚠️ Exception Recherche eBay: {e}")
        return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    items = data.get("items", [])
    results = {}
    
    ebay_token = get_ebay_token()
    
    for item in items:
        cm_url = item.get("cm_url")
        ebay_keyword = item.get("ebay_keyword")
        
        cm_price = None
        ebay_price = None
        
        if cm_url:
            cm_price = get_price_cardmarket(cm_url)
            await asyncio.sleep(4) 
            
        if ebay_token and ebay_keyword:
            ebay_price = get_ebay_average_price(ebay_keyword, ebay_token)
            
        final_cote = None
        if cm_price and ebay_price:
             final_cote = round((cm_price + ebay_price) / 2, 2)
        elif cm_price:
             final_cote = cm_price
        elif ebay_price:
             final_cote = ebay_price
             
        key = cm_url if cm_url else ebay_keyword
        results[key] = {
            "cardmarket_price": cm_price,
            "ebay_average": ebay_price,
            "cote_hybride": final_cote
        }
        
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
