from fastapi import FastAPI, HTTPException
from scraping_puppis import scrape_puppis
import uvicorn

app = FastAPI()

@app.get("/scrape")
async def run_scraper():
    try:
        print("Starting scraper...")
        data = await scrape_puppis()
        return {"status": "success", "count": len(data), "data": data}
    except Exception as e:
        print(f"Scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
