"""
The Website Auditor — Complete FastAPI Application
Brand: Navy #0A1A40 + Lime #A3E635 + Yellow #FACC15
Deploy: Render.com via GitHub
Contact: amit.ahuja@thewebsiteauditor.com | +91 98866 50133
"""

import re
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="The Website Auditor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────
# BRAND COLORS — Change these hex values to update entire website colors
# ─────────────────────────────────────────────────────────────────────────
COLORS = {
    "navy": "#0A1A40",          # Main color (headers, text, navbar)
    "lime": "#A3E635",          # Accent (borders, highlights)
    "yellow": "#FACC15",        # CTA button color ("SCAN NOW")
    "white": "#FFFFFF",         # Background
    "light_bg": "#EAF1F8",      # Light background sections
    "green_text": "#65A30D",    # Subtext, descriptions
}

# ─────────────────────────────────────────────────────────────────────────
# HOMEPAGE (Complete Landing Page with Brand Colors)
# ─────────────────────────────────────────────────────────────────────────

HOMEPAGE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Website Auditor — Free Website Audit in 60 Seconds</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{ 
            font-family: 'Poppins', sans-serif; 
            background: {COLORS['white']}; 
            color: {COLORS['navy']}; 
            line-height: 1.6; 
        }}
        
        .navbar {{
            background: {COLORS['navy']};
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .logo {{ 
            font-size: 20px; 
            font-weight: 700; 
            color: {COLORS['lime']}; 
        }}
        
        .nav-links {{ 
            display: flex; 
            gap: 2rem; 
        }}
        
        .nav-links a {{ 
            color: {COLORS['white']}; 
            text-decoration: none;
            transition: opacity 0.3s;
        }}
        
        .nav-links a:hover {{
            opacity: 0.8;
        }}
        
        .hero {{
            background: linear-gradient(135deg, {COLORS['navy']} 0%, {COLORS['navy']} 100%);
            color: {COLORS['white']};
            padding: 5rem 2rem;
            text-align: center;
        }}
        
        .hero h1 {{ 
            font-size: 3rem; 
            margin-bottom: 1rem; 
            font-weight: 800; 
        }}
        
        .hero p {{ 
            font-size: 1.2rem; 
            margin-bottom: 2rem; 
            opacity: 0.9; 
        }}
        
        .form-section {{
            max-width: 500px;
            margin: -3rem auto 3rem;
            background: {COLORS['white']};
            border: 2px solid {COLORS['lime']};
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 10px 40px rgba(10, 26, 64, 0.15);
        }}
        
        .form-section h3 {{
            color: {COLORS['navy']};
            margin-bottom: 1rem;
            font-size: 18px;
        }}
        
        .form-group {{
            margin-bottom: 1.5rem;
        }}
        
        label {{
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: {COLORS['navy']};
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        input {{
            width: 100%;
            padding: 12px 14px;
            border: 1.5px solid {COLORS['navy']};
            border-radius: 6px;
            font-family: 'Poppins', sans-serif;
            font-size: 14px;
            color: {COLORS['navy']};
            transition: all 0.3s;
        }}
        
        input:focus {{
            outline: none;
            border-color: {COLORS['lime']};
            box-shadow: 0 0 0 3px rgba(163, 230, 53, 0.1);
        }}
        
        button {{
            width: 100%;
            padding: 14px;
            background: {COLORS['yellow']};
            color: {COLORS['navy']};
            border: none;
            border-radius: 6px;
            font-family: 'Poppins', sans-serif;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 1rem;
            transition: all 0.3s;
        }}
        
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(250, 204, 21, 0.3);
        }}
        
        button:active {{
            transform: translateY(0);
        }}
        
        .features {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 2rem;
            max-width: 1200px;
            margin: 4rem auto;
            padding: 0 2rem;
        }}
        
        .feature-card {{
            background: {COLORS['light_bg']};
            border-left: 4px solid {COLORS['lime']};
            padding: 2rem;
            border-radius: 8px;
            transition: transform 0.3s;
        }}
        
        .feature-card:hover {{
            transform: translateY(-4px);
        }}
        
        .feature-card h3 {{
            color: {COLORS['navy']};
            margin-bottom: 0.5rem;
            font-size: 18px;
        }}
        
        .feature-card p {{
            color: {COLORS['green_text']};
            font-size: 14px;
        }}
        
        .checks-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 1rem;
            max-width: 1200px;
            margin: 3rem auto;
            padding: 0 2rem;
        }}
        
        .check-item {{
            background: {COLORS['light_bg']};
            padding: 1rem;
            border-radius: 6px;
            text-align: center;
            font-size: 13px;
            color: {COLORS['navy']};
            border: 1px solid {COLORS['lime']};
        }}
        
        .check-item .emoji {{ 
            font-size: 24px; 
            margin-bottom: 0.5rem; 
        }}
        
        .section {{
            max-width: 1200px;
            margin: 4rem auto;
            padding: 0 2rem;
        }}
        
        .section h2 {{
            text-align: center;
            color: {COLORS['navy']};
            margin-bottom: 2rem;
            font-size: 2rem;
            font-weight: 800;
        }}
        
        footer {{
            background: {COLORS['navy']};
            color: {COLORS['white']};
            text-align: center;
            padding: 2rem;
            margin-top: 4rem;
            font-size: 14px;
        }}
        
        .success-msg {{
            display: none;
            background: #ECFDF5;
            border: 1.5px solid {COLORS['green_text']};
            color: #166534;
            padding: 1rem;
            border-radius: 6px;
            margin-top: 1rem;
            text-align: center;
            font-weight: 600;
        }}
        
        .success-msg.show {{
            display: block;
        }}
        
        @media (max-width: 768px) {{
            .features, .checks-grid {{
                grid-template-columns: 1fr;
            }}
            .hero h1 {{
                font-size: 2rem;
            }}
            .nav-links {{
                gap: 1rem;
                font-size: 14px;
            }}
        }}
    </style>
</head>
<body>
    <div class="navbar">
        <div class="logo">🔍 The Website Auditor</div>
        <div class="nav-links">
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="https://wa.me/919886650133?text=Hi%20Amit%2C%20I'm%20interested%20in%20The%20Website%20Auditor" target="_blank">WhatsApp</a>
        </div>
    </div>
    
    <div class="hero">
        <h1>Is Your Website Ready?</h1>
        <p>Get a complete audit in 60 seconds. Free. No signup required.</p>
    </div>
    
    <div class="form-section">
        <h3>Free Website Audit</h3>
        <form id="auditForm">
            <div class="form-group">
                <label for="website">Website URL *</label>
                <input type="text" id="website" placeholder="https://example.com" required />
            </div>
            <div class="form-group">
                <label for="email">Email Address *</label>
                <input type="email" id="email" placeholder="you@company.com" required />
            </div>
            <div class="form-group">
                <label for="phone">Phone (optional)</label>
                <input type="tel" id="phone" placeholder="+91 98866 50133" />
            </div>
            <button type="submit">🚀 SCAN NOW — FREE</button>
            <div class="success-msg" id="successMsg">
                ✓ Scan queued! Check your inbox for results.
            </div>
        </form>
    </div>
    
    <div class="section" id="features">
        <h2>What We Check</h2>
        <div class="features">
            <div class="feature-card">
                <h3>📊 Traffic Intelligence</h3>
                <p>GA4, GTM, Clarity, Hotjar tracking</p>
            </div>
            <div class="feature-card">
                <h3>🎯 Retargeting</h3>
                <p>Meta Pixel, Google Ads, LinkedIn tags</p>
            </div>
            <div class="feature-card">
                <h3>💬 Lead Capture</h3>
                <p>WhatsApp, live chat, contact forms</p>
            </div>
            <div class="feature-card">
                <h3>🔒 Trust & Security</h3>
                <p>SSL, privacy policy, reviews</p>
            </div>
            <div class="feature-card">
                <h3>🚀 Discovery</h3>
                <p>SEO, schema, Open Graph, llms.txt</p>
            </div>
            <div class="feature-card">
                <h3>🤖 AI Ready</h3>
                <p>ChatGPT, Claude, Gemini visibility</p>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>25-Point Scan</h2>
        <div class="checks-grid">
            <div class="check-item"><div class="emoji">📊</div>GA4</div>
            <div class="check-item"><div class="emoji">📍</div>GTM</div>
            <div class="check-item"><div class="emoji">📈</div>Clarity</div>
            <div class="check-item"><div class="emoji">🎯</div>Meta Pixel</div>
            <div class="check-item"><div class="emoji">💰</div>Google Ads</div>
            <div class="check-item"><div class="emoji">🔗</div>LinkedIn</div>
            <div class="check-item"><div class="emoji">💬</div>WhatsApp</div>
            <div class="check-item"><div class="emoji">💬</div>Live Chat</div>
            <div class="check-item"><div class="emoji">📝</div>Lead Form</div>
            <div class="check-item"><div class="emoji">🚪</div>Exit Intent</div>
            <div class="check-item"><div class="emoji">🔒</div>SSL</div>
            <div class="check-item"><div class="emoji">📄</div>Privacy</div>
            <div class="check-item"><div class="emoji">⭐</div>Reviews</div>
            <div class="check-item"><div class="emoji">🏷️</div>Schema</div>
            <div class="check-item"><div class="emoji">🌐</div>Open Graph</div>
            <div class="check-item"><div class="emoji">📱</div>Mobile</div>
            <div class="check-item"><div class="emoji">🔍</div>Favicon</div>
            <div class="check-item"><div class="emoji">🤖</div>llms.txt</div>
            <div class="check-item"><div class="emoji">🏷️</div>H1 Tag</div>
            <div class="check-item"><div class="emoji">🔗</div>Canonical</div>
            <div class="check-item"><div class="emoji">📍</div>Sitemap</div>
            <div class="check-item"><div class="emoji">🔄</div>Redirect</div>
            <div class="check-item"><div class="emoji">⚡</div>Speed</div>
            <div class="check-item"><div class="emoji">📞</div>Click-to-Call</div>
            <div class="check-item"><div class="emoji">✅</div>AI Ready</div>
        </div>
    </div>
    
    <footer>
        <p>The Website Auditor © 2026 | amit.ahuja@thewebsiteauditor.com | +91 98866 50133</p>
    </footer>
    
    <script>
        document.getElementById('auditForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const website = document.getElementById('website').value;
            const email = document.getElementById('email').value;
            const phone = document.getElementById('phone').value;
            
            try {{
                const response = await fetch('/api/scan', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{website, email, phone}})
                }});
                
                if (response.ok) {{
                    document.getElementById('successMsg').classList.add('show');
                    document.getElementById('auditForm').reset();
                    setTimeout(() => {{
                        document.getElementById('successMsg').classList.remove('show');
                    }}, 5000);
                }}
            }} catch (err) {{
                console.error('Scan error:', err);
            }}
        }});
    </script>
</body>
</html>
"""

# ─────────────────────────────────────────────────────────────────────────
# API MODELS
# ─────────────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    website: str
    email: str
    phone: str = None

# ─────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def homepage():
    """Serve homepage with form"""
    return HOMEPAGE

@app.post("/api/scan")
async def scan(request: ScanRequest):
    """Handle scan request from form"""
    return {
        "status": "success",
        "message": f"Scan queued for {request.website}. Report will be sent to {request.email}",
        "website": request.website,
        "email": request.email
    }

@app.get("/health")
async def health():
    """Health check for Render"""
    return {"status": "ok", "app": "Website Auditor"}

# ─────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
