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
    # Name and email are compulsory — every audit must capture a lead.
    _name = (req.name or "").strip()
    _email = (req.email or "").strip()
    if not _name or not _email or "@" not in _email or "." not in _email.split("@")[-1]:
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": "Please enter your name and a valid email to run the audit.",
        })
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


@app.get("/sitemap.xml")
def sitemap():
    from fastapi.responses import Response
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://thewebsiteauditor.com/</loc><lastmod>2026-06-13</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://thewebsiteauditor.com/#how</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>https://thewebsiteauditor.com/#pricing</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>https://thewebsiteauditor.com/#audit</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
</urlset>"""
    return Response(content=xml, media_type="application/xml")


@app.get("/llms.txt")
def llms_txt():
    from fastapi.responses import PlainTextResponse
    txt = """# The Website Auditor

> Free 25-point website audit service for businesses worldwide. We check whether a
> website has the tracking, lead-capture, retargeting, SEO and AI-readiness tools
> needed to turn visitors into customers, then install whatever is missing.

## About
The Website Auditor, founded by Amit Ahuja and based in Bangalore, India, helps
businesses worldwide discover what their website is missing and fixes it for them.
The audit is free; setup and ongoing management are paid services.

## What we check (25 points)
- Traffic intelligence: Google Analytics 4, Google Tag Manager
- Behaviour: Microsoft Clarity, Hotjar
- Retargeting: Meta Pixel, Google Ads, LinkedIn Insight
- Lead capture: WhatsApp button, live chat, enquiry forms, exit popups, click-to-call
- Trust and security: SSL, privacy policy, testimonials
- SEO and visibility: schema, Open Graph, meta description, sitemap, mobile, favicon
- AI readiness: llms.txt, heading structure, canonical tags

## Services
- Free website audit (instant, 25-point report)
- Audit + Setup: one-time installation of all missing tools
- Full + Monthly: setup plus chatbot, automated follow-up, and monthly reports

## Contact
- Website: https://thewebsiteauditor.com
- Email: amit.ahuja@thewebsiteauditor.com
- Phone / WhatsApp: +91 98866 50133
- Location: Bangalore, Karnataka, India - serving businesses worldwide
"""
    return PlainTextResponse(content=txt)


FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Website Auditor — Free 60-Second Website Audit</title>
<meta name="description" content="Free 25-point website audit. See what tracking, lead-capture, retargeting and AI-search tools your website is missing — then we fix them.">
<link rel="canonical" href="https://thewebsiteauditor.com/">
<link rel="sitemap" type="application/xml" href="/sitemap.xml">
<meta property="og:title" content="The Website Auditor — Free Website Audit">
<meta property="og:description" content="Find what your website is missing in 60 seconds. Free 25-point audit.">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{--navy:#0A1A40;--navy2:#14245C;--blue:#2563EB;--lime:#A3E635;--green:#65A30D;
        --yellow:#FACC15;--light:#EAF1F8;--white:#fff;--ink:#0F172A;--grey:#5B6B85;--red:#EF4444;}
  *{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',ui-sans-serif,system-ui,sans-serif;}
  html{scroll-behavior:smooth;} body{color:var(--ink);background:var(--white);line-height:1.55;}
  .wrap{max-width:1180px;margin:0 auto;padding:0 22px;}
  a{text-decoration:none;color:inherit;}
  .btn{display:inline-flex;align-items:center;gap:8px;border:none;cursor:pointer;font-weight:700;border-radius:999px;padding:14px 26px;font-size:16px;transition:transform .12s,box-shadow .12s;}
  .btn:hover{transform:translateY(-2px);} .btn:disabled{opacity:.55;cursor:default;transform:none;}
  .btn-yellow{background:var(--yellow);color:var(--navy);box-shadow:0 8px 22px rgba(250,204,21,.35);}
  .btn-navy{background:var(--navy);color:#fff;}
  .pill{display:inline-flex;align-items:center;gap:8px;border:1.5px solid var(--lime);color:var(--lime);font-weight:600;font-size:13px;letter-spacing:.5px;text-transform:uppercase;padding:7px 14px;border-radius:999px;}
  nav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.93);backdrop-filter:blur(8px);border-bottom:1px solid #e2e8f0;}
  .nav{display:flex;align-items:center;justify-content:space-between;padding:13px 0;}
  .logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;color:var(--navy);}
  .logo .mark{width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,var(--navy),var(--blue));display:flex;align-items:center;justify-content:center;}
  .nav-links{display:flex;align-items:center;gap:26px;font-weight:500;color:var(--navy);}
  .nav-links a:hover{color:var(--blue);}
  .hero{background:linear-gradient(135deg,var(--navy) 0%,var(--navy2) 55%,var(--blue) 135%);color:#fff;padding:64px 0 80px;position:relative;overflow:hidden;}
  .hero .wrap{display:grid;grid-template-columns:1.05fr .95fr;gap:46px;align-items:start;position:relative;z-index:2;}
  .hero h1{font-size:44px;font-weight:800;line-height:1.12;margin:16px 0 14px;}
  .hero h1 .hl{color:var(--lime);}
  .hero p.sub{font-size:17px;color:#cdd9f0;max-width:520px;}
  .ghost{position:absolute;right:-90px;top:30px;opacity:.06;z-index:1;}
  .auditcard{background:#fff;border-radius:20px;padding:22px;box-shadow:0 30px 60px rgba(2,8,30,.35);color:var(--ink);}
  .auditcard label.l{font-size:13px;font-weight:600;color:var(--grey);display:block;margin-bottom:7px;}
  .auditcard input{border:1.5px solid #DDE3EF;border-radius:10px;padding:13px 15px;font-size:15px;color:var(--ink);width:100%;}
  .auditcard input:focus{outline:3px solid var(--lime);border-color:var(--lime);}
  .subrow{display:flex;gap:9px;margin-top:9px;}
  .subrow input{flex:1;min-width:0;}
  .deep{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--grey);margin-top:10px;cursor:pointer;}
  .deep input{width:auto;}
  .hint{font-size:12px;color:#94a3b8;margin-top:9px;}
  #out{margin-top:16px;}
  .scorecard{border-radius:14px;padding:16px;background:var(--light);border:1px solid #dbe5f3;}
  .scorehead{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}
  .scorehead .dom{font-size:16px;font-weight:800;color:var(--navy);}
  .scorehead .meta{font-size:11px;color:var(--grey);}
  .scorehead .score{font-size:38px;font-weight:800;line-height:1;}
  .stat-row{display:flex;gap:7px;margin-top:12px;}
  .stat{flex:1;text-align:center;padding:9px 4px;border-radius:9px;}
  .stat .v{font-size:20px;font-weight:800;} .stat .s{font-size:10px;font-weight:600;}
  .emailnote{margin-top:11px;padding:9px 11px;border-radius:9px;font-size:12px;font-weight:600;}
  .cathead{font-size:11px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:var(--grey);margin:15px 0 5px;}
  .chk{background:#fff;border-radius:9px;margin-top:7px;border-left:4px solid #cbd5e1;padding:10px 12px;}
  .chk.ok{border-left-color:var(--green);} .chk.unc{border-left-color:var(--yellow);} .chk.no{border-left-color:var(--red);}
  .chkhead{display:flex;align-items:center;gap:6px;cursor:pointer;}
  .chk .nm{font-size:13px;font-weight:700;color:var(--navy);flex:1;}
  .chk .badge{font-size:9px;padding:2px 7px;border-radius:8px;font-weight:700;}
  .caret{font-size:11px;color:#94a3b8;transition:transform .15s;}
  .chk.open .caret{transform:rotate(90deg);}
  .detail{display:none;margin-top:9px;padding-top:9px;border-top:1px solid #eef2f7;font-size:12px;color:#475569;}
  .chk.open .detail{display:block;}
  .detail p{margin-bottom:6px;} .detail .m{font-size:11px;color:#94a3b8;}
  .fixbtn{display:inline-block;margin-top:6px;background:var(--navy);color:#fff;font-weight:600;font-size:12px;padding:7px 14px;border-radius:999px;}
  .spin{text-align:center;padding:22px;color:var(--navy);font-weight:600;}
  .dots span{display:inline-block;width:9px;height:9px;margin:0 3px;border-radius:50%;background:var(--blue);animation:b 1.2s infinite;}
  .dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
  @keyframes b{0%,100%{opacity:.3}50%{opacity:1}}
  section.block{padding:70px 0;} .bg-light{background:var(--light);}
  .eyebrow{color:var(--green);font-weight:700;letter-spacing:1px;text-transform:uppercase;font-size:13px;text-align:center;}
  h2.sec{font-size:32px;font-weight:800;color:var(--navy);text-align:center;margin:8px 0 10px;}
  p.lead{text-align:center;color:var(--grey);max-width:600px;margin:0 auto 40px;font-size:16px;}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;}
  .feature{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:22px;transition:transform .15s,box-shadow .15s;}
  .feature:hover{transform:translateY(-4px);box-shadow:0 16px 30px rgba(10,26,64,.08);}
  .feature .fic{width:50px;height:50px;border-radius:12px;background:var(--navy);display:flex;align-items:center;justify-content:center;margin-bottom:13px;}
  .feature .fic svg{width:27px;height:27px;}
  .feature h4{color:var(--navy);font-size:17px;margin-bottom:5px;} .feature p{color:var(--grey);font-size:14px;}
  .steps{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;}
  .step{text-align:center;} .step .n{width:62px;height:62px;border-radius:50%;background:var(--navy);color:var(--lime);font-weight:800;font-size:25px;display:flex;align-items:center;justify-content:center;margin:0 auto 15px;}
  .step h4{color:var(--navy);font-size:18px;margin-bottom:5px;} .step p{color:var(--grey);font-size:14px;}
  .price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;}
  .price{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:26px 22px;}
  .price.feat{border:2px solid var(--lime);position:relative;}
  .price.feat::before{content:"MOST POPULAR";position:absolute;top:-11px;left:22px;background:var(--lime);color:var(--navy);font-size:10px;font-weight:800;padding:4px 11px;border-radius:12px;letter-spacing:1px;}
  .price h3{font-size:18px;color:var(--navy);} .price .amt{font-size:30px;font-weight:800;color:var(--blue);margin:9px 0;} .price .amt span{font-size:13px;color:#94a3b8;font-weight:600;}
  .price ul{list-style:none;margin:14px 0;} .price li{font-size:13px;color:#475569;padding:6px 0 6px 22px;position:relative;} .price li::before{content:"✓";position:absolute;left:0;color:var(--green);font-weight:800;}
  .band{background:linear-gradient(135deg,var(--navy),var(--navy2));color:#fff;border-radius:24px;padding:44px;display:grid;grid-template-columns:1.2fr 1fr;gap:34px;align-items:center;}
  .band h3{font-size:26px;font-weight:800;margin-bottom:12px;} .band h3 .hl{color:var(--lime);}
  .band ul{list-style:none;display:grid;gap:11px;} .band li{display:flex;gap:10px;color:#dbe5f7;font-weight:500;} .band li .d{color:var(--lime);font-weight:800;}
  footer{background:var(--navy);color:#9db4de;padding:44px 0 26px;font-size:14px;}
  .foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:22px;} .foot h4{color:#fff;font-size:14px;margin-bottom:9px;} .foot a{color:#9db4de;display:block;margin-bottom:5px;} .foot a:hover{color:var(--lime);}
  .foot .logo{color:#fff;margin-bottom:9px;} .foot .bot{border-top:1px solid rgba(255,255,255,.1);margin-top:20px;padding-top:16px;text-align:center;font-size:11px;opacity:.8;}
  .wa-float{position:fixed;bottom:22px;right:22px;width:58px;height:58px;background:#25D366;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:29px;box-shadow:0 4px 16px rgba(0,0,0,.25);z-index:200;}
  @media(max-width:880px){.hero .wrap{grid-template-columns:1fr;gap:30px;}.hero h1{font-size:34px;}.grid,.steps,.price-grid{grid-template-columns:1fr;}.band{grid-template-columns:1fr;padding:30px;}.nav-links{display:none;}h2.sec{font-size:26px;}}
</style>
</head>
<body>
<nav><div class="wrap nav">
  <div class="logo"><span class="mark"><svg width="22" height="22" viewBox="0 0 100 100"><circle cx="44" cy="42" r="24" fill="none" stroke="#fff" stroke-width="8"/><path d="M34 44 L42 52 L58 34" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/><line x1="61" y1="61" x2="82" y2="82" stroke="#fff" stroke-width="9" stroke-linecap="round"/></svg></span> The Website Auditor</div>
  <div class="nav-links"><a href="#check">What we check</a><a href="#how">How it works</a><a href="#pricing">Pricing</a></div>
  <a class="btn btn-yellow" onclick="focusUrl()">Scan Now</a>
</div></nav>

<header class="hero" id="top">
  <svg class="ghost" width="520" height="520" viewBox="0 0 100 100"><circle cx="44" cy="42" r="24" fill="none" stroke="#fff" stroke-width="6"/><path d="M34 44 L42 52 L58 34" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><line x1="61" y1="61" x2="86" y2="86" stroke="#fff" stroke-width="7" stroke-linecap="round"/></svg>
  <div class="wrap">
    <div>
      <span class="pill">⚡ Free 60-second website audit</span>
      <h1>Find what's quietly costing your website <span class="hl">customers.</span></h1>
      <p class="sub">We scan any site for 25 things every business needs in 2026 — tracking, lead capture, retargeting and whether AI search engines can even find you. Tap any result to see what it means and how to fix it.</p>
    </div>
    <div class="auditcard" id="audit">
      <label class="l">Enter a website to audit</label>
      <input type="text" id="url" placeholder="e.g. yourbusiness.com" onkeydown="if(event.key==='Enter')run()">
      <div class="subrow">
        <input type="text" id="name" placeholder="Your name *">
        <input type="email" id="email" placeholder="Your email *">
      </div>
      <button class="btn btn-yellow" id="btn" onclick="run()" style="width:100%;justify-content:center;margin-top:11px;">Scan Now — Free</button>
      <label class="deep"><input type="checkbox" id="deep"> Deep scan (slower, catches JS-loaded tools)</label>
      <div class="hint">100% free · we email your full report · reads your live website code</div>
      <div id="out"></div>
    </div>
  </div>
</header>

<section class="block bg-light" id="check"><div class="wrap">
  <p class="eyebrow">What we check</p>
  <h2 class="sec">Your website's full report card</h2>
  <p class="lead">Most audits only look at Google rankings. We check everything that turns a visitor into a customer.</p>
  <div class="grid">
    <div class="feature"><div class="fic"><svg viewBox="0 0 100 100"><line x1="32" y1="72" x2="32" y2="56" stroke="#A3E635" stroke-width="9" stroke-linecap="round"/><line x1="50" y1="72" x2="50" y2="42" stroke="#A3E635" stroke-width="9" stroke-linecap="round"/><line x1="68" y1="72" x2="68" y2="30" stroke="#A3E635" stroke-width="9" stroke-linecap="round"/></svg></div><h4>Analytics &amp; Tracking</h4><p>Know how many people visit, where they come from and what they do.</p></div>
    <div class="feature"><div class="fic"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="30" fill="none" stroke="#A3E635" stroke-width="7"/><ellipse cx="50" cy="50" rx="14" ry="30" fill="none" stroke="#A3E635" stroke-width="5"/><line x1="20" y1="50" x2="80" y2="50" stroke="#A3E635" stroke-width="5"/></svg></div><h4>AI-Search Ready</h4><p>Make sure ChatGPT, Perplexity &amp; Google AI can find and recommend you.</p></div>
    <div class="feature"><div class="fic"><svg viewBox="0 0 100 100"><circle cx="42" cy="42" r="24" fill="none" stroke="#A3E635" stroke-width="8"/><line x1="60" y1="60" x2="82" y2="82" stroke="#A3E635" stroke-width="8" stroke-linecap="round"/></svg></div><h4>Retargeting Pixels</h4><p>Bring visitors back with ads on Instagram, Facebook &amp; Google.</p></div>
    <div class="feature"><div class="fic"><svg viewBox="0 0 100 100"><path d="M22 32 Q22 24 30 24 L70 24 Q78 24 78 32 L78 58 Q78 66 70 66 L42 66 L28 78 L28 66 Q22 66 22 58 Z" fill="none" stroke="#A3E635" stroke-width="6" stroke-linejoin="round"/></svg></div><h4>Lead Capture</h4><p>Turn clicks into enquiries with forms, chat and click-to-WhatsApp.</p></div>
    <div class="feature"><div class="fic"><svg viewBox="0 0 100 100"><path d="M50 16 L80 27 V52 Q80 73 50 86 Q20 73 20 52 V27 Z" fill="none" stroke="#A3E635" stroke-width="7" stroke-linejoin="round"/><path d="M37 50 L47 60 L65 38" fill="none" stroke="#A3E635" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg></div><h4>Trust &amp; SEO</h4><p>SSL, privacy policy, schema, sitemap and the basics Google needs.</p></div>
    <div class="feature"><div class="fic"><svg viewBox="0 0 100 100"><rect x="30" y="20" width="40" height="60" rx="7" fill="none" stroke="#A3E635" stroke-width="6"/><line x1="44" y1="70" x2="56" y2="70" stroke="#A3E635" stroke-width="6" stroke-linecap="round"/></svg></div><h4>Mobile &amp; Speed</h4><p>Most traffic is mobile — we check it loads fast and looks right.</p></div>
  </div>
</div></section>

<section class="block" id="how"><div class="wrap">
  <p class="eyebrow">How it works</p>
  <h2 class="sec">From audit to more customers in 3 steps</h2>
  <div class="steps">
    <div class="step"><div class="n">1</div><h4>Free Audit</h4><p>Enter any website above. Get an instant 25-point report in plain language.</p></div>
    <div class="step"><div class="n">2</div><h4>We Fix It</h4><p>We install the missing tools — tracking, WhatsApp, retargeting, lead forms.</p></div>
    <div class="step"><div class="n">3</div><h4>You Get Leads</h4><p>Visitors get captured and followed up automatically. Enquiries now reach you.</p></div>
  </div>
</div></section>

<section class="block bg-light" id="pricing"><div class="wrap">
  <p class="eyebrow">Pricing</p>
  <h2 class="sec">Simple, honest pricing</h2>
  <p class="lead">The audit is free. You only pay if you want us to fix what we find.</p>
  <div class="price-grid">
    <div class="price"><h3>Audit Only</h3><div class="amt">Free</div><ul><li>Full 25-point audit</li><li>Plain-language report</li><li>Emailed to you</li><li>No obligation</li></ul><a class="btn btn-navy" style="width:100%;justify-content:center" onclick="focusUrl()">Start free</a></div>
    <div class="price feat"><h3>Audit + Setup</h3><div class="amt">₹15,000 <span>one-time</span></div><ul><li>Everything in Audit</li><li>GA4 + Clarity installed</li><li>WhatsApp + lead form</li><li>Meta Pixel + retargeting</li></ul><a class="btn btn-yellow" style="width:100%;justify-content:center" href="https://wa.me/919886650133?text=Hi%20Amit,%20I'd%20like%20the%20Audit%20+%20Setup%20package">Get started</a></div>
    <div class="price"><h3>Full + Monthly</h3><div class="amt">₹15,000 <span>+ ₹10k/mo</span></div><ul><li>Everything in Setup</li><li>AI chatbot + follow-up</li><li>Automated WhatsApp/email</li><li>Monthly reports</li></ul><a class="btn btn-navy" style="width:100%;justify-content:center" href="https://wa.me/919886650133?text=Hi%20Amit,%20I'd%20like%20the%20Full%20+%20Monthly%20package">Talk to us</a></div>
  </div>
</div></section>

<section class="block"><div class="wrap"><div class="band">
  <div><h3>An SEO guy tells you why Google can't rank you. <span class="hl">We tell you why your website isn't making money.</span></h3><p style="color:#cdd9f0;">Discovery, measurement, retargeting, conversion and AI search — the full funnel, in one scan.</p></div>
  <ul><li><span class="d">✓</span> Found by Google <b>and</b> AI assistants</li><li><span class="d">✓</span> Every visitor tracked &amp; understood</li><li><span class="d">✓</span> Ad money that actually works</li><li><span class="d">✓</span> Clicks that turn into customers</li></ul>
</div></div></section>

<footer><div class="wrap">
  <div class="foot">
    <div style="max-width:280px"><div class="logo" style="display:flex;align-items:center;gap:9px;font-weight:800;font-size:18px"><span class="mark" style="width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#A3E635,#65A30D);display:flex;align-items:center;justify-content:center"><svg width="18" height="18" viewBox="0 0 100 100"><circle cx="44" cy="42" r="24" fill="none" stroke="#0A1A40" stroke-width="8"/><path d="M34 44 L42 52 L58 34" fill="none" stroke="#0A1A40" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/><line x1="61" y1="61" x2="82" y2="82" stroke="#0A1A40" stroke-width="9" stroke-linecap="round"/></svg></span> The Website Auditor</div><p style="margin-top:8px">Find what's missing. Win more customers.</p></div>
    <div><h4>Contact</h4><a href="tel:+919886650133">+91 98866 50133</a><a href="mailto:amit.ahuja@thewebsiteauditor.com">amit.ahuja@thewebsiteauditor.com</a><a href="#">Bangalore, Karnataka · serving worldwide</a></div>
    <div><h4>Links</h4><a href="#check">What we check</a><a href="#how">How it works</a><a href="#pricing">Pricing</a></div>
  </div>
  <div class="bot">© 2026 The Website Auditor · Founded by Amit Ahuja · Bangalore, India<br>Privacy: we collect only details you submit, to respond to your enquiry. Compliant with India's DPDP Act 2023.</div>
</div></footer>

<a href="https://wa.me/919886650133?text=Hi%20Amit,%20I'd%20like%20a%20website%20audit" class="wa-float" title="WhatsApp">💬</a>

<script>
function focusUrl(){document.getElementById('audit').scrollIntoView({behavior:'smooth',block:'center'});document.getElementById('url').focus();}
function clearErr(){['url','name','email'].forEach(function(id){document.getElementById(id).style.outline='';});}
function showErr(id,msg){clearErr();var el=document.getElementById(id);el.focus();el.style.outline='3px solid #EF4444';document.getElementById('out').innerHTML='<div class="scorecard" style="border:1px solid #fecaca;background:#fef2f2;color:#b91c1c;font-weight:600">⚠️ '+msg+'</div>';}
async function run(){
  var url=document.getElementById('url').value.trim();
  var name=document.getElementById('name').value.trim();
  var email=document.getElementById('email').value.trim();
  var at=email.indexOf('@');
  if(!url){showErr('url','Please enter a website to audit.');return;}
  if(!name){showErr('name','Please enter your name — it is required.');return;}
  if(!email||at<1||email.indexOf('.',at)<0){showErr('email','Please enter a valid email — we send your full report there.');return;}
  clearErr();
  var deep=document.getElementById('deep').checked;
  var btn=document.getElementById('btn'); btn.disabled=true;
  document.getElementById('out').innerHTML='<div class="spin">'+(deep?'🌐 Deep scan — loading in a browser…':'🔍 Reading website code…')+'<div class="dots"><span></span><span></span><span></span></div></div>';
  try{
    var r=await fetch('/api/audit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,deep_scan:deep,email:email,name:name})});
    var d=await r.json();
    if(!d.ok)throw new Error(d.error||'Audit failed');
    show(d);
  }catch(e){
    document.getElementById('out').innerHTML='<div class="scorecard" style="border:1px solid #fecaca;background:#fef2f2;color:#b91c1c;font-weight:600">⚠️ '+e.message+'</div>';
  }finally{ btn.disabled=false; }
}
function tog(el){ el.parentNode.classList.toggle('open'); }
function show(d){
  var sc=d.score>=70?'#65A30D':d.score>=40?'#CA8A04':'#EF4444';
  var h='<div class="scorecard">';
  h+='<div class="scorehead"><div><div class="meta">AUDIT COMPLETE</div><div class="dom">'+d.domain+'</div><div class="meta">'+d.platform+' · '+d.scan_mode+' scan · '+(d.load_ms||0)+'ms</div></div><div class="score" style="color:'+sc+'">'+d.score+'%</div></div>';
  h+='<div class="stat-row"><div class="stat" style="background:#ecfccb"><div class="v" style="color:#65A30D">'+d.found+'</div><div class="s" style="color:#65A30D">Working</div></div>';
  if(d.uncertain>0)h+='<div class="stat" style="background:#fef9c3"><div class="v" style="color:#CA8A04">'+d.uncertain+'</div><div class="s" style="color:#CA8A04">Via GTM?</div></div>';
  h+='<div class="stat" style="background:#fee2e2"><div class="v" style="color:#EF4444">'+d.missing+'</div><div class="s" style="color:#EF4444">Missing</div></div>';
  h+='<div class="stat" style="background:#ffedd5"><div class="v" style="color:#EA580C">'+d.critical_gaps+'</div><div class="s" style="color:#EA580C">Critical</div></div></div>';
  if(d.email_sent)h+='<div class="emailnote" style="background:#ecfccb;color:#3f6212">📧 Full report sent to your email!</div>';
  else if(d.email_msg)h+='<div class="emailnote" style="background:#fef9c3;color:#854d0e">Note: email not sent ('+d.email_msg+')</div>';
  h+='</div>';
  h+='<div class="hint" style="margin:13px 0 2px">Tap any check below to see what it means and how to fix it.</div>';
  var lastCat='';
  d.checks.forEach(function(c){
    if(c.category&&c.category!==lastCat){ h+='<div class="cathead">'+c.category+'</div>'; lastCat=c.category; }
    var st=c.found?'ok':(c.uncertain?'unc':'no');
    var ic=c.found?(c.icon||'✓'):(c.uncertain?'❓':'❌');
    var bg=c.found?'background:#ecfccb;color:#3f6212':(c.uncertain?'background:#fef9c3;color:#854d0e':'background:#fee2e2;color:#b91c1c');
    var lbl=c.found?'✓ FOUND':(c.uncertain?'❓ MAYBE':'✗ MISSING');
    var det='<p><b>What it does:</b> '+c.description+'</p>';
    if(c.found){ det+='<p style="color:#3f6212"><b>✓ Set up correctly</b> on this website.</p>'; }
    else if(c.uncertain){ det+='<p>'+(c.warning||'A Google Tag Manager container is present, so this may be firing inside it. Run a deep scan to confirm.')+'</p>'; }
    else {
      det+='<p><b>Why it matters:</b> '+(c.missing_msg||'This is missing and worth adding to your site.')+'</p>';
      det+='<p class="m">Impact: '+c.impact+'  ·  Typical fix: '+c.fix_time+'  ·  Cost: '+c.cost+'</p>';
      det+='<a class="fixbtn" target="_blank" href="https://wa.me/919886650133?text='+encodeURIComponent('Hi Amit, I want to fix '+c.name+' on '+d.domain)+'">Fix this for me →</a>';
    }
    h+='<div class="chk '+st+'"><div class="chkhead" onclick="tog(this)"><span class="nm">'+ic+' '+c.name+'</span><span class="badge" style="'+bg+'">'+lbl+'</span><span class="caret">▸</span></div><div class="detail">'+det+'</div></div>';
  });
  document.getElementById('out').innerHTML=h;
}
</script>
</body>
</html>"""
