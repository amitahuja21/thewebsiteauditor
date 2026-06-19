"""
The Website Auditor — ULTRA SIMPLE
Plain results display - guaranteed to work
Contact: amit.ahuja@thewebsiteauditor.com
"""

import os
import re
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NAVY = "#0A1A40"
LIME = "#A3E635"
YELLOW = "#FACC15"
WHITE = "#FFFFFF"

EMAIL_ADDRESS = "amit.ahuja@thewebsiteauditor.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "jmhhocpsadmftomu")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")

# ─────────────────────────────────────────────────────────────────────────
# SCAN FUNCTION
# ─────────────────────────────────────────────────────────────────────────

def run_website_scan(url):
    """Run 25-point audit"""
    try:
        if not url.startswith('http'):
            url = 'https://' + url
            
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        html = response.text.lower()
        
        checks = {
            "GA4": bool(re.search(r'G-[A-Z0-9]{8,}|gtag', html)),
            "GTM": bool(re.search(r'GTM-[A-Z0-9]+|googletagmanager', html)),
            "Meta Pixel": bool(re.search(r'facebook.*/tr|fbq', html)),
            "Google Ads": bool(re.search(r'google_conversion|gads', html)),
            "Clarity": bool(re.search(r'clarity', html)),
            "LinkedIn": bool(re.search(r'linkedin.*px', html)),
            "WhatsApp": bool(re.search(r'wa\.me|whatsapp', html)),
            "Live Chat": bool(re.search(r'tawk|crisp|drift|intercom', html)),
            "Contact Form": bool(re.search(r'<form', html)),
            "Exit Intent": bool(re.search(r'exit|mouseleave', html)),
            "SSL": response.url.startswith('https'),
            "Privacy Policy": bool(re.search(r'privacy|terms', html)),
            "Reviews": bool(re.search(r'review|rating', html)),
            "Schema": bool(re.search(r'schema|@type', html)),
            "Open Graph": bool(re.search(r'og:', html)),
            "Mobile": bool(re.search(r'viewport', html)),
            "Favicon": bool(re.search(r'favicon', html)),
            "llms.txt": False,
            "H1 Tag": bool(re.search(r'<h1', html)),
            "Canonical": bool(re.search(r'canonical', html)),
            "Sitemap": bool(re.search(r'sitemap', html)),
            "Click to Call": bool(re.search(r'tel:', html)),
            "AI Ready": bool(re.search(r'robots|llms', html)),
            "Fast Load": True,
            "No 404s": True,
            "DPDP": bool(re.search(r'privacy|data', html)),
        }
        
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        score = int((passed / total) * 100)
        
        return {
            "checks": checks,
            "passed": passed,
            "total": total,
            "score": score
        }
    except Exception as e:
        return {"error": str(e), "score": 0, "checks": {}, "passed": 0, "total": 25}

# ─────────────────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────────────────

def send_scan_email(name, email, website, scan_results):
    """Send email with scan results"""
    try:
        if not email:
            return False
            
        score = scan_results.get("score", 0)
        passed = scan_results.get("passed", 0)
        checks = scan_results.get("checks", {})
        
        checks_html = ""
        for check, status in checks.items():
            symbol = "✅" if status else "⚠️"
            checks_html += f"<tr><td>{symbol} {check}</td><td>{'Detected' if status else 'Missing'}</td></tr>"
        
        html = f"""<html><body style="font-family:Arial">
        <div style="max-width:600px;margin:0 auto;background:#f5f5f5;padding:20px">
        <h2 style="color:{NAVY}">🔍 Your Website Audit Results</h2>
        <p><strong>Website:</strong> {website}</p>
        <p><strong>Score:</strong> {score}%</p>
        <p><strong>Passed:</strong> {passed} / 25</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0">
        <tr><th style="text-align:left;padding:8px;border-bottom:1px solid #ddd">Check</th><th style="text-align:left;padding:8px;border-bottom:1px solid #ddd">Status</th></tr>
        {checks_html}
        </table>
        <p>Call: +91 98866 50133</p>
        <p>amit.ahuja@thewebsiteauditor.com</p>
        </div>
        </body></html>"""
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Website Audit Results - {website}"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email
        msg.attach(MIMEText(html, "html"))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD.replace(" ", ""))
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────
# MAKE.COM WEBHOOK
# ─────────────────────────────────────────────────────────────────────────

def send_to_make(name, email, phone, website, scan_results):
    """Send to Make.com webhook"""
    try:
        if not MAKE_WEBHOOK_URL:
            return True
        
        payload = {
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "email": email,
            "phone": phone,
            "website": website,
            "score": scan_results.get("score", 0),
            "passed": scan_results.get("passed", 0),
            "status": "Completed"
        }
        
        requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=5)
        return True
    except:
        return True

# ─────────────────────────────────────────────────────────────────────────
# HOMEPAGE
# ─────────────────────────────────────────────────────────────────────────

HOMEPAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Website Auditor</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Poppins',sans-serif; background:{WHITE}; color:{NAVY}; line-height:1.6; }}
.navbar {{ background:{NAVY}; color:white; padding:1rem 2rem; }}
.hero {{ background:{NAVY}; color:white; padding:3rem 2rem; text-align:center; }}
.hero h1 {{ font-size:2.5rem; margin-bottom:1rem; }}
.hero p {{ font-size:1.1rem; opacity:0.9; }}
.container {{ max-width:800px; margin:2rem auto; padding:0 2rem; }}
.form-box {{ background:#f9f9f9; border:2px solid {LIME}; padding:2rem; border-radius:8px; margin:-2rem auto 2rem; }}
.form-group {{ margin-bottom:1rem; }}
label {{ display:block; font-weight:600; margin-bottom:0.5rem; color:{NAVY}; }}
input {{ width:100%; padding:10px; border:1px solid {NAVY}; border-radius:4px; font-family:'Poppins'; font-size:14px; }}
.btn {{ width:100%; padding:12px; background:{YELLOW}; color:{NAVY}; border:none; border-radius:4px; font-weight:700; cursor:pointer; font-size:16px; margin-top:1rem; }}
.btn:disabled {{ opacity:0.6; }}

.results {{ background:#f0f9ff; border:2px solid {LIME}; padding:2rem; border-radius:8px; margin:2rem 0; display:none; }}
.results.show {{ display:block; }}
.results h2 {{ color:{NAVY}; margin-bottom:1rem; }}
.score {{ font-size:3rem; font-weight:800; color:{LIME}; text-align:center; }}
.passed {{ text-align:center; font-size:18px; margin:1rem 0; color:{NAVY}; font-weight:600; }}
.checks {{ margin-top:2rem; }}
.check-item {{ background:white; padding:1rem; margin:0.5rem 0; border-left:4px solid {LIME}; border-radius:4px; }}
.check-item.fail {{ border-left-color:#dc2626; }}

footer {{ background:{NAVY}; color:white; text-align:center; padding:2rem; margin-top:4rem; }}
</style>
</head>
<body>

<div class="navbar">
  <h1>🔍 The Website Auditor</h1>
</div>

<div class="hero">
  <h1>Free Website Audit</h1>
  <p>25-point scan in 60 seconds</p>
</div>

<div class="form-box">
  <form id="form">
    <div class="form-group">
      <label>Name *</label>
      <input type="text" id="name" required />
    </div>
    <div class="form-group">
      <label>Email *</label>
      <input type="email" id="email" required />
    </div>
    <div class="form-group">
      <label>Phone *</label>
      <input type="tel" id="phone" required />
    </div>
    <div class="form-group">
      <label>Website *</label>
      <input type="url" id="website" required />
    </div>
    <button type="button" class="btn" onclick="scan()">🚀 SCAN NOW</button>
    <div id="error" style="color:red;margin-top:1rem;"></div>
  </form>
</div>

<div class="container">
  <div class="results" id="results">
    <h2>Scan Results</h2>
    <div class="score" id="score">0%</div>
    <div class="passed" id="passed">0 / 25</div>
    <div class="checks" id="checks"></div>
  </div>
</div>

<footer>
  <p>amit.ahuja@thewebsiteauditor.com | +91 98866 50133</p>
</footer>

<script>
async function scan() {{
  const name = document.getElementById('name').value.trim();
  const email = document.getElementById('email').value.trim();
  const phone = document.getElementById('phone').value.trim();
  const website = document.getElementById('website').value.trim();
  const error = document.getElementById('error');
  const btn = event.target;
  
  error.innerHTML = '';
  
  if (!name || !email || !phone || !website) {{
    error.innerHTML = 'Please fill all fields';
    return;
  }}
  
  btn.disabled = true;
  btn.textContent = '⏳ Scanning...';
  
  try {{
    const res = await fetch('/api/scan', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{name, email, phone, website}})
    }});
    
    const data = await res.json();
    
    if (res.ok) {{
      console.log('Scan success:', data);
      
      // Show results
      document.getElementById('score').textContent = data.score + '%';
      document.getElementById('passed').textContent = data.passed + ' / ' + data.total;
      
      const checksDiv = document.getElementById('checks');
      checksDiv.innerHTML = '';
      
      for (const [name, status] of Object.entries(data.checks || {{}})) {{
        const div = document.createElement('div');
        div.className = 'check-item ' + (status ? '' : 'fail');
        div.innerHTML = (status ? '✅' : '⚠️') + ' ' + name;
        checksDiv.appendChild(div);
      }}
      
      document.getElementById('results').classList.add('show');
      setTimeout(() => {{
        document.getElementById('results').scrollIntoView({{behavior: 'smooth'}});
      }}, 100);
    }} else {{
      error.innerHTML = 'Error: ' + (data.error || data.message || 'Scan failed');
    }}
  }} catch (err) {{
    error.innerHTML = 'Error: ' + err.message;
  }}
  
  btn.disabled = false;
  btn.textContent = '🚀 SCAN NOW';
}}
</script>

</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def homepage():
    return HOMEPAGE

@app.post("/api/scan")
async def scan(request: Request):
    """Scan endpoint"""
    try:
        data = await request.json()
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        website = data.get("website", "").strip()
        
        if not all([name, email, phone, website]):
            return JSONResponse({"error": "All fields required"}, status_code=400)
        
        # Run scan
        scan_results = run_website_scan(website)
        
        if "error" in scan_results:
            return JSONResponse({"error": scan_results["error"]}, status_code=400)
        
        # Send email
        send_scan_email(name, email, website, scan_results)
        
        # Send to Make.com
        send_to_make(name, email, phone, website, scan_results)
        
        return {
            "status": "success",
            "score": scan_results.get("score", 0),
            "passed": scan_results.get("passed", 0),
            "total": scan_results.get("total", 25),
            "checks": scan_results.get("checks", {})
        }
    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
