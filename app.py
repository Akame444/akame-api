def get_ebay_market_data(keyword, token):
    """Récupère uniquement les annonces NEUVES et calcule les stats"""
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"
    }
    
    # --- FILTRE DE MOTS-CLÉS ULTRA STRICT ---
    # On exclut : lots, boosters vides, produits abîmés, ouverts ou d'occasion
    safe_keyword = f"{keyword} -lot -booster -vide -empty -occasion -used -abîmé -damaged -reconditionné"
    
    params = {
        "q": safe_keyword,
        "limit": 20,
        # --- LA MAGIE EST ICI ---
        # conditions:{NEW} -> Force uniquement le NEUF / SCELLÉ
        # buyingOptions:{FIXED_PRICE} -> Uniquement les prix fixes (pas d'enchères bizarres)
        "filter": "conditions:{NEW},buyingOptions:{FIXED_PRICE},itemLocationCountry:{FR}",
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
            
            # Calculs
            avg_price = round(statistics.mean(prices), 2)
            median_price = round(statistics.median(prices), 2)
            
            # Calcul du Spread (volatilité du neuf)
            low_market = statistics.mean(prices[:5])
            high_market = statistics.mean(prices[-5:])
            spread_trend = round(((high_market - low_market) / low_market) * 100, 2)

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
                "tendance_marche": f"{spread_trend}%",
                "derniere_ventes_estim": listings
            }
    except Exception as e:
        print(f"Erreur API eBay : {e}")
    return None
