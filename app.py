import os
import re
import asyncio
import uvicorn
from fastapi import FastAPI, Request
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "En ligne", "message": "API AkameTCG active sur Render ! 🚀"}

def get_price_free(url):
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        print(f"🕵️ Scan en cours : {url}")
        # On force la version 147 pour correspondre à l'installation système
        driver = uc.Chrome(
            options=options, 
            browser_executable_path='/usr/bin/google-chrome-stable',
            version_main=147 
        )
        
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "table-body")))
        
        from lxml import html
        tree = html.fromstring(driver.page_source)
        rows = tree.xpath('//div[contains(@class, "table-body")]/div[contains(@class, "row")]')
        
        blacklist = ["rmp", "main propre", "remise", "abim", "abîm", "damage", "enfonc", "déchir"]
        
        for row in rows:
            text_ligne = " ".join(row.xpath('.//text()')).lower()
            if not any(word in text_ligne for word in blacklist):
                price_element = row.xpath('.//div[contains(@class, "price-container")]//span/text()')
                if price_element:
                    price = float(re.sub(r'[^\d.,]', '', price_element[0]).replace(',', '.'))
                    print(f"💰 PRIX TROUVÉ : {price} €")
                    driver.quit()
                    return price
        driver.quit()
        return None
    except Exception as e:
        print(f"❌ Erreur : {e}")
        try: driver.quit()
        except: pass
        return None

@app.post("/get_prices")
async def get_prices(request: Request):
    data = await request.json()
    links = data.get("links", [])
    results = {}
    for link in links:
        results[link] = get_price_free(link)
        await asyncio.sleep(2)
    return results

if __name__ == "__main__":
    # Render utilise la variable d'environnement PORT
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)