import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import sqlite3
from db import init_db, get_items, add_item, delete_item, get_results, save_results, update_last_scraped
from scraper import scrape_site

SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "10")) * 60
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_scrape_all, "interval", seconds=SCRAPE_INTERVAL)
    scheduler.start()
    yield

app = FastAPI(lifespan=lifespan)
#app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

async def run_scrape_all():
    items = await get_items()
    for item in items:
        results = await scrape_site(item["site"], item["query"], REQUEST_DELAY)
        await save_results(item["id"], results)
        await update_last_scraped(item["id"])
        print(f"Scraped: {item['query']} ({item['site']}) -> {len(results)} results")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    conn = sqlite3.connect("/app/data/watch.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Fetch all items
    cur.execute("SELECT * FROM items")
    items = [dict(row) for row in cur.fetchall()]
    conn.close()
    
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
async def trigger_scan(item_id: int):
    # Assuming you have a scraper function like `run_scrape(item_id)`
    # Replace with your actual function name
    try:
        # run_scrape(item_id)  # 👈 Uncomment when you have the function
        return {"status": "manual trigger added. Check logs.", "item_id": item_id}
    except Exception as e:
        return {"error": str(e)}

@app.get("/results/{item_id}", response_class=HTMLResponse)
async def view_results(request: Request, item_id: int):
    conn = sqlite3.connect("/app/data/watch.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Fetch listings for this item
    cur.execute("SELECT * FROM results WHERE item_id = ? ORDER BY scraped_at DESC", (item_id,))
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "item_id": item_id,
        "results": results,  # 👈 Match template variable
        "has_data": len(results) > 0
    })
