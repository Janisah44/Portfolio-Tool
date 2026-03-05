"""
Portfolio Construction Tool — Evergreen Credit Secondaries & Co-Investment Fund
Plotly Dash implementation

Install dependencies:
    pip install dash plotly pandas numpy

Run:
    python portfolio_tool.py
Then open http://127.0.0.1:8050 in your browser.
"""

import math
import numpy as np
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx, ALL, MATCH
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Colour palette ────────────────────────────────────────────────────────────
C = dict(
    bg="#060f18", surface="#0a1e2e", border="#1a3348",
    blue="#1e6fa8", sky="#4fc3f7", purple="#a78bfa",
    green="#27ae60", red="#e74c3c", amber="#f39c12",
    text="#c8dce8", muted="#5a8ab0", dim="#3d6a85",
)

CHART_LAYOUT = dict(
    paper_bgcolor=C["bg"], plot_bgcolor=C["surface"],
    font=dict(family="IBM Plex Mono, monospace", color=C["text"], size=11),
    margin=dict(l=50, r=20, t=40, b=40),
)

# ── Maths helpers ─────────────────────────────────────────────────────────────

def required_ann_return(moic: float, hold_years: float) -> float | None:
    if hold_years <= 0 or moic <= 0:
        return None
    return (moic ** (1 / hold_years) - 1) * 100


def required_moic(hold_years: float, target_twr: float) -> float:
    return (1 + target_twr / 100) ** hold_years


def portfolio_twr(deals: list[dict]) -> float | None:
    total = sum(d["commitment"] for d in deals)
    if not total:
        return None
    weighted = sum(
        (required_ann_return(d["moic"], d["hold_years"]) or 0) * d["commitment"]
        for d in deals
    )
    return weighted / total


def calc_irr(commitment: float, moic: float, hold_years: float) -> float | None:
    if hold_years <= 0 or commitment <= 0:
        return None
    r = 0.1
    for _ in range(200):
        cfs = [(-commitment, 0), (commitment * moic, hold_years)]
        f = sum(cf / (1 + r) ** t for cf, t in cfs)
        df = sum(-t * cf / ((1 + r) ** (t + 1)) for cf, t in cfs)
        if abs(df) < 1e-12:
            break
        nr = r - f / df
        if abs(nr - r) < 1e-9:
            r = nr
            break
        r = nr
    return r * 100


def generate_pacing(deals: list[dict], fund_size: float, quarters: int = 20) -> pd.DataFrame:
    rows = []
    for q in range(1, quarters + 1):
        year = math.ceil(q / 4)
        qtr = ((q - 1) % 4) + 1
        committed = sum(d["commitment"] for d in deals if d["deploy_q"] == q)
        deployed = sum(
            d["commitment"] * d["deployment_rate"] / 100
            for d in deals if d["deploy_q"] == q
        )
        deal_names = [d["name"].split()[-1] for d in deals if d["deploy_q"] == q]
        rows.append(dict(q=q, label=f"Q{qtr} Y{year}", committed=committed,
                         deployed=deployed, deal_names=", ".join(deal_names) or "—"))
    df = pd.DataFrame(rows)
    df["cum_committed"] = df["committed"].cumsum()
    df["cum_deployed"] = df["deployed"].cumsum()
    df["pct_fund"] = df["cum_committed"] / fund_size * 100 if fund_size else 0
    return df


# ── Default deals ─────────────────────────────────────────────────────────────

DEFAULT_DEALS = [
    dict(id=1, name="Senior Secured LP Interest A", type="Secondary",
         commitment=25, moic=1.45, hold_years=3.5, deploy_q=1, deployment_rate=85, sector="Diversified Credit"),
    dict(id=2, name="Mezzanine Co-Invest B", type="Co-investment",
         commitment=15, moic=1.72, hold_years=4.0, deploy_q=2, deployment_rate=100, sector="Healthcare"),
    dict(id=3, name="Distressed Debt Portfolio C", type="Secondary",
         commitment=30, moic=1.38, hold_years=2.5, deploy_q=1, deployment_rate=90, sector="TMT"),
    dict(id=4, name="Unitranche Co-Invest D", type="Co-investment",
         commitment=20, moic=1.85, hold_years=5.0, deploy_q=3, deployment_rate=100, sector="Infrastructure"),
    dict(id=5, name="CLO Tranche Secondary E", type="Secondary",
         commitment=18, moic=1.52, hold_years=3.0, deploy_q=4, deployment_rate=80, sector="Structured Credit"),
    dict(id=6, name="First Lien Co-Invest F", type="Co-investment",
         commitment=12, moic=1.62, hold_years=3.5, deploy_q=5, deployment_rate=100, sector="Consumer"),
]

SECTORS = ["Diversified Credit", "Healthcare", "TMT", "Infrastructure",
           "Structured Credit", "Consumer", "Real Assets", "Financial Services"]
DEAL_TYPES = ["Secondary", "Co-investment"]


# ── App ───────────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, title="Portfolio Construction Tool",
                suppress_callback_exceptions=True)

# ── Layout helpers ─────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, sub: str = "", color: str = C["sky"]) -> html.Div:
    return html.Div([
        html.Div(label, style={"fontSize": 10, "letterSpacing": 2, "color": C["muted"],
                               "textTransform": "uppercase", "marginBottom": 4}),
        html.Div(value, style={"fontSize": 24, "fontWeight": 700, "color": color,
                               "fontFamily": "IBM Plex Mono, monospace"}),
        html.Div(sub, style={"fontSize": 11, "color": C["dim"], "marginTop": 2}),
    ], style={"background": C["surface"], "border": f"1px solid {C['border']}",
              "borderRadius": 8, "padding": "16px 20px", "minWidth": 130})


def section_header(text: str) -> html.Div:
    return html.Div(text, style={"fontSize": 10, "letterSpacing": 2, "color": C["muted"],
                                 "textTransform": "uppercase", "marginBottom": 12})


# ── Main layout ────────────────────────────────────────────────────────────────

app.layout = html.Div([

    # State stores
    dcc.Store(id="deals-store", data=DEFAULT_DEALS),
    dcc.Store(id="next-id-store", data=20),

    # ── Header ──
    html.Div([
        html.Div([
            html.Div("Portfolio Construction Tool", style={
                "fontSize": 20, "fontWeight": 700, "color": "#e8f4fd"}),
            html.Div([
                html.Span("EVERGREEN", style={"background": "#1e6fa833", "border": "1px solid #1e6fa855",
                          "color": C["sky"], "borderRadius": 4, "padding": "2px 8px",
                          "fontSize": 10, "fontWeight": 600, "marginRight": 6}),
                html.Span("CREDIT SECONDARIES & CO-INVEST", style={"background": "#a78bfa22",
                          "border": "1px solid #a78bfa44", "color": C["purple"],
                          "borderRadius": 4, "padding": "2px 8px", "fontSize": 10, "fontWeight": 600}),
            ], style={"marginTop": 6}),
        ]),
        html.Div([
            html.Div([
                html.Label("Fund Size ($M)", style={"fontSize": 10, "color": C["muted"],
                                                     "letterSpacing": 1, "display": "block", "marginBottom": 4}),
                dcc.Input(id="fund-size", type="number", value=200, min=1,
                          style={"background": C["surface"], "border": f"1px solid {C['border']}",
                                 "color": C["text"], "borderRadius": 6, "padding": "6px 10px",
                                 "width": 100, "fontFamily": "IBM Plex Mono, monospace"}),
            ]),
            html.Div([
                html.Label("Target TWR (%)", style={"fontSize": 10, "color": C["muted"],
                                                     "letterSpacing": 1, "display": "block", "marginBottom": 4}),
                dcc.Input(id="target-twr", type="number", value=10, min=0, step=0.5,
                          style={"background": C["surface"], "border": f"1px solid {C['border']}",
                                 "color": C["text"], "borderRadius": 6, "padding": "6px 10px",
                                 "width": 100, "fontFamily": "IBM Plex Mono, monospace"}),
            ]),
        ], style={"display": "flex", "gap": 16, "alignItems": "flex-end"}),
    ], style={"background": "#081624", "borderBottom": f"1px solid {C['border']}",
              "padding": "24px 36px", "display": "flex",
              "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": 16}),

    # ── KPI row ──
    html.Div(id="kpi-row", style={"padding": "20px 36px", "display": "flex",
                                  "gap": 12, "flexWrap": "wrap", "alignItems": "flex-start"}),

    # ── Tabs ──
    html.Div([
        dcc.Tabs(id="tabs", value="deals", children=[
            dcc.Tab(label="Deal Book", value="deals"),
            dcc.Tab(label="Commitment Pacing", value="pacing"),
            dcc.Tab(label="Return Analysis", value="analytics"),
        ], colors={"border": C["border"], "primary": C["blue"], "background": C["bg"]},
           style={"fontFamily": "IBM Plex Sans, sans-serif"},
           content_style={"background": C["bg"], "padding": "24px 36px",
                          "border": f"1px solid {C['border']}"}),
    ], style={"padding": "0 36px"}),

    html.Div(id="tab-content", style={"padding": "0 36px 60px"}),

], style={"background": C["bg"], "minHeight": "100vh", "fontFamily": "IBM Plex Sans, sans-serif",
          "color": C["text"]})


# ── KPI row callback ───────────────────────────────────────────────────────────

@app.callback(
    Output("kpi-row", "children"),
    Input("deals-store", "data"),
    Input("fund-size", "value"),
    Input("target-twr", "value"),
)
def update_kpis(deals, fund_size, target_twr):
    fund_size = fund_size or 200
    target_twr = target_twr or 10
    total = sum(d["commitment"] for d in deals)
    remaining = fund_size - total
    utilisation = total / fund_size * 100 if fund_size else 0
    port_twr = portfolio_twr(deals)
    twr_gap = (port_twr - target_twr) if port_twr is not None else None

    wt_moic = (sum(d["moic"] * d["commitment"] for d in deals) / total) if total else None
    wt_hold = (sum(d["hold_years"] * d["commitment"] for d in deals) / total) if total else None

    port_irr = None
    if wt_moic and wt_hold and total:
        port_irr = calc_irr(total, wt_moic, wt_hold)

    deals_on_target = sum(
        1 for d in deals
        if (required_ann_return(d["moic"], d["hold_years"]) or 0) >= target_twr
    )
    req_moic_avg = required_moic(wt_hold or 3, target_twr)

    def color_twr(v):
        if v is None: return C["muted"]
        return C["green"] if v >= target_twr else C["red"]

    # Gauge figure
    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=port_twr or 0,
        number={"suffix": "%", "font": {"size": 22, "family": "IBM Plex Mono",
                                        "color": color_twr(port_twr)}},
        gauge=dict(
            axis=dict(range=[0, 20], tickfont=dict(color=C["muted"], size=9)),
            bar=dict(color=color_twr(port_twr)),
            bgcolor=C["surface"],
            borderwidth=0,
            steps=[dict(range=[0, target_twr], color="#0d2137"),
                   dict(range=[target_twr, 20], color="#0d2a1e")],
            threshold=dict(line=dict(color=C["sky"], width=2), thickness=0.8, value=target_twr),
        ),
        title=dict(text="Portfolio TWR p.a.", font=dict(color=C["muted"], size=10)),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    gauge_fig.update_layout(
        paper_bgcolor=C["surface"], font_color=C["text"],
        height=160, margin=dict(l=20, r=20, t=30, b=10),
    )

    gap_text = ""
    if twr_gap is not None:
        arrow = "▲" if twr_gap >= 0 else "▼"
        gap_color = C["green"] if twr_gap >= 0 else C["red"]
        gap_text = html.Div(f"{arrow} {abs(twr_gap):.1f}% vs target",
                            style={"fontSize": 11, "color": gap_color,
                                   "fontFamily": "IBM Plex Mono, monospace", "textAlign": "center"})

    gauge_card = html.Div([
        dcc.Graph(figure=gauge_fig, config={"displayModeBar": False}),
        gap_text,
    ], style={"background": C["surface"], "border": f"1px solid {C['border']}",
              "borderRadius": 8, "padding": "12px 16px"})

    cards = [
        gauge_card,
        kpi_card("Total Committed", f"${total:.0f}M", f"${remaining:.0f}M remaining"),
        kpi_card("Fund Utilisation", f"{utilisation:.1f}%", f"{len(deals)} deals",
                 color=C["amber"] if utilisation > 80 else C["sky"]),
        kpi_card("Wtd Avg MOIC", f"{wt_moic:.2f}x" if wt_moic else "—",
                 f"Hold: {wt_hold:.1f}y avg" if wt_hold else ""),
        kpi_card("Portfolio IRR", f"{port_irr:.1f}%" if port_irr else "—", "Blended estimate"),
        kpi_card("On-Target Deals", f"{deals_on_target}/{len(deals)}",
                 f"≥{target_twr}% p.a.",
                 color=C["green"] if deals_on_target == len(deals) else C["red"]),
        kpi_card("Required Avg MOIC", f"{req_moic_avg:.2f}x",
                 f"For {target_twr}% TWR @ {wt_hold:.1f}y" if wt_hold else ""),
    ]
    return cards


# ── Tab content router ─────────────────────────────────────────────────────────

@app.callback(
    Output("tab-content", "children"),
    Input("tabs", "value"),
    Input("deals-store", "data"),
    Input("fund-size", "value"),
    Input("target-twr", "value"),
)
def render_tab(tab, deals, fund_size, target_twr):
    fund_size = fund_size or 200
    target_twr = target_twr or 10

    if tab == "deals":
        return render_deals_tab(deals, target_twr)
    elif tab == "pacing":
        return render_pacing_tab(deals, fund_size)
    elif tab == "analytics":
        return render_analytics_tab(deals, fund_size, target_twr)
    return html.Div()


# ── Deal Book tab ──────────────────────────────────────────────────────────────

def render_deals_tab(deals, target_twr):
    rows = []
    total = sum(d["commitment"] for d in deals)
    for d in deals:
        ann = required_ann_return(d["moic"], d["hold_years"])
        irr = calc_irr(d["commitment"], d["moic"], d["hold_years"])
        req_m = required_moic(d["hold_years"], target_twr)
        meets = ann is not None and ann >= target_twr
        weight = (d["commitment"] / total * 100) if total else 0
        rows.append({
            "ID": d["id"],
            "Deal Name": d["name"],
            "Type": d["type"],
            "Sector": d["sector"],
            "Commit $M": f"${d['commitment']:.1f}M",
            "Weight %": f"{weight:.1f}%",
            "MOIC": f"{d['moic']:.2f}x",
            "Hold (y)": f"{d['hold_years']:.1f}",
            "Deploy Q": f"Q{d['deploy_q']}",
            "Ann. Return": f"{ann:.1f}%" if ann else "—",
            "Req. MOIC": f"{req_m:.2f}x",
            "IRR": f"{irr:.1f}%" if irr else "—",
            "Status": "✓ On Target" if meets else "✗ Below",
        })

    tbl_style = {"backgroundColor": C["surface"], "color": C["text"],
                 "fontFamily": "IBM Plex Mono, monospace", "border": "none"}

    table = dash_table.DataTable(
        id="deal-table",
        columns=[{"name": c, "id": c} for c in rows[0].keys() if c != "ID"],
        data=rows,
        style_table={"overflowX": "auto"},
        style_cell={**tbl_style, "padding": "9px 12px", "textAlign": "left",
                    "border": f"1px solid {C['border']}", "fontSize": 12},
        style_header={"backgroundColor": "#081624", "color": C["muted"],
                      "fontWeight": 600, "fontSize": 10, "letterSpacing": 1,
                      "textTransform": "uppercase", "border": f"1px solid {C['border']}"},
        style_data_conditional=[
            {"if": {"filter_query": '{Status} = "✓ On Target"', "column_id": "Status"},
             "color": C["green"], "fontWeight": 700},
            {"if": {"filter_query": '{Status} = "✗ Below"', "column_id": "Status"},
             "color": C["red"], "fontWeight": 700},
            {"if": {"row_index": "odd"}, "backgroundColor": "#081624"},
        ],
        page_size=20,
        sort_action="native",
    )

    # Add deal form
    input_style = {"background": C["surface"], "border": f"1px solid {C['border']}",
                   "color": C["text"], "borderRadius": 6, "padding": "6px 10px", "width": "100%",
                   "fontFamily": "IBM Plex Mono, monospace", "fontSize": 12}

    add_form = html.Div([
        section_header("Add New Deal"),
        html.Div([
            html.Div([html.Label("Deal Name", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Input(id="new-name", type="text", placeholder="Deal name", style=input_style)]),
            html.Div([html.Label("Type", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Dropdown(id="new-type", options=DEAL_TYPES, value="Secondary",
                                   style={"background": C["surface"], "color": C["text"]})]),
            html.Div([html.Label("Sector", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Dropdown(id="new-sector", options=SECTORS, value="Diversified Credit",
                                   style={"background": C["surface"]})]),
            html.Div([html.Label("Commit $M", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Input(id="new-commit", type="number", value=10, min=0.1, style=input_style)]),
            html.Div([html.Label("MOIC", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Input(id="new-moic", type="number", value=1.5, min=1.0, step=0.01, style=input_style)]),
            html.Div([html.Label("Hold (y)", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Input(id="new-hold", type="number", value=3.0, min=0.5, step=0.5, style=input_style)]),
            html.Div([html.Label("Deploy Q", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Input(id="new-deployq", type="number", value=1, min=1, max=20, style=input_style)]),
            html.Div([html.Label("Deploy %", style={"fontSize": 10, "color": C["muted"], "display": "block", "marginBottom": 3}),
                      dcc.Input(id="new-deploy-rate", type="number", value=100, min=0, max=100, style=input_style)]),
            html.Div([html.Label(" ", style={"fontSize": 10, "display": "block", "marginBottom": 3}),
                      html.Button("+ Add Deal", id="add-deal-btn",
                                  style={"background": C["blue"], "border": "none", "color": "#fff",
                                         "borderRadius": 6, "padding": "8px 18px", "cursor": "pointer",
                                         "fontWeight": 600, "fontSize": 12, "width": "100%"})]),
        ], style={"display": "grid", "gridTemplateColumns": "2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr auto",
                  "gap": 10, "alignItems": "end"}),
        html.Div(id="add-deal-msg", style={"marginTop": 8, "fontSize": 11, "color": C["green"]}),
    ], style={"background": "#081624", "border": f"1px solid {C['blue']}44",
              "borderRadius": 8, "padding": 20, "marginBottom": 20})

    return html.Div([add_form, table])


# ── Pacing tab ─────────────────────────────────────────────────────────────────

def render_pacing_tab(deals, fund_size):
    df = generate_pacing(deals, fund_size)
    df16 = df.head(16)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.4],
                        subplot_titles=["Quarterly Commitments & Deployments",
                                        "Cumulative Capital Deployed (% of Fund)"])
    fig.add_trace(go.Bar(x=df16["label"], y=df16["committed"], name="Committed",
                         marker_color=C["blue"], opacity=0.85), row=1, col=1)
    fig.add_trace(go.Bar(x=df16["label"], y=df16["deployed"], name="Deployed",
                         marker_color=C["sky"], opacity=0.9), row=1, col=1)
    fig.add_trace(go.Scatter(x=df16["label"], y=df16["pct_fund"], name="% of Fund",
                             line=dict(color=C["purple"], width=2),
                             fill="tozeroy", fillcolor=C["purple"] + "22"), row=2, col=1)
    fig.add_hline(y=100, line_dash="dash", line_color=C["amber"], row=2, col=1)
    fig.update_layout(**CHART_LAYOUT, height=480, barmode="group",
                      legend=dict(bgcolor=C["surface"], bordercolor=C["border"]))
    fig.update_yaxes(gridcolor=C["border"], zerolinecolor=C["border"])

    # Table
    tbl_cols = ["label", "committed", "deployed", "cum_committed", "cum_deployed",
                "pct_fund", "deal_names"]
    tbl_rename = {"label": "Period", "committed": "New Committed ($M)",
                  "deployed": "New Deployed ($M)", "cum_committed": "Cumul. Committed ($M)",
                  "cum_deployed": "Cumul. Deployed ($M)", "pct_fund": "% of Fund",
                  "deal_names": "Deals"}
    tbl_data = df16[tbl_cols].rename(columns=tbl_rename)
    for col in ["New Committed ($M)", "New Deployed ($M)",
                "Cumul. Committed ($M)", "Cumul. Deployed ($M)"]:
        tbl_data[col] = tbl_data[col].apply(lambda x: f"${x:.1f}M" if x else "—")
    tbl_data["% of Fund"] = tbl_data["% of Fund"].apply(lambda x: f"{x:.1f}%")

    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in tbl_data.columns],
        data=tbl_data.to_dict("records"),
        style_cell={"backgroundColor": C["surface"], "color": C["text"],
                    "fontFamily": "IBM Plex Mono, monospace", "fontSize": 11,
                    "padding": "8px 12px", "border": f"1px solid {C['border']}"},
        style_header={"backgroundColor": "#081624", "color": C["muted"],
                      "fontWeight": 600, "fontSize": 10, "letterSpacing": 1,
                      "textTransform": "uppercase", "border": f"1px solid {C['border']}"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#081624"}],
    )

    return html.Div([
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        html.Div(style={"height": 24}),
        table,
    ])


# ── Analytics tab ──────────────────────────────────────────────────────────────

def render_analytics_tab(deals, fund_size, target_twr):
    total = sum(d["commitment"] for d in deals)

    # 1. Required MOIC table by hold period
    hold_range = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7]
    req_rows = [{"Hold (y)": y, "Required MOIC": f"{required_moic(y, target_twr):.2f}x",
                 "Deals Near": ", ".join(d["name"].split()[-1] for d in deals
                                         if abs(d["hold_years"] - y) < 0.3) or "—"}
                for y in hold_range]

    req_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in req_rows[0]],
        data=req_rows,
        style_cell={"backgroundColor": C["surface"], "color": C["text"],
                    "fontFamily": "IBM Plex Mono, monospace", "fontSize": 11,
                    "padding": "8px 12px", "border": f"1px solid {C['border']}"},
        style_header={"backgroundColor": "#081624", "color": C["muted"],
                      "fontWeight": 600, "fontSize": 10, "letterSpacing": 1,
                      "textTransform": "uppercase", "border": f"1px solid {C['border']}"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#081624"}],
    )

    # 2. Return gap waterfall
    deal_labels = [d["name"].split()[:3] for d in deals]
    deal_labels = [" ".join(l) for l in deal_labels]
    ann_returns = [(required_ann_return(d["moic"], d["hold_years"]) or 0) for d in deals]
    gaps = [a - target_twr for a in ann_returns]
    colors = [C["green"] if g >= 0 else C["red"] for g in gaps]

    gap_fig = go.Figure(go.Bar(
        x=deal_labels, y=gaps,
        marker_color=colors,
        text=[f"{g:+.1f}%" for g in gaps],
        textposition="outside",
    ))
    gap_fig.add_hline(y=0, line_color=C["muted"], line_width=1)
    gap_fig.update_layout(**CHART_LAYOUT, title=f"Return Gap vs {target_twr}% Target",
                          height=300, yaxis_title="Gap (pp)")
    gap_fig.update_yaxes(gridcolor=C["border"])

    # 3. Portfolio composition donut charts
    type_vals = {t: sum(d["commitment"] for d in deals if d["type"] == t) for t in DEAL_TYPES}
    sector_vals = {}
    for d in deals:
        sector_vals[d["sector"]] = sector_vals.get(d["sector"], 0) + d["commitment"]

    donut_fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]],
                              subplot_titles=["By Type", "By Sector"])
    donut_fig.add_trace(go.Pie(labels=list(type_vals.keys()), values=list(type_vals.values()),
                                hole=0.55, marker_colors=[C["blue"], C["purple"]],
                                textfont=dict(color=C["text"])), row=1, col=1)
    donut_fig.add_trace(go.Pie(labels=list(sector_vals.keys()), values=list(sector_vals.values()),
                                hole=0.55, marker_colors=px.colors.qualitative.Dark24[:len(sector_vals)],
                                textfont=dict(color=C["text"])), row=1, col=2)
    donut_fig.update_layout(**CHART_LAYOUT, height=320,
                            legend=dict(bgcolor=C["surface"], bordercolor=C["border"]))

    # 4. MOIC sensitivity
    deltas = [-0.2, -0.1, 0.0, 0.1, 0.2]
    scen_twrs = []
    for delta in deltas:
        scen = [dict(**d, moic=max(1.0, d["moic"] + delta)) for d in deals]
        scen_twrs.append(portfolio_twr(scen) or 0)

    sens_fig = go.Figure(go.Bar(
        x=[f"MOIC {d:+.1f}x" for d in deltas],
        y=scen_twrs,
        marker_color=[C["green"] if t >= target_twr else C["red"] for t in scen_twrs],
        text=[f"{t:.1f}%" for t in scen_twrs],
        textposition="outside",
    ))
    sens_fig.add_hline(y=target_twr, line_dash="dash", line_color=C["sky"],
                       annotation_text=f"Target {target_twr}%", annotation_font_color=C["sky"])
    sens_fig.update_layout(**CHART_LAYOUT, title="MOIC Sensitivity — Impact on Portfolio TWR",
                           height=300, yaxis_title="Portfolio TWR (%)")
    sens_fig.update_yaxes(gridcolor=C["border"])

    card = lambda title, content: html.Div([
        section_header(title), content
    ], style={"background": C["surface"], "border": f"1px solid {C['border']}",
              "borderRadius": 8, "padding": 20})

    return html.Div([
        html.Div([
            html.Div([card(f"Required MOIC to Achieve {target_twr}% TWR by Hold Period", req_table)],
                     style={"flex": "0 0 340px"}),
            html.Div([
                dcc.Graph(figure=gap_fig, config={"displayModeBar": False}),
            ], style={"flex": 1, "background": C["surface"], "border": f"1px solid {C['border']}",
                      "borderRadius": 8}),
        ], style={"display": "flex", "gap": 20, "marginBottom": 20, "flexWrap": "wrap"}),
        html.Div([
            html.Div(dcc.Graph(figure=donut_fig, config={"displayModeBar": False}),
                     style={"flex": 1, "background": C["surface"], "border": f"1px solid {C['border']}",
                            "borderRadius": 8}),
            html.Div(dcc.Graph(figure=sens_fig, config={"displayModeBar": False}),
                     style={"flex": 1, "background": C["surface"], "border": f"1px solid {C['border']}",
                            "borderRadius": 8}),
        ], style={"display": "flex", "gap": 20, "flexWrap": "wrap"}),
    ])


# ── Add deal callback ──────────────────────────────────────────────────────────

@app.callback(
    Output("deals-store", "data"),
    Output("next-id-store", "data"),
    Output("add-deal-msg", "children"),
    Input("add-deal-btn", "n_clicks"),
    State("deals-store", "data"),
    State("next-id-store", "data"),
    State("new-name", "value"),
    State("new-type", "value"),
    State("new-sector", "value"),
    State("new-commit", "value"),
    State("new-moic", "value"),
    State("new-hold", "value"),
    State("new-deployq", "value"),
    State("new-deploy-rate", "value"),
    prevent_initial_call=True,
)
def add_deal(n_clicks, deals, next_id, name, dtype, sector, commit, moic, hold, deployq, deploy_rate):
    if not name or not commit or not moic or not hold:
        return deals, next_id, "⚠ Please fill in all required fields."
    new = dict(id=next_id, name=name, type=dtype or "Secondary",
               commitment=float(commit), moic=float(moic), hold_years=float(hold),
               deploy_q=int(deployq or 1), deployment_rate=float(deploy_rate or 100),
               sector=sector or "Diversified Credit")
    return deals + [new], next_id + 1, f"✓ Added: {name}"


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=8050)
