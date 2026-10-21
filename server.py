import os
import json
import csv
import io
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import ShopifyIntelScraper, normalize_domain
from batch_manager import BatchManager

app = FastAPI(title="Shopify Intelligence & Revenue Scraper", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
scraper = ShopifyIntelScraper()
batch_manager = BatchManager(scraper)

# Ensure history file exists
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def get_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_to_history(entry: dict):
    try:
        history = get_history()
        # Keep unique by domain, latest first
        history = [h for h in history if h.get("domain") != entry.get("domain")]
        history.insert(0, entry)
        history = history[:25]  # keep last 25 searches
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Failed to save history:", e)

class AnalyzeRequest(BaseModel):
    url: str
    custom_traffic: Optional[int] = None
    custom_cr: Optional[float] = None

class RecalculateRequest(BaseModel):
    aov: float
    monthly_visitors: int
    conversion_rate: float

class BatchUrlRequest(BaseModel):
    urls: List[str]
    filename: Optional[str] = "direct_url_batch"

# ==========================================
# SINGLE STORE MANUAL ANALYSIS ENDPOINTS
# ==========================================

@app.post("/api/analyze")
async def analyze_store(req: AnalyzeRequest):
    if not req.url or len(req.url.strip()) < 3:
        raise HTTPException(status_code=400, detail="Please provide a valid store domain or website URL.")

    result = scraper.analyze_store(req.url.strip())

    if result.get("success") and result.get("is_ecommerce"):
        # If user passed custom traffic or CR, recalculate
        if req.custom_traffic or req.custom_cr:
            aov = result["catalog"]["avg_price"] or 45.0
            visitors = req.custom_traffic or result["revenue"]["monthly_visitors"]
            cr = req.custom_cr or 1.8
            orders = int(visitors * (cr / 100.0))
            monthly_rev = round(orders * aov, 2)
            result["revenue"]["monthly_visitors"] = visitors
            result["revenue"]["scenarios"]["expected"]["conversion_rate_pct"] = cr
            result["revenue"]["scenarios"]["expected"]["monthly_orders"] = orders
            result["revenue"]["scenarios"]["expected"]["monthly_revenue"] = monthly_rev
            result["revenue"]["scenarios"]["expected"]["daily_revenue"] = round(monthly_rev / 30, 2)
            result["revenue"]["scenarios"]["expected"]["annual_run_rate"] = round(monthly_rev * 12, 2)

        # Save to history summary
        save_to_history({
            "domain": result.get("domain"),
            "store_name": result.get("store_info", {}).get("store_name"),
            "is_ecommerce": True,
            "is_shopify": result.get("is_shopify", False),
            "platform": result.get("platform", "E-Commerce"),
            "platform_category": result.get("platform_category", "custom"),
            "currency": result.get("store_info", {}).get("currency", "USD"),
            "niche": result.get("catalog", {}).get("niche_info", {}).get("niche", "General E-Commerce"),
            "aov": result.get("catalog", {}).get("true_cart_aov"),
            "monthly_revenue": result.get("revenue", {}).get("scenarios", {}).get("expected", {}).get("monthly_revenue"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    elif result.get("success") and not result.get("is_ecommerce"):
        save_to_history({
            "domain": result.get("domain"),
            "store_name": result.get("domain"),
            "is_ecommerce": False,
            "is_shopify": False,
            "platform": result.get("platform", "Non-Commerce Website"),
            "platform_category": "non_ecommerce",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        })


    return result

@app.post("/api/recalculate")
async def recalculate_revenue(req: RecalculateRequest):
    cr_decimal = req.conversion_rate / 100.0
    orders = int(req.monthly_visitors * cr_decimal)
    monthly_rev = round(orders * req.aov, 2)
    daily_rev = round(monthly_rev / 30, 2)
    annual_rev = round(monthly_rev * 12, 2)
    return {
        "monthly_visitors": req.monthly_visitors,
        "conversion_rate": req.conversion_rate,
        "aov": req.aov,
        "monthly_orders": orders,
        "monthly_revenue": monthly_rev,
        "daily_revenue": daily_rev,
        "annual_run_rate": annual_rev
    }

@app.get("/api/history")
async def get_search_history():
    return get_history()

@app.delete("/api/history")
async def clear_search_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return {"success": True}

@app.post("/api/export/csv")
async def export_products_csv(data: dict):
    products = data.get("products", [])
    if not products:
        raise HTTPException(status_code=400, detail="Products data not found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Price", "Product Type", "Vendor", "Variants Count", "URL", "Published At", "Image URL"])

    for p in products:
        writer.writerow([
            p.get("title", ""),
            p.get("price", ""),
            p.get("product_type", ""),
            p.get("vendor", ""),
            p.get("variants_count", ""),
            p.get("url", ""),
            p.get("published_at", ""),
            p.get("image_url", "")
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=shopify_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

# ==========================================
# BATCH AUTOMATION & BULK CSV ENDPOINTS
# ==========================================

@app.post("/api/batch/upload")
async def upload_batch_csv(
    file: Optional[UploadFile] = File(None),
    raw_urls: Optional[str] = Form(None)
):
    """Handles CSV file upload or pasted URLs and starts background batch scraping."""
    urls = []
    filename = "pasted_urls.csv"

    if file:
        filename = file.filename or "uploaded_batch.csv"
        content_bytes = await file.read()
        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content_str = content_bytes.decode("latin-1", errors="ignore")
        urls = BatchManager.extract_urls_from_csv(content_str)
    elif raw_urls:
        urls = BatchManager.extract_urls_from_csv(raw_urls)

    if not urls:
        raise HTTPException(status_code=400, detail="No valid URLs or store domains found in the provided input.")

    batch_id = batch_manager.create_batch(filename, urls)
    batch_manager.start_batch(batch_id)

    return {
        "success": True,
        "batch_id": batch_id,
        "filename": filename,
        "total_queued": len(urls),
        "message": f"Successfully queued {len(urls)} stores for automated intelligence scanning."
    }

@app.post("/api/batch/urls")
async def start_batch_from_urls(req: BatchUrlRequest):
    """Starts batch scraping from a direct JSON list of URLs."""
    urls = []
    seen = set()
    for u in req.urls:
        norm = normalize_domain(u)
        if norm and norm not in seen:
            seen.add(norm)
            urls.append(u)

    if not urls:
        raise HTTPException(status_code=400, detail="No valid URLs provided.")

    batch_id = batch_manager.create_batch(req.filename or "direct_urls", urls)
    batch_manager.start_batch(batch_id)

    return {
        "success": True,
        "batch_id": batch_id,
        "filename": req.filename,
        "total_queued": len(urls)
    }

@app.get("/api/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Fetches real-time status, KPIs, and progressive store results for a batch."""
    batch = batch_manager.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch job not found.")
    return batch

@app.post("/api/batch/{batch_id}/cancel")
async def cancel_batch_job(batch_id: str):
    """Cancels or stops a running batch."""
    success = batch_manager.cancel_batch(batch_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch job not found.")
    return {"success": True, "message": "Batch cancellation requested."}

@app.get("/api/batch/{batch_id}/export")
async def export_batch_csv(batch_id: str, filter: Optional[str] = "all"):
    """Exports batch results to CSV, supports ?filter=all, ?filter=ecommerce, ?filter=shopify, ?filter=woocommerce, ?filter=custom."""
    csv_content = batch_manager.get_batch_csv_content(batch_id, filter_type=filter or "all")
    if not csv_content:
        raise HTTPException(status_code=404, detail="Batch CSV not available.")

    filter_prefixes = {
        "shopify": "ShopifyVerifiedOnly",
        "woocommerce": "WooCommerceVerifiedOnly",
        "custom": "CustomEcommerceOnly",
        "ecommerce": "AllEcommerceVerified",
        "non_ecommerce": "NonCommerceFiltered"
    }
    prefix = filter_prefixes.get(filter, "AllScannedStores")
    filename = f"{prefix}_Batch_{batch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/batch-sample-csv")
async def download_sample_csv():
    """Generates and serves a ready-to-test multi-platform sample CSV template."""
    csv_str = BatchManager.generate_sample_csv()
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_ecommerce_stores.csv"}
    )

@app.get("/api/download-500-test-suite")
@app.get("/api/download-200-test-suite")
async def download_test_suite_csv():
    """Serves the 500-store comprehensive edge-case test suite CSV."""
    for fname in ["comprehensive_500_ecommerce_test_suite.csv", "comprehensive_200_ecommerce_test_suite.csv"]:
        csv_path = os.path.join(os.path.dirname(__file__), fname)
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={fname}"}
            )
    raise HTTPException(status_code=404, detail="Test suite CSV not found.")


@app.get("/api/batches")
async def list_all_batches():
    """Lists historical and active batch jobs."""
    return batch_manager.list_batches()

@app.get("/api/proxy-image")
async def proxy_image(url: str):
    """Safely proxies images with Chrome impersonation to bypass CDN hotlinking / CORS / referrer restrictions."""
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        session = scraper._get_session()
        resp = session.get(
            url,
            impersonate="chrome124",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
            timeout=8
        )
        if resp.status_code == 200 and resp.content:
            content_type = resp.headers.get("content-type", "image/jpeg")
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        raise HTTPException(status_code=resp.status_code, detail="Remote server rejected image request")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Image proxy failed: {str(e)}")

# ==========================================
# STATIC FILES & ROOT DASHBOARD
# ==========================================

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Dashboard loading... Static index.html not found.</h1>")

if __name__ == "__main__":
    import uvicorn
    import socket

    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    port = 8080 if is_port_in_use(8000) else 8000
    print("\n" + "="*60)
    print(">> Shopify Intelligence & Revenue Scraper Dashboard v2.0")
    print(f">> Dashboard URL: http://localhost:{port}")
    print(">> Bulk Automation & CSV Scanning Enabled")
    print("="*60 + "\n")
    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=False)

