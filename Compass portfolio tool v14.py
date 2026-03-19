import math
import os
import pickle
import random
import numpy as np
from datetime import datetime

import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx, no_update
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Persistence ──────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credit_portfolio_tool_v13_data.pkl")


def save_data(portfolio, pipeline, placeholders, config, next_id):
    payload = {
        "portfolio": portfolio,
        "pipeline": pipeline,
        "placeholders": placeholders,
        "config": config,
        "next_id": next_id,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(DATA_FILE, "wb") as f:
        pickle.dump(payload, f)


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


# ── Palette ──────────────────────────────────────────────────────────────────
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


def cl(base, opacity):
    r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
    return f"rgba({r},{g},{b},{opacity})"


CHART = dict(
    paper_bgcolor=C["panel"], plot_bgcolor=C["surface"],
    font=dict(family=C["mono"], color=C["text"], size=11),
    margin=dict(l=52, r=20, t=40, b=40),
    xaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    yaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    legend=dict(bgcolor=C["panel"], bordercolor=C["border"], borderwidth=1),
)

# ── Taxonomy ─────────────────────────────────────────────────────────────────
DEAL_TYPES = [
    "GP-Led Multi Asset CV",
    "GP-Led Single Asset CV",
    "LP-Led Secondary",
    "Co-Investment",
]
REGIONS = ["North America", "Europe", "United Kingdom", "Asia", "Global"]
SECTORS = [
    "Diversified", "Consumer", "Healthcare", "Industrial", "Infrastructure",
    "Real Estate", "Specialty Finance", "Technology", "Financials"
]
PRIORITIES = ["High", "Medium", "Low"]
STAGES = ["Screening", "Due Diligence", "Term Sheet", "IC Approved", "Closing"]
SECURITY_TYPES = ["Senior Secured", "Unitranche", "Second Lien", "Subordinated", "Structured", "Preferred"]
RATE_TYPES = ["Floating", "Fixed"]

# ── Seed data ────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "fund_size": 1000,
    "target_net_return": 11.0,
    "fee_drag": 1.5,
    "target_duration": 3.5,
    "recycling_rate": 100,  # 100% principal recycled; interest distributed to investors
    "target_utilisation": 85,
    "deployment_years": 4.0,
    "deals_per_year": 8,
    "max_deal_pct": 8.0,
}

SEED_PORTFOLIO = [
    dict(id=1, name="Aquila Credit Opportunities", manager="Aquila Capital", deal_type="LP-Led Secondary",
         region="Europe", sector="Diversified", commitment=65,
         original_legal_commitment=75, price_to_nav=94.0, current_commitment=65, current_nav=69, pro_forma_nav=None,
         moic=1.42, hold_years=3.0, spread_bps=625, base_rate=4.5, all_in_yield=10.8,
         ltv=48, attachment_point=0, security_type="Senior Secured", rate_type="Floating",
         vintage=2025, deploy_q=1, deployment_rate=100, status="Allocated"),
    dict(id=2, name="Brookfield Credit Continuation", manager="Brookfield", deal_type="GP-Led Multi Asset CV",
         region="North America", sector="Specialty Finance", commitment=90,
         original_legal_commitment=95, price_to_nav=97.0, current_commitment=90, current_nav=93, pro_forma_nav=None,
         moic=1.36, hold_years=2.8, spread_bps=575, base_rate=4.25, all_in_yield=9.9,
         ltv=62, attachment_point=10, security_type="Senior Secured", rate_type="Floating",
         vintage=2025, deploy_q=2, deployment_rate=100, status="Allocated"),
    dict(id=3, name="Mercury Senior Credit", manager="Mercury Partners", deal_type="Co-Investment",
         region="United Kingdom", sector="Industrial", commitment=80,
         original_legal_commitment=80, price_to_nav=100.0, current_commitment=80, current_nav=82, pro_forma_nav=None,
         moic=1.55, hold_years=4.2, spread_bps=720, base_rate=4.5, all_in_yield=12.0,
         ltv=35, attachment_point=22, security_type="Structured", rate_type="Floating",
         vintage=2024, deploy_q=1, deployment_rate=90, status="Allocated"),
    dict(id=4, name="Northlight Capital CV", manager="Northlight", deal_type="GP-Led Single Asset CV", region="Global",
         sector="Financials", commitment=55,
         original_legal_commitment=60, price_to_nav=96.0, current_commitment=55, current_nav=57, pro_forma_nav=None,
         moic=1.48, hold_years=3.6, spread_bps=850, base_rate=4.0, all_in_yield=12.5,
         ltv=25, attachment_point=30, security_type="Senior Secured", rate_type="Floating",
         vintage=2026, deploy_q=3, deployment_rate=100, status="Allocated"),
]

SEED_PIPELINE = [
    dict(id=10, name="Project Cedar", manager="Cedar Ridge", deal_type="GP-Led Multi Asset CV", region="Europe",
         sector="Financials", commitment=45,
         original_legal_commitment=50, price_to_nav=95.0, current_commitment=45, current_nav=47, pro_forma_nav=49,
         moic=1.50, hold_years=3.2, spread_bps=900, base_rate=4.25, all_in_yield=13.3,
         ltv=20, attachment_point=35, security_type="Preferred", rate_type="Floating",
         vintage=2026, deploy_q=3, deployment_rate=100, status="Pipeline", pipeline_stage="IC Approved",
         priority="High"),
    dict(id=11, name="Project Juniper", manager="Juniper Credit", deal_type="LP-Led Secondary", region="North America",
         sector="Healthcare", commitment=70,
         original_legal_commitment=80, price_to_nav=92.0, current_commitment=70, current_nav=74, pro_forma_nav=76,
         moic=1.40, hold_years=3.4, spread_bps=610, base_rate=4.5, all_in_yield=10.6,
         ltv=52, attachment_point=5, security_type="Unitranche", rate_type="Floating",
         vintage=2026, deploy_q=4, deployment_rate=100, status="Pipeline", pipeline_stage="Due Diligence",
         priority="Medium"),
    dict(id=12, name="Project Quartz", manager="Quartz Partners", deal_type="Co-Investment", region="United Kingdom",
         sector="Real Estate", commitment=50,
         original_legal_commitment=55, price_to_nav=98.0, current_commitment=50, current_nav=51, pro_forma_nav=53,
         moic=1.60, hold_years=4.8, spread_bps=760, base_rate=3.8, all_in_yield=11.4,
         ltv=58, attachment_point=18, security_type="Structured", rate_type="Fixed",
         vintage=2027, deploy_q=5, deployment_rate=80, status="Pipeline", pipeline_stage="Term Sheet", priority="High"),
]

SEED_PLACEHOLDERS = [
    dict(id=20, year=2026, quarter="Q4", deal_type="Direct Lending", sector="Diversified", size=75,
         target_yield=10.5, target_duration=3.0, target_ltv=50, notes="Base case private lending allocation"),
    dict(id=21, year=2027, quarter="Q2", deal_type="NAV Lending", sector="Financials", size=60,
         target_yield=12.0, target_duration=3.5, target_ltv=30, notes="Potential GP-led / NAV sleeve"),
    dict(id=22, year=2028, quarter="Q1", deal_type="Credit Secondaries", sector="Diversified", size=90,
         target_yield=13.0, target_duration=4.0, target_ltv=35, notes="Vintage diversification placeholder"),
]


def enrich_deal(d, is_pipeline=False):
    d = dict(d)
    d.setdefault("manager", "")
    d.setdefault("region", "Europe")
    base_commitment = float(d.get("commitment", 0) or 0)
    d.setdefault("original_legal_commitment", base_commitment)
    d.setdefault("price_to_nav", 100.0)
    d.setdefault("current_commitment", base_commitment)
    d.setdefault("current_nav", base_commitment)
    d.setdefault("pro_forma_nav", d.get("current_nav", base_commitment) if is_pipeline else None)
    d["commitment"] = float(d.get("current_commitment", d.get("commitment", 0)) or 0)
    return d


def enrich_placeholder(p):
    p = dict(p)
    p.setdefault("region", "Global")
    p.setdefault("manager", "")
    return p


loaded = load_data()
if loaded:
    INITIAL_PORTFOLIO = [enrich_deal(d, False) for d in loaded.get("portfolio", SEED_PORTFOLIO)]
    INITIAL_PIPELINE = [enrich_deal(d, True) for d in loaded.get("pipeline", SEED_PIPELINE)]
    INITIAL_PLACEHOLDERS = [enrich_placeholder(p) for p in loaded.get("placeholders", SEED_PLACEHOLDERS)]
    INITIAL_CONFIG = loaded.get("config", DEFAULT_CONFIG)
    INITIAL_NEXT_ID = loaded.get("next_id", 50)
    SAVED_AT = loaded.get("saved_at", "Loaded")
else:
    INITIAL_PORTFOLIO = [enrich_deal(d, False) for d in SEED_PORTFOLIO]
    INITIAL_PIPELINE = [enrich_deal(d, True) for d in SEED_PIPELINE]
    INITIAL_PLACEHOLDERS = [enrich_placeholder(p) for p in SEED_PLACEHOLDERS]
    INITIAL_CONFIG = DEFAULT_CONFIG
    INITIAL_NEXT_ID = 50
    SAVED_AT = "Seed data"


# ── Maths ────────────────────────────────────────────────────────────────────
def ann_return_from_moic(moic, hold_y):
    if not hold_y or hold_y <= 0 or not moic or moic <= 0:
        return None
    return (moic ** (1 / hold_y) - 1) * 100


def calc_irr_newton(commitment, moic, hold_y, guess=0.12):
    if hold_y <= 0 or commitment <= 0:
        return None
    cfs = [(-commitment, 0), (commitment * moic, hold_y)]
    r = guess
    for _ in range(200):
        f = sum(cf / (1 + r) ** t for cf, t in cfs)
        df = sum(-t * cf / ((1 + r) ** (t + 1)) for cf, t in cfs)
        if abs(df) < 1e-12:
            break
        nr = r - f / df
        if abs(nr - r) < 1e-9:
            r = nr
            break
        r = max(-0.999, nr)
    return r * 100


def weighted_average(deals, key, weight_key="commitment"):
    total = sum(float(d.get(weight_key, 0) or 0) for d in deals)
    if not total:
        return None
    return sum(float(d.get(key, 0) or 0) * float(d.get(weight_key, 0) or 0) for d in deals) / total


def modified_duration(deal, discount_rate):
    hold = float(deal.get("hold_years", 0) or 0)
    return hold / (1 + discount_rate / 100) if hold > 0 else 0


def maturity_bucket(hold):
    if hold < 2:
        return "0-2 years"
    if hold < 4:
        return "2-4 years"
    if hold < 6:
        return "4-6 years"
    return "6+ years"


def seniority_bucket(security_type):
    if security_type in {"Senior Secured", "Unitranche"}:
        return "Senior / Unitranche"
    if security_type in {"Second Lien", "Subordinated", "Preferred"}:
        return "Junior / Pref"
    return "Structured"


def required_moic_for_target(hold_y, gross_return):
    return (1 + gross_return / 100) ** hold_y


def discount_purchase_price(nav_value, price_to_nav):
    nav_value = float(nav_value or 0)
    price_to_nav = float(price_to_nav or 0)
    return nav_value * price_to_nav / 100 if nav_value > 0 and price_to_nav > 0 else 0


def discount_implied_moic(base_nav, entry_price_to_nav, hold_y, nav_growth=0, exit_price_to_nav=100):
    if hold_y <= 0:
        return None
    purchase_price = discount_purchase_price(base_nav, entry_price_to_nav)
    if purchase_price <= 0:
        return None
    exit_nav = float(base_nav or 0) * ((1 + float(nav_growth or 0) / 100) ** hold_y)
    exit_value = exit_nav * float(exit_price_to_nav or 0) / 100
    return exit_value / purchase_price if purchase_price else None


def discount_implied_irr(base_nav, entry_price_to_nav, hold_y, nav_growth=0, exit_price_to_nav=100):
    moic = discount_implied_moic(base_nav, entry_price_to_nav, hold_y, nav_growth, exit_price_to_nav)
    if moic is None or moic <= 0 or hold_y <= 0:
        return None
    return (moic ** (1 / hold_y) - 1) * 100


def aggregate_metrics(portfolio, pipeline, config):
    fund_size = float(config.get("fund_size", 0) or 0)
    target = float(config.get("target_net_return", 0) or 0)
    fee_drag = float(config.get("fee_drag", 0) or 0)

    deployed = sum(float(d.get("commitment", 0) or 0) for d in portfolio)
    pipeline_amt = sum(float(d.get("commitment", 0) or 0) for d in pipeline)
    util = deployed / fund_size * 100 if fund_size else 0

    portfolio_return = weighted_average(
        [dict(d, ann_return=ann_return_from_moic(d.get("moic"), d.get("hold_years"))) for d in portfolio],
        "ann_return"
    )
    wal = weighted_average(portfolio, "hold_years")
    duration = None
    if portfolio:
        total = sum(d["commitment"] for d in portfolio)
        duration = sum(modified_duration(d, target) * d["commitment"] for d in portfolio) / total

    return {
        "deployed": deployed,
        "pipeline_amt": pipeline_amt,
        "util": util,
        "portfolio_return": portfolio_return,
        "wal": wal,
        "duration": duration,
        "wa_spread": weighted_average(portfolio, "spread_bps"),
        "wa_yield": weighted_average(portfolio, "all_in_yield"),
        "wa_ltv": weighted_average(portfolio, "ltv"),
        "blended_price_to_nav": weighted_average(portfolio, "price_to_nav", "current_nav"),
        "pipeline_blended_price_to_nav": weighted_average(pipeline, "price_to_nav", "current_nav"),
        "pipeline_current_nav": sum(float(d.get("current_nav", d.get("commitment", 0)) or 0) for d in pipeline),
        "pipeline_pro_forma_nav": sum(
            float(d.get("pro_forma_nav", d.get("current_nav", d.get("commitment", 0))) or 0) for d in pipeline),
        "gross_target": target + fee_drag,
    }


def build_pacing_df(portfolio, pipeline, placeholders, config, quarters=20):
    fund_size = float(config.get("fund_size", 0) or 0)
    target_util = float(config.get("target_utilisation", 85) or 85) / 100
    recycling = float(config.get("recycling_rate", 100) or 100) / 100  # default 100%
    base_hold = weighted_average(portfolio + pipeline, "hold_years") or float(config.get("target_duration", 3.5) or 3.5)
    deals_per_year = max(float(config.get("deals_per_year", 8) or 8), 1)
    wa_yield = weighted_average(portfolio + pipeline, "all_in_yield") or float(
        config.get("target_net_return", 11) or 11)

    placeholder_map = {}
    for p in placeholders:
        key = int((float(p.get("year", datetime.now().year)) - datetime.now().year) * 4)
        q_lookup = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get(p.get("quarter", "Q1"), 1)
        idx = max(1, key + q_lookup)
        placeholder_map[idx] = placeholder_map.get(idx, 0) + float(p.get("size", 0) or 0)

    nav = sum(float(d.get("commitment", 0) or 0) for d in portfolio)
    rows = []
    q_hold = max(int(round(base_hold * 4)), 1)
    cumulative = nav

    for q in range(1, quarters + 1):
        label = f"Q{((q - 1) % 4) + 1} Y{datetime.now().year + ((q - 1) // 4)}"
        capacity = max(fund_size * target_util - nav, 0)
        base_deploy = min(capacity, fund_size / max(float(config.get("deployment_years", 4) or 4) * 4, 1))

        # Full principal recycling: repayments go back into redeployment
        repayments = nav / q_hold if q > 4 else 0
        recycled = repayments * recycling  # with 100% recycling, all principal redeploys

        # Interest income distributed to investors (not recycled)
        quarterly_interest = nav * (wa_yield / 100) / 4

        future_alloc = placeholder_map.get(q, 0)
        target_deploy = min(capacity, base_deploy + future_alloc + recycled)
        nav = max(0, nav + target_deploy - repayments)
        cumulative += target_deploy
        rows.append({
            "Quarter": label,
            "New Deployment": round(base_deploy + future_alloc, 2),
            "Principal Recycled": round(recycled, 2),
            "Total Deployment": round(target_deploy, 2),
            "Repayments": round(repayments, 2),
            "Interest Distributed": round(quarterly_interest, 2),
            "NAV": round(nav, 2),
            "Dry Powder": round(max(fund_size - nav, 0), 2),
            "Utilisation": round(nav / fund_size * 100 if fund_size else 0, 1),
            "Deals Needed": round(deals_per_year / 4, 1),
            "Cumulative Deployment": round(cumulative, 2),
        })
    return pd.DataFrame(rows)


# ── Style helpers ────────────────────────────────────────────────────────────
INP = dict(background=C["surface"], border=f"1px solid {C['border2']}",
           color=C["text"], borderRadius=6, padding="6px 10px",
           fontFamily=C["mono"], fontSize=12, outline="none", width="100%")

BTN = lambda bg, fg="#fff": dict(
    background=bg, border="none", color=fg, borderRadius=6,
    padding="7px 16px", cursor="pointer", fontWeight=600,
    fontSize=12, fontFamily=C["sans"], letterSpacing=0.5)

TBL_CELL = dict(backgroundColor=C["panel"], color=C["text"],
                fontFamily=C["mono"], fontSize=11, padding="8px 12px",
                border=f"1px solid {C['border']}", textAlign="left")
TBL_HEAD = dict(backgroundColor=C["bg"], color=C["muted"], fontWeight=700,
                fontSize=10, letterSpacing=1.5, textTransform="uppercase",
                border=f"1px solid {C['border']}", padding="9px 12px")
TBL_ODD = [{"if": {"row_index": "odd"}, "backgroundColor": C["surface"]}]


def card(children, style_extra=None):
    base = dict(background=C["panel"], border=f"1px solid {C['border']}", borderRadius=10, padding=18)
    if style_extra:
        base.update(style_extra)
    return html.Div(children, style=base)


def kpi(label, value, sub="", color=None, width=150):
    color = color or C["sky"]
    return html.Div([
        html.Div(label,
                 style=dict(fontSize=9, letterSpacing=2, color=C["muted"], textTransform="uppercase", marginBottom=5,
                            fontFamily=C["sans"])),
        html.Div(value, style=dict(fontSize=22, fontWeight=700, color=color, fontFamily=C["mono"])),
        html.Div(sub, style=dict(fontSize=10, color=C["dim"], marginTop=3, fontFamily=C["sans"])),
    ], style=dict(background=C["surface"], border=f"1px solid {C['border']}", borderRadius=8, padding="14px 18px",
                  minWidth=width))


def section_lbl(text):
    return html.Div(text, style=dict(fontSize=9, letterSpacing=2.5, color=C["muted"], textTransform="uppercase",
                                     marginBottom=10, fontFamily=C["sans"]))


def _field(label, component):
    return html.Div([
        html.Label(label, style=dict(fontSize=9, color=C["muted"], display="block", marginBottom=4, letterSpacing=1,
                                     textTransform="uppercase")),
        component,
    ])


def _dd():
    return dict(backgroundColor=C["surface"], color=C["text"], border=f"1px solid {C['border2']}", borderRadius=6,
                fontFamily=C["mono"], fontSize=12)


def fmt_money(x):
    return f"${x:,.1f}M"


# ── App ──────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="Credit Portfolio Tool v13", suppress_callback_exceptions=True)

app.layout = html.Div([
    dcc.Store(id="portfolio-store", data=INITIAL_PORTFOLIO),
    dcc.Store(id="pipeline-store", data=INITIAL_PIPELINE),
    dcc.Store(id="placeholder-store", data=INITIAL_PLACEHOLDERS),
    dcc.Store(id="config-store", data=INITIAL_CONFIG),
    dcc.Store(id="next-id", data=INITIAL_NEXT_ID),

    html.Div([
        html.Div([
            html.Div([
                html.Span("CREDIT PORTFOLIO",
                          style=dict(fontSize=18, fontWeight=700, color=C["text"], fontFamily=C["sans"],
                                     letterSpacing=1)),
                html.Span(" · ", style=dict(color=C["dim"], margin="0 6px")),
                html.Span("Institutional Dashboard v13",
                          style=dict(fontSize=18, fontWeight=300, color=C["muted"], fontFamily=C["sans"])),
            ]),
            html.Div(f"Persistent data: {SAVED_AT}",
                     style=dict(color=C["dim"], marginTop=8, fontSize=11, fontFamily=C["mono"])),
        ]),
        html.Div([
            html.Div([
                html.Label("Fund Size ($M)",
                           style=dict(fontSize=9, color=C["muted"], letterSpacing=2, display="block", marginBottom=4,
                                      textTransform="uppercase")),
                dcc.Input(id="fund-size", type="number", value=INITIAL_CONFIG["fund_size"],
                          style={**INP, "width": 100}),
            ]),
            html.Div([
                html.Label("Target Net Return (%)",
                           style=dict(fontSize=9, color=C["muted"], letterSpacing=2, display="block", marginBottom=4,
                                      textTransform="uppercase")),
                dcc.Input(id="target-return", type="number", value=INITIAL_CONFIG["target_net_return"], step=0.25,
                          style={**INP, "width": 100}),
            ]),
            html.Div([
                html.Label("Fee Drag (%)",
                           style=dict(fontSize=9, color=C["muted"], letterSpacing=2, display="block", marginBottom=4,
                                      textTransform="uppercase")),
                dcc.Input(id="fee-drag", type="number", value=INITIAL_CONFIG["fee_drag"], step=0.1,
                          style={**INP, "width": 100}),
            ]),
            html.Div([
                html.Label("Target Duration (y)",
                           style=dict(fontSize=9, color=C["muted"], letterSpacing=2, display="block", marginBottom=4,
                                      textTransform="uppercase")),
                dcc.Input(id="target-duration", type="number", value=INITIAL_CONFIG["target_duration"], step=0.25,
                          style={**INP, "width": 100}),
            ]),
            html.Div([
                html.Label("Recycling Rate (%)",
                           style=dict(fontSize=9, color=C["muted"], letterSpacing=2, display="block", marginBottom=4,
                                      textTransform="uppercase")),
                dcc.Input(id="recycling-rate", type="number", value=INITIAL_CONFIG["recycling_rate"], step=5,
                          style={**INP, "width": 100}),
            ]),
        ], style=dict(display="flex", gap=12, alignItems="flex-end", flexWrap="wrap")),
    ], style=dict(background="#070c13", borderBottom=f"1px solid {C['border']}", padding="22px 36px", display="flex",
                  justifyContent="space-between", alignItems="center", flexWrap="wrap", gap=16)),

    html.Div(id="kpi-strip", style=dict(padding="16px 36px", display="flex", gap=10, flexWrap="wrap")),

    html.Div([
        dcc.Tabs(id="tabs", value="portfolio", children=[
            dcc.Tab(label="📂 Portfolio", value="portfolio"),
            dcc.Tab(label="🔭 Pipeline", value="pipeline"),
            dcc.Tab(label="🧩 Future Allocations", value="placeholders"),
            dcc.Tab(label="📊 Credit Analytics", value="analytics"),
            dcc.Tab(label="♻️ Pacing Model", value="pacing"),
            dcc.Tab(label="🧮 Return Calculator", value="returns"),
            dcc.Tab(label="🎲 TWR Monte Carlo", value="twr_mc"),
            dcc.Tab(label="⚙️ Settings", value="settings"),
        ], colors=dict(border=C["border"], primary=C["blue"], background=C["bg"]), style=dict(fontFamily=C["sans"]))
    ], style=dict(padding="0 36px", borderBottom=f"1px solid {C['border']}")),

    html.Div(id="tab-content", style=dict(padding="24px 36px 60px")),
], style=dict(background=C["bg"], minHeight="100vh", fontFamily=C["sans"], color=C["text"]))


# ── Data/config callbacks ────────────────────────────────────────────────────
@app.callback(
    Output("config-store", "data"),
    Input("fund-size", "value"), Input("target-return", "value"), Input("fee-drag", "value"),
    Input("target-duration", "value"), Input("recycling-rate", "value"),
    State("config-store", "data"),
)
def sync_config(fund_size, target_return, fee_drag, target_duration, recycling_rate, config):
    cfg = dict(config or DEFAULT_CONFIG)
    cfg.update({
        "fund_size": float(fund_size or cfg.get("fund_size", 1000)),
        "target_net_return": float(target_return or cfg.get("target_net_return", 11)),
        "fee_drag": float(fee_drag or cfg.get("fee_drag", 1.5)),
        "target_duration": float(target_duration or cfg.get("target_duration", 3.5)),
        "recycling_rate": float(recycling_rate or cfg.get("recycling_rate", 70)),
    })
    return cfg


@app.callback(
    Output("kpi-strip", "children"),
    Input("portfolio-store", "data"), Input("pipeline-store", "data"), Input("config-store", "data")
)
def update_kpis(portfolio, pipeline, config):
    m = aggregate_metrics(portfolio, pipeline, config)
    fund_size = float(config.get("fund_size", 0) or 0)
    float_pct = 0
    senior_pct = 0
    if portfolio:
        total = sum(d["commitment"] for d in portfolio)
        float_pct = sum(d["commitment"] for d in portfolio if d.get("rate_type") == "Floating") / total * 100
        senior_pct = sum(d["commitment"] for d in portfolio if
                         seniority_bucket(d.get("security_type")) == "Senior / Unitranche") / total * 100
    return [
        kpi("Portfolio Return", f"{m['portfolio_return']:.1f}%" if m["portfolio_return"] is not None else "—",
            f"Target {config.get('target_net_return', 0):.1f}%",
            C["green"] if (m["portfolio_return"] or 0) >= config.get("target_net_return", 0) else C["amber"]),
        kpi("Deployed NAV", fmt_money(m["deployed"]), f"{m['util']:.1f}% of {fmt_money(fund_size)}", C["sky"]),
        kpi("Pipeline", fmt_money(m["pipeline_amt"]), f"{len(pipeline)} deals pending", C["purple"]),
        kpi("Wtd Avg Duration", f"{m['duration']:.2f}y" if m["duration"] is not None else "—",
            f"WAL {m['wal']:.2f}y" if m["wal"] is not None else "", C["teal"]),
        kpi("Wtd Avg Spread", f"{m['wa_spread']:.0f} bps" if m["wa_spread"] is not None else "—", "Portfolio weighted",
            C["amber"]),
        kpi("Wtd Avg LTV", f"{m['wa_ltv']:.1f}%" if m["wa_ltv"] is not None else "—",
            f"Yield {m['wa_yield']:.1f}%" if m["wa_yield"] is not None else "", C["pink"]),
        kpi("Floating Rate", f"{float_pct:.0f}%", "Exposure", C["blue"]),
        kpi("Senior / Unitranche", f"{senior_pct:.0f}%", "Exposure", C["green"]),
    ]


# ── Tab router ───────────────────────────────────────────────────────────────
@app.callback(
    Output("tab-content", "children"),
    Input("tabs", "value"),
    Input("portfolio-store", "data"), Input("pipeline-store", "data"),
    Input("placeholder-store", "data"), Input("config-store", "data")
)
def route_tab(tab, portfolio, pipeline, placeholders, config):
    if tab == "portfolio":
        return tab_portfolio(portfolio, config)
    if tab == "pipeline":
        return tab_pipeline(pipeline, portfolio, config)
    if tab == "placeholders":
        return tab_placeholders(placeholders)
    if tab == "analytics":
        return tab_analytics(portfolio, pipeline, config)
    if tab == "pacing":
        return tab_pacing(portfolio, pipeline, placeholders, config)
    if tab == "returns":
        return tab_returns(portfolio, pipeline, config)
    if tab == "twr_mc":
        return tab_twr_montecarlo(portfolio, pipeline, config)
    if tab == "settings":
        return tab_settings(config)
    return html.Div()


# ── Tab builders ─────────────────────────────────────────────────────────────
def portfolio_table_rows(portfolio, config):
    target = float(config.get("target_net_return", 0) or 0)
    rows = []
    total = sum(d["commitment"] for d in portfolio) or 1
    for d in portfolio:
        irr = calc_irr_newton(d["commitment"], d["moic"], d["hold_years"])
        ann = ann_return_from_moic(d["moic"], d["hold_years"])
        rows.append({
            "ID": d["id"], "Deal": d["name"], "Manager": d.get("manager", ""), "Type": d["deal_type"],
            "Region": d.get("region", ""), "Sector": d["sector"],
            "Current Commit": fmt_money(d.get("current_commitment", d["commitment"])),
            "Current NAV": fmt_money(d.get("current_nav", d["commitment"])),
            "Orig Legal Commit": fmt_money(d.get("original_legal_commitment", d["commitment"])),
            "Price/NAV": f"{float(d.get('price_to_nav', 100) or 0):.1f}%",
            "Weight": f"{d['commitment'] / total * 100:.1f}%", "Yield": f"{d['all_in_yield']:.1f}%",
            "Spread": f"{d['spread_bps']:.0f}",
            "Duration": f"{modified_duration(d, target):.2f}y", "Hold": f"{d['hold_years']:.1f}y",
            "LTV": f"{d['ltv']:.0f}%", "IRR": f"{irr:.1f}%" if irr is not None else "—",
            "MOIC": f"{d['moic']:.2f}x", "Rate": d["rate_type"], "Security": d["security_type"],
            "Vintage": d["vintage"],
        })
    return rows


def tab_portfolio(portfolio, config):
    rows = portfolio_table_rows(portfolio, config)
    type_vals = pd.DataFrame(portfolio).groupby("deal_type")["commitment"].sum().sort_values(
        ascending=False) if portfolio else pd.Series(dtype=float)
    bucket = {}
    for d in portfolio:
        bucket[maturity_bucket(d["hold_years"])] = bucket.get(maturity_bucket(d["hold_years"]), 0) + d["commitment"]

    fig = make_subplots(1, 2, specs=[[{"type": "domain"}, {"type": "xy"}]],
                        subplot_titles=["Exposure by Deal Type", "Duration Bucket"])
    fig.add_trace(go.Pie(labels=list(type_vals.index), values=list(type_vals.values), hole=0.58,
                         marker_colors=[C["blue"], C["purple"], C["teal"], C["amber"], C["pink"], C["green"], C["sky"]],
                         textfont_color=C["text"]), 1, 1)
    fig.add_trace(go.Bar(x=list(bucket.keys()), y=list(bucket.values()), marker_color=C["blue"],
                         text=[fmt_money(v) for v in bucket.values()], textposition="outside",
                         textfont_color=C["text"]), 1, 2)
    fig.update_layout(**CHART, height=320)

    form = html.Div([
        section_lbl("Add Portfolio Deal"),
        html.Div([
            _field("Deal Name", dcc.Input(id="port-name", type="text", style=INP)),
            _field("Manager", dcc.Input(id="port-manager", type="text", style=INP)),
            _field("Deal Type", dcc.Dropdown(id="port-type", options=DEAL_TYPES, value=DEAL_TYPES[0], style=_dd())),
            _field("Region", dcc.Dropdown(id="port-region", options=REGIONS, value=REGIONS[0], style=_dd())),
            _field("Sector", dcc.Dropdown(id="port-sector", options=SECTORS, value=SECTORS[0], style=_dd())),
            _field("Orig Legal Commit", dcc.Input(id="port-orig-commit", type="number", value=40, style=INP)),
            _field("Current Commit", dcc.Input(id="port-commit", type="number", value=40, style=INP)),
            _field("MOIC", dcc.Input(id="port-moic", type="number", value=1.4, step=0.01, style=INP)),
            _field("Hold (y)", dcc.Input(id="port-hold", type="number", value=3.0, step=0.1, style=INP)),
            _field("Yield %", dcc.Input(id="port-yield", type="number", value=10.5, step=0.1, style=INP)),
            _field("Spread bps", dcc.Input(id="port-spread", type="number", value=600, step=5, style=INP)),
            _field("LTV %", dcc.Input(id="port-ltv", type="number", value=50, step=1, style=INP)),
            _field("Price to NAV %", dcc.Input(id="port-price-to-nav", type="number", value=100, step=0.5, style=INP)),
            _field("Current NAV", dcc.Input(id="port-current-nav", type="number", value=40, step=0.1, style=INP)),
            _field("Security",
                   dcc.Dropdown(id="port-security", options=SECURITY_TYPES, value=SECURITY_TYPES[0], style=_dd())),
            _field("Rate", dcc.Dropdown(id="port-rate", options=RATE_TYPES, value="Floating", style=_dd())),
            html.Div([html.Label(" "),
                      html.Button("+ Add Deal", id="add-portfolio-btn", style={**BTN(C["blue"]), "width": "100%"})]),
        ], style=dict(display="grid",
                      gridTemplateColumns="1.6fr 1.3fr 1.2fr 1.2fr .9fr .9fr .7fr .7fr .8fr .8fr .8fr .9fr 1fr .8fr auto",
                      gap=8, alignItems="end")),
        html.Div(id="portfolio-msg", style=dict(marginTop=8, color=C["green"], fontSize=11))
    ], style=dict(background=C["surface"], border=f"1px solid {cl(C['blue'], 0.4)}", borderRadius=8, padding=18,
                  marginBottom=18))

    table = dash_table.DataTable(
        id="portfolio-table",
        data=rows,
        columns=[{"name": c, "id": c} for c in rows[0].keys()] if rows else [],
        row_selectable="single",
        selected_rows=[],
        style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD, sort_action="native",
        page_size=12, style_table={"overflowX": "auto"}
    )

    actions = card([
        section_lbl("Portfolio Actions"),
        html.Button("Delete Selected", id="delete-portfolio-btn", style=BTN(C["red"])),
        html.Div(id="portfolio-action-msg", style=dict(marginTop=10, color=C["muted"], fontSize=11))
    ], dict(width=220))

    return html.Div([
        form,
        html.Div([
            html.Div(table, style=dict(flex=3)),
            html.Div([dcc.Graph(figure=fig, config={"displayModeBar": False}), actions],
                     style=dict(flex=2, display="flex", flexDirection="column", gap=16, minWidth=320)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


def tab_pipeline(pipeline, portfolio, config):
    rows = []
    for d in pipeline:
        ann = ann_return_from_moic(d["moic"], d["hold_years"])
        rows.append({
            "ID": d["id"], "Deal": d["name"], "Manager": d.get("manager", ""), "Type": d["deal_type"],
            "Region": d.get("region", ""),
            "Stage": d.get("pipeline_stage", "Screening"), "Priority": d.get("priority", "Medium"),
            "Orig Legal Commit": fmt_money(d.get("original_legal_commitment", d["commitment"])),
            "Current Commit": fmt_money(d.get("current_commitment", d["commitment"])),
            "Current NAV": fmt_money(d.get("current_nav", d["commitment"])),
            "Price/NAV": f"{float(d.get('price_to_nav', 100) or 0):.1f}%",
            "Pro Forma NAV": fmt_money(d.get("pro_forma_nav", d.get("current_nav", d["commitment"]))),
            "Yield": f"{d['all_in_yield']:.1f}%", "Spread": f"{d['spread_bps']:.0f}",
            "Duration": f"{modified_duration(d, config.get('target_net_return', 11)):.2f}y",
            "LTV": f"{d['ltv']:.0f}%", "Exp Return": f"{ann:.1f}%" if ann is not None else "—", "Vintage": d["vintage"]
        })

    stage_caps = {s: sum(d["commitment"] for d in pipeline if d.get("pipeline_stage") == s) for s in STAGES}
    fig = go.Figure(go.Funnel(y=STAGES, x=[stage_caps.get(s, 0) for s in STAGES], textinfo="value+percent initial",
                              marker_color=[C["blue"], C["teal"], C["amber"], C["purple"], C["green"]],
                              textfont=dict(color=C["text"])))
    fig.update_layout(**CHART, height=320, title="Pipeline Funnel by Committed ($M)")

    form = html.Div([
        section_lbl("Add Pipeline Deal"),
        html.Div([
            _field("Deal Name", dcc.Input(id="pipe-name", type="text", style=INP)),
            _field("Manager", dcc.Input(id="pipe-manager", type="text", style=INP)),
            _field("Deal Type", dcc.Dropdown(id="pipe-type", options=DEAL_TYPES, value=DEAL_TYPES[0], style=_dd())),
            _field("Region", dcc.Dropdown(id="pipe-region", options=REGIONS, value=REGIONS[0], style=_dd())),
            _field("Sector", dcc.Dropdown(id="pipe-sector", options=SECTORS, value=SECTORS[0], style=_dd())),
            _field("Stage", dcc.Dropdown(id="pipe-stage", options=STAGES, value=STAGES[0], style=_dd())),
            _field("Priority", dcc.Dropdown(id="pipe-priority", options=PRIORITIES, value="Medium", style=_dd())),
            _field("Orig Legal Commit", dcc.Input(id="pipe-orig-commit", type="number", value=40, style=INP)),
            _field("Current Commit", dcc.Input(id="pipe-commit", type="number", value=40, style=INP)),
            _field("MOIC", dcc.Input(id="pipe-moic", type="number", value=1.45, step=0.01, style=INP)),
            _field("Hold", dcc.Input(id="pipe-hold", type="number", value=3.5, step=0.1, style=INP)),
            _field("Yield %", dcc.Input(id="pipe-yield", type="number", value=11.5, step=0.1, style=INP)),
            _field("Spread", dcc.Input(id="pipe-spread", type="number", value=700, step=5, style=INP)),
            _field("LTV", dcc.Input(id="pipe-ltv", type="number", value=45, step=1, style=INP)),
            _field("Price to NAV %", dcc.Input(id="pipe-price-to-nav", type="number", value=100, step=0.5, style=INP)),
            _field("Current NAV", dcc.Input(id="pipe-current-nav", type="number", value=40, step=0.1, style=INP)),
            _field("Pro Forma NAV", dcc.Input(id="pipe-pro-forma-nav", type="number", value=42, step=0.1, style=INP)),
            html.Div([html.Label(" "),
                      html.Button("+ Add", id="add-pipeline-btn", style={**BTN(C["purple"]), "width": "100%"})]),
        ], style=dict(display="grid",
                      gridTemplateColumns="1.5fr 1.2fr 1.1fr 1.1fr .9fr .8fr .9fr .9fr .7fr .7fr .7fr .7fr .7fr .8fr .8fr .8fr auto",
                      gap=8, alignItems="end")),
        html.Div(id="pipeline-msg", style=dict(marginTop=8, color=C["green"], fontSize=11))
    ], style=dict(background=C["surface"], border=f"1px solid {cl(C['purple'], 0.4)}", borderRadius=8, padding=18,
                  marginBottom=18))

    table = dash_table.DataTable(
        id="pipeline-table", data=rows, columns=[{"name": c, "id": c} for c in rows[0].keys()] if rows else [],
        row_selectable="single", selected_rows=[], style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD + [
            {"if": {"filter_query": '{Priority} = "High"', "column_id": "Priority"}, "color": C["red"],
             "fontWeight": 700},
            {"if": {"filter_query": '{Priority} = "Medium"', "column_id": "Priority"}, "color": C["amber"]},
            {"if": {"filter_query": '{Priority} = "Low"', "column_id": "Priority"}, "color": C["green"]},
        ],
        sort_action="native", page_size=10, style_table={"overflowX": "auto"}
    )

    actions = card([
        section_lbl("Pipeline Actions"),
        html.Button("Promote Selected to Portfolio", id="promote-pipeline-btn",
                    style={**BTN(C["green"]), "width": "100%"}),
        html.Div(style=dict(height=10)),
        html.Button("Delete Selected", id="delete-pipeline-btn", style={**BTN(C["red"]), "width": "100%"}),
        html.Div(id="pipeline-action-msg", style=dict(marginTop=10, color=C["muted"], fontSize=11)),
    ], dict(width=260))

    return html.Div([
        form,
        html.Div([
            html.Div(table, style=dict(flex=3)),
            html.Div([dcc.Graph(figure=fig, config={"displayModeBar": False}), actions],
                     style=dict(flex=2, display="flex", flexDirection="column", gap=16, minWidth=320)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap"))
    ])


def tab_placeholders(placeholders):
    rows = [{"ID": p["id"], "Year": p["year"], "Quarter": p["quarter"], "Deal Type": p["deal_type"],
             "$M": fmt_money(p["size"]), "Target Yield": f"{p['target_yield']:.1f}%",
             "Target Duration": f"{p['target_duration']:.1f}y", "Target LTV": f"{p['target_ltv']:.0f}%",
             "Notes": p.get("notes", "")} for p in placeholders]

    future = pd.DataFrame(placeholders)
    fig = go.Figure(go.Bar(x=[f"{r['quarter']} {r['year']}" for _, r in future.iterrows()], y=future["size"],
                           marker_color=C["teal"], text=[fmt_money(v) for v in future["size"]], textposition="outside",
                           textfont_color=C["text"])) if not future.empty else go.Figure()
    fig.update_layout(**CHART, height=320, title="Future Credit Allocation Plan")

    form = html.Div([
        section_lbl("Add Placeholder / Future Allocation"),
        html.Div([
            _field("Year", dcc.Input(id="ph-year", type="number", value=datetime.now().year, style=INP)),
            _field("Quarter", dcc.Dropdown(id="ph-quarter", options=["Q1", "Q2", "Q3", "Q4"], value="Q1", style=_dd())),
            _field("Deal Type", dcc.Dropdown(id="ph-type", options=DEAL_TYPES, value=DEAL_TYPES[0], style=_dd())),
            _field("Sector", dcc.Dropdown(id="ph-sector", options=SECTORS, value=SECTORS[0], style=_dd())),
            _field("$M", dcc.Input(id="ph-size", type="number", value=50, style=INP)),
            _field("Target Yield %", dcc.Input(id="ph-yield", type="number", value=11.0, step=0.1, style=INP)),
            _field("Target Duration", dcc.Input(id="ph-duration", type="number", value=3.0, step=0.1, style=INP)),
            _field("Target LTV", dcc.Input(id="ph-ltv", type="number", value=45, step=1, style=INP)),
            _field("Notes", dcc.Input(id="ph-notes", type="text", value="", style=INP)),
            html.Div([html.Label(" "),
                      html.Button("+ Add", id="add-placeholder-btn", style={**BTN(C["teal"]), "width": "100%"})]),
        ], style=dict(display="grid", gridTemplateColumns=".7fr .8fr 1.2fr 1fr .8fr .8fr .8fr .8fr 2fr auto", gap=8,
                      alignItems="end")),
        html.Div(id="placeholder-msg", style=dict(marginTop=8, color=C["green"], fontSize=11))
    ], style=dict(background=C["surface"], border=f"1px solid {cl(C['teal'], 0.4)}", borderRadius=8, padding=18,
                  marginBottom=18))

    table = dash_table.DataTable(id="placeholder-table", data=rows,
                                 columns=[{"name": c, "id": c} for c in rows[0].keys()] if rows else [],
                                 row_selectable="single", selected_rows=[], style_cell=TBL_CELL, style_header=TBL_HEAD,
                                 style_data_conditional=TBL_ODD, page_size=10, style_table={"overflowX": "auto"})

    actions = card([
        section_lbl("Future Allocation Actions"),
        html.Button("Delete Selected", id="delete-placeholder-btn", style={**BTN(C["red"]), "width": "100%"}),
        html.Div(id="placeholder-action-msg", style=dict(marginTop=10, color=C["muted"], fontSize=11)),
    ], dict(width=220))

    return html.Div([
        form,
        html.Div([
            html.Div(table, style=dict(flex=3)),
            html.Div([dcc.Graph(figure=fig, config={"displayModeBar": False}), actions],
                     style=dict(flex=2, display="flex", flexDirection="column", gap=16, minWidth=320)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap"))
    ])


def tab_analytics(portfolio, pipeline, config):
    deals = [dict(d, pool="Portfolio") for d in portfolio] + [dict(d, pool="Pipeline") for d in pipeline]
    if not deals:
        return card("No data.")
    target = float(config.get("target_net_return", 11) or 11)

    vintage = {}
    maturity = {}
    for d in deals:
        vintage[d["vintage"]] = vintage.get(d["vintage"], 0) + d["commitment"]
        maturity[maturity_bucket(d["hold_years"])] = maturity.get(maturity_bucket(d["hold_years"]), 0) + d["commitment"]

    fig_vintage = go.Figure(
        go.Bar(x=[str(k) for k in vintage.keys()], y=list(vintage.values()), marker_color=C["purple"],
               text=[fmt_money(v) for v in vintage.values()], textposition="outside", textfont_color=C["text"]))
    fig_vintage.update_layout(**CHART, height=320, title="Vintage Exposure")

    fig_scatter = go.Figure()
    for pool, color in [("Portfolio", C["blue"]), ("Pipeline", C["purple"])]:
        ds = [d for d in deals if d["pool"] == pool]
        fig_scatter.add_trace(go.Scatter(
            x=[modified_duration(d, target) for d in ds],
            y=[ann_return_from_moic(d["moic"], d["hold_years"]) or 0 for d in ds],
            mode="markers+text", name=pool,
            marker=dict(color=color, size=[d["commitment"] * 0.6 for d in ds], opacity=0.8,
                        line=dict(color=C["border"], width=1)),
            text=[d["name"].split()[-1] for d in ds], textposition="top center", textfont=dict(color=C["text"], size=9),
            hovertext=[f"{d['name']}<br>Yield {d['all_in_yield']:.1f}%<br>LTV {d['ltv']:.0f}%" for d in ds],
            hoverinfo="text"
        ))
    fig_scatter.add_hline(y=target, line_color=C["amber"], line_dash="dash")
    fig_scatter.update_layout(**CHART, height=360, title="IRR / Annual Return vs Duration",
                              xaxis_title="Modified Duration (y)", yaxis_title="Annual Return (%)")

    wall = pd.DataFrame([{"Deal": d["name"], "Pool": d["pool"], "Maturity Bucket": maturity_bucket(d["hold_years"]),
                          "Refi Year": int(datetime.now().year + math.ceil(d["hold_years"])), "$M": d["commitment"],
                          "Yield": d["all_in_yield"], "LTV": d["ltv"]} for d in deals])
    wall_rows = wall.to_dict("records")
    wall_table = dash_table.DataTable(data=wall_rows, columns=[{"name": c, "id": c} for c in wall.columns],
                                      style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                      page_size=10, style_table={"overflowX": "auto"})

    fig_maturity = go.Figure(go.Bar(x=list(maturity.keys()), y=list(maturity.values()), marker_color=C["teal"],
                                    text=[fmt_money(v) for v in maturity.values()], textposition="outside",
                                    textfont_color=C["text"]))
    fig_maturity.update_layout(**CHART, height=320, title="Refinancing Wall / Maturity Ladder")

    df = pd.DataFrame(deals)
    manager_exp = df.groupby("manager", as_index=False)["commitment"].sum().sort_values("commitment",
                                                                                        ascending=False).head(10)
    fig_manager = go.Figure(go.Bar(x=manager_exp["manager"], y=manager_exp["commitment"], marker_color=C["blue"],
                                   text=[fmt_money(v) for v in manager_exp["commitment"]], textposition="outside",
                                   textfont_color=C["text"]))
    fig_manager.update_layout(**CHART, height=320, title="Exposure by Manager", xaxis_title="Manager", yaxis_title="$M")

    region_exp = df.groupby("region", as_index=False)["commitment"].sum().sort_values("commitment", ascending=False)
    fig_region = go.Figure(go.Pie(labels=region_exp["region"], values=region_exp["commitment"], hole=0.55,
                                  marker_colors=[C["purple"], C["teal"], C["sky"], C["amber"], C["pink"]],
                                  textfont_color=C["text"]))
    fig_region.update_layout(**CHART, height=320, title="Exposure by Region")

    discount_by_type = df.groupby("deal_type").apply(
        lambda x: (x["price_to_nav"] * x["current_nav"]).sum() / max(x["current_nav"].sum(), 1)).reset_index(
        name="blended_price_to_nav")
    fig_discount = go.Figure(
        go.Bar(x=discount_by_type["deal_type"], y=discount_by_type["blended_price_to_nav"], marker_color=C["amber"],
               text=[f"{v:.1f}%" for v in discount_by_type["blended_price_to_nav"]], textposition="outside",
               textfont_color=C["text"]))
    fig_discount.add_hline(y=100, line_dash="dash", line_color=C["dim"])
    fig_discount.update_layout(**CHART, height=320, title="Blended Price to NAV by Deal Type", yaxis_title="% of NAV")

    pipe = pd.DataFrame(pipeline)
    if not pipe.empty:
        bridge = pd.DataFrame({
            "Deal": pipe["name"],
            "Current NAV": pipe["current_nav"],
            "Uplift": pipe["pro_forma_nav"].fillna(pipe["current_nav"]) - pipe["current_nav"],
            "Pro Forma NAV": pipe["pro_forma_nav"].fillna(pipe["current_nav"])
        })
        fig_bridge = go.Figure()
        fig_bridge.add_trace(
            go.Bar(x=bridge["Deal"], y=bridge["Current NAV"], name="Current NAV", marker_color=C["sky"]))
        fig_bridge.add_trace(
            go.Bar(x=bridge["Deal"], y=bridge["Uplift"], name="PF NAV uplift", marker_color=C["green"]))
        fig_bridge.update_layout(**CHART, barmode="relative", height=340,
                                 title="Pipeline Current NAV to Pro Forma NAV Bridge", yaxis_title="$M")
    else:
        fig_bridge = go.Figure()
        fig_bridge.update_layout(**CHART, height=340, title="Pipeline Current NAV to Pro Forma NAV Bridge")

    return html.Div([
        html.Div([
            card([dcc.Graph(figure=fig_vintage, config={"displayModeBar": False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_maturity, config={"displayModeBar": False})], dict(flex=1)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap", marginBottom=16)),
        html.Div([
            card([dcc.Graph(figure=fig_manager, config={"displayModeBar": False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_region, config={"displayModeBar": False})], dict(flex=1)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap", marginBottom=16)),
        html.Div([
            card([dcc.Graph(figure=fig_discount, config={"displayModeBar": False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_bridge, config={"displayModeBar": False})], dict(flex=1)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap", marginBottom=16)),
        card([dcc.Graph(figure=fig_scatter, config={"displayModeBar": False})], dict(marginBottom=16)),
        card([section_lbl("Refinancing Wall Detail"), wall_table]),
    ])


def tab_pacing(portfolio, pipeline, placeholders, config):
    df = build_pacing_df(portfolio, pipeline, placeholders, config)
    recycling_rate = float(config.get("recycling_rate", 100) or 100)

    fig_dep = go.Figure()
    fig_dep.add_trace(go.Bar(x=df["Quarter"], y=df["New Deployment"], name="New Deployment", marker_color=C["blue"]))
    fig_dep.add_trace(
        go.Bar(x=df["Quarter"], y=df["Principal Recycled"], name="Principal Recycled (100%)", marker_color=C["teal"]))
    fig_dep.add_trace(
        go.Bar(x=df["Quarter"], y=df["Interest Distributed"], name="Interest to Investors", marker_color=C["green"],
               opacity=0.7))
    fig_dep.update_layout(**CHART, height=360, barmode="stack",
                          title=f"Capital Deployment — Principal Recycling {recycling_rate:.0f}% · Interest Distributed to Investors")

    fig_nav = go.Figure()
    fig_nav.add_trace(
        go.Scatter(x=df["Quarter"], y=df["NAV"], mode="lines+markers", name="NAV", line=dict(color=C["sky"], width=3)))
    fig_nav.add_trace(go.Scatter(x=df["Quarter"], y=df["Dry Powder"], mode="lines+markers", name="Dry Powder",
                                 line=dict(color=C["amber"], width=2, dash="dash")))
    fig_nav.update_layout(**CHART, height=340, title="NAV and Dry Powder Forecast")

    fig_util = go.Figure(go.Bar(x=df["Quarter"], y=df["Utilisation"], marker_color=C["purple"],
                                text=[f"{v:.0f}%" for v in df["Utilisation"]], textposition="outside",
                                textfont_color=C["text"]))
    fig_util.add_hline(y=float(config.get("target_utilisation", 85)), line_dash="dash", line_color=C["amber"])
    fig_util.update_layout(**CHART, height=320, title="Utilisation Path")

    # ── Future Duration Needed Panel ──────────────────────────────────────────
    fund_size = float(config.get("fund_size", 1000) or 1000)
    target_duration = float(config.get("target_duration", 3.5) or 3.5)
    wa_yield = weighted_average(portfolio + pipeline, "all_in_yield") or 10.0

    deals_all = portfolio + pipeline
    current_deployed = sum(float(d.get("commitment", 0) or 0) for d in portfolio)
    current_duration = None
    target_net = float(config.get("target_net_return", 11) or 11)
    if portfolio:
        total = sum(d["commitment"] for d in portfolio)
        current_duration = sum(modified_duration(d, target_net) * d["commitment"] for d in portfolio) / total

    # How much more duration is needed to meet the target
    pipeline_amt = sum(float(d.get("commitment", 0) or 0) for d in pipeline)
    pipeline_duration = None
    if pipeline:
        total_p = sum(d["commitment"] for d in pipeline)
        pipeline_duration = sum(modified_duration(d, target_net) * d["commitment"] for d in pipeline) / total_p

    total_deployed_incl_pipe = current_deployed + pipeline_amt
    blended_duration = None
    if total_deployed_incl_pipe > 0:
        port_dur_contrib = (current_duration or 0) * current_deployed
        pipe_dur_contrib = (pipeline_duration or 0) * pipeline_amt
        blended_duration = (port_dur_contrib + pipe_dur_contrib) / total_deployed_incl_pipe

    duration_gap = (target_duration - (blended_duration or 0))

    # Duration buckets needed to plug the gap
    bucket_labels = ["0-2y", "2-3y", "3-4y", "4-5y", "5-6y", "6-7y"]
    bucket_midpoints = [1.0, 2.5, 3.5, 4.5, 5.5, 6.5]
    future_alloc_total = sum(float(p.get("size", 0) or 0) for p in placeholders)

    fig_dur_needed = go.Figure()
    # show current portfolio duration breakdown
    dur_buckets = {}
    for d in deals_all:
        md = modified_duration(d, target_net)
        b = maturity_bucket(d["hold_years"])
        dur_buckets[b] = dur_buckets.get(b, 0) + d["commitment"]

    fig_dur_needed.add_trace(go.Bar(
        x=list(dur_buckets.keys()), y=list(dur_buckets.values()),
        name="Current + Pipeline", marker_color=C["blue"],
        text=[fmt_money(v) for v in dur_buckets.values()], textposition="outside", textfont_color=C["text"]
    ))
    fig_dur_needed.add_hline(y=total_deployed_incl_pipe * target_duration / len(dur_buckets) if dur_buckets else 0,
                             line_dash="dot", line_color=C["amber"], annotation_text="Target avg bucket")
    fig_dur_needed.update_layout(**CHART, height=320, title="Duration Bucket Exposure — Portfolio + Pipeline")

    duration_kpis = html.Div([
        kpi("Current Portfolio Duration", f"{current_duration:.2f}y" if current_duration is not None else "—",
            "Wtd modified duration", C["sky"]),
        kpi("Incl. Pipeline Duration", f"{blended_duration:.2f}y" if blended_duration is not None else "—",
            "Portfolio + pipeline blended", C["purple"]),
        kpi("Target Duration", f"{target_duration:.2f}y", "From fund config", C["amber"]),
        kpi("Duration Gap", f"{duration_gap:+.2f}y" if blended_duration is not None else "—",
            "Need longer-dated assets" if duration_gap > 0 else "Portfolio is long enough",
            C["red"] if duration_gap > 0.2 else C["green"]),
        kpi("Future Allocations", fmt_money(future_alloc_total),
            f"{len(placeholders)} placeholders", C["teal"]),
    ], style=dict(display="flex", gap=10, flexWrap="wrap", marginBottom=12))

    # Interest income summary
    annual_interest = current_deployed * (wa_yield / 100)
    interest_summary = card([
        section_lbl("Principal Recycling & Interest Distribution Summary"),
        html.Div([
            kpi("Recycling Rate", f"{recycling_rate:.0f}%", "100% = full principal reinvested", C["teal"]),
            kpi("Deployed NAV", fmt_money(current_deployed), "Earns interest", C["sky"]),
            kpi("Wtd Avg Yield", f"{wa_yield:.1f}%", "Portfolio + pipeline", C["amber"]),
            kpi("Est. Annual Interest Income", fmt_money(annual_interest), "Distributed to investors", C["green"]),
            kpi("Quarterly Interest Dist.", fmt_money(annual_interest / 4), "Per quarter estimate", C["purple"]),
        ], style=dict(display="flex", gap=10, flexWrap="wrap")),
        html.Div(
            "Principal repayments are fully reinvested (100% recycling). Coupon/interest income flows to investors each quarter.",
            style=dict(color=C["muted"], fontSize=11, marginTop=10, fontFamily=C["sans"])),
    ], dict(marginBottom=16))

    table = dash_table.DataTable(data=df.to_dict("records"), columns=[{"name": c, "id": c} for c in df.columns],
                                 style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                 page_size=10, style_table={"overflowX": "auto"})

    return html.Div([
        interest_summary,
        html.Div([
            card([dcc.Graph(figure=fig_dep, config={"displayModeBar": False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_nav, config={"displayModeBar": False})], dict(flex=1)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap", marginBottom=16)),
        card([
            section_lbl("Future Duration Analysis"),
            duration_kpis,
            dcc.Graph(figure=fig_dur_needed, config={"displayModeBar": False}),
        ], dict(marginBottom=16)),
        card([dcc.Graph(figure=fig_util, config={"displayModeBar": False})], dict(marginBottom=16)),
        card([section_lbl("Quarterly Pacing Schedule"), table]),
    ])


def tab_returns(portfolio, pipeline, config):
    deals = portfolio + pipeline
    gross_target = float(config.get("target_net_return", 11) or 11) + float(config.get("fee_drag", 1.5) or 1.5)
    hold_range = [1, 2, 3, 4, 5, 6, 7]
    req_rows = []
    for h in hold_range:
        req_rows.append({
            "Hold (y)": h,
            "Req MOIC": f"{required_moic_for_target(h, gross_target):.2f}x",
            "Req Gross IRR": f"{gross_target:.1f}%",
            "Req Exit Value on $50m": fmt_money(50 * required_moic_for_target(h, gross_target)),
        })
    req_tbl = dash_table.DataTable(data=req_rows, columns=[{"name": c, "id": c} for c in req_rows[0]],
                                   style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
                                   style_table={"overflowX": "auto"})

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hold_range, y=[required_moic_for_target(h, gross_target) for h in hold_range],
                             mode="lines+markers", line=dict(color=C["amber"], width=3), name="Required MOIC"))
    fig.update_layout(**CHART, height=320, title="Required MOIC by Hold Period", xaxis_title="Hold Period (y)",
                      yaxis_title="MOIC")

    scatter = go.Figure()
    scatter.add_trace(go.Scatter(
        x=[d["hold_years"] for d in deals],
        y=[calc_irr_newton(d["commitment"], d["moic"], d["hold_years"]) or 0 for d in deals],
        mode="markers+text",
        marker=dict(color=C["blue"], size=[max(d["commitment"] * 0.5, 8) for d in deals], opacity=0.8),
        text=[d["name"].split()[-1] for d in deals], textposition="top center", textfont=dict(color=C["text"], size=9),
        name="Deals"
    ))
    scatter.add_hline(y=gross_target, line_dash="dash", line_color=C["amber"])
    scatter.update_layout(**CHART, height=340, title="Deal IRR vs Hold Period", xaxis_title="Hold (y)",
                          yaxis_title="IRR (%)")

    controls = card([
        section_lbl("Discount Return Calculator"),
        html.Div([
            _field("NAV Growth % p.a.", dcc.Input(id="disc-nav-growth", type="number", value=4.0, step=0.5, style=INP)),
            _field("Exit Price to NAV %",
                   dcc.Input(id="disc-exit-price", type="number", value=100.0, step=0.5, style=INP)),
            _field("Hold Override (blank = deal hold)",
                   dcc.Input(id="disc-hold-override", type="number", value=None, step=0.25, style=INP)),
        ], style=dict(display="grid", gridTemplateColumns="repeat(3, minmax(180px, 1fr))", gap=10)),
        html.Div(id="discount-return-output", style=dict(marginTop=14))
    ], dict(marginBottom=16))

    return html.Div([
        html.Div([
            card([section_lbl("Required Return Thresholds"), req_tbl], dict(flex=2)),
            card([
                kpi("Net Target", f"{config.get('target_net_return', 11):.1f}%", "Annualised", C["teal"]),
                html.Div(style=dict(height=10)),
                kpi("Gross Target", f"{gross_target:.1f}%", "Net + fee drag", C["amber"]),
                html.Div(style=dict(height=10)),
                kpi("MOIC @ 3y", f"{required_moic_for_target(3, gross_target):.2f}x", "Required", C["sky"]),
                html.Div(style=dict(height=10)),
                kpi("MOIC @ 5y", f"{required_moic_for_target(5, gross_target):.2f}x", "Required", C["purple"]),
            ], dict(flex=1, minWidth=220))
        ], style=dict(display="flex", gap=16, flexWrap="wrap", marginBottom=16)),
        controls,
        card([dcc.Graph(figure=fig, config={"displayModeBar": False})], dict(marginBottom=16)),
        card([dcc.Graph(figure=scatter, config={"displayModeBar": False})]),
    ])


def tab_settings(config):
    target_portfolio = float(config.get("fund_size", 0) or 0) * float(config.get("target_utilisation", 85) or 85) / 100
    deals_per_year = max(float(config.get("deals_per_year", 8) or 8), 1)
    max_deal_pct = float(config.get("max_deal_pct", 8) or 8) / 100
    avg_deal = target_portfolio / max(deals_per_year * float(config.get("deployment_years", 4) or 4), 1)
    max_deal = float(config.get("fund_size", 0) or 0) * max_deal_pct
    min_deal = avg_deal * 0.6

    return html.Div([
        html.Div([
            card([
                section_lbl("Credit Bite Sizing"),
                kpi("Min Deal Size", fmt_money(min_deal), "Suggested lower bound", C["teal"]),
                html.Div(style=dict(height=10)),
                kpi("Target Deal Size", fmt_money(avg_deal), "Base case pacing", C["sky"]),
                html.Div(style=dict(height=10)),
                kpi("Max Deal Size", fmt_money(max_deal), f"{config.get('max_deal_pct', 8):.1f}% of fund", C["amber"]),
            ], dict(flex=1)),
            card([
                section_lbl("Model Parameters"),
                _field("Deployment Years",
                       dcc.Input(id="cfg-deployment-years", type="number", value=config.get("deployment_years", 4),
                                 step=0.5, style=INP)),
                _field("Deals Per Year",
                       dcc.Input(id="cfg-deals-per-year", type="number", value=config.get("deals_per_year", 8), step=1,
                                 style=INP)),
                _field("Target Utilisation %",
                       dcc.Input(id="cfg-util", type="number", value=config.get("target_utilisation", 85), step=1,
                                 style=INP)),
                _field("Max Deal % of Fund",
                       dcc.Input(id="cfg-max-deal", type="number", value=config.get("max_deal_pct", 8), step=0.5,
                                 style=INP)),
                html.Button("Save Settings", id="save-config-btn",
                            style={**BTN(C["blue"]), "width": "100%", "marginTop": 10}),
                html.Div(id="config-msg", style=dict(marginTop=8, color=C["green"], fontSize=11)),
            ], dict(flex=1, minWidth=260)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


def tab_twr_montecarlo(portfolio, pipeline, config):
    """Monte Carlo TWR simulator for the credit portfolio."""
    deals = portfolio + pipeline
    if not deals:
        return card("No portfolio data available for simulation.")

    wa_yield = weighted_average(deals, "all_in_yield") or 10.0
    wa_spread = weighted_average(deals, "spread_bps") or 650.0
    wa_hold = weighted_average(deals, "hold_years") or 3.5
    fund_size = float(config.get("fund_size", 1000) or 1000)
    fee_drag = float(config.get("fee_drag", 1.5) or 1.5)
    target_net = float(config.get("target_net_return", 11.0) or 11.0)
    recycling_rate = float(config.get("recycling_rate", 100) or 100) / 100
    deployed = sum(float(d.get("commitment", 0) or 0) for d in portfolio)
    n_sims = 1000
    n_quarters = 20

    # Seed controls layout
    controls = card([
        section_lbl("Monte Carlo TWR Simulator — Controls"),
        html.Div([
            _field("Simulations", dcc.Input(id="mc-n-sims", type="number", value=1000, step=100, style=INP)),
            _field("Quarters to Simulate", dcc.Input(id="mc-quarters", type="number", value=20, step=4, style=INP)),
            _field("Base Yield Assumption (%)",
                   dcc.Input(id="mc-base-yield", type="number", value=round(wa_yield, 1), step=0.25, style=INP)),
            _field("Yield Volatility (±%)",
                   dcc.Input(id="mc-yield-vol", type="number", value=1.5, step=0.25, style=INP)),
            _field("Default Rate Annual (%)",
                   dcc.Input(id="mc-default-rate", type="number", value=1.0, step=0.25, style=INP)),
            _field("Recovery Rate (%)", dcc.Input(id="mc-recovery", type="number", value=65.0, step=5, style=INP)),
            _field("Spread Drift Volatility (bps)",
                   dcc.Input(id="mc-spread-vol", type="number", value=50, step=10, style=INP)),
            _field("Base Rate Drift (±%)",
                   dcc.Input(id="mc-rate-drift", type="number", value=0.5, step=0.25, style=INP)),
            html.Div([html.Label(" "), html.Button("▶ Run Simulation", id="mc-run-btn",
                                                   style={**BTN(C["blue"]), "width": "100%", "padding": "10px 16px"})]),
        ], style=dict(display="grid", gridTemplateColumns="repeat(8, 1fr)", gap=8, alignItems="end")),
    ], dict(marginBottom=16))

    output_area = html.Div(id="mc-output", style=dict(marginTop=0))

    return html.Div([controls, output_area])


def run_mc_simulation(n_sims, n_quarters, base_yield, yield_vol, default_rate_annual,
                      recovery_rate, spread_vol_bps, rate_drift, deployed, fund_size,
                      fee_drag, recycling_rate, wa_hold):
    """Run Monte Carlo and return percentile TWR paths + summary stats."""
    random.seed(42)
    np.random.seed(42)

    q_default = default_rate_annual / 100 / 4
    q_recovery = recovery_rate / 100
    q_fee = fee_drag / 100 / 4

    all_twr = []

    for _ in range(n_sims):
        nav = deployed
        cumulative_return = 1.0
        path = [1.0]

        for q in range(n_quarters):
            # Stochastic yield: base + random shock
            q_yield = (base_yield / 100 / 4) + np.random.normal(0, yield_vol / 100 / 4)
            q_yield = max(q_yield, 0.001)

            # Stochastic defaults
            defaults = nav * q_default * (1 + np.random.exponential(0.5))
            loss = defaults * (1 - q_recovery)

            # Interest income (distributed, not compounded since recycling is principal-only)
            interest_income = nav * q_yield  # distributed to investors

            # Principal recycled — NAV stays stable, just interest flows out
            nav_after_defaults = max(nav - loss, 0)

            # Principal recycling: repayments come back in
            q_hold_quarters = max(int(round(wa_hold * 4)), 1)
            repayment = nav_after_defaults / q_hold_quarters if q > 4 else 0
            recycled_principal = repayment * recycling_rate
            nav = max(nav_after_defaults - repayment + recycled_principal, 0)

            # TWR: return this quarter = interest received / nav at start (before defaults)
            # Net of defaults and fees
            q_return = (interest_income - loss - nav * q_fee) / max(nav, 1)
            cumulative_return *= (1 + q_return)
            path.append(cumulative_return)

        all_twr.append(path)

    arr = np.array(all_twr)  # shape: (n_sims, n_quarters+1)
    return arr

    target_portfolio = float(config.get("fund_size", 0) or 0) * float(config.get("target_utilisation", 85) or 85) / 100
    deals_per_year = max(float(config.get("deals_per_year", 8) or 8), 1)
    max_deal_pct = float(config.get("max_deal_pct", 8) or 8) / 100
    avg_deal = target_portfolio / max(deals_per_year * float(config.get("deployment_years", 4) or 4), 1)
    max_deal = float(config.get("fund_size", 0) or 0) * max_deal_pct
    min_deal = avg_deal * 0.6

    return html.Div([
        html.Div([
            card([
                section_lbl("Credit Bite Sizing"),
                kpi("Min Deal Size", fmt_money(min_deal), "Suggested lower bound", C["teal"]),
                html.Div(style=dict(height=10)),
                kpi("Target Deal Size", fmt_money(avg_deal), "Base case pacing", C["sky"]),
                html.Div(style=dict(height=10)),
                kpi("Max Deal Size", fmt_money(max_deal), f"{config.get('max_deal_pct', 8):.1f}% of fund", C["amber"]),
            ], dict(flex=1)),
            card([
                section_lbl("Model Parameters"),
                _field("Deployment Years",
                       dcc.Input(id="cfg-deployment-years", type="number", value=config.get("deployment_years", 4),
                                 step=0.5, style=INP)),
                _field("Deals Per Year",
                       dcc.Input(id="cfg-deals-per-year", type="number", value=config.get("deals_per_year", 8), step=1,
                                 style=INP)),
                _field("Target Utilisation %",
                       dcc.Input(id="cfg-util", type="number", value=config.get("target_utilisation", 85), step=1,
                                 style=INP)),
                _field("Max Deal % of Fund",
                       dcc.Input(id="cfg-max-deal", type="number", value=config.get("max_deal_pct", 8), step=0.5,
                                 style=INP)),
                html.Button("Save Settings", id="save-config-btn",
                            style={**BTN(C["blue"]), "width": "100%", "marginTop": 10}),
                html.Div(id="config-msg", style=dict(marginTop=8, color=C["green"], fontSize=11)),
            ], dict(flex=1, minWidth=260)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


@app.callback(
    Output("discount-return-output", "children"),
    Input("disc-nav-growth", "value"),
    Input("disc-exit-price", "value"),
    Input("disc-hold-override", "value"),
    Input("portfolio-store", "data"),
    Input("pipeline-store", "data"),
)
def update_discount_return_output(nav_growth, exit_price_to_nav, hold_override, portfolio, pipeline):
    nav_growth = float(nav_growth or 0)
    exit_price_to_nav = float(exit_price_to_nav or 100)
    deals = [dict(d, pool="Portfolio") for d in (portfolio or [])] + [dict(d, pool="Pipeline") for d in
                                                                      (pipeline or [])]
    rows = []
    total_cost = total_exit = 0
    weighted_years = 0
    for d in deals:
        base_nav = float(
            d.get("pro_forma_nav") if d.get("status") == "Pipeline" and d.get("pro_forma_nav") is not None else d.get(
                "current_nav", d.get("commitment", 0)) or 0)
        hold_y = float(hold_override) if hold_override not in (None, "") else float(d.get("hold_years", 0) or 0)
        entry_ptnav = float(d.get("price_to_nav", 100) or 100)
        purchase_price = discount_purchase_price(base_nav, entry_ptnav)
        implied_moic = discount_implied_moic(base_nav, entry_ptnav, hold_y, nav_growth, exit_price_to_nav)
        implied_irr = discount_implied_irr(base_nav, entry_ptnav, hold_y, nav_growth, exit_price_to_nav)
        exit_nav = base_nav * ((1 + nav_growth / 100) ** hold_y) if hold_y > 0 else base_nav
        exit_value = exit_nav * exit_price_to_nav / 100
        total_cost += purchase_price
        total_exit += exit_value
        weighted_years += purchase_price * hold_y
        rows.append({
            "Pool": d.get("pool", d.get("status", "")),
            "Deal": d.get("name", ""),
            "Manager": d.get("manager", ""),
            "Region": d.get("region", ""),
            "Entry Price/NAV": f"{entry_ptnav:.1f}%",
            "Base NAV": fmt_money(base_nav),
            "Implied Cost": fmt_money(purchase_price),
            "Exit NAV": fmt_money(exit_nav),
            "Exit Price/NAV": f"{exit_price_to_nav:.1f}%",
            "Implied MOIC": f"{implied_moic:.2f}x" if implied_moic is not None else "—",
            "Discount IRR": f"{implied_irr:.1f}%" if implied_irr is not None else "—",
        })
    weighted_hold = weighted_years / total_cost if total_cost else 0
    portfolio_moic = total_exit / total_cost if total_cost else None
    portfolio_irr = (portfolio_moic ** (1 / weighted_hold) - 1) * 100 if portfolio_moic and weighted_hold > 0 else None
    total_base_nav = sum(float(
        d.get("pro_forma_nav") if d.get("status") == "Pipeline" and d.get("pro_forma_nav") is not None else d.get(
            "current_nav", d.get("commitment", 0)) or 0) for d in deals)
    blended_discount = (100 - (total_cost / total_base_nav * 100)) if total_base_nav else None

    tbl = dash_table.DataTable(
        data=rows,
        columns=[{"name": c, "id": c} for c in rows[0].keys()] if rows else [],
        style_cell=TBL_CELL, style_header=TBL_HEAD, style_data_conditional=TBL_ODD,
        page_size=8, style_table={"overflowX": "auto"}
    )

    summary = html.Div([
        kpi("Blended Entry Discount", f"{blended_discount:.1f}%" if blended_discount is not None else "—",
            "Versus base NAV", C["green"]),
        kpi("Total Implied Cost", fmt_money(total_cost), "Entry cost at discount", C["sky"]),
        kpi("Total Exit Value", fmt_money(total_exit), "Based on growth + exit multiple", C["amber"]),
        kpi("Blended Discount IRR", f"{portfolio_irr:.1f}%" if portfolio_irr is not None else "—",
            "Weighted by entry cost", C["purple"]),
    ], style=dict(display="flex", gap=10, flexWrap="wrap", marginBottom=12))

    return html.Div([summary, tbl])


# ── Mutation callbacks ───────────────────────────────────────────────────────
def build_deal(nid, name, manager, deal_type, region, sector, commitment, moic, hold, deal_yield, spread, ltv,
               original_legal_commitment=None, price_to_nav=100, current_nav=None, pro_forma_nav=None,
               security=None, rate_type=None, stage=None, priority=None, status="Allocated"):
    current_commitment = float(commitment)
    original_legal_commitment = float(
        original_legal_commitment if original_legal_commitment is not None else current_commitment)
    current_nav = float(current_nav if current_nav is not None else current_commitment)
    pro_forma_nav = float(pro_forma_nav) if pro_forma_nav is not None else (
        current_nav if status == "Pipeline" else None)
    return dict(
        id=nid, name=name, manager=manager or "", deal_type=deal_type, region=region or "Europe", sector=sector,
        commitment=current_commitment, current_commitment=current_commitment,
        original_legal_commitment=original_legal_commitment,
        price_to_nav=float(price_to_nav), current_nav=current_nav, pro_forma_nav=pro_forma_nav,
        moic=float(moic), hold_years=float(hold), spread_bps=float(spread), base_rate=4.0,
        all_in_yield=float(deal_yield), ltv=float(ltv), attachment_point=0,
        security_type=security or "Senior Secured", rate_type=rate_type or "Floating",
        vintage=datetime.now().year, deploy_q=1, deployment_rate=100, status=status,
        pipeline_stage=stage, priority=priority,
    )


@app.callback(
    Output("portfolio-store", "data"), Output("next-id", "data"), Output("portfolio-msg", "children"),
    Input("add-portfolio-btn", "n_clicks"),
    State("portfolio-store", "data"), State("next-id", "data"),
    State("port-name", "value"), State("port-manager", "value"), State("port-type", "value"),
    State("port-region", "value"), State("port-sector", "value"),
    State("port-orig-commit", "value"), State("port-commit", "value"), State("port-moic", "value"),
    State("port-hold", "value"),
    State("port-yield", "value"), State("port-spread", "value"), State("port-ltv", "value"),
    State("port-price-to-nav", "value"), State("port-current-nav", "value"),
    State("port-security", "value"), State("port-rate", "value"),
    prevent_initial_call=True,
)
def add_portfolio(_, portfolio, nid, name, manager, deal_type, region, sector, original_legal_commitment, commitment,
                  moic, hold, deal_yield, spread, ltv, price_to_nav, current_nav, security, rate_type):
    if not name:
        return portfolio, nid, "⚠ Enter a deal name."
    deal = build_deal(nid, name, manager, deal_type, region, sector, commitment, moic, hold, deal_yield, spread, ltv,
                      original_legal_commitment, price_to_nav, current_nav, None, security, rate_type,
                      status="Allocated")
    return portfolio + [deal], nid + 1, f"✓ Added portfolio deal: {name}"


@app.callback(
    Output("pipeline-store", "data"), Output("next-id", "data", allow_duplicate=True),
    Output("pipeline-msg", "children"),
    Input("add-pipeline-btn", "n_clicks"),
    State("pipeline-store", "data"), State("next-id", "data"),
    State("pipe-name", "value"), State("pipe-manager", "value"), State("pipe-type", "value"),
    State("pipe-region", "value"), State("pipe-sector", "value"),
    State("pipe-stage", "value"), State("pipe-priority", "value"), State("pipe-orig-commit", "value"),
    State("pipe-commit", "value"),
    State("pipe-moic", "value"), State("pipe-hold", "value"), State("pipe-yield", "value"),
    State("pipe-spread", "value"), State("pipe-ltv", "value"), State("pipe-price-to-nav", "value"),
    State("pipe-current-nav", "value"), State("pipe-pro-forma-nav", "value"),
    prevent_initial_call=True,
)
def add_pipeline(_, pipeline, nid, name, manager, deal_type, region, sector, stage, priority, original_legal_commitment,
                 commitment, moic, hold, deal_yield, spread, ltv, price_to_nav, current_nav, pro_forma_nav):
    if not name:
        return pipeline, nid, "⚠ Enter a deal name."
    deal = build_deal(nid, name, manager, deal_type, region, sector, commitment, moic, hold, deal_yield, spread, ltv,
                      original_legal_commitment, price_to_nav, current_nav, pro_forma_nav, stage=stage,
                      priority=priority, status="Pipeline")
    return pipeline + [deal], nid + 1, f"✓ Added pipeline deal: {name}"


@app.callback(
    Output("placeholder-store", "data"), Output("next-id", "data", allow_duplicate=True),
    Output("placeholder-msg", "children"),
    Input("add-placeholder-btn", "n_clicks"),
    State("placeholder-store", "data"), State("next-id", "data"),
    State("ph-year", "value"), State("ph-quarter", "value"), State("ph-type", "value"), State("ph-sector", "value"),
    State("ph-size", "value"), State("ph-yield", "value"), State("ph-duration", "value"), State("ph-ltv", "value"),
    State("ph-notes", "value"),
    prevent_initial_call=True,
)
def add_placeholder(_, placeholders, nid, year, quarter, deal_type, sector, size, target_yield, target_duration,
                    target_ltv, notes):
    p = dict(id=nid, year=int(year), quarter=quarter, deal_type=deal_type, sector=sector, size=float(size),
             target_yield=float(target_yield), target_duration=float(target_duration), target_ltv=float(target_ltv),
             notes=notes or "")
    return placeholders + [p], nid + 1, f"✓ Added future allocation for {quarter} {year}"


@app.callback(
    Output("portfolio-store", "data", allow_duplicate=True), Output("portfolio-action-msg", "children"),
    Input("delete-portfolio-btn", "n_clicks"), State("portfolio-table", "selected_rows"),
    State("portfolio-store", "data"),
    prevent_initial_call=True,
)
def delete_portfolio(_, selected, portfolio):
    if not selected:
        return no_update, "Select a portfolio deal first."
    idx = selected[0]
    if idx >= len(portfolio):
        return no_update, "Invalid selection."
    name = portfolio[idx]["name"]
    new = [d for i, d in enumerate(portfolio) if i != idx]
    return new, f"Deleted portfolio deal: {name}"


@app.callback(
    Output("pipeline-store", "data", allow_duplicate=True), Output("portfolio-store", "data", allow_duplicate=True),
    Output("pipeline-action-msg", "children"),
    Input("promote-pipeline-btn", "n_clicks"), State("pipeline-table", "selected_rows"),
    State("pipeline-store", "data"), State("portfolio-store", "data"),
    prevent_initial_call=True,
)
def promote_pipeline(_, selected, pipeline, portfolio):
    if not selected:
        return no_update, no_update, "Select a pipeline deal first."
    idx = selected[0]
    if idx >= len(pipeline):
        return no_update, no_update, "Invalid selection."
    promoted = dict(pipeline[idx])
    promoted["status"] = "Allocated"
    promoted["pipeline_stage"] = None
    promoted["priority"] = None
    if promoted.get("pro_forma_nav") is not None:
        promoted["current_nav"] = promoted.get("pro_forma_nav")
    new_pipeline = [d for i, d in enumerate(pipeline) if i != idx]
    return new_pipeline, portfolio + [promoted], f"Promoted to portfolio: {promoted['name']}"


@app.callback(
    Output("pipeline-store", "data", allow_duplicate=True),
    Output("pipeline-action-msg", "children", allow_duplicate=True),
    Input("delete-pipeline-btn", "n_clicks"), State("pipeline-table", "selected_rows"), State("pipeline-store", "data"),
    prevent_initial_call=True,
)
def delete_pipeline(_, selected, pipeline):
    if not selected:
        return no_update, "Select a pipeline deal first."
    idx = selected[0]
    if idx >= len(pipeline):
        return no_update, "Invalid selection."
    name = pipeline[idx]["name"]
    return [d for i, d in enumerate(pipeline) if i != idx], f"Deleted pipeline deal: {name}"


@app.callback(
    Output("placeholder-store", "data", allow_duplicate=True), Output("placeholder-action-msg", "children"),
    Input("delete-placeholder-btn", "n_clicks"), State("placeholder-table", "selected_rows"),
    State("placeholder-store", "data"),
    prevent_initial_call=True,
)
def delete_placeholder(_, selected, placeholders):
    if not selected:
        return no_update, "Select a future allocation first."
    idx = selected[0]
    if idx >= len(placeholders):
        return no_update, "Invalid selection."
    p = placeholders[idx]
    return [d for i, d in enumerate(placeholders) if i != idx], f"Deleted placeholder: {p['quarter']} {p['year']}"


@app.callback(
    Output("config-store", "data", allow_duplicate=True), Output("config-msg", "children"),
    Input("save-config-btn", "n_clicks"),
    State("cfg-deployment-years", "value"), State("cfg-deals-per-year", "value"), State("cfg-util", "value"),
    State("cfg-max-deal", "value"), State("config-store", "data"),
    prevent_initial_call=True,
)
def save_config(_, deployment_years, deals_per_year, target_util, max_deal_pct, config):
    cfg = dict(config or DEFAULT_CONFIG)
    cfg.update({
        "deployment_years": float(deployment_years or cfg.get("deployment_years", 4)),
        "deals_per_year": float(deals_per_year or cfg.get("deals_per_year", 8)),
        "target_utilisation": float(target_util or cfg.get("target_utilisation", 85)),
        "max_deal_pct": float(max_deal_pct or cfg.get("max_deal_pct", 8)),
    })
    return cfg, "✓ Settings updated"


@app.callback(
    Output("fund-size", "value", allow_duplicate=True), Output("target-return", "value", allow_duplicate=True),
    Output("fee-drag", "value", allow_duplicate=True), Output("target-duration", "value", allow_duplicate=True),
    Output("recycling-rate", "value", allow_duplicate=True),
    Input("config-store", "data"), prevent_initial_call=True,
)
def reflect_config_to_header(config):
    return config.get("fund_size"), config.get("target_net_return"), config.get("fee_drag"), config.get(
        "target_duration"), config.get("recycling_rate")


@app.callback(
    Output("tabs", "id"),
    Input("portfolio-store", "data"), Input("pipeline-store", "data"), Input("placeholder-store", "data"),
    Input("config-store", "data"), Input("next-id", "data"),
)
def persist_all(portfolio, pipeline, placeholders, config, next_id):
    save_data(portfolio, pipeline, placeholders, config, next_id)
    return "tabs"


@app.callback(
    Output("mc-output", "children"),
    Input("mc-run-btn", "n_clicks"),
    State("mc-n-sims", "value"),
    State("mc-quarters", "value"),
    State("mc-base-yield", "value"),
    State("mc-yield-vol", "value"),
    State("mc-default-rate", "value"),
    State("mc-recovery", "value"),
    State("mc-spread-vol", "value"),
    State("mc-rate-drift", "value"),
    State("portfolio-store", "data"),
    State("pipeline-store", "data"),
    State("config-store", "data"),
    prevent_initial_call=True,
)
def run_montecarlo(_, n_sims, n_quarters, base_yield, yield_vol, default_rate, recovery,
                   spread_vol, rate_drift, portfolio, pipeline, config):
    n_sims = int(n_sims or 1000)
    n_quarters = int(n_quarters or 20)
    base_yield = float(base_yield or 10.0)
    yield_vol = float(yield_vol or 1.5)
    default_rate = float(default_rate or 1.0)
    recovery = float(recovery or 65.0)
    spread_vol = float(spread_vol or 50)
    rate_drift = float(rate_drift or 0.5)
    fee_drag = float(config.get("fee_drag", 1.5) or 1.5)
    recycling_rate = float(config.get("recycling_rate", 100) or 100) / 100
    fund_size = float(config.get("fund_size", 1000) or 1000)
    target_net = float(config.get("target_net_return", 11) or 11)
    deals = (portfolio or []) + (pipeline or [])
    deployed = sum(float(d.get("commitment", 0) or 0) for d in (portfolio or []))
    wa_hold = weighted_average(deals, "hold_years") or 3.5

    arr = run_mc_simulation(n_sims, n_quarters, base_yield, yield_vol, default_rate,
                            recovery, spread_vol, rate_drift, deployed, fund_size,
                            fee_drag, recycling_rate, wa_hold)

    quarters_labels = [f"Q{((q) % 4) + 1} Y{datetime.now().year + q // 4}" for q in range(n_quarters + 1)]

    p5 = np.percentile(arr, 5, axis=0)
    p25 = np.percentile(arr, 25, axis=0)
    p50 = np.percentile(arr, 50, axis=0)
    p75 = np.percentile(arr, 75, axis=0)
    p95 = np.percentile(arr, 95, axis=0)
    mean_path = np.mean(arr, axis=0)

    # TWR fan chart
    fig_fan = go.Figure()
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=p95, mode="lines", name="P95",
                                 line=dict(color=cl(C["green"], 0.3), width=0), showlegend=False))
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=p5, mode="lines", name="P5–P95 band",
                                 line=dict(color=cl(C["green"], 0.3), width=0),
                                 fill="tonexty", fillcolor=cl(C["green"], 0.08)))
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=p75, mode="lines", name="P75",
                                 line=dict(color=cl(C["teal"], 0.5), width=0), showlegend=False))
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=p25, mode="lines", name="P25–P75 band",
                                 line=dict(color=cl(C["teal"], 0.5), width=0),
                                 fill="tonexty", fillcolor=cl(C["teal"], 0.15)))
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=p50, mode="lines+markers", name="Median (P50)",
                                 line=dict(color=C["sky"], width=3)))
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=mean_path, mode="lines", name="Mean",
                                 line=dict(color=C["amber"], width=2, dash="dash")))
    # Target line
    target_path = [(1 + target_net / 100 / 4) ** q for q in range(n_quarters + 1)]
    fig_fan.add_trace(go.Scatter(x=quarters_labels, y=target_path, mode="lines", name=f"Target {target_net:.1f}% p.a.",
                                 line=dict(color=C["red"], width=2, dash="dot")))
    fig_fan.update_layout(**CHART, height=420,
                          title=f"TWR Monte Carlo Fan Chart — {n_sims:,} Simulations · Principal 100% Recycled · Interest Distributed",
                          yaxis_title="Cumulative TWR (×1 = flat)", xaxis_title="Quarter")

    # Final value distribution histogram
    final_vals = arr[:, -1]
    fig_hist = go.Figure(go.Histogram(x=final_vals, nbinsx=60, marker_color=C["purple"],
                                      opacity=0.8, name="Final TWR"))
    fig_hist.add_vline(x=float(p50[-1]), line_color=C["sky"], line_dash="dash",
                       annotation_text=f"P50: {p50[-1]:.3f}×", annotation_font_color=C["sky"])
    fig_hist.add_vline(x=float(mean_path[-1]), line_color=C["amber"], line_dash="dot",
                       annotation_text=f"Mean: {mean_path[-1]:.3f}×", annotation_font_color=C["amber"])
    fig_hist.add_vline(x=float(target_path[-1]), line_color=C["red"], line_dash="dot",
                       annotation_text=f"Target: {target_path[-1]:.3f}×", annotation_font_color=C["red"])
    fig_hist.update_layout(**CHART, height=340,
                           title="Distribution of Final Cumulative TWR", xaxis_title="Cumulative TWR",
                           yaxis_title="Count")

    # Annualised return distribution (from final TWR)
    ann_returns = ((final_vals ** (4 / n_quarters)) - 1) * 100
    pct_above_target = (ann_returns >= target_net).sum() / n_sims * 100

    # Per-quarter return distribution
    q_returns = (arr[:, 1:] / arr[:, :-1] - 1) * 100 * 4  # annualised quarterly returns
    q_mean = q_returns.mean(axis=0)
    q_p25 = np.percentile(q_returns, 25, axis=0)
    q_p75 = np.percentile(q_returns, 75, axis=0)

    fig_qret = go.Figure()
    fig_qret.add_trace(go.Scatter(x=quarters_labels[1:], y=q_p75, mode="lines",
                                  line=dict(color=cl(C["teal"], 0.4), width=0), showlegend=False))
    fig_qret.add_trace(go.Scatter(x=quarters_labels[1:], y=q_p25, mode="lines",
                                  line=dict(color=cl(C["teal"], 0.4), width=0),
                                  fill="tonexty", fillcolor=cl(C["teal"], 0.15), name="P25–P75"))
    fig_qret.add_trace(go.Scatter(x=quarters_labels[1:], y=q_mean, mode="lines+markers",
                                  name="Mean ann. return", line=dict(color=C["amber"], width=2)))
    fig_qret.add_hline(y=target_net, line_dash="dash", line_color=C["red"])
    fig_qret.update_layout(**CHART, height=320,
                           title="Quarterly Annualised Return Path (Mean ± IQR)", yaxis_title="Ann. Return (%)")

    # Summary KPIs
    ann_p5 = ((p5[-1] ** (4 / n_quarters)) - 1) * 100
    ann_p50 = ((p50[-1] ** (4 / n_quarters)) - 1) * 100
    ann_p95 = ((p95[-1] ** (4 / n_quarters)) - 1) * 100
    ann_mean = ((mean_path[-1] ** (4 / n_quarters)) - 1) * 100
    worst_drawdown = float(np.min((arr / np.maximum.accumulate(arr, axis=1) - 1).min(axis=1).mean()))

    summary_kpis = html.Div([
        kpi("P5 Ann. TWR", f"{ann_p5:.1f}%", "Downside scenario", C["red"]),
        kpi("P50 Ann. TWR", f"{ann_p50:.1f}%", "Median outcome", C["sky"]),
        kpi("P95 Ann. TWR", f"{ann_p95:.1f}%", "Upside scenario", C["green"]),
        kpi("Mean Ann. TWR", f"{ann_mean:.1f}%", f"vs target {target_net:.1f}%",
            C["green"] if ann_mean >= target_net else C["amber"]),
        kpi("% Paths ≥ Target", f"{pct_above_target:.0f}%", f"Target {target_net:.1f}% net", C["teal"]),
        kpi("Avg Max Drawdown", f"{worst_drawdown * 100:.1f}%", "Mean of worst path dips", C["pink"]),
    ], style=dict(display="flex", gap=10, flexWrap="wrap", marginBottom=16))

    # Scenario table
    scenario_rows = [
        {"Scenario": "Bear (P5)", "Ann. TWR": f"{ann_p5:.1f}%", "Final TWR Mult": f"{p5[-1]:.3f}×",
         "vs Target": f"{ann_p5 - target_net:+.1f}%"},
        {"Scenario": "Base (P25)", "Ann. TWR": f"{((p25[-1] ** (4 / n_quarters)) - 1) * 100:.1f}%",
         "Final TWR Mult": f"{p25[-1]:.3f}×",
         "vs Target": f"{((p25[-1] ** (4 / n_quarters)) - 1) * 100 - target_net:+.1f}%"},
        {"Scenario": "Median (P50)", "Ann. TWR": f"{ann_p50:.1f}%", "Final TWR Mult": f"{p50[-1]:.3f}×",
         "vs Target": f"{ann_p50 - target_net:+.1f}%"},
        {"Scenario": "Bull (P75)", "Ann. TWR": f"{((p75[-1] ** (4 / n_quarters)) - 1) * 100:.1f}%",
         "Final TWR Mult": f"{p75[-1]:.3f}×",
         "vs Target": f"{((p75[-1] ** (4 / n_quarters)) - 1) * 100 - target_net:+.1f}%"},
        {"Scenario": "Upside (P95)", "Ann. TWR": f"{ann_p95:.1f}%", "Final TWR Mult": f"{p95[-1]:.3f}×",
         "vs Target": f"{ann_p95 - target_net:+.1f}%"},
    ]
    scenario_tbl = dash_table.DataTable(
        data=scenario_rows, columns=[{"name": c, "id": c} for c in scenario_rows[0]],
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD + [
            {"if": {"filter_query": '{vs Target} contains "+"', "column_id": "vs Target"}, "color": C["green"]},
            {"if": {"filter_query": '{vs Target} contains "-"', "column_id": "vs Target"}, "color": C["red"]},
        ],
        style_table={"overflowX": "auto"}
    )

    note = html.Div(
        "Model assumes: principal fully recycled each period (100%); interest/coupon distributed quarterly to investors; "
        "defaults drawn from exponential distribution scaled to annual default rate; yield shocks are normally distributed; "
        "fees deducted quarterly. TWR measures portfolio performance independent of external cash flows.",
        style=dict(color=C["muted"], fontSize=10, marginTop=12, fontFamily=C["sans"], fontStyle="italic")
    )

    return html.Div([
        summary_kpis,
        html.Div([
            card([dcc.Graph(figure=fig_fan, config={"displayModeBar": False})], dict(flex=2)),
            card([dcc.Graph(figure=fig_hist, config={"displayModeBar": False})], dict(flex=1, minWidth=300)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap", marginBottom=16)),
        card([dcc.Graph(figure=fig_qret, config={"displayModeBar": False})], dict(marginBottom=16)),
        card([section_lbl("Scenario Summary Table"), scenario_tbl, note]),
    ])


if __name__ == "__main__":
    app.run(debug=True, port=8073)
