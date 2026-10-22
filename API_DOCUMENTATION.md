# ShopifyIntel PRO — Headless REST API Developer Guide

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![OpenAPI Spec](https://img.shields.io/badge/OpenAPI-3.1-brightgreen.svg)](http://localhost:8000/docs)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](Dockerfile)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A high-performance, standalone Headless REST API for autonomous revenue estimation, store intelligence, and catalog analytics across **Shopify**, **WooCommerce / WordPress**, and **Custom E-Commerce** storefronts.

Zero frontend dependencies. Pure JSON inputs and outputs designed for direct integration into backends, CRM pipelines, microservices, and automation workflows.

---

## 1. Quickstart

### Option A: One-Click Startup (Windows)
Double-click `run_api.bat` or run:
```cmd
run_api.bat
```
The server will start and automatically open the interactive Swagger UI in your browser at **`http://localhost:8000/docs`** *(or `http://localhost:8080/docs` if port 8000 is occupied)*.

### Option B: Python CLI
```bash
pip install -r requirements.txt
python api_server.py
```

### Option C: Docker Container (Optional)
```bash
docker compose up -d
```
Or:
```bash
docker build -t shopifyintel-api .
docker run -p 8000:8000 shopifyintel-api
```

---

## 2. Interactive API Documentation

When the server is running, interactive documentation is accessible at:
* **Swagger UI (Interactive API Tester):** [`http://localhost:8000/docs`](http://localhost:8000/docs) *(or `http://localhost:8080/docs`)*
* **ReDoc (Technical Documentation):** [`http://localhost:8000/redoc`](http://localhost:8000/redoc)
* **OpenAPI 3.1 JSON Schema:** [`http://localhost:8000/openapi.json`](http://localhost:8000/openapi.json)

---

## 3. API Endpoints Reference

### 1. Health Check
* **Endpoint:** `GET /api/health`
* **Description:** Verifies service health and uptime status.
* **Example Request (cURL):**
  ```bash
  curl -X GET http://localhost:8000/api/health
  ```
* **Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "service": "ShopifyIntel PRO API",
    "version": "2.0.0",
    "timestamp": "2026-10-22T13:00:00.000000"
  }
  ```

---

### 2. Single Store Deep-Dive Analysis
* **Endpoint:** `POST /api/analyze`
* **Description:** Analyzes any website domain or store URL. Detects platform, scrapes public catalog, calculates True Cart AOV (Pareto 80/20 weighted), scales Tranco traffic, and computes monthly & annual revenue projections.
* **Request Headers:** `Content-Type: application/json`
* **Request Body:**
  ```json
  {
    "url": "gymshark.com"
  }
  ```
  *(Optional overrides: `"custom_traffic": 250000`, `"custom_cr": 2.5`)*

#### Integration Examples:

**cURL:**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "gymshark.com"}'
```

**Python (`requests`):**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/analyze",
    json={"url": "gymshark.com"},
    timeout=30
)
data = response.json()
print(f"Platform: {data['platform']}")
print(f"Monthly Revenue: ${data['revenue']['estimated_monthly_revenue']:,.2f}")
print(f"AOV: ${data['catalog']['cart_aov']:.2f} {data['catalog']['currency']}")
```

**Node.js / JavaScript (`fetch`):**
```javascript
const response = await fetch("http://localhost:8000/api/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url: "gymshark.com" })
});
const data = await response.json();
console.log(`Platform: ${data.platform}, Revenue: $${data.revenue.estimated_monthly_revenue}`);
```

* **Response (200 OK — Abbreviated):**
  ```json
  {
    "success": true,
    "is_ecommerce": true,
    "is_shopify": true,
    "platform": "Shopify",
    "platform_category": "shopify",
    "domain": "gymshark.com",
    "working_url": "https://www.gymshark.com",
    "store_info": {
      "store_name": "Gymshark",
      "currency": "USD",
      "theme": "Custom Enterprise Theme",
      "apps": [
        {"name": "Klaviyo", "category": "Marketing Automation"},
        {"name": "Meta Pixel", "category": "Tracking & Attribution"}
      ]
    },
    "catalog": {
      "total_products_found": 1840,
      "cart_aov": 64.45,
      "true_cart_aov": 64.45,
      "currency": "USD",
      "best_sellers": [
        {"title": "Vital Seamless 2.0 Leggings", "price": 54.0}
      ]
    },
    "revenue": {
      "monthly_visitors": 4180000,
      "estimated_monthly_revenue": 5393627.15,
      "dynamic_cr": 2.0,
      "annual_run_rate": 64723525.80,
      "daily_revenue": 179787.57,
      "confidence": "High (Verified Web Traffic Rank)"
    }
  }
  ```

---

### 3. Batch Queue via Direct JSON Array
* **Endpoint:** `POST /api/batch/urls`
* **Description:** Directly queues a list of domains for background processing without multipart file uploads.
* **Request Body:**
  ```json
  {
    "urls": ["allbirds.com", "colourpop.com", "kith.com", "skims.com"],
    "filename": "q4_high_priority_leads"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "batch_id": "8a32b11e-42c",
    "filename": "q4_high_priority_leads",
    "total_queued": 4,
    "message": "Successfully queued 4 stores for background scanning."
  }
  ```

---

### 4. Batch Upload via CSV / Form
* **Endpoint:** `POST /api/batch/upload`
* **Description:** Uploads a CSV file or raw multiline text string of store domains.
* **Example cURL:**
  ```bash
  curl -X POST http://localhost:8000/api/batch/upload \
    -F "file=@stores_list.csv"
  ```

---

### 5. Poll Batch Status & Progressive Results
* **Endpoint:** `GET /api/batch/{batch_id}`
* **Description:** Retrieves real-time execution progress, KPI counters, and all completed store records.
* **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/api/batch/8a32b11e-42c
  ```
* **Response (200 OK):**
  ```json
  {
    "batch_id": "8a32b11e-42c",
    "filename": "q4_high_priority_leads",
    "status": "completed",
    "total": 4,
    "completed": 4,
    "ecommerce_count": 4,
    "shopify_count": 4,
    "total_monthly_revenue": 9470891.75,
    "items": [
      {
        "domain": "colourpop.com",
        "is_ecommerce": true,
        "platform": "Shopify",
        "monthly_revenue": 3021666.69,
        "true_cart_aov": 70.77,
        "monthly_traffic": 1312000,
        "dynamic_cr": 3.25
      }
    ]
  }
  ```

---

### 6. Export Filtered Batch Results to CSV
* **Endpoint:** `GET /api/batch/{batch_id}/export?filter={filter_type}`
* **Query Parameters:**
  * `filter=all` — All processed stores
  * `filter=ecommerce` — E-Commerce stores only (Shopify, WooCommerce, Custom)
  * `filter=shopify` — Shopify verified stores only
  * `filter=woocommerce` — WordPress / WooCommerce stores only
  * `filter=custom` — Custom / Headless stores only
  * `filter=non_ecommerce` — Non-commerce filtered websites ($0.00 revenue)
* **Example cURL:**
  ```bash
  curl -O -J "http://localhost:8000/api/batch/8a32b11e-42c/export?filter=ecommerce"
  ```
* **Self-Healing:** Automatically reconstructs CSV data on the fly from in-memory records or JSON if file on disk is deleted.

---

### 7. Stop / Cancel Active Batch
* **Endpoint:** `POST /api/batch/{batch_id}/cancel`
* **Description:** Gracefully halts remaining background scraping while safely preserving all completed stores.

---

### 8. List All Batch Jobs
* **Endpoint:** `GET /api/batches`
* **Description:** Returns summary history of all batches with total stores, revenue KPI, and completion status.

---

## 4. Production Deployment Best Practices

### Systemd Service (Linux / Ubuntu)
Create `/etc/systemd/system/shopifyintel.service`:
```ini
[Unit]
Description=ShopifyIntel PRO Headless API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/shopifyintel
ExecStart=/home/ubuntu/shopifyintel/venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable shopifyintel
sudo systemctl start shopifyintel
```

---

## 5. License
Distributed under the [MIT License](LICENSE).
