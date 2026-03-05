"""
Evergreen Credit Secondaries & Co-Investment Fund
Portfolio Construction Tool v2

Install:
    pip install dash plotly pandas

Run:
    python portfolio_tool_v2.py  →  http://127.0.0.1:8050
"""

import math
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go
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

def rgba(hex_color, alpha):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"

CHART_BASE = dict(
    paper_bgcolor=C["panel"], plot_bgcolor=C["surface"],
    font=dict(family=C["mono"], color=C["text"], size=11),
    margin=dict(l=52, r=24, t=40, b=40),
    xaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    yaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"]),
    legend=dict(bgcolor=C["panel"], bordercolor=C["border"], borderwidth=1),
)

# ── Finance helpers ───────────────────────────────────────────────────────────

def ann_return(moic, hold_y):
    if not hold_y or not moic or hold_y <= 0 or moic <= 0:
        return None
    return (moic ** (1.0 / hold_y) - 1.0) * 100.0

def req_moic(hold_y, twr_pct):
    return (1.0 + twr_pct / 100.0) ** hold_y

def calc_irr(commitment, moic, hold_y, guess=0.12):
    if hold_y <= 0 or commitment <= 0 or moic <= 0:
        return None
    cfs = [(-commitment, 0.0), (commitment * moic, float(hold_y))]
    r = guess
    for _ in range(300):
        f  = sum(cf / (1 + r) ** t for cf, t in cfs)
        df = sum(-t * cf / ((1 + r) ** (t + 1)) for cf, t in cfs)
        if abs(df) < 1e-14:
            break
        nr = r - f / df
        if abs(nr - r) < 1e-9:
            r = nr
            break
        r = max(-0.999, nr)
    return r * 100.0

def wal(deals):
    total = sum(d["commitment"] for d in deals)
    if not total:
        return None
    return sum(d["commitment"] * d["hold_years"] for d in deals) / total

def mod_duration(deals, twr_pct):
    w = wal(deals)
    if w is None:
        return None
    return w / (1.0 + twr_pct / 100.0)

def portfolio_twr(deals):
    total = sum(d["commitment"] for d in deals)
    if not total:
        return None
    ws = sum((ann_return(d["moic"], d["hold_years"]) or 0.0) * d["commitment"] for d in deals)
    return ws / total

def evergreen_schedule(fund_size, target_util, recycling_rate, avg_hold_y, quarters=24):
    rows = []
    nav = 0.0
    cum_deployed = 0.0
    q_hold = max(1.0, avg_hold_y * 4)

    for q in range(1, quarters + 1):
        yr  = math.ceil(q / 4)
        qtr = ((q - 1) % 4) + 1

        target_nav = fund_size * target_util
        new_deploy = max(0.0, (target_nav - nav) / max(1, q_hold / 2))
        new_deploy = min(new_deploy, fund_size / q_hold * 1.2)

        recycled = 0.0
        if q > q_hold:
            recycled = (nav * recycling_rate) / q_hold

        total_deploy = new_deploy + recycled
        repayments   = (nav / q_hold) if q > max(1, q_hold * 0.5) else 0.0
        nav          = max(0.0, nav + total_deploy - repayments)
        cum_deployed += total_deploy

        rows.append(dict(
            q=q, label=f"Q{qtr} Y{yr}",
            new_deploy=round(new_deploy, 2),
            recycled=round(recycled, 2),
            total_deploy=round(total_deploy, 2),
            repayments=round(repayments, 2),
            nav=round(nav, 2),
            utilisation=round(nav / fund_size * 100, 1) if fund_size else 0.0,
            cum_deployed=round(cum_deployed, 2),
        ))
    return pd.DataFrame(rows)

# ── Constants ─────────────────────────────────────────────────────────────────

SECTORS = ["Diversified Credit", "Healthcare", "TMT", "Infrastructure",
           "Structured Credit", "Consumer", "Real Assets", "Financial Services"]
TYPES  = ["Secondary", "Co-investment"]
STAGES = ["Screening", "Due Diligence", "Term Sheet", "IC Approved", "Closing"]
PRIOS  = ["High", "Medium", "Low"]

# ── Style helpers ─────────────────────────────────────────────────────────────

INP = dict(
    background=C["surface"], border=f"1px solid {C['border2']}",
    color=C["text"], borderRadius=6, padding="6px 10px",
    fontFamily=C["mono"], fontSize=12, outline="none", width="100%",
)

def btn_style(bg, fg="#fff"):
    return dict(background=bg, border="none", color=fg, borderRadius=6,
                padding="7px 16px", cursor="pointer", fontWeight=600,
                fontSize=12, fontFamily=C["sans"], letterSpacing=0.5, width="100%")

def tag_style(color):
    return dict(background=rgba(color, 0.15), border=f"1px solid {rgba(color, 0.4)}",
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
TBL_ODD  = [{"if": {"row_index": "odd"}, "backgroundColor": C["surface"]}]

def pill(text, color):
    return html.Span(text, style=tag_style(color))

def card(children, extra=None):
    s = dict(background=C["panel"], border=f"1px solid {C['border']}",
             borderRadius=10, padding=20)
    if extra:
        s.update(extra)
    return html.Div(children, style=s)

def sec_lbl(text):
    return html.Div(text, style=dict(fontSize=9, letterSpacing=2.5, color=C["muted"],
                                     textTransform="uppercase", marginBottom=10,
                                     fontFamily=C["sans"]))

def kpi_card(label, value, sub="", color=C["sky"], min_w=140):
    return html.Div([
        html.Div(label, style=dict(fontSize=9, letterSpacing=2, color=C["muted"],
                                   textTransform="uppercase", marginBottom=5,
                                   fontFamily=C["sans"])),
        html.Div(value, style=dict(fontSize=22, fontWeight=700, color=color,
                                   fontFamily=C["mono"])),
        html.Div(sub, style=dict(fontSize=10, color=C["dim"], marginTop=3,
                                 fontFamily=C["sans"])),
    ], style=dict(background=C["surface"], border=f"1px solid {C['border']}",
                  borderRadius=8, padding="14px 18px", minWidth=min_w))

def lbl(text):
    return html.Label(text, style=dict(fontSize=9, color=C["muted"], display="block",
                                       marginBottom=4, letterSpacing=1,
                                       textTransform="uppercase"))

def field(label_text, component):
    return html.Div([lbl(label_text), component])

def dd_style():
    return dict(backgroundColor=C["surface"], color=C["text"],
                border=f"1px solid {C['border2']}", borderRadius=6,
                fontFamily=C["mono"], fontSize=12)

def empty_state(msg):
    return html.Div(msg, style=dict(color=C["muted"], padding="40px 20px",
                                    textAlign="center", fontStyle="italic", fontSize=13))

def insight_row(text, color):
    return html.Div([
        html.Span("▸ ", style=dict(color=color, fontWeight=700)),
        html.Span(text, style=dict(fontSize=12, color=C["text"])),
    ], style=dict(marginBottom=8, lineHeight="1.6"))

# ── App ───────────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="Evergreen Credit Portfolio Tool",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width,initial-scale=1"}],
)

app.layout = html.Div([
    dcc.Store(id="alloc-store", data=[]),
    dcc.Store(id="pipe-store",  data=[]),
    dcc.Store(id="next-id",     data=1),

    # ── Header ──────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div([
                html.Span("EVERGREEN CREDIT", style=dict(
                    fontSize=18, fontWeight=700, color=C["text"],
                    fontFamily=C["sans"], letterSpacing=1)),
                html.Span(" · ", style=dict(color=C["dim"], margin="0 6px")),
                html.Span("Portfolio Construction", style=dict(
                    fontSize=18, fontWeight=300, color=C["muted"],
                    fontFamily=C["sans"])),
            ]),
            html.Div([
                pill("Secondaries", C["blue"]),
                html.Span("  "),
                pill("Co-Investment", C["purple"]),
                html.Span("  "),
                pill("Evergreen", C["teal"]),
            ], style=dict(marginTop=8)),
        ]),
        html.Div([
            field("Fund Size ($M)",
                  dcc.Input(id="fund-size", type="number", value=200, min=1,
                            style={**INP, "width": "110px"})),
            field("Target Net TWR (%)",
                  dcc.Input(id="target-twr", type="number", value=10.0, min=0, step=0.5,
                            style={**INP, "width": "110px"})),
            field("Fee Drag (% p.a.)",
                  dcc.Input(id="fee-drag", type="number", value=1.5, min=0, step=0.1,
                            style={**INP, "width": "110px"})),
            field("Target Duration (y)",
                  dcc.Input(id="target-dur", type="number", value=4.0, min=0.5, step=0.5,
                            style={**INP, "width": "110px"})),
            field("Recycling Rate (%)",
                  dcc.Input(id="recycling", type="number", value=70, min=0, max=100, step=5,
                            style={**INP, "width": "110px"})),
        ], style=dict(display="flex", gap=12, alignItems="flex-end", flexWrap="wrap")),
    ], style=dict(
        background="#070c13", borderBottom=f"1px solid {C['border']}",
        padding="22px 36px", display="flex", justifyContent="space-between",
        alignItems="center", flexWrap="wrap", gap=16)),

    # ── KPI strip ───────────────────────────────────────────────────────────
    html.Div(id="kpi-strip",
             style=dict(padding="16px 36px", display="flex", gap=10, flexWrap="wrap")),

    # ── Tabs ────────────────────────────────────────────────────────────────
    html.Div([
        dcc.Tabs(id="tabs", value="allocated", children=[
            dcc.Tab(label="📂  Allocated Portfolio",  value="allocated"),
            dcc.Tab(label="🔭  Deal Pipeline",         value="pipeline"),
            dcc.Tab(label="📈  IRR & Return Targets",  value="irr"),
            dcc.Tab(label="♻️   Evergreen Pacing",     value="pacing"),
            dcc.Tab(label="⏱   Duration Analysis",    value="duration"),
        ],
        colors=dict(border=C["border"], primary=C["blue"], background=C["bg"]),
        style=dict(fontFamily=C["sans"])),
    ], style=dict(padding="0 36px", borderBottom=f"1px solid {C['border']}")),

    html.Div(id="tab-content", style=dict(padding="24px 36px 60px")),

], style=dict(background=C["bg"], minHeight="100vh",
              fontFamily=C["sans"], color=C["text"]))


# ── KPI Strip ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("kpi-strip", "children"),
    Input("alloc-store", "data"),
    Input("pipe-store", "data"),
    Input("fund-size", "value"),
    Input("target-twr", "value"),
    Input("fee-drag", "value"),
)
def cb_kpis(alloc, pipe, fund_size, twr, fee_drag):
    fund_size = fund_size or 200
    twr       = twr       or 10
    fee_drag  = fee_drag  or 0

    total_alloc = sum(d["commitment"] for d in alloc)
    total_pipe  = sum(d["commitment"] for d in pipe)
    util        = total_alloc / fund_size * 100 if fund_size else 0
    port_t      = portfolio_twr(alloc) if alloc else None
    w_life      = wal(alloc) if alloc else None
    mdur        = mod_duration(alloc, twr) if alloc else None
    req_gross   = twr + fee_drag
    on_tgt      = sum(1 for d in alloc if (ann_return(d["moic"], d["hold_years"]) or 0) >= twr)

    twr_c  = C["green"] if port_t and port_t >= twr else C["red"]
    util_c = C["red"] if util > 100 else (C["amber"] if util > 85 else C["sky"])

    return [
        kpi_card("Portfolio TWR",   f"{port_t:.1f}%" if port_t else "—",
                 f"Target {twr}%", twr_c),
        kpi_card("Deployed NAV",    f"${total_alloc:.0f}M",
                 f"{util:.1f}% of ${fund_size:.0f}M", util_c),
        kpi_card("Pipeline",        f"${total_pipe:.0f}M",
                 f"{len(pipe)} deals pending", C["purple"]),
        kpi_card("Req. Gross IRR",  f"{req_gross:.1f}%",
                 f"net {twr}% + {fee_drag}% fees", C["amber"]),
        kpi_card("Wtd Avg Life",    f"{w_life:.1f}y" if w_life else "—",
                 "allocated", C["teal"]),
        kpi_card("Mod. Duration",   f"{mdur:.2f}y"   if mdur   else "—",
                 "allocated", C["teal"]),
        kpi_card("On-Target Deals", f"{on_tgt}/{len(alloc)}",
                 f"≥{twr}% net TWR",
                 C["green"] if (on_tgt == len(alloc) and alloc) else C["red"]),
    ]


# ── Tab Router ────────────────────────────────────────────────────────────────

@app.callback(
    Output("tab-content", "children"),
    Input("tabs", "value"),
    Input("alloc-store", "data"),
    Input("pipe-store", "data"),
    Input("fund-size", "value"),
    Input("target-twr", "value"),
    Input("fee-drag", "value"),
    Input("target-dur", "value"),
    Input("recycling", "value"),
)
def cb_route(tab, alloc, pipe, fund_size, twr, fee_drag, target_dur, recycling):
    fs  = fund_size  or 200
    t   = twr        or 10
    fd  = fee_drag   or 1.5
    td  = target_dur or 4.0
    rec = (recycling or 70) / 100.0

    if tab == "allocated": return render_allocated(alloc, t, fd, fs)
    if tab == "pipeline":  return render_pipeline(pipe, t, fd)
    if tab == "irr":       return render_irr(alloc, pipe, t, fd)
    if tab == "pacing":    return render_pacing(alloc, pipe, fs, t, rec)
    if tab == "duration":  return render_duration(alloc, pipe, t, td)
    return html.Div()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Allocated Portfolio
# ══════════════════════════════════════════════════════════════════════════════

def render_allocated(alloc, twr, fee_drag, fund_size):
    req_gross = twr + fee_drag

    form = html.Div([
        sec_lbl("Add Allocated Deal"),
        html.Div([
            field("Deal Name",
                  dcc.Input(id="a-name", type="text",
                            placeholder="e.g. Senior Secured LP A", style=INP)),
            field("Type",
                  dcc.Dropdown(id="a-type", options=TYPES,
                               value="Secondary", style=dd_style())),
            field("Sector",
                  dcc.Dropdown(id="a-sector", options=SECTORS,
                               value="Diversified Credit", style=dd_style())),
            field("Commit ($M)",
                  dcc.Input(id="a-commit", type="number",
                            value=10, min=0.1, step=0.5, style=INP)),
            field("MOIC",
                  dcc.Input(id="a-moic", type="number",
                            value=1.5, min=1.0, step=0.01, style=INP)),
            field("Hold (y)",
                  dcc.Input(id="a-hold", type="number",
                            value=3.0, min=0.5, step=0.5, style=INP)),
            field("Deploy Q",
                  dcc.Input(id="a-dq", type="number",
                            value=1, min=1, max=20, style=INP)),
            field("Deploy %",
                  dcc.Input(id="a-dr", type="number",
                            value=100, min=0, max=100, style=INP)),
            html.Div([
                lbl(" "),
                html.Button("+ Allocate", id="add-alloc-btn",
                            style=btn_style(C["blue"])),
            ]),
        ], style=dict(
            display="grid",
            gridTemplateColumns="2fr 1fr 1.4fr 1fr 1fr 1fr 0.8fr 0.8fr auto",
            gap=10, alignItems="end",
        )),
        html.Div(id="alloc-msg",
                 style=dict(marginTop=6, fontSize=11, color=C["green"])),
    ], style=dict(
        background=C["surface"],
        border=f"1px solid {rgba(C['blue'], 0.4)}",
        borderRadius=8, padding=18, marginBottom=18,
    ))

    if not alloc:
        tbl = empty_state("No allocated deals yet — add your first deal above.")
    else:
        total = sum(d["commitment"] for d in alloc)
        rows  = []
        for d in alloc:
            a   = ann_return(d["moic"], d["hold_years"])
            irr = calc_irr(d["commitment"], d["moic"], d["hold_years"])
            rm  = req_moic(d["hold_years"], twr)
            w   = d["commitment"] / total * 100 if total else 0
            rows.append({
                "Deal":        d["name"],
                "Type":        d["type"],
                "Sector":      d["sector"],
                "$M":          f"${d['commitment']:.1f}M",
                "Weight":      f"{w:.1f}%",
                "MOIC":        f"{d['moic']:.2f}x",
                "Hold (y)":    f"{d['hold_years']:.1f}",
                "Deal IRR":    f"{irr:.1f}%" if irr else "—",
                "Req. IRR":    f"{req_gross:.1f}%",
                "Ann. Return": f"{a:.1f}%" if a else "—",
                "Req. MOIC":   f"{rm:.2f}x",
                "Status":      "✓ On Target" if a and a >= twr else "✗ Below",
            })
        tbl = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in rows[0]],
            data=rows,
            style_cell=TBL_CELL, style_header=TBL_HEAD,
            style_data_conditional=TBL_ODD + [
                {"if": {"filter_query": '{Status} = "✓ On Target"',
                        "column_id": "Status"},
                 "color": C["green"], "fontWeight": 700},
                {"if": {"filter_query": '{Status} = "✗ Below"',
                        "column_id": "Status"},
                 "color": C["red"], "fontWeight": 700},
            ],
            sort_action="native", page_size=15,
            style_table={"overflowX": "auto"},
        )

    if alloc:
        type_vals = {}
        sec_vals  = {}
        for d in alloc:
            type_vals[d["type"]]  = type_vals.get(d["type"], 0)  + d["commitment"]
            sec_vals[d["sector"]] = sec_vals.get(d["sector"], 0) + d["commitment"]
        palette = [C["blue"], C["teal"], C["purple"], C["pink"],
                   C["amber"], C["green"], C["red"], C["sky"]]
        fig = make_subplots(1, 2,
                            specs=[[{"type": "domain"}, {"type": "domain"}]],
                            subplot_titles=["By Strategy", "By Sector"])
        fig.add_trace(go.Pie(
            labels=list(type_vals.keys()), values=list(type_vals.values()),
            hole=0.58, marker_colors=[C["blue"], C["purple"]],
            textfont_color=C["text"]), 1, 1)
        fig.add_trace(go.Pie(
            labels=list(sec_vals.keys()), values=list(sec_vals.values()),
            hole=0.58, marker_colors=palette[:len(sec_vals)],
            textfont_color=C["text"]), 1, 2)
        fig.update_layout(**CHART_BASE, height=260)
        chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    else:
        chart = empty_state("Chart will appear once deals are added.")

    return html.Div([
        form,
        html.Div([
            html.Div(tbl, style=dict(
                flex=3, overflowX="auto",
                background=C["panel"],
                border=f"1px solid {C['border']}",
                borderRadius=8, padding=4)),
            html.Div(card([chart]), style=dict(flex=2, minWidth=300)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Deal Pipeline
# ══════════════════════════════════════════════════════════════════════════════

def render_pipeline(pipe, twr, fee_drag):
    req_gross = twr + fee_drag

    form = html.Div([
        sec_lbl("Add Pipeline Deal"),
        html.Div([
            field("Deal Name",
                  dcc.Input(id="p-name", type="text",
                            placeholder="e.g. Unitranche Co-Invest D", style=INP)),
            field("Type",
                  dcc.Dropdown(id="p-type", options=TYPES,
                               value="Secondary", style=dd_style())),
            field("Sector",
                  dcc.Dropdown(id="p-sector", options=SECTORS,
                               value="Diversified Credit", style=dd_style())),
            field("Stage",
                  dcc.Dropdown(id="p-stage", options=STAGES,
                               value="Screening", style=dd_style())),
            field("Priority",
                  dcc.Dropdown(id="p-priority", options=PRIOS,
                               value="Medium", style=dd_style())),
            field("$M",
                  dcc.Input(id="p-commit", type="number",
                            value=10, min=0.1, step=0.5, style=INP)),
            field("MOIC",
                  dcc.Input(id="p-moic", type="number",
                            value=1.5, min=1.0, step=0.01, style=INP)),
            field("Hold (y)",
                  dcc.Input(id="p-hold", type="number",
                            value=3.0, min=0.5, step=0.5, style=INP)),
            field("Deploy Q",
                  dcc.Input(id="p-dq", type="number",
                            value=4, min=1, max=20, style=INP)),
            html.Div([
                lbl(" "),
                html.Button("+ Add to Pipeline", id="add-pipe-btn",
                            style=btn_style(C["purple"])),
            ]),
        ], style=dict(
            display="grid",
            gridTemplateColumns="2fr 1fr 1.4fr 1fr 1fr 1fr 1fr 1fr 0.8fr auto",
            gap=10, alignItems="end",
        )),
        html.Div(id="pipe-msg",
                 style=dict(marginTop=6, fontSize=11, color=C["green"])),
    ], style=dict(
        background=C["surface"],
        border=f"1px solid {rgba(C['purple'], 0.4)}",
        borderRadius=8, padding=18, marginBottom=18,
    ))

    if not pipe:
        tbl = empty_state("Pipeline is empty — add deals above.")
    else:
        rows = []
        for d in pipe:
            a   = ann_return(d["moic"], d["hold_years"])
            irr = calc_irr(d["commitment"], d["moic"], d["hold_years"])
            rm  = req_moic(d["hold_years"], twr)
            rows.append({
                "Deal":           d["name"],
                "Type":           d["type"],
                "Sector":         d["sector"],
                "Stage":          d.get("pipeline_stage", "Screening"),
                "Priority":       d.get("priority", "Medium"),
                "$M":             f"${d['commitment']:.1f}M",
                "MOIC":           f"{d['moic']:.2f}x",
                "Hold (y)":       f"{d['hold_years']:.1f}",
                "Deal IRR":       f"{irr:.1f}%" if irr else "—",
                "Req. Gross IRR": f"{req_gross:.1f}%",
                "Ann. Return":    f"{a:.1f}%" if a else "—",
                "Req. MOIC":      f"{rm:.2f}x",
                "vs Target":      "✓ Meets" if a and a >= twr else "✗ Miss",
            })
        tbl = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in rows[0]],
            data=rows,
            style_cell=TBL_CELL, style_header=TBL_HEAD,
            style_data_conditional=TBL_ODD + [
                {"if": {"filter_query": '{vs Target} = "✓ Meets"',
                        "column_id": "vs Target"},
                 "color": C["green"], "fontWeight": 700},
                {"if": {"filter_query": '{vs Target} = "✗ Miss"',
                        "column_id": "vs Target"},
                 "color": C["red"], "fontWeight": 700},
                {"if": {"filter_query": '{Priority} = "High"',
                        "column_id": "Priority"},
                 "color": C["red"], "fontWeight": 700},
                {"if": {"filter_query": '{Priority} = "Medium"',
                        "column_id": "Priority"},
                 "color": C["amber"]},
                {"if": {"filter_query": '{Priority} = "Low"',
                        "column_id": "Priority"},
                 "color": C["green"]},
            ],
            sort_action="native", page_size=10,
            style_table={"overflowX": "auto"},
        )

    if pipe:
        stage_caps = {
            s: sum(d["commitment"] for d in pipe if d.get("pipeline_stage") == s)
            for s in STAGES
        }
        ff = go.Figure(go.Funnel(
            y=STAGES,
            x=[stage_caps.get(s, 0) for s in STAGES],
            textinfo="value+percent initial",
            marker_color=[C["blue"], C["teal"], C["amber"], C["purple"], C["green"]],
            textfont=dict(color=C["text"]),
            connector=dict(line=dict(color=C["border"], width=1)),
        ))
        ff.update_layout(**CHART_BASE, height=300,
                         title="Pipeline Funnel by Committed ($M)")
        funnel = dcc.Graph(figure=ff, config={"displayModeBar": False})
    else:
        funnel = empty_state("Funnel will appear once pipeline deals are added.")

    return html.Div([
        form,
        html.Div([
            html.Div(tbl, style=dict(
                flex=3, overflowX="auto",
                background=C["panel"],
                border=f"1px solid {C['border']}",
                borderRadius=8, padding=4)),
            html.Div(card([funnel]), style=dict(flex=2, minWidth=300)),
        ], style=dict(display="flex", gap=16, flexWrap="wrap")),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IRR & Return Targets
# ══════════════════════════════════════════════════════════════════════════════

def render_irr(alloc, pipe, twr, fee_drag):
    req_gross = twr + fee_drag
    all_deals = (
        [dict(**d, pool="Allocated") for d in alloc] +
        [dict(**d, pool="Pipeline")  for d in pipe]
    )

    hold_range = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0]
    req_rows = []
    for h in hold_range:
        near = [d["name"].split()[-1] for d in all_deals
                if abs(d["hold_years"] - h) < 0.3]
        req_rows.append({
            "Hold (y)":                           f"{h:.1f}",
            f"Net MOIC ({twr}% TWR)":             f"{req_moic(h, twr):.3f}x",
            f"Gross MOIC ({req_gross:.1f}% IRR)": f"{req_moic(h, req_gross):.3f}x",
            "Deals Near":                          ", ".join(near) or "—",
        })

    req_tbl = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in req_rows[0]],
        data=req_rows,
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD,
        style_table={"overflowX": "auto"},
    )

    fig_sc = go.Figure()
    for pool, color in [("Allocated", C["blue"]), ("Pipeline", C["purple"])]:
        ds = [d for d in all_deals if d["pool"] == pool]
        if not ds:
            continue
        irrs  = [calc_irr(d["commitment"], d["moic"], d["hold_years"]) or 0 for d in ds]
        sizes = [max(8, d["commitment"] * 1.5) for d in ds]
        fig_sc.add_trace(go.Scatter(
            x=[d["hold_years"] for d in ds], y=irrs,
            mode="markers+text", name=pool,
            marker=dict(color=color, size=sizes, opacity=0.8,
                        line=dict(color=C["border"], width=1)),
            text=[d["name"].split()[-1] for d in ds],
            textposition="top center",
            textfont=dict(color=C["text"], size=9),
            hovertext=[f"{d['name']}<br>IRR: {i:.1f}%<br>${d['commitment']:.0f}M"
                       for d, i in zip(ds, irrs)],
            hoverinfo="text",
        ))

    xs = [0.5, 8.0]
    fig_sc.add_trace(go.Scatter(
        x=xs, y=[req_gross] * 2, mode="lines",
        name=f"Req. Gross IRR ({req_gross:.1f}%)",
        line=dict(color=C["amber"], dash="dash", width=2),
    ))
    fig_sc.add_trace(go.Scatter(
        x=xs, y=[twr] * 2, mode="lines",
        name=f"Net TWR ({twr:.1f}%)",
        line=dict(color=C["teal"], dash="dot", width=1.5),
    ))
    fig_sc.update_layout(
        **CHART_BASE, height=360,
        title="Deal IRR vs Hold Period  (bubble size ∝ commitment $M)",
        xaxis_title="Hold Period (y)", yaxis_title="IRR (%)",
    )

    if all_deals:
        labels = [" ".join(d["name"].split()[:2]) for d in all_deals]
        gaps   = [(ann_return(d["moic"], d["hold_years"]) or 0) - twr
                  for d in all_deals]
        colors = [C["green"] if g >= 0 else C["red"] for g in gaps]
        fig_gap = go.Figure(go.Bar(
            x=labels, y=gaps,
            marker_color=colors,
            text=[f"{g:+.1f}%" for g in gaps],
            textposition="outside",
            textfont_color=C["text"],
        ))
        fig_gap.add_hline(y=0, line_color=C["muted"], line_width=1.5)
        fig_gap.update_layout(
            **CHART_BASE, height=300,
            title=f"Ann. Return Gap vs {twr}% Net TWR  (all deals)",
            yaxis_title="Gap (pp)",
        )
        gap_chart = dcc.Graph(figure=fig_gap, config={"displayModeBar": False})
    else:
        gap_chart = empty_state("Add deals to see gap analysis.")

    return html.Div([
        html.Div([
            card([
                sec_lbl(f"Required MOIC · Net TWR {twr}% · Gross IRR {req_gross:.1f}%"),
                req_tbl,
            ], {"flex": 2}),
            card([
                sec_lbl("Hurdle Summary"),
                kpi_card("Required Net TWR",   f"{twr:.1f}%",
                         "annualised", C["teal"], 120),
                html.Div(style=dict(height=8)),
                kpi_card("Required Gross IRR", f"{req_gross:.1f}%",
                         f"net + {fee_drag:.1f}% fees", C["amber"], 120),
                html.Div(style=dict(height=8)),
                kpi_card("Gross MOIC @ 3y",
                         f"{req_moic(3, req_gross):.2f}x", "gross", C["sky"], 120),
                html.Div(style=dict(height=8)),
                kpi_card("Gross MOIC @ 5y",
                         f"{req_moic(5, req_gross):.2f}x", "gross", C["sky"], 120),
            ], {"flex": 1, "minWidth": 200}),
        ], style=dict(display="flex", gap=16, marginBottom=16, flexWrap="wrap")),
        card([dcc.Graph(figure=fig_sc, config={"displayModeBar": False})],
             {"marginBottom": 16}),
        card([gap_chart]),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Evergreen Pacing  (FIXED dual-axis + empty-store safe)
# ══════════════════════════════════════════════════════════════════════════════

def render_pacing(alloc, pipe, fund_size, twr, recycling):
    all_deals = alloc + pipe
    avg_hold  = wal(all_deals) or 3.5

    df = evergreen_schedule(fund_size, 0.85, recycling, avg_hold, quarters=24)

    # Chart 1: stacked deployment bars + NAV on secondary axis
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(
        go.Bar(x=df["label"], y=df["new_deploy"],
               name="New Capital", marker_color=C["blue"], opacity=0.9),
        secondary_y=False,
    )
    fig1.add_trace(
        go.Bar(x=df["label"], y=df["recycled"],
               name="Recycled", marker_color=C["teal"], opacity=0.85),
        secondary_y=False,
    )
    fig1.add_trace(
        go.Scatter(x=df["label"], y=df["nav"], name="NAV",
                   mode="lines+markers",
                   line=dict(color=C["amber"], width=2.5),
                   marker=dict(size=4)),
        secondary_y=True,
    )
    fig1.update_layout(
        **CHART_BASE, barmode="stack", height=380,
        title="Evergreen Deployment — New + Recycled Capital vs NAV",
    )
    fig1.update_yaxes(
        title_text="Quarterly Deployment ($M)",
        gridcolor=C["border"], secondary_y=False,
    )
    fig1.update_yaxes(
        title_text="NAV ($M)",
        showgrid=False, secondary_y=True,
    )

    # Chart 2: utilisation
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["label"], y=df["utilisation"],
        fill="tozeroy", fillcolor=rgba(C["blue"], 0.12),
        line=dict(color=C["blue"], width=2), name="Utilisation %",
    ))
    fig2.add_hline(y=85,  line_dash="dash", line_color=C["amber"],
                   annotation_text="85% target",
                   annotation_font_color=C["amber"])
    fig2.add_hline(y=100, line_dash="dot", line_color=C["red"],
                   annotation_text="100%",
                   annotation_font_color=C["red"])
    fig2.update_layout(
        **CHART_BASE, height=260,
        title="NAV Utilisation Over Time (%)",
        yaxis=dict(title="%", range=[0, 115], gridcolor=C["border"]),
    )

    # Chart 3: actual deal pacing
    q_labels   = [f"Q{((q-1)%4)+1} Y{math.ceil(q/4)}" for q in range(1, 17)]
    alloc_by_q = {q: 0.0 for q in range(1, 17)}
    pipe_by_q  = {q: 0.0 for q in range(1, 17)}
    for d in alloc:
        q = min(16, max(1, int(d.get("deploy_q", 1))))
        alloc_by_q[q] += d["commitment"]
    for d in pipe:
        q = min(16, max(1, int(d.get("deploy_q", 1))))
        pipe_by_q[q]  += d["commitment"]

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=q_labels,
        y=[alloc_by_q[q] for q in range(1, 17)],
        name="Allocated", marker_color=C["blue"],
    ))
    fig3.add_trace(go.Bar(
        x=q_labels,
        y=[pipe_by_q[q] for q in range(1, 17)],
        name="Pipeline", marker_color=C["purple"], opacity=0.7,
    ))
    fig3.update_layout(
        **CHART_BASE, barmode="stack", height=280,
        title="Actual Deal Pacing — Allocated + Pipeline ($M committed)",
        yaxis=dict(title="$M", gridcolor=C["border"]),
    )

    # Quarterly schedule table
    tbl_df = df[[
        "label", "new_deploy", "recycled", "total_deploy",
        "repayments", "nav", "utilisation", "cum_deployed",
    ]].head(16).copy()
    tbl_df.columns = [
        "Period", "New ($M)", "Recycled ($M)", "Total ($M)",
        "Repaid ($M)", "NAV ($M)", "Util %", "Cum. Deployed ($M)",
    ]
    for col in ["New ($M)", "Recycled ($M)", "Total ($M)",
                "Repaid ($M)", "NAV ($M)", "Cum. Deployed ($M)"]:
        tbl_df[col] = tbl_df[col].apply(lambda x: f"${x:.1f}M")
    tbl_df["Util %"] = tbl_df["Util %"].apply(lambda x: f"{x:.1f}%")

    pacing_tbl = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in tbl_df.columns],
        data=tbl_df.to_dict("records"),
        style_cell=TBL_CELL, style_header=TBL_HEAD,
        style_data_conditional=TBL_ODD,
        style_table={"overflowX": "auto"},
    )

    return html.Div([
        card([dcc.Graph(figure=fig1, config={"displayModeBar": False})],
             {"marginBottom": 16}),
        html.Div([
            card([dcc.Graph(figure=fig2, config={"displayModeBar": False})],
                 {"flex": 1}),
            card([dcc.Graph(figure=fig3, config={"displayModeBar": False})],
                 {"flex": 1}),
        ], style=dict(display="flex", gap=16, marginBottom=16, flexWrap="wrap")),
        card([
            sec_lbl(
                f"Quarterly Schedule  ·  Avg Hold {avg_hold:.1f}y  ·  "
                f"Recycling {recycling*100:.0f}%  ·  Fund ${fund_size:.0f}M"
            ),
            pacing_tbl,
        ]),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Duration Analysis
# ══════════════════════════════════════════════════════════════════════════════

def render_duration(alloc, pipe, twr, target_dur):
    all_deals = (
        [dict(**d, pool="Allocated") for d in alloc] +
        [dict(**d, pool="Pipeline")  for d in pipe]
    )

    wal_a = wal(alloc)     or 0.0
    dur_a = mod_duration(alloc, twr) or 0.0
    wal_p = wal(all_deals) or 0.0
    dur_p = mod_duration(all_deals, twr) or 0.0

    wal_gap = target_dur - wal_a
    dur_gap = (target_dur / (1 + twr / 100)) - dur_a

    if all_deals:
        total_c = sum(d["commitment"] for d in all_deals) or 1
        rows = []
        for d in all_deals:
            a    = ann_return(d["moic"], d["hold_years"])
            mdur = d["hold_years"] / (1 + twr / 100)
            rows.append({
                "Deal":              d["name"],
                "Pool":              d["pool"],
                "Type":              d["type"],
                "$M":                f"${d['commitment']:.1f}M",
                "Hold (y)":          f"{d['hold_years']:.1f}",
                "Mod. Dur. (y)":     f"{mdur:.2f}",
                "Dur. Contribution": f"{mdur * d['commitment'] / total_c:.3f}y",
                "Ann. Return":       f"{a:.1f}%" if a else "—",
            })
        dur_tbl = dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in rows[0]],
            data=rows,
            style_cell=TBL_CELL, style_header=TBL_HEAD,
            style_data_conditional=TBL_ODD + [
                {"if": {"filter_query": '{Pool} = "Allocated"',
                        "column_id": "Pool"},
                 "color": C["sky"], "fontWeight": 600},
                {"if": {"filter_query": '{Pool} = "Pipeline"',
                        "column_id": "Pool"},
                 "color": C["purple"], "fontWeight": 600},
            ],
            sort_action="native",
            style_table={"overflowX": "auto"},
        )
    else:
        dur_tbl = empty_state("Add deals to see duration breakdown.")

    cats = ["Allocated", "Alloc + Pipeline", f"Target ({target_dur:.1f}y)"]
    wals = [wal_a, wal_p, target_dur]
    durs = [dur_a, dur_p, target_dur / (1 + twr / 100)]
    cols = [C["blue"], C["purple"], C["teal"]]

    fig_dur = go.Figure()
    fig_dur.add_trace(go.Bar(
        x=cats, y=wals, name="WAL (y)",
        marker_color=cols, opacity=0.85,
        text=[f"{v:.2f}y" for v in wals],
        textposition="outside", textfont_color=C["text"],
    ))
    fig_dur.add_trace(go.Bar(
        x=cats, y=durs, name="Mod. Duration (y)",
        marker_color=[rgba(c, 0.45) for c in cols],
        text=[f"{v:.2f}y" for v in durs],
        textposition="inside", textfont_color=C["text"],
    ))
    fig_dur.add_hline(
        y=target_dur, line_dash="dash", line_color=C["amber"],
        annotation_text=f"WAL target {target_dur}y",
        annotation_font_color=C["amber"],
    )
    fig_dur.update_layout(
        **CHART_BASE, barmode="group", height=320,
        title="Weighted Average Life & Modified Duration",
        yaxis=dict(title="Years", gridcolor=C["border"]),
    )

    if all_deals:
        total_c = sum(d["commitment"] for d in all_deals) or 1
        contribs = sorted(
            [(d["name"].split()[-1],
              (d["hold_years"] / (1 + twr / 100)) * d["commitment"] / total_c,
              C["blue"] if d["pool"] == "Allocated" else C["purple"])
             for d in all_deals],
            key=lambda x: x[1], reverse=True,
        )
        fig_contrib = go.Figure(go.Bar(
            y=[x[0] for x in contribs],
            x=[x[1] for x in contribs],
            orientation="h",
            marker_color=[x[2] for x in contribs],
            text=[f"{x[1]:.3f}y" for x in contribs],
            textposition="outside",
            textfont_color=C["text"],
        ))
        fig_contrib.update_layout(
            **CHART_BASE,
            height=max(220, len(contribs) * 34 + 80),
            title="Duration Contribution by Deal (y)",
            xaxis_title="Mod. Duration Contribution (y)",
            margin=dict(l=80, r=40, t=38, b=38),
        )
        contrib_chart = dcc.Graph(figure=fig_contrib,
                                   config={"displayModeBar": False})
    else:
        contrib_chart = empty_state("Add deals to see duration contributions.")

    return html.Div([
        html.Div([
            kpi_card("WAL — Allocated",
                     f"{wal_a:.2f}y", f"Target {target_dur:.1f}y", C["blue"]),
            kpi_card("WAL — Alloc + Pipeline",
                     f"{wal_p:.2f}y", f"Gap {target_dur - wal_p:+.2f}y",
                     C["green"] if wal_p >= target_dur else C["amber"]),
            kpi_card("Mod. Duration",
                     f"{dur_a:.2f}y", f"= WAL / (1+{twr}%)", C["teal"]),
            kpi_card("WAL Gap",
                     f"{wal_gap:+.2f}y", "vs target",
                     C["green"] if wal_gap >= 0 else C["red"]),
            kpi_card("Duration Gap",
                     f"{dur_gap:+.2f}y", "mod. duration",
                     C["green"] if dur_gap >= 0 else C["red"]),
        ], style=dict(display="flex", gap=10, flexWrap="wrap", marginBottom=16)),

        html.Div([
            card([dcc.Graph(figure=fig_dur, config={"displayModeBar": False})],
                 {"flex": 3}),
            card([contrib_chart], {"flex": 2}),
        ], style=dict(display="flex", gap=16, marginBottom=16, flexWrap="wrap")),

        card([sec_lbl("Duration Detail by Deal"), dur_tbl],
             {"marginBottom": 16}),

        card([
            html.Div("🔬  Duration Prescription",
                     style=dict(fontSize=11, color=C["muted"], fontWeight=600,
                                marginBottom=10, letterSpacing=1)),
            insight_row(
                f"Current allocated WAL is {wal_a:.1f}y vs {target_dur:.1f}y target "
                f"— gap of {wal_gap:+.1f}y.",
                C["amber"] if abs(wal_gap) > 0.5 else C["green"],
            ),
            insight_row(
                f"Including pipeline reduces gap to {target_dur - wal_p:+.1f}y.",
                C["teal"] if wal_p > wal_a else C["muted"],
            ),
            insight_row(
                f"To extend duration: favour longer-dated deals "
                f"(>{target_dur:.0f}y hold) or reduce short-tenor secondaries.",
                C["sky"],
            ),
            insight_row(
                f"At {target_dur:.1f}y WAL, gross MOIC needed = "
                f"{req_moic(target_dur, twr + 1.5):.2f}x "
                f"(net TWR {twr:.1f}% + 1.5% fee drag).",
                C["purple"],
            ),
        ]),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("alloc-store", "data"),
    Output("next-id", "data"),
    Output("alloc-msg", "children"),
    Input("add-alloc-btn", "n_clicks"),
    State("alloc-store", "data"),
    State("next-id", "data"),
    State("a-name",   "value"),
    State("a-type",   "value"),
    State("a-sector", "value"),
    State("a-commit", "value"),
    State("a-moic",   "value"),
    State("a-hold",   "value"),
    State("a-dq",     "value"),
    State("a-dr",     "value"),
    prevent_initial_call=True,
)
def cb_add_alloc(_, alloc, nid, name, dtype, sector,
                 commit, moic, hold, dq, dr):
    if not all([name, commit, moic, hold]):
        return alloc, nid, "⚠ Please fill in all required fields."
    new = dict(
        id=nid, name=name,
        type=dtype   or "Secondary",
        sector=sector or SECTORS[0],
        commitment=float(commit),
        moic=float(moic),
        hold_years=float(hold),
        deploy_q=int(dq or 1),
        deployment_rate=float(dr or 100),
        status="allocated",
    )
    return alloc + [new], nid + 1, f"✓ Allocated: {name}"


@app.callback(
    Output("pipe-store", "data"),
    Output("next-id", "data", allow_duplicate=True),
    Output("pipe-msg", "children"),
    Input("add-pipe-btn", "n_clicks"),
    State("pipe-store", "data"),
    State("next-id", "data"),
    State("p-name",     "value"),
    State("p-type",     "value"),
    State("p-sector",   "value"),
    State("p-stage",    "value"),
    State("p-priority", "value"),
    State("p-commit",   "value"),
    State("p-moic",     "value"),
    State("p-hold",     "value"),
    State("p-dq",       "value"),
    prevent_initial_call=True,
)
def cb_add_pipe(_, pipe, nid, name, dtype, sector,
                stage, prio, commit, moic, hold, dq):
    if not all([name, commit, moic, hold]):
        return pipe, nid, "⚠ Please fill in all required fields."
    new = dict(
        id=nid, name=name,
        type=dtype    or "Secondary",
        sector=sector  or SECTORS[0],
        pipeline_stage=stage or "Screening",
        priority=prio  or "Medium",
        commitment=float(commit),
        moic=float(moic),
        hold_years=float(hold),
        deploy_q=int(dq or 4),
        deployment_rate=100,
        status="pipeline",
    )
    return pipe + [new], nid + 1, f"✓ Added to pipeline: {name}"


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=8050)
