import os
import re
import asyncio
import uvicorn
import time
import random
import base64
from fastapi import FastAPI, Request
from lxml import html
import requests 
from curl_cffi import requests as curl_requests 

app = FastAPI()

# --- CONFIGURATION (PROXY FRANCE) ---
RAW_PROXY = "iproyaleu.boilingproxies.com:11002:Nh4BaPOY:QzmAQ3Ap-country-fr"

def get_formatted_proxy(raw):
    try:
        parts = raw.split(':')
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    except:
        return None

PROXY_URL = get_formatted_proxy(RAW_PROXY)

# --- CONFIGURATION EBAY ---
EBAY_APP_ID = os.environ.get("EBAY_APP_ID")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID")

@app.get("/")
@app.head("/") 
async def root():
    return {"status": "En ligne", "region": "France (FR) ✅", "mode": "Furtif (curl_cffi) + eBay FR"}

# --- CARDMARKET (MODE FURTIF ANTI-CLOUDFLARE) ---
def get_price_cardmarket(url):
    if not PROXY_URL:
        return None

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    for attempt in range(3):
        try:
            print(f"🕵️ CM Tentative {attempt+1} (Furtif FR) : {url}")
            time.sleep(random.uniform(2, 5))
            
            # Utilisation de curl_cffi pour imiter l'empreinte TLS de Chrome 110
            response = curl_requests.get(
                url, 
                proxies=proxies, 
                impersonate="chrome110", 
                timeout=30
            )
            
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

# --- LE CODE EBAY ---
def get_ebay_token():
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        print("❌ Clés eBay manquantes !")
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
            return None
    except:
        return None

def get_ebay_average_price(keyword, token):
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"
    }
    
    safe_keyword = f"{keyword} -lot -display -booster -psa -pca -bgs -cgc -gradé -grade -vide"
    
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
             return None
    except:
        return None

# --- POINT D'ENTRÉE ---
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
            await asyncio.sleep(6) 
            
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
