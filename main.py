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
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Website Intelligence Auditor")

# ─── Email configuration (set these as environment variables on Render) ───────
# SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL, OWNER_EMAIL
# For Google Workspace use smtp.gmail.com with an App Password (not your normal password).
SMTP_HOST   = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER   = os.environ.get("SMTP_USER", "")          # e.g. amit.ahuja@thewebsiteauditor.com
SMTP_PASS   = os.environ.get("SMTP_PASS", "")          # an app password
FROM_EMAIL  = os.environ.get("FROM_EMAIL", SMTP_USER)
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "amit.ahuja@thewebsiteauditor.com")

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
    email: str = ""          # optional — if provided, email the report
    name: str = ""           # optional — visitor's name


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


def build_report_html(result: dict, visitor_name: str = "") -> str:
    """Build a plain-language HTML email report from audit results."""
    score = result["score"]
    sc_color = "#2E7D32" if score >= 70 else "#E8680A" if score >= 40 else "#C62828"
    greeting = f"Hi {visitor_name}," if visitor_name else "Hello,"

    missing = [c for c in result["checks"] if not c["found"] and not c.get("uncertain")]
    found   = [c for c in result["checks"] if c["found"]]

    missing_rows = ""
    for c in missing:
        missing_rows += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:14px;">
            <b>{c['icon']} {c['name']}</b>
            <div style="color:#777;font-size:12px;margin-top:3px;">{c.get('missing_msg') or c['description']}</div>
          </td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:center;font-size:11px;color:#C62828;font-weight:700;white-space:nowrap;">{c['impact']}</td>
        </tr>"""

    found_list = " · ".join(c["name"] for c in found) or "None yet"

    return f"""<!DOCTYPE html><html><body style="margin:0;background:#f0f4fa;font-family:Arial,sans-serif;">
    <div style="max-width:640px;margin:0 auto;background:#fff;">
      <div style="background:linear-gradient(135deg,#1A4A8A,#0D2E5A);padding:28px 30px;color:#fff;">
        <div style="font-size:11px;letter-spacing:2px;color:#8FB8F0;text-transform:uppercase;">Website Health Report</div>
        <div style="font-size:24px;font-weight:900;margin-top:6px;">{result['domain']}</div>
        <div style="font-size:13px;color:#C5D8F5;margin-top:4px;">Prepared by The Website Auditor</div>
      </div>
      <div style="padding:24px 30px;text-align:center;background:#FFF4E6;border-bottom:1px solid #f0dcc0;">
        <div style="font-size:48px;font-weight:900;color:{sc_color};line-height:1;">{score}%</div>
        <div style="font-size:13px;color:#666;margin-top:6px;">Health Score — {result['found']} working, {result['missing']} missing of 25 essential tools</div>
      </div>
      <div style="padding:24px 30px;">
        <p style="font-size:15px;color:#333;">{greeting}</p>
        <p style="font-size:15px;color:#333;line-height:1.6;">Here is the free health check for <b>{result['domain']}</b>. Your website is missing <b style="color:#C62828;">{result['missing']} tools</b> that help capture and follow up with visitors. The good news: most are free and quick to fix.</p>
        <h3 style="font-size:16px;color:#1A4A8A;margin:22px 0 10px;">What's missing right now</h3>
        <table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden;">{missing_rows}</table>
        <h3 style="font-size:16px;color:#2E7D32;margin:22px 0 8px;">Already working ✓</h3>
        <p style="font-size:13px;color:#555;line-height:1.6;">{found_list}</p>
        <div style="margin-top:26px;padding:18px;background:#1A4A8A;border-radius:10px;text-align:center;">
          <div style="color:#fff;font-size:15px;font-weight:700;margin-bottom:6px;">Want us to fix all of this for you?</div>
          <div style="color:#B8D0F0;font-size:13px;margin-bottom:14px;">Most fixes are free. You only pay for setup time.</div>
          <a href="https://wa.me/919886650133" style="background:#E8680A;color:#fff;text-decoration:none;padding:11px 24px;border-radius:8px;font-weight:700;font-size:14px;display:inline-block;">Chat on WhatsApp →</a>
        </div>
      </div>
      <div style="padding:18px 30px;background:#0D2E5A;color:#9DBDEE;font-size:12px;text-align:center;">
        Amit Ahuja · The Website Auditor · +91 98866 50133<br>amit.ahuja@thewebsiteauditor.com · Bangalore, Karnataka
      </div>
    </div></body></html>"""


def send_email(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Send an HTML email via SMTP. Returns (success, message)."""
    if not SMTP_USER or not SMTP_PASS:
        return False, "Email not configured on server (SMTP_USER/SMTP_PASS missing)."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
        return True, "sent"
    except Exception as e:
        return False, f"{e.__class__.__name__}: {e}"


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

    result = {
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

    # ─── Email the report if a visitor email was provided ───
    email = (req.email or "").strip()
    if email and "@" in email:
        report_html = build_report_html(result, req.name)
        # 1) Send report to the visitor
        ok_visitor, msg_v = send_email(
            email,
            f"Your Website Health Report — {domain} ({score}%)",
            report_html,
        )
        # 2) Send a copy/lead alert to the owner (Amit)
        if OWNER_EMAIL:
            lead_note = (
                f"<p style='font-family:Arial'>New audit lead:<br>"
                f"<b>Name:</b> {req.name or '—'}<br>"
                f"<b>Email:</b> {email}<br>"
                f"<b>Website audited:</b> {domain} — scored {score}%</p>"
            )
            send_email(OWNER_EMAIL, f"New lead: {email} audited {domain}", lead_note + report_html)

        result["email_sent"] = ok_visitor
        result["email_msg"] = msg_v

    return result


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
<title>The Website Auditor — Free 25-Point Website Audit</title>
<meta name="description" content="Free instant 25-point audit of any website. See what tracking, lead-capture and retargeting tools are missing — and get the report by email.">
<link rel="canonical" href="https://thewebsiteauditor.com/">
<meta property="og:title" content="The Website Auditor — Free Website Audit">
<meta property="og:description" content="Check any website in seconds. 25-point report on what's missing.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://thewebsiteauditor.com/">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%231A4A8A'/><text x='50' y='70' font-size='62' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'>W</text></svg>">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ProfessionalService","name":"The Website Auditor","url":"https://thewebsiteauditor.com","email":"amit.ahuja@thewebsiteauditor.com","telephone":"+91-98866-50133","areaServed":"India","address":{"@type":"PostalAddress","addressLocality":"Bangalore","addressRegion":"Karnataka","addressCountry":"IN"},"founder":{"@type":"Person","name":"Amit Ahuja"}}
</script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',Arial,sans-serif; }
  html { scroll-behavior:smooth; }
  body { color:#1a1a1a; line-height:1.6; background:#fff; }
  .wrap { max-width:1080px; margin:0 auto; padding:0 20px; }
  nav { position:sticky; top:0; background:rgba(255,255,255,0.97); backdrop-filter:blur(8px); box-shadow:0 1px 12px rgba(0,0,0,0.06); z-index:100; }
  nav .wrap { display:flex; align-items:center; justify-content:space-between; padding:13px 20px; }
  .logo { display:flex; align-items:center; gap:9px; font-weight:900; font-size:18px; color:#1A4A8A; }
  .logo .mark { width:32px; height:32px; background:#1A4A8A; color:#fff; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:18px; }
  nav .links { display:flex; gap:20px; align-items:center; }
  nav .links a { text-decoration:none; color:#444; font-size:14px; font-weight:600; }
  nav .cta { background:#E8680A; color:#fff !important; padding:8px 16px; border-radius:8px; }
  @media(max-width:760px){ nav .links a:not(.cta){ display:none; } }
  .hero { background:linear-gradient(135deg,#1A4A8A,#0D2E5A); color:#fff; padding:54px 0 60px; }
  .hero h1 { font-size:38px; font-weight:900; line-height:1.15; max-width:740px; }
  .hero p { font-size:17px; color:#C5D8F5; margin-top:16px; max-width:600px; }
  @media(max-width:760px){ .hero h1{ font-size:28px; } }
  .audit-box { background:#fff; border-radius:16px; padding:22px; margin-top:30px; max-width:620px; box-shadow:0 12px 40px rgba(0,0,0,0.18); }
  .audit-box label { font-size:12px; font-weight:700; color:#666; text-transform:uppercase; letter-spacing:1px; }
  .row1 { display:flex; gap:10px; margin-top:8px; }
  .row1 input { flex:1; padding:13px 14px; border:1.5px solid #DDE3EF; border-radius:9px; font-size:15px; outline:none; color:#111; }
  .row1 button { padding:13px 22px; border:none; border-radius:9px; background:#E8680A; color:#fff; font-weight:800; font-size:15px; cursor:pointer; white-space:nowrap; }
  .row1 button:disabled { background:#aaa; }
  .opts { display:flex; gap:16px; margin-top:12px; flex-wrap:wrap; align-items:center; }
  .opts label { display:flex; align-items:center; gap:6px; font-size:13px; color:#555; text-transform:none; letter-spacing:0; font-weight:500; cursor:pointer; }
  .opts input[type=email] { flex:1; min-width:180px; padding:9px 12px; border:1.5px solid #DDE3EF; border-radius:8px; font-size:13px; }
  .hint2 { font-size:11px; color:#999; margin-top:8px; }
  section { padding:56px 0; }
  .eyebrow { font-size:12px; letter-spacing:2px; text-transform:uppercase; color:#E8680A; font-weight:700; }
  h2.title { font-size:28px; font-weight:900; color:#1A2B45; margin-top:8px; }
  .lead { font-size:16px; color:#666; margin-top:10px; max-width:600px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:16px; margin-top:32px; }
  .cardx { border:1px solid #EEF1F6; border-radius:14px; padding:20px; }
  .cardx .ic { font-size:28px; } .cardx h3 { font-size:16px; margin-top:10px; color:#1A2B45; } .cardx p { font-size:13px; color:#777; margin-top:5px; }
  .alt { background:#F6F9FD; }
  .steps { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:22px; margin-top:32px; }
  .step { text-align:center; } .step .n { width:50px; height:50px; border-radius:50%; background:#1A4A8A; color:#fff; font-size:20px; font-weight:900; display:flex; align-items:center; justify-content:center; margin:0 auto 12px; }
  .step h3 { font-size:17px; color:#1A2B45; } .step p { font-size:13px; color:#777; margin-top:5px; }
  .price-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:20px; margin-top:32px; }
  .price { border:1px solid #E5EBF3; border-radius:16px; padding:28px 24px; }
  .price.featured { border:2px solid #E8680A; position:relative; }
  .price.featured::before { content:"MOST POPULAR"; position:absolute; top:-11px; left:24px; background:#E8680A; color:#fff; font-size:10px; font-weight:800; padding:4px 11px; border-radius:12px; letter-spacing:1px; }
  .price h3 { font-size:19px; color:#1A2B45; } .price .amt { font-size:32px; font-weight:900; color:#1A4A8A; margin:10px 0; } .price .amt span { font-size:13px; color:#999; font-weight:600; }
  .price ul { list-style:none; margin:16px 0; } .price li { font-size:13px; color:#555; padding:6px 0 6px 24px; position:relative; } .price li::before { content:"✓"; position:absolute; left:0; color:#2E7D32; font-weight:900; }
  footer { background:#0D2E5A; color:#9DBDEE; padding:36px 0 22px; font-size:13px; }
  footer .cols { display:flex; justify-content:space-between; flex-wrap:wrap; gap:22px; margin-bottom:22px; }
  footer h4 { color:#fff; font-size:14px; margin-bottom:9px; } footer a { color:#9DBDEE; text-decoration:none; display:block; margin-bottom:5px; }
  footer .bot { border-top:1px solid rgba(255,255,255,0.1); padding-top:16px; text-align:center; font-size:11px; }
  .wa-float { position:fixed; bottom:22px; right:22px; width:58px; height:58px; background:#25D366; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:30px; box-shadow:0 4px 16px rgba(0,0,0,0.25); z-index:200; text-decoration:none; }
  /* results */
  #out { margin-top:22px; }
  .scorecard { background:#fff; border-radius:14px; padding:18px; box-shadow:0 2px 10px rgba(0,0,0,0.1); color:#111; }
  .stat-row { display:flex; gap:8px; margin-top:12px; }
  .stat { flex:1; text-align:center; padding:9px 4px; border-radius:8px; }
  .stat .v { font-size:22px; font-weight:900; } .stat .l { font-size:10px; font-weight:600; }
  .chk { background:#fff; border-radius:9px; margin-top:7px; box-shadow:0 1px 4px rgba(0,0,0,0.07); border-left:4px solid #ddd; padding:11px 13px; color:#111; }
  .chk.ok { border-left-color:#2E7D32; } .chk.unc { border-left-color:#F9A825; }
  .chk .nm { font-size:13px; font-weight:700; } .chk .ds { font-size:11px; color:#888; }
  .badge { font-size:9px; padding:2px 7px; border-radius:8px; font-weight:700; margin-left:6px; }
  .spin { text-align:center; padding:24px; color:#fff; }
  .dots span { display:inline-block; width:9px; height:9px; margin:0 3px; border-radius:50%; background:#fff; animation:b 1.2s infinite; }
  .dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
  @keyframes b{0%,100%{opacity:.3}50%{opacity:1}}
</style>
</head>
<body>
<nav><div class="wrap">
  <div class="logo"><span class="mark">W</span> The Website Auditor</div>
  <div class="links"><a href="#how">How It Works</a><a href="#pricing">Pricing</a><a href="#audit" class="cta">Free Audit</a></div>
</div></nav>

<header class="hero"><div class="wrap" id="audit">
  <h1>Check any website in seconds. See exactly what it's missing.</h1>
  <p>Our free 25-point audit reveals the tracking, lead-capture and retargeting tools a website lacks — and we can email you the full report.</p>
  <div class="audit-box">
    <label>Enter a website to audit</label>
    <div class="row1">
      <input type="text" id="url" placeholder="e.g. yourbusiness.com" onkeydown="if(event.key==='Enter')run()">
      <button id="btn" onclick="run()">Audit →</button>
    </div>
    <div class="opts">
      <label><input type="checkbox" id="deep"> Deep scan (slower, catches JS tools)</label>
    </div>
    <div class="opts">
      <input type="email" id="email" placeholder="Your email (optional) — we'll send the report">
      <input type="text" id="name" placeholder="Your name" style="max-width:140px;padding:9px 12px;border:1.5px solid #DDE3EF;border-radius:8px;font-size:13px;">
    </div>
    <div class="hint2">100% free · No signup · Reads the live website code</div>
    <div id="out"></div>
  </div>
</div></header>

<section id="how" class="alt"><div class="wrap">
  <div class="eyebrow">How It Works</div>
  <h2 class="title">From audit to more customers in 3 steps</h2>
  <div class="steps">
    <div class="step"><div class="n">1</div><h3>Free Audit</h3><p>Enter any website above. Get an instant 25-point report in plain language.</p></div>
    <div class="step"><div class="n">2</div><h3>We Fix It</h3><p>We install the missing tools — tracking, WhatsApp, retargeting, lead forms. Most are free.</p></div>
    <div class="step"><div class="n">3</div><h3>You Get Leads</h3><p>Visitors get captured and followed up automatically. Enquiries you were losing now reach you.</p></div>
  </div>
</div></section>

<section id="pricing"><div class="wrap">
  <div class="eyebrow">Pricing</div>
  <h2 class="title">Simple, honest pricing</h2>
  <p class="lead">The audit is free. You only pay if you want us to fix what we find.</p>
  <div class="price-grid">
    <div class="price"><h3>Audit Only</h3><div class="amt">Free</div><ul><li>Full 25-point audit</li><li>Plain-language report</li><li>Emailed to you</li><li>No obligation</li></ul></div>
    <div class="price featured"><h3>Audit + Setup</h3><div class="amt">₹15,000 <span>one-time</span></div><ul><li>Everything in Audit</li><li>GA4 + Clarity installed</li><li>WhatsApp + lead form</li><li>Meta Pixel + retargeting</li></ul></div>
    <div class="price"><h3>Full + Monthly</h3><div class="amt">₹15,000 <span>+ ₹10k/mo</span></div><ul><li>Everything in Setup</li><li>AI chatbot + follow-up</li><li>Automated WhatsApp/email</li><li>Monthly reports</li></ul></div>
  </div>
</div></section>

<footer><div class="wrap">
  <div class="cols">
    <div style="max-width:280px"><div class="logo" style="color:#fff;margin-bottom:9px"><span class="mark">W</span> The Website Auditor</div><p>Helping Indian businesses turn website visitors into customers.</p></div>
    <div><h4>Contact</h4><a href="tel:+919886650133">+91 98866 50133</a><a href="mailto:amit.ahuja@thewebsiteauditor.com">amit.ahuja@thewebsiteauditor.com</a><a href="#">Bangalore, Karnataka</a></div>
    <div><h4>Links</h4><a href="#how">How It Works</a><a href="#pricing">Pricing</a><a href="#audit">Free Audit</a></div>
  </div>
  <div class="bot">© 2026 The Website Auditor · Founded by Amit Ahuja · Bangalore, India<br><span style="font-size:11px;opacity:.8;display:block;margin-top:6px">Privacy: we collect only details you submit, to respond to your enquiry. Compliant with India's DPDP Act 2023.</span></div>
</div></footer>

<a href="https://wa.me/919886650133?text=Hi%20Amit,%20I'd%20like%20a%20website%20audit" class="wa-float" title="WhatsApp">💬</a>

<script>
async function run(){
  const url=document.getElementById('url').value.trim();
  if(!url){return;}
  const deep=document.getElementById('deep').checked;
  const email=document.getElementById('email').value.trim();
  const name=document.getElementById('name').value.trim();
  document.getElementById('btn').disabled=true;
  document.getElementById('out').innerHTML='<div class="spin">'+(deep?'🌐 Deep scan — loading in a browser…':'🔍 Reading website code…')+'<div class="dots"><span></span><span></span><span></span></div></div>';
  try{
    const r=await fetch('/api/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,deep_scan:deep,email,name})});
    const d=await r.json();
    if(!d.ok)throw new Error(d.error||'Audit failed');
    show(d);
  }catch(e){
    document.getElementById('out').innerHTML='<div class="scorecard" style="border-left:4px solid #C62828">⚠️ '+e.message+'</div>';
  }finally{ document.getElementById('btn').disabled=false; }
}
function show(d){
  const sc=d.score>=70?'#2E7D32':d.score>=40?'#E8680A':'#C62828';
  let h='<div class="scorecard" style="border-top:4px solid '+sc+'">';
  h+='<div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div style="font-size:10px;color:#aaa;text-transform:uppercase">Audit Complete</div><div style="font-size:16px;font-weight:800">'+d.domain+'</div><div style="font-size:11px;color:#888">'+d.platform+' · '+d.scan_mode+' scan</div></div><div style="text-align:center"><div style="font-size:36px;font-weight:900;color:'+sc+'">'+d.score+'%</div></div></div>';
  h+='<div class="stat-row"><div class="stat" style="background:#E8F5E9"><div class="v" style="color:#2E7D32">'+d.found+'</div><div class="l" style="color:#2E7D32">Working</div></div>';
  if(d.uncertain>0)h+='<div class="stat" style="background:#FFF8E1"><div class="v" style="color:#F57F17">'+d.uncertain+'</div><div class="l" style="color:#F57F17">Via GTM?</div></div>';
  h+='<div class="stat" style="background:#FFEBEE"><div class="v" style="color:#C62828">'+d.missing+'</div><div class="l" style="color:#C62828">Missing</div></div>';
  h+='<div class="stat" style="background:#FFF3E0"><div class="v" style="color:#E8680A">'+d.critical_gaps+'</div><div class="l" style="color:#E8680A">Critical</div></div></div>';
  if(d.email_sent)h+='<div style="margin-top:12px;padding:9px 11px;background:#E8F5E9;border-radius:8px;font-size:12px;color:#2E7D32;font-weight:600">📧 Full report sent to your email!</div>';
  else if(d.email_msg)h+='<div style="margin-top:12px;padding:9px 11px;background:#FFF8E1;border-radius:8px;font-size:11px;color:#a76f00">Note: email not sent ('+d.email_msg+')</div>';
  h+='</div>';
  d.checks.forEach(function(c){
    const st=c.found?'ok':(c.uncertain?'unc':'');
    const ic=c.found?c.icon:(c.uncertain?'❓':'❌');
    const bg=c.found?'background:#E8F5E9;color:#2E7D32':(c.uncertain?'background:#FFF8E1;color:#F57F17':'background:#FFEBEE;color:#C62828');
    const lbl=c.found?'✓ FOUND':(c.uncertain?'❓ MAYBE':'✗ MISSING');
    h+='<div class="chk '+st+'"><span class="nm">'+ic+' '+c.name+'</span><span class="badge" style="'+bg+'">'+lbl+'</span><div class="ds">'+c.description+'</div></div>';
  });
  document.getElementById('out').innerHTML=h;
}
</script>
</body>
</html>"""
