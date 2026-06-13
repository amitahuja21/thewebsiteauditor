# The Website Auditor — Complete Site + Tool

ONE web page that:
1. Looks like a professional homepage (hero, how-it-works, pricing)
2. Runs a live 25-point audit on any website the visitor enters
3. Emails the full report to the visitor (and a lead alert to you)

Built for: Amit Ahuja · thewebsiteauditor.com · +91 98866 50133

## Run on your computer
    pip install -r requirements.txt
    playwright install chromium          (one time, for deep scan)
    uvicorn main:app --port 8000
Open http://localhost:8000

## Deploy on Render (free) — this is how it goes live on your domain

1. Put main.py, requirements.txt, README.md in a GitHub repo
2. render.com -> New -> Web Service -> connect the repo
3. Build command:
       pip install -r requirements.txt && playwright install --with-deps chromium
4. Start command:
       uvicorn main:app --host 0.0.0.0 --port $PORT
5. Render gives you a URL like thewebsiteauditor.onrender.com
6. Settings -> Custom Domain -> add thewebsiteauditor.com
7. Render shows DNS records -> paste them in Squarespace (your domain's DNS)

Your Google Workspace email keeps working — different DNS records.

## EMAIL SETUP (so reports actually send)

The tool sends email via SMTP. With Google Workspace:

1. Turn on 2-Step Verification for amit.ahuja@thewebsiteauditor.com
2. Create an "App Password" (Google Account -> Security -> App Passwords)
3. In Render -> Environment, add these variables:
       SMTP_HOST   = smtp.gmail.com
       SMTP_PORT   = 587
       SMTP_USER   = amit.ahuja@thewebsiteauditor.com
       SMTP_PASS   = (the 16-character app password)
       FROM_EMAIL  = amit.ahuja@thewebsiteauditor.com
       OWNER_EMAIL = amit.ahuja@thewebsiteauditor.com

Without these, the audit still works — it just won't email the report
(it shows a small note instead). Add them anytime to switch email on.

## Two scan modes
FAST (default): reads raw HTML, ~1-2 sec. Great for SME sites.
DEEP (checkbox): loads page in real browser, catches JS-injected tools.

## The 25 checks
Traffic: GA4, old-UA detection, Tag Manager
Behaviour: Microsoft Clarity, Hotjar
Retargeting: Meta Pixel, Google Ads, LinkedIn
Lead Capture: WhatsApp, live chat, forms, exit popups, click-to-call
Trust: SSL, privacy policy, testimonials
SEO: schema, Open Graph, meta description, sitemap, mobile, favicon
AI Readiness: llms.txt, H1 structure, canonical
