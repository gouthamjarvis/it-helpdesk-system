from flask import Flask, request, redirect, url_for, session, make_response
import sqlite3
import csv
import io
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "servicedeskSECRET2024!"   # change this in production

DB_NAME = "complaints.db"

# ── Admin credentials (change these) ──────────────────────────────────────────
ADMIN_USERS = {
    "admin":   "Admin@1234",
    "goutham": "goutham@12",
}

# ─────────────────────────── DATABASE ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            location    TEXT,
            issue       TEXT,
            priority    TEXT,
            status      TEXT,
            assigned_to TEXT,
            solution    TEXT,
            created_at  TEXT,
            category    TEXT,
            ticket_no   TEXT,
            closed_at   TEXT
        )
    """)
    # Migrate old databases
    existing = [row[1] for row in c.execute("PRAGMA table_info(complaints)")]
    for col, typ in [("category","TEXT"), ("ticket_no","TEXT"), ("closed_at","TEXT")]:
        if col not in existing:
            c.execute(f"ALTER TABLE complaints ADD COLUMN {col} {typ}")
    conn.commit()
    conn.close()

init_db()

# ─────────────────────────── HELPERS ──────────────────────────────────────────
def ticket_number(id_):
    return f"INC{str(id_).zfill(7)}"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def priority_badge(p):
    cls = {"High": "b-high", "Medium": "b-medium", "Low": "b-low"}.get(p, "b-low")
    return f'<span class="badge {cls}">{p}</span>'

def status_badge(s):
    cls = {"Open":"b-open","Assigned":"b-assigned","In Progress":"b-inprogress",
           "Resolved":"b-resolved","Closed":"b-closed"}.get(s, "b-open")
    return f'<span class="badge {cls}">{s}</span>'

# ─────────────────────────── SHARED CSS ───────────────────────────────────────
BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2230;--surface3:#21262d;
  --border:#30363d;--border2:#21262d;--text:#e6edf3;--muted:#8b949e;
  --accent:#2563eb;--accent2:#1d4ed8;
  --green:#16a34a;--green-l:#4ade80;--green-bg:rgba(22,163,74,.12);
  --red:#dc2626;--red-l:#f87171;--red-bg:rgba(220,38,38,.12);
  --yellow:#d97706;--yellow-l:#fbbf24;--yellow-bg:rgba(217,119,6,.12);
  --blue-l:#60a5fa;--blue-bg:rgba(37,99,235,.12);
  --purple:#7c3aed;--purple-l:#a78bfa;--purple-bg:rgba(124,58,237,.12);
  --cyan-l:#22d3ee;--cyan-bg:rgba(8,145,178,.12);
  --radius:10px;--sidebar-w:252px;--topbar-h:56px;
  --font:'DM Sans',sans-serif;--mono:'JetBrains Mono',monospace;
}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px;line-height:1.5}

/* ── TOPBAR ── */
.topbar{position:fixed;top:0;left:0;right:0;height:var(--topbar-h);background:var(--surface);
  border-bottom:1px solid var(--border);display:flex;align-items:center;
  justify-content:space-between;padding:0 22px;z-index:100}
.tb-brand{display:flex;align-items:center;gap:10px}
.tb-logo{width:30px;height:30px;background:var(--accent);border-radius:7px;
  display:grid;place-items:center}
.tb-logo svg{width:16px;height:16px}
.tb-title{font-weight:700;font-size:15px;letter-spacing:-.3px}
.tb-title span{color:var(--muted);font-weight:400}
.tb-right{display:flex;align-items:center;gap:12px}
.tb-chip{background:var(--accent);color:#fff;padding:3px 10px;border-radius:20px;font-size:11.5px;font-weight:600}
.tb-user{width:32px;height:32px;border-radius:50%;background:var(--purple);
  display:grid;place-items:center;font-weight:700;font-size:12px}
.tb-logout{color:var(--muted);font-size:12.5px;text-decoration:none;
  padding:5px 10px;border-radius:6px;border:1px solid var(--border)}
.tb-logout:hover{color:var(--text);background:var(--surface2)}

/* ── SIDEBAR ── */
.sidebar{position:fixed;top:var(--topbar-h);left:0;width:var(--sidebar-w);
  height:calc(100vh - var(--topbar-h));background:var(--surface);
  border-right:1px solid var(--border);padding:16px 10px;overflow-y:auto}
.nav-label{font-size:10.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);padding:0 10px;margin:16px 0 5px}
.nav-label:first-child{margin-top:0}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:7px;
  color:var(--muted);text-decoration:none;font-size:13.5px;font-weight:500;transition:.12s}
.nav-item:hover,.nav-item.active{background:var(--surface2);color:var(--text)}
.nav-item.active{color:var(--accent)}
.nav-item svg{width:15px;height:15px;flex-shrink:0}
.nav-badge{margin-left:auto;background:var(--red);color:#fff;font-size:10px;
  font-weight:700;padding:1px 6px;border-radius:20px}

/* ── MAIN ── */
.main{margin-left:var(--sidebar-w);padding:calc(var(--topbar-h) + 26px) 26px 30px;min-height:100vh}
.main-full{padding:calc(var(--topbar-h) + 40px) 26px 30px}

/* ── PAGE HEADER ── */
.page-hd{margin-bottom:22px}
.page-hd h1{font-size:21px;font-weight:700;letter-spacing:-.4px}
.page-hd p{color:var(--muted);font-size:13px;margin-top:3px}
.breadcrumb{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);margin-bottom:8px}
.breadcrumb a{color:var(--muted);text-decoration:none}
.breadcrumb a:hover{color:var(--text)}

/* ── STATS ── */
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 18px}
.stat-label{font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:7px}
.stat-value{font-size:26px;font-weight:700;letter-spacing:-1px;font-family:var(--mono)}
.stat-sub{font-size:11.5px;color:var(--muted);margin-top:3px}
.stat-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}

/* ── TABLE ── */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.table-hdr{display:flex;align-items:center;justify-content:space-between;
  padding:14px 18px;border-bottom:1px solid var(--border)}
.table-title{font-weight:600;font-size:14px}
.tbl-actions{display:flex;gap:8px}
table{width:100%;border-collapse:collapse}
thead{background:var(--bg)}
th{padding:10px 14px;text-align:left;font-size:10.5px;font-weight:600;letter-spacing:.07em;
  text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border2)}
td{padding:12px 14px;border-bottom:1px solid var(--border2);font-size:13px;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surface2)}

/* ── BADGES ── */
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:20px;
  font-size:11px;font-weight:600;letter-spacing:.02em}
.badge::before{content:'';width:5px;height:5px;border-radius:50%;background:currentColor;opacity:.7}
.b-high{background:var(--red-bg);color:var(--red-l)}
.b-medium{background:var(--yellow-bg);color:var(--yellow-l)}
.b-low{background:var(--green-bg);color:var(--green-l)}
.b-open{background:var(--red-bg);color:var(--red-l)}
.b-assigned{background:var(--yellow-bg);color:var(--yellow-l)}
.b-inprogress{background:var(--cyan-bg);color:var(--cyan-l)}
.b-resolved{background:var(--blue-bg);color:var(--blue-l)}
.b-closed{background:var(--green-bg);color:var(--green-l)}

/* ── TICKET NO ── */
.tno{font-family:var(--mono);font-size:11.5px;color:var(--accent);
  background:var(--blue-bg);padding:2px 7px;border-radius:4px}

/* ── BUTTONS ── */
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 13px;border-radius:7px;
  border:none;font-family:var(--font);font-size:13px;font-weight:500;
  cursor:pointer;transition:.12s;text-decoration:none}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent2)}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{background:var(--border2)}
.btn-success{background:var(--green-bg);color:var(--green-l);border:1px solid rgba(22,163,74,.25)}
.btn-success:hover{background:rgba(22,163,74,.2)}
.btn-danger{background:var(--red-bg);color:var(--red-l);border:1px solid rgba(220,38,38,.25)}
.btn-danger:hover{background:rgba(220,38,38,.2)}
.btn-export{background:var(--green-bg);color:var(--green-l);border:1px solid rgba(22,163,74,.3)}
.btn-export:hover{background:rgba(22,163,74,.22)}
.btn-sm{padding:5px 10px;font-size:12px}

/* ── FILTER BAR ── */
.filter-bar{display:flex;align-items:center;gap:8px;padding:12px 18px;
  border-bottom:1px solid var(--border);background:var(--bg);flex-wrap:wrap}
.filter-bar select,.filter-bar input{
  background:var(--surface);border:1px solid var(--border);border-radius:7px;
  padding:6px 10px;color:var(--text);font-size:12.5px;font-family:var(--font);outline:none}
.filter-bar select:focus,.filter-bar input:focus{border-color:var(--accent)}
.filter-sep{width:1px;height:22px;background:var(--border);margin:0 4px}
.filter-label{font-size:11.5px;color:var(--muted);font-weight:500}

/* ── SLIDE PANEL ── */
.panel{display:none;position:fixed;top:0;right:0;width:500px;height:100vh;
  background:var(--surface);border-left:1px solid var(--border);z-index:200;
  overflow-y:auto;box-shadow:-10px 0 50px rgba(0,0,0,.5)}
.panel.open{display:block;animation:slideIn .2s ease}
@keyframes slideIn{from{transform:translateX(30px);opacity:0}to{transform:none;opacity:1}}
.panel-head{padding:18px 22px;border-bottom:1px solid var(--border);position:sticky;
  top:0;background:var(--surface);z-index:1;display:flex;align-items:center;justify-content:space-between}
.panel-close{background:none;border:none;color:var(--muted);cursor:pointer;font-size:18px;
  width:28px;height:28px;border-radius:6px;display:grid;place-items:center}
.panel-close:hover{background:var(--surface2);color:var(--text)}
.panel-body{padding:22px}
.field-group{margin-bottom:18px}
.field-label{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted);font-weight:600;margin-bottom:5px}
.field-val{font-size:13.5px;line-height:1.6}
.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}
.info-item .field-label{margin-bottom:3px}

/* ── UPDATE FORM IN PANEL ── */
.uf{background:var(--bg);border:1px solid var(--border2);border-radius:8px;padding:16px;margin-top:4px}
.uf label{display:block;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);font-weight:600;margin-bottom:5px}
.uf input,.uf select,.uf textarea{
  width:100%;background:var(--surface);border:1px solid var(--border);
  border-radius:6px;padding:8px 10px;color:var(--text);font-family:var(--font);
  font-size:13px;margin-bottom:12px;outline:none;transition:.12s}
.uf input:focus,.uf select:focus,.uf textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(37,99,235,.12)}
.uf textarea{resize:vertical;min-height:90px}
.uf-row{display:flex;gap:8px}

/* ── FORM CARD ── */
.form-card{background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;max-width:700px;margin:0 auto}
.form-sec{padding:18px 22px;border-bottom:1px solid var(--border2)}
.form-sec-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted);font-weight:600;margin-bottom:14px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.fg{margin-bottom:12px}
.fg label{display:block;font-size:12px;font-weight:500;color:var(--muted);margin-bottom:5px}
.fg input,.fg textarea,.fg select{
  width:100%;background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:9px 12px;color:var(--text);font-family:var(--font);font-size:13.5px;
  transition:.12s;outline:none}
.fg input:focus,.fg textarea:focus,.fg select:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(37,99,235,.12)}
.fg textarea{resize:vertical;min-height:100px}
.form-footer{padding:16px 22px;display:flex;justify-content:flex-end;gap:10px}

/* ── EXPORT SECTION ── */
.export-bar{display:flex;align-items:center;gap:8px;padding:12px 18px;
  background:var(--surface2);border-bottom:1px solid var(--border);flex-wrap:wrap}
.export-bar select{background:var(--surface);border:1px solid var(--border);border-radius:6px;
  padding:5px 9px;color:var(--text);font-family:var(--font);font-size:12px;outline:none}

/* ── LOGIN PAGE ── */
.login-wrap{min-height:100vh;display:grid;place-items:center;background:var(--bg)}
.login-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:36px 40px;width:380px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
.login-logo{width:44px;height:44px;background:var(--accent);border-radius:11px;
  display:grid;place-items:center;margin-bottom:18px}
.login-logo svg{width:22px;height:22px}
.login-card h2{font-size:20px;font-weight:700;letter-spacing:-.3px;margin-bottom:4px}
.login-card p{color:var(--muted);font-size:13px;margin-bottom:26px}
.login-card .fg{margin-bottom:14px}
.error-msg{background:var(--red-bg);border:1px solid rgba(220,38,38,.3);
  color:var(--red-l);padding:10px 14px;border-radius:7px;font-size:13px;margin-bottom:16px}

/* ── LANDING / HOME ── */
.landing{min-height:100vh;display:flex;flex-direction:column}
.landing-hero{background:linear-gradient(135deg,var(--surface) 0%,var(--bg) 100%);
  border-bottom:1px solid var(--border);padding:80px 40px 60px;text-align:center}
.landing-hero h1{font-size:36px;font-weight:700;letter-spacing:-.8px;margin-bottom:10px}
.landing-hero h1 span{color:var(--accent)}
.landing-hero p{color:var(--muted);font-size:15px;max-width:480px;margin:0 auto 30px}
.landing-body{display:grid;grid-template-columns:1fr 380px;gap:0;flex:1}
.landing-form-col{padding:40px;border-right:1px solid var(--border)}
.landing-side{padding:40px;background:var(--surface)}
.side-card{background:var(--bg);border:1px solid var(--border);border-radius:10px;
  padding:20px;margin-bottom:16px}
.side-card h4{font-size:13px;font-weight:600;margin-bottom:4px}
.side-card p{font-size:12.5px;color:var(--muted);line-height:1.6}
.side-icon{width:32px;height:32px;border-radius:8px;display:grid;place-items:center;margin-bottom:10px}

/* ── OVERLAY ── */
#overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:190}

/* ── TOAST ── */
.toast{position:fixed;bottom:22px;right:22px;z-index:999;background:var(--surface);
  border:1px solid var(--border);border-left:3px solid var(--green);border-radius:8px;
  padding:13px 16px;display:none;align-items:center;gap:9px;
  box-shadow:0 8px 32px rgba(0,0,0,.4);font-size:13.5px;
  animation:toastIn .25s ease}
.toast.show{display:flex}
@keyframes toastIn{from{transform:translateY(10px);opacity:0}to{transform:none;opacity:1}}

/* ── EMPTY ── */
.empty{text-align:center;padding:50px 20px;color:var(--muted)}
.empty svg{width:44px;height:44px;opacity:.3;margin-bottom:12px}
.empty h3{font-size:15px;color:var(--text);margin-bottom:4px}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* ── DIVIDER ── */
hr.div{border:none;border-top:1px solid var(--border);margin:18px 0}
</style>
"""

def topbar(show_logout=True, username=""):
    logout = f'<a href="/admin/logout" class="tb-logout">Logout</a>' if show_logout else ""
    uname  = f'<div class="tb-user">{username[0].upper() if username else "A"}</div>' if show_logout else ""
    utext  = f'<span style="font-size:12px;color:var(--muted)">{username}</span>' if username else ""
    return f"""
<div class="topbar">
  <div class="tb-brand">
    <div class="tb-logo"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div>
    <div class="tb-title">SMILES IT <span>Helpdesk</span></div>
  </div>
  <div class="tb-right">
    <div class="tb-chip">IT Support</div>
    {utext}{uname}{logout}
  </div>
</div>"""

def sidebar(active="dashboard", open_count=0):
    nav = [
        ("dashboard", "/admin",          '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',  "Dashboard"),
        ("tickets",   "/admin/tickets",  '<path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>',  "All Tickets"),
        ("export",    "/admin/export",   '<path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>',  "Export Report"),
    ]
    badge = f'<span class="nav-badge">{open_count}</span>' if open_count else ""
    html  = '<div class="sidebar">'
    html += '<div class="nav-label">Main</div>'
    for key, href, icon_d, label in nav:
        cls  = "nav-item active" if active==key else "nav-item"
        nb   = badge if key=="tickets" else ""
        html += f'<a href="{href}" class="{cls}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">{icon_d}</svg>{label}{nb}</a>'
    html += '<div class="nav-label" style="margin-top:20px">Quick</div>'
    html += '<a href="/" class="nav-item" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 4v16m8-8H4"/></svg>New Ticket</a>'
    html += '</div>'
    return html

# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """Landing page — user complaint form + admin login link."""
    return f"""<!DOCTYPE html><html lang="en">
<head><title>SMILES IT Helpdesk — Raise a Ticket</title>{BASE_STYLE}</head>
<body>

<!-- minimal topbar without login -->
<div class="topbar">
  <div class="tb-brand">
    <div class="tb-logo"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div>
    <div class="tb-title">SMILES IT <span>Helpdesk</span></div>
  </div>
  <div class="tb-right">
    <a href="/admin/login" class="btn btn-ghost btn-sm">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3"/></svg>
      Admin Login
    </a>
  </div>
</div>

<div class="landing" style="padding-top:var(--topbar-h)">

  <!-- HERO -->
  <div class="landing-hero">
    <h1>SMILES IT <span>Helpdesk</span> Portal</h1>
    <p>Submit your IT support request below. Our team will pick it up and get back to you as quickly as possible.</p>
    <div style="display:flex;gap:10px;justify-content:center;margin-bottom:22px">
      <span class="badge b-open" style="font-size:12px">Fast Response</span>
      <span class="badge b-resolved" style="font-size:12px">Tracked</span>
      <span class="badge b-closed" style="font-size:12px">Resolved</span>
    </div>

    <!-- CALL BANNER -->
    <div style="display:inline-flex;align-items:center;gap:14px;
      background:rgba(37,99,235,.12);border:1px solid rgba(37,99,235,.3);
      border-radius:12px;padding:13px 28px;margin-top:4px">
      <div style="width:38px;height:38px;background:var(--accent);border-radius:50%;
        display:grid;place-items:center;flex-shrink:0">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2">
          <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.09 9.81 19.79 19.79 0 01.05 1.18 2 2 0 012 0h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 14.92z"/></svg>
      </div>
      <div style="text-align:left">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--blue-l);font-weight:600;margin-bottom:2px">Prefer to call us?</div>
        <div style="font-size:22px;font-weight:700;letter-spacing:-.5px;font-family:var(--mono)">
          722
          <span style="font-size:13px;font-weight:500;color:var(--muted);font-family:var(--font);margin-left:6px">SMILES IT Helpdesk</span>
        </div>
      </div>
    </div>

  </div>

  <div class="landing-body">

    <!-- FORM -->
    <div class="landing-form-col">
      <h2 style="font-size:17px;font-weight:700;margin-bottom:18px">Raise a New Ticket</h2>

      <form method="POST" action="/submit">

        <div class="form-row" style="margin-bottom:12px">
          <div class="fg" style="margin:0">
            <label>Full Name *</label>
            <input name="name" placeholder="Your full name" required>
          </div>
          <div class="fg" style="margin:0">
            <label>Department / Location *</label>
            <input name="location" placeholder="e.g. Finance — Floor 2" required>
          </div>
        </div>

        <div class="form-row" style="margin-bottom:12px">
          <div class="fg" style="margin:0">
            <label>Category</label>
            <select name="category">
              <option>Hardware</option>
              <option>Software</option>
              <option>Network</option>
              <option>Access / Permissions</option>
              <option>Email</option>
              <option>Server / Infrastructure</option>
              <option>Printer / Peripherals</option>
              <option>Other</option>
            </select>
          </div>
          <div class="fg" style="margin:0">
            <label>Priority</label>
            <select name="priority">
              <option>Low</option>
              <option selected>Medium</option>
              <option>High</option>
            </select>
          </div>
        </div>

        <div class="fg">
          <label>Issue Description *</label>
          <textarea name="issue" rows="5"
            placeholder="Describe the issue — what happened, since when, what you've tried..." required></textarea>
        </div>

        <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:11px">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M5 12h14M12 5l7 7-7 7"/></svg>
          Submit Ticket
        </button>

      </form>
    </div>

    <!-- SIDE INFO -->
    <div class="landing-side">
      <h3 style="font-size:14px;font-weight:600;margin-bottom:14px;color:var(--muted)">How it works</h3>

      <div class="side-card">
        <div class="side-icon" style="background:var(--blue-bg)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--blue-l)" stroke-width="2">
            <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></div>
        <h4>1. Fill the form</h4>
        <p>Describe your issue, select category and priority. Takes less than a minute.</p>
      </div>

      <div class="side-card">
        <div class="side-icon" style="background:var(--yellow-bg)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--yellow-l)" stroke-width="2">
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg></div>
        <h4>2. We assign it</h4>
        <p>Our IT admin assigns the ticket to the right technician based on priority.</p>
      </div>

      <div class="side-card">
        <div class="side-icon" style="background:var(--green-bg)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--green-l)" stroke-width="2">
            <path d="M20 6L9 17l-5-5"/></svg></div>
        <h4>3. Issue resolved</h4>
        <p>You get notified, solution is documented, and the ticket is closed.</p>
      </div>

      <hr class="div">

      <!-- CALL CARD -->
      <div style="background:var(--bg);border:1px solid rgba(37,99,235,.3);border-radius:10px;padding:16px;margin-bottom:14px;display:flex;align-items:center;gap:12px">
        <div style="width:34px;height:34px;background:var(--accent);border-radius:50%;display:grid;place-items:center;flex-shrink:0">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2">
            <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.09 9.81 19.79 19.79 0 01.05 1.18 2 2 0 012 0h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 14.92z"/></svg>
        </div>
        <div>
          <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--blue-l);font-weight:600;margin-bottom:2px">Call Helpdesk</div>
          <div style="font-size:19px;font-weight:700;font-family:var(--mono);letter-spacing:-.3px">722</div>
          <div style="font-size:11.5px;color:var(--muted)">SMILES IT Helpdesk</div>
        </div>
      </div>

      <p style="font-size:12px;color:var(--muted);text-align:center">
        IT Admin? <a href="/admin/login" style="color:var(--accent)">Login to Dashboard →</a>
      </p>
    </div>

  </div>
</div>
</body></html>"""


@app.route('/submit', methods=['POST'])
def submit():
    name     = request.form['name']
    location = request.form['location']
    issue    = request.form['issue']
    priority = request.form['priority']
    category = request.form.get('category', 'Other')
    created  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO complaints (name,location,issue,priority,status,assigned_to,solution,created_at,category)
        VALUES (?,?,?,?,'Open','','',?,?)
    """, (name, location, issue, priority, created, category))
    new_id = c.lastrowid
    tno    = ticket_number(new_id)
    c.execute("UPDATE complaints SET ticket_no=? WHERE id=?", (tno, new_id))
    conn.commit()
    conn.close()

    return f"""<!DOCTYPE html><html lang="en">
<head><title>Submitted — SMILES IT Helpdesk</title>{BASE_STYLE}</head><body>
<div style="min-height:100vh;display:grid;place-items:center;background:var(--bg)">
  <div style="text-align:center;max-width:420px;padding:40px">
    <div style="width:60px;height:60px;background:var(--green-bg);border-radius:50%;
      display:grid;place-items:center;margin:0 auto 18px">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--green-l)" stroke-width="2.5">
        <path d="M20 6L9 17l-5-5"/></svg></div>
    <h2 style="font-size:21px;font-weight:700;margin-bottom:7px">Ticket Submitted!</h2>
    <p style="color:var(--muted);margin-bottom:18px;font-size:13.5px">
      Your request has been logged. Save your ticket number below for future reference.
    </p>
    <div class="tno" style="font-size:22px;display:inline-block;padding:10px 22px;margin-bottom:28px">{tno}</div>
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;
      padding:16px;margin-bottom:24px;text-align:left">
      <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px">Summary</div>
      <div style="font-size:13px"><b>{name}</b> · {location}</div>
      <div style="font-size:12.5px;color:var(--muted);margin-top:4px">{category} · {priority_badge(priority)}</div>
      <div style="font-size:12.5px;color:var(--muted);margin-top:6px">{issue[:120]}{'...' if len(issue)>120 else ''}</div>
    </div>
    <div style="display:flex;gap:10px;justify-content:center">
      <a href="/" class="btn btn-ghost">Raise Another</a>
    </div>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username in ADMIN_USERS and ADMIN_USERS[username] == password:
            session['admin_logged_in'] = True
            session['admin_user']      = username
            return redirect(url_for('admin_dashboard'))
        error = "Invalid username or password. Please try again."

    return f"""<!DOCTYPE html><html lang="en">
<head><title>Admin Login — SMILES IT Helpdesk</title>{BASE_STYLE}</head><body>
<div class="login-wrap">
  <div class="login-card">
    <div class="login-logo">
      <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div>
    <h2>Admin Login</h2>
    <p>SMILES IT Helpdesk Dashboard — restricted access</p>

    {'<div class="error-msg">⚠ ' + error + '</div>' if error else ''}

    <form method="POST">
      <div class="fg">
        <label>Username</label>
        <input name="username" placeholder="Enter username" required autocomplete="username">
      </div>
      <div class="fg">
        <label>Password</label>
        <input name="password" type="password" placeholder="Enter password" required autocomplete="current-password">
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:10px;margin-top:6px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3"/></svg>
        Sign In
      </button>
    </form>

    <div style="text-align:center;margin-top:18px">
      <a href="/" style="font-size:12px;color:var(--muted)">← Back to User Portal</a>
    </div>
  </div>
</div>
</body></html>"""


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM complaints")
    all_rows = c.fetchall()
    conn.close()

    total      = len(all_rows)
    open_c     = sum(1 for r in all_rows if r['status'] == 'Open')
    assigned_c = sum(1 for r in all_rows if r['status'] in ('Assigned', 'In Progress'))
    resolved_c = sum(1 for r in all_rows if r['status'] == 'Resolved')
    closed_c   = sum(1 for r in all_rows if r['status'] == 'Closed')
    high_c     = sum(1 for r in all_rows if r['priority'] == 'High')

    username = session.get('admin_user', 'admin')

    # recent 5 tickets
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM complaints ORDER BY id DESC LIMIT 5")
    recent = c.fetchall()
    conn.close()

    rows_html = ""
    for row in recent:
        tno = row['ticket_no'] or ticket_number(row['id'])
        rows_html += f"""<tr>
          <td><span class="tno">{tno}</span></td>
          <td>{row['name']}</td>
          <td>{priority_badge(row['priority'])}</td>
          <td>{status_badge(row['status'])}</td>
          <td style="font-size:11.5px;color:var(--muted);font-family:var(--mono)">{row['created_at']}</td>
          <td><a href="/admin/tickets" class="btn btn-ghost btn-sm">View All</a></td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="en">
<head><title>Dashboard — SMILES IT Helpdesk</title>{BASE_STYLE}</head><body>
{topbar(username=username)}
{sidebar('dashboard', open_c)}
<div class="main">
  <div class="page-hd">
    <h1>Dashboard</h1>
    <p>Welcome back, <b>{username}</b>. Here's the current SMILES helpdesk overview.</p>
  </div>

  <!-- STATS -->
  <div class="stats">
    <div class="stat">
      <div class="stat-label">Total</div>
      <div class="stat-value">{total}</div>
      <div class="stat-sub">All tickets</div>
    </div>
    <div class="stat">
      <div class="stat-label">Open</div>
      <div class="stat-value" style="color:var(--red-l)">{open_c}</div>
      <div class="stat-sub"><span class="stat-dot" style="background:var(--red-l)"></span>Needs action</div>
    </div>
    <div class="stat">
      <div class="stat-label">In Progress</div>
      <div class="stat-value" style="color:var(--yellow-l)">{assigned_c}</div>
      <div class="stat-sub"><span class="stat-dot" style="background:var(--yellow-l)"></span>Being worked on</div>
    </div>
    <div class="stat">
      <div class="stat-label">Resolved</div>
      <div class="stat-value" style="color:var(--blue-l)">{resolved_c}</div>
      <div class="stat-sub"><span class="stat-dot" style="background:var(--blue-l)"></span>Awaiting closure</div>
    </div>
    <div class="stat">
      <div class="stat-label">Closed</div>
      <div class="stat-value" style="color:var(--green-l)">{closed_c}</div>
      <div class="stat-sub"><span class="stat-dot" style="background:var(--green-l)"></span>Completed</div>
    </div>
  </div>

  <!-- RECENT TICKETS -->
  <div class="table-wrap">
    <div class="table-hdr">
      <div class="table-title">Recent Tickets</div>
      <div class="tbl-actions">
        <a href="/admin/tickets" class="btn btn-ghost btn-sm">View All →</a>
        <a href="/" target="_blank" class="btn btn-primary btn-sm">+ New Ticket</a>
      </div>
    </div>
    <table>
      <thead><tr>
        <th>Ticket #</th><th>Requester</th><th>Priority</th>
        <th>Status</th><th>Created</th><th></th>
      </tr></thead>
      <tbody>{rows_html if rows_html else '<tr><td colspan="6"><div class="empty"><h3>No tickets yet</h3></div></td></tr>'}</tbody>
    </table>
  </div>
</div>

<div class="toast" id="toast">
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--green-l)" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
  Ticket updated successfully
</div>
<script>
if(new URLSearchParams(location.search).get('updated')){{
  const t=document.getElementById('toast'); t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),3000);
}}
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  ALL TICKETS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/tickets')
@login_required
def admin_tickets():
    status_f   = request.args.get('status',   'All')
    priority_f = request.args.get('priority', 'All')
    category_f = request.args.get('category', 'All')
    search_q   = request.args.get('q', '').strip()
    username   = session.get('admin_user', 'admin')

    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM complaints ORDER BY id DESC")
    all_rows = c.fetchall()
    open_c   = sum(1 for r in all_rows if r['status'] == 'Open')
    conn.close()

    # apply filters
    data = all_rows
    if status_f   != 'All': data = [r for r in data if r['status']   == status_f]
    if priority_f != 'All': data = [r for r in data if r['priority'] == priority_f]
    if category_f != 'All': data = [r for r in data if (r['category'] or '') == category_f]
    if search_q:            data = [r for r in data if search_q.lower() in
                                     (str(r['name'])+str(r['issue'])+str(r['location'])+str(r['ticket_no'])).lower()]

    cats = sorted(set(r['category'] for r in all_rows if r['category']))

    rows_html = ""
    for row in data:
        tno = row['ticket_no'] or ticket_number(row['id'])
        rows_html += f"""<tr onclick="openPanel({row['id']})" style="cursor:pointer">
          <td><span class="tno">{tno}</span></td>
          <td>
            <div style="font-weight:500">{row['issue'][:52]}{'...' if len(str(row['issue']))>52 else ''}</div>
            <div style="font-size:11.5px;color:var(--muted)">{row['category'] or '—'}</div>
          </td>
          <td>{row['name']}<div style="font-size:11.5px;color:var(--muted)">{row['location']}</div></td>
          <td>{priority_badge(row['priority'])}</td>
          <td>{status_badge(row['status'])}</td>
          <td style="font-size:12.5px;color:var(--muted)">{row['assigned_to'] or '—'}</td>
          <td style="font-size:11px;color:var(--muted);font-family:var(--mono)">{row['created_at']}</td>
          <td onclick="event.stopPropagation()">
            <button class="btn btn-ghost btn-sm" onclick="openPanel({row['id']})">Edit</button>
          </td>
        </tr>"""

    if not data:
        rows_html = '<tr><td colspan="8"><div class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg><h3>No tickets match your filters</h3></div></td></tr>'

    # JS data for panels
    panel_js = "const TICKETS={};\n"
    for row in all_rows:
        tno   = row['ticket_no'] or ticket_number(row['id'])
        iss   = str(row['issue']).replace("`","'").replace("\n","\\n")
        sol   = str(row['solution'] or "").replace("`","'").replace("\n","\\n")
        panel_js += f"""TICKETS[{row['id']}]={{
  id:{row['id']},tno:"{tno}",name:"{row['name']}",location:"{row['location']}",
  issue:`{iss}`,priority:"{row['priority']}",status:"{row['status']}",
  assigned:"{row['assigned_to'] or ''}",solution:`{sol}`,
  created:"{row['created_at']}",category:"{row['category'] or ''}"
}};\n"""

    cat_opts = ''.join(f'<option {"selected" if category_f==c else ""}>{c}</option>' for c in cats)

    return f"""<!DOCTYPE html><html lang="en">
<head><title>All Tickets — SMILES IT Helpdesk</title>{BASE_STYLE}</head><body>
{topbar(username=username)}
{sidebar('tickets', open_c)}

<!-- DETAIL PANEL -->
<div class="panel" id="detailPanel">
  <div class="panel-head">
    <div>
      <div style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:4px">Ticket Detail</div>
      <span class="tno" id="pTno" style="font-size:13px"></span>
    </div>
    <button class="panel-close" onclick="closePanel()">✕</button>
  </div>
  <div class="panel-body">

    <div style="display:flex;gap:7px;margin-bottom:18px" id="pBadges"></div>

    <div class="field-group">
      <div class="field-label">Issue Description</div>
      <div class="field-val" id="pIssue" style="background:var(--bg);border:1px solid var(--border2);
        border-radius:7px;padding:12px;font-size:13px;line-height:1.7"></div>
    </div>

    <div class="info-grid">
      <div class="info-item"><div class="field-label">Requester</div><div class="field-val" id="pName"></div></div>
      <div class="info-item"><div class="field-label">Location</div><div class="field-val" id="pLoc"></div></div>
      <div class="info-item"><div class="field-label">Category</div><div class="field-val" id="pCat"></div></div>
      <div class="info-item"><div class="field-label">Created</div><div class="field-val" id="pCreated" style="font-size:12px;font-family:var(--mono)"></div></div>
    </div>

    <div id="pSolWrap" style="display:none" class="field-group">
      <div class="field-label">Current Solution / Notes</div>
      <div class="field-val" id="pSol" style="color:var(--muted);font-size:13px;line-height:1.6"></div>
    </div>

    <hr class="div">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:600;margin-bottom:12px">Update Ticket</div>

    <form id="updateForm" method="POST">
      <div class="uf">

        <label>ASSIGN TO TECHNICIAN</label>
        <input id="uf_assign" name="assigned_to" placeholder="Name or team (e.g. John — Network Team)">

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div>
            <label>PRIORITY</label>
            <select id="uf_priority" name="priority">
              <option>Low</option>
              <option>Medium</option>
              <option>High</option>
            </select>
          </div>
          <div>
            <label>STATUS</label>
            <select id="uf_status" name="status">
              <option>Open</option>
              <option>Assigned</option>
              <option>In Progress</option>
              <option>Resolved</option>
              <option>Closed</option>
            </select>
          </div>
        </div>

        <label>SOLUTION / ACTION TAKEN</label>
        <textarea id="uf_sol" name="solution" rows="4"
          placeholder="Describe what was done to fix the issue..."></textarea>

        <div class="uf-row">
          <button type="submit" class="btn btn-success" style="flex:1;justify-content:center">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
            Save Changes
          </button>
          <button type="button" onclick="closePanel()" class="btn btn-ghost">Cancel</button>
        </div>

      </div>
    </form>

  </div>
</div>
<div id="overlay" onclick="closePanel()"></div>

<div class="main">
  <div class="breadcrumb">
    <a href="/admin">Dashboard</a><span>/</span><span style="color:var(--text)">All Tickets</span>
  </div>
  <div class="page-hd">
    <h1>All Tickets</h1>
    <p>Click any row to view details and update the ticket.</p>
  </div>

  <div class="table-wrap">
    <div class="table-hdr">
      <div class="table-title">Incidents &nbsp;<span style="color:var(--muted);font-weight:400;font-size:13px">({len(data)} shown of {len(all_rows)})</span></div>
      <div class="tbl-actions">
        <a href="/admin/export" class="btn btn-export btn-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 10v6m0 0l-3-3m3 3l3-3M3 17v3a2 2 0 002 2h14a2 2 0 002-2v-3"/></svg>
          Export
        </a>
        <a href="/" target="_blank" class="btn btn-primary btn-sm">+ New Ticket</a>
      </div>
    </div>

    <!-- FILTERS -->
    <form method="GET" action="/admin/tickets" class="filter-bar">
      <span class="filter-label">Filter:</span>
      <select name="status" onchange="this.form.submit()">
        {''.join(f'<option {"selected" if status_f==s else ""}>{s}</option>' for s in ['All','Open','Assigned','In Progress','Resolved','Closed'])}
      </select>
      <select name="priority" onchange="this.form.submit()">
        {''.join(f'<option {"selected" if priority_f==p else ""}>{p}</option>' for p in ['All','High','Medium','Low'])}
      </select>
      <select name="category" onchange="this.form.submit()">
        <option {'selected' if category_f=='All' else ''}>All</option>
        {cat_opts}
      </select>
      <div class="filter-sep"></div>
      <input name="q" placeholder="Search…" value="{search_q}" style="width:200px">
      <button type="submit" class="btn btn-ghost btn-sm">Go</button>
      <a href="/admin/tickets" class="btn btn-ghost btn-sm">Clear</a>
    </form>

    <table>
      <thead><tr>
        <th>Ticket #</th><th>Issue</th><th>Requester</th>
        <th>Priority</th><th>Status</th><th>Assigned To</th>
        <th>Created</th><th></th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>

<div class="toast" id="toast">
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--green-l)" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
  Ticket updated successfully
</div>

<script>
{panel_js}

function pb(p){{const m={{High:'b-high',Medium:'b-medium',Low:'b-low'}};return`<span class="badge ${{m[p]||'b-low'}}">${{p}}</span>`;}}
function sb(s){{const m={{Open:'b-open',Assigned:'b-assigned','In Progress':'b-inprogress',Resolved:'b-resolved',Closed:'b-closed'}};return`<span class="badge ${{m[s]||'b-open'}}">${{s}}</span>`;}}

function openPanel(id){{
  const t=TICKETS[id]; if(!t) return;
  document.getElementById('pTno').textContent=t.tno;
  document.getElementById('pIssue').textContent=t.issue;
  document.getElementById('pName').textContent=t.name;
  document.getElementById('pLoc').textContent=t.location;
  document.getElementById('pCat').textContent=t.category||'—';
  document.getElementById('pCreated').textContent=t.created;
  document.getElementById('pBadges').innerHTML=pb(t.priority)+' '+sb(t.status);
  const sw=document.getElementById('pSolWrap');
  if(t.solution){{sw.style.display='block';document.getElementById('pSol').textContent=t.solution;}}
  else sw.style.display='none';
  document.getElementById('uf_assign').value=t.assigned;
  document.getElementById('uf_sol').value=t.solution;
  const ps=document.getElementById('uf_priority');
  for(let o of ps.options) o.selected=(o.value===t.priority);
  const ss=document.getElementById('uf_status');
  for(let o of ss.options) o.selected=(o.value===t.status);
  document.getElementById('updateForm').action='/admin/update/'+id;
  document.getElementById('detailPanel').classList.add('open');
  document.getElementById('overlay').style.display='block';
}}

function closePanel(){{
  document.getElementById('detailPanel').classList.remove('open');
  document.getElementById('overlay').style.display='none';
}}

if(new URLSearchParams(location.search).get('updated')){{
  const t=document.getElementById('toast'); t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),3000);
}}
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  UPDATE TICKET
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/update/<int:id>', methods=['POST'])
@login_required
def admin_update(id):
    assigned = request.form.get('assigned_to', '')
    solution = request.form.get('solution', '')
    status   = request.form.get('status', 'Open')
    priority = request.form.get('priority', 'Medium')
    closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == 'Closed' else None

    conn = get_db()
    c    = conn.cursor()
    if closed_at:
        c.execute("""UPDATE complaints SET assigned_to=?,solution=?,status=?,priority=?,closed_at=? WHERE id=?""",
                  (assigned, solution, status, priority, closed_at, id))
    else:
        c.execute("""UPDATE complaints SET assigned_to=?,solution=?,status=?,priority=? WHERE id=?""",
                  (assigned, solution, status, priority, id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_tickets') + '?updated=1')


# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT REPORT
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/export', methods=['GET', 'POST'])
@login_required
def admin_export():
    username = session.get('admin_user', 'admin')

    conn     = get_db()
    c        = conn.cursor()
    c.execute("SELECT * FROM complaints ORDER BY id DESC")
    all_rows = c.fetchall()
    open_c   = sum(1 for r in all_rows if r['status'] == 'Open')
    conn.close()

    if request.method == 'POST':
        period   = request.form.get('period', 'all')
        fmt      = request.form.get('format', 'csv')
        status_f = request.form.get('status', 'All')
        now      = datetime.now()

        if   period == 'today': cutoff = now.replace(hour=0, minute=0, second=0)
        elif period == 'week':  cutoff = now - timedelta(days=7)
        elif period == 'month': cutoff = now - timedelta(days=30)
        else:                   cutoff = None

        data = all_rows
        if cutoff:
            data = [r for r in data if datetime.strptime(r['created_at'], "%Y-%m-%d %H:%M:%S") >= cutoff]
        if status_f != 'All':
            data = [r for r in data if r['status'] == status_f]

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Ticket No", "Name", "Location", "Category", "Issue",
                         "Priority", "Status", "Assigned To", "Solution", "Created At", "Closed At"])
        for row in data:
            writer.writerow([
                row['ticket_no'] or ticket_number(row['id']),
                row['name'], row['location'], row['category'] or '',
                row['issue'], row['priority'], row['status'],
                row['assigned_to'] or '', row['solution'] or '',
                row['created_at'], row['closed_at'] or ''
            ])

        fname = f"helpdesk_report_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        resp  = make_response(output.getvalue())
        resp.headers['Content-Type']        = 'text/csv'
        resp.headers['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp

    # ── GET: show export page ──
    conn = get_db()
    c    = conn.cursor()

    today_count = 0; week_count = 0; month_count = 0
    now = datetime.now()
    for row in all_rows:
        try:
            created = datetime.strptime(row['created_at'], "%Y-%m-%d %H:%M:%S")
            if created.date() == now.date():          today_count += 1
            if (now - created).days <= 7:             week_count  += 1
            if (now - created).days <= 30:            month_count += 1
        except: pass

    return f"""<!DOCTYPE html><html lang="en">
<head><title>Export — SMILES IT Helpdesk</title>{BASE_STYLE}</head><body>
{topbar(username=username)}
{sidebar('export', open_c)}

<div class="main">
  <div class="breadcrumb">
    <a href="/admin">Dashboard</a><span>/</span><span style="color:var(--text)">Export Report</span>
  </div>
  <div class="page-hd">
    <h1>Export Report</h1>
    <p>Download ticket data as a CSV file. Filter by time period and status before exporting.</p>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:800px">

    <!-- EXPORT FORM -->
    <div class="form-card" style="max-width:none">
      <div class="form-sec">
        <div class="form-sec-title">Export Settings</div>

        <form method="POST">

          <div class="fg">
            <label>Time Period</label>
            <select name="period">
              <option value="today">Today</option>
              <option value="week">Last 7 Days</option>
              <option value="month">Last 30 Days</option>
              <option value="all" selected>All Time</option>
            </select>
          </div>

          <div class="fg">
            <label>Filter by Status</label>
            <select name="status">
              <option>All</option>
              <option>Open</option>
              <option>Assigned</option>
              <option>In Progress</option>
              <option>Resolved</option>
              <option>Closed</option>
            </select>
          </div>

          <div class="fg">
            <label>Format</label>
            <select name="format">
              <option value="csv">CSV (Excel compatible)</option>
            </select>
          </div>

          <button type="submit" class="btn btn-export" style="width:100%;justify-content:center;padding:10px">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 10v6m0 0l-3-3m3 3l3-3M3 17v3a2 2 0 002 2h14a2 2 0 002-2v-3"/></svg>
            Download CSV
          </button>

        </form>
      </div>
    </div>

    <!-- QUICK STATS -->
    <div>
      <div style="font-size:13px;font-weight:600;color:var(--muted);margin-bottom:12px;
        text-transform:uppercase;letter-spacing:.07em">Snapshot</div>

      <div class="stat" style="margin-bottom:12px">
        <div class="stat-label">Today's Tickets</div>
        <div class="stat-value" style="color:var(--blue-l)">{today_count}</div>
        <div class="stat-sub">{now.strftime('%d %b %Y')}</div>
      </div>

      <div class="stat" style="margin-bottom:12px">
        <div class="stat-label">Last 7 Days</div>
        <div class="stat-value" style="color:var(--yellow-l)">{week_count}</div>
        <div class="stat-sub">Weekly volume</div>
      </div>

      <div class="stat">
        <div class="stat-label">Last 30 Days</div>
        <div class="stat-value" style="color:var(--purple-l)">{month_count}</div>
        <div class="stat-sub">Monthly volume</div>
      </div>
    </div>

  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

