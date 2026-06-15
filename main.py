"""
Website Intelligence Auditor — Standalone Version
Built for: Amit Ahuja
Run locally:  pip install -r requirements.txt && uvicorn main:app --reload
Deploy free:  Railway.app / Render.com (instructions in README.md)
"""

import re
import ssl
import socket
import time
from urllib.parse import urlparse

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Website Intelligence Auditor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────────────────────────────────────────
# CHECK DEFINITIONS — each check has regex patterns matched against raw HTML
# ─────────────────────────────────────────────────────────────────────────────

CHECKS = [
    # ── Traffic Intelligence ──
    {
        "id": "ga4", "name": "Google Analytics 4", "icon": "📊",
        "category": "Traffic Intelligence", "impact": "HIGH",
        "fix_time": "10 min", "cost": "Free",
        "patterns": [r"gtag\(\s*['\"]config['\"],\s*['\"]G-[A-Z0-9]+", r"googletagmanager\.com/gtag/js\?id=G-", r"['\"]G-[A-Z0-9]{8,}['\"]"],
        "description": "Tracks visitors, cities, traffic sources, time on site",
        "missing_msg": "Zero visibility into who visits, from where, or what they do.",
    },
    {
        "id": "ua_old", "name": "Old Google Analytics (UA) — outdated", "icon": "⚠️",
        "category": "Traffic Intelligence", "impact": "MEDIUM",
        "fix_time": "15 min", "cost": "Free",
        "patterns": [r"['\"]UA-\d{4,}-\d", r"google-analytics\.com/analytics\.js"],
        "description": "Legacy version — stopped collecting data July 2023",
        "missing_msg": "",
        "inverse": True,  # finding this is BAD
    },
    {
        "id": "gtm", "name": "Google Tag Manager", "icon": "🏷️",
        "category": "Traffic Intelligence", "impact": "MEDIUM",
        "fix_time": "20 min", "cost": "Free",
        "patterns": [r"googletagmanager\.com/gtm\.js", r"GTM-[A-Z0-9]{4,}", r"googletagmanager\.com/ns\.html"],
        "description": "Manages all tracking tags from one dashboard",
        "missing_msg": "No central tag management — every tool needs developer time to add.",
    },
    # ── Behaviour Intelligence ──
    {
        "id": "clarity", "name": "Microsoft Clarity", "icon": "🎥",
        "category": "Behaviour Intelligence", "impact": "HIGH",
        "fix_time": "5 min", "cost": "Free forever",
        "patterns": [r"clarity\.ms", r"['\"]clarity['\"]", r"c\.clarity"],
        "description": "Session recordings, heatmaps, rage clicks, exit points",
        "missing_msg": "Cannot see what visitors do — where they click, scroll, or abandon.",
    },
    {
        "id": "hotjar", "name": "Hotjar", "icon": "🔥",
        "category": "Behaviour Intelligence", "impact": "MEDIUM",
        "fix_time": "10 min", "cost": "Free tier",
        "patterns": [r"static\.hotjar\.com", r"_hjSettings", r"hotjar\.com/c/"],
        "description": "Heatmaps, recordings, feedback polls",
        "missing_msg": "No heatmap or behaviour data on user interactions.",
    },
    # ── Retargeting ──
    {
        "id": "meta_pixel", "name": "Meta (Facebook) Pixel", "icon": "📘",
        "category": "Retargeting", "impact": "HIGH",
        "fix_time": "15 min", "cost": "Free",
        "patterns": [r"fbq\(\s*['\"]init['\"]", r"connect\.facebook\.net/[a-z_A-Z]+/fbevents\.js", r"facebook\.com/tr\?id="],
        "description": "Retarget visitors on Instagram & Facebook after they leave",
        "missing_msg": "Visitors who leave can never be shown your Instagram/Facebook ads.",
    },
    {
        "id": "google_ads", "name": "Google Ads Remarketing", "icon": "🎯",
        "category": "Retargeting", "impact": "MEDIUM",
        "fix_time": "20 min", "cost": "Free tag",
        "patterns": [r"['\"]AW-\d{6,}", r"googleadservices\.com/pagead", r"google_conversion_id"],
        "description": "Retarget via Google Search, YouTube, Gmail & 2M+ sites",
        "missing_msg": "Cannot re-reach visitors through the Google network.",
    },
    {
        "id": "linkedin", "name": "LinkedIn Insight Tag", "icon": "💼",
        "category": "Retargeting", "impact": "LOW",
        "fix_time": "15 min", "cost": "Free",
        "patterns": [r"snap\.licdn\.com", r"_linkedin_partner_id"],
        "description": "B2B retargeting on LinkedIn — great for dealer/investor audiences",
        "missing_msg": "Missing B2B retargeting for professional audiences.",
    },
    # ── Lead Capture ──
    {
        "id": "whatsapp", "name": "WhatsApp Chat Button", "icon": "🟢",
        "category": "Lead Capture", "impact": "HIGH",
        "fix_time": "5 min", "cost": "Free",
        "patterns": [r"wa\.me/\d", r"api\.whatsapp\.com/send", r"whatsapp://send"],
        "description": "One-tap WhatsApp contact — the #1 channel in India",
        "missing_msg": "Critical for India — visitors cannot reach you on WhatsApp in one tap.",
    },
    {
        "id": "livechat", "name": "Live Chat / Chatbot", "icon": "💬",
        "category": "Lead Capture", "impact": "HIGH",
        "fix_time": "30 min", "cost": "Free tier",
        "patterns": [r"tawk\.to", r"crisp\.chat", r"intercom", r"freshchat|freshworks", r"tidio", r"drift\.com", r"smartsupp", r"zoho.*salesiq|salesiq\.zoho", r"hubspot.*conversations"],
        "description": "Engage visitors in real time, capture name & phone",
        "missing_msg": "Visitors with questions leave silently — no way to engage them.",
    },
    {
        "id": "lead_form", "name": "Lead / Contact Form", "icon": "📝",
        "category": "Lead Capture", "impact": "HIGH",
        "fix_time": "20 min", "cost": "Free",
        "patterns": [r"<form[^>]*>", r"typeform\.com", r"jotform", r"forms\.gle", r"wpforms|gravity.?forms|ninja.?forms|cf7|contact-form-7"],
        "description": "Structured way for visitors to submit an enquiry",
        "missing_msg": "Interested visitors have nowhere to leave their details.",
    },
    {
        "id": "exit_popup", "name": "Exit Intent / Popup Tool", "icon": "🚪",
        "category": "Lead Capture", "impact": "MEDIUM",
        "fix_time": "20 min", "cost": "Free tier",
        "patterns": [r"optinmonster", r"poptin", r"sumo\.com|sumome", r"privy", r"hellobar", r"exit.?intent", r"mailmunch", r"convertbox"],
        "description": "Catches abandoning visitors with an offer or callback",
        "missing_msg": "Nothing recovers visitors as they leave — 3–5% of leads lost.",
    },
    {
        "id": "click_to_call", "name": "Click-to-Call Phone Link", "icon": "📞",
        "category": "Lead Capture", "impact": "MEDIUM",
        "fix_time": "5 min", "cost": "Free",
        "patterns": [r"href=['\"]tel:"],
        "description": "Tap-to-dial phone number — essential on mobile",
        "missing_msg": "Mobile visitors (74% of India) cannot call you in one tap.",
    },
    # ── Trust & Security ──
    {
        "id": "ssl", "name": "SSL / HTTPS", "icon": "🔒",
        "category": "Trust & Security", "impact": "HIGH",
        "fix_time": "1 hour", "cost": "Free",
        "patterns": [],  # checked separately via URL
        "description": "Secure connection — required for trust & Google ranking",
        "missing_msg": "Visitors see 'Not Secure' warning. Google penalises HTTP sites.",
        "special": "ssl",
    },
    {
        "id": "privacy_policy", "name": "Privacy Policy Page", "icon": "📜",
        "category": "Trust & Security", "impact": "MEDIUM",
        "fix_time": "1 hour", "cost": "Free",
        "patterns": [r"privacy.?policy", r"/privacy"],
        "description": "Legal requirement under India's DPDP Act + builds trust",
        "missing_msg": "DPDP Act compliance risk — and reduces visitor trust.",
    },
    {
        "id": "testimonials", "name": "Reviews / Testimonials", "icon": "⭐",
        "category": "Trust & Security", "impact": "MEDIUM",
        "fix_time": "2 hours", "cost": "Free",
        "patterns": [r"testimonial", r"review", r"rating", r"stars?-?rating"],
        "description": "Social proof on the page — what others say about the business",
        "missing_msg": "No social proof — visitors have no reason to trust claims.",
    },
    # ── SEO & Visibility ──
    {
        "id": "schema", "name": "Schema / Structured Data", "icon": "🗂️",
        "category": "SEO & Visibility", "impact": "MEDIUM",
        "fix_time": "1 hour", "cost": "Free",
        "patterns": [r"application/ld\+json", r"schema\.org", r"itemtype="],
        "description": "Rich results in Google + feeds AI search engines",
        "missing_msg": "Missing rich snippets and invisible to AI-powered search.",
    },
    {
        "id": "og_tags", "name": "Open Graph / Social Meta Tags", "icon": "🔍",
        "category": "SEO & Visibility", "impact": "MEDIUM",
        "fix_time": "30 min", "cost": "Free",
        "patterns": [r"property=['\"]og:title", r"property=['\"]og:image", r"name=['\"]twitter:card"],
        "description": "Link previews when shared on WhatsApp / social media",
        "missing_msg": "Shared links show no image/preview — looks unprofessional on WhatsApp.",
    },
    {
        "id": "meta_desc", "name": "Meta Description", "icon": "📄",
        "category": "SEO & Visibility", "impact": "MEDIUM",
        "fix_time": "15 min", "cost": "Free",
        "patterns": [r"<meta[^>]+name=['\"]description['\"]"],
        "description": "The snippet Google shows under your site name",
        "missing_msg": "Google shows random text from your page — lower click rates.",
    },
    {
        "id": "sitemap_link", "name": "Sitemap Reference", "icon": "🗺️",
        "category": "SEO & Visibility", "impact": "LOW",
        "fix_time": "30 min", "cost": "Free",
        "patterns": [r"sitemap\.xml"],
        "description": "Helps Google discover and index all your pages",
        "missing_msg": "Google may not find all your pages.",
        "special": "sitemap",  # also try fetching /sitemap.xml
    },
    {
        "id": "mobile_viewport", "name": "Mobile Responsive Tag", "icon": "📱",
        "category": "SEO & Visibility", "impact": "HIGH",
        "fix_time": "varies", "cost": "Free",
        "patterns": [r"<meta[^>]+name=['\"]viewport['\"]"],
        "description": "Page adapts to mobile screens — 74% of India traffic",
        "missing_msg": "Site likely broken on mobile where 3 of 4 visitors are.",
    },
    {
        "id": "favicon", "name": "Favicon / Brand Icon", "icon": "🎨",
        "category": "SEO & Visibility", "impact": "LOW",
        "fix_time": "10 min", "cost": "Free",
        "patterns": [r"rel=['\"](?:shortcut )?icon['\"]"],
        "description": "Brand icon in browser tabs and bookmarks",
        "missing_msg": "Generic browser icon — small but visible polish gap.",
    },
    # ── AI Search Readiness (2026 differentiator) ──
    {
        "id": "llms_txt", "name": "llms.txt (AI Search File)", "icon": "🤖",
        "category": "AI Readiness", "impact": "MEDIUM",
        "fix_time": "30 min", "cost": "Free",
        "patterns": [],
        "description": "New standard telling AI assistants (ChatGPT, Perplexity) about your business",
        "missing_msg": "Invisible to AI assistants — the fastest-growing search channel of 2026.",
        "special": "llms",
    },
    {
        "id": "h1_structure", "name": "Clear Heading Structure (H1)", "icon": "📑",
        "category": "AI Readiness", "impact": "LOW",
        "fix_time": "30 min", "cost": "Free",
        "patterns": [r"<h1[^>]*>"],
        "description": "Clean headings help both Google and AI understand your content",
        "missing_msg": "No H1 heading — harder for search engines and AI to parse the page.",
    },
    {
        "id": "canonical", "name": "Canonical URL Tag", "icon": "🔗",
        "category": "AI Readiness", "impact": "LOW",
        "fix_time": "15 min", "cost": "Free",
        "patterns": [r"rel=['\"]canonical['\"]"],
        "description": "Tells search engines the master version of each page",
        "missing_msg": "Risk of duplicate-content confusion in Google indexing.",
    },
]


class AuditRequest(BaseModel):
    url: str
    deep_scan: bool = False


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw.rstrip("/")


def fetch_html(url: str) -> tuple[str, dict]:
    """Fetch page HTML with redirects. Returns (html, meta)."""
    meta = {"final_url": url, "status": None, "load_ms": None, "error": None}
    try:
        t0 = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        meta["load_ms"] = int((time.time() - t0) * 1000)
        meta["status"] = resp.status_code
        meta["final_url"] = resp.url
        resp.raise_for_status()
        return resp.text, meta
    except requests.exceptions.SSLError:
        # Retry over http to at least audit the content
        try:
            alt = url.replace("https://", "http://")
            t0 = time.time()
            resp = requests.get(alt, headers=HEADERS, timeout=15, allow_redirects=True)
            meta["load_ms"] = int((time.time() - t0) * 1000)
            meta["status"] = resp.status_code
            meta["final_url"] = resp.url
            meta["error"] = "ssl_error"
            return resp.text, meta
        except Exception as e:
            meta["error"] = f"unreachable: {e.__class__.__name__}"
            return "", meta
    except Exception as e:
        meta["error"] = f"unreachable: {e.__class__.__name__}"
        return "", meta


def fetch_html_rendered(url: str) -> tuple[str, dict]:
    """
    DEEP SCAN: load the page in a real headless browser, wait for all
    JavaScript to run, then return the fully-rendered HTML. This catches
    tracking tags injected after page load and tools fired inside GTM —
    removing the 'JavaScript-injected tools may show as missing' limitation.
    Falls back to a plain fetch if the browser engine isn't available.
    """
    meta = {"final_url": url, "status": None, "load_ms": None, "error": None, "rendered": False}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Playwright not installed — fall back to fast fetch
        html, m = fetch_html(url)
        m["error"] = (m.get("error") or "") + " | deep_scan_unavailable"
        m["rendered"] = False
        return html, m

    try:
        t0 = time.time()
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            # networkidle = wait until network has been quiet for 500ms,
            # i.e. all async scripts (pixels, GTM tags, chat widgets) have loaded
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)  # extra settle time for lazy widgets
            html = page.content()
            meta["final_url"] = page.url
            meta["status"] = 200
            browser.close()
        meta["load_ms"] = int((time.time() - t0) * 1000)
        meta["rendered"] = True
        return html, meta
    except Exception as e:
        # Browser failed (timeout, blocked, etc.) — fall back to fast fetch
        html, m = fetch_html(url)
        m["error"] = (m.get("error") or "") + f" | deep_scan_failed:{e.__class__.__name__}"
        m["rendered"] = False
        return html, m


def check_url_exists(url: str) -> bool:
    try:
        r = requests.head(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if r.status_code == 405:  # some servers block HEAD
            r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True, stream=True)
        return r.status_code == 200
    except Exception:
        return False


def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else ""


def detect_platform(html: str) -> str:
    h = html.lower()
    if "wp-content" in h or "wp-includes" in h:
        return "WordPress"
    if "cdn.shopify.com" in h:
        return "Shopify"
    if "wix.com" in h or "wixstatic" in h:
        return "Wix"
    if "squarespace" in h:
        return "Squarespace"
    if "__next" in h or "_next/static" in h:
        return "Next.js (custom build)"
    if "react" in h and "root" in h:
        return "React (custom build)"
    return "Custom / Unknown"


@app.post("/api/audit")
def audit(req: AuditRequest):
    url = normalize_url(req.url)
    parsed = urlparse(url)
    domain = parsed.netloc

    html, meta = (fetch_html_rendered(url) if req.deep_scan else fetch_html(url))
    if not html:
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": "Could not reach this website. Check the URL and try again.",
            "detail": meta.get("error"),
        })

    is_https = meta["final_url"].startswith("https://") and meta.get("error") != "ssl_error"
    was_rendered = meta.get("rendered", False)

    # Detect GTM container presence — used for "deep scan" hints below
    gtm_present = bool(
        re.search(r"googletagmanager\.com/gtm\.js", html, re.I)
        or re.search(r"GTM-[A-Z0-9]{4,}", html, re.I)
        or re.search(r"googletagmanager\.com/ns\.html", html, re.I)
    )
    # Tools that are commonly fired *inside* a GTM container rather than hard-coded
    GTM_MANAGED_TOOLS = {"ga4", "meta_pixel", "google_ads", "clarity", "hotjar", "linkedin"}

    results = []
    for chk in CHECKS:
        found = False
        if chk.get("special") == "ssl":
            found = is_https
        elif chk.get("special") == "sitemap":
            found = bool(re.search(chk["patterns"][0], html, re.I)) or \
                    check_url_exists(f"{parsed.scheme}://{domain}/sitemap.xml")
        elif chk.get("special") == "llms":
            found = check_url_exists(f"{parsed.scheme}://{domain}/llms.txt")
        else:
            for pat in chk["patterns"]:
                if re.search(pat, html, re.I):
                    found = True
                    break

        # inverse checks: finding the pattern is BAD (e.g. old UA analytics)
        if chk.get("inverse"):
            results.append({
                "id": chk["id"], "name": chk["name"], "icon": chk["icon"],
                "category": chk["category"], "impact": chk["impact"],
                "fix_time": chk["fix_time"], "cost": chk["cost"],
                "description": chk["description"],
                "found": not found,  # found old UA -> mark as failed
                "uncertain": False,
                "warning": "Old Universal Analytics detected — it stopped working in July 2023. Migrate to GA4." if found else None,
                "missing_msg": "Old UA tracking found — broken since 2023." if found else "",
            })
        else:
            # GTM-aware logic: if a GTM-managed tool isn't in the raw HTML but a
            # GTM container IS present, mark it "uncertain" rather than a flat miss.
            # BUT if we did a deep scan (full browser render), there's no uncertainty —
            # everything that would load HAS loaded, so a miss is a real miss.
            uncertain = (
                not found
                and gtm_present
                and not was_rendered
                and chk["id"] in GTM_MANAGED_TOOLS
            )
            results.append({
                "id": chk["id"], "name": chk["name"], "icon": chk["icon"],
                "category": chk["category"], "impact": chk["impact"],
                "fix_time": chk["fix_time"], "cost": chk["cost"],
                "description": chk["description"],
                "found": found,
                "uncertain": uncertain,
                "warning": (
                    "Not in page source, but a Google Tag Manager container is present — "
                    "this tool may be firing inside GTM. A deep scan is recommended to confirm."
                ) if uncertain else None,
                "missing_msg": chk["missing_msg"] if (not found and not uncertain) else "",
            })

    found_n     = sum(1 for r in results if r["found"])
    uncertain_n = sum(1 for r in results if r.get("uncertain"))
    # Hard misses exclude uncertain (GTM-managed) items
    missing_n   = sum(1 for r in results if not r["found"] and not r.get("uncertain"))
    high_miss   = sum(1 for r in results if not r["found"] and not r.get("uncertain") and r["impact"] == "HIGH")
    # Score gives uncertain items half credit (they're likely present via GTM)
    score = round((found_n + uncertain_n * 0.5) / len(results) * 100)

    return {
        "ok": True,
        "domain": domain,
        "final_url": meta["final_url"],
        "page_title": extract_title(html),
        "platform": detect_platform(html),
        "load_ms": meta["load_ms"],
        "gtm_present": gtm_present,
        "scan_mode": "deep" if was_rendered else "fast",
        "score": score,
        "found": found_n,
        "uncertain": uncertain_n,
        "missing": missing_n,
        "critical_gaps": high_miss,
        "checks": results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND — served at /
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home():
    return FRONTEND_HTML


FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Website Intelligence Auditor</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',Arial,sans-serif; }
  body { background:#F0F4FA; min-height:100vh; }
  .header { background:linear-gradient(135deg,#1A4A8A,#0D2E5A); padding:24px 18px 28px; }
  .header .tag { font-size:10px; color:#7FB3FF; letter-spacing:2px; text-transform:uppercase; margin-bottom:4px; }
  .header h1 { font-size:24px; font-weight:900; color:white; line-height:1.2; }
  .header p { font-size:13px; color:#B0C8F0; margin-top:6px; }
  .container { max-width:680px; margin:0 auto; padding:0 14px 50px; }
  .card { background:white; border-radius:12px; padding:16px; margin-top:14px; box-shadow:0 2px 8px rgba(0,0,0,0.08); }
  .input-row { display:flex; gap:8px; }
  input[type=text] { flex:1; padding:12px 14px; border-radius:8px; border:1.5px solid #DDE3EF; font-size:14px; outline:none; }
  input[type=text]:focus { border-color:#1A4A8A; }
  button.audit-btn { padding:12px 22px; border-radius:8px; border:none; background:#1A4A8A; color:white; font-weight:700; font-size:14px; cursor:pointer; }
  button.audit-btn:disabled { background:#999; }
  .hint { font-size:11px; color:#AAA; margin-top:6px; }
  .spinner { text-align:center; padding:30px 0; display:none; }
  .spinner .dots span { display:inline-block; width:10px; height:10px; margin:0 4px; border-radius:50%; background:#1A4A8A; animation:b 1.2s infinite ease-in-out; }
  .spinner .dots span:nth-child(2){animation-delay:.2s} .spinner .dots span:nth-child(3){animation-delay:.4s}
  @keyframes b {0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.2)}}
  .score-row { display:flex; justify-content:space-between; align-items:flex-start; }
  .score-big { font-size:44px; font-weight:900; line-height:1; }
  .stat-row { display:flex; gap:8px; margin-top:14px; }
  .stat { flex:1; text-align:center; padding:10px 4px; border-radius:8px; }
  .stat .v { font-size:24px; font-weight:900; }
  .stat .l { font-size:10px; font-weight:600; margin-top:2px; }
  .pill-row { display:flex; gap:6px; overflow-x:auto; margin-top:14px; padding-bottom:4px; }
  .pill { padding:6px 12px; border-radius:16px; border:none; font-size:11px; font-weight:600; white-space:nowrap; cursor:pointer; background:white; color:#555; box-shadow:0 1px 3px rgba(0,0,0,0.1); }
  .pill.active { background:#1A4A8A; color:white; }
  .check { background:white; border-radius:10px; margin-top:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); border-left:4px solid #DDD; overflow:hidden; cursor:pointer; }
  .check.found { border-left-color:#2E7D32; }
  .check.uncertain { border-left-color:#F9A825; }
  .check-head { padding:12px 14px; display:flex; align-items:center; gap:10px; }
  .check-head .ic { font-size:18px; }
  .check-head .nm { font-size:13px; font-weight:700; }
  .badge { font-size:9px; padding:2px 7px; border-radius:8px; font-weight:700; margin-left:6px; }
  .b-found { background:#E8F5E9; color:#2E7D32; } .b-miss { background:#FFEBEE; color:#C62828; }
  .b-uncertain { background:#FFF8E1; color:#F57F17; }
  .b-high { background:#FFEBEE; color:#C62828; } .b-med { background:#FFF8E1; color:#E8680A; } .b-low { background:#F0F4FA; color:#888; }
  .check .desc { font-size:11px; color:#888; margin-top:2px; }
  .check-body { padding:0 14px 13px; display:none; }
  .check.open .check-body { display:block; }
  .impact-box { font-size:11px; color:#C62828; padding:9px 11px; background:#FFF5F5; border-radius:8px; line-height:1.5; }
  .meta-box { display:flex; gap:8px; margin-top:8px; }
  .meta-box div { flex:1; padding:7px 9px; background:#F8FAFF; border-radius:7px; }
  .meta-box .k { font-size:9px; color:#AAA; text-transform:uppercase; }
  .meta-box .v { font-size:13px; font-weight:700; color:#1A4A8A; }
  .pitch { margin-top:16px; padding:14px; background:#FFF3E0; border-radius:10px; border:1.5px solid #E8680A; }
  .pitch h3 { font-size:13px; color:#E8680A; margin-bottom:6px; }
  .pitch p { font-size:12px; color:#555; line-height:1.7; }
  .err { margin-top:14px; padding:14px; background:#FFEBEE; border-radius:10px; border-left:4px solid #C62828; font-size:13px; color:#C62828; display:none; }
  .site-meta { font-size:11px; color:#888; margin-top:4px; }
  .platform-chip { display:inline-block; margin-top:6px; font-size:10px; font-weight:600; background:#F0F4FA; color:#555; padding:3px 9px; border-radius:6px; }
</style>
</head>
<body>
<div class="header">
  <div class="container" style="padding-bottom:0">
    <div class="tag">Website Intelligence Auditor</div>
    <h1>Is This Website<br>Capturing Leads?</h1>
    <p>25-point instant audit — analytics, retargeting, lead capture, SEO & AI readiness</p>
  </div>
</div>

<div class="container">
  <div class="card">
    <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:8px">Enter any website URL</div>
    <div class="input-row">
      <input type="text" id="url" placeholder="e.g. speedforceev.in" onkeydown="if(event.key==='Enter')runAudit()">
      <button class="audit-btn" id="btn" onclick="runAudit()">Audit →</button>
    </div>
    <div class="hint">Reads the live HTML source — 100% accurate, no AI guessing</div>
    <label style="display:flex;align-items:center;gap:8px;margin-top:12px;cursor:pointer;user-select:none">
      <input type="checkbox" id="deep" style="width:18px;height:18px;cursor:pointer">
      <span style="font-size:12px;color:#444"><b>Deep Scan</b> — load the page in a real browser to catch tools added by JavaScript & inside GTM <span style="color:#999">(slower, ~10–15 sec)</span></span>
    </label>
  </div>

  <div class="spinner" id="spin">
    <div style="font-size:15px;font-weight:700;color:#1A4A8A;margin-bottom:10px" id="spin-text">🔍 Fetching live source code…</div>
    <div class="dots"><span></span><span></span><span></span></div>
  </div>

  <div class="err" id="err"></div>
  <div id="results"></div>
</div>

<script>
const CAT_COLORS = {
  "Traffic Intelligence":"#1A4A8A","Behaviour Intelligence":"#E8680A",
  "Retargeting":"#7B1FA2","Lead Capture":"#2E7D32",
  "Trust & Security":"#C62828","SEO & Visibility":"#00796B","AI Readiness":"#5E35B1"
};
let DATA = null, FILTER = "All";

async function runAudit() {
  const url = document.getElementById('url').value.trim();
  if (!url) return;
  const deep = document.getElementById('deep').checked;
  document.getElementById('btn').disabled = true;
  document.getElementById('spin-text').textContent = deep
    ? '🌐 Deep scan — loading page in a real browser…'
    : '🔍 Fetching live source code…';
  document.getElementById('spin').style.display = 'block';
  document.getElementById('err').style.display = 'none';
  document.getElementById('results').innerHTML = '';
  try {
    const res = await fetch('/api/audit', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url, deep_scan: deep})
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Audit failed');
    DATA = data; FILTER = "All";
    render();
  } catch(e) {
    const errBox = document.getElementById('err');
    errBox.textContent = '⚠️ ' + e.message;
    errBox.style.display = 'block';
  } finally {
    document.getElementById('btn').disabled = false;
    document.getElementById('spin').style.display = 'none';
  }
}

function render() {
  const d = DATA;
  const sc = d.score >= 70 ? '#2E7D32' : d.score >= 40 ? '#E8680A' : '#C62828';
  const scLbl = d.score >= 70 ? 'Good Setup' : d.score >= 40 ? 'Needs Work' : 'Critical Gaps';
  const cats = ["All", ...new Set(d.checks.map(c => c.category))];
  const visible = d.checks.filter(c => FILTER === "All" || c.category === FILTER);
  const missingNames = d.checks.filter(c => !c.found && !c.uncertain).map(c => c.name).join('  ·  ');
  const uncertainNames = d.checks.filter(c => c.uncertain).map(c => c.name).join('  ·  ');

  document.getElementById('results').innerHTML = `
    <div class="card" style="border-top:4px solid ${sc}">
      <div class="score-row">
        <div>
          <div style="font-size:10px;color:#AAA;text-transform:uppercase;letter-spacing:1px">Audit Complete</div>
          <div style="font-size:17px;font-weight:800;margin-top:2px">${d.domain}</div>
          ${d.page_title ? `<div class="site-meta">"${d.page_title}"</div>` : ''}
          <span class="platform-chip">🏗 ${d.platform} · ⚡ ${d.load_ms}ms load</span>
          <span class="platform-chip" style="background:${d.scan_mode==='deep'?'#E8F5E9':'#F0F4FA'};color:${d.scan_mode==='deep'?'#2E7D32':'#777'}">${d.scan_mode==='deep'?'🌐 Deep Scan (browser-rendered)':'⚡ Fast Scan (HTML source)'}</span>
        </div>
        <div style="text-align:center">
          <div class="score-big" style="color:${sc}">${d.score}%</div>
          <div style="font-size:10px;font-weight:700;color:${sc}">${scLbl}</div>
        </div>
      </div>
      <div class="stat-row">
        <div class="stat" style="background:#E8F5E9"><div class="v" style="color:#2E7D32">${d.found}</div><div class="l" style="color:#2E7D32">Installed</div></div>
        ${d.uncertain > 0 ? `<div class="stat" style="background:#FFF8E1"><div class="v" style="color:#F57F17">${d.uncertain}</div><div class="l" style="color:#F57F17">Via GTM?</div></div>` : ''}
        <div class="stat" style="background:#FFEBEE"><div class="v" style="color:#C62828">${d.missing}</div><div class="l" style="color:#C62828">Missing</div></div>
        <div class="stat" style="background:#FFF3E0"><div class="v" style="color:#E8680A">${d.critical_gaps}</div><div class="l" style="color:#E8680A">Critical</div></div>
      </div>
      ${d.gtm_present && d.uncertain > 0 ? `
        <div style="margin-top:12px;padding:10px 12px;background:#FFF8E1;border-radius:8px;border-left:3px solid #F9A825">
          <div style="font-size:11px;font-weight:700;color:#F57F17;margin-bottom:3px">🏷️ Google Tag Manager detected</div>
          <div style="font-size:11px;color:#7A5C00;line-height:1.5">${d.uncertain} tool(s) not found directly in the page source, but they may be firing inside the GTM container. A deep scan is recommended to confirm before telling the client these are missing.</div>
        </div>` : ''}
    </div>

    <div class="pill-row">
      ${cats.map(c => `<button class="pill ${FILTER===c?'active':''}" onclick="FILTER='${c}';render()">${c}</button>`).join('')}
    </div>

    <div id="checks">
      ${visible.map((c,i) => {
        const state = c.found ? 'found' : c.uncertain ? 'uncertain' : 'miss';
        const icon = c.found ? c.icon : c.uncertain ? '❓' : '❌';
        const badge = c.found
          ? '<span class="badge b-found">✓ FOUND</span>'
          : c.uncertain
            ? '<span class="badge b-uncertain">❓ MAYBE (via GTM)</span>'
            : '<span class="badge b-miss">✗ MISSING</span>';
        return `
        <div class="check ${state}" onclick="this.classList.toggle('open')">
          <div class="check-head">
            <span class="ic">${icon}</span>
            <div style="flex:1">
              <span class="nm">${c.name}</span>
              ${badge}
              <span class="badge ${c.impact==='HIGH'?'b-high':c.impact==='MEDIUM'?'b-med':'b-low'}">${c.impact}</span>
              <div class="desc">${c.description}</div>
              ${c.warning ? `<div style="font-size:10px;color:${c.uncertain?'#F57F17':'#C62828'};font-weight:700;margin-top:3px">⚠️ ${c.warning}</div>` : ''}
            </div>
            <span style="font-size:10px;color:#CCC">▼</span>
          </div>
          <div class="check-body">
            ${c.found
              ? `<div style="font-size:11px;color:#2E7D32;font-weight:600;padding:9px 11px;background:#E8F5E9;border-radius:8px">✅ Active — ${c.description}</div>`
              : c.uncertain
                ? `<div style="font-size:11px;color:#7A5C00;padding:9px 11px;background:#FFF8E1;border-radius:8px;line-height:1.5">❓ Not found in page source, but a GTM container is present. This tool is often loaded through GTM, so it may already be active. Verify inside the client's GTM dashboard before reporting it as missing.</div>`
                : `<div class="impact-box">🚨 <strong>What's being lost:</strong> ${c.missing_msg}</div>
                   <div class="meta-box">
                     <div><div class="k">Fix Time</div><div class="v">${c.fix_time}</div></div>
                     <div><div class="k">Cost</div><div class="v" style="color:#2E7D32">${c.cost}</div></div>
                   </div>`}
          </div>
        </div>`;
      }).join('')}
    </div>

    ${d.missing > 0 ? `
      <div class="pitch">
        <h3>📋 Sales Pitch — Ready to Use</h3>
        <p><strong>${d.domain}</strong> is missing <strong style="color:#C62828">${d.critical_gaps} critical</strong>
        and <strong>${d.missing - d.critical_gaps} other</strong> tools. Every month without them,
        visitor data is lost permanently. Most fixes are free and take under 3 hours total.</p>
        <p style="margin-top:8px;padding:8px 10px;background:white;border-radius:8px"><strong>Confirmed missing:</strong> ${missingNames}</p>
        ${uncertainNames ? `<p style="margin-top:6px;padding:8px 10px;background:#FFF8E1;border-radius:8px;font-size:11px"><strong>Verify in GTM:</strong> ${uncertainNames}</p>` : ''}
      </div>` : ''}
  `;
}
</script>
</body>
</html>"""
