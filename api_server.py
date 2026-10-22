import os
import json
import csv
import io
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from scraper import ShopifyIntelScraper, normalize_domain
from batch_manager import BatchManager

# =====================================================================
# FASTAPI HEADLESS REST API INITIALIZATION
# =====================================================================
app = FastAPI(
    title="ShopifyIntel PRO — Headless REST API",
    description=(
        "Enterprise-grade autonomous revenue estimation, store intelligence, and catalog analytics API "
        "for Shopify, WooCommerce, and Custom E-Commerce stores. Pure headless backend with zero frontend dependencies."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Global CORS middleware for seamless integration into any frontend or microservice
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

def get_history() -> List[Dict[str, Any]]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_to_history(entry: dict):
    try:
        history = get_history()
        history = [h for h in history if h.get("domain") != entry.get("domain")]
        history.insert(0, entry)
        history = history[:50]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[API] History save error: {e}")

# =====================================================================
# REQUEST & RESPONSE MODELS (PYDANTIC SCHEMAS)
# =====================================================================
class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="Store domain or website URL to analyze", example="gymshark.com")
    custom_traffic: Optional[int] = Field(None, description="Optional override for monthly visitor traffic", example=250000)
    custom_cr: Optional[float] = Field(None, description="Optional override for conversion rate percentage", example=2.4)

class RecalculateRequest(BaseModel):
    aov: float = Field(..., description="Average Order Value in USD", example=65.0)
    monthly_visitors: int = Field(..., description="Monthly visitor count", example=100000)
    conversion_rate: float = Field(..., description="Expected conversion rate percentage", example=2.0)

class BatchUrlRequest(BaseModel):
    urls: List[str] = Field(..., description="List of store domains or website URLs to queue", example=["gymshark.com", "allbirds.com", "kith.com"])
    filename: Optional[str] = Field("direct_url_batch", description="Batch label or filename identifier", example="q4_lead_generation")

# =====================================================================
# ROOT & SYSTEM HEALTH ENDPOINTS
# =====================================================================
@app.get("/", summary="API Root & Status", tags=["System"])
async def api_root():
    """Returns service metadata, health status, and links to interactive OpenAPI / Swagger documentation."""
    return {
        "service": "ShopifyIntel PRO — Headless REST API",
        "version": "2.0.0",
        "status": "online",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_schema": "/openapi.json"
        },
        "endpoints": {
            "analyze_store": "POST /api/analyze",
            "recalculate_revenue": "POST /api/recalculate",
            "batch_upload": "POST /api/batch/upload",
            "batch_urls": "POST /api/batch/urls",
            "batch_status": "GET /api/batch/{batch_id}",
            "batch_cancel": "POST /api/batch/{batch_id}/cancel",
            "batch_export": "GET /api/batch/{batch_id}/export",
            "list_batches": "GET /api/batches",
            "search_history": "GET /api/history",
            "health_check": "GET /api/health"
        }
    }

@app.get("/api/health", summary="Health Check", tags=["System"])
async def health_check():
    """Health check endpoint for Docker, Kubernetes, and monitoring uptime tools."""
    return {
        "status": "healthy",
        "service": "ShopifyIntel PRO API",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }

# =====================================================================
# SINGLE STORE DEEP-DIVE ANALYSIS
# =====================================================================
@app.post("/api/analyze", summary="Analyze Single E-Commerce Store", tags=["Store Intelligence"])
async def analyze_store(req: AnalyzeRequest):
    """
    Performs autonomous revenue estimation and store intelligence scanning:
    - **Platform Detection:** Shopify, WooCommerce, or Custom E-Commerce.
    - **Non-Commerce Filtering:** Automatically flags non-commerce sites with $0.00 revenue.
    - **Catalog Mining:** Extracts public products, pricing, and category distribution.
    - **True Cart AOV:** Pareto 80/20 weighted unit pricing multiplied by vertical basket multiplier.
    - **Traffic & Revenue:** Tranco ranking power-law model with dynamic conversion rate stack.
    """
    if not req.url or len(req.url.strip()) < 3:
        raise HTTPException(status_code=400, detail="Please provide a valid store domain or website URL.")

    result = scraper.analyze_store(req.url.strip())

    if result.get("success") and result.get("is_ecommerce"):
        if req.custom_traffic or req.custom_cr:
            aov = result.get("catalog", {}).get("avg_price") or 45.0
            visitors = req.custom_traffic or result.get("revenue", {}).get("monthly_visitors", 50000)
            cr = req.custom_cr or 1.8
            orders = int(visitors * (cr / 100.0))
            monthly_rev = round(orders * aov, 2)
            result["revenue"]["monthly_visitors"] = visitors
            result["revenue"]["scenarios"]["expected"]["conversion_rate_pct"] = cr
            result["revenue"]["scenarios"]["expected"]["monthly_orders"] = orders
            result["revenue"]["scenarios"]["expected"]["monthly_revenue"] = monthly_rev
            result["revenue"]["scenarios"]["expected"]["daily_revenue"] = round(monthly_rev / 30, 2)
            result["revenue"]["scenarios"]["expected"]["annual_run_rate"] = round(monthly_rev * 12, 2)

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

@app.post("/api/recalculate", summary="Recalculate Revenue Scenarios", tags=["Store Intelligence"])
async def recalculate_revenue(req: RecalculateRequest):
    """Calculates monthly, annual, daily revenue and orders based on custom AOV, traffic, and conversion rate."""
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

# =====================================================================
# BATCH AUTOMATION & HIGH-THROUGHPUT ENGINE
# =====================================================================
@app.post("/api/batch/upload", summary="Upload CSV or Raw URLs for Batch Scanning", tags=["Batch Automation"])
async def upload_batch_csv(
    file: Optional[UploadFile] = File(None, description="CSV file containing a column of store URLs"),
    raw_urls: Optional[str] = Form(None, description="Line-separated or comma-separated list of store domains")
):
    """
    Submits a batch job from a CSV file or text list of domains.
    Executes in the background via multi-threaded concurrency pool (up to 1,000+ stores).
    """
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

@app.post("/api/batch/urls", summary="Queue Direct JSON Array of Store URLs", tags=["Batch Automation"])
async def start_batch_from_urls(req: BatchUrlRequest):
    """Direct JSON API endpoint to queue a list of domains for batch processing without multipart forms."""
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
        "total_queued": len(urls),
        "message": f"Successfully queued {len(urls)} stores for background scanning."
    }

@app.get("/api/batch/{batch_id}", summary="Get Batch Status & Results", tags=["Batch Automation"])
async def get_batch_status(batch_id: str):
    """Returns real-time execution status, progress counters, cumulative revenue KPI, and processed store results."""
    batch = batch_manager.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch job not found.")
    return batch

@app.post("/api/batch/{batch_id}/cancel", summary="Cancel / Stop Running Batch", tags=["Batch Automation"])
async def cancel_batch_job(batch_id: str):
    """Gracefully requests cancellation of an active batch job while preserving all processed stores."""
    success = batch_manager.cancel_batch(batch_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch job not found.")
    return {"success": True, "message": "Batch cancellation requested."}

@app.get("/api/batch/{batch_id}/export", summary="Export Batch Results to CSV", tags=["Batch Automation"])
async def export_batch_csv(
    batch_id: str,
    filter: Optional[str] = Query("all", description="Filter criteria: 'all', 'ecommerce', 'shopify', 'woocommerce', 'custom', 'non_ecommerce'")
):
    """Exports batch results to formatted CSV with self-healing reconstruction support."""
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

@app.get("/api/batches", summary="List All Batch Jobs", tags=["Batch Automation"])
async def list_all_batches():
    """Lists historical and active batch jobs with summary KPIs."""
    return batch_manager.list_batches()

# =====================================================================
# SEARCH HISTORY & EXPORT UTILITIES
# =====================================================================
@app.get("/api/history", summary="Get Search History", tags=["History"])
async def get_search_history():
    """Returns the list of recently analyzed single stores."""
    return get_history()

@app.delete("/api/history", summary="Clear Search History", tags=["History"])
async def clear_search_history():
    """Clears the search history store."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return {"success": True, "message": "Search history cleared."}

@app.post("/api/export/csv", summary="Export Products Sample to CSV", tags=["Utilities"])
async def export_products_csv(data: dict):
    """Generates a downloadable CSV for a store's top products catalog."""
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

# =====================================================================
# SERVER RUNNER
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    import socket
    import webbrowser
    import threading
    import time

    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    port = 8080 if is_port_in_use(8000) else 8000
    docs_url = f"http://localhost:{port}/docs"
    print("\n" + "="*65)
    print(">> ShopifyIntel PRO — Headless REST API Server v2.0")
    print(f">> API Base URL:    http://localhost:{port}")
    print(f">> Swagger Docs:    {docs_url}")
    print(f">> ReDoc Specs:     http://localhost:{port}/redoc")
    print("="*65 + "\n")

    def _open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(docs_url)
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("api_server:app", host="127.0.0.1", port=port, reload=False)
