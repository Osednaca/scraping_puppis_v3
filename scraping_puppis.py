import asyncio
from playwright.async_api import async_playwright

async def scrape_puppis():
    async with async_playwright() as p:
        # Launch browser (headless=True for server environment, but can be False for debugging)
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",      # importante con poca RAM
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--single-process",             # solo si tenés poca RAM (<1.5 GB)
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        print("Navigating to Puppis...")
        await page.goto("https://www.puppis.com.co/perro", timeout=60000)
        
        # --- Handle Location Modal ---
        try:
            print("Checking for location modal...")
            # Wait a bit for modal to appear
            await page.wait_for_timeout(5000)
            
            # Look for common modal elements
            # Strategy: Look for "Bogotá" option and click it, then "Guardar"
            # Or just "Guardar" if a default is selected.
            
            if await page.get_by_text("Selecciona tu ubicación").is_visible():
                print("Modal detected.")
                # Try to click the dropdown or location if needed. 
                # Assuming we can just click "Guardar" or select Bogota.
                # Let's try to find "Bogotá" text and click it.
                bogota_option = page.get_by_text("Bogotá DC y aledaños")
                if await bogota_option.is_visible():
                    await bogota_option.click()
                    await page.wait_for_timeout(1000)
                
                # Click Guardar
                guardar_btn = page.get_by_role("button", name="GUARDAR")
                if await guardar_btn.is_visible():
                    await guardar_btn.click()
                else:
                    # Fallback text search
                    await page.get_by_text("GUARDAR").click()
                
                print("Modal handled.")
                await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Modal handling skipped or failed (might not be present): {e}")

        # --- Get Categories ---
        print("Extracting categories...")
        # User mentioned a "Menu" button. We'll try to find categories on the page first.
        # Usually /perro has subcategories listed.
        
        # We look for links that contain /perros/ and are likely categories.
        # We filter out the main /perro link and duplicates.
        category_links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll("a[href^='/perros/']"));
                return [...new Set(links.map(a => a.href))].filter(href => href !== 'https://www.puppis.com.co/perro');
            }
        """)
        
        # Deduplicate categories
        category_links = list(set(category_links))
        print(f"Found {len(category_links)} categories.")
        
        all_products = []
        
        # Restart browser context every 3 categories to prevent crashes/memory leaks
        for i, link in enumerate(category_links):
            if i % 3 == 0 and i > 0:
                print("\n♻ Restarting browser context to free resources...")
                await context.close()
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    viewport={"width": 1280, "height": 720}
                )
                page = await context.new_page()
            
            print(f"\n📂 [{i+1}/{len(category_links)}] Scraping: {link}")
            try:
                await page.goto(link, timeout=60000)
                await page.wait_for_timeout(1000)  # Reduced from 3000ms
                
                # --- Infinite Scroll & Load More ---
                clicks = 0
                max_clicks = 50  # Prevent infinite loop
                while clicks < max_clicks:
                    # Scroll to bottom
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(800)  # Reduced from 2000ms
                    
                    # Use JavaScript to find and click the button directly
                    button_clicked = await page.evaluate("""
                        () => {
                            // Look for button with "Mostrar más" text
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const loadMoreBtn = buttons.find(btn => {
                                const text = btn.innerText || btn.textContent || '';
                                return text.trim().toLowerCase().includes('mostrar más') || 
                                       text.trim().toLowerCase().includes('mostrar mas');
                            });
                            
                            if (loadMoreBtn) {
                                loadMoreBtn.click();
                                return true;
                            }
                            return false;
                        }
                    """)
                    
                    found_button = button_clicked
                    
                    if found_button:
                        clicks += 1
                        print(f"  ✓ Clicked 'Mostrar más' button (click #{clicks})")
                        await page.wait_for_timeout(1500)  # Reduced from 3000ms
                    else:
                        # If button is not visible, we might be at the end.
                        print(f"  ✗ No more 'Mostrar más' button found after {clicks} clicks.")
                        break
                
                # --- Extract Products & Variations ---
                print(f"\n📦 Extracting products and variations...")
                
                # Use JavaScript to extract all products with their variations
                # This avoids Playwright locator caching issues
                products_data = await page.evaluate("""
                    async () => {
                        const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
                        const products = [];
                        const cards = document.querySelectorAll('a.vtex-product-summary-2-x-clearLink');
                        
                        for (let i = 0; i < cards.length; i++) {
                            try {
                                const card = cards[i];
                                
                                // Scroll into view
                                card.scrollIntoView({ behavior: 'auto', block: 'center' });
                                await sleep(100);
                                
                                // Basic info
                                const titleEl = card.querySelector('h3 > span');
                                const title = titleEl ? titleEl.innerText.trim() : 'No Title';
                                const url = card.href || '';
                                const imgEl = card.querySelector('img');
                                const image = imgEl ? imgEl.src : null;
                                
                                // Variations
                                const presentations = [];
                                
                                // Click +1 button if present
                                const plusOne = card.querySelector('div.product-show-more-list');
                                if (plusOne) {
                                    try {
                                        plusOne.click();
                                        await sleep(300);
                                    } catch (e) {}
                                }
                                
                                // Get variation buttons
                                const varButtons = card.querySelectorAll('button.product-variation');
                                
                                if (varButtons.length > 0) {
                                    for (let j = 0; j < varButtons.length; j++) {
                                        const btn = varButtons[j];
                                        const size = btn.innerText.trim();
                                        
                                        // Click variation
                                        try {
                                            btn.click();
                                            await sleep(1000); // Wait for price update
                                            
                                            // Re-query price element to get fresh value
                                            const priceEl = card.querySelector('span[class*=\"sellingPrice\"]');
                                            const price = priceEl ? priceEl.innerText.trim() : 'N/A';
                                            
                                            presentations.push({ size, price });
                                        } catch (e) {
                                            console.log('Error clicking variation:', e);
                                        }
                                    }
                                } else {
                                    // No variations
                                    const priceEl = card.querySelector('span[class*=\"sellingPrice\"]');
                                    const price = priceEl ? priceEl.innerText.trim() : 'N/A';
                                    presentations.push({ size: 'Default', price });
                                }
                                
                                products.push({ title, url, image, presentations });
                                
                            } catch (e) {
                                console.log('Error extracting product:', e);
                            }
                        }
                        
                        return products;
                    }
                """)
                
                # Log the extracted products
                for idx, prod in enumerate(products_data):
                    print(f"  [{idx+1}/{len(products_data)}] {prod['title']}")
                    print(f"       Image: {prod['image'][:50]}..." if prod['image'] else "       Image: None")
                    print(f"       Variations: {len(prod['presentations'])}")
                    for pres in prod['presentations']:
                        print(f"         • {pres['size']}: {pres['price']}")
                
                print(f"\n✅ Category complete: {len(products_data)} products extracted.")
                all_products.extend(products_data)
                
            except Exception as e:
                print(f"Error scraping category {link}: {e}")
                # If page crashes, try to recover by creating a new page
                try:
                    await page.close()
                    page = await context.new_page()
                except:
                    pass
                continue

        await browser.close()
        
        # Deduplicate products by URL
        unique_products = {p['url']: p for p in all_products}.values()
        return list(unique_products)

if __name__ == "__main__":
    data = asyncio.run(scrape_puppis())
    import json
    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Scraping complete. Saved {len(data)} products to products.json")
