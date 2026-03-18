"""
HORIZON PORTFOLIO TOOL v75
PE Secondaries & Co-Investment LP Management

Same features as v74, Credit Portfolio Tool v9 style:
  - Flat dcc.Tabs, no Bootstrap sidebar
  - Inline forms, card()/kpi()/_field() helpers
  - No Bootstrap dependency

Tabs:
  📂 Portfolio       add/edit/delete deals, KPIs, charts
  🔭 Pipeline        deal pipeline, stage funnel, promote → portfolio
  🧩 Pro Forma       placeholder/future deals, deployment bar
  📊 Analytics       strategy/region/vintage/sector/concentration/scatter
  📈 Segments & TWR  seed/new/money-market breakdown, TWR forecast
  💧 Dry Powder      12-month forecast, bite-size guide
  ♻️ Pacing          quarterly deployment model
  🧮 Return Calc     required IRR waterfall, Monte Carlo TWR
  ⚙️ Settings        fund params, bite sizes

Run:  python Horizon_portfolio_tool_v75.py
Open: http://localhost:8050
"""

import math, os, pickle, json
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta

import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context, ALL, no_update
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Persistence ───────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "horizon_v75_data.pkl")

def save_data(portfolio, pipeline, placeholders, config, next_id):
    try:
        with open(DATA_FILE, "wb") as f:
            pickle.dump({"portfolio": portfolio, "pipeline": pipeline,
                         "placeholders": placeholders, "config": config,
                         "next_id": next_id,
                         "saved_at": datetime.now().isoformat(timespec="seconds")}, f)
    except Exception as e:
        print(f"Save error: {e}")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None

# ── Palette (identical to Credit Tool v9) ────────────────────────────────────
C = dict(
    bg="#07090f", panel="#0d1117", surface="#111822",
    border="#1c2a3a", border2="#243649",
    blue="#2979c8", sky="#56b4f5", teal="#2ec4b6",
    green="#2ecc71", red="#e5493a", amber="#f0a500",
    purple="#9b72cf", pink="#e05c8a",
    text="#d4e6f5", muted="#5e82a0", dim="#324d63",
    mono="'JetBrains Mono', 'Fira Mono', monospace",
    sans="'IBM Plex Sans', 'Segoe UI', sans-serif",
)

def cl(hex_c, alpha):
    r, g, b = int(hex_c[1:3],16), int(hex_c[3:5],16), int(hex_c[5:7],16)
    return f"rgba({r},{g},{b},{alpha})"

CHART = dict(
    paper_bgcolor=C["panel"], plot_bgcolor=C["surface"],
    font=dict(family=C["mono"], color=C["text"], size=11),
    margin=dict(l=52, r=20, t=40, b=40),
    xaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    yaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    legend=dict(bgcolor=C["panel"], bordercolor=C["border"], borderwidth=1),
)

# ── Taxonomy ──────────────────────────────────────────────────────────────────
STRATEGIES    = ["GP-Led (Multi-Asset)", "GP-Led (Single-Asset)", "Diversified LP-Led", "Co-Investment", "Primary"]
DEAL_TYPES    = ["Secondary", "Co-Investment"]
SECTORS       = ["Technology","Healthcare","Financial Services","Consumer","Industrials","Energy","Real Estate","Diversified","Other"]
REGIONS       = ["North America","Europe","Asia","Global"]
STAGES_DEAL   = ["Buyout","Growth","Venture","Liquidity"]
SEGMENTS      = ["Seed","New","MoneyMarket"]
ALLOC_STATUS  = ["Closed","Pending Close","Commitment"]
CURRENCIES    = ["USD","EUR","GBP","CHF"]
PIPE_STAGES   = ["Screening","Diligence","IC Review","Negotiation","Final Docs"]
PRIORITIES    = ["High","Medium","Low"]
VINTAGES      = list(range(2030, 2013, -1))

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "fund_size": 1000.0, "dry_powder": 300.0,
    "target_net_twr": 0.13, "management_fee": 0.0125,
    "carry_rate": 0.125, "hurdle_rate": 0.10,
    "loss_drag": 0.01, "liquidity_reserve_pct": 0.05,
    "distribution_rate": 0.20, "cash_yield": 0.03,
    "avg_hold_period": 5.0, "deployment_years": 4.0,
    "deals_per_year": 6.0,
    "bite_min_pct": 0.005, "bite_desired_pct": 0.0275, "bite_max_pct": 0.05,
}

SEED_PORTFOLIO = [
    dict(id=1, name="Project Alpha", manager="Hamilton Lane",
         strategy="GP-Led (Multi-Asset)", deal_type="Secondary", stage="Buyout",
         sector="Technology", region="North America", currency="USD",
         total_commitment=50.0, current_commitment=50.0, nav=58.0,
         target_irr=0.18, hold_period=4.5, moic=2.18,
         vintage=2023, segment="Seed", allocation_status="Closed",
         date_added="2023-06-01"),
    dict(id=2, name="Project Beta", manager="Coller Capital",
         strategy="Diversified LP-Led", deal_type="Secondary", stage="Buyout",
         sector="Diversified", region="Europe", currency="EUR",
         total_commitment=35.0, current_commitment=35.0, nav=40.0,
         target_irr=0.16, hold_period=3.5, moic=1.85,
         vintage=2024, segment="Seed", allocation_status="Closed",
         date_added="2024-01-15"),
    dict(id=3, name="Project Gamma", manager="Ardian",
         strategy="Co-Investment", deal_type="Co-Investment", stage="Growth",
         sector="Healthcare", region="Europe", currency="EUR",
         total_commitment=20.0, current_commitment=20.0, nav=24.0,
         target_irr=0.22, hold_period=5.0, moic=2.93,
         vintage=2024, segment="New", allocation_status="Closed",
         date_added="2024-03-20"),
    dict(id=4, name="Project Delta", manager="Blackstone",
         strategy="GP-Led (Single-Asset)", deal_type="Secondary", stage="Buyout",
         sector="Industrials", region="North America", currency="USD",
         total_commitment=45.0, current_commitment=45.0, nav=51.0,
         target_irr=0.20, hold_period=3.0, moic=1.73,
         vintage=2025, segment="New", allocation_status="Closed",
         date_added="2025-01-10"),
]

SEED_PIPELINE = [
    dict(id=10, name="Project Epsilon", strategy="GP-Led (Multi-Asset)", stage_deal="Buyout",
         sector="Technology", region="North America", size=30.0, target_irr=0.19,
         pipeline_stage="IC Review", priority="High", date_added="2025-10-01"),
    dict(id=11, name="Project Zeta", strategy="Co-Investment", stage_deal="Growth",
         sector="Healthcare", region="Europe", size=15.0, target_irr=0.24,
         pipeline_stage="Diligence", priority="Medium", date_added="2025-11-01"),
]

SEED_PLACEHOLDERS = [
    dict(id=20, name="GP-Led Placeholder 1", strategy="GP-Led (Multi-Asset)",
         deal_type="Secondary", size=35.0, expected_month=3,
         region="North America", target_irr=0.17, date_added="2025-01-01"),
    dict(id=21, name="Co-Invest Placeholder", strategy="Co-Investment",
         deal_type="Co-Investment", size=20.0, expected_month=6,
         region="Europe", target_irr=0.22, date_added="2025-01-01"),
]

loaded            = load_data()
INITIAL_PORT      = loaded.get("portfolio",    SEED_PORTFOLIO)    if loaded else SEED_PORTFOLIO
INITIAL_PIPE      = loaded.get("pipeline",     SEED_PIPELINE)     if loaded else SEED_PIPELINE
INITIAL_PH        = loaded.get("placeholders", SEED_PLACEHOLDERS) if loaded else SEED_PLACEHOLDERS
INITIAL_CFG       = loaded.get("config",       DEFAULT_CONFIG)    if loaded else DEFAULT_CONFIG
INITIAL_NEXT_ID   = loaded.get("next_id",      50)                if loaded else 50
SAVED_AT          = loaded.get("saved_at",     "Seed data")       if loaded else "Seed data"

# ── Style helpers ─────────────────────────────────────────────────────────────
INP = dict(background=C["surface"], border=f"1px solid {C['border2']}",
           color=C["text"], borderRadius=6, padding="6px 10px",
           fontFamily=C["mono"], fontSize=12, outline="none", width="100%")
BTN = lambda bg, fg="#fff": dict(
    background=bg, border="none", color=fg, borderRadius=6,
    padding="7px 16px", cursor="pointer", fontWeight=600,
    fontSize=12, fontFamily=C["sans"])
TBL_CELL = dict(backgroundColor=C["panel"], color=C["text"],
                fontFamily=C["mono"], fontSize=11, padding="8px 12px",
                border=f"1px solid {C['border']}", textAlign="left")
TBL_HEAD = dict(backgroundColor=C["bg"], color=C["muted"], fontWeight=700,
                fontSize=10, letterSpacing=1.5, textTransform="uppercase",
                border=f"1px solid {C['border']}", padding="9px 12px")
TBL_ODD  = [{"if": {"row_index": "odd"}, "backgroundColor": C["surface"]}]

def card(children, style_extra=None):
    base = dict(background=C["panel"], border=f"1px solid {C['border']}", borderRadius=10, padding=18)
    if style_extra: base.update(style_extra)
    return html.Div(children, style=base)

def kpi(label, value, sub="", color=None, width=150):
    return html.Div([
        html.Div(label, style=dict(fontSize=9, letterSpacing=2, color=C["muted"],
                                   textTransform="uppercase", marginBottom=5, fontFamily=C["sans"])),
        html.Div(value, style=dict(fontSize=22, fontWeight=700, color=color or C["sky"], fontFamily=C["mono"])),
        html.Div(sub,   style=dict(fontSize=10, color=C["dim"], marginTop=3, fontFamily=C["sans"])),
    ], style=dict(background=C["surface"], border=f"1px solid {C['border']}",
                  borderRadius=8, padding="14px 18px", minWidth=width))

def section_lbl(text):
    return html.Div(text, style=dict(fontSize=9, letterSpacing=2.5, color=C["muted"],
                                      textTransform="uppercase", marginBottom=10, fontFamily=C["sans"]))

def _field(label, component):
    return html.Div([
        html.Label(label, style=dict(fontSize=9, color=C["muted"], display="block",
                                     marginBottom=4, letterSpacing=1, textTransform="uppercase")),
        component,
    ])

def _dd():
    return dict(backgroundColor=C["surface"], color=C["text"],
                border=f"1px solid {C['border2']}", borderRadius=6,
                fontFamily=C["mono"], fontSize=12)

def fmt_m(x):
    try: return f"${float(x or 0):,.1f}M"
    except: return "$—"

def dd_opts(lst):
    return [{"label": x, "value": x} for x in lst]

def month_options():
    names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return [{"label": f"{names[i%12]} {2026+(i//12)}", "value": i} for i in range(60)]

# ── Maths ─────────────────────────────────────────────────────────────────────
def w_avg(deals, key, wkey="nav"):
    total = sum(float(d.get(wkey,0) or 0) for d in deals)
    if not total: return 0.0
    return sum(float(d.get(key,0) or 0)*float(d.get(wkey,0) or 0) for d in deals)/total

def portfolio_metrics(deals):
    if not deals:
        return dict(total_nav=0, num=0, w_irr=0, top1=0, top3=0, top5=0, eff_n=0,
                    total_commit=0, curr_commit=0, total_unfunded=0)
    total = sum(d.get("nav",0) for d in deals)
    w_irr = w_avg(deals, "target_irr")
    weights = [d["nav"]/total for d in deals] if total else []
    eff_n = 1/sum(w**2 for w in weights) if weights else 0
    sd = sorted(deals, key=lambda x: x["nav"], reverse=True)
    top1 = sd[0]["nav"]/total       if sd and total else 0
    top3 = sum(d["nav"] for d in sd[:3])/total if len(sd)>=3 and total else 0
    top5 = sum(d["nav"] for d in sd[:5])/total if len(sd)>=5 and total else 0
    tc = sum(d.get("total_commitment",0) for d in deals)
    cc = sum(d.get("current_commitment",0) for d in deals)
    uf = sum(d.get("total_commitment",0)-d.get("current_commitment",0) for d in deals)
    return dict(total_nav=total, num=len(deals), w_irr=w_irr,
                top1=top1, top3=top3, top5=top5, eff_n=eff_n,
                total_commit=tc, curr_commit=cc, total_unfunded=uf)

def calc_required_irr(current_irr, nav, dry_powder, config):
    target  = float(config.get("target_net_twr", 0.13))
    fee     = float(config.get("management_fee", 0.0125))
    carry   = float(config.get("carry_rate", 0.125))
    hurdle  = float(config.get("hurdle_rate", 0.10))
    loss    = float(config.get("loss_drag", 0.01))
    liq     = float(config.get("liquidity_reserve_pct", 0.05))
    cy      = float(config.get("cash_yield", 0.03))
    invested = max(0, 1-liq)
    gross_needed = (target + fee + loss - liq*cy) / invested if invested else target
    if gross_needed > hurdle:
        gross_needed += (gross_needed-hurdle)*carry
    total = nav+dry_powder
    if not total or not dry_powder: return gross_needed
    req = (gross_needed - (nav/total)*current_irr) / (dry_powder/total)
    return max(0, min(1.5, req))

def bite_sizes(config):
    dp = float(config.get("dry_powder",300) or 300)
    mn = float(config.get("bite_min_pct",0.005))
    ds = float(config.get("bite_desired_pct",0.0275))
    mx = float(config.get("bite_max_pct",0.05))
    return {s: {"min": dp*mn, "desired": dp*ds, "max": dp*mx, "min_pct": mn, "desired_pct": ds, "max_pct": mx}
            for s in STRATEGIES}

def forecast_dp(nav, dry_powder, placeholders, config, months=12):
    rows = []
    base = datetime(2026, 1, 1)
    monthly_ret  = float(config.get("target_net_twr", 0.13))/12
    monthly_dist = float(config.get("distribution_rate", 0.20))/12
    dp = dry_powder
    n  = nav
    for m in range(months):
        d_nav  = n * monthly_ret
        dist   = n * monthly_dist
        calls  = sum(p.get("size",0) for p in (placeholders or []) if p.get("expected_month")==m)
        dp     = dp + dist - calls
        n      = n + d_nav + calls - dist
        rows.append({"month": (base+relativedelta(months=m)).strftime("%b %Y"),
                     "dry_powder": dp, "nav": n, "distributions": dist, "calls": calls})
    return rows

def build_pacing(portfolio, pipeline, placeholders, config, quarters=16):
    fund_size  = float(config.get("fund_size",1000) or 1000)
    dep_years  = float(config.get("deployment_years",4) or 4)
    deals_py   = max(float(config.get("deals_per_year",6) or 6),1)
    dist_rate  = float(config.get("distribution_rate",0.20) or 0.20)
    nav = sum(d.get("nav",0) for d in (portfolio or []))
    ph_map = {}
    for p in (placeholders or []):
        q = max(1, int(p.get("expected_month",0)/3)+1)
        ph_map[q] = ph_map.get(q,0)+p.get("size",0)
    rows = []
    for q in range(1, quarters+1):
        yr = datetime.now().year+(q-1)//4
        label = f"Q{((q-1)%4)+1} {yr}"
        base_deploy = fund_size/(dep_years*4)
        future      = ph_map.get(q,0)
        capacity    = max(fund_size-nav, 0)
        deploy      = min(base_deploy+future, capacity)
        repay       = nav*dist_rate/4 if q>4 else 0
        nav         = max(0, nav+deploy-repay)
        rows.append({"Quarter": label, "Deployment ($M)": round(deploy,1),
                     "Repayments/Dist ($M)": round(repay,1), "NAV ($M)": round(nav,1),
                     "Dry Powder ($M)": round(max(fund_size-nav,0),1),
                     "Utilisation %": round(nav/fund_size*100,1) if fund_size else 0,
                     "Deals (est)": round(deals_py/4,1)})
    return pd.DataFrame(rows)

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="Horizon PE Secondaries", suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div([
    dcc.Store(id="port-store",  data=INITIAL_PORT),
    dcc.Store(id="pipe-store",  data=INITIAL_PIPE),
    dcc.Store(id="ph-store",    data=INITIAL_PH),
    dcc.Store(id="cfg-store",   data=INITIAL_CFG),
    dcc.Store(id="next-id",     data=INITIAL_NEXT_ID),
    dcc.Store(id="edit-idx",    data=None),  # for edit mode

    # ── Header ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div([
                html.Span("HORIZON", style=dict(fontSize=19, fontWeight=700, color=C["text"],
                                                 fontFamily=C["sans"], letterSpacing=2)),
                html.Span(" · ", style=dict(color=C["dim"], margin="0 6px")),
                html.Span("PE Secondaries & Co-Investment Dashboard",
                           style=dict(fontSize=16, fontWeight=300, color=C["muted"], fontFamily=C["sans"])),
            ]),
            html.Div(id="save-status-lbl",
                     style=dict(color=C["dim"], marginTop=6, fontSize=11, fontFamily=C["mono"])),
        ]),
        html.Div([
            html.Div([html.Label("Fund Size ($M)",    style=dict(fontSize=9,color=C["muted"],letterSpacing=2,display="block",marginBottom=4,textTransform="uppercase")),
                      dcc.Input(id="hdr-fund-size",  type="number", value=INITIAL_CFG.get("fund_size",1000),  style={**INP,"width":90})]),
            html.Div([html.Label("Dry Powder ($M)",   style=dict(fontSize=9,color=C["muted"],letterSpacing=2,display="block",marginBottom=4,textTransform="uppercase")),
                      dcc.Input(id="hdr-dry-powder", type="number", value=INITIAL_CFG.get("dry_powder",300),  style={**INP,"width":90})]),
            html.Div([html.Label("Target Net TWR",    style=dict(fontSize=9,color=C["muted"],letterSpacing=2,display="block",marginBottom=4,textTransform="uppercase")),
                      dcc.Input(id="hdr-twr",        type="number", value=round(INITIAL_CFG.get("target_net_twr",0.13)*100,2), step=0.25, style={**INP,"width":85})]),
            html.Div([html.Label("Mgmt Fee %",        style=dict(fontSize=9,color=C["muted"],letterSpacing=2,display="block",marginBottom=4,textTransform="uppercase")),
                      dcc.Input(id="hdr-fee",        type="number", value=round(INITIAL_CFG.get("management_fee",0.0125)*100,3), step=0.125, style={**INP,"width":80})]),
        ], style=dict(display="flex", gap=12, alignItems="flex-end", flexWrap="wrap")),
    ], style=dict(background="#070c13", borderBottom=f"1px solid {C['border']}",
                  padding="22px 36px", display="flex", justifyContent="space-between",
                  alignItems="center", flexWrap="wrap", gap=16)),

    # ── KPI strip ─────────────────────────────────────────────────────────────
    html.Div(id="kpi-strip", style=dict(padding="16px 36px", display="flex", gap=10, flexWrap="wrap")),

    # ── Tabs ──────────────────────────────────────────────────────────────────
    html.Div([
        dcc.Tabs(id="tabs", value="portfolio", children=[
            dcc.Tab(label="📂 Portfolio",      value="portfolio"),
            dcc.Tab(label="🔭 Pipeline",       value="pipeline"),
            dcc.Tab(label="🧩 Pro Forma",      value="proforma"),
            dcc.Tab(label="📊 Analytics",      value="analytics"),
            dcc.Tab(label="📈 Segments & TWR", value="segments"),
            dcc.Tab(label="💧 Dry Powder",     value="drypowder"),
            dcc.Tab(label="♻️ Pacing",         value="pacing"),
            dcc.Tab(label="🧮 Return Calc",    value="returns"),
            dcc.Tab(label="⚙️ Settings",       value="settings"),
        ], colors=dict(border=C["border"], primary=C["blue"], background=C["bg"]),
           style=dict(fontFamily=C["sans"]))
    ], style=dict(padding="0 36px", borderBottom=f"1px solid {C['border']}")),

    html.Div(id="tab-content", style=dict(padding="24px 36px 60px")),

], style=dict(background=C["bg"], minHeight="100vh", fontFamily=C["sans"], color=C["text"]))


# ── Header → config sync ──────────────────────────────────────────────────────
@app.callback(
    Output("cfg-store","data"),
    Input("hdr-fund-size","value"), Input("hdr-dry-powder","value"),
    Input("hdr-twr","value"), Input("hdr-fee","value"),
    State("cfg-store","data"),
)
def sync_header(fund_size, dry_powder, twr, fee, config):
    cfg = dict(config or DEFAULT_CONFIG)
    cfg.update({
        "fund_size":      float(fund_size    or cfg.get("fund_size",1000)),
        "dry_powder":     float(dry_powder   or cfg.get("dry_powder",300)),
        "target_net_twr": float(twr          or cfg.get("target_net_twr",0.13)*100)/100,
        "management_fee": float(fee          or cfg.get("management_fee",0.0125)*100)/100,
    })
    return cfg


# ── KPI strip ─────────────────────────────────────────────────────────────────
@app.callback(
    Output("kpi-strip","children"),
    Input("port-store","data"), Input("pipe-store","data"),
    Input("ph-store","data"), Input("cfg-store","data"),
)
def update_kpis(portfolio, pipeline, placeholders, config):
    m   = portfolio_metrics(portfolio or [])
    nav = m["total_nav"]
    dp  = float(config.get("dry_powder",300) or 300)
    req = calc_required_irr(m["w_irr"], nav, dp, config)
    bs  = bite_sizes(config)
    desired = bs.get("GP-Led (Multi-Asset)",{}).get("desired",0)
    sec_nav = sum(d["nav"] for d in (portfolio or []) if d.get("deal_type")=="Secondary")
    ci_nav  = sum(d["nav"] for d in (portfolio or []) if d.get("deal_type")=="Co-Investment")
    tgt_twr = float(config.get("target_net_twr",0.13))
    status  = "✅ On target" if m["w_irr"] >= tgt_twr else "⚠️ Below target"
    return [
        kpi("Investment NAV",  fmt_m(nav),             f"{m['num']} deals",                C["green"]),
        kpi("Dry Powder",      fmt_m(dp),              "Available to deploy",               C["blue"]),
        kpi("Total Fund",      fmt_m(nav+dp),          "NAV + Powder",                      C["sky"]),
        kpi("Portfolio IRR",   f"{m['w_irr']:.1%}",   status,                              C["teal"]),
        kpi("Required IRR",    f"{req:.1%}",           "On future deals",                   C["amber"]),
        kpi("Pipeline",        fmt_m(sum(p.get("size",0) for p in (pipeline or []))),
                               f"{len(pipeline or [])} deals",                              C["purple"]),
        kpi("Pro Forma",       fmt_m(sum(p.get("size",0) for p in (placeholders or []))),
                               f"{len(placeholders or [])} placeholders",                   C["pink"]),
        kpi("Secondaries",     fmt_m(sec_nav),         "In current portfolio",              C["blue"]),
        kpi("Co-Investments",  fmt_m(ci_nav),          "In current portfolio",              C["teal"]),
        kpi("Desired Bite",    fmt_m(desired),         f"{float(config.get('bite_desired_pct',0.0275))*100:.2f}% of DP", C["green"]),
    ]


# ── Tab router ────────────────────────────────────────────────────────────────
@app.callback(
    Output("tab-content","children"),
    Input("tabs","value"),
    Input("port-store","data"), Input("pipe-store","data"),
    Input("ph-store","data"), Input("cfg-store","data"),
)
def route(tab, portfolio, pipeline, placeholders, config):
    p  = portfolio or []
    pi = pipeline  or []
    ph = placeholders or []
    if tab == "portfolio": return tab_portfolio(p, config)
    if tab == "pipeline":  return tab_pipeline(pi, p, config)
    if tab == "proforma":  return tab_proforma(ph, config)
    if tab == "analytics": return tab_analytics(p, pi, config)
    if tab == "segments":  return tab_segments(p, pi, ph, config)
    if tab == "drypowder": return tab_drypowder(p, ph, config)
    if tab == "pacing":    return tab_pacing(p, pi, ph, config)
    if tab == "returns":   return tab_returns(p, pi, config)
    if tab == "settings":  return tab_settings(config)
    return html.Div()


# ══════════════════════════════════════════════════════════════════════════════
# TAB BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _form_row(*cols, gap=8):
    """Render field columns in a flex row."""
    return html.Div(list(cols), style=dict(display="flex", gap=gap, flexWrap="wrap", alignItems="flex-end", marginBottom=10))

def _port_add_form():
    """Add-deal inline form for the Portfolio tab."""
    inp = lambda id_, **kw: dcc.Input(id=id_, style=INP, **kw)
    drp = lambda id_, opts, val=None: dcc.Dropdown(id=id_, options=dd_opts(opts), value=val or opts[0], style=_dd())
    return html.Div([
        section_lbl("Add / Edit Portfolio Deal"),
        dcc.Store(id="edit-idx", data=None),
        _form_row(
            _field("Deal Name *",      inp("port-name",  type="text",   placeholder="Project Alpha", style={**INP,"minWidth":160})),
            _field("Manager *",        inp("port-manager",type="text",  placeholder="Hamilton Lane", style={**INP,"minWidth":150})),
            _field("Strategy *",       drp("port-strategy", STRATEGIES)),
            _field("Deal Type *",      drp("port-dtype",    DEAL_TYPES)),
            _field("Stage *",          drp("port-stage",    STAGES_DEAL, "Buyout")),
            _field("Sector",           drp("port-sector",   SECTORS, "Diversified")),
        ),
        _form_row(
            _field("Region",           drp("port-region",   REGIONS, "North America")),
            _field("Currency",         drp("port-currency", CURRENCIES, "USD")),
            _field("Total Commit $M",  inp("port-total-commit", type="number", value=30, step=0.1)),
            _field("Curr Commit $M",   inp("port-curr-commit",  type="number", value=30, step=0.1)),
            _field("Current NAV $M *", inp("port-nav",          type="number", value=30, step=0.1)),
            html.Div([
                html.Label("Unfunded $M", style=dict(fontSize=9,color=C["muted"],display="block",marginBottom=4,letterSpacing=1,textTransform="uppercase")),
                html.Div(id="unfunded-calc", style=dict(background=C["surface"], border=f"1px solid {C['border2']}", borderRadius=6,
                          padding="6px 10px", fontFamily=C["mono"], fontSize=12, color=C["amber"], minWidth=90)),
            ]),
        ),
        _form_row(
            _field("Target IRR % *",   inp("port-irr",   type="number", value=18, step=0.5)),
            _field("Hold Period (y)",  inp("port-hold",  type="number", value=5.0, step=0.5)),
            _field("MOIC",             inp("port-moic",  type="number", value=1.75, step=0.01)),
            _field("Vintage",          dcc.Dropdown(id="port-vintage", options=[{"label":str(y),"value":y} for y in VINTAGES], value=2025, style=_dd())),
            _field("Segment",          drp("port-segment",     SEGMENTS,     "New")),
            _field("Alloc Status",     drp("port-alloc-status",ALLOC_STATUS, "Closed")),
            html.Div([
                html.Label(" ", style=dict(display="block", marginBottom=4, fontSize=9)),
                html.Button("+ Add Deal", id="add-port-btn", style={**BTN(C["blue"]), "minWidth":100}),
            ]),
            html.Div([
                html.Label(" ", style=dict(display="block", marginBottom=4, fontSize=9)),
                html.Button("Clear",     id="clear-port-btn", style={**BTN(C["surface"], C["muted"]), "border":f"1px solid {C['border2']}","minWidth":70}),
            ]),
        ),
        html.Div(id="port-msg", style=dict(color=C["green"], fontSize=11, marginTop=4)),
    ], style=dict(background=C["surface"], border=f"1px solid {cl(C['blue'],0.4)}", borderRadius=8, padding=18, marginBottom=18))


def tab_portfolio(portfolio, config):
    m = portfolio_metrics(portfolio)
    total = m["total_nav"] or 1
    rows = []
    for i, d in enumerate(portfolio):
        uf = d.get("total_commitment",d.get("nav",0)) - d.get("current_commitment",d.get("nav",0))
        rows.append({
            "_idx": i,
            "Deal": d["name"], "Manager": d.get("manager",""),
            "Strategy": d.get("strategy",""), "Type": d.get("deal_type",""),
            "Stage": d.get("stage",""), "Sector": d.get("sector",""),
            "Region": d.get("region",""), "CCY": d.get("currency",""),
            "Total Commit": fmt_m(d.get("total_commitment",d.get("nav",0))),
            "Curr Commit":  fmt_m(d.get("current_commitment",d.get("nav",0))),
            "NAV":          fmt_m(d.get("nav",0)),
            "Unfunded":     fmt_m(uf),
            "IRR %":        f"{d.get('target_irr',0)*100:.1f}%",
            "MOIC":         f"{d.get('moic',0):.2f}x",
            "Hold (y)":     f"{d.get('hold_period',0):.1f}",
            "Weight":       f"{d.get('nav',0)/total*100:.1f}%",
            "Vintage":      str(d.get("vintage","")),
            "Segment":      d.get("segment",""),
            "Status":       d.get("allocation_status",""),
        })

    # Charts
    by_strat = {}
    by_type  = {"Secondary":0,"Co-Investment":0}
    for d in portfolio:
        k = d.get("strategy","?")
        by_strat[k] = by_strat.get(k,0)+d.get("nav",0)
        t = d.get("deal_type","Secondary")
        by_type[t]  = by_type.get(t,0)+d.get("nav",0)

    pie_colors = [C["blue"],C["purple"],C["teal"],C["green"],C["amber"]]
    fig = make_subplots(1,2,specs=[[{"type":"domain"},{"type":"domain"}]],
                        subplot_titles=["Exposure by Strategy","Secondary vs Co-Invest"])
    if any(by_strat.values()):
        fig.add_trace(go.Pie(labels=list(by_strat.keys()),values=list(by_strat.values()),hole=0.55,
                             marker_colors=pie_colors[:len(by_strat)],textfont_color=C["text"],showlegend=True),1,1)
    if any(by_type.values()):
        fig.add_trace(go.Pie(labels=list(by_type.keys()),values=list(by_type.values()),hole=0.55,
                             marker_colors=[C["sky"],C["teal"]],textfont_color=C["text"],showlegend=True),1,2)
    fig.update_layout(**CHART, height=280, margin=dict(t=50,b=10,l=10,r=10))

    # Summary KPIs for this tab
    tab_kpis = html.Div([
        kpi("Total NAV",          fmt_m(m["total_nav"]),      f"{m['num']} deals",            C["green"],  130),
        kpi("Total Commitment",   fmt_m(m["total_commit"]),   "Across portfolio",             C["blue"],   130),
        kpi("Curr Commitment",    fmt_m(m["curr_commit"]),    "Capital called",               C["sky"],    130),
        kpi("Unfunded",           fmt_m(m["total_unfunded"]), "Remaining",                    C["amber"],  120),
        kpi("Portfolio IRR",      f"{m['w_irr']*100:.1f}%",  "NAV-weighted",                 C["teal"],   120),
        kpi("Top 1 Conc",         f"{m['top1']*100:.1f}%",   "Limit 15%",                    C["red"] if m["top1"]>0.15 else C["green"], 110),
        kpi("Eff. # Positions",   f"{m['eff_n']:.1f}",       "Herfindahl",                   C["purple"], 110),
    ], style=dict(display="flex",gap=10,flexWrap="wrap",marginBottom=16))

    table = dash_table.DataTable(
        id="portfolio-table", data=rows,
        columns=[{"name":c,"id":c} for c in rows[0].keys()] if rows else [],
        hidden_columns=["_idx"],
        row_selectable="single", selected_rows=[],
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD+[
            {"if":{"column_id":"Type","filter_query":'{Type} = "Co-Investment"'},"color":C["teal"],"fontWeight":700},
            {"if":{"column_id":"IRR %"},"color":C["green"]},
            {"if":{"column_id":"NAV"},"color":C["sky"]},
        ],
        sort_action="native", filter_action="native",
        page_size=15, style_table={"overflowX":"auto"},
        export_format="xlsx",
    )

    actions = card([
        section_lbl("Actions"),
        html.Button("✏️ Edit Selected",   id="edit-port-btn",  style={**BTN(C["amber"]), "width":"100%", "marginBottom":8}),
        html.Button("🗑 Delete Selected", id="delete-port-btn",style={**BTN(C["red"]),   "width":"100%"}),
        html.Div(id="port-action-msg", style=dict(marginTop=10, color=C["muted"], fontSize=11)),
    ], dict(minWidth=180))

    return html.Div([
        _port_add_form(),
        tab_kpis,
        html.Div([
            html.Div(table, style=dict(flex=3, minWidth=0)),
            html.Div([
                dcc.Graph(figure=fig, config={"displayModeBar":False}),
                actions,
            ], style=dict(flex=1, display="flex", flexDirection="column", gap=16, minWidth=280)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


def tab_pipeline(pipeline, portfolio, config):
    rows = []
    for i, d in enumerate(pipeline):
        rows.append({
            "_idx": i,
            "Deal": d["name"], "Strategy": d.get("strategy",""),
            "Deal Stage": d.get("stage_deal",""), "Sector": d.get("sector",""),
            "Region": d.get("region",""), "Size ($M)": fmt_m(d.get("size",0)),
            "Target IRR": f"{d.get('target_irr',0)*100:.1f}%",
            "Pipeline Stage": d.get("pipeline_stage",""),
            "Priority": d.get("priority",""),
        })

    stages = PIPE_STAGES
    stage_vals = [sum(d.get("size",0) for d in pipeline if d.get("pipeline_stage")==s) for s in stages]
    fig_funnel = go.Figure(go.Funnel(y=stages, x=stage_vals, textinfo="value+percent initial",
                                     marker_color=[C["blue"],C["teal"],C["amber"],C["purple"],C["green"]],
                                     textfont=dict(color=C["text"])))
    fig_funnel.update_layout(**CHART, height=300, title="Pipeline Funnel ($M)")

    # Add form
    form = html.Div([
        section_lbl("Add Pipeline Deal"),
        _form_row(
            _field("Deal Name",       dcc.Input(id="pipe-name",       type="text",  style=INP, placeholder="Project X")),
            _field("Strategy",        dcc.Dropdown(id="pipe-strategy", options=dd_opts(STRATEGIES), value=STRATEGIES[0],  style=_dd())),
            _field("Deal Stage",      dcc.Dropdown(id="pipe-stage-deal",options=dd_opts(STAGES_DEAL),value="Buyout",       style=_dd())),
            _field("Sector",          dcc.Dropdown(id="pipe-sector",   options=dd_opts(SECTORS),    value="Technology",   style=_dd())),
            _field("Region",          dcc.Dropdown(id="pipe-region",   options=dd_opts(REGIONS),    value="North America",style=_dd())),
            _field("Size ($M)",       dcc.Input(id="pipe-size",        type="number",value=25, step=0.5, style=INP)),
            _field("Target IRR %",    dcc.Input(id="pipe-irr",         type="number",value=18, step=0.5, style=INP)),
            _field("Pipeline Stage",  dcc.Dropdown(id="pipe-pipe-stage",options=dd_opts(PIPE_STAGES),value="Screening",   style=_dd())),
            _field("Priority",        dcc.Dropdown(id="pipe-priority", options=dd_opts(PRIORITIES), value="Medium",       style=_dd())),
            html.Div([html.Label(" ",style=dict(display="block",marginBottom=4,fontSize=9)),
                      html.Button("+ Add",id="add-pipe-btn",style={**BTN(C["purple"]),"minWidth":80})]),
        ),
        html.Div(id="pipe-msg",style=dict(color=C["green"],fontSize=11,marginTop=4)),
    ], style=dict(background=C["surface"],border=f"1px solid {cl(C['purple'],0.4)}",borderRadius=8,padding=18,marginBottom=18))

    table = dash_table.DataTable(
        id="pipeline-table", data=rows,
        columns=[{"name":c,"id":c} for c in rows[0].keys()] if rows else [],
        hidden_columns=["_idx"],
        row_selectable="single", selected_rows=[],
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD+[
            {"if":{"filter_query":'{Priority} = "High"',  "column_id":"Priority"},"color":C["red"],   "fontWeight":700},
            {"if":{"filter_query":'{Priority} = "Medium"',"column_id":"Priority"},"color":C["amber"]},
            {"if":{"filter_query":'{Priority} = "Low"',   "column_id":"Priority"},"color":C["green"]},
        ],
        sort_action="native", filter_action="native",
        page_size=12, style_table={"overflowX":"auto"}, export_format="xlsx",
    )

    actions = card([
        section_lbl("Pipeline Actions"),
        html.Button("✅ Promote → Portfolio", id="promote-pipe-btn",style={**BTN(C["green"]),"width":"100%","marginBottom":8}),
        html.Button("🗑 Delete Selected",     id="delete-pipe-btn",  style={**BTN(C["red"]),  "width":"100%"}),
        html.Div(id="pipe-action-msg",style=dict(marginTop=10,color=C["muted"],fontSize=11)),
    ], dict(minWidth=200))

    return html.Div([
        form,
        html.Div([
            html.Div(table, style=dict(flex=3, minWidth=0)),
            html.Div([dcc.Graph(figure=fig_funnel,config={"displayModeBar":False}), actions],
                     style=dict(flex=1,display="flex",flexDirection="column",gap=16,minWidth=280)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap")),
    ])


def tab_proforma(placeholders, config):
    mo = month_options()
    rows = []
    for i, p in enumerate(placeholders):
        midx = p.get("expected_month",0)
        mlbl = mo[midx]["label"] if 0 <= midx < len(mo) else f"M{midx}"
        rows.append({
            "_idx": i,
            "Name": p["name"], "Strategy": p.get("strategy",""),
            "Type": p.get("deal_type",""), "Region": p.get("region",""),
            "Size ($M)": fmt_m(p.get("size",0)),
            "Target IRR": f"{p.get('target_irr',0)*100:.1f}%",
            "Expected": mlbl,
        })

    by_month = {}
    for p in placeholders:
        midx = p.get("expected_month",0)
        mlbl = mo[midx]["label"] if 0<=midx<len(mo) else "?"
        by_month[mlbl] = by_month.get(mlbl,0)+p.get("size",0)

    fig = go.Figure()
    if by_month:
        fig.add_trace(go.Bar(x=list(by_month.keys()), y=list(by_month.values()),
                             marker_color=C["teal"],
                             text=[fmt_m(v) for v in by_month.values()],
                             textposition="outside", textfont_color=C["text"]))
    fig.update_layout(**CHART, height=300, title="Planned Future Deployments ($M)")

    form = html.Div([
        section_lbl("Add Placeholder / Future Deal"),
        _form_row(
            _field("Name",         dcc.Input(id="ph-name",     type="text",  style=INP, placeholder="GP-Led Placeholder 1")),
            _field("Strategy",     dcc.Dropdown(id="ph-strategy", options=dd_opts(STRATEGIES), value=STRATEGIES[0],  style=_dd())),
            _field("Type",         dcc.Dropdown(id="ph-dtype",   options=dd_opts(DEAL_TYPES),  value="Secondary",    style=_dd())),
            _field("Region",       dcc.Dropdown(id="ph-region",  options=dd_opts(REGIONS),     value="North America",style=_dd())),
            _field("Size ($M)",    dcc.Input(id="ph-size",   type="number", value=30, step=0.5, style=INP)),
            _field("Target IRR %", dcc.Input(id="ph-irr",    type="number", value=17, step=0.5, style=INP)),
            _field("Expected Month", dcc.Dropdown(id="ph-month", options=month_options(), value=3, style=_dd())),
            html.Div([html.Label(" ",style=dict(display="block",marginBottom=4,fontSize=9)),
                      html.Button("+ Add",id="add-ph-btn",style={**BTN(C["teal"]),"minWidth":80})]),
        ),
        html.Div(id="ph-msg",style=dict(color=C["green"],fontSize=11,marginTop=4)),
    ], style=dict(background=C["surface"],border=f"1px solid {cl(C['teal'],0.4)}",borderRadius=8,padding=18,marginBottom=18))

    # Pro forma summary vs current
    total_current = sum(d.get("nav",0) for d in [])  # fed from port-store via route
    total_ph      = sum(p.get("size",0) for p in placeholders)

    table = dash_table.DataTable(
        id="ph-table", data=rows,
        columns=[{"name":c,"id":c} for c in rows[0].keys()] if rows else [],
        hidden_columns=["_idx"],
        row_selectable="single", selected_rows=[],
        style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
        sort_action="native", page_size=12, style_table={"overflowX":"auto"}, export_format="xlsx",
    )

    actions = card([
        section_lbl("Placeholder Actions"),
        html.Button("🗑 Delete Selected", id="delete-ph-btn", style={**BTN(C["red"]),"width":"100%"}),
        html.Div(id="ph-action-msg",style=dict(marginTop=10,color=C["muted"],fontSize=11)),
    ], dict(minWidth=180))

    return html.Div([
        form,
        html.Div([
            kpi("Total Planned",       fmt_m(total_ph), f"{len(placeholders)} placeholders", C["teal"]),
        ], style=dict(display="flex",gap=10,marginBottom=16)),
        html.Div([
            html.Div(table, style=dict(flex=3, minWidth=0)),
            html.Div([dcc.Graph(figure=fig,config={"displayModeBar":False}), actions],
                     style=dict(flex=1,display="flex",flexDirection="column",gap=16,minWidth=280)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap")),
    ])


def tab_analytics(portfolio, pipeline, config):
    all_deals = [dict(d, _pool="Portfolio") for d in portfolio] + [
        dict(name=p["name"], strategy=p.get("strategy",""), nav=p.get("size",0),
             target_irr=p.get("target_irr",0), region=p.get("region",""),
             sector=p.get("sector",""), vintage=2026, deal_type="Secondary",
             _pool="Pipeline")
        for p in pipeline
    ]
    if not all_deals:
        return card(html.P("No data yet. Add deals on the Portfolio tab.", style=dict(color=C["muted"])))

    def group_nav(key_fn):
        d = {}
        for x in all_deals:
            k = key_fn(x)
            d[k] = d.get(k,0)+x.get("nav",0)
        return d

    by_strat  = group_nav(lambda x: x.get("strategy","?"))
    by_region = group_nav(lambda x: x.get("region","Other"))
    by_vint   = group_nav(lambda x: str(x.get("vintage","?")))
    by_sector = group_nav(lambda x: x.get("sector","Other"))
    by_type   = {"Secondary":0,"Co-Investment":0}
    for x in all_deals:
        k = x.get("deal_type","Secondary")
        by_type[k] = by_type.get(k,0)+x.get("nav",0)

    m = portfolio_metrics(portfolio)

    def bar(lbls, vals, color, title):
        f = go.Figure(go.Bar(x=lbls, y=vals, marker_color=color,
                             text=[fmt_m(v) for v in vals], textposition="outside", textfont_color=C["text"]))
        f.update_layout(**CHART, height=300, title=title)
        return f

    def pie(lbls, vals, colors, title):
        f = go.Figure(go.Pie(labels=lbls, values=vals, hole=0.52,
                             marker_colors=colors, textfont_color=C["text"]))
        f.update_layout(**CHART, height=300, title=title, margin=dict(t=50,b=10,l=10,r=10))
        return f

    palette = [C["blue"],C["purple"],C["teal"],C["green"],C["amber"],C["pink"],C["sky"],C["red"]]
    fig_strat  = pie(list(by_strat.keys()),  list(by_strat.values()),  palette[:len(by_strat)], "Strategy Exposure")
    fig_region = bar(list(by_region.keys()), list(by_region.values()), C["sky"],  "Regional Exposure")
    fig_vint   = bar([k for k in sorted(by_vint.keys())],
                     [by_vint[k] for k in sorted(by_vint.keys())], C["purple"], "Vintage Exposure")
    fig_sector = pie(list(by_sector.keys()), list(by_sector.values()), palette[:len(by_sector)], "Sector Exposure")
    fig_type   = pie(list(by_type.keys()),   list(by_type.values()),   [C["sky"],C["teal"]],    "Secondary vs Co-Invest")

    cats  = ["Top 1","Top 3","Top 5"]
    vals  = [m["top1"]*100, m["top3"]*100, m["top5"]*100]
    limits= [15,40,60]
    fig_conc = go.Figure(go.Bar(x=cats,y=vals,
                                 marker_color=[C["red"] if v>l else C["green"] for v,l in zip(vals,limits)],
                                 text=[f"{v:.1f}%" for v in vals],textposition="outside",textfont_color=C["text"]))
    for lim in limits:
        fig_conc.add_hline(y=lim,line_dash="dash",line_color=C["amber"],opacity=0.6)
    fig_conc.update_layout(**CHART, height=300, title="Concentration Risk (% of NAV)")

    tgt = float(config.get("target_net_twr",0.13))*100
    fig_scatter = go.Figure()
    for pool, color in [("Portfolio",C["blue"]),("Pipeline",C["purple"])]:
        ds = [d for d in all_deals if d.get("_pool")==pool]
        if ds:
            fig_scatter.add_trace(go.Scatter(
                x=[d.get("nav",0) for d in ds],
                y=[d.get("target_irr",0)*100 for d in ds],
                mode="markers+text", name=pool,
                marker=dict(color=color,size=10,opacity=0.85,line=dict(color=C["border"],width=1)),
                text=[d.get("name","")[-10:] for d in ds],
                textposition="top center", textfont=dict(color=C["text"],size=9),
                hovertext=[f"<b>{d.get('name','')}</b><br>{d.get('strategy','')}<br>NAV:{fmt_m(d.get('nav',0))}<br>Region:{d.get('region','')}" for d in ds],
                hoverinfo="text",
            ))
    fig_scatter.add_hline(y=tgt, line_dash="dash", line_color=C["amber"],
                          annotation_text=f"Target {tgt:.1f}%", annotation_position="right")
    fig_scatter.update_layout(**CHART, height=340, title="IRR vs NAV — Deal-level Scatter",
                               xaxis_title="NAV ($M)", yaxis_title="Target IRR (%)")

    wall_rows = [{"Deal":d.get("name",""),"Pool":d.get("_pool",""),"Strategy":d.get("strategy",""),
                  "Type":d.get("deal_type",""),"Region":d.get("region",""),"Sector":d.get("sector",""),
                  "NAV":fmt_m(d.get("nav",0)),"IRR":f"{d.get('target_irr',0)*100:.1f}%","Vintage":d.get("vintage","")}
                 for d in all_deals]
    wall_tbl = dash_table.DataTable(data=wall_rows, columns=[{"name":c,"id":c} for c in wall_rows[0]],
                                    style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                    sort_action="native", filter_action="native",
                                    page_size=15, style_table={"overflowX":"auto"}, export_format="xlsx")

    return html.Div([
        html.Div([
            card([dcc.Graph(figure=fig_strat,  config={"displayModeBar":False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_region, config={"displayModeBar":False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_type,   config={"displayModeBar":False})], dict(flex=1)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap",marginBottom=16)),
        html.Div([
            card([dcc.Graph(figure=fig_vint,   config={"displayModeBar":False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_sector, config={"displayModeBar":False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_conc,   config={"displayModeBar":False})], dict(flex=1)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap",marginBottom=16)),
        card([dcc.Graph(figure=fig_scatter, config={"displayModeBar":False})], dict(marginBottom=16)),
        card([section_lbl("Full Portfolio & Pipeline Detail"), wall_tbl]),
    ])


def tab_segments(portfolio, pipeline, placeholders, config):
    seed_deals = [d for d in portfolio if d.get("segment","Seed")=="Seed"]
    new_deals  = [d for d in portfolio if d.get("segment","Seed")=="New"]
    mm_deals   = [d for d in portfolio if d.get("segment","Seed")=="MoneyMarket"]

    seed_nav = sum(d["nav"] for d in seed_deals)
    new_nav  = sum(d["nav"] for d in new_deals)
    mm_nav   = sum(d["nav"] for d in mm_deals)
    pipe_nav = sum(p.get("size",0) for p in pipeline)
    ph_nav   = sum(p.get("size",0) for p in placeholders)
    total_nav= seed_nav+new_nav+mm_nav

    seed_twr = w_avg(seed_deals,"target_irr") if seed_deals else 0
    new_twr  = w_avg(new_deals, "target_irr") if new_deals  else 0
    mm_twr   = 0.03
    pipe_twr = w_avg(pipeline,"target_irr","size") if pipeline else 0
    total_twr= (seed_nav*seed_twr+new_nav*new_twr+mm_nav*mm_twr)/total_nav if total_nav else 0

    kpi_row = html.Div([
        kpi("Total Portfolio",  fmt_m(total_nav), f"TWR: {total_twr:.1%}", C["blue"],  140),
        kpi("Seed Portfolio",   fmt_m(seed_nav),  f"TWR: {seed_twr:.1%}", C["green"], 140),
        kpi("New Deals",        fmt_m(new_nav),   f"TWR: {new_twr:.1%}",  C["purple"],140),
        kpi("Money Market",     fmt_m(mm_nav),    f"TWR: {mm_twr:.1%}",   C["amber"], 130),
        kpi("Pipeline",         fmt_m(pipe_nav),  f"Est IRR: {pipe_twr:.1%}", C["teal"],130),
        kpi("Pro Forma",        fmt_m(ph_nav),    f"{len(placeholders)} placeholders", C["pink"],130),
    ], style=dict(display="flex",gap=10,flexWrap="wrap",marginBottom=16))

    # 12-month cumulative TWR forecast by segment
    tgt = float(config.get("target_net_twr",0.13))
    base = datetime(2026,1,1)
    months = [(base+relativedelta(months=i)).strftime("%b %Y") for i in range(12)]
    total_twrs = [(((1+tgt)**(i/12))-1)*100         for i in range(12)]
    seed_twrs  = [(((1+tgt*0.95)**(i/12))-1)*100    for i in range(12)]
    new_twrs   = [(((1+tgt*1.05)**(i/12))-1)*100    for i in range(12)]
    mm_twrs    = [(((1.03)**(i/12))-1)*100          for i in range(12)]

    fig_twr = go.Figure()
    for name, y, color, dash in [
        ("Total Portfolio", total_twrs, C["blue"],   "solid"),
        ("Seed Portfolio",  seed_twrs,  C["green"],  "dash"),
        ("New Deals",       new_twrs,   C["purple"], "dot"),
        ("Money Market",    mm_twrs,    C["amber"],  "dashdot"),
    ]:
        fig_twr.add_trace(go.Scatter(x=months,y=y,name=name,mode="lines",
                                     line=dict(color=color,width=2,dash=dash)))
    fig_twr.update_layout(**CHART, height=360, title="12-Month Cumulative TWR Forecast by Segment",
                           yaxis_title="Cumulative TWR (%)", hovermode="x unified",
                           legend=dict(orientation="h",y=1.08,x=0))

    # Allocation & contribution charts
    seg_labels = ["Seed","New Deals","Money Market","Pipeline","Pro Forma"]
    seg_vals   = [seed_nav, new_nav, mm_nav, pipe_nav, ph_nav]
    seg_colors = [C["green"],C["purple"],C["amber"],C["teal"],C["pink"]]
    fig_alloc = go.Figure(go.Pie(labels=seg_labels, values=seg_vals, hole=0.5,
                                  marker_colors=seg_colors, textfont_color=C["text"]))
    fig_alloc.update_layout(**CHART, height=300, title="Segment Allocation")

    contrib_segs = ["Seed","New Deals","MM"]
    contrib_vals = [seed_nav*seed_twr*100, new_nav*new_twr*100, mm_nav*mm_twr*100]
    fig_contrib = go.Figure(go.Bar(x=contrib_segs, y=contrib_vals,
                                    marker_color=[C["green"],C["purple"],C["amber"]],
                                    text=[f"{v:.1f}" for v in contrib_vals],textposition="outside",
                                    textfont_color=C["text"]))
    fig_contrib.update_layout(**CHART, height=300, title="TWR Contribution (NAV × IRR)")

    def seg_table(deals, name):
        if not deals:
            return html.P(f"No {name} deals yet.", style=dict(color=C["muted"],fontSize=12))
        data = [{"Deal":d["name"],"NAV":fmt_m(d["nav"]),"IRR":f"{d.get('target_irr',0)*100:.1f}%",
                 "Vintage":str(d.get("vintage","")),"Manager":d.get("manager","")} for d in deals]
        return dash_table.DataTable(data=data, columns=[{"name":c,"id":c} for c in data[0]],
                                    style_cell=TBL_CELL, style_header=TBL_HEAD,
                                    style_data_conditional=TBL_ODD, page_size=8,
                                    style_table={"overflowX":"auto"})

    return html.Div([
        kpi_row,
        card([dcc.Graph(figure=fig_twr, config={"displayModeBar":True})], dict(marginBottom=16)),
        html.Div([
            card([dcc.Graph(figure=fig_alloc,  config={"displayModeBar":False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_contrib,config={"displayModeBar":False})], dict(flex=1)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap",marginBottom=16)),
        html.Div([
            card([section_lbl("Seed Portfolio Deals"), seg_table(seed_deals,"seed")], dict(flex=1)),
            card([section_lbl("New Deals"),            seg_table(new_deals, "new")],  dict(flex=1)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap")),
    ])


def tab_drypowder(portfolio, placeholders, config):
    dp  = float(config.get("dry_powder",300) or 300)
    nav = sum(d.get("nav",0) for d in portfolio)
    fc  = forecast_dp(nav, dp, placeholders, config, 12)

    months   = [f["month"]         for f in fc]
    dp_vals  = [f["dry_powder"]    for f in fc]
    nav_vals = [f["nav"]           for f in fc]
    dists    = [f["distributions"] for f in fc]
    calls    = [f["calls"]         for f in fc]

    fig = make_subplots(specs=[[{"secondary_y":True}]])
    fig.add_trace(go.Scatter(x=months,y=dp_vals,name="Dry Powder",
                              line=dict(color=C["blue"],width=3),fill="tozeroy",
                              fillcolor=cl(C["blue"],0.15),marker=dict(size=5,color=C["sky"])),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=months,y=nav_vals,name="Portfolio NAV",
                              line=dict(color=C["green"],width=2,dash="dash"),marker=dict(size=4)),
                  secondary_y=False)
    fig.add_trace(go.Bar(x=months,y=calls,name="Capital Calls",
                          marker_color=cl(C["red"],0.65)),secondary_y=True)
    fig.add_trace(go.Bar(x=months,y=dists,name="Distributions",
                          marker_color=cl(C["green"],0.55)),secondary_y=True)
    fig.update_xaxes(gridcolor=C["border"])
    fig.update_yaxes(title_text="$M",secondary_y=False,gridcolor=C["border"])
    fig.update_yaxes(title_text="Flows $M",secondary_y=True,showgrid=False)
    fig.update_layout(**CHART, height=400, title="12-Month Dry Powder Forecast",
                      hovermode="x unified", barmode="group")

    # Summary kpis
    kpi_row = html.Div([
        kpi("Current Dry Powder",   fmt_m(dp),                "Available now",          C["blue"]),
        kpi("Planned Calls (12M)",  fmt_m(sum(calls)),        "From placeholders",      C["amber"]),
        kpi("Forecast Distributions",fmt_m(sum(dists)),       "Over 12 months",         C["green"]),
        kpi("Forecast End DP",      fmt_m(dp_vals[-1] if dp_vals else 0), "In 12 months",C["teal"]),
    ], style=dict(display="flex",gap=10,flexWrap="wrap",marginBottom=16))

    # Bite-size table
    bs = bite_sizes(config)
    bite_rows = [{"Strategy":s,"Min $M":fmt_m(v["min"]),"Desired $M":fmt_m(v["desired"]),"Max $M":fmt_m(v["max"]),
                  "Min %":f"{v['min_pct']*100:.2f}%","Desired %":f"{v['desired_pct']*100:.2f}%","Max %":f"{v['max_pct']*100:.2f}%"}
                 for s,v in bs.items()]
    bite_tbl = dash_table.DataTable(data=bite_rows, columns=[{"name":c,"id":c} for c in bite_rows[0]],
                                     style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                     style_table={"overflowX":"auto"})

    dp_tbl_rows = [{"Month":f["month"],"Dry Powder $M":fmt_m(f["dry_powder"]),"NAV $M":fmt_m(f["nav"]),
                    "Distributions $M":fmt_m(f["distributions"]),"Calls $M":fmt_m(f["calls"]) if f["calls"]>0 else "—"}
                   for f in fc]
    dp_tbl = dash_table.DataTable(data=dp_tbl_rows, columns=[{"name":c,"id":c} for c in dp_tbl_rows[0]],
                                   style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                   page_size=12, style_table={"overflowX":"auto"})

    return html.Div([
        kpi_row,
        card([dcc.Graph(figure=fig, config={"displayModeBar":True})], dict(marginBottom=16)),
        html.Div([
            card([section_lbl("Bite Size Guide (on current dry powder)"), bite_tbl], dict(flex=1)),
            card([section_lbl("Monthly Schedule"),                         dp_tbl],  dict(flex=1)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap")),
    ])


def tab_pacing(portfolio, pipeline, placeholders, config):
    df = build_pacing(portfolio, pipeline, placeholders, config)

    fig_dep = go.Figure()
    fig_dep.add_trace(go.Bar(x=df["Quarter"],y=df["Deployment ($M)"],name="New Deployment",marker_color=C["blue"]))
    fig_dep.add_trace(go.Bar(x=df["Quarter"],y=df["Repayments/Dist ($M)"],name="Repayments/Dist",marker_color=C["teal"]))
    fig_dep.update_layout(**CHART, height=340, barmode="stack", title="Capital Deployment & Distributions")

    fig_nav = go.Figure()
    fig_nav.add_trace(go.Scatter(x=df["Quarter"],y=df["NAV ($M)"],mode="lines+markers",name="NAV",
                                  line=dict(color=C["sky"],width=3)))
    fig_nav.add_trace(go.Scatter(x=df["Quarter"],y=df["Dry Powder ($M)"],mode="lines+markers",name="Dry Powder",
                                  line=dict(color=C["amber"],width=2,dash="dash")))
    fig_nav.update_layout(**CHART, height=340, title="NAV & Dry Powder Projection")

    fig_util = go.Figure(go.Bar(x=df["Quarter"],y=df["Utilisation %"],marker_color=C["purple"],
                                 text=[f"{v:.0f}%" for v in df["Utilisation %"]],textposition="outside",
                                 textfont_color=C["text"]))
    fig_util.update_layout(**CHART, height=300, title="Fund Utilisation Path", yaxis_title="%")

    tbl = dash_table.DataTable(data=df.to_dict("records"),
                                columns=[{"name":c,"id":c} for c in df.columns],
                                style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                page_size=16, style_table={"overflowX":"auto"}, export_format="xlsx")
    return html.Div([
        html.Div([
            card([dcc.Graph(figure=fig_dep,config={"displayModeBar":False})],dict(flex=1)),
            card([dcc.Graph(figure=fig_nav,config={"displayModeBar":False})],dict(flex=1)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap",marginBottom=16)),
        card([dcc.Graph(figure=fig_util,config={"displayModeBar":False})],dict(marginBottom=16)),
        card([section_lbl("Quarterly Pacing Schedule"), tbl]),
    ])


def tab_returns(portfolio, pipeline, config):
    m         = portfolio_metrics(portfolio)
    curr_irr  = m["w_irr"]
    nav       = m["total_nav"]
    dp        = float(config.get("dry_powder",300) or 300)
    tgt       = float(config.get("target_net_twr",0.13))
    fee       = float(config.get("management_fee",0.0125))
    carry     = float(config.get("carry_rate",0.125))
    hurdle    = float(config.get("hurdle_rate",0.10))
    loss      = float(config.get("loss_drag",0.01))
    liq       = float(config.get("liquidity_reserve_pct",0.05))
    cy        = float(config.get("cash_yield",0.03))
    invested  = max(0,1-liq)
    gross_needed = (tgt+fee+loss-liq*cy)/invested if invested else tgt
    if gross_needed > hurdle:
        gross_needed += (gross_needed-hurdle)*carry
    req_irr = calc_required_irr(curr_irr, nav, dp, config)

    hold_range = [2,3,4,5,6,7]
    req_moic   = [(1+gross_needed)**h for h in hold_range]
    req_rows   = [{"Hold (y)":h,"Req MOIC":f"{m:.2f}x","Gross IRR Target":f"{gross_needed:.1%}",
                   "Exit on $30M":fmt_m(30*m),"Exit on $50M":fmt_m(50*m),"Exit on $100M":fmt_m(100*m)}
                  for h,m in zip(hold_range,req_moic)]
    req_tbl = dash_table.DataTable(data=req_rows, columns=[{"name":c,"id":c} for c in req_rows[0]],
                                    style_cell=TBL_CELL, style_header=TBL_HEAD,
                                    style_data_conditional=TBL_ODD, style_table={"overflowX":"auto"})

    fig_moic = go.Figure()
    fig_moic.add_trace(go.Scatter(x=hold_range,y=req_moic,mode="lines+markers",name="Required MOIC",
                                   line=dict(color=C["amber"],width=3)))
    fig_moic.update_layout(**CHART, height=300, title="Required MOIC by Hold Period",
                            xaxis_title="Hold (y)", yaxis_title="MOIC")

    # Waterfall: Net TWR → Required Gross
    wf_steps = ["Target Net TWR","+ Mgmt Fee","+ Loss Drag","- Cash Yield × Reserve","÷ Invested Ratio","+ Carry Drag"]
    wf_vals  = [tgt*100, fee*100, loss*100, -(liq*cy)*100, 0, 0]
    # simplify: just show gross_needed as total
    wf_display = [
        ("Target Net TWR (LPs)",    f"{tgt:.2%}"),
        ("+ Management Fee",        f"{fee:.3%}"),
        ("+ Loss Drag",             f"{loss:.2%}"),
        ("- Cash Yield on Reserves",f"-{liq*cy:.3%}"),
        ("÷ Invested Ratio",        f"÷ {invested:.0%}"),
        ("+ Carry Drag (>hurdle)",  f"+variable ({carry:.0%})"),
        ("══════════════════════",  "════════"),
        ("REQUIRED GROSS DEAL IRR", f"{gross_needed:.2%}"),
    ]
    wf_table = html.Table([
        html.Tbody([
            html.Tr([
                html.Td(step, style=dict(fontFamily=C["mono"],fontSize=13,padding="6px 12px",
                                          fontWeight="bold" if "═" in step or "REQUIRED" in step else "normal",
                                          color=C["green"] if "REQUIRED" in step else C["text"])),
                html.Td(val,  style=dict(fontFamily=C["mono"],fontSize=13,padding="6px 12px",
                                          textAlign="right", fontWeight="bold",
                                          color=C["green"] if "REQUIRED" in step else C["text"])),
            ]) for step,val in wf_display
        ])
    ], style=dict(width="100%", borderCollapse="collapse",
                  background=C["surface"], borderRadius=8, overflow="hidden"))

    # Deal scatter
    all_deals = list(portfolio)+[
        dict(name=p["name"],nav=p.get("size",0),target_irr=p.get("target_irr",0),
             hold_period=4.0, _pool="Pipeline")
        for p in pipeline
    ]
    fig_scatter = go.Figure()
    for pool, color in [("Portfolio",C["blue"]),("Pipeline",C["purple"])]:
        ds = [d for d in all_deals if d.get("_pool","Portfolio")==pool]
        if ds:
            fig_scatter.add_trace(go.Scatter(
                x=[d.get("hold_period",0) for d in ds],
                y=[d.get("target_irr",0)*100 for d in ds],
                mode="markers+text", name=pool,
                marker=dict(color=color,size=[max(d.get("nav",10)*0.25,6) for d in ds],opacity=0.85),
                text=[d.get("name","")[-10:] for d in ds],
                textposition="top center", textfont=dict(color=C["text"],size=9),
            ))
    fig_scatter.add_hline(y=gross_needed*100, line_dash="dash", line_color=C["amber"],
                           annotation_text=f"Gross target {gross_needed:.1%}")
    fig_scatter.update_layout(**CHART, height=340, title="Deal IRR vs Hold Period",
                               xaxis_title="Hold (y)", yaxis_title="IRR (%)")

    # Monte Carlo section
    mc_section = html.Div([
        card([
            section_lbl("Monte Carlo TWR Simulation"),
            _form_row(
                _field("Current Portfolio IRR", html.Div(f"{curr_irr:.2%}",
                        style=dict(fontFamily=C["mono"],fontSize=16,color=C["green"],padding="6px 0"))),
                _field("Future Deals Mean IRR %", dcc.Input(id="mc-mean",type="number",value=25,step=0.5,style={**INP,"width":90})),
                _field("Future Deals Std Dev %",  dcc.Input(id="mc-std",  type="number",value=5,  step=0.5,style={**INP,"width":90})),
                _field("# Simulations", dcc.Dropdown(id="mc-nsims",
                        options=[{"label":"1,000","value":1000},{"label":"5,000","value":5000},{"label":"10,000","value":10000}],
                        value=5000, style={**_dd(),"width":120})),
                html.Div([html.Label(" ",style=dict(display="block",marginBottom=4,fontSize=9)),
                          html.Button("▶ Run Simulation",id="mc-run-btn",style={**BTN(C["blue"]),"minWidth":140})]),
            ),
            html.Div(id="mc-results"),
        ])
    ], style=dict(marginTop=16))

    return html.Div([
        html.Div([
            kpi("Net Target",     f"{tgt:.1%}",          "Annualised to LPs",    C["teal"]),
            kpi("Gross Target",   f"{gross_needed:.1%}", "Net + fee drag",       C["amber"]),
            kpi("Required IRR",   f"{req_irr:.1%}",      "On future deals",      C["red"] if req_irr>0.30 else C["green"]),
            kpi("MOIC @ 3y",      f"{(1+gross_needed)**3:.2f}x","Required",      C["sky"]),
            kpi("MOIC @ 5y",      f"{(1+gross_needed)**5:.2f}x","Required",      C["purple"]),
            kpi("Carry Rate",     f"{carry:.1%}",        f"Hurdle {hurdle:.1%}", C["pink"]),
        ], style=dict(display="flex",gap=10,flexWrap="wrap",marginBottom=16)),
        html.Div([
            card([section_lbl("Required Return Thresholds"), req_tbl], dict(flex=2)),
            card([section_lbl("IRR Waterfall: Gross → Net"), wf_table],dict(flex=1, minWidth=300)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap",marginBottom=16)),
        html.Div([
            card([dcc.Graph(figure=fig_moic,   config={"displayModeBar":False})],dict(flex=1)),
            card([dcc.Graph(figure=fig_scatter,config={"displayModeBar":False})],dict(flex=2)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap",marginBottom=16)),
        mc_section,
    ])


def tab_settings(config):
    dp   = float(config.get("dry_powder",300) or 300)
    bs   = bite_sizes(config)
    gma  = bs.get("GP-Led (Multi-Asset)",{})

    def num(id_, val, step=0.005):
        return dcc.Input(id=id_, type="number", value=round(val,6), step=step, style=INP)

    return html.Div([
        html.Div([
            card([
                section_lbl("Current Bite Sizes (on dry powder)"),
                kpi("Min Bite",     fmt_m(gma.get("min",0)),     f"{gma.get('min_pct',0)*100:.2f}% of DP", C["teal"]),
                html.Div(style=dict(height=10)),
                kpi("Desired Bite", fmt_m(gma.get("desired",0)), f"{gma.get('desired_pct',0)*100:.2f}% of DP", C["sky"]),
                html.Div(style=dict(height=10)),
                kpi("Max Bite",     fmt_m(gma.get("max",0)),     f"{gma.get('max_pct',0)*100:.2f}% of DP", C["amber"]),
            ], dict(flex=1, minWidth=220)),
            card([
                section_lbl("Fund Parameters"),
                html.Div([
                    _field("Distribution Rate (annual)",  num("cfg-dist",   float(config.get("distribution_rate",0.20)),0.01)),
                    _field("Cash Yield",                  num("cfg-cy",     float(config.get("cash_yield",0.03)),0.005)),
                    _field("Hurdle Rate",                 num("cfg-hurdle", float(config.get("hurdle_rate",0.10)),0.005)),
                    _field("Carry Rate",                  num("cfg-carry",  float(config.get("carry_rate",0.125)),0.005)),
                    _field("Loss Drag",                   num("cfg-loss",   float(config.get("loss_drag",0.01)),0.005)),
                    _field("Liquidity Reserve",           num("cfg-liq",    float(config.get("liquidity_reserve_pct",0.05)),0.005)),
                    _field("Avg Hold Period (y)",         dcc.Input(id="cfg-hold",     type="number",value=float(config.get("avg_hold_period",5.0)),step=0.5,style=INP)),
                    _field("Deployment Years",            dcc.Input(id="cfg-dep-years",type="number",value=float(config.get("deployment_years",4.0)),step=0.5,style=INP)),
                    _field("Deals Per Year",              dcc.Input(id="cfg-deals-py", type="number",value=float(config.get("deals_per_year",6.0)),step=1,  style=INP)),
                ], style=dict(display="grid",gridTemplateColumns="1fr 1fr 1fr",gap=12)),
                html.Div(style=dict(height=14)),
                section_lbl("Bite Size Percentages (% of Dry Powder)"),
                html.Div([
                    _field("Min %",     dcc.Input(id="cfg-bite-min",     type="number",value=round(float(config.get("bite_min_pct",0.005))*100,3),step=0.1,style=INP)),
                    _field("Desired %", dcc.Input(id="cfg-bite-desired", type="number",value=round(float(config.get("bite_desired_pct",0.0275))*100,3),step=0.25,style=INP)),
                    _field("Max %",     dcc.Input(id="cfg-bite-max",     type="number",value=round(float(config.get("bite_max_pct",0.05))*100,3),step=0.25,style=INP)),
                ], style=dict(display="grid",gridTemplateColumns="1fr 1fr 1fr",gap=12)),
                html.Div(style=dict(height=12)),
                html.Button("💾 Save Settings", id="save-cfg-btn",
                            style={**BTN(C["blue"]),"width":"100%"}),
                html.Div(id="cfg-msg",style=dict(marginTop=8,color=C["green"],fontSize=11)),
            ], dict(flex=3, minWidth=360)),
        ], style=dict(display="flex",gap=16,flexWrap="wrap")),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

# Auto-calc unfunded
@app.callback(
    Output("unfunded-calc","children"),
    Input("port-total-commit","value"), Input("port-curr-commit","value"),
)
def calc_unfunded(tc, cc):
    try: return fmt_m(float(tc or 0)-float(cc or 0))
    except: return "$—"


# ── Portfolio: add or update ─────────────────────────────────────────────────
@app.callback(
    Output("port-store","data"),
    Output("next-id","data"),
    Output("port-msg","children"),
    Input("add-port-btn","n_clicks"),
    State("port-store","data"), State("next-id","data"), State("edit-idx","data"),
    State("port-name","value"), State("port-manager","value"),
    State("port-strategy","value"), State("port-dtype","value"),
    State("port-stage","value"), State("port-sector","value"),
    State("port-region","value"), State("port-currency","value"),
    State("port-total-commit","value"), State("port-curr-commit","value"),
    State("port-nav","value"), State("port-irr","value"),
    State("port-hold","value"), State("port-moic","value"),
    State("port-vintage","value"), State("port-segment","value"),
    State("port-alloc-status","value"),
    prevent_initial_call=True,
)
def add_or_update_portfolio(_, portfolio, nid, edit_idx,
                             name, manager, strategy, dtype, stage, sector, region,
                             currency, total_commit, curr_commit, nav, irr,
                             hold, moic, vintage, segment, alloc_status):
    if not name:
        return no_update, no_update, "⚠ Enter a deal name."
    p = portfolio or []
    irr_dec  = float(irr or 0)/100
    nav_val  = float(nav or 0)
    deal = dict(
        name=name, manager=manager or "", strategy=strategy, deal_type=dtype,
        stage=stage or "Buyout", sector=sector or "Diversified",
        region=region or "North America", currency=currency or "USD",
        total_commitment=float(total_commit or nav_val),
        current_commitment=float(curr_commit or nav_val),
        nav=nav_val, target_irr=irr_dec,
        hold_period=float(hold or 5), moic=float(moic or 1.0),
        vintage=int(vintage or datetime.now().year),
        segment=segment or "New", allocation_status=alloc_status or "Closed",
        date_added=datetime.now().isoformat()[:10],
    )
    if edit_idx is not None and 0 <= edit_idx < len(p):
        deal["id"] = p[edit_idx]["id"]
        p[edit_idx] = deal
        return p, nid, f"✓ Updated: {name}"
    else:
        deal["id"] = nid
        return p+[deal], nid+1, f"✓ Added: {name}"


# ── Portfolio: populate edit form ────────────────────────────────────────────
@app.callback(
    Output("edit-idx","data"),
    Output("port-name","value"), Output("port-manager","value"),
    Output("port-strategy","value"), Output("port-dtype","value"),
    Output("port-stage","value"), Output("port-sector","value"),
    Output("port-region","value"), Output("port-currency","value"),
    Output("port-total-commit","value"), Output("port-curr-commit","value"),
    Output("port-nav","value"), Output("port-irr","value"),
    Output("port-hold","value"), Output("port-moic","value"),
    Output("port-vintage","value"), Output("port-segment","value"),
    Output("port-alloc-status","value"),
    Output("port-msg","children",allow_duplicate=True),
    Input("edit-port-btn","n_clicks"),
    State("portfolio-table","selected_rows"), State("port-store","data"),
    prevent_initial_call=True,
)
def populate_edit(_, selected, portfolio):
    if not selected or not portfolio:
        return [no_update]*19
    idx = selected[0]
    if idx >= len(portfolio):
        return [no_update]*19
    d = portfolio[idx]
    return (
        idx,
        d["name"], d.get("manager",""),
        d.get("strategy",""), d.get("deal_type","Secondary"),
        d.get("stage","Buyout"), d.get("sector","Diversified"),
        d.get("region","North America"), d.get("currency","USD"),
        d.get("total_commitment",d.get("nav",0)),
        d.get("current_commitment",d.get("nav",0)),
        d.get("nav",0), round(d.get("target_irr",0)*100,2),
        d.get("hold_period",5), d.get("moic",1.0),
        d.get("vintage",2025), d.get("segment","New"),
        d.get("allocation_status","Closed"),
        f"📝 Editing: {d['name']} — make changes and click '+ Add Deal' to save."
    )


# ── Portfolio: clear form ────────────────────────────────────────────────────
@app.callback(
    Output("edit-idx","data",allow_duplicate=True),
    Output("port-name","value",allow_duplicate=True),
    Output("port-manager","value",allow_duplicate=True),
    Output("port-msg","children",allow_duplicate=True),
    Input("clear-port-btn","n_clicks"),
    prevent_initial_call=True,
)
def clear_form(_):
    return None, "", "", ""


# ── Portfolio: delete ────────────────────────────────────────────────────────
@app.callback(
    Output("port-store","data",allow_duplicate=True),
    Output("port-action-msg","children"),
    Input("delete-port-btn","n_clicks"),
    State("portfolio-table","selected_rows"), State("port-store","data"),
    prevent_initial_call=True,
)
def delete_portfolio(_, selected, portfolio):
    if not selected: return no_update, "Select a row first."
    idx = selected[0]
    if not portfolio or idx>=len(portfolio): return no_update, "Invalid selection."
    name = portfolio[idx]["name"]
    return [d for i,d in enumerate(portfolio) if i!=idx], f"🗑 Deleted: {name}"


# ── Pipeline: add ────────────────────────────────────────────────────────────
@app.callback(
    Output("pipe-store","data"),
    Output("next-id","data",allow_duplicate=True),
    Output("pipe-msg","children"),
    Input("add-pipe-btn","n_clicks"),
    State("pipe-store","data"), State("next-id","data"),
    State("pipe-name","value"), State("pipe-strategy","value"),
    State("pipe-stage-deal","value"), State("pipe-sector","value"),
    State("pipe-region","value"), State("pipe-size","value"),
    State("pipe-irr","value"), State("pipe-pipe-stage","value"),
    State("pipe-priority","value"),
    prevent_initial_call=True,
)
def add_pipeline(_, pipeline, nid, name, strategy, stage_deal, sector,
                  region, size, irr, pipe_stage, priority):
    if not name: return no_update, no_update, "⚠ Enter a deal name."
    deal = dict(id=nid, name=name, strategy=strategy, stage_deal=stage_deal,
                sector=sector, region=region, size=float(size or 0),
                target_irr=float(irr or 0)/100, pipeline_stage=pipe_stage,
                priority=priority, date_added=datetime.now().isoformat()[:10])
    return (pipeline or [])+[deal], nid+1, f"✓ Added pipeline: {name}"


# ── Pipeline: promote → portfolio ────────────────────────────────────────────
@app.callback(
    Output("pipe-store","data",allow_duplicate=True),
    Output("port-store","data",allow_duplicate=True),
    Output("next-id","data",allow_duplicate=True),
    Output("pipe-action-msg","children"),
    Input("promote-pipe-btn","n_clicks"),
    State("pipeline-table","selected_rows"),
    State("pipe-store","data"), State("port-store","data"), State("next-id","data"),
    prevent_initial_call=True,
)
def promote_pipeline(_, selected, pipeline, portfolio, nid):
    if not selected: return no_update, no_update, no_update, "Select a row first."
    idx = selected[0]
    pipeline = pipeline or []
    if idx>=len(pipeline): return no_update, no_update, no_update, "Invalid."
    p = pipeline[idx]
    size = float(p.get("size",0))
    promoted = dict(id=nid, name=p["name"],
                    manager="", strategy=p.get("strategy",""),
                    deal_type="Secondary", stage=p.get("stage_deal","Buyout"),
                    sector=p.get("sector",""), region=p.get("region",""),
                    currency="USD",
                    total_commitment=size, current_commitment=size, nav=size,
                    target_irr=float(p.get("target_irr",0)),
                    hold_period=5.0, moic=1.75, vintage=datetime.now().year,
                    segment="New", allocation_status="Pending Close",
                    date_added=datetime.now().isoformat()[:10])
    new_pipe = [d for i,d in enumerate(pipeline) if i!=idx]
    return new_pipe, (portfolio or [])+[promoted], nid+1, f"✅ Promoted: {p['name']}"


# ── Pipeline: delete ─────────────────────────────────────────────────────────
@app.callback(
    Output("pipe-store","data",allow_duplicate=True),
    Output("pipe-action-msg","children",allow_duplicate=True),
    Input("delete-pipe-btn","n_clicks"),
    State("pipeline-table","selected_rows"), State("pipe-store","data"),
    prevent_initial_call=True,
)
def delete_pipeline(_, selected, pipeline):
    if not selected: return no_update, "Select a row first."
    idx = selected[0]
    pipeline = pipeline or []
    if idx>=len(pipeline): return no_update, "Invalid."
    name = pipeline[idx]["name"]
    return [d for i,d in enumerate(pipeline) if i!=idx], f"🗑 Deleted: {name}"


# ── Placeholder: add ─────────────────────────────────────────────────────────
@app.callback(
    Output("ph-store","data"),
    Output("next-id","data",allow_duplicate=True),
    Output("ph-msg","children"),
    Input("add-ph-btn","n_clicks"),
    State("ph-store","data"), State("next-id","data"),
    State("ph-name","value"), State("ph-strategy","value"),
    State("ph-dtype","value"), State("ph-region","value"),
    State("ph-size","value"), State("ph-irr","value"),
    State("ph-month","value"),
    prevent_initial_call=True,
)
def add_placeholder(_, placeholders, nid, name, strategy, dtype, region, size, irr, month):
    if not name: return no_update, no_update, "⚠ Enter a name."
    ph = dict(id=nid, name=name, strategy=strategy, deal_type=dtype,
              region=region, size=float(size or 0), target_irr=float(irr or 0)/100,
              expected_month=int(month or 0), date_added=datetime.now().isoformat()[:10])
    return (placeholders or [])+[ph], nid+1, f"✓ Added: {name}"


# ── Placeholder: delete ──────────────────────────────────────────────────────
@app.callback(
    Output("ph-store","data",allow_duplicate=True),
    Output("ph-action-msg","children"),
    Input("delete-ph-btn","n_clicks"),
    State("ph-table","selected_rows"), State("ph-store","data"),
    prevent_initial_call=True,
)
def delete_placeholder(_, selected, placeholders):
    if not selected: return no_update, "Select a row first."
    idx = selected[0]
    placeholders = placeholders or []
    if idx>=len(placeholders): return no_update, "Invalid."
    name = placeholders[idx]["name"]
    return [d for i,d in enumerate(placeholders) if i!=idx], f"🗑 Deleted: {name}"


# ── Settings: save ───────────────────────────────────────────────────────────
@app.callback(
    Output("cfg-store","data",allow_duplicate=True),
    Output("cfg-msg","children"),
    Input("save-cfg-btn","n_clicks"),
    State("cfg-dist","value"),  State("cfg-cy","value"),
    State("cfg-hurdle","value"),State("cfg-carry","value"),
    State("cfg-loss","value"),  State("cfg-liq","value"),
    State("cfg-hold","value"),  State("cfg-dep-years","value"),
    State("cfg-deals-py","value"),
    State("cfg-bite-min","value"),State("cfg-bite-desired","value"),State("cfg-bite-max","value"),
    State("cfg-store","data"),
    prevent_initial_call=True,
)
def save_settings(_, dist, cy, hurdle, carry, loss, liq, hold, dep_yrs, deals_py,
                   bite_min, bite_des, bite_max, config):
    cfg = dict(config or DEFAULT_CONFIG)
    def f(v, k): return float(v) if v is not None else float(cfg.get(k,0))
    cfg.update({
        "distribution_rate":     f(dist,   "distribution_rate"),
        "cash_yield":            f(cy,     "cash_yield"),
        "hurdle_rate":           f(hurdle, "hurdle_rate"),
        "carry_rate":            f(carry,  "carry_rate"),
        "loss_drag":             f(loss,   "loss_drag"),
        "liquidity_reserve_pct": f(liq,    "liquidity_reserve_pct"),
        "avg_hold_period":       f(hold,   "avg_hold_period"),
        "deployment_years":      f(dep_yrs,"deployment_years"),
        "deals_per_year":        f(deals_py,"deals_per_year"),
        "bite_min_pct":          f(bite_min,"bite_min_pct")/100 if bite_min is not None else cfg.get("bite_min_pct",0.005),
        "bite_desired_pct":      f(bite_des,"bite_desired_pct")/100 if bite_des is not None else cfg.get("bite_desired_pct",0.0275),
        "bite_max_pct":          f(bite_max,"bite_max_pct")/100 if bite_max is not None else cfg.get("bite_max_pct",0.05),
    })
    return cfg, "✓ Settings saved"


# ── Monte Carlo TWR ──────────────────────────────────────────────────────────
@app.callback(
    Output("mc-results","children"),
    Input("mc-run-btn","n_clicks"),
    State("port-store","data"), State("cfg-store","data"),
    State("mc-mean","value"), State("mc-std","value"), State("mc-nsims","value"),
    prevent_initial_call=True,
)
def run_mc(_, portfolio, config, mean_pct, std_pct, n_sims):
    m        = portfolio_metrics(portfolio or [])
    curr_irr = m["w_irr"]
    nav      = m["total_nav"]
    dp       = float(config.get("dry_powder",300) or 300)
    tgt      = float(config.get("target_net_twr",0.13))
    fee      = float(config.get("management_fee",0.0125))
    carry    = float(config.get("carry_rate",0.125))
    hurdle   = float(config.get("hurdle_rate",0.10))
    loss     = float(config.get("loss_drag",0.01))
    liq      = float(config.get("liquidity_reserve_pct",0.05))
    cy       = float(config.get("cash_yield",0.03))
    invested = max(0,1-liq)

    np.random.seed(42)
    future_irrs = np.random.normal(float(mean_pct or 25)/100, float(std_pct or 5)/100, int(n_sims or 5000))
    results = []
    total = nav+dp
    for fir in future_irrs:
        blended = (nav*curr_irr + dp*fir)/total if total else 0
        gross   = blended*invested + cy*liq - fee - loss
        net     = gross-(gross-hurdle)*carry if gross>hurdle else gross
        results.append(net)
    results = np.array(results)
    prob    = (results>=tgt).mean()
    p5,p95  = np.percentile(results,5), np.percentile(results,95)

    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(x=results*100, nbinsx=60, marker_color=C["blue"],
                                     opacity=0.8, name="Simulated Net TWR"))
    fig_dist.add_vline(x=tgt*100, line_dash="dash", line_color=C["red"],
                       annotation_text=f"Target {tgt:.1%}")
    fig_dist.add_vline(x=np.mean(results)*100, line_dash="solid", line_color=C["green"],
                       annotation_text=f"Mean {np.mean(results):.1%}")
    fig_dist.update_layout(**CHART, height=320, title=f"Net TWR Distribution ({n_sims:,} simulations)",
                            xaxis_title="Net TWR (%)", yaxis_title="Frequency")

    # Sensitivity line
    irr_range = np.linspace(0.12,0.40,30)
    twr_sens  = []
    for fir in irr_range:
        blended = (nav*curr_irr + dp*fir)/total if total else 0
        gross   = blended*invested + cy*liq - fee - loss
        net     = gross-(gross-hurdle)*carry if gross>hurdle else gross
        twr_sens.append(net*100)
    fig_sens = go.Figure()
    fig_sens.add_trace(go.Scatter(x=irr_range*100, y=twr_sens, mode="lines+markers",
                                   line=dict(color=C["teal"],width=3), name="Net TWR"))
    fig_sens.add_hline(y=tgt*100, line_dash="dash", line_color=C["red"],
                       annotation_text=f"Target {tgt:.1%}")
    fig_sens.update_layout(**CHART, height=300, title="Net TWR Sensitivity to Future Deal IRR",
                            xaxis_title="Future Deal IRR (%)", yaxis_title="Net TWR (%)")

    stats = html.Div([
        html.Div([
            html.Strong("Prob. of Hitting Target: "),
            html.Span(f"{prob:.1%}", style=dict(fontSize=20,fontWeight=700,fontFamily=C["mono"],
                      color=C["green"] if prob>=0.75 else C["amber"] if prob>=0.5 else C["red"])),
        ], style=dict(marginBottom=12)),
        html.Div([
            html.P([html.Strong("Mean TWR: "),       html.Span(f"{np.mean(results):.2%}",   style=dict(color=C["blue"],  fontFamily=C["mono"]))]),
            html.P([html.Strong("Median TWR: "),     html.Span(f"{np.median(results):.2%}", style=dict(color=C["green"], fontFamily=C["mono"]))]),
            html.P([html.Strong("Std Dev: "),        html.Span(f"{np.std(results):.2%}",    style=dict(color=C["muted"], fontFamily=C["mono"]))]),
            html.P([html.Strong("5th Percentile: "), html.Span(f"{p5:.2%}",                 style=dict(color=C["red"],   fontFamily=C["mono"]))]),
            html.P([html.Strong("95th Percentile: "),html.Span(f"{p95:.2%}",                style=dict(color=C["green"], fontFamily=C["mono"]))]),
        ], style=dict(fontSize=13)),
    ])

    return html.Div([
        html.Div([
            html.Div([dcc.Graph(figure=fig_dist,config={"displayModeBar":False})], style=dict(flex=2)),
            html.Div([stats], style=dict(flex=1, padding="12px")),
        ], style=dict(display="flex",gap=16,alignItems="flex-start")),
        dcc.Graph(figure=fig_sens, config={"displayModeBar":False}),
    ])


# ── Reflect config back to header on load ────────────────────────────────────
@app.callback(
    Output("hdr-fund-size","value",allow_duplicate=True),
    Output("hdr-dry-powder","value",allow_duplicate=True),
    Output("hdr-twr","value",allow_duplicate=True),
    Output("hdr-fee","value",allow_duplicate=True),
    Input("cfg-store","data"),
    prevent_initial_call=True,
)
def reflect_cfg(config):
    return (config.get("fund_size"),
            config.get("dry_powder"),
            round(float(config.get("target_net_twr",0.13))*100,2),
            round(float(config.get("management_fee",0.0125))*100,3))


# ── Auto-persist ─────────────────────────────────────────────────────────────
@app.callback(
    Output("save-status-lbl","children"),
    Input("port-store","data"), Input("pipe-store","data"),
    Input("ph-store","data"), Input("cfg-store","data"),
    Input("next-id","data"),
)
def persist(portfolio, pipeline, placeholders, config, next_id):
    save_data(portfolio, pipeline, placeholders, config, next_id)
    return f"Last saved: {datetime.now().strftime('%H:%M:%S')}"


if __name__ == "__main__":
    print("\n" + "="*70)
    print("HORIZON PORTFOLIO TOOL v75 — PE Secondaries & Co-Investment")
    print("="*70)
    print(f"\n✅  http://localhost:8050")
    print("\nTabs: Portfolio | Pipeline | Pro Forma | Analytics | Segments & TWR |")
    print("      Dry Powder | Pacing | Return Calc | Settings")
    print("\nPress CTRL+C to stop\n")
    app.run(debug=True, host="0.0.0.0", port=8050)
