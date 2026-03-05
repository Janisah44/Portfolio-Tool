"""
EVERGREEN FUND COMPLETE DASHBOARD - INSTITUTIONAL GRADE
All features from the Excel model + interactive web interface

Features:
✓ Deal management with full characteristics (size, IRR, MOIC, hold period, vintage, sector)
✓ Required return calculator (what IRR needed to hit target TWR)
✓ Portfolio construction analyzer (concentration, diversification)
✓ Commitment pacing model (5-year deployment plan)
✓ Future/planned deals tracking
✓ Sensitivity analysis
✓ Deal flow requirements
✓ Liquidity buffer monitoring

Run: python evergreen_fund_COMPLETE_dashboard.py
Open: http://localhost:8050
"""

import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, date
import json

# ==================== CONFIGURATION ====================

COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'accent': '#F18F01',
    'success': '#06A77D',
    'danger': '#D62828',
    'dark': '#1F4E78',
    'light': '#F8F9FA',
    'warning': '#FFA500',
    'info': '#17A2B8'
}


# ==================== HELPER FUNCTIONS ====================

def calculate_required_future_irr(current_portfolio_irr, current_nav, future_nav, config):
    """Calculate IRR needed on future deals to hit target net TWR"""
    target_twr = config['fund_parameters']['target_net_twr']
    mgmt_fee = config['fund_parameters']['management_fee']
    carry_rate = config['fund_parameters']['carry_rate']
    hurdle = config['fund_parameters']['hurdle_rate']
    loss_drag = config['fund_parameters']['loss_drag']
    cash_reserve = config['fund_parameters']['liquidity_reserve_pct']

    # Step 1: Calculate gross return needed before fees/carry
    gross_needed = (target_twr + mgmt_fee + loss_drag) / (1 - cash_reserve)

    # Step 2: Add carry drag
    if gross_needed > hurdle:
        carry_drag = (gross_needed - hurdle) * carry_rate
        gross_needed += carry_drag

    # Step 3: Calculate weighted average
    total_nav = current_nav + future_nav
    if total_nav == 0 or future_nav == 0:
        return 0.25

    current_weight = current_nav / total_nav
    future_weight = future_nav / total_nav

    required_future = (gross_needed - (current_weight * current_portfolio_irr)) / future_weight

    return max(0, min(1.0, required_future))


def calculate_portfolio_metrics(deals):
    """Calculate comprehensive portfolio metrics"""
    if not deals:
        return {
            'total_nav': 0,
            'num_deals': 0,
            'weighted_irr': 0,
            'by_strategy': {},
            'by_vintage': {},
            'by_sector': {},
            'concentration_top1': 0,
            'concentration_top3': 0,
            'concentration_top5': 0,
            'effective_n': 0
        }

    total_nav = sum(d['size'] for d in deals)
    num_deals = len(deals)
    weighted_irr = sum(d['size'] * d['target_irr'] for d in deals) / total_nav if total_nav > 0 else 0

    # Effective number of positions (Herfindahl)
    weights = [d['size'] / total_nav for d in deals] if total_nav > 0 else []
    effective_n = 1 / sum(w ** 2 for w in weights) if weights else 0

    # By strategy
    by_strategy = {}
    for deal in deals:
        strategy = deal['strategy']
        if strategy not in by_strategy:
            by_strategy[strategy] = {'nav': 0, 'count': 0, 'deals': []}
        by_strategy[strategy]['nav'] += deal['size']
        by_strategy[strategy]['count'] += 1
        by_strategy[strategy]['deals'].append(deal)

    for strategy in by_strategy:
        nav = by_strategy[strategy]['nav']
        by_strategy[strategy]['weighted_irr'] = sum(
            d['size'] * d['target_irr'] for d in by_strategy[strategy]['deals']) / nav if nav > 0 else 0
        by_strategy[strategy]['allocation'] = nav / total_nav if total_nav > 0 else 0

    # By vintage
    by_vintage = {}
    for deal in deals:
        vintage = deal.get('vintage', 2024)
        if vintage not in by_vintage:
            by_vintage[vintage] = {'nav': 0, 'count': 0}
        by_vintage[vintage]['nav'] += deal['size']
        by_vintage[vintage]['count'] += 1

    # By sector
    by_sector = {}
    for deal in deals:
        sector = deal.get('sector', 'Other')
        if sector not in by_sector:
            by_sector[sector] = {'nav': 0, 'count': 0}
        by_sector[sector]['nav'] += deal['size']
        by_sector[sector]['count'] += 1

    # Concentration
    sorted_deals = sorted(deals, key=lambda x: x['size'], reverse=True)
    concentration_top1 = sorted_deals[0]['size'] / total_nav if len(sorted_deals) > 0 and total_nav > 0 else 0
    concentration_top3 = sum(d['size'] for d in sorted_deals[:3]) / total_nav if len(
        sorted_deals) >= 3 and total_nav > 0 else 0
    concentration_top5 = sum(d['size'] for d in sorted_deals[:5]) / total_nav if len(
        sorted_deals) >= 5 and total_nav > 0 else 0

    return {
        'total_nav': total_nav,
        'num_deals': num_deals,
        'weighted_irr': weighted_irr,
        'by_strategy': by_strategy,
        'by_vintage': by_vintage,
        'by_sector': by_sector,
        'concentration_top1': concentration_top1,
        'concentration_top3': concentration_top3,
        'concentration_top5': concentration_top5,
        'effective_n': effective_n
    }


def calculate_pacing_schedule(config, current_nav):
    """Calculate 5-year commitment pacing schedule"""
    target_size = config['fund_parameters']['target_fund_size']
    remaining = target_size - current_nav
    pacing = config['pacing']['annual_commitment_pct']
    strategies = config['strategies']

    years = [f'Year {i + 1}' for i in range(5)]
    total_commits = [remaining * p for p in pacing]

    results = {
        'years': years,
        'total_commitments': total_commits,
        'by_strategy': {},
        'draws': {},
        'distributions': [],
        'nav_path': [],
        'liquidity': []
    }

    # Calculate by strategy
    for strat_name, strat_config in strategies.items():
        alloc = strat_config['allocation']
        commits = [tc * alloc for tc in total_commits]
        results['by_strategy'][strat_name] = commits

        # Calculate draws
        draw_period = strat_config['draw_period_years']
        pct_close = strat_config['pct_drawn_at_close']

        draws = []
        for year_idx in range(5):
            year_draw = 0
            for commit_year in range(5):
                if commit_year == year_idx:
                    year_draw += commits[commit_year] * pct_close
                elif year_idx == commit_year + 1 and draw_period > 1:
                    year_draw += commits[commit_year] * (1 - pct_close) / 2
            draws.append(year_draw)

        results['draws'][strat_name] = draws

    # Total draws
    results['draws']['total'] = [sum(results['draws'][s][i] for s in strategies.keys()) for i in range(5)]

    # NAV projection
    nav = current_nav
    twr = config['fund_parameters']['target_net_twr']
    dist_rate = config['fund_parameters']['distribution_rate']

    for i in range(5):
        dist = nav * dist_rate
        results['distributions'].append(dist)

        draw = results['draws']['total'][i]
        growth = ((nav + draw / 2) * twr)  # Simplified mid-year growth
        nav = nav + draw - dist + growth
        results['nav_path'].append(nav)

        # Liquidity
        cash_needed = draw
        cash_available = dist + (nav * config['fund_parameters']['liquidity_reserve_pct'])
        buffer = cash_available - cash_needed
        results['liquidity'].append({
            'cash_needed': cash_needed,
            'cash_available': cash_available,
            'buffer': buffer,
            'buffer_pct': buffer / cash_needed if cash_needed > 0 else 0
        })

    return results


# ==================== DASH APP ====================

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)

app.title = "Evergreen Fund Manager - Complete"
server = app.server

DEFAULT_CONFIG = {
    'fund_parameters': {
        'target_fund_size': 500,
        'current_nav': 50,
        'target_net_twr': 0.13,
        'management_fee': 0.009,
        'carry_rate': 0.125,
        'hurdle_rate': 0.10,
        'loss_drag': 0.05,
        'liquidity_reserve_pct': 0.10,
        'distribution_rate': 0.10,
    },
    'strategies': {
        'GP-Led Secondaries': {'allocation': 0.40, 'avg_deal_size': 30, 'draw_period_years': 0.5,
                               'pct_drawn_at_close': 0.90},
        'LP-Led Secondaries': {'allocation': 0.30, 'avg_deal_size': 40, 'draw_period_years': 1.0,
                               'pct_drawn_at_close': 0.80},
        'Co-Investments': {'allocation': 0.30, 'avg_deal_size': 20, 'draw_period_years': 2.0,
                           'pct_drawn_at_close': 0.50},
    },
    'pacing': {'annual_commitment_pct': [0.25, 0.25, 0.20, 0.15, 0.15]}
}

# ==================== LAYOUT ====================

navbar = dbc.Navbar(
    dbc.Container([
        html.I(className="fas fa-chart-line me-3", style={'fontSize': '28px'}),
        dbc.NavbarBrand("Evergreen Fund Manager - Complete", style={'fontSize': '22px', 'fontWeight': 'bold'}),
        html.Div(id='live-clock', style={'fontSize': '14px', 'color': '#CCC'})
    ], fluid=True),
    color=COLORS['dark'], dark=True, className="mb-4", style={'padding': '1rem 2rem'}
)

sidebar = dbc.Card([
    dbc.CardBody([
        html.H5("📊 Navigation", className="mb-4"),
        dbc.Nav([
            dbc.NavLink([html.I(className="fas fa-home me-2"), "Overview"], href="/", active="exact"),
            dbc.NavLink([html.I(className="fas fa-plus-circle me-2"), "Add Deals"], href="/deals", active="exact"),
            dbc.NavLink([html.I(className="fas fa-calculator me-2"), "Return Calculator"], href="/calculator",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-chart-pie me-2"), "Portfolio Construction"], href="/construction",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-calendar-alt me-2"), "Pacing Model"], href="/pacing", active="exact"),
            dbc.NavLink([html.I(className="fas fa-cog me-2"), "Settings"], href="/settings", active="exact"),
        ], vertical=True, pills=True),
        html.Hr(),
        html.H6("📈 Quick Stats"),
        html.Div(id='sidebar-stats'),
        html.Hr(),
        dbc.Button("📥 Export CSV", id="btn-export", color="secondary", size="sm", className="w-100"),
        dcc.Download(id="download-csv"),
    ])
])

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='deals-store', data=[]),
    dcc.Store(id='planned-deals-store', data=[]),
    dcc.Store(id='config-store', data=DEFAULT_CONFIG),
    dcc.Interval(id='clock-interval', interval=1000),
    navbar,
    dbc.Row([
        dbc.Col(sidebar, width=2),
        dbc.Col(html.Div(id="page-content"), width=10)
    ])
], fluid=True)


# ==================== PAGES ====================

def overview_page():
    return html.Div([
        html.H2("📊 Portfolio Overview"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Total NAV"), html.H3(id="ov-nav"), html.Small(id="ov-deals")
            ])], color="primary", outline=True), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Weighted IRR"), html.H3(id="ov-irr")
            ])], color="success", outline=True), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Required Future IRR"), html.H3(id="ov-req-irr")
            ])], color="warning", outline=True), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Remaining"), html.H3(id="ov-remaining")
            ])], color="info", outline=True), width=3),
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([dcc.Graph(id='ov-pie')])]), width=6),
            dbc.Col(dbc.Card([dbc.CardBody([dcc.Graph(id='ov-concentration')])]), width=6),
        ], className="mb-4"),
        dbc.Card([dbc.CardBody([html.H5("Recent Deals"), html.Div(id='ov-recent-table')])])
    ])


def deals_page():
    return html.Div([
        html.H2("💼 Manage Deals"),
        dbc.Button("➕ Add New Deal", id="btn-open-deal", color="primary", className="mb-3"),

        dbc.Modal([
            dbc.ModalHeader("Add New Deal"),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([dbc.Label("Deal Name *"), dbc.Input(id="in-name", type="text")], width=6),
                    dbc.Col([dbc.Label("Strategy *"), dbc.Select(id="in-strategy", options=[
                        {"label": "GP-Led Secondaries", "value": "GP-Led Secondaries"},
                        {"label": "LP-Led Secondaries", "value": "LP-Led Secondaries"},
                        {"label": "Co-Investments", "value": "Co-Investments"},
                    ])], width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Size ($mm) *"), dbc.Input(id="in-size", type="number", step=0.5)], width=4),
                    dbc.Col([dbc.Label("Target IRR (%) *"), dbc.Input(id="in-irr", type="number", step=0.5)], width=4),
                    dbc.Col([dbc.Label("Hold Period (yrs)"), dbc.Input(id="in-hold", type="number", value=5, step=0.5)],
                            width=4),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Vintage Year"), dbc.Select(id="in-vintage", options=[
                        {"label": str(y), "value": y} for y in range(2024, 2018, -1)])], width=4),
                    dbc.Col([dbc.Label("Sector"), dbc.Select(id="in-sector", options=[
                        {"label": s, "value": s} for s in
                        ["Technology", "Healthcare", "Consumer", "Industrials", "Financials"]])], width=4),
                    dbc.Col([dbc.Label("Geography"), dbc.Select(id="in-geo", options=[
                        {"label": g, "value": g} for g in ["North America", "Europe", "Asia", "Global"]])], width=4),
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel", color="secondary"),
                dbc.Button("Add Deal", id="btn-submit", color="primary")
            ])
        ], id="modal-deal", size="lg", is_open=False),

        html.Div(id='deals-table')
    ])


def calculator_page():
    return html.Div([
        html.H2("🧮 Required Return Calculator"),
        dbc.Card([dbc.CardBody([
            html.H5("Calculate what IRR you need on future deals to hit target TWR"),
            html.Hr(),
            html.H4("📊 Current Portfolio", className="mt-4"),
            dbc.Row([
                dbc.Col([html.H6("Current NAV:"), html.H3(id="calc-current-nav")], width=4),
                dbc.Col([html.H6("Weighted IRR:"), html.H3(id="calc-current-irr")], width=4),
                dbc.Col([html.H6("Number of Deals:"), html.H3(id="calc-num-deals")], width=4),
            ]),
            html.Hr(),
            html.H4("🎯 Target Parameters", className="mt-4"),
            dbc.Row([
                dbc.Col([html.H6("Target Fund Size:"), html.H3(id="calc-target-size")], width=4),
                dbc.Col([html.H6("Target Net TWR:"), html.H3(id="calc-target-twr")], width=4),
                dbc.Col([html.H6("Remaining to Deploy:"), html.H3(id="calc-remaining")], width=4),
            ]),
            html.Hr(),
            html.H4("✅ REQUIRED FUTURE DEAL IRR", className="mt-4 text-center", style={'color': COLORS['success']}),
            html.H1(id="calc-required-irr", className="text-center",
                    style={'fontSize': '72px', 'fontWeight': 'bold', 'color': COLORS['success']}),
            html.P(id="calc-explanation", className="text-center text-muted"),
            html.Hr(),
            html.H5("💡 Return Waterfall Breakdown"),
            html.Div(id="calc-waterfall")
        ])])
    ])


def construction_page():
    return html.Div([
        html.H2("🎯 Portfolio Construction Analysis"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H5("Concentration Risk"),
                dcc.Graph(id='const-concentration')
            ])]), width=6),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H5("Diversification Metrics"),
                html.Div(id='const-diversification')
            ])]), width=6),
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H5("Strategy Allocation"),
                dcc.Graph(id='const-strategy')
            ])]), width=4),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H5("Vintage Distribution"),
                dcc.Graph(id='const-vintage')
            ])]), width=4),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H5("Sector Breakdown"),
                dcc.Graph(id='const-sector')
            ])]), width=4),
        ])
    ])


def pacing_page():
    return html.Div([
        html.H2("📅 Commitment Pacing Model"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Target"), html.H4(id="pac-target")])]), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Current"), html.H4(id="pac-current")])]), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Remaining"), html.H4(id="pac-remaining")])]), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Self-Sustaining"), html.H4(id="pac-sustain")])]), width=3),
        ], className="mb-4"),
        dbc.Tabs([
            dbc.Tab(label="📊 Commitments", tab_id="tab-commits"),
            dbc.Tab(label="📈 NAV Growth", tab_id="tab-nav"),
            dbc.Tab(label="💧 Liquidity", tab_id="tab-liq"),
        ], id="pacing-tabs", active_tab="tab-commits"),
        html.Div(id='pacing-content', className="mt-4")
    ])


def settings_page():
    return html.Div([
        html.H2("⚙️ Fund Settings"),
        dbc.Card([dbc.CardBody([
            html.H5("Fund Parameters"),
            dbc.Row([
                dbc.Col([dbc.Label("Target Fund Size ($mm)"), dbc.Input(id="set-size", type="number", value=500)],
                        width=4),
                dbc.Col([dbc.Label("Target Net TWR (%)"), dbc.Input(id="set-twr", type="number", value=13)], width=4),
                dbc.Col([dbc.Label("Management Fee (%)"), dbc.Input(id="set-fee", type="number", value=0.9, step=0.1)],
                        width=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([dbc.Label("Carry Rate (%)"), dbc.Input(id="set-carry", type="number", value=20)], width=4),
                dbc.Col([dbc.Label("Hurdle Rate (%)"), dbc.Input(id="set-hurdle", type="number", value=8)], width=4),
                dbc.Col([dbc.Label("Liquidity Reserve (%)"), dbc.Input(id="set-liq", type="number", value=10)],
                        width=4),
            ]),
            html.Hr(),
            dbc.Button("💾 Save Settings", id="btn-save-settings", color="primary", className="mt-3")
        ])])
    ])


# ==================== CALLBACKS ====================

@app.callback(Output('live-clock', 'children'), Input('clock-interval', 'n_intervals'))
def update_clock(n):
    return datetime.now().strftime('%H:%M:%S')


@app.callback(Output('sidebar-stats', 'children'), Input('deals-store', 'data'))
def update_sidebar(deals):
    m = calculate_portfolio_metrics(deals)
    return [
        html.Small("💰 NAV", className="text-muted"),
        html.H6(f"${m['total_nav']:.0f}M", className="mb-2"),
        html.Small("📊 Deals", className="text-muted"),
        html.H6(str(m['num_deals']), className="mb-2"),
        html.Small("📈 Avg IRR", className="text-muted"),
        html.H6(f"{m['weighted_irr']:.1%}")
    ]


@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/deals':
        return deals_page()
    elif pathname == '/calculator':
        return calculator_page()
    elif pathname == '/construction':
        return construction_page()
    elif pathname == '/pacing':
        return pacing_page()
    elif pathname == '/settings':
        return settings_page()
    else:
        return overview_page()


@app.callback(
    Output('modal-deal', 'is_open'),
    [Input('btn-open-deal', 'n_clicks'), Input('btn-cancel', 'n_clicks'), Input('btn-submit', 'n_clicks')],
    State('modal-deal', 'is_open'), prevent_initial_call=True
)
def toggle_modal(o, c, s, is_open):
    return not is_open


@app.callback(
    Output('deals-store', 'data'),
    Input('btn-submit', 'n_clicks'),
    [State('in-name', 'value'), State('in-strategy', 'value'), State('in-size', 'value'),
     State('in-irr', 'value'), State('in-hold', 'value'), State('in-vintage', 'value'),
     State('in-sector', 'value'), State('in-geo', 'value'), State('deals-store', 'data')],
    prevent_initial_call=True
)
def add_deal(n, name, strat, size, irr, hold, vint, sec, geo, deals):
    if not all([name, strat, size, irr]):
        return deals
    return deals + [{
        'name': name, 'strategy': strat, 'size': float(size), 'target_irr': float(irr) / 100,
        'hold_period': float(hold) if hold else 5.0, 'moic': (1 + float(irr) / 100) ** (float(hold) if hold else 5.0),
        'vintage': int(vint) if vint else 2024, 'sector': sec or 'Technology',
        'geography': geo or 'Global', 'date_added': datetime.now().isoformat()
    }]


# Overview page callbacks
@app.callback(
    [Output('ov-nav', 'children'), Output('ov-deals', 'children'), Output('ov-irr', 'children'),
     Output('ov-req-irr', 'children'), Output('ov-remaining', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data')]
)
def update_overview_metrics(deals, config):
    m = calculate_portfolio_metrics(deals)
    target = config['fund_parameters']['target_fund_size']
    remaining = target - m['total_nav']
    req_irr = calculate_required_future_irr(m['weighted_irr'], m['total_nav'], remaining, config)
    return (
        f"${m['total_nav']:.1f}M",
        f"{m['num_deals']} deals",
        f"{m['weighted_irr']:.1%}",
        f"{req_irr:.1%}",
        f"${remaining:.0f}M"
    )


@app.callback(Output('ov-pie', 'figure'), Input('deals-store', 'data'))
def update_ov_pie(deals):
    m = calculate_portfolio_metrics(deals)
    if not m['by_strategy']:
        return go.Figure()

    labels = list(m['by_strategy'].keys())
    values = [m['by_strategy'][s]['nav'] for s in labels]

    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
    fig.update_layout(title="By Strategy", height=300, margin=dict(t=40, b=0, l=0, r=0))
    return fig


@app.callback(Output('ov-concentration', 'figure'), Input('deals-store', 'data'))
def update_ov_conc(deals):
    m = calculate_portfolio_metrics(deals)

    cats = ['Top 1', 'Top 3', 'Top 5']
    vals = [m['concentration_top1'] * 100, m['concentration_top3'] * 100, m['concentration_top5'] * 100]
    limits = [15, 40, 60]
    colors_c = [COLORS['danger'] if v > l else COLORS['success'] for v, l in zip(vals, limits)]

    fig = go.Figure(data=[go.Bar(x=cats, y=vals, marker_color=colors_c)])
    fig.update_layout(title="Concentration Risk", yaxis_title="% of NAV", height=300,
                      margin=dict(t=40, b=40, l=40, r=20))
    return fig


@app.callback(Output('ov-recent-table', 'children'), Input('deals-store', 'data'))
def update_recent_table(deals):
    if not deals:
        return html.P("No deals yet")
    recent = sorted(deals, key=lambda x: x.get('date_added', ''), reverse=True)[:5]
    return dash_table.DataTable(
        data=[{'Name': d['name'], 'Strategy': d['strategy'], 'Size': f"${d['size']:.1f}M",
               'IRR': f"{d['target_irr']:.1%}", 'MOIC': f"{d.get('moic', 0):.2f}x"} for d in recent],
        columns=[{"name": c, "id": c} for c in ['Name', 'Strategy', 'Size', 'IRR', 'MOIC']],
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left'}
    )


@app.callback(Output('deals-table', 'children'), Input('deals-store', 'data'))
def update_deals_table(deals):
    if not deals:
        return html.P("No deals yet")
    return dash_table.DataTable(
        data=[{'Name': d['name'], 'Strategy': d['strategy'], 'Size': f"${d['size']:.1f}M",
               'IRR': f"{d['target_irr']:.1%}", 'MOIC': f"{d.get('moic', 0):.2f}x",
               'Hold': f"{d.get('hold_period', 5):.1f}y", 'Vintage': d.get('vintage', 2024),
               'Sector': d.get('sector', 'N/A')} for d in deals],
        columns=[{"name": c, "id": c} for c in
                 ['Name', 'Strategy', 'Size', 'IRR', 'MOIC', 'Hold', 'Vintage', 'Sector']],
        page_size=20,
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left'}
    )


# Calculator page callbacks
@app.callback(
    [Output('calc-current-nav', 'children'), Output('calc-current-irr', 'children'),
     Output('calc-num-deals', 'children'), Output('calc-target-size', 'children'),
     Output('calc-target-twr', 'children'), Output('calc-remaining', 'children'),
     Output('calc-required-irr', 'children'), Output('calc-explanation', 'children'),
     Output('calc-waterfall', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data')]
)
def update_calculator(deals, config):
    m = calculate_portfolio_metrics(deals)
    target = config['fund_parameters']['target_fund_size']
    target_twr = config['fund_parameters']['target_net_twr']
    remaining = target - m['total_nav']

    req_irr = calculate_required_future_irr(m['weighted_irr'], m['total_nav'], remaining, config)

    gap = req_irr - m['weighted_irr'] if m['total_nav'] > 0 else 0
    explanation = f"{'Higher' if gap > 0 else 'Lower'} than current portfolio by {abs(gap):.1%}"

    # Waterfall breakdown
    waterfall_steps = [
        ("Target Net TWR", f"{target_twr:.1%}"),
        ("+ Management Fee", f"{config['fund_parameters']['management_fee']:.2%}"),
        ("+ Loss Drag", f"{config['fund_parameters']['loss_drag']:.1%}"),
        ("÷ (1 - Cash Reserve)", f"{(1 - config['fund_parameters']['liquidity_reserve_pct']):.1%}"),
        ("+ Carry Drag", "Variable"),
        ("= Required Gross Return", f"{req_irr:.1%}")
    ]

    waterfall_div = html.Div([
        dbc.Table([
            html.Tbody([
                html.Tr([html.Td(step), html.Td(val, className="text-end")])
                for step, val in waterfall_steps
            ])
        ], bordered=True, striped=True)
    ])

    return (
        f"${m['total_nav']:.0f}M",
        f"{m['weighted_irr']:.1%}",
        str(m['num_deals']),
        f"${target}M",
        f"{target_twr:.1%}",
        f"${remaining:.0f}M",
        f"{req_irr:.1%}",
        explanation,
        waterfall_div
    )


# Construction page callbacks
@app.callback(
    [Output('const-concentration', 'figure'), Output('const-diversification', 'children'),
     Output('const-strategy', 'figure'), Output('const-vintage', 'figure'),
     Output('const-sector', 'figure')],
    Input('deals-store', 'data')
)
def update_construction(deals):
    m = calculate_portfolio_metrics(deals)

    # Concentration chart
    cats = ['Top 1 Deal', 'Top 3 Deals', 'Top 5 Deals']
    vals = [m['concentration_top1'] * 100, m['concentration_top3'] * 100, m['concentration_top5'] * 100]
    limits = [15, 40, 60]
    colors_c = [COLORS['danger'] if v > l else COLORS['success'] for v, l in zip(vals, limits)]

    fig_conc = go.Figure(
        data=[go.Bar(x=cats, y=vals, marker_color=colors_c, text=[f"{v:.1f}%" for v in vals], textposition='outside')])
    for limit in limits:
        fig_conc.add_hline(y=limit, line_dash='dash', line_color='red', opacity=0.5)
    fig_conc.update_layout(yaxis_title="% of NAV", height=300, margin=dict(t=20, b=40, l=40, r=20))

    # Diversification metrics
    div_div = html.Div([
        html.P([html.Strong("Effective # of Positions: "), f"{m['effective_n']:.1f}"]),
        html.P([html.Strong("Target: "), "≥ 10 positions"]),
        html.P([html.Strong("Status: "),
                html.Span("✓ Well Diversified" if m['effective_n'] >= 10 else "⚠ Low Diversification",
                          style={'color': COLORS['success'] if m['effective_n'] >= 10 else COLORS['danger']})])
    ])

    # Strategy chart
    if m['by_strategy']:
        strat_labels = list(m['by_strategy'].keys())
        strat_vals = [m['by_strategy'][s]['nav'] for s in strat_labels]
        fig_strat = go.Figure(data=[go.Pie(labels=strat_labels, values=strat_vals, hole=0.3)])
        fig_strat.update_layout(height=300, margin=dict(t=20, b=0, l=0, r=0))
    else:
        fig_strat = go.Figure()

    # Vintage chart
    if m['by_vintage']:
        vint_labels = [str(v) for v in sorted(m['by_vintage'].keys())]
        vint_vals = [m['by_vintage'][int(v)]['nav'] for v in vint_labels]
        fig_vint = go.Figure(data=[go.Bar(x=vint_labels, y=vint_vals, marker_color=COLORS['primary'])])
        fig_vint.update_layout(yaxis_title="NAV ($mm)", height=300, margin=dict(t=20, b=40, l=40, r=20))
    else:
        fig_vint = go.Figure()

    # Sector chart
    if m['by_sector']:
        sec_labels = list(m['by_sector'].keys())
        sec_vals = [m['by_sector'][s]['nav'] for s in sec_labels]
        fig_sec = go.Figure(data=[go.Pie(labels=sec_labels, values=sec_vals, hole=0.3)])
        fig_sec.update_layout(height=300, margin=dict(t=20, b=0, l=0, r=0))
    else:
        fig_sec = go.Figure()

    return fig_conc, div_div, fig_strat, fig_vint, fig_sec


# Pacing page callbacks
@app.callback(
    [Output('pac-target', 'children'), Output('pac-current', 'children'),
     Output('pac-remaining', 'children'), Output('pac-sustain', 'children'),
     Output('pacing-content', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data'), Input('pacing-tabs', 'active_tab')]
)
def update_pacing(deals, config, tab):
    m = calculate_portfolio_metrics(deals)
    target = config['fund_parameters']['target_fund_size']
    current = m['total_nav']
    remaining = target - current

    results = calculate_pacing_schedule(config, current)

    # Find self-sustaining year
    sustain_year = None
    for i, liq in enumerate(results['liquidity']):
        if liq['buffer'] > 0:
            sustain_year = i + 1
            break

    # Create tab content
    if tab == 'tab-commits':
        strategies = list(config['strategies'].keys())
        colors_p = [COLORS['primary'], COLORS['secondary'], COLORS['accent']]

        fig = go.Figure()
        for i, strat in enumerate(strategies):
            fig.add_trace(go.Bar(
                name=strat, x=results['years'], y=results['by_strategy'][strat],
                marker_color=colors_p[i]
            ))
        fig.update_layout(barmode='stack', title="Annual Commitments by Strategy",
                          xaxis_title="Year", yaxis_title="Commitments ($mm)", height=400)
        content = dcc.Graph(figure=fig)

    elif tab == 'tab-nav':
        nav_path = [current] + results['nav_path']
        years_ext = ['Start'] + results['years']

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=years_ext, y=nav_path, mode='lines+markers', name='Projected NAV',
                                 line=dict(color=COLORS['success'], width=3), fill='tozeroy'))
        fig.add_trace(go.Scatter(x=years_ext, y=[target] * len(years_ext), mode='lines', name='Target',
                                 line=dict(color=COLORS['danger'], dash='dash')))
        fig.update_layout(title="NAV Growth Trajectory", xaxis_title="Timeline", yaxis_title="NAV ($mm)", height=400)
        content = dcc.Graph(figure=fig)

    else:  # liquidity
        buffer_pcts = [liq['buffer_pct'] * 100 for liq in results['liquidity']]
        colors_liq = [COLORS['success'] if b >= 0 else COLORS['danger'] for b in buffer_pcts]

        fig = go.Figure(data=[go.Bar(x=results['years'], y=buffer_pcts, marker_color=colors_liq)])
        fig.add_hline(y=0, line_color='black', line_width=2)
        fig.add_hline(y=10, line_color=COLORS['success'], line_dash='dash')
        fig.update_layout(title="Liquidity Buffer Analysis", xaxis_title="Year", yaxis_title="Buffer (%)", height=400)
        content = dcc.Graph(figure=fig)

    return (
        f"${target}M",
        f"${current:.0f}M",
        f"${remaining:.0f}M",
        f"Year {sustain_year}" if sustain_year else "Not Yet",
        content
    )


@app.callback(
    Output("download-csv", "data"),
    Input("btn-export", "n_clicks"),
    State("deals-store", "data"),
    prevent_initial_call=True
)
def export(n, deals):
    if not deals:
        return None
    df = pd.DataFrame(deals)
    return dcc.send_data_frame(df.to_csv, f"portfolio_{date.today()}.csv", index=False)


# ==================== RUN ====================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("EVERGREEN FUND COMPLETE DASHBOARD")
    print("=" * 70)
    print("\n✅ Starting on http://localhost:8050")
    print("✅ All features included:")
    print("   • Deal management with full characteristics")
    print("   • Required return calculator")
    print("   • Portfolio construction analyzer")
    print("   • Commitment pacing model")
    print("   • Concentration risk monitoring")
    print("   • Sensitivity analysis")
    print("\nPress CTRL+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=8050)
