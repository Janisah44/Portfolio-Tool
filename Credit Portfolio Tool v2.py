"""
Evergreen Credit Secondaries & Co-Investment Fund
Portfolio Construction Tool v2

Features:
  · Allocated deals (deployed capital) with size tracking
  · Pipeline deals (not yet allocated) with promotion workflow
  · Required IRR per deal to achieve annualised TWR target
  · Evergreen pacing — continuous deployment & recycling model
  · Duration analysis — weighted average life & duration gap

Install:
    pip install dash plotly pandas numpy dash-bootstrap-components

Run:
    python portfolio_tool_v2.py
    → http://127.0.0.1:8050
"""

import math
import numpy as np
import pandas as pd
import json

import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx, ALL, no_update
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Palette ───────────────────────────────────────────────────────────────────
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
    """hex + opacity → rgba string"""
    r,g,b = int(base[1:3],16), int(base[3:5],16), int(base[5:7],16)
    return f"rgba({r},{g},{b},{opacity})"

CHART = dict(
    paper_bgcolor=C["panel"], plot_bgcolor=C["surface"],
    font=dict(family=C["mono"], color=C["text"], size=11),
    margin=dict(l=52, r=20, t=38, b=38),
    xaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    yaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
)

# ── Maths ─────────────────────────────────────────────────────────────────────

def ann_return_from_moic(moic, hold_y):
    if hold_y <= 0 or moic <= 0: return None
    return (moic ** (1/hold_y) - 1) * 100

def required_moic_for_twr(hold_y, twr_pct):
    return (1 + twr_pct/100) ** hold_y

def required_irr_for_twr(twr_pct, hold_y, fee_drag=0.0):
    """
    For an evergreen fund, IRR ≈ TWR when no interim cashflows.
    With fee drag the gross IRR needed = TWR + fee_drag.
    Returns annualised gross IRR % required.
    """
    return twr_pct + fee_drag

def calc_irr_newton(commitment, moic, hold_y, guess=0.12):
    if hold_y <= 0 or commitment <= 0: return None
    cfs = [(-commitment, 0), (commitment * moic, hold_y)]
    r = guess
    for _ in range(300):
        f  = sum(cf / (1+r)**t for cf,t in cfs)
        df = sum(-t*cf / ((1+r)**(t+1)) for cf,t in cfs)
        if abs(df) < 1e-14: break
        nr = r - f/df
        if abs(nr - r) < 1e-9: r = nr; break
        r = max(-0.999, nr)
    return r * 100

def weighted_avg_life(deals):
    """Commitment-weighted average hold period (years)."""
    total = sum(d["commitment"] for d in deals)
    if not total: return None
    return sum(d["commitment"] * d["hold_years"] for d in deals) / total

def portfolio_duration(deals, twr_pct):
    """
    Approximate modified duration of the portfolio.
    Treat each deal as a zero-coupon bond: D = hold_y / (1 + twr/100).
    Weighted by commitment.
    """
    total = sum(d["commitment"] for d in deals)
    if not total: return None
    wal = sum(d["commitment"] * d["hold_years"] for d in deals) / total
    return wal / (1 + twr_pct/100)

def evergreen_deployment_schedule(
    fund_size, target_utilisation, recycling_rate,
    avg_hold_y, deals_per_year, quarters=24
):
    """
    Model evergreen continuous deployment.
    recycling_rate: fraction of returned principal re-deployed (0–1).
    Returns DataFrame with quarterly deployed, recycled, NAV.
    """
    rows = []
    nav = 0.0
    cumulative_deployed = 0.0
    repaid_pool = 0.0
    q_hold = avg_hold_y * 4  # quarters until repayment

    for q in range(1, quarters+1):
        yr = math.ceil(q/4); qtr = ((q-1)%4)+1
        # new deployment from undeployed capital
        capacity = max(0, fund_size * target_utilisation - nav)
        new_deploy = min(capacity, fund_size / (avg_hold_y * 4) * 1.1)
        # recycled capital becomes available after avg_hold_y
        recycled = 0.0
        if q > q_hold:
            recycled = (nav * recycling_rate) / q_hold  # simplified
        total_deploy = new_deploy + recycled
        # repayments reduce NAV
        repayments = nav / q_hold if q > 4 else 0
        nav = max(0, nav + total_deploy - repayments)
        cumulative_deployed += total_deploy
        rows.append(dict(
            q=q, label=f"Q{qtr} Y{yr}",
            new_deploy=round(new_deploy,2),
            recycled=round(recycled,2),
            total_deploy=round(total_deploy,2),
            repayments=round(repayments,2),
            nav=round(nav,2),
            utilisation=round(nav/fund_size*100,1) if fund_size else 0,
            cumulative_deployed=round(cumulative_deployed,2),
        ))
    return pd.DataFrame(rows)

def duration_gap_analysis(deals, twr_pct, target_duration):
    """How many quarters of additional deals needed to hit target duration."""
    current_wal = weighted_avg_life(deals) or 0
    current_dur = portfolio_duration(deals, twr_pct) or 0
    gap_wal = target_duration - current_wal
    gap_dur = target_duration / (1 + twr_pct/100) - current_dur
    return dict(current_wal=current_wal, current_dur=current_dur,
                gap_wal=gap_wal, gap_dur=gap_dur)

# ── Seed data ─────────────────────────────────────────────────────────────────

SEED_ALLOCATED = [
    dict(id=1, name="Senior Secured LP Interest A", type="Secondary", sector="Diversified Credit",
         commitment=25, moic=1.45, hold_years=3.5, deploy_q=1, deployment_rate=85, status="allocated"),
    dict(id=2, name="Mezzanine Co-Invest B", type="Co-investment", sector="Healthcare",
         commitment=15, moic=1.72, hold_years=4.0, deploy_q=2, deployment_rate=100, status="allocated"),
    dict(id=3, name="Distressed Debt Portfolio C", type="Secondary", sector="TMT",
         commitment=30, moic=1.38, hold_years=2.5, deploy_q=1, deployment_rate=90, status="allocated"),
]

SEED_PIPELINE = [
    dict(id=10, name="Unitranche Co-Invest D", type="Co-investment", sector="Infrastructure",
         commitment=20, moic=1.85, hold_years=5.0, deploy_q=3, deployment_rate=100, status="pipeline",
         pipeline_stage="IC Approved", priority="High"),
    dict(id=11, name="CLO Tranche Secondary E", type="Secondary", sector="Structured Credit",
         commitment=18, moic=1.52, hold_years=3.0, deploy_q=4, deployment_rate=80, status="pipeline",
         pipeline_stage="Due Diligence", priority="Medium"),
    dict(id=12, name="First Lien Co-Invest F", type="Co-investment", sector="Consumer",
         commitment=12, moic=1.62, hold_years=3.5, deploy_q=5, deployment_rate=100, status="pipeline",
         pipeline_stage="Screening", priority="Low"),
    dict(id=13, name="Real Estate Debt Secondary G", type="Secondary", sector="Real Assets",
         commitment=22, moic=1.41, hold_years=3.0, deploy_q=5, deployment_rate=75, status="pipeline",
         pipeline_stage="Term Sheet", priority="High"),
]

SECTORS = ["Diversified Credit","Healthcare","TMT","Infrastructure",
           "Structured Credit","Consumer","Real Assets","Financial Services"]
TYPES   = ["Secondary","Co-investment"]
STAGES  = ["Screening","Due Diligence","Term Sheet","IC Approved","Closing"]
PRIOS   = ["High","Medium","Low"]

# ── App ───────────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, title="Evergreen Credit Portfolio Tool",
                suppress_callback_exceptions=True,
                meta_tags=[{"name":"viewport","content":"width=device-width,initial-scale=1"}])

# ── Style helpers ─────────────────────────────────────────────────────────────

INP = dict(background=C["surface"], border=f"1px solid {C['border2']}",
           color=C["text"], borderRadius=6, padding="6px 10px",
           fontFamily=C["mono"], fontSize=12, outline="none", width="100%")

BTN = lambda bg, fg="#fff": dict(
    background=bg, border="none", color=fg, borderRadius=6,
    padding="7px 16px", cursor="pointer", fontWeight=600,
    fontSize=12, fontFamily=C["sans"], letterSpacing=0.5)

TAG = lambda color: dict(
    background=cl(color, 0.15), border=f"1px solid {cl(color, 0.4)}",
    color=color, borderRadius=4, padding="2px 8px",
    fontSize=10, fontWeight=600, letterSpacing=1,
    textTransform="uppercase", display="inline-block")

TBL_CELL = dict(backgroundColor=C["panel"], color=C["text"],
                fontFamily=C["mono"], fontSize=11,
                padding="8px 12px", border=f"1px solid {C['border']}",
                textAlign="left")
TBL_HEAD = dict(backgroundColor=C["bg"], color=C["muted"],
                fontWeight=700, fontSize=10, letterSpacing=1.5,
                textTransform="uppercase", border=f"1px solid {C['border']}",
                padding="9px 12px")
TBL_ODD  = [{"if":{"row_index":"odd"}, "backgroundColor":C["surface"]}]

def pill(text, color):
    return html.Span(text, style=TAG(color))

def card(children, style_extra=None):
    base = dict(background=C["panel"], border=f"1px solid {C['border']}",
                borderRadius=10, padding=20)
    if style_extra: base.update(style_extra)
    return html.Div(children, style=base)

def section_lbl(text):
    return html.Div(text, style=dict(fontSize=9, letterSpacing=2.5, color=C["muted"],
                                     textTransform="uppercase", marginBottom=10, fontFamily=C["sans"]))

def kpi(label, value, sub="", color=C["sky"], width=140):
    return html.Div([
        html.Div(label, style=dict(fontSize=9, letterSpacing=2, color=C["muted"],
                                   textTransform="uppercase", marginBottom=5, fontFamily=C["sans"])),
        html.Div(value, style=dict(fontSize=22, fontWeight=700, color=color, fontFamily=C["mono"])),
        html.Div(sub,   style=dict(fontSize=10, color=C["dim"], marginTop=3, fontFamily=C["sans"])),
    ], style=dict(background=C["surface"], border=f"1px solid {C['border']}",
                  borderRadius=8, padding="14px 18px", minWidth=width))

# ── Layout ────────────────────────────────────────────────────────────────────

app.layout = html.Div([
    dcc.Store(id="allocated-store", data=SEED_ALLOCATED),
    dcc.Store(id="pipeline-store",  data=SEED_PIPELINE),
    dcc.Store(id="next-id",         data=50),

    # ── Header ──────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div([
                html.Span("EVERGREEN CREDIT", style=dict(fontSize=18, fontWeight=700,
                          color=C["text"], fontFamily=C["sans"], letterSpacing=1)),
                html.Span(" · ", style=dict(color=C["dim"], margin="0 6px")),
                html.Span("Portfolio Construction", style=dict(fontSize=18, fontWeight=300,
                          color=C["muted"], fontFamily=C["sans"])),
            ]),
            html.Div([
                pill("Secondaries", C["blue"]),
                html.Span(" ", style=dict(marginLeft=6)),
                pill("Co-Investment", C["purple"]),
                html.Span(" ", style=dict(marginLeft=6)),
                pill("Evergreen", C["teal"]),
            ], style=dict(marginTop=8)),
        ]),
        html.Div([
            html.Div([
                html.Label("Fund Size ($M)", style=dict(fontSize=9, color=C["muted"],
                           letterSpacing=2, display="block", marginBottom=4, textTransform="uppercase")),
                dcc.Input(id="fund-size", type="number", value=200, min=1,
                          style={**INP, width:100}),
            ]),
            html.Div([
                html.Label("Target Net TWR (%)", style=dict(fontSize=9, color=C["muted"],
                           letterSpacing=2, display="block", marginBottom=4, textTransform="uppercase")),
                dcc.Input(id="target-twr", type="number", value=10, min=0, step=0.5,
                          style={**INP, width:100}),
            ]),
            html.Div([
                html.Label("Fee Drag (% p.a.)", style=dict(fontSize=9, color=C["muted"],
                           letterSpacing=2, display="block", marginBottom=4, textTransform="uppercase")),
                dcc.Input(id="fee-drag", type="number", value=1.5, min=0, step=0.1,
                          style={**INP, width:100}),
            ]),
            html.Div([
                html.Label("Target Duration (y)", style=dict(fontSize=9, color=C["muted"],
                           letterSpacing=2, display="block", marginBottom=4, textTransform="uppercase")),
                dcc.Input(id="target-duration", type="number", value=4.0, min=0.5, step=0.5,
                          style={**INP, width:100}),
            ]),
            html.Div([
                html.Label("Recycling Rate (%)", style=dict(fontSize=9, color=C["muted"],
                           letterSpacing=2, display="block", marginBottom=4, textTransform="uppercase")),
                dcc.Input(id="recycling-rate", type="number", value=70, min=0, max=100, step=5,
                          style={**INP, width:100}),
            ]),
        ], style=dict(display="flex", gap=12, alignItems="flex-end", flexWrap="wrap")),
    ], style=dict(background="#070c13", borderBottom=f"1px solid {C['border']}",
                  padding="22px 36px", display="flex", justifyContent="space-between",
                  alignItems="center", flexWrap="wrap", gap=16)),

    # ── KPI Strip ───────────────────────────────────────────────────────────
    html.Div(id="kpi-strip",
             style=dict(padding="16px 36px", display="flex", gap=10, flexWrap="wrap")),

    # ── Tabs ────────────────────────────────────────────────────────────────
    html.Div([
        dcc.Tabs(id="tabs", value="allocated",
            children=[
                dcc.Tab(label="📂  Allocated Portfolio", value="allocated"),
                dcc.Tab(label="🔭  Deal Pipeline",        value="pipeline"),
                dcc.Tab(label="📈  IRR & Return Targets", value="irr"),
                dcc.Tab(label="♻️   Evergreen Pacing",    value="pacing"),
                dcc.Tab(label="⏱   Duration Analysis",   value="duration"),
            ],
            colors=dict(border=C["border"], primary=C["blue"], background=C["bg"]),
            style=dict(fontFamily=C["sans"]),
        ),
    ], style=dict(padding="0 36px", borderBottom=f"1px solid {C['border']}")),

    html.Div(id="tab-content", style=dict(padding="24px 36px 60px")),

], style=dict(background=C["bg"], minHeight="100vh",
              fontFamily=C["sans"], color=C["text"]))


# ── KPI Strip ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("kpi-strip","children"),
    Input("allocated-store","data"), Input("pipeline-store","data"),
    Input("fund-size","value"), Input("target-twr","value"),
    Input("fee-drag","value"),
)
def update_kpis(alloc, pipe, fund_size, twr, fee_drag):
    fund_size = fund_size or 200; twr = twr or 10; fee_drag = fee_drag or 0

    total_alloc = sum(d["commitment"] for d in alloc)
    total_pipe  = sum(d["commitment"] for d in pipe)
    util = total_alloc / fund_size * 100 if fund_size else 0

    wal = weighted_avg_life(alloc) if alloc else None
    dur = portfolio_duration(alloc, twr) if alloc else None

    # Weighted portfolio TWR
    port_ann = None
    if alloc:
        total = sum(d["commitment"] for d in alloc)
        if total:
            ws = sum((ann_return_from_moic(d["moic"],d["hold_years"]) or 0)*d["commitment"] for d in alloc)
            port_ann = ws / total

    req_gross_irr = twr + fee_drag
    on_target = sum(1 for d in alloc if (ann_return_from_moic(d["moic"],d["hold_years"]) or 0) >= twr)

    twr_color = C["green"] if port_ann and port_ann >= twr else C["red"]
    util_color = C["amber"] if util > 85 else (C["red"] if util > 100 else C["sky"])

    return [
        kpi("Portfolio TWR", f"{port_ann:.1f}%" if port_ann else "—",
            f"Target: {twr}%", twr_color),
        kpi("Deployed NAV", f"${total_alloc:.0f}M",
            f"{util:.1f}% of ${fund_size:.0f}M fund", util_color),
        kpi("Pipeline", f"${total_pipe:.0f}M",
            f"{len(pipe)} deals pending", C["purple"]),
        kpi("Req. Gross IRR", f"{req_gross_irr:.1f}%",
            f"Net TWR {twr}% + {fee_drag}% fees", C["amber"]),
        kpi("Wtd Avg Life", f"{wal:.1f}y" if wal else "—",
            "allocated portfolio", C["teal"]),
        kpi("Mod. Duration", f"{dur:.2f}y" if dur else "—",
            "allocated portfolio", C["teal"]),
        kpi("On-Target Deals", f"{on_target}/{len(alloc)}",
            f"≥{twr}% p.a. net TWR", C["green"] if on_target==len(alloc) else C["red"]),
    ]


# ── Tab Router ────────────────────────────────────────────────────────────────

@app.callback(
    Output("tab-content","children"),
    Input("tabs","value"),
    Input("allocated-store","data"), Input("pipeline-store","data"),
    Input("fund-size","value"), Input("target-twr","value"),
    Input("fee-drag","value"), Input("target-duration","value"),
    Input("recycling-rate","value"),
)
def route_tab(tab, alloc, pipe, fund_size, twr, fee_drag, target_dur, recycling):
    fund_size    = fund_size    or 200
    twr          = twr          or 10
    fee_drag     = fee_drag     or 1.5
    target_dur   = target_dur   or 4.0
    recycling    = (recycling   or 70) / 100

    if tab == "allocated": return tab_allocated(alloc, twr, fee_drag, fund_size)
    if tab == "pipeline":  return tab_pipeline(pipe, alloc, twr, fee_drag)
    if tab == "irr":       return tab_irr(alloc, pipe, twr, fee_drag)
    if tab == "pacing":    return tab_pacing(alloc, pipe, fund_size, twr, recycling)
    if tab == "duration":  return tab_duration(alloc, pipe, twr, target_dur, fund_size)
    return html.Div()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Allocated Portfolio
# ══════════════════════════════════════════════════════════════════════════════

def tab_allocated(alloc, twr, fee_drag, fund_size):
    req_gross = twr + fee_drag
    rows = []
    total = sum(d["commitment"] for d in alloc)
    for d in alloc:
        ann  = ann_return_from_moic(d["moic"], d["hold_years"])
        irr  = calc_irr_newton(d["commitment"], d["moic"], d["hold_years"])
        req_m= required_moic_for_twr(d["hold_years"], twr)
        w    = d["commitment"]/total*100 if total else 0
        rows.append({
            "Deal": d["name"],
            "Type": d["type"],
            "Sector": d["sector"],
            "$M Committed": f"${d['commitment']:.1f}M",
            "Weight": f"{w:.1f}%",
            "MOIC": f"{d['moic']:.2f}x",
            "Hold (y)": f"{d['hold_years']:.1f}",
            "Deal IRR": f"{irr:.1f}%" if irr else "—",
            "Req. IRR": f"{req_gross:.1f}%",
            "Ann. Return": f"{ann:.1f}%" if ann else "—",
            "Req. MOIC": f"{req_m:.2f}x",
            "Status": "✓ On Target" if ann and ann >= twr else "✗ Below",
        })

    # Add deal form
    form = html.Div([
        section_lbl("Add Allocated Deal"),
        html.Div([
            _field("Deal Name",    dcc.Input(id="a-name", type="text", placeholder="Name…",      style=INP)),
            _field("Type",         dcc.Dropdown(id="a-type", options=TYPES, value="Secondary",    style=_dd())),
            _field("Sector",       dcc.Dropdown(id="a-sector", options=SECTORS, value=SECTORS[0], style=_dd())),
            _field("Commit ($M)",  dcc.Input(id="a-commit", type="number", value=10, min=0.1,     style=INP)),
            _field("MOIC",         dcc.Input(id="a-moic", type="number", value=1.5, step=0.01,    style=INP)),
            _field("Hold (y)",     dcc.Input(id="a-hold", type="number", value=3, step=0.5,       style=INP)),
            _field("Deploy Q",     dcc.Input(id="a-dq", type="number", value=1, min=1, max=20,    style=INP)),
            _field("Deploy %",     dcc.Input(id="a-dr", type="number", value=100, min=0, max=100, style=INP)),
            html.Div([
                html.Label(" ", style=dict(fontSize=9, display="block", marginBottom=4)),
                html.Button("+ Allocate", id="add-alloc-btn", style={**BTN(C["blue"]), width:"100%"}),
            ]),
        ], style=dict(display="grid",
                      gridTemplateColumns="2fr 1fr 1.2fr 1fr 1fr 1fr 0.8fr 0.8fr auto",
                      gap=8, alignItems="end")),
        html.Div(id="alloc-msg", style=dict(marginTop=6, fontSize=11, color=C["green"])),
    ], style=dict(background=C["surface"], border=f"1px solid {cl(C['blue'],0.4)}",
                  borderRadius=8, padding=18, marginBottom=18))

    tbl = dash_table.DataTable(
        id="alloc-table",
        columns=[{"name":c,"id":c} for c in rows[0]] if rows else [],
        data=rows,
        style_cell=TBL_CELL,
        style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD + [
            {"if":{"filter_query":'{Status} = "✓ On Target"',"column_id":"Status"},
             "color":C["green"],"fontWeight":700},
            {"if":{"filter_query":'{Status} = "✗ Below"',"column_id":"Status"},
             "color":C["red"],"fontWeight":700},
        ],
        sort_action="native", page_size=15,
        style_table={"overflowX":"auto"},
    ) if rows else html.Div("No allocated deals yet.", style=dict(color=C["muted"], padding=20))

    # Composition donut
    type_vals  = {}
    for d in alloc: type_vals[d["type"]] = type_vals.get(d["type"],0) + d["commitment"]
    sec_vals = {}
    for d in alloc: sec_vals[d["sector"]] = sec_vals.get(d["sector"],0) + d["commitment"]

    fig = make_subplots(1,2, specs=[[{"type":"domain"},{"type":"domain"}]],
                        subplot_titles=["By Strategy","By Sector"])
    fig.add_trace(go.Pie(labels=list(type_vals.keys()), values=list(type_vals.values()),
                          hole=0.58, marker_colors=[C["blue"],C["purple"]],
                          textfont_color=C["text"]), 1, 1)
    fig.add_trace(go.Pie(labels=list(sec_vals.keys()), values=list(sec_vals.values()),
                          hole=0.58,
                          marker_colors=["#2979c8","#2ec4b6","#9b72cf","#e05c8a",
                                         "#f0a500","#2ecc71","#e5493a","#56b4f5"],
                          textfont_color=C["text"]), 1, 2)
    fig.update_layout(**CHART, height=260,
                      legend=dict(bgcolor=C["panel"],bordercolor=C["border"],font_color=C["muted"]))

    return html.Div([
        form,
        html.Div([
            html.Div(tbl, style=dict(flex=3, overflowX="auto")),
            html.Div(dcc.Graph(figure=fig, config={"displayModeBar":False}),
                     style=dict(flex=2, background=C["panel"], border=f"1px solid {C['border']}",
                                borderRadius=8, minWidth=320)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Deal Pipeline
# ══════════════════════════════════════════════════════════════════════════════

def tab_pipeline(pipe, alloc, twr, fee_drag):
    req_gross = twr + fee_drag
    stage_order = {s:i for i,s in enumerate(STAGES)}
    prio_color  = {"High":C["red"],"Medium":C["amber"],"Low":C["green"]}

    rows = []
    for d in pipe:
        ann = ann_return_from_moic(d["moic"], d["hold_years"])
        irr = calc_irr_newton(d["commitment"], d["moic"], d["hold_years"])
        req_m = required_moic_for_twr(d["hold_years"], twr)
        rows.append({
            "ID": d["id"],
            "Deal": d["name"],
            "Type": d["type"],
            "Sector": d["sector"],
            "Stage": d.get("pipeline_stage","Screening"),
            "Priority": d.get("priority","Medium"),
            "$M": f"${d['commitment']:.1f}M",
            "MOIC": f"{d['moic']:.2f}x",
            "Hold (y)": f"{d['hold_years']:.1f}",
            "Deal IRR": f"{irr:.1f}%" if irr else "—",
            "Req. Gross IRR": f"{req_gross:.1f}%",
            "Exp. Ann. Return": f"{ann:.1f}%" if ann else "—",
            "Req. MOIC": f"{req_m:.2f}x",
            "vs Target": ("✓ Meets" if ann and ann >= twr else "✗ Miss"),
        })

    # Funnel by stage
    stage_caps = {s: sum(d["commitment"] for d in pipe if d.get("pipeline_stage")==s) for s in STAGES}
    funnel_fig = go.Figure(go.Funnel(
        y=STAGES,
        x=[stage_caps.get(s,0) for s in STAGES],
        textinfo="value+percent initial",
        marker_color=[C["blue"],C["teal"],C["amber"],C["purple"],C["green"]],
        textfont=dict(color=C["text"]),
        connector=dict(line=dict(color=C["border"], width=1)),
    ))
    funnel_fig.update_layout(**CHART, height=300, title="Pipeline Funnel by Committed ($M)")

    # Add pipeline deal form
    form = html.Div([
        section_lbl("Add Pipeline Deal"),
        html.Div([
            _field("Deal Name",  dcc.Input(id="p-name", type="text", placeholder="Name…",       style=INP)),
            _field("Type",       dcc.Dropdown(id="p-type", options=TYPES, value="Secondary",     style=_dd())),
            _field("Sector",     dcc.Dropdown(id="p-sector", options=SECTORS, value=SECTORS[0],  style=_dd())),
            _field("Stage",      dcc.Dropdown(id="p-stage", options=STAGES, value="Screening",   style=_dd())),
            _field("Priority",   dcc.Dropdown(id="p-priority", options=PRIOS, value="Medium",    style=_dd())),
            _field("$M",         dcc.Input(id="p-commit", type="number", value=10, min=0.1,      style=INP)),
            _field("MOIC",       dcc.Input(id="p-moic", type="number", value=1.5, step=0.01,     style=INP)),
            _field("Hold (y)",   dcc.Input(id="p-hold", type="number", value=3, step=0.5,        style=INP)),
            _field("Deploy Q",   dcc.Input(id="p-dq", type="number", value=4, min=1, max=20,     style=INP)),
            html.Div([
                html.Label(" ", style=dict(fontSize=9, display="block", marginBottom=4)),
                html.Button("+ Add to Pipeline", id="add-pipe-btn",
                            style={**BTN(C["purple"]), width:"100%"}),
            ]),
        ], style=dict(display="grid",
                      gridTemplateColumns="2fr 1fr 1.2fr 1fr 1fr 1fr 1fr 1fr 0.8fr auto",
                      gap=8, alignItems="end")),
        html.Div(id="pipe-msg", style=dict(marginTop=6, fontSize=11, color=C["green"])),
    ], style=dict(background=C["surface"], border=f"1px solid {cl(C['purple'],0.4)}",
                  borderRadius=8, padding=18, marginBottom=18))

    tbl = dash_table.DataTable(
        columns=[{"name":c,"id":c} for c in rows[0] if c!="ID"] if rows else [],
        data=[{k:v for k,v in r.items() if k!="ID"} for r in rows],
        style_cell=TBL_CELL,
        style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD + [
            {"if":{"filter_query":'{vs Target} = "✓ Meets"',"column_id":"vs Target"},
             "color":C["green"],"fontWeight":700},
            {"if":{"filter_query":'{vs Target} = "✗ Miss"',"column_id":"vs Target"},
             "color":C["red"],"fontWeight":700},
            {"if":{"filter_query":'{Priority} = "High"',"column_id":"Priority"},
             "color":C["red"],"fontWeight":700},
            {"if":{"filter_query":'{Priority} = "Medium"',"column_id":"Priority"},
             "color":C["amber"]},
            {"if":{"filter_query":'{Priority} = "Low"',"column_id":"Priority"},
             "color":C["green"]},
        ],
        sort_action="native", page_size=10,
        style_table={"overflowX":"auto"},
    ) if rows else html.Div("Pipeline is empty.", style=dict(color=C["muted"], padding=20))

    return html.Div([
        form,
        html.Div([
            html.Div(tbl, style=dict(flex=3)),
            html.Div(dcc.Graph(figure=funnel_fig, config={"displayModeBar":False}),
                     style=dict(flex=2, background=C["panel"], border=f"1px solid {C['border']}",
                                borderRadius=8, minWidth=300)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IRR & Return Targets
# ══════════════════════════════════════════════════════════════════════════════

def tab_irr(alloc, pipe, twr, fee_drag):
    req_gross = twr + fee_drag
    all_deals = [dict(**d, pool="Allocated") for d in alloc] + \
                [dict(**d, pool="Pipeline") for d in pipe]

    # Required MOIC table across hold periods
    hold_range = [1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,7.0]
    req_rows = []
    for h in hold_range:
        rmoic = required_moic_for_twr(h, twr)
        near = [d["name"].split()[-1] for d in all_deals if abs(d["hold_years"]-h)<0.3]
        req_rows.append({
            "Hold (y)": f"{h:.1f}",
            f"Req. MOIC (Net {twr}%)": f"{rmoic:.3f}x",
            f"Req. Gross MOIC (+{fee_drag}% fees)": f"{required_moic_for_twr(h, req_gross):.3f}x",
            "Deals Near": ", ".join(near) or "—",
        })

    req_tbl = dash_table.DataTable(
        columns=[{"name":c,"id":c} for c in req_rows[0]],
        data=req_rows,
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD,
        style_table={"overflowX":"auto"},
    )

    # IRR scatter: deal IRR vs required gross IRR
    fig_scatter = go.Figure()
    for pool, color in [("Allocated", C["blue"]), ("Pipeline", C["purple"])]:
        ds = [d for d in all_deals if d["pool"]==pool]
        if not ds: continue
        irrs = [calc_irr_newton(d["commitment"], d["moic"], d["hold_years"]) or 0 for d in ds]
        names = [d["name"] for d in ds]
        sizes = [d["commitment"]*1.5 for d in ds]
        fig_scatter.add_trace(go.Scatter(
            x=[d["hold_years"] for d in ds], y=irrs,
            mode="markers+text", name=pool,
            marker=dict(color=color, size=sizes, opacity=0.8, line=dict(color=C["border"],width=1)),
            text=[n.split()[-1] for n in names], textposition="top center",
            textfont=dict(color=C["text"], size=9),
            hovertext=[f"{n}<br>IRR: {i:.1f}%<br>${d['commitment']:.0f}M" for n,i,d in zip(names,irrs,ds)],
            hoverinfo="text",
        ))
    # Required IRR line
    xs = [0.5, 8]
    fig_scatter.add_trace(go.Scatter(
        x=xs, y=[req_gross]*2, mode="lines", name=f"Req. Gross IRR ({req_gross:.1f}%)",
        line=dict(color=C["amber"], dash="dash", width=2),
    ))
    fig_scatter.add_trace(go.Scatter(
        x=xs, y=[twr]*2, mode="lines", name=f"Net TWR Target ({twr:.1f}%)",
        line=dict(color=C["teal"], dash="dot", width=1.5),
    ))
    fig_scatter.update_layout(**CHART, height=380, title="Deal IRR vs Hold Period",
                              xaxis_title="Hold Period (y)", yaxis_title="IRR (%)",
                              legend=dict(bgcolor=C["panel"],bordercolor=C["border"]))

    # Return gap bars
    gap_labels, gap_vals, gap_colors, gap_pools = [], [], [], []
    for d in all_deals:
        ann = ann_return_from_moic(d["moic"], d["hold_years"])
        if ann is None: continue
        gap_labels.append(d["name"].split()[:2])
        gap_vals.append(round(ann - twr, 2))
        gap_colors.append(C["green"] if ann >= twr else C["red"])
        gap_pools.append(d["pool"])

    gap_labels = [" ".join(l) for l in gap_labels]
    fig_gap = go.Figure(go.Bar(
        x=gap_labels, y=gap_vals,
        marker_color=gap_colors,
        text=[f"{v:+.1f}%" for v in gap_vals], textposition="outside",
        textfont=dict(color=C["text"]),
    ))
    fig_gap.add_hline(y=0, line_color=C["muted"], line_width=1.5)
    fig_gap.update_layout(**CHART, height=320,
                          title=f"Return Gap vs {twr}% Net TWR Target (all deals)",
                          yaxis_title="Gap (pp)")

    return html.Div([
        html.Div([
            card([section_lbl(f"Required MOIC by Hold Period  ·  Net TWR {twr}%  ·  Gross IRR {req_gross:.1f}%"),
                  req_tbl], dict(flex=2)),
            card([section_lbl("Key Thresholds"),
                  kpi("Required Net TWR",   f"{twr:.1f}%",     "annualised",     C["teal"],  120),
                  html.Div(style=dict(height=10)),
                  kpi("Required Gross IRR", f"{req_gross:.1f}%", f"net + {fee_drag}% fees", C["amber"], 120),
                  html.Div(style=dict(height=10)),
                  kpi("Gross MOIC @ 3y",    f"{required_moic_for_twr(3,req_gross):.2f}x", "gross", C["sky"], 120),
                  html.Div(style=dict(height=10)),
                  kpi("Gross MOIC @ 5y",    f"{required_moic_for_twr(5,req_gross):.2f}x", "gross", C["sky"], 120),
                  ], dict(flex=1, minWidth=200)),
        ], style=dict(display="flex", gap=16, marginBottom=16, flexWrap="wrap")),
        card([dcc.Graph(figure=fig_scatter, config={"displayModeBar":False})], dict(marginBottom=16)),
        card([dcc.Graph(figure=fig_gap, config={"displayModeBar":False})]),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Evergreen Pacing
# ══════════════════════════════════════════════════════════════════════════════

def tab_pacing(alloc, pipe, fund_size, twr, recycling):
    all_deals = alloc + pipe
    avg_hold  = weighted_avg_life(all_deals) or 3.5
    target_util = 0.85  # target 85% utilisation

    df = evergreen_deployment_schedule(fund_size, target_util, recycling, avg_hold,
                                       deals_per_year=4, quarters=24)

    # Stacked bar: new deploy + recycled
    fig_deploy = go.Figure()
    fig_deploy.add_trace(go.Bar(x=df["label"], y=df["new_deploy"], name="New Capital",
                                 marker_color=C["blue"], opacity=0.9))
    fig_deploy.add_trace(go.Bar(x=df["label"], y=df["recycled"], name="Recycled Capital",
                                 marker_color=C["teal"], opacity=0.9))
    fig_deploy.add_trace(go.Scatter(x=df["label"], y=df["nav"], name="NAV",
                                     line=dict(color=C["amber"], width=2.5),
                                     yaxis="y2", mode="lines+markers",
                                     marker=dict(size=5)))
    fig_deploy.update_layout(
        **CHART, barmode="stack", height=380,
        title="Evergreen Deployment — New Capital + Recycling vs NAV",
        yaxis=dict(title="Quarterly Deployment ($M)", gridcolor=C["border"]),
        yaxis2=dict(title="NAV ($M)", overlaying="y", side="right",
                    gridcolor="transparent", color=C["amber"]),
        legend=dict(bgcolor=C["panel"], bordercolor=C["border"]),
    )

    # Utilisation line
    fig_util = go.Figure()
    fig_util.add_trace(go.Scatter(x=df["label"], y=df["utilisation"],
                                   fill="tozeroy", fillcolor=cl(C["blue"],0.15),
                                   line=dict(color=C["blue"], width=2), name="Utilisation %"))
    fig_util.add_hline(y=85, line_dash="dash", line_color=C["amber"],
                        annotation_text="85% target", annotation_font_color=C["amber"])
    fig_util.add_hline(y=100, line_dash="dot", line_color=C["red"],
                        annotation_text="100%", annotation_font_color=C["red"])
    fig_util.update_layout(**CHART, height=260, title="NAV Utilisation Over Time (%)",
                            yaxis=dict(title="%", range=[0,115], gridcolor=C["border"]))

    # Deal-level commitment pacing from actual deals
    q_labels = [f"Q{((q-1)%4)+1} Y{math.ceil(q/4)}" for q in range(1,17)]
    alloc_by_q = {q:0 for q in range(1,17)}
    pipe_by_q  = {q:0 for q in range(1,17)}
    for d in alloc:
        q = min(16, max(1, d["deploy_q"]))
        alloc_by_q[q] += d["commitment"]
    for d in pipe:
        q = min(16, max(1, d["deploy_q"]))
        pipe_by_q[q]  += d["commitment"]

    fig_deals = go.Figure()
    fig_deals.add_trace(go.Bar(x=q_labels, y=[alloc_by_q[q] for q in range(1,17)],
                                name="Allocated", marker_color=C["blue"]))
    fig_deals.add_trace(go.Bar(x=q_labels, y=[pipe_by_q[q] for q in range(1,17)],
                                name="Pipeline", marker_color=C["purple"], opacity=0.7))
    fig_deals.update_layout(**CHART, barmode="stack", height=280,
                             title="Actual Deal Pacing — Allocated + Pipeline ($M committed)",
                             yaxis=dict(title="$M", gridcolor=C["border"]))

    tbl_df = df[["label","new_deploy","recycled","total_deploy","repayments",
                 "nav","utilisation","cumulative_deployed"]].head(16).copy()
    tbl_df.columns = ["Period","New ($M)","Recycled ($M)","Total Deploy ($M)",
                       "Repayments ($M)","NAV ($M)","Util %","Cum. Deployed ($M)"]
    for col in ["New ($M)","Recycled ($M)","Total Deploy ($M)","Repayments ($M)","NAV ($M)","Cum. Deployed ($M)"]:
        tbl_df[col] = tbl_df[col].apply(lambda x: f"${x:.1f}M")
    tbl_df["Util %"] = tbl_df["Util %"].apply(lambda x: f"{x:.1f}%")

    pacing_tbl = dash_table.DataTable(
        columns=[{"name":c,"id":c} for c in tbl_df.columns],
        data=tbl_df.to_dict("records"),
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD,
        style_table={"overflowX":"auto"},
    )

    return html.Div([
        card([dcc.Graph(figure=fig_deploy, config={"displayModeBar":False})], dict(marginBottom=16)),
        html.Div([
            card([dcc.Graph(figure=fig_util, config={"displayModeBar":False})], dict(flex=1)),
            card([dcc.Graph(figure=fig_deals, config={"displayModeBar":False})], dict(flex=1)),
        ], style=dict(display="flex", gap=16, marginBottom=16, flexWrap="wrap")),
        card([section_lbl(f"Quarterly Pacing Schedule  ·  Avg Hold {avg_hold:.1f}y  ·  Recycling {recycling*100:.0f}%"),
              pacing_tbl]),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Duration Analysis
# ══════════════════════════════════════════════════════════════════════════════

def tab_duration(alloc, pipe, twr, target_dur, fund_size):
    all_deals = [dict(**d, pool="Allocated") for d in alloc] + \
                [dict(**d, pool="Pipeline") for d in pipe]

    wal_alloc = weighted_avg_life(alloc) or 0
    dur_alloc = portfolio_duration(alloc, twr) or 0
    wal_all   = weighted_avg_life(all_deals) or 0
    dur_all   = portfolio_duration(all_deals, twr) or 0

    wal_gap_alloc = target_dur - wal_alloc
    dur_gap_alloc = (target_dur/(1+twr/100)) - dur_alloc
    wal_gap_all   = target_dur - wal_all

    # Duration required by deal
    rows = []
    for d in all_deals:
        ann  = ann_return_from_moic(d["moic"], d["hold_years"])
        mdur = d["hold_years"] / (1 + twr/100)
        contrib = mdur * d["commitment"] / (sum(x["commitment"] for x in all_deals) or 1)
        rows.append({
            "Deal": d["name"],
            "Pool": d["pool"],
            "Type": d["type"],
            "$M": f"${d['commitment']:.1f}M",
            "Hold (y)": f"{d['hold_years']:.1f}",
            "Mod. Duration (y)": f"{mdur:.2f}",
            "Duration Contrib (y)": f"{contrib:.3f}",
            "Ann. Return": f"{ann:.1f}%" if ann else "—",
        })

    dur_tbl = dash_table.DataTable(
        columns=[{"name":c,"id":c} for c in rows[0]] if rows else [],
        data=rows,
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD + [
            {"if":{"filter_query":'{Pool} = "Allocated"',"column_id":"Pool"},
             "color":C["sky"],"fontWeight":600},
            {"if":{"filter_query":'{Pool} = "Pipeline"',"column_id":"Pool"},
             "color":C["purple"],"fontWeight":600},
        ],
        sort_action="native",
        style_table={"overflowX":"auto"},
    ) if rows else html.Div("No deals.", style=dict(color=C["muted"],padding=20))

    # Duration waterfall / bar comparison
    categories = ["Allocated\nPortfolio","Allocated +\nPipeline","Target\nDuration"]
    wal_vals   = [wal_alloc, wal_all, target_dur]
    dur_vals   = [dur_alloc, dur_all, target_dur/(1+twr/100)]
    colors_wal = [C["blue"],C["purple"],C["teal"]]

    fig_dur = go.Figure()
    fig_dur.add_trace(go.Bar(x=categories, y=wal_vals, name="WAL (y)",
                              marker_color=colors_wal, opacity=0.85,
                              text=[f"{v:.2f}y" for v in wal_vals], textposition="outside",
                              textfont_color=C["text"]))
    fig_dur.add_trace(go.Bar(x=categories, y=dur_vals, name="Mod. Duration (y)",
                              marker_color=[cl(c,0.5) for c in colors_wal], opacity=0.9,
                              text=[f"{v:.2f}y" for v in dur_vals], textposition="inside",
                              textfont_color=C["text"]))
    fig_dur.add_hline(y=target_dur, line_dash="dash", line_color=C["amber"],
                       annotation_text=f"Target WAL {target_dur}y",
                       annotation_font_color=C["amber"])
    fig_dur.update_layout(**CHART, barmode="group", height=340,
                           title="Weighted Average Life & Modified Duration",
                           yaxis=dict(title="Years", gridcolor=C["border"]))

    # Duration contribution by deal (horizontal bar)
    total_commit = sum(d["commitment"] for d in all_deals) or 1
    dur_contribs = [(d["name"].split()[-1],
                     (d["hold_years"]/(1+twr/100)) * d["commitment"]/total_commit,
                     C["blue"] if d["pool"]=="Allocated" else C["purple"])
                    for d in all_deals]
    dur_contribs.sort(key=lambda x: x[1], reverse=True)

    fig_contrib = go.Figure(go.Bar(
        y=[x[0] for x in dur_contribs],
        x=[x[1] for x in dur_contribs],
        orientation="h",
        marker_color=[x[2] for x in dur_contribs],
        text=[f"{x[1]:.3f}y" for x in dur_contribs],
        textposition="outside", textfont_color=C["text"],
    ))
    fig_contrib.update_layout(**CHART, height=max(220, len(dur_contribs)*34+80),
                               title="Duration Contribution by Deal (y)",
                               xaxis_title="Modified Duration Contribution (y)",
                               margin=dict(l=80, r=40, t=38, b=38))

    # How much more duration needed?
    deals_needed_wal = math.ceil(wal_gap_alloc / (wal_alloc if wal_alloc else 1)) if wal_gap_alloc > 0 else 0

    return html.Div([
        # Summary cards
        html.Div([
            kpi("WAL — Allocated",        f"{wal_alloc:.2f}y",  f"Target {target_dur:.1f}y", C["blue"]),
            kpi("WAL — Alloc + Pipeline", f"{wal_all:.2f}y",    f"Gap {wal_gap_all:+.2f}y",
                C["green"] if wal_gap_all >= 0 else C["amber"]),
            kpi("Mod. Duration — Alloc",  f"{dur_alloc:.2f}y",  f"= WAL/(1+{twr}%)",         C["teal"]),
            kpi("WAL Gap (Alloc)",        f"{wal_gap_alloc:+.2f}y", "vs target",
                C["green"] if wal_gap_alloc >= 0 else C["red"]),
            kpi("Dur. Gap (Alloc)",       f"{dur_gap_alloc:+.2f}y", "mod. duration gap",
                C["green"] if dur_gap_alloc >= 0 else C["red"]),
        ], style=dict(display="flex", gap=10, flexWrap="wrap", marginBottom=16)),

        html.Div([
            card([dcc.Graph(figure=fig_dur,    config={"displayModeBar":False})], dict(flex=3)),
            card([dcc.Graph(figure=fig_contrib,config={"displayModeBar":False})], dict(flex=2)),
        ], style=dict(display="flex", gap=16, marginBottom=16, flexWrap="wrap")),

        card([
            section_lbl("Duration Detail by Deal"),
            dur_tbl,
        ]),

        # Duration prescription
        html.Div([
            html.Div("🔬  Duration Prescription", style=dict(fontSize=11, color=C["muted"],
                     fontWeight=600, marginBottom=10, letterSpacing=1)),
            html.Div([
                _insight(f"Current allocated WAL is {wal_alloc:.1f}y vs {target_dur:.1f}y target — "
                         f"gap of {wal_gap_alloc:+.1f}y.",
                         C["amber"] if abs(wal_gap_alloc)>0.5 else C["green"]),
                _insight(f"Including pipeline reduces gap to {wal_gap_all:+.1f}y.",
                         C["teal"] if abs(wal_gap_all)<abs(wal_gap_alloc) else C["amber"]),
                _insight(f"To extend duration: add longer-dated deals (>{ target_dur:.0f}y hold) "
                         f"or reduce short-tenor secondaries.",
                         C["sky"]),
                _insight(f"Required gross IRR {twr+1.5:.1f}% = {twr:.1f}% net TWR + 1.5% fee drag. "
                         f"At {target_dur:.1f}y WAL this implies gross MOIC of "
                         f"{required_moic_for_twr(target_dur, twr+1.5):.2f}x.",
                         C["purple"]),
            ]),
        ], style=dict(background=C["surface"], border=f"1px solid {C['border2']}",
                      borderRadius=8, padding=18, marginTop=16)),
    ])


# ── Callbacks: Add Allocated Deal ─────────────────────────────────────────────

@app.callback(
    Output("allocated-store","data"),
    Output("next-id","data"),
    Output("alloc-msg","children"),
    Input("add-alloc-btn","n_clicks"),
    State("allocated-store","data"), State("next-id","data"),
    State("a-name","value"), State("a-type","value"), State("a-sector","value"),
    State("a-commit","value"), State("a-moic","value"), State("a-hold","value"),
    State("a-dq","value"), State("a-dr","value"),
    prevent_initial_call=True,
)
def add_allocated(_, alloc, nid, name, dtype, sector, commit, moic, hold, dq, dr):
    if not name or not commit or not moic or not hold:
        return alloc, nid, "⚠ Fill all required fields."
    new = dict(id=nid, name=name, type=dtype or "Secondary",
               sector=sector or SECTORS[0], commitment=float(commit),
               moic=float(moic), hold_years=float(hold),
               deploy_q=int(dq or 1), deployment_rate=float(dr or 100),
               status="allocated")
    return alloc+[new], nid+1, f"✓ Allocated: {name}"


# ── Callbacks: Add Pipeline Deal ──────────────────────────────────────────────

@app.callback(
    Output("pipeline-store","data"),
    Output("next-id","data", allow_duplicate=True),
    Output("pipe-msg","children"),
    Input("add-pipe-btn","n_clicks"),
    State("pipeline-store","data"), State("next-id","data"),
    State("p-name","value"), State("p-type","value"), State("p-sector","value"),
    State("p-stage","value"), State("p-priority","value"),
    State("p-commit","value"), State("p-moic","value"), State("p-hold","value"),
    State("p-dq","value"),
    prevent_initial_call=True,
)
def add_pipeline(_, pipe, nid, name, dtype, sector, stage, prio, commit, moic, hold, dq):
    if not name or not commit or not moic or not hold:
        return pipe, nid, "⚠ Fill all required fields."
    new = dict(id=nid, name=name, type=dtype or "Secondary",
               sector=sector or SECTORS[0], pipeline_stage=stage or "Screening",
               priority=prio or "Medium", commitment=float(commit),
               moic=float(moic), hold_years=float(hold),
               deploy_q=int(dq or 4), deployment_rate=100,
               status="pipeline")
    return pipe+[new], nid+1, f"✓ Added to pipeline: {name}"


# ── Helpers ───────────────────────────────────────────────────────────────────

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

def _insight(text, color):
    return html.Div([
        html.Span("▸ ", style=dict(color=color, fontWeight=700)),
        html.Span(text, style=dict(fontSize=12, color=C["text"])),
    ], style=dict(marginBottom=8, lineHeight="1.6"))


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=8050)
