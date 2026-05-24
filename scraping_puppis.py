import asyncio
from playwright.async_api import async_playwright

async def scrape_puppis():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        # --- Hardcoded highlighted category URLs (Perros + Gatos) ---
        category_links = [
            # ===== PERROS - Alimentos =====
            "https://www.puppis.com.co/perros/alimentos/alimento-seco",
            "https://www.puppis.com.co/perros/alimentos/alimento-humedo",
            "https://www.puppis.com.co/perros/snacks",
            "https://www.puppis.com.co/perros/snacks/bocaditos",
            "https://www.puppis.com.co/perros/snacks/dentales",
            "https://www.puppis.com.co/perros/snacks/galletas",
            "https://www.puppis.com.co/perros/snacks/salsas",
            "https://www.puppis.com.co/perros/snacks/cremosos",
            # ===== PERROS - Estética e higiene =====
            "https://www.puppis.com.co/perros/estetica-e-higiene/recolectores-y-bolsas",
            "https://www.puppis.com.co/perros/estetica-e-higiene/cepillos-y-peines",
            "https://www.puppis.com.co/perros/estetica-e-higiene/shampoo-acondicionador-y-jabones",
            "https://www.puppis.com.co/perros/estetica-e-higiene/limpieza-dental",
            "https://www.puppis.com.co/perros/estetica-e-higiene/eliminadores-de-olores-y-manchas",
            # ===== PERROS - Medicamentos =====
            "https://www.puppis.com.co/perros/desparasitantes",
            "https://www.puppis.com.co/perros/medicamentos/complementos-y-suplementos",
            # ===== GATOS - Alimentos =====
            "https://www.puppis.com.co/gatos/alimentos/alimento-seco",
            "https://www.puppis.com.co/gatos/alimentos/alimento-humedo",
            "https://www.puppis.com.co/gatos/snack",
            "https://www.puppis.com.co/gatos/snack/bocaditos",
            "https://www.puppis.com.co/gatos/snack/dentals",
            "https://www.puppis.com.co/gatos/snack/cremosos",
            # ===== GATOS - Estética e higiene =====
            "https://www.puppis.com.co/gatos/estetica-e-higiene/arenas",
            "https://www.puppis.com.co/gatos/estetica-e-higiene/areneras",
            "https://www.puppis.com.co/gatos/estetica-e-higiene/palas-y-bolsas",
            "https://www.puppis.com.co/gatos/estetica-e-higiene/cepillos-y-peines",
            "https://www.puppis.com.co/gatos/estetica-e-higiene/eliminadores-de-olores",
            "https://www.puppis.com.co/gatos/estetica-e-higiene/shampoo-acondicionador-y-jabones",
            "https://www.puppis.com.co/gatos/estetica-e-higiene/limpieza-dental",
            # ===== GATOS - Medicamentos =====
            "https://www.puppis.com.co/gatos/desparasitantes",
            "https://www.puppis.com.co/gatos/medicamentos/complementos-y-suplementos",
        ]
        print(f"Total categories to scrape: {len(category_links)}")

        # --- Handle Location Modal on first page load ---
        print("Navigating to Puppis to handle location modal...")
        await page.goto("https://www.puppis.com.co/perro", timeout=60000)
        try:
            print("Checking for location modal...")
            await page.wait_for_timeout(5000)

            if await page.get_by_text("Selecciona tu ubicación").is_visible():
                print("Modal detected.")
                bogota_option = page.get_by_text("Bogotá DC y aledaños")
                if await bogota_option.is_visible():
                    await bogota_option.click()
                    await page.wait_for_timeout(1000)

                guardar_btn = page.get_by_role("button", name="GUARDAR")
                if await guardar_btn.is_visible():
                    await guardar_btn.click()
                else:
                    await page.get_by_text("GUARDAR").click()

                print("Modal handled.")
                await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Modal handling skipped or failed (might not be present): {e}")

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
                await page.wait_for_timeout(1000)

                # --- Extraer categoría y subcategoría del breadcrumb ---
                # El breadcrumb tiene clases con índices: --2 = categoría, --3 = subcategoría
                breadcrumb_data = await page.evaluate("""
                    () => {
                        const cat2 = document.querySelector('a.vtex-breadcrumb-1-x-link--2');
                        const cat3 = document.querySelector('a.vtex-breadcrumb-1-x-link--3');
                        return {
                            category: cat2 ? cat2.innerText.trim() : null,
                            subcategory: cat3 ? cat3.innerText.trim() : null,
                        };
                    }
                """)
                category    = breadcrumb_data.get("category")
                subcategory = breadcrumb_data.get("subcategory")
                print(f"  📁 Categoría: {category} | Subcategoría: {subcategory}")

                # --- Infinite Scroll & Load More ---
                clicks = 0
                max_clicks = 50
                while clicks < max_clicks:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(800)

                    button_clicked = await page.evaluate("""
                        () => {
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

                    if button_clicked:
                        clicks += 1
                        print(f"  ✓ Clicked 'Mostrar más' button (click #{clicks})")
                        await page.wait_for_timeout(1500)
                    else:
                        print(f"  ✗ No more 'Mostrar más' button found after {clicks} clicks.")
                        break

                # --- Extract Products & Variations ---
                print(f"\n📦 Extracting products and variations...")

                products_data = await page.evaluate("""
                    async () => {
                        const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
                        const products = [];
                        const cards = document.querySelectorAll('a.vtex-product-summary-2-x-clearLink');

                        for (let i = 0; i < cards.length; i++) {
                            try {
                                const card = cards[i];

                                card.scrollIntoView({ behavior: 'auto', block: 'center' });
                                await sleep(100);

                                const titleEl = card.querySelector('h3 > span');
                                const title = titleEl ? titleEl.innerText.trim() : 'No Title';
                                const url = card.href || '';
                                const imgEl = card.querySelector('img');
                                const image = imgEl ? imgEl.src : null;

                                const presentations = [];

                                const plusOne = card.querySelector('div.product-show-more-list');
                                if (plusOne) {
                                    try {
                                        plusOne.click();
                                        await sleep(300);
                                    } catch (e) {}
                                }

                                const varButtons = card.querySelectorAll('button.product-variation');

                                if (varButtons.length > 0) {
                                    for (let j = 0; j < varButtons.length; j++) {
                                        const btn = varButtons[j];
                                        const size = btn.innerText.trim();
                                        try {
                                            btn.click();
                                            await sleep(1000);
                                            const priceEl = card.querySelector('span[class*="sellingPrice"]');
                                            const price = priceEl ? priceEl.innerText.trim() : 'N/A';
                                            presentations.push({ size, price });
                                        } catch (e) {
                                            console.log('Error clicking variation:', e);
                                        }
                                    }
                                } else {
                                    const priceEl = card.querySelector('span[class*="sellingPrice"]');
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

                # Agregar categoría y subcategoría a cada producto
                for prod in products_data:
                    prod["category"]    = category
                    prod["subcategory"] = subcategory

                # Log
                for idx, prod in enumerate(products_data):
                    print(f"  [{idx+1}/{len(products_data)}] {prod['title']}")
                    print(f"       Categoría: {prod['category']} > {prod['subcategory']}")
                    print(f"       Image: {prod['image'][:50]}..." if prod['image'] else "       Image: None")
                    print(f"       Variations: {len(prod['presentations'])}")
                    for pres in prod['presentations']:
                        print(f"         • {pres['size']}: {pres['price']}")

                print(f"\n✅ Category complete: {len(products_data)} products extracted.")
                all_products.extend(products_data)

            except Exception as e:
                print(f"Error scraping category {link}: {e}")
                try:
                    await page.close()
                    page = await context.new_page()
                except:
                    pass
                continue

        await browser.close()

        # Deduplicate by URL — keep last occurrence to preserve category info
        seen = {}
        for p in all_products:
            seen[p['url']] = p
        return list(seen.values())


if __name__ == "__main__":
    import json
    data = asyncio.run(scrape_puppis())
    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Scraping complete. Saved {len(data)} products to products.json")