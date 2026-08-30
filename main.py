import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

async def run_scrape_all():
    items = await get_items()
    for item in items:
        results = await scrape_site(item["site"], item["query"], REQUEST_DELAY)
        await save_results(item["id"], results)
        await update_last_scraped(item["id"])
        print(f"Scraped: {item['query']} ({item['site']}) -> {len(results)} results")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    items = await get_items()
    return templates.TemplateResponse("index.html", {"request": request, "items": items})

@app.post("/add")
async def add(request: Request, query: str = Form(...), site: str = Form(...)):
    await add_item(query, site)
    return RedirectResponse("/", status_code=303)

@app.post("/delete/{item_id}")
async def delete(request: Request, item_id: int):
    await delete_item(item_id)
    return RedirectResponse("/", status_code=303)

@app.get("/results/{item_id}")
async def results(request: Request, item_id: int):
    item_results = await get_results(item_id)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "items": await get_items(),
        "active_results": item_results
    })
