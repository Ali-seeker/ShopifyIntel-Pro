# ShopifyIntel PRO — Universal E-Commerce & Shopify Revenue Intelligence Engine

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Shopify%20%7C%20WooCommerce%20%7C%20Custom-orange.svg)]()
[![Status](https://img.shields.io/badge/status-Production%20Ready-brightgreen.svg)]()
[![Repository](https://img.shields.io/badge/GitHub-ShopifyIntel--Pro-black?logo=github)](https://github.com/Ali-seeker/ShopifyIntel-Pro)

A high-performance, enterprise-grade revenue estimation and store intelligence platform. Designed to analyze any e-commerce storefront (**Shopify**, **WooCommerce / WordPress**, and **Custom E-Commerce**) with deep-dive financial calculations, catalog breakdown, multi-currency normalization, and high-throughput batch automation (1,000+ stores).

---

## Key Features

### 1. Universal Multi-Platform Detection & Filtering
* **Shopify Intelligence:** Native detection via public product APIs (`/products.json`, `/collections/all`), theme metadata, and CDN signatures.
* **WooCommerce / WordPress:** Automatic REST API endpoint discovery (`/wp-json/wc/v3`, `/wp-json/wp/v2`) and Store API catalog extraction.
* **Custom E-Commerce Engine:** Microdata, OpenGraph (`og:price:amount`), Schema.org Product JSON-LD, and semantic DOM scraper for headless and enterprise platforms (Magento, BigCommerce, Salesforce Commerce Cloud).
* **Strict Non-Commerce Filtering:** Automatically filters out blogs, SaaS tools, news sites, universities, and government portals with **$0.00** revenue to eliminate false positives.

### 2. Triangulated Revenue Intelligence Model
* **Tranco Global Rank Scaling:** Traffic estimation derived from calibrated global ranking data and Zipf's Law power-law distribution.
* **Pareto 80/20 Best-Seller Weighting:** Averages are weighted 70% toward top-selling products and 30% across catalog median to reflect real customer purchasing behavior.
* **Units Per Transaction (UPT / Basket Multiplier):** Contextual basket sizing based on industry vertical (e.g., 2.10 items for beauty, 1.60 for apparel, 1.25 for footwear).
* **Dynamic Conversion Rate (CR%) Stack:** Calibrated baseline CR modified by price tiers (-0.2% to -0.65% for high-ticket items) and detected marketing pixels (Meta Pixel, TikTok Pixel, Google Tag Manager, Klaviyo flows).
* **Staging SKU & Outlier Clipping:** Automatic protection against staging placeholder prices ($999,999) to ensure realistic, audited AOV.

### 3. Multi-Currency Normalization Engine
* Real-time recognition and conversion for **13+ global currencies** (`USD`, `EUR`, `GBP`, `CAD`, `AUD`, `PKR`, `INR`, `DKK`, `AED`, `JPY`, `SGD`, etc.).
* Standardized USD financial reporting alongside native currency catalog figures.

### 4. High-Volume Batch Automation (1,000+ Stores)
* **Concurrent Multi-Threading:** Worker thread pool processes hundreds of domains efficiently without memory leaks.
* **Real-Time Web Dashboard:** Live progress bar, automated KPI counters (Total, Shopify, Non-Commerce, Cumulative Revenue), and interactive paginated tables.
* **Instant Export:** One-click CSV and JSON export with filter options (All Stores, E-Commerce Only, Shopify Only).
* **Graceful Cancellation:** Safely halt active batch runs while preserving all completed records.

### 5. SaaS-Grade User Interface
* **Zero Browser-Native Popups:** Replaced all generic `alert()` and `confirm()` dialogs with custom animated modal dialogs (`customModalBox`) featuring smooth backdrop blurs, contextual icons, and keyboard navigation (`Esc` to close, `Enter` to confirm).
* **Glassmorphism Toast Notifications:** Floating slide-in toasts for non-blocking actions (copy to clipboard, batch export).
* **Fully Offline-Ready:** Bundled self-contained Tailwind CSS and typography scripts—no external CDN dependency needed.

---

## Project Structure

```text
├── scraper.py                 # Core scraping engine & financial calculation algorithms
├── server.py                  # FastAPI REST API & application web server
├── batch_manager.py           # Concurrency queue & batch persistence engine
├── run.bat                    # One-click Windows startup script
├── requirements.txt           # Python package dependencies
├── history.json               # Local persistent search history storage
├── SHOPIFY_ENGINE_DOCUMENTATION.md # Deep research document & algorithmic rationale
├── static/
│   ├── index.html             # Responsive SaaS dashboard UI
│   ├── tailwind.js            # Bundled Tailwind CSS compiler
│   └── tailwind.min.css       # Bundled utility styles
└── batches/                   # Runtime batch result storage (JSON & CSV exports)
    └── .gitkeep
```

---

## Quickstart & Installation

### Prerequisites
* **Python 3.10+** installed on your system.

### Option A: One-Click Startup (Windows)
Double-click `run.bat` or run:
```cmd
run.bat
```
This automatically verifies dependencies and launches the dashboard at `http://localhost:8000`.

### Option B: Manual Startup

1. **Clone repository:**
   ```bash
   git clone https://github.com/Ali-seeker/ShopifyIntel-Pro.git
   cd ShopifyIntel-Pro
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the server:**
   ```bash
   python server.py
   ```
   *The interactive web interface is now accessible at `http://localhost:8000`.*

---

## REST API Documentation

### Single Store Analysis
* **Endpoint:** `POST /api/analyze`
* **Payload:**
  ```json
  {
    "url": "gymshark.com"
  }
  ```
* **Response (Abbreviated):**
  ```json
  {
    "success": true,
    "is_ecommerce": true,
    "is_shopify": true,
    "platform": "Shopify",
    "domain": "gymshark.com",
    "revenue": {
      "monthly_visitors": 4180000,
      "aov": 64.45,
      "dynamic_cr": 2.0,
      "estimated_monthly_revenue": 5393627.15,
      "annual_run_rate": 64723525.80
    },
    "catalog": {
      "total_products_detected": 1840,
      "cart_aov": 64.45,
      "currency": "USD"
    }
  }
  ```

### Batch Upload & Scanning
* **Endpoint:** `POST /api/batch/upload`
* **Body:** `multipart/form-data` with CSV file or `raw_urls` form field.
* **Response:**
  ```json
  {
    "success": true,
    "batch_id": "6711ce86-8bd",
    "total_queued": 1000,
    "message": "Successfully queued 1000 stores for automated intelligence scanning."
  }
  ```

### Poll Batch Status
* **Endpoint:** `GET /api/batch/{batch_id}`

### Stop Active Batch
* **Endpoint:** `POST /api/batch/{batch_id}/cancel`

### Export Batch Results
* **Endpoint:** `GET /api/batch/{batch_id}/export?filter=all|ecommerce|shopify`

---

## Security & Reliability
* **Anti-Bot & Cloudflare Bypass:** Emulates Chrome browser headers with HTTP/2 and modern TLS cipher suites via `curl_cffi`.
* **Zero System Freezes:** Asynchronous non-blocking architecture ensures the web UI remains completely responsive during heavy background operations.
* **Deterministic Deduplication:** All domains are normalized (lowercased, stripped of protocols, query strings, and trailing slashes) to prevent redundant network calls.

---

## License
Released under the [MIT License](LICENSE).
