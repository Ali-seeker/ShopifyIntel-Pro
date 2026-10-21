import re
import json
import statistics
import html
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from curl_cffi import requests

def normalize_domain(user_input: str) -> str:
    """Cleans up user input to get a canonical domain name."""
    cleaned = user_input.strip().lower()
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned
    parsed = urlparse(cleaned)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    domain = domain.split("/")[0].split(":")[0]
    return domain

# E-commerce Niche Benchmarks: (Base Conversion Rate, Units Per Cart / Basket Multiplier)
NICHE_PROFILES = {
    "Beauty & Cosmetics": {
        "keywords": ["makeup", "palette", "shadow", "lip", "skin", "lash", "beauty", "serum", "cream", "cosmetic", "glow", "blush", "lotion", "skincare"],
        "base_cr": 2.6,
        "basket_multiplier": 2.10,
        "description": "High impulse, multi-item shopping baskets (lipsticks, palettes, brushes)."
    },
    "Apparel & Fashion": {
        "keywords": ["shirt", "hoodie", "legging", "top", "pant", "dress", "jacket", "t-shirt", "short", "apparel", "denim", "clothing", "wear", "outfit", "trousers"],
        "base_cr": 2.0,
        "basket_multiplier": 1.60,
        "description": "Seasonal catalog purchases, matching sets & tops/bottoms."
    },
    "Footwear & Shoes": {
        "keywords": ["shoe", "sneaker", "runner", "boot", "slip-on", "wool", "flats", "slide", "sandal", "footwear", "clog", "heel"],
        "base_cr": 1.7,
        "basket_multiplier": 1.25,
        "description": "Considered purchase, sizing checks, lower units per cart."
    },
    "Health, Fitness & Supplements": {
        "keywords": ["protein", "vitamin", "supplement", "gummy", "collagen", "powder", "workout", "nutrition", "gym", "creatine", "shaker", "energy"],
        "base_cr": 2.7,
        "basket_multiplier": 1.85,
        "description": "Repeat bundle buyers, high subscription intent."
    },
    "Jewelry & Luxury Goods": {
        "keywords": ["ring", "necklace", "earring", "bracelet", "gold", "silver", "jewelry", "diamond", "gemstone", "pendant", "eyewear", "glasses", "sunglasses", "watch"],
        "base_cr": 1.1,
        "basket_multiplier": 1.15,
        "description": "High ticket, high research cycle, single item focus."
    },
    "Electronics & Tech Accessories": {
        "keywords": ["charger", "cable", "case", "wireless", "headphone", "audio", "mount", "gadget", "powerbank", "usb", "screen", "keyboard"],
        "base_cr": 1.3,
        "basket_multiplier": 1.20,
        "description": "Utility purchase, single item focus."
    },
    "Food, Beverage & Grocery": {
        "keywords": ["tea", "coffee", "snack", "chocolate", "sauce", "drink", "beverage", "cookie", "food", "spices", "sweet", "candy"],
        "base_cr": 2.9,
        "basket_multiplier": 2.20,
        "description": "Fast consumption, bulk ordering, subscription packs."
    },
    "Home, Decor & Kitchen": {
        "keywords": ["candle", "pillow", "blanket", "vase", "mug", "decor", "lamp", "table", "cookware", "kitchen", "bedding", "towel", "furniture"],
        "base_cr": 1.6,
        "basket_multiplier": 1.40,
        "description": "Home design, gift items."
    }
}

class ShopifyIntelScraper:
    """
    Universal Multi-Platform E-Commerce Intelligence & Revenue Engine:
    - Shopify Stores
    - WordPress / WooCommerce E-Commerce Stores
    - Custom Coded / Headless E-Commerce (Next.js, React, Magento, BigCommerce, etc.)
    - Non-Commerce Filtering (Blogs, Portfolios, Wikipedia, Informational sites)
    """
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.cookies = {
            "cart_currency": "USD",
            "localization": "US"
        }

    def _get_session(self):
        s = requests.Session()
        s.cookies.set("cart_currency", "USD")
        s.cookies.set("localization", "US")
        return s

    def detect_platform_and_ecommerce(self, domain: str) -> Dict[str, Any]:
        """
        Deep multi-layer platform & e-commerce verification:
        Checks HTTP headers, DOM structure, platform scripts, Store APIs, and checkout signals.
        """
        urls_to_try = [f"https://{domain}", f"https://www.{domain}"]
        home_resp = None
        working_url = None
        session = self._get_session()

        for u in urls_to_try:
            try:
                resp = session.get(u, impersonate="chrome124", headers=self.headers, timeout=self.timeout, allow_redirects=True)
                if resp.status_code in [200, 301, 302, 403]:
                    home_resp = resp
                    parsed_work = urlparse(str(resp.url))
                    working_url = f"{parsed_work.scheme}://{parsed_work.netloc}"
                    break
            except Exception:
                continue

        if not home_resp:
            return {
                "is_ecommerce": False,
                "is_shopify": False,
                "reachable": False,
                "platform": "Unreachable",
                "platform_category": "non_ecommerce",
                "domain": domain,
                "message": f"Unable to reach website '{domain}'. Please verify the URL and try again.",
                "reason": "Host Unreachable / DNS failure"
            }

        html_text = home_resp.text
        headers = {k.lower(): v for k, v in home_resp.headers.items()}
        lower_html = html_text.lower()

        # 0. Check known corporate platforms / SaaS providers that are not retail merchant stores
        KNOWN_NON_COMMERCE_PLATFORMS = {
            "shopify.com", "automattic.com", "wordpress.org", "w3.org",
            "cloudflarestatus.com", "example.com", "bigcommerce.com", "magento.com"
        }
        if domain.lower() in KNOWN_NON_COMMERCE_PLATFORMS:
            return {
                "is_ecommerce": False,
                "is_shopify": False,
                "reachable": True,
                "platform": "Corporate Platform / Non-Retail",
                "platform_category": "non_ecommerce",
                "domain": domain,
                "working_url": working_url,
                "html": html_text,
                "message": f"Website '{domain}' is a corporate software platform / marketing portal without an active retail merchant catalog."
            }

        # 1. Shopify Detection
        shopify_headers = ["x-shopid", "x-shopify-stage", "x-shopify-renderer"]
        shopify_sigs = ["cdn.shopify.com", "shopify.shop", "window.shopify", "shopify-features", "myshopify.com", "shopify.theme", "collections/all"]
        matched_shopify = [sig for sig in shopify_sigs if sig in lower_html]
        products_json_valid = False
        try:
            p_resp = session.get(f"{working_url}/products.json?limit=1", impersonate="chrome124", headers=self.headers, timeout=5)
            if p_resp.status_code == 200 and "products" in p_resp.text:
                products_json_valid = True
        except Exception:
            pass

        is_shopify = products_json_valid or any(h in headers for h in shopify_headers) or len(matched_shopify) >= 1 or "cdn.shopify.com" in lower_html

        # 2. WordPress / WooCommerce Detection
        is_wordpress = ("wp-content/" in lower_html or "wp-includes/" in lower_html or "x-pingback" in headers)
        is_woocommerce = False
        wc_tech_sigs = ["plugins/woocommerce", "woocommerce-js", "class=\"woocommerce", "wc-block-grid", "wc-ajax=", "woocommerce/packages"]
        if any(sig in lower_html for sig in wc_tech_sigs):
            is_woocommerce = True

        if is_wordpress and not is_woocommerce:
            try:
                wc_chk = session.get(f"{working_url}/wp-json/wc/store/v1/products?per_page=1", impersonate="chrome124", headers=self.headers, timeout=4)
                if wc_chk.status_code == 200 and isinstance(wc_chk.json(), list):
                    is_woocommerce = True
            except Exception:
                pass

        # 3. Magento, BigCommerce, PrestaShop
        is_magento = bool(re.search(r'data-mage-init|/static/frontend/|/skin/frontend/|mage/cookies', lower_html))
        is_bigcommerce = bool("cdn11.bigcommerce.com" in lower_html or "bigcommerce.com" in lower_html)
        is_prestashop = "prestashop" in lower_html and ("themes/" in lower_html or "modules/" in lower_html)
        is_wix = "wixsite.com" in lower_html or "wix-warmup-data" in lower_html
        is_squarespace = "squarespace.com" in lower_html and "static1.squarespace.com" in lower_html

        # 4. Strict E-Commerce Verification Signals
        ecommerce_signals = []
        if is_shopify:
            ecommerce_signals.append("Shopify E-Commerce Engine")
        if is_woocommerce:
            ecommerce_signals.append("WooCommerce E-Commerce Engine")
        if is_magento:
            ecommerce_signals.append("Magento E-Commerce Engine")
        if is_bigcommerce:
            ecommerce_signals.append("BigCommerce E-Commerce Engine")
        if is_prestashop:
            ecommerce_signals.append("PrestaShop E-Commerce Engine")

        # Active Cart & Checkout Endpoints
        cart_matches = re.findall(r'href=[\'"][^\'"]*(?:/cart|/checkout|/basket|/bag|add-to-cart)[^\'"]*[\'"]', html_text, re.I)
        if cart_matches:
            ecommerce_signals.append("Cart / Checkout Endpoints Detected")

        # Add to cart buttons / action triggers
        if re.search(r'<(?:button|input|a)[^>]*(?:add[\s_-]*to[\s_-]*cart|buy[\s_-]*now|wc-block-cart|woocommerce-cart)', html_text, re.I):
            ecommerce_signals.append("Add to Cart / Buy Action Triggers")

        # Schema.org Product / Offer Microdata
        if any(term in html_text for term in ['"@type": "Product"', '"@type":"Product"', '"@type": "Offer"', '"@type":"Offer"', '"@type": "IndividualProduct"']):
            ecommerce_signals.append("Schema.org Product Microdata")

        # Classification Rule:
        # A website is classified as E-Commerce ONLY if it has an e-commerce engine, cart/checkout URL, add-to-cart action, or product schema.
        is_ecommerce = len(ecommerce_signals) >= 1

        # Platform Labeling & Category
        if is_shopify:
            platform = "Shopify"
            platform_category = "shopify"
        elif is_woocommerce:
            platform = "WordPress / WooCommerce"
            platform_category = "woocommerce"
        elif is_magento:
            platform = "Magento / Adobe Commerce"
            platform_category = "custom"
        elif is_bigcommerce:
            platform = "BigCommerce"
            platform_category = "custom"
        elif is_ecommerce:
            if "_next/" in html_text or "__NEXT_DATA__" in html_text:
                platform = "Next.js / Headless Custom E-Commerce"
            elif "react" in lower_html:
                platform = "React / Custom E-Commerce"
            elif "nuxt" in lower_html:
                platform = "Nuxt.js / Vue Custom E-Commerce"
            elif is_wix:
                platform = "Wix Stores"
            elif is_squarespace:
                platform = "Squarespace Commerce"
            else:
                platform = "Custom Coded E-Commerce"
            platform_category = "custom"
        else:
            if is_wordpress:
                platform = "WordPress (Non-Commerce / Blog)"
            else:
                platform = "Informational / Corporate Website (Non-Commerce)"
            platform_category = "non_ecommerce"

        return {
            "reachable": True,
            "domain": domain,
            "working_url": working_url,
            "html": html_text,
            "headers": headers,
            "is_ecommerce": is_ecommerce,
            "is_shopify": is_shopify,
            "is_woocommerce": is_woocommerce,
            "platform": platform,
            "platform_category": platform_category,
            "ecommerce_signals": ecommerce_signals,
            "products_endpoint_accessible": products_json_valid
        }

    def verify_shopify(self, domain: str) -> Dict[str, Any]:
        """Legacy helper maintained for backward compatibility."""
        res = self.detect_platform_and_ecommerce(domain)
        if not res.get("reachable"):
            return {
                "is_shopify": False,
                "reachable": False,
                "message": res.get("message", f"Unable to reach website '{domain}'."),
                "reason": "Host Unreachable / DNS failure"
            }
        return {
            "is_shopify": res.get("is_shopify", False),
            "reachable": True,
            "domain": domain,
            "working_url": res.get("working_url"),
            "detected_platform": res.get("platform"),
            "platform_category": res.get("platform_category"),
            "is_ecommerce": res.get("is_ecommerce"),
            "html": res.get("html"),
            "headers": res.get("headers"),
            "products_endpoint_accessible": res.get("products_endpoint_accessible", False),
            "message": f"Detected platform: {res.get('platform')}"
        }

    def extract_store_details(self, html_text: str, domain: str, working_url: str, platform_category: str = "shopify") -> Dict[str, Any]:
        """Universal metadata extraction (store name, theme, currency, apps/pixels, contact info, socials)."""
        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Store Name
        store_name = domain.split(".")[0].replace("-", " ").capitalize()
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            store_name = og_site["content"].strip()
        elif soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            parts = re.split(r"[-|–—:]", title_text)
            if len(parts) > 1:
                store_name = parts[-1].strip()
            else:
                store_name = title_text[:35]

        # 2. Myshopify domain (if Shopify)
        myshopify_domain = None
        ms_matches = re.findall(r"([a-zA-Z0-9\-]+\.myshopify\.com)", html_text)
        if ms_matches:
            filtered = [m for m in ms_matches if m not in ["account.myshopify.com", "cdn.myshopify.com", "help.myshopify.com"]]
            myshopify_domain = filtered[0] if filtered else ms_matches[0]

        # 3. Theme & Tech Stack Detection
        if platform_category == "shopify":
            theme_name = "Shopify Custom/Standard Theme"
            theme_match = re.search(r"Shopify\.theme\s*=\s*({[^}]+})", html_text)
            if theme_match:
                try:
                    name_match = re.search(r'\"name\"\s*:\s*\"([^\"]+)\"', theme_match.group(1))
                    if name_match:
                        theme_name = name_match.group(1)
                except Exception:
                    pass
            if theme_name == "Shopify Custom/Standard Theme":
                if "theme-dawn" in html_text or "Dawn" in html_text:
                    theme_name = "Dawn (Official Shopify)"
                elif "Prestige" in html_text:
                    theme_name = "Prestige"
                elif "Impulse" in html_text:
                    theme_name = "Impulse"
                elif "Motion" in html_text:
                    theme_name = "Motion"
        elif platform_category == "woocommerce":
            theme_name = "WordPress Theme (Custom / WooCommerce)"
            wp_theme_m = re.search(r'/wp-content/themes/([a-zA-Z0-9_-]+)/', html_text)
            if wp_theme_m:
                raw_t = wp_theme_m.group(1).replace("-", " ").capitalize()
                theme_name = f"{raw_t} (WooCommerce)"
        else:
            if "_next/" in html_text or "__NEXT_DATA__" in html_text:
                theme_name = "Next.js Headless Frontend"
            elif "react" in html_text.lower():
                theme_name = "React Custom Storefront"
            elif "nuxt" in html_text.lower():
                theme_name = "Nuxt.js / Vue Storefront"
            else:
                theme_name = "Custom Engineered Storefront"

        # 4. Currency
        currency = "USD"
        curr_match = re.search(r"\"currency\"\s*:\s*\"([A-Z]{3})\"", html_text)
        if curr_match:
            currency = curr_match.group(1)
        else:
            shop_curr = re.search(r"Shopify\.currency\s*=\s*{.*?\"active\"\s*:\s*\"([A-Z]{3})\"", html_text, re.DOTALL)
            if shop_curr:
                currency = shop_curr.group(1)
            elif "€" in html_text or "EUR" in html_text:
                currency = "EUR"
            elif "£" in html_text or "GBP" in html_text:
                currency = "GBP"
            elif "₹" in html_text or "INR" in html_text:
                currency = "INR"

        # 5. Tracking Pixels & Marketing Automation Apps
        apps = []
        fb_pixel = re.search(r"fbq\('init',\s*'(\d+)'\)", html_text)
        if fb_pixel or "connect.facebook.net" in html_text:
            apps.append({
                "name": "Meta / Facebook Pixel",
                "category": "Tracking & Attribution",
                "id": fb_pixel.group(1) if fb_pixel else "Active"
            })

        tt_pixel = re.search(r"ttq\.load\('([A-Z0-9]+)'\)", html_text)
        if tt_pixel or "analytics.tiktok.com" in html_text:
            apps.append({
                "name": "TikTok Pixel",
                "category": "Tracking & Attribution",
                "id": tt_pixel.group(1) if tt_pixel else "Active"
            })

        ga_match = re.search(r"(G-[A-Z0-9]{8,12})", html_text)
        if ga_match or "googletagmanager.com" in html_text or "google-analytics.com" in html_text:
            apps.append({
                "name": "Google Analytics (GA4 / GTM)",
                "category": "Tracking & Attribution",
                "id": ga_match.group(1) if ga_match else "Active"
            })

        if "_learnq" in html_text or "klaviyo.com" in html_text or "static.klaviyo.com" in html_text:
            apps.append({"name": "Klaviyo Email Automation", "category": "Marketing Automation", "id": "Detected"})
        elif "mailchimp" in html_text.lower():
            apps.append({"name": "Mailchimp Marketing", "category": "Marketing Automation", "id": "Detected"})

        if "judge.me" in html_text:
            apps.append({"name": "Judge.me Product Reviews", "category": "Social Commerce", "id": "Active"})
        elif "loox.io" in html_text:
            apps.append({"name": "Loox Photo Reviews", "category": "Social Commerce", "id": "Active"})
        elif "yotpo.com" in html_text:
            apps.append({"name": "Yotpo Reviews & Loyalty", "category": "Social Commerce", "id": "Active"})
        elif "stamped.io" in html_text:
            apps.append({"name": "Stamped.io Reviews", "category": "Social Commerce", "id": "Active"})
        elif "woocommerce-review" in html_text or "woocommerce-Reviews" in html_text:
            apps.append({"name": "WooCommerce Verified Reviews", "category": "Social Commerce", "id": "Active"})

        if "recharge" in html_text.lower():
            apps.append({"name": "Recharge Subscriptions", "category": "Subscriptions", "id": "Active"})

        if "gorgias.chat" in html_text:
            apps.append({"name": "Gorgias Helpdesk", "category": "Customer Support", "id": "Active"})
        elif "tidio.co" in html_text:
            apps.append({"name": "Tidio Live Chat", "category": "Customer Support", "id": "Active"})
        elif "intercom" in html_text:
            apps.append({"name": "Intercom Chat", "category": "Customer Support", "id": "Active"})
        elif "whatsapp" in html_text.lower():
            apps.append({"name": "WhatsApp Direct Support", "category": "Customer Support", "id": "Active"})

        if "hotjar.com" in html_text:
            apps.append({"name": "Hotjar Heatmaps", "category": "Behavior Analytics", "id": "Active"})
        elif "clarity.ms" in html_text:
            apps.append({"name": "Microsoft Clarity", "category": "Behavior Analytics", "id": "Active"})

        # 6. Contact Information
        emails = set()
        phones = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("mailto:"):
                clean_email = href.replace("mailto:", "").split("?")[0].strip()
                if "@" in clean_email and not clean_email.endswith((".png", ".jpg", ".webp")):
                    emails.add(clean_email)
            elif href.startswith("tel:"):
                clean_phone = href.replace("tel:", "").strip()
                if len(clean_phone) >= 7:
                    phones.add(clean_phone)

        text_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html_text)
        for e in text_emails:
            if not e.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".js", ".css")) and len(e) < 50:
                emails.add(e)

        socials = {}
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if "instagram.com/" in h and not socials.get("instagram"):
                socials["instagram"] = h
            elif "facebook.com/" in h and not socials.get("facebook"):
                socials["facebook"] = h
            elif "tiktok.com/" in h and not socials.get("tiktok"):
                socials["tiktok"] = h
            elif ("twitter.com/" in h or "x.com/" in h) and not socials.get("twitter"):
                socials["twitter"] = h
            elif "youtube.com/" in h and not socials.get("youtube"):
                socials["youtube"] = h
            elif "pinterest.com/" in h and not socials.get("pinterest"):
                socials["pinterest"] = h

        contact_email = list(emails)[0] if emails else ""

        return {
            "store_name": store_name,
            "myshopify_domain": myshopify_domain or f"{domain}.myshopify.com",
            "currency": currency,
            "theme": theme_name,
            "theme_name": theme_name,
            "apps": apps,
            "emails": list(emails)[:5],
            "phones": list(phones)[:3],
            "contact_email": contact_email,
            "socials": socials
        }

    def classify_niche(self, product_types: List[str], product_titles: List[str]) -> Dict[str, Any]:
        """Classifies the store into an e-commerce vertical to determine benchmark CR and basket size."""
        text_blob = " ".join(product_types + product_titles).lower()
        niche_scores = {}

        for niche_name, profile in NICHE_PROFILES.items():
            score = sum(text_blob.count(kw) for kw in profile["keywords"])
            niche_scores[niche_name] = score

        best_niche = max(niche_scores.items(), key=lambda x: x[1])
        if best_niche[1] >= 2:
            niche_name = best_niche[0]
            profile = NICHE_PROFILES[niche_name]
            return {
                "niche": niche_name,
                "base_cr": profile["base_cr"],
                "basket_multiplier": profile["basket_multiplier"],
                "description": profile["description"],
                "confidence": "High (Text Signature Matched)"
            }

        return {
            "niche": "General E-Commerce",
            "base_cr": 1.8,
            "basket_multiplier": 1.45,
            "description": "Diverse catalog, standard consumer retail basket.",
            "confidence": "Standard Baseline"
        }

    def _process_catalog_metrics(self, raw_products: List[Dict[str, Any]], domain: str, working_url: str, total_count: Optional[int] = None, currency: str = "USD") -> Dict[str, Any]:
        """
        Standardizes catalog pricing, Pareto 80/20 distribution, niche classification,
        and True Cart AOV across Shopify, WooCommerce, and Custom stores.
        """
        prices = []
        types = {}
        vendors = {}
        titles = []
        processed_products = []

        for p in raw_products:
            p_title = p.get("title", "")
            p_price = p.get("price")
            p_type = p.get("type") or p.get("product_type") or "General"
            p_vendor = p.get("vendor") or domain
            p_img = p.get("image") or p.get("image_url") or ""
            if p_img:
                p_img = str(p_img).strip()
                if p_img.startswith("//"):
                    p_img = "https:" + p_img
                elif p_img.startswith("/") and not p_img.startswith("//"):
                    p_img = working_url.rstrip("/") + p_img
                # Strip WordPress Photon CDN (i0.wp.com, i1.wp.com, etc.) so direct domain image is preferred
                p_img = re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", p_img)
            p_url = p.get("url") or working_url
            p_published = p.get("published_at")

            if p_price is not None and isinstance(p_price, (int, float)) and p_price > 0:
                prices.append(float(p_price))

            titles.append(p_title)
            types[p_type] = types.get(p_type, 0) + 1
            vendors[p_vendor] = vendors.get(p_vendor, 0) + 1

            processed_products.append({
                "title": p_title,
                "price": p_price,
                "product_type": p_type,
                "vendor": p_vendor,
                "published_at": p_published,
                "image_url": p_img,
                "variants_count": p.get("variants_count", 1),
                "url": p_url
            })

        if not prices:
            prices = [45.0]

        # Filter out placeholder/dummy staging prices (e.g. 999999, 99999) commonly set by Shopify merchants for unreleased products
        valid_prices = [pr for pr in prices if pr < 90000]
        if valid_prices:
            cat_med = statistics.median(valid_prices)
            if cat_med < 3000:
                filtered_prices = [pr for pr in valid_prices if pr <= 30 * cat_med]
                if filtered_prices:
                    prices = filtered_prices
            else:
                prices = valid_prices

        # Best sellers: first 10 items with valid commercial prices
        valid_processed = [p for p in processed_products if p.get("price") and p["price"] in prices]
        best_sellers = (valid_processed[:10] if valid_processed else processed_products[:10])
        best_seller_prices = [p["price"] for p in best_sellers if p.get("price")]

        # Mathematical Pricing Distribution
        raw_mean_price = round(statistics.mean(prices), 2)
        catalog_median_price = round(statistics.median(prices), 2)
        best_sellers_mean_price = round(statistics.mean(best_seller_prices), 2) if best_seller_prices else raw_mean_price
        min_price = round(min(prices), 2)
        max_price = round(max(prices), 2)

        # Pareto 80/20 Weighted Unit Price
        pareto_weighted_unit_price = round((0.70 * best_sellers_mean_price) + (0.30 * catalog_median_price), 2)

        # Classify Niche & Cart Multiplier
        niche_info = self.classify_niche(list(types.keys()), titles)
        basket_multiplier = niche_info["basket_multiplier"]

        # Automatic Currency Anomaly & High-Denomination FX Normalization
        # Prevents extreme inflations if Shopify Markets ever returns un-converted Asian currencies
        fx_rate = 1.0
        if catalog_median_price > 10000 and niche_info["niche"] not in ["Jewelry & Luxury Goods"]:
            fx_rate = 1.0 / 278.0  # Normalize PKR/JPY scale to USD
            currency = "USD"
        elif currency == "JPY" and catalog_median_price > 1000:
            fx_rate = 1.0 / 152.0  # Convert JPY to USD
            currency = "USD"
        elif currency == "INR" and catalog_median_price > 5000:
            fx_rate = 1.0 / 84.0   # Convert INR to USD
            currency = "USD"
        elif currency == "KRW" and catalog_median_price > 20000:
            fx_rate = 1.0 / 1380.0 # Convert KRW to USD
            currency = "USD"

        if fx_rate != 1.0:
            prices = [round(pr * fx_rate, 2) for pr in prices]
            for p in processed_products:
                if p.get("price"):
                    p["price"] = round(p["price"] * fx_rate, 2)
            raw_mean_price = round(statistics.mean(prices), 2)
            catalog_median_price = round(statistics.median(prices), 2)
            best_seller_prices = [p["price"] for p in best_sellers if p.get("price")]
            best_sellers_mean_price = round(statistics.mean(best_seller_prices), 2) if best_seller_prices else raw_mean_price
            min_price = round(min(prices), 2)
            max_price = round(max(prices), 2)
            pareto_weighted_unit_price = round((0.70 * best_sellers_mean_price) + (0.30 * catalog_median_price), 2)

        # True Cart AOV = Pareto Weighted Unit Price × Category Basket Size
        true_cart_aov = round(pareto_weighted_unit_price * basket_multiplier, 2)

        latest_products = sorted(
            [p for p in processed_products if p.get("published_at")],
            key=lambda x: str(x["published_at"]),
            reverse=True
        )[:8] if any(p.get("published_at") for p in processed_products) else processed_products[:8]

        total_found = total_count if (total_count and total_count > len(processed_products)) else len(processed_products)

        return {
            "total_products_found": total_found,
            "total_products_scraped": len(processed_products),
            "currency": currency,
            "niche_info": niche_info,
            "min_price": min_price,
            "max_price": max_price,
            "raw_mean_price": raw_mean_price,
            "catalog_median_price": catalog_median_price,
            "best_sellers_mean_price": best_sellers_mean_price,
            "pareto_weighted_unit_price": pareto_weighted_unit_price,
            "basket_multiplier": basket_multiplier,
            "true_cart_aov": true_cart_aov,
            "avg_price": true_cart_aov,  # Canonical AOV used across UI
            "top_categories": sorted(types.items(), key=lambda x: x[1], reverse=True)[:6],
            "top_vendors": sorted(vendors.items(), key=lambda x: x[1], reverse=True)[:5],
            "best_sellers": best_sellers,
            "latest_products": latest_products,
            "raw_products_sample": processed_products[:30]
        }

    def fetch_shopify_catalog(self, domain: str, working_url: str) -> Dict[str, Any]:
        """Deep catalog extraction for Shopify storefronts via /products.json."""
        session = self._get_session()
        products = []
        page = 1
        max_pages = 2

        try:
            while page <= max_pages:
                p_url = f"{working_url}/products.json?limit=250&page={page}"
                res = session.get(p_url, impersonate="chrome124", headers=self.headers, cookies=self.cookies, timeout=self.timeout)
                if res.status_code == 200:
                    data = res.json()
                    curr_batch = data.get("products", [])
                    if not curr_batch:
                        break
                    products.extend(curr_batch)
                    if len(curr_batch) < 250:
                        break
                    page += 1
                else:
                    break
        except Exception:
            pass

        # Identify best sellers from live best-selling collection
        best_selling_handles = []
        try:
            r_best = session.get(f"{working_url}/collections/all?sort_by=best-selling", impersonate="chrome124", headers=self.headers, timeout=8)
            if r_best.status_code == 200:
                soup = BeautifulSoup(r_best.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    if "/products/" in a["href"]:
                        h = a["href"].split("/products/")[-1].split("?")[0].split("#")[0].strip("/")
                        if h and h not in best_selling_handles:
                            best_selling_handles.append(h)
        except Exception:
            pass

        raw_items = []
        for p in products:
            variants = p.get("variants", [])
            price = None
            if variants:
                try:
                    price = float(variants[0].get("price", 0))
                except Exception:
                    pass
            images = p.get("images", [])
            img = images[0]["src"] if images else ""
            raw_items.append({
                "title": p.get("title", ""),
                "handle": p.get("handle", ""),
                "price": price,
                "type": p.get("product_type", "General") or "General",
                "vendor": p.get("vendor", domain),
                "published_at": p.get("published_at"),
                "image": img,
                "variants_count": len(variants),
                "url": f"{working_url}/products/{p.get('handle')}" if p.get("handle") else working_url
            })

        # Prioritize best-selling sort if handles found
        if best_selling_handles:
            handle_map = {item["handle"]: item for item in raw_items if item.get("handle")}
            sorted_items = []
            for h in best_selling_handles:
                if h in handle_map:
                    sorted_items.append(handle_map[h])
            for it in raw_items:
                if it.get("handle") not in best_selling_handles:
                    sorted_items.append(it)
            raw_items = sorted_items

        return self._process_catalog_metrics(raw_items, domain, working_url)

    def fetch_woocommerce_catalog(self, domain: str, working_url: str, html_text: str) -> Dict[str, Any]:
        """
        Deep catalog extraction for WordPress / WooCommerce stores:
        1. Queries WooCommerce Store Public REST API (/wp-json/wc/store/v1/products?per_page=100)
        2. Retrieves total catalog count via x-wp-total header
        3. Parses prices with minor unit conversions
        4. Fallback to /shop/ DOM product cards if REST API is disabled
        """
        session = self._get_session()
        raw_items = []
        total_catalog_count = 0
        currency = "USD"

        # Strategy 1: WooCommerce Store REST API
        try:
            api_url = f"{working_url}/wp-json/wc/store/v1/products?per_page=100"
            resp = session.get(api_url, impersonate="chrome124", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                raw_data = resp.json()
                if isinstance(raw_data, list) and len(raw_data) > 0:
                    header_total = resp.headers.get("x-wp-total")
                    if header_total and header_total.isdigit():
                        total_catalog_count = int(header_total)
                    else:
                        total_catalog_count = len(raw_data)

                    for p in raw_data:
                        p_name = html.unescape(p.get("name", "")).strip()
                        prices_obj = p.get("prices", {})
                        minor_unit = prices_obj.get("currency_minor_unit", 2)
                        raw_p = prices_obj.get("price") or prices_obj.get("regular_price") or "0"
                        currency = prices_obj.get("currency_code", currency)
                        try:
                            price_val = round(float(raw_p) / (10 ** minor_unit), 2)
                        except Exception:
                            price_val = 0.0

                        if p_name and price_val > 0:
                            cats = [c.get("name") for c in p.get("categories", []) if c.get("name")]
                            img = p.get("images", [{}])[0].get("src") if p.get("images") else ""
                            if img:
                                img = re.sub(r"^https?://i[0-9]\.wp\.com/", "https://", img)
                            raw_items.append({
                                "title": p_name,
                                "price": price_val,
                                "type": cats[0] if cats else "General",
                                "vendor": domain,
                                "image": img,
                                "url": p.get("permalink", f"{working_url}/product/{p.get('slug', '')}"),
                                "published_at": p.get("date_created")
                            })
        except Exception:
            pass

        # Strategy 2: If REST API had no items, check /shop/ and DOM product cards
        if not raw_items:
            shop_endpoints = [f"{working_url}/shop/", f"{working_url}/shop", f"{working_url}/store/", working_url]
            for s_url in shop_endpoints:
                try:
                    s_resp = session.get(s_url, impersonate="chrome124", headers=self.headers, timeout=8)
                    if s_resp.status_code == 200:
                        soup = BeautifulSoup(s_resp.text, "html.parser")
                        items = soup.select(".product, li.product, .wc-block-grid__product")
                        for it in items:
                            t_el = it.select_one(".woocommerce-loop-product__title, .wc-block-grid__product-title, h2, h3")
                            p_el = it.select_one(".woocommerce-Price-amount, .price")
                            if t_el and p_el:
                                title = t_el.get_text(strip=True)
                                p_text = p_el.get_text(strip=True).replace(",", "")
                                p_match = re.search(r"(\d+(?:\.\d{2})?)", p_text)
                                if p_match:
                                    price = float(p_match.group(1))
                                    if price > 0:
                                        img_el = it.select_one("img")
                                        a_el = it.select_one("a[href]")
                                        raw_items.append({
                                            "title": title,
                                            "price": price,
                                            "type": "General",
                                            "vendor": domain,
                                            "image": img_el.get("src", "") if img_el else "",
                                            "url": a_el.get("href", "") if a_el else working_url,
                                            "published_at": None
                                        })
                        if raw_items:
                            total_catalog_count = len(raw_items)
                            break
                except Exception:
                    continue

        return self._process_catalog_metrics(raw_items, domain, working_url, total_catalog_count, currency)

    def fetch_custom_catalog(self, domain: str, working_url: str, html_text: str) -> Dict[str, Any]:
        """
        Deep catalog extraction for Custom Coded & Headless E-Commerce storefronts:
        1. Parses Schema.org JSON-LD microdata (@type: Product, @type: Offer)
        2. Clives DOM hierarchy from price elements to find product titles and cards
        3. Queries catalog endpoints (/shop, /collections, /products) if homepage is limited
        """
        session = self._get_session()
        raw_items = []
        seen_titles = set()
        currency = "USD"

        pages_to_check = [(working_url, html_text)]

        # If homepage has limited HTML, check /shop or /collections
        soup_init = BeautifulSoup(html_text, "html.parser")
        has_schema = bool(soup_init.find_all("script", type="application/ld+json"))
        if not has_schema:
            for sub in ["/shop", "/collections", "/products", "/store"]:
                try:
                    sub_r = session.get(f"{working_url}{sub}", impersonate="chrome124", headers=self.headers, timeout=6)
                    if sub_r.status_code == 200:
                        pages_to_check.append((f"{working_url}{sub}", sub_r.text))
                        break
                except Exception:
                    pass

        for page_url, p_html in pages_to_check:
            soup = BeautifulSoup(p_html, "html.parser")

            # 1. Schema.org JSON-LD
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    txt = script.string or ""
                    if not txt.strip():
                        continue
                    data = json.loads(txt)
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        if "@graph" in data and isinstance(data["@graph"], list):
                            items = data["@graph"]
                        else:
                            items = [data]

                    for it in items:
                        t = it.get("@type")
                        if t in ["Product", "IndividualProduct", "ProductGroup"]:
                            p_name = html.unescape(it.get("name", "")).strip()
                            if not p_name or p_name.lower() in seen_titles:
                                continue

                            price = 0.0
                            curr = currency
                            offers = it.get("offers")
                            if isinstance(offers, dict):
                                curr = offers.get("priceCurrency", curr)
                                raw_p = offers.get("price") or offers.get("lowPrice") or 0.0
                                try:
                                    price = float(raw_p)
                                except Exception:
                                    pass
                            elif isinstance(offers, list) and offers:
                                curr = offers[0].get("priceCurrency", curr)
                                raw_p = offers[0].get("price") or offers[0].get("lowPrice") or 0.0
                                try:
                                    price = float(raw_p)
                                except Exception:
                                    pass

                            if p_name and price > 0:
                                seen_titles.add(p_name.lower())
                                currency = curr
                                img = it.get("image")
                                if isinstance(img, list) and img:
                                    img = img[0]
                                elif isinstance(img, dict):
                                    img = img.get("url", "")
                                raw_items.append({
                                    "title": p_name,
                                    "price": price,
                                    "type": it.get("category") or "General",
                                    "vendor": domain,
                                    "image": img or "",
                                    "url": it.get("url") or page_url,
                                    "published_at": None
                                })
                except Exception:
                    pass

            # 2. DOM Price Upward-Climbing Parser
            if len(raw_items) < 8:
                for el in soup.find_all(string=re.compile(r'(?:[\$€£₹]|USD|EUR|GBP)\s*\d+')):
                    txt = el.strip()
                    m = re.search(r'(?:[\$€£₹]|USD|EUR|GBP)\s*(\d+(?:\.\d{2})?)', txt)
                    if not m:
                        continue
                    try:
                        price = float(m.group(1))
                    except Exception:
                        continue
                    if price <= 0 or price > 20000:
                        continue

                    # Climb DOM to locate heading or title
                    curr_node = el.parent
                    title = None
                    card_container = None
                    for _ in range(6):
                        if curr_node is None or curr_node.name in ['body', 'html']:
                            break
                        headings = curr_node.find_all(['h2', 'h3', 'h4', 'h5', 'a', 'p'])
                        for h in headings:
                            ht = h.get_text(strip=True)
                            if ht and 3 < len(ht) < 65 and not re.search(r'^\s*[\$€£₹]\d+', ht) and ht.lower() not in ["shop now", "add to cart", "buy now", "learn more", "quick view"]:
                                title = ht
                                break
                        if title:
                            card_container = curr_node
                            break
                        curr_node = curr_node.parent

                    if title and title.lower() not in seen_titles:
                        seen_titles.add(title.lower())
                        img_node = card_container.find("img") if card_container else None
                        a_node = card_container.find("a", href=True) if card_container else None
                        raw_items.append({
                            "title": title,
                            "price": price,
                            "type": "General",
                            "vendor": domain,
                            "image": img_node.get("src", "") if img_node else "",
                            "url": a_node.get("href", "") if a_node else page_url,
                            "published_at": None
                        })

        return self._process_catalog_metrics(raw_items, domain, working_url, len(raw_items), currency)

    def fetch_advanced_catalog(self, domain: str, working_url: str) -> Dict[str, Any]:
        """Maintains backward compatibility by routing to Shopify catalog scraper."""
        return self.fetch_shopify_catalog(domain, working_url)

    def calculate_dynamic_conversion_rate(self, niche_info: Dict[str, Any], weighted_unit_price: float, apps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Dynamically calculates store-specific conversion rate:
        1. Category Baseline (e.g. Beauty 2.6%, Apparel 2.0%, Luxury 1.1%)
        2. Price Elasticity Modifier (< $25 gets +0.4%, > $120 gets -0.65%)
        3. Marketing Funnel & Retargeting Stack Modifier (Meta +0.25%, Klaviyo +0.30%, Reviews +0.25%)
        """
        base_cr = niche_info.get("base_cr", 1.8)

        # 1. Price Elasticity
        price_mod = 0.0
        if weighted_unit_price < 25.0:
            price_mod = 0.40  # impulse buy
        elif weighted_unit_price <= 60.0:
            price_mod = 0.00  # standard
        elif weighted_unit_price <= 120.0:
            price_mod = -0.30
        else:
            price_mod = -0.65  # high ticket, lower CR

        # 2. Marketing Stack Score
        app_names = [a.get("name", "") for a in apps]
        stack_mod = 0.0
        stack_breakdown = []

        if any("Meta" in n or "Facebook" in n for n in app_names):
            stack_mod += 0.25
            stack_breakdown.append("Meta Pixel (+0.25% - Active Paid Retargeting)")

        if any("TikTok" in n for n in app_names):
            stack_mod += 0.20
            stack_breakdown.append("TikTok Pixel (+0.20% - Social Traffic Funnel)")

        if any("Klaviyo" in n or "Mailchimp" in n for n in app_names):
            stack_mod += 0.30
            stack_breakdown.append("Klaviyo / Email (+0.30% - Abandoned Cart & Email Flows)")

        if any("Reviews" in n or "Judge.me" in n or "Loox" in n or "Yotpo" in n for n in app_names):
            stack_mod += 0.25
            stack_breakdown.append("Social Proof Reviews (+0.25% - Conversion Trust)")

        if any("Helpdesk" in n or "Gorgias" in n or "Tidio" in n or "Support" in n for n in app_names):
            stack_mod += 0.10
            stack_breakdown.append("Live Chat Support (+0.10% - Pre-sale Assurance)")

        raw_dynamic_cr = round(base_cr + price_mod + stack_mod, 2)
        # Realistic bounds (0.8% to 4.5%)
        final_expected_cr = max(0.8, min(4.5, raw_dynamic_cr))

        return {
            "base_cr": base_cr,
            "price_modifier": round(price_mod, 2),
            "stack_modifier": round(stack_mod, 2),
            "stack_breakdown": stack_breakdown,
            "dynamic_expected_cr": final_expected_cr
        }

    def estimate_traffic_and_revenue(self, domain: str, catalog_stats: Dict[str, Any], apps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Triangulates Traffic and synthesizes Dynamic Revenue:
        - Traffic from Tranco Global Rank with calibrated power-law model.
        - True Cart AOV (Pareto weighted unit price × category basket multiplier).
        - Dynamic Store-Specific Conversion Rate.
        """
        session = self._get_session()
        tranco_rank = None
        monthly_visitors = None
        confidence = "Standard Estimate"
        rank_source = "E-Commerce Catalog Tiering"
        aov = catalog_stats["true_cart_aov"]
        weighted_unit_price = catalog_stats["pareto_weighted_unit_price"]
        niche_info = catalog_stats["niche_info"]
        total_products = catalog_stats.get("total_products_found") or catalog_stats.get("total_products_scraped", 10)

        # 1. Fetch Global Rank from Tranco API
        try:
            r = session.get(f"https://tranco-list.eu/api/ranks/domain/{domain}", timeout=6)
            if r.status_code == 200:
                data = r.json()
                ranks = data.get("ranks", [])
                if ranks and ranks[0].get("rank"):
                    tranco_rank = ranks[0]["rank"]
                    rank_source = f"Tranco Global Rank #{tranco_rank:,}"
                    confidence = "High (Verified Web Traffic Rank)"

                    # Calibrated Zipf power law traffic model
                    K = 4.2e10
                    beta = 0.92
                    power_visitors = int(K / (tranco_rank**beta))

                    # Ad scaling: If store has Meta + TikTok pixels, they actively acquire paid traffic
                    has_paid_ads = any("Pixel" in a.get("name", "") for a in apps)
                    ad_multiplier = 1.15 if has_paid_ads else 1.0

                    monthly_visitors = int(max(10000, min(30000000, power_visitors * ad_multiplier)))
        except Exception:
            pass

        # Fallback if unranked in top 1M
        if not monthly_visitors:
            if total_products <= 20:
                monthly_visitors = 14000
                confidence = "Boutique Scale Estimate"
            elif total_products <= 80:
                monthly_visitors = 32000
                confidence = "Growing Brand Estimate"
            elif total_products <= 250:
                monthly_visitors = 75000
                confidence = "Established Brand Estimate"
            else:
                monthly_visitors = 160000
                confidence = "Enterprise Catalog Estimate"

        # 2. Dynamic Conversion Rate Breakdown
        cr_intel = self.calculate_dynamic_conversion_rate(niche_info, weighted_unit_price, apps)
        expected_cr = cr_intel["dynamic_expected_cr"]
        conservative_cr = round(max(0.7, expected_cr - 0.9), 2)
        aggressive_cr = round(min(5.2, expected_cr + 1.1), 2)

        # 3. Revenue Scenarios
        orders_conservative = int(monthly_visitors * (conservative_cr / 100.0))
        orders_expected = int(monthly_visitors * (expected_cr / 100.0))
        orders_aggressive = int(monthly_visitors * (aggressive_cr / 100.0))

        rev_conservative = round(orders_conservative * aov, 2)
        rev_expected = round(orders_expected * aov, 2)
        rev_aggressive = round(orders_aggressive * aov, 2)

        daily_expected = round(rev_expected / 30, 2)
        annual_expected = round(rev_expected * 12, 2)

        return {
            "tranco_rank": tranco_rank,
            "rank_source": rank_source,
            "confidence": confidence,
            "monthly_visitors": monthly_visitors,
            "aov": aov,
            "cr_intelligence": cr_intel,
            "scenarios": {
                "conservative": {
                    "conversion_rate_pct": conservative_cr,
                    "monthly_orders": orders_conservative,
                    "monthly_revenue": rev_conservative
                },
                "expected": {
                    "conversion_rate_pct": expected_cr,
                    "monthly_orders": orders_expected,
                    "monthly_revenue": rev_expected,
                    "daily_revenue": daily_expected,
                    "annual_run_rate": annual_expected
                },
                "aggressive": {
                    "conversion_rate_pct": aggressive_cr,
                    "monthly_orders": orders_aggressive,
                    "monthly_revenue": rev_aggressive
                }
            },
            "formula_explanation": (
                f"Revenue = {monthly_visitors:,} Monthly Visitors × {expected_cr}% Dynamic CR × ${aov:,.2f} True Cart AOV"
            )
        }

    def analyze_store(self, user_input: str) -> Dict[str, Any]:
        """
        Universal End-to-End Analysis Orchestration:
        1. Classifies platform & verifies e-commerce status
        2. Filters out non-commerce / informational sites cleanly
        3. Scrapes deep catalog (Shopify, WooCommerce, or Custom)
        4. Extracts pixels, apps, themes, and contacts
        5. Synthesizes Dynamic CR, Tranco traffic, and multi-tier revenue projections
        """
        domain = normalize_domain(user_input)
        if not domain or len(domain) < 3:
            return {"success": False, "message": "Please enter a valid store domain or website URL."}

        # Step 1: Multi-platform & E-Commerce verification
        verification = self.detect_platform_and_ecommerce(domain)
        if not verification.get("reachable"):
            return {
                "success": False,
                "domain": domain,
                "reachable": False,
                "is_ecommerce": False,
                "is_shopify": False,
                "platform": "Unreachable",
                "platform_category": "non_ecommerce",
                "message": verification.get("message", f"Unable to reach website '{domain}'.")
            }

        is_ecommerce = verification.get("is_ecommerce", False)
        platform = verification.get("platform", "Unknown")
        platform_category = verification.get("platform_category", "non_ecommerce")
        working_url = verification["working_url"]
        html_text = verification["html"]

        # Step 2: Clean Non-Commerce Filtering
        if not is_ecommerce:
            return {
                "success": True,
                "is_ecommerce": False,
                "is_shopify": False,
                "domain": domain,
                "working_url": working_url,
                "platform": platform,
                "platform_category": "non_ecommerce",
                "message": f"Website '{domain}' is an informational site ({platform}). No active e-commerce cart, checkout, or product catalog was detected."
            }

        # Step 3: Extract Metadata, Pixels, and Stack
        meta = self.extract_store_details(html_text, domain, working_url, platform_category)

        # Step 4: Platform-Specific Deep Catalog Extraction
        if platform_category == "shopify":
            catalog = self.fetch_shopify_catalog(domain, working_url)
        elif platform_category == "woocommerce":
            catalog = self.fetch_woocommerce_catalog(domain, working_url, html_text)
        else:
            catalog = self.fetch_custom_catalog(domain, working_url, html_text)

        # Step 5: Triangulate Traffic & Dynamic Revenue
        revenue_intel = self.estimate_traffic_and_revenue(domain, catalog, meta["apps"])

        return {
            "success": True,
            "is_ecommerce": True,
            "is_shopify": (platform_category == "shopify"),
            "is_woocommerce": (platform_category == "woocommerce"),
            "platform": platform,
            "platform_category": platform_category,
            "domain": domain,
            "working_url": working_url,
            "store_info": meta,
            "catalog": catalog,
            "revenue": revenue_intel
        }
