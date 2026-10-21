import os
import io
import csv
import json
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from scraper import ShopifyIntelScraper, normalize_domain

BATCH_CSV_COLUMNS = [
    "Domain",
    "Input URL",
    "Is E-Commerce",
    "Platform",
    "Platform Category",
    "Is Shopify",
    "Store Name",
    "Niche / Category",
    "Est. Monthly Revenue (USD)",
    "Est. Annual Revenue (USD)",
    "Est. Daily Revenue (USD)",
    "Est. Monthly Traffic",
    "True Cart AOV (USD)",
    "Dynamic Conversion Rate (%)",
    "Catalog Products Found",
    "Currency",
    "Detected Theme / Stack",
    "Tracking Pixels / Marketing Apps",
    "Contact Email",
    "Top Best-Selling Product",
    "Top Best-Seller Price (USD)",
    "Analysis Status",
    "Analyzed At"
]

class BatchManager:
    def __init__(self, scraper: ShopifyIntelScraper, batches_dir: Optional[str] = None, max_workers: int = 6):
        self.scraper = scraper
        self.batches_dir = batches_dir or os.path.join(os.path.dirname(__file__), "batches")
        os.makedirs(self.batches_dir, exist_ok=True)
        self.max_workers = max_workers
        self.batches: Dict[str, Dict[str, Any]] = {}
        self.cancel_flags: Dict[str, bool] = {}
        self.lock = threading.Lock()
        self._load_existing_batches()

    def _load_existing_batches(self):
        """Loads metadata of previously processed batches from disk safely with per-file isolation."""
        if not os.path.exists(self.batches_dir):
            return
        for fname in os.listdir(self.batches_dir):
            if fname.endswith(".json"):
                batch_id = fname[:-5]
                filepath = os.path.join(self.batches_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # If a batch was left as 'running' or 'queued' when server stopped, mark interrupted
                        if data.get("status") in ["running", "queued"]:
                            data["status"] = "cancelled"
                            data["current_domain"] = ""
                        self.batches[batch_id] = data
                except Exception as e:
                    print(f"[BatchManager] Warning: skipped corrupted batch file {fname}: {e}")

    @staticmethod
    def extract_urls_from_csv(content_str: str) -> List[str]:
        """Intelligently detects URL/domain column in CSV or raw list, handling up to thousands of rows."""
        lines = [line.strip() for line in content_str.splitlines() if line.strip()]
        if not lines:
            return []

        # Attempt standard CSV parsing
        try:
            reader = csv.reader(io.StringIO(content_str))
            rows = [r for r in reader if any(cell.strip() for cell in r)]
        except Exception:
            rows = [[l] for l in lines]

        if not rows:
            return []

        header = [c.strip().lower() for c in rows[0]]
        url_col_idx = -1
        url_keywords = ["url", "domain", "website", "store", "site", "link", "shop", "address", "host"]
        for idx, col_name in enumerate(header):
            if any(kw in col_name for kw in url_keywords):
                url_col_idx = idx
                break

        start_row = 1 if url_col_idx != -1 else 0
        if url_col_idx == -1:
            if len(rows) > 1 and "." not in rows[0][0]:
                start_row = 1
            url_col_idx = 0

        extracted_urls = []
        for row in rows[start_row:]:
            if len(row) > url_col_idx:
                val = row[url_col_idx].strip().strip("'\"")
                if val and len(val) >= 3 and not val.lower().startswith("http://example"):
                    extracted_urls.append(val)

        # Deduplicate while preserving input sequence
        seen = set()
        deduped = []
        for u in extracted_urls:
            norm = normalize_domain(u)
            if norm and norm not in seen:
                seen.add(norm)
                deduped.append(u)

        return deduped

    def create_batch(self, filename: str, urls: List[str], custom_workers: Optional[int] = None) -> str:
        """Initializes a new batch job scalable for up to thousands of URLs."""
        batch_id = str(uuid.uuid4())[:12]
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Dynamically scale workers for large lists (up to 8 threads)
        workers = custom_workers or (8 if len(urls) >= 100 else 6)

        batch_data = {
            "batch_id": batch_id,
            "filename": filename,
            "status": "queued",  # queued, running, completed, cancelled
            "total": len(urls),
            "completed": 0,
            "ecommerce_count": 0,
            "shopify_count": 0,
            "woocommerce_count": 0,
            "custom_count": 0,
            "non_ecommerce_count": 0,
            "non_shopify_count": 0,
            "error_count": 0,
            "total_monthly_revenue": 0.0,
            "created_at": created_at,
            "current_domain": "",
            "workers": workers,
            "items": [],
            "urls_queue": urls
        }

        with self.lock:
            self.batches[batch_id] = batch_data
            self.cancel_flags[batch_id] = False
            self._save_batch_json(batch_id)
            self._init_batch_csv(batch_id)

        return batch_id

    def _init_batch_csv(self, batch_id: str):
        """Initializes the CSV export file with headers."""
        csv_path = os.path.join(self.batches_dir, f"{batch_id}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(BATCH_CSV_COLUMNS)

    def _append_to_batch_csv(self, batch_id: str, row: List[Any]):
        """Appends a single verified result row to the batch CSV."""
        csv_path = os.path.join(self.batches_dir, f"{batch_id}.csv")
        try:
            with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            print(f"[BatchManager] CSV write error: {e}")

    def _save_batch_json(self, batch_id: str):
        """Persists batch status and data to JSON disk file atomically."""
        if batch_id not in self.batches:
            return
        filepath = os.path.join(self.batches_dir, f"{batch_id}.json")
        tmppath = os.path.join(self.batches_dir, f"{batch_id}.json.tmp")
        try:
            with open(tmppath, "w", encoding="utf-8") as f:
                json.dump(self.batches[batch_id], f, indent=2, ensure_ascii=False)
            os.replace(tmppath, filepath)
        except Exception as e:
            print(f"[BatchManager] JSON persist error: {e}")
            if os.path.exists(tmppath):
                try:
                    os.remove(tmppath)
                except Exception:
                    pass

    def start_batch(self, batch_id: str):
        """Launches background worker thread for batch processing."""
        if batch_id not in self.batches:
            return False
        t = threading.Thread(target=self._run_batch, args=(batch_id,), daemon=True)
        t.start()
        return True

    def _process_single_url(self, batch_id: str, index: int, url: str) -> Dict[str, Any]:
        """Processes a single URL through universal multi-platform intelligence."""
        if self.cancel_flags.get(batch_id, False):
            return {"index": index, "status": "cancelled", "url": url}

        domain = normalize_domain(url)
        with self.lock:
            if batch_id in self.batches:
                self.batches[batch_id]["current_domain"] = domain

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            result = self.scraper.analyze_store(domain)
            is_ecommerce = result.get("is_ecommerce", False)
            platform = result.get("platform", "Unknown")
            platform_category = result.get("platform_category", "non_ecommerce")
            is_shopify = result.get("is_shopify", False)

            if is_ecommerce:
                store_info = result.get("store_info", {})
                catalog = result.get("catalog", {})
                revenue = result.get("revenue", {})
                scenarios = revenue.get("scenarios", {})
                expected = scenarios.get("expected", {})

                best_sellers = catalog.get("best_sellers", [])
                top_best_seller = best_sellers[0] if best_sellers else {}

                item = {
                    "index": index,
                    "input_url": url,
                    "domain": domain,
                    "is_ecommerce": True,
                    "platform": platform,
                    "platform_category": platform_category,
                    "is_shopify": is_shopify,
                    "store_name": store_info.get("store_name", domain),
                    "niche": catalog.get("niche_info", {}).get("niche", "General E-Commerce"),
                    "monthly_revenue": expected.get("monthly_revenue", 0.0),
                    "annual_revenue": expected.get("annual_run_rate", 0.0),
                    "daily_revenue": expected.get("daily_revenue", 0.0),
                    "monthly_traffic": revenue.get("monthly_visitors", 0),
                    "true_cart_aov": catalog.get("true_cart_aov", 0.0),
                    "dynamic_cr": expected.get("conversion_rate_pct", 0.0),
                    "products_count": catalog.get("total_products_found", 0),
                    "currency": store_info.get("currency", "USD"),
                    "theme": store_info.get("theme", "Custom"),
                    "pixels": [a["name"] for a in store_info.get("apps", []) if a.get("category") in ["Tracking & Attribution", "Marketing Automation", "Social Commerce"]],
                    "contact_email": store_info.get("contact_email", "") or "",
                    "best_seller_title": top_best_seller.get("title", ""),
                    "best_seller_price": top_best_seller.get("price", 0.0),
                    "status": "completed",
                    "analyzed_at": timestamp,
                    "full_data": result
                }
            else:
                item = {
                    "index": index,
                    "input_url": url,
                    "domain": domain,
                    "is_ecommerce": False,
                    "platform": platform,
                    "platform_category": platform_category,
                    "is_shopify": False,
                    "store_name": domain,
                    "niche": "Non-Commerce",
                    "monthly_revenue": 0.0,
                    "annual_revenue": 0.0,
                    "daily_revenue": 0.0,
                    "monthly_traffic": 0,
                    "true_cart_aov": 0.0,
                    "dynamic_cr": 0.0,
                    "products_count": 0,
                    "currency": "-",
                    "theme": "-",
                    "pixels": [],
                    "contact_email": "",
                    "best_seller_title": "",
                    "best_seller_price": 0.0,
                    "status": "filtered (non-commerce)",
                    "analyzed_at": timestamp,
                    "full_data": result
                }

        except Exception as e:
            item = {
                "index": index,
                "input_url": url,
                "domain": domain,
                "is_ecommerce": False,
                "platform": "Error / Unreachable",
                "platform_category": "non_ecommerce",
                "is_shopify": False,
                "store_name": domain,
                "niche": "Error",
                "monthly_revenue": 0.0,
                "annual_revenue": 0.0,
                "daily_revenue": 0.0,
                "monthly_traffic": 0,
                "true_cart_aov": 0.0,
                "dynamic_cr": 0.0,
                "products_count": 0,
                "currency": "-",
                "theme": "-",
                "pixels": [],
                "contact_email": "",
                "best_seller_title": "",
                "best_seller_price": 0.0,
                "status": f"error: {str(e)[:50]}",
                "analyzed_at": timestamp,
                "full_data": None
            }

        # Format CSV row adhering to BATCH_CSV_COLUMNS
        csv_row = self._format_item_to_csv_row(item)

        # Progressive thread-safe update
        with self.lock:
            if batch_id in self.batches:
                batch = self.batches[batch_id]
                batch["items"].append(item)
                batch["completed"] += 1

                if item["is_ecommerce"]:
                    batch["ecommerce_count"] = batch.get("ecommerce_count", 0) + 1
                    batch["total_monthly_revenue"] = round(batch["total_monthly_revenue"] + item["monthly_revenue"], 2)
                    cat = item.get("platform_category", "")
                    if cat == "shopify":
                        batch["shopify_count"] += 1
                    elif cat == "woocommerce":
                        batch["woocommerce_count"] = batch.get("woocommerce_count", 0) + 1
                    elif cat == "custom":
                        batch["custom_count"] = batch.get("custom_count", 0) + 1
                elif "error" in item["status"].lower():
                    batch["error_count"] += 1
                else:
                    batch["non_ecommerce_count"] = batch.get("non_ecommerce_count", 0) + 1
                    batch["non_shopify_count"] += 1

                self._append_to_batch_csv(batch_id, csv_row)
                self._save_batch_json(batch_id)

        return item

    def _run_batch(self, batch_id: str):
        """Executes the batch worker with controlled thread pool."""
        batch = self.batches.get(batch_id)
        if not batch:
            return

        with self.lock:
            batch["status"] = "running"
            self._save_batch_json(batch_id)

        urls = batch["urls_queue"]
        workers_count = batch.get("workers", self.max_workers)

        with ThreadPoolExecutor(max_workers=workers_count) as executor:
            from concurrent.futures import as_completed
            future_to_url = {}
            for idx, url in enumerate(urls, 1):
                if self.cancel_flags.get(batch_id, False):
                    break
                f = executor.submit(self._process_single_url, batch_id, idx, url)
                future_to_url[f] = url

            for f in as_completed(future_to_url):
                if self.cancel_flags.get(batch_id, False):
                    break
                try:
                    f.result()
                except Exception as e:
                    u = future_to_url.get(f, "unknown")
                    print(f"[BatchManager] Execution error for {u}: {e}")

        with self.lock:
            if self.cancel_flags.get(batch_id, False):
                batch["status"] = "cancelled"
            else:
                batch["status"] = "completed"
            batch["current_domain"] = ""
            self._save_batch_json(batch_id)

    def cancel_batch(self, batch_id: str) -> bool:
        """Signals a running batch to stop immediately."""
        with self.lock:
            if batch_id in self.batches:
                self.cancel_flags[batch_id] = True
                self.batches[batch_id]["status"] = "cancelled"
                self.batches[batch_id]["current_domain"] = ""
                self._save_batch_json(batch_id)
                return True
        return False

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves live batch status and processed stores."""
        with self.lock:
            batch = self.batches.get(batch_id)
            if not batch:
                return None
            return {
                "batch_id": batch["batch_id"],
                "filename": batch["filename"],
                "status": batch["status"],
                "total": batch["total"],
                "completed": batch["completed"],
                "ecommerce_count": batch.get("ecommerce_count", 0),
                "shopify_count": batch["shopify_count"],
                "woocommerce_count": batch.get("woocommerce_count", 0),
                "custom_count": batch.get("custom_count", 0),
                "non_ecommerce_count": batch.get("non_ecommerce_count", 0),
                "non_shopify_count": batch.get("non_shopify_count", 0),
                "error_count": batch["error_count"],
                "total_monthly_revenue": batch["total_monthly_revenue"],
                "created_at": batch["created_at"],
                "current_domain": batch.get("current_domain", ""),
                "items": batch["items"]
            }

    def _format_item_to_csv_row(self, item: Dict[str, Any]) -> List[Any]:
        """Maps an internal item dictionary to a standard BATCH_CSV_COLUMNS row."""
        return [
            item.get("domain", ""),
            item.get("input_url", ""),
            "Yes" if item.get("is_ecommerce") else "No",
            item.get("platform", ""),
            item.get("platform_category", ""),
            "Yes" if item.get("is_shopify") else "No",
            item.get("store_name", ""),
            item.get("niche", ""),
            item.get("monthly_revenue", 0.0),
            item.get("annual_revenue", 0.0),
            item.get("daily_revenue", 0.0),
            item.get("monthly_traffic", 0),
            item.get("true_cart_aov", 0.0),
            item.get("dynamic_cr", 0.0),
            item.get("products_count", 0),
            item.get("currency", "-"),
            item.get("theme", "-"),
            "; ".join(item.get("pixels", [])) if item.get("pixels") else "-",
            item.get("contact_email", ""),
            item.get("best_seller_title", ""),
            item.get("best_seller_price", 0.0),
            item.get("status", ""),
            item.get("analyzed_at", "")
        ]

    def get_batch_csv_content(self, batch_id: str, filter_type: str = "all", only_shopify: bool = False) -> Optional[str]:
        """
        Returns full CSV content with flexible multi-platform filtering:
        - filter_type='all': All records
        - filter_type='ecommerce': All verified e-commerce stores (Shopify, WooCommerce, Custom)
        - filter_type='shopify' or only_shopify=True: Shopify stores only
        - filter_type='woocommerce': WordPress / WooCommerce stores only
        - filter_type='custom': Custom-coded / Headless stores only
        - filter_type='non_ecommerce': Non-commerce filtered websites
        """
        csv_path = self.get_batch_csv_path(batch_id)
        if not csv_path or not os.path.exists(csv_path):
            # Self-healing: if CSV file is missing, automatically reconstruct it from memory or JSON
            batch_data = self.batches.get(batch_id)
            if not batch_data:
                json_path = os.path.join(self.batches_dir, f"{batch_id}.json")
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as jf:
                            batch_data = json.load(jf)
                            self.batches[batch_id] = batch_data
                    except Exception as e:
                        print(f"[BatchManager] JSON load fallback error: {e}")
                        batch_data = None

            if batch_data and batch_data.get("items"):
                try:
                    reconstructed_path = os.path.join(self.batches_dir, f"{batch_id}.csv")
                    with open(reconstructed_path, "w", newline="", encoding="utf-8-sig") as cf:
                        writer = csv.writer(cf)
                        writer.writerow(BATCH_CSV_COLUMNS)
                        for it in batch_data["items"]:
                            writer.writerow(self._format_item_to_csv_row(it))
                    csv_path = reconstructed_path
                except Exception as e:
                    print(f"[BatchManager] CSV reconstruction error: {e}")

        if not csv_path or not os.path.exists(csv_path):
            return None

        if only_shopify:
            filter_type = "shopify"

        if filter_type == "all":
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                return f.read()

        out = io.StringIO()
        writer = csv.writer(out)
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            writer.writerow(header)

            is_ecom_idx = 2
            plat_cat_idx = 4
            is_shopify_idx = 5

            for row in reader:
                if len(row) <= max(is_ecom_idx, plat_cat_idx, is_shopify_idx):
                    continue
                is_ecom = row[is_ecom_idx].strip().lower() in ["yes", "true"]
                cat = row[plat_cat_idx].strip().lower()
                is_shop = row[is_shopify_idx].strip().lower() in ["yes", "true"]

                if filter_type == "ecommerce" and is_ecom:
                    writer.writerow(row)
                elif filter_type == "shopify" and (cat == "shopify" or is_shop):
                    writer.writerow(row)
                elif filter_type == "woocommerce" and cat == "woocommerce":
                    writer.writerow(row)
                elif filter_type == "custom" and cat == "custom":
                    writer.writerow(row)
                elif filter_type == "non_ecommerce" and not is_ecom:
                    writer.writerow(row)

        return out.getvalue()

    def get_batch_csv_path(self, batch_id: str) -> Optional[str]:
        """Returns the absolute path to the batch's CSV export file."""
        csv_path = os.path.join(self.batches_dir, f"{batch_id}.csv")
        return csv_path if os.path.exists(csv_path) else None

    def list_batches(self) -> List[Dict[str, Any]]:
        """Lists summaries of all batch jobs."""
        with self.lock:
            summaries = []
            for b_id, b in self.batches.items():
                summaries.append({
                    "batch_id": b["batch_id"],
                    "filename": b["filename"],
                    "status": b["status"],
                    "total": b["total"],
                    "completed": b["completed"],
                    "ecommerce_count": b.get("ecommerce_count", 0),
                    "shopify_count": b.get("shopify_count", 0),
                    "woocommerce_count": b.get("woocommerce_count", 0),
                    "total_monthly_revenue": b.get("total_monthly_revenue", 0.0),
                    "created_at": b.get("created_at", "")
                })
            summaries.sort(key=lambda x: x["created_at"], reverse=True)
            return summaries

    @staticmethod
    def generate_sample_csv() -> str:
        """Returns sample CSV template with a realistic mix of Shopify, WooCommerce, Custom, and Non-Commerce sites."""
        sample_rows = [
            ["store_url"],
            ["colourpop.com"],        # Shopify (Beauty)
            ["skinfit.com"],          # WooCommerce (Skincare)
            ["gymshark.com"],         # Shopify
            ["warbyparker.com"],      # Custom / Headless Commerce
            ["techcrunch.com"],       # WordPress (Non-Commerce / Blog)
            ["allbirds.com"],         # Shopify
            ["wikipedia.org"],        # Non-Commerce / Informational
            ["woocommerce.com"]       # WooCommerce
        ]
        out = io.StringIO()
        writer = csv.writer(out)
        for r in sample_rows:
            writer.writerow(r)
        return out.getvalue()
