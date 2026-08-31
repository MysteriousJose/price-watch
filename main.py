import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from db import init_db, get_items, add_item, delete_item, get_results, save_results, update_last_scraped
from scraper import scrape_site

SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "10")) * 60
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scrape_all, 
        "interval", 
        seconds=SCRAPE_INTERVAL,
        misfire_grace_time=0,
        max_instances=1,
        coalesce=True
    )
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

async def run_scrape_all():
    items = await get_items()
    for item in items:
        try:
            results = await scrape_site(item["site"], item["query"], REQUEST_DELAY)
            if results:
                await save_results(item["id"], results)
                await update_last_scraped(item["id"])
                print(f"✅ Scraped: {item['query']} ({item['site']}) -> {len(results)} results")
            else:
                print(f"⚠️ No results for: {item['query']} ({item['site']})")
        except Exception as e:
            print(f"❌ Failed to scrape {item['query']}: {e}")
    print("🔄 Scheduled job completed.")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    items = await get_items()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "items": items,
        "current_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    })

@app.post("/add")
async def add(request: Request, query: str = Form(...), site: str = Form(...)):
    await add_item(query, site)
    return RedirectResponse("/", status_code=303)

@app.post("/delete/{item_id}")
async def delete(request: Request, item_id: int):
    await delete_item(item_id)
    return RedirectResponse("/", status_code=303)

@app.post("/trigger-scan/{item_id}")
async def trigger_scan(request: Request, item_id: int):
    items = await get_items()
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        results = await scrape_site(item["site"], item["query"], REQUEST_DELAY)
        if results:
            await save_results(item_id, results)
            await update_last_scraped(item_id)
        return JSONResponse({"status": "success", "count": len(results)})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

@app.get("/results/{item_id}", response_class=HTMLResponse)
async def view_results(request: Request, item_id: int):
    results = await get_results(item_id)
    return templates.TemplateResponse("results.html", {
        "request": request,
        "item_id": item_id,
        "results": results,
        "has_data": len(results) > 0
    })
