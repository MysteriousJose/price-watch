import aiosqlite
import os
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "watch.db")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                site TEXT NOT NULL CHECK(site IN ('amazon', 'ebay', 'swappa')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scraped TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER REFERENCES items(id),
                title TEXT,
                price TEXT,
                url TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_items() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM items ORDER BY created_at DESC") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def add_item(query: str, site: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO items (query, site) VALUES (?, ?)", (query, site)
        )
        await db.commit()
        return cursor.lastrowid

async def delete_item(item_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        await db.execute("DELETE FROM results WHERE item_id = ?", (item_id,))
        await db.commit()

async def get_results(item_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM results WHERE item_id = ? ORDER BY scraped_at DESC LIMIT ?",
            (item_id, limit)
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def save_results(item_id: int, results: List[Dict[str, Any]]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM results WHERE item_id = ?", (item_id,))
        for r in results:
            await db.execute(
                "INSERT INTO results (item_id, title, price, url) VALUES (?, ?, ?, ?)",
                (item_id, r.get("title", ""), r.get("price", ""), r.get("url", ""))
            )
        await db.commit()

async def update_last_scraped(item_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE items SET last_scraped = CURRENT_TIMESTAMP WHERE id = ?",
            (item_id,)
        )
        await db.commit()
