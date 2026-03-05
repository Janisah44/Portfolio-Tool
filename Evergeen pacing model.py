"""
EVERGREEN FUND INTERACTIVE DASHBOARD
Built with Plotly Dash for professional portfolio management

Run with: python dash_dashboard.py
Access at: http://localhost:8050
"""

import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, date
import json
from evergreen_pacing_model import EvergreenCommitmentPacingModel

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)

app.title = "Evergreen Fund Manager"

# Global data storage (in production, use database or file storage)
deals_data = []
config_data = EvergreenCommitmentPacingModel.default_config()

# Color scheme
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'accent': '#F18F01',
    'success': '#06A77D',
    'danger': '#D62828',
    'dark': '#1F4E78',
    'light': '#F8F9FA'
}


# ========== HELPER FUNCTIONS ==========

def calculate_portfolio_metrics(deals):
    """Calculate portfolio metrics from deals list"""
    if not deals:
        return {
            'total_nav': 0,
            'num_deals': 0,
            'weighted_irr': 0,
            'by_strategy': {}
        }

    total_nav = sum(d['size'] for d in deals)
    num_deals = len(deals)
    weighted_irr = sum(d['size'] * d['target_irr'] for d in deals) / total_nav if total_nav > 0 else 0

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

    return {
        'total_nav': total_nav,
        'num_deals': num_deals,
        'weighted_irr': weighted_irr,
        'by_strategy': by_strategy
    }


def create_commitment_waterfall(model_results):
    """Create commitment waterfall chart"""
    strategies = list(config_data['strategies'].keys())
    years = model_results['years']

    fig = go.Figure()

    colors = [COLORS['primary'], COLORS['secondary'], COLORS['accent']]

    for i, strategy in enumerate(strategies):
        fig.add_trace(go.Bar(
            name=strategy,
            x=years,
            y=model_results['commitments'][strategy],
            marker_color=colors[i],
            hovertemplate='<b>%{x}</b><br>%{fullData.name}: $%{y:.1f}M<extra></extra>'
        ))

    fig.update_layout(
        barmode='stack',
        title='Annual Commitment Pacing by Strategy',
        xaxis_title='Year',
        yaxis_title='Commitments ($mm)',
        font=dict(size=12),
        hovermode='x unified',
        plot_bgcolor='white',
        height=400
    )

    return fig


def create_nav_trajectory(model_results, config):
    """Create NAV trajectory chart"""
    nav_path = [config['fund_parameters']['current_nav']] + model_results['nav_projection']
    years_extended = ['Start'] + model_results['years']
    target = config['fund_parameters']['target_fund_size']

    fig = go.Figure()

    # Area under NAV
    fig.add_trace(go.Scatter(
        x=years_extended,
        y=nav_path,
        fill='tozeroy',
        mode='lines+markers',
        name='Projected NAV',
        line=dict(color=COLORS['success'], width=3),
        marker=dict(size=10, color='white', line=dict(color=COLORS['success'], width=3)),
        hovertemplate='<b>%{x}</b><br>NAV: $%{y:.1f}M<extra></extra>'
    ))

    # Target line
    fig.add_trace(go.Scatter(
        x=years_extended,
        y=[target] * len(years_extended),
        mode='lines',
        name=f'Target (${target}M)',
        line=dict(color=COLORS['danger'], width=2, dash='dash'),
        hovertemplate='Target: $%{y:.0f}M<extra></extra>'
    ))

    fig.update_layout(
        title='NAV Growth Trajectory - Path to Target',
        xaxis_title='Timeline',
        yaxis_title='NAV ($mm)',
        font=dict(size=12),
        hovermode='x unified',
        plot_bgcolor='white',
        height=400,
        showlegend=True
    )

    return fig


def create_liquidity_buffer(model_results):
    """Create liquidity buffer chart"""
    years = model_results['years']
    liq = model_results['liquidity_analysis']

    buffer_pcts = [liq[year]['buffer_pct'] * 100 for year in years]
    colors_buffer = [COLORS['success'] if b >= 0 else COLORS['danger'] for b in buffer_pcts]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=years,
        y=buffer_pcts,
        marker_color=colors_buffer,
        text=[f"{b:.1f}%" for b in buffer_pcts],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Buffer: %{y:.1f}%<extra></extra>'
    ))

    # Zero line
    fig.add_hline(y=0, line_color='black', line_width=2)

    # 10% target line
    fig.add_hline(y=10, line_color=COLORS['success'], line_width=2, line_dash='dash',
                  annotation_text="10% Target", annotation_position="right")

    fig.update_layout(
        title='Liquidity Buffer Analysis by Year',
        xaxis_title='Year',
        yaxis_title='Liquidity Buffer (%)',
        font=dict(size=12),
        plot_bgcolor='white',
        height=400
    )

    return fig


def create_strategy_pie(metrics):
    """Create strategy allocation pie chart"""
    if not metrics['by_strategy']:
        return go.Figure()

    strategies = list(metrics['by_strategy'].keys())
    navs = [metrics['by_strategy'][s]['nav'] for s in strategies]
    colors = [COLORS['primary'], COLORS['secondary'], COLORS['accent'], COLORS['success'], COLORS['danger']][
        :len(strategies)]

    fig = go.Figure(data=[go.Pie(
        labels=strategies,
        values=navs,
        hole=0.4,
        marker_colors=colors,
        textinfo='label+percent',
        textfont_size=12,
        hovertemplate='<b>%{label}</b><br>$%{value:.1f}M<br>%{percent}<extra></extra>'
    )])

    fig.update_layout(
        title='Portfolio Allocation by Strategy',
        font=dict(size=12),
        height=350,
        showlegend=False
    )

    return fig


# ========== LAYOUT COMPONENTS ==========

# Navbar
navbar = dbc.Navbar(
    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.I(className="fas fa-briefcase me-2", style={'fontSize': '24px'}),
                dbc.NavbarBrand("Evergreen Fund Manager", className="ms-2",
                                style={'fontSize': '20px', 'fontWeight': 'bold'})
            ], width="auto"),
        ], align="center"),
        dbc.Row([
            dbc.Col([
                html.Div(id='live-clock', style={'fontSize': '14px', 'color': '#6c757d'})
            ])
        ])
    ], fluid=True),
    color=COLORS['dark'],
    dark=True,
    className="mb-4"
)

# Sidebar
sidebar = dbc.Card([
    dbc.CardBody([
        html.H5("Navigation", className="card-title mb-4"),
        dbc.Nav([
            dbc.NavLink([
                html.I(className="fas fa-home me-2"),
                "Overview"
            ], href="/", active="exact", id="nav-overview"),
            dbc.NavLink([
                html.I(className="fas fa-folder-plus me-2"),
                "Manage Deals"
            ], href="/deals", active="exact", id="nav-deals"),
            dbc.NavLink([
                html.I(className="fas fa-chart-line me-2"),
                "Pacing Model"
            ], href="/pacing", active="exact", id="nav-pacing"),
            dbc.NavLink([
                html.I(className="fas fa-cog me-2"),
                "Settings"
            ], href="/settings", active="exact", id="nav-settings"),
        ], vertical=True, pills=True),

        html.Hr(),

        html.H6("Quick Stats", className="mt-4 mb-3"),
        html.Div(id='sidebar-stats'),

        html.Hr(),

        html.H6("Data Management", className="mt-4 mb-3"),
        dbc.Button([
            html.I(className="fas fa-download me-2"),
            "Export CSV"
        ], id="btn-export", color="secondary", size="sm", className="w-100 mb-2"),
        dcc.Download(id="download-csv"),

        dcc.Upload(
            id='upload-csv',
            children=dbc.Button([
                html.I(className="fas fa-upload me-2"),
                "Import CSV"
            ], color="secondary", size="sm", className="w-100"),
            multiple=False
        ),
    ])
], className="h-100")

# Main content area
content = html.Div(id="page-content", style={'minHeight': '80vh'})

# App layout
app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='deals-store', data=[]),
    dcc.Store(id='config-store', data=config_data),
    dcc.Interval(id='clock-interval', interval=1000, n_intervals=0),

    navbar,

    dbc.Row([
        dbc.Col(sidebar, width=2, className="pe-0"),
        dbc.Col(content, width=10)
    ], className="g-0")
], fluid=True)


# ========== PAGE LAYOUTS ==========

def overview_layout():
    return dbc.Container([
        html.H2("Portfolio Overview", className="mb-4"),

        # Metrics cards
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Total Portfolio NAV", className="text-muted"),
                    html.H3(id="metric-total-nav", className="mb-0"),
                    html.Small(id="metric-num-deals", className="text-muted")
                ])
            ], color="primary", outline=True), width=3),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Weighted Avg IRR", className="text-muted"),
                    html.H3(id="metric-weighted-irr", className="mb-0"),
                    html.Small("Portfolio Level", className="text-muted")
                ])
            ], color="success", outline=True), width=3),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Required Future IRR", className="text-muted"),
                    html.H3(id="metric-required-irr", className="mb-0"),
                    html.Small(id="metric-irr-gap", className="text-muted")
                ])
            ], color="warning", outline=True), width=3),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Remaining to Deploy", className="text-muted"),
                    html.H3(id="metric-remaining", className="mb-0"),
                    html.Small(id="metric-remaining-pct", className="text-muted")
                ])
            ], color="info", outline=True), width=3),
        ], className="mb-4"),

        # Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='overview-pie-chart')
                    ])
                ])
            ], width=6),

            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Strategy Breakdown", className="card-title"),
                        html.Div(id='strategy-breakdown')
                    ])
                ])
            ], width=6)
        ], className="mb-4"),

        # Recent deals
        dbc.Card([
            dbc.CardBody([
                html.H5("Recent Deals", className="card-title mb-3"),
                html.Div(id='recent-deals-table')
            ])
        ])
    ], fluid=True)


def deals_layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col(html.H2("Deal Management"), width=8),
            dbc.Col([
                dbc.Button([
                    html.I(className="fas fa-plus me-2"),
                    "Add New Deal"
                ], id="btn-open-add-deal", color="primary", className="float-end")
            ], width=4)
        ], className="mb-4"),

        # Add deal modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Add New Deal")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Deal Name *"),
                        dbc.Input(id="input-deal-name", placeholder="e.g., Acme GP-Led 2024", type="text")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Strategy Type *"),
                        dbc.Select(id="input-strategy", options=[
                            {"label": "GP-Led Secondaries", "value": "GP-Led Secondaries"},
                            {"label": "LP-Led Secondaries", "value": "LP-Led Secondaries"},
                            {"label": "Co-Investments", "value": "Co-Investments"},
                            {"label": "Direct Secondary", "value": "Direct Secondary"},
                            {"label": "Other", "value": "Other"}
                        ])
                    ], width=6)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Deal Size ($mm) *"),
                        dbc.Input(id="input-size", placeholder="25.0", type="number", min=0.1, step=0.5)
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Target Gross IRR (%) *"),
                        dbc.Input(id="input-irr", placeholder="20.0", type="number", min=0, max=100, step=0.5)
                    ], width=6)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Vintage Year *"),
                        dbc.Select(id="input-vintage", options=[
                            {"label": str(year), "value": year} for year in range(2024, 2018, -1)
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Sector *"),
                        dbc.Select(id="input-sector", options=[
                            {"label": "Technology", "value": "Technology"},
                            {"label": "Healthcare", "value": "Healthcare"},
                            {"label": "Consumer", "value": "Consumer"},
                            {"label": "Industrials", "value": "Industrials"},
                            {"label": "Financials", "value": "Financials"},
                            {"label": "Energy", "value": "Energy"},
                            {"label": "Real Estate", "value": "Real Estate"},
                            {"label": "Other", "value": "Other"}
                        ])
                    ], width=6)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Geography"),
                        dbc.Select(id="input-geography", options=[
                            {"label": "North America", "value": "North America"},
                            {"label": "Europe", "value": "Europe"},
                            {"label": "Asia", "value": "Asia"},
                            {"label": "Global", "value": "Global"},
                            {"label": "Other", "value": "Other"}
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Hold Period (years)"),
                        dbc.Input(id="input-hold", placeholder="5.0", type="number", min=1, step=0.5, value=5.0)
                    ], width=6)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Notes"),
                        dbc.Textarea(id="input-notes", placeholder="Additional deal information...", rows=3)
                    ])
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel-deal", color="secondary", className="me-2"),
                dbc.Button("Add Deal", id="btn-submit-deal", color="primary")
            ])
        ], id="modal-add-deal", size="lg", is_open=False),

        # Filters
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Filter by Strategy"),
                        dcc.Dropdown(id="filter-strategy", multi=True, placeholder="All Strategies")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Filter by Vintage"),
                        dcc.Dropdown(id="filter-vintage", multi=True, placeholder="All Vintages")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Sort By"),
                        dbc.Select(id="sort-deals", options=[
                            {"label": "Date Added (Newest)", "value": "date_desc"},
                            {"label": "Size (Largest)", "value": "size_desc"},
                            {"label": "IRR (Highest)", "value": "irr_desc"},
                            {"label": "Name (A-Z)", "value": "name_asc"}
                        ], value="date_desc")
                    ], width=4)
                ])
            ])
        ], className="mb-4"),

        # Deals table
        html.Div(id='deals-table-container')
    ], fluid=True)


def pacing_layout():
    return dbc.Container([
        html.H2("Commitment Pacing Model", className="mb-4"),

        # Summary metrics
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Target Fund Size"),
                    html.H4(id="pacing-target-size")
                ])
            ]), width=3),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Current NAV"),
                    html.H4(id="pacing-current-nav")
                ])
            ]), width=3),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Remaining to Deploy"),
                    html.H4(id="pacing-remaining")
                ])
            ]), width=3),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Self-Sustaining"),
                    html.H4(id="pacing-self-sustain")
                ])
            ]), width=3)
        ], className="mb-4"),

        # Tabs
        dbc.Tabs([
            dbc.Tab(label="Commitments", tab_id="tab-commitments"),
            dbc.Tab(label="NAV Growth", tab_id="tab-nav"),
            dbc.Tab(label="Liquidity", tab_id="tab-liquidity"),
            dbc.Tab(label="Deal Flow", tab_id="tab-dealflow")
        ], id="pacing-tabs", active_tab="tab-commitments"),

        html.Div(id='pacing-tab-content', className="mt-4")
    ], fluid=True)


def settings_layout():
    return dbc.Container([
        html.H2("Model Settings", className="mb-4"),

        dbc.Card([
            dbc.CardBody([
                html.H5("Fund Parameters", className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Target Fund Size ($mm)"),
                        dbc.Input(id="setting-target-size", type="number", value=500, min=100, step=50)
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Deployment Timeline (years)"),
                        dbc.Input(id="setting-timeline", type="number", value=5, min=3, max=10)
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Liquidity Reserve (%)"),
                        dbc.Input(id="setting-liquidity", type="number", value=10, min=0, max=25, step=1)
                    ], width=4)
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Target TWR (%)"),
                        dbc.Input(id="setting-twr", type="number", value=13, min=8, max=20, step=0.5)
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Distribution Rate (%)"),
                        dbc.Input(id="setting-dist-rate", type="number", value=20, min=10, max=30, step=1)
                    ], width=6)
                ])
            ])
        ], className="mb-4"),

        dbc.Card([
            dbc.CardBody([
                html.H5("Strategy Allocations", className="mb-3"),

                dbc.Row([
                    dbc.Col([
                        html.H6("GP-Led Secondaries"),
                        dbc.Label("Allocation (%)"),
                        dbc.Input(id="setting-gpled-alloc", type="number", value=40, min=0, max=100, step=5),
                        dbc.Label("Avg Deal Size ($mm)", className="mt-2"),
                        dbc.Input(id="setting-gpled-size", type="number", value=30, min=10, max=100, step=5)
                    ], width=4),
                    dbc.Col([
                        html.H6("LP-Led Secondaries"),
                        dbc.Label("Allocation (%)"),
                        dbc.Input(id="setting-lpled-alloc", type="number", value=30, min=0, max=100, step=5),
                        dbc.Label("Avg Deal Size ($mm)", className="mt-2"),
                        dbc.Input(id="setting-lpled-size", type="number", value=40, min=10, max=100, step=5)
                    ], width=4),
                    dbc.Col([
                        html.H6("Co-Investments"),
                        dbc.Label("Allocation (%)"),
                        dbc.Input(id="setting-coinv-alloc", type="number", value=30, min=0, max=100, step=5),
                        dbc.Label("Avg Deal Size ($mm)", className="mt-2"),
                        dbc.Input(id="setting-coinv-size", type="number", value=20, min=10, max=100, step=5)
                    ], width=4)
                ]),

                html.Div(id="allocation-warning", className="mt-3")
            ])
        ], className="mb-4"),

        dbc.Card([
            dbc.CardBody([
                html.H5("Pacing Strategy", className="mb-3"),

                dbc.Label("Pacing Preset"),
                dbc.Select(id="setting-pacing-preset", options=[
                    {"label": "Front-Loaded (Recommended)", "value": "front"},
                    {"label": "Even", "value": "even"},
                    {"label": "Back-Loaded", "value": "back"}
                ], value="front"),

                html.Div(id="pacing-chart-preview", className="mt-3")
            ])
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Button("Save Settings", id="btn-save-settings", color="primary", size="lg", className="me-2"),
                dbc.Button("Reset to Default", id="btn-reset-settings", color="secondary", size="lg")
            ])
        ])
    ], fluid=True)


# ========== CALLBACKS ==========

# Update clock
@app.callback(
    Output('live-clock', 'children'),
    Input('clock-interval', 'n_intervals')
)
def update_clock(n):
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# Update sidebar stats
@app.callback(
    Output('sidebar-stats', 'children'),
    Input('deals-store', 'data')
)
def update_sidebar_stats(deals):
    metrics = calculate_portfolio_metrics(deals)
    return [
        html.Div([
            html.Small("Total NAV", className="text-muted"),
            html.H6(f"${metrics['total_nav']:.0f}M", className="mb-0")
        ], className="mb-2"),
        html.Div([
            html.Small("Active Deals", className="text-muted"),
            html.H6(str(metrics['num_deals']), className="mb-0")
        ], className="mb-2"),
        html.Div([
            html.Small("Avg IRR", className="text-muted"),
            html.H6(f"{metrics['weighted_irr']:.1%}", className="mb-0")
        ])
    ]


# Page routing
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/deals':
        return deals_layout()
    elif pathname == '/pacing':
        return pacing_layout()
    elif pathname == '/settings':
        return settings_layout()
    else:  # Default to overview
        return overview_layout()


# Modal control
@app.callback(
    Output('modal-add-deal', 'is_open'),
    [Input('btn-open-add-deal', 'n_clicks'),
     Input('btn-cancel-deal', 'n_clicks'),
     Input('btn-submit-deal', 'n_clicks')],
    State('modal-add-deal', 'is_open'),
    prevent_initial_call=True
)
def toggle_modal(open_clicks, cancel_clicks, submit_clicks, is_open):
    return not is_open


# Add deal
@app.callback(
    Output('deals-store', 'data'),
    Input('btn-submit-deal', 'n_clicks'),
    [State('input-deal-name', 'value'),
     State('input-strategy', 'value'),
     State('input-size', 'value'),
     State('input-irr', 'value'),
     State('input-vintage', 'value'),
     State('input-sector', 'value'),
     State('input-geography', 'value'),
     State('input-hold', 'value'),
     State('input-notes', 'value'),
     State('deals-store', 'data')],
    prevent_initial_call=True
)
def add_deal(n_clicks, name, strategy, size, irr, vintage, sector, geography, hold, notes, current_deals):
    if not all([name, strategy, size, irr]):
        return current_deals

    new_deal = {
        'name': name,
        'strategy': strategy,
        'size': float(size),
        'target_irr': float(irr) / 100,
        'vintage': int(vintage) if vintage else 2024,
        'sector': sector or 'Other',
        'geography': geography or 'Global',
        'hold_period': float(hold) if hold else 5.0,
        'notes': notes or '',
        'date_added': datetime.now().isoformat()
    }

    return current_deals + [new_deal]


# Overview metrics
@app.callback(
    [Output('metric-total-nav', 'children'),
     Output('metric-num-deals', 'children'),
     Output('metric-weighted-irr', 'children'),
     Output('metric-required-irr', 'children'),
     Output('metric-irr-gap', 'children'),
     Output('metric-remaining', 'children'),
     Output('metric-remaining-pct', 'children')],
    [Input('deals-store', 'data'),
     Input('config-store', 'data')]
)
def update_overview_metrics(deals, config):
    metrics = calculate_portfolio_metrics(deals)
    target_size = config['fund_parameters']['target_fund_size']
    remaining = target_size - metrics['total_nav']
    required_irr = 0.25  # Simplified - would calculate from model
    gap = metrics['weighted_irr'] - required_irr if metrics['total_nav'] > 0 else 0

    return (
        f"${metrics['total_nav']:.1f}M",
        f"{metrics['num_deals']} deals",
        f"{metrics['weighted_irr']:.1%}",
        f"{required_irr:.1%}",
        f"{gap:+.1%} vs current" if metrics['total_nav'] > 0 else "N/A",
        f"${remaining:.0f}M",
        f"{remaining / target_size:.0%} of target"
    )


# Overview pie chart
@app.callback(
    Output('overview-pie-chart', 'figure'),
    Input('deals-store', 'data')
)
def update_pie_chart(deals):
    metrics = calculate_portfolio_metrics(deals)
    return create_strategy_pie(metrics)


# Strategy breakdown
@app.callback(
    Output('strategy-breakdown', 'children'),
    Input('deals-store', 'data')
)
def update_strategy_breakdown(deals):
    metrics = calculate_portfolio_metrics(deals)

    if not metrics['by_strategy']:
        return html.P("No deals yet", className="text-muted")

    cards = []
    for strategy, data in metrics['by_strategy'].items():
        cards.append(
            dbc.Card([
                dbc.CardBody([
                    html.H6(strategy, className="card-subtitle mb-2"),
                    html.P([
                        html.Strong(f"${data['nav']:.1f}M"),
                        html.Br(),
                        f"{data['count']} deals • {data['weighted_irr']:.1%} IRR",
                        html.Br(),
                        f"{data['nav'] / metrics['total_nav']:.1%} allocation"
                    ], className="card-text small mb-0")
                ])
            ], className="mb-2")
        )

    return cards


# Recent deals table
@app.callback(
    Output('recent-deals-table', 'children'),
    Input('deals-store', 'data')
)
def update_recent_deals(deals):
    if not deals:
        return html.P("No deals in portfolio yet. Add your first deal in 'Manage Deals'", className="text-muted")

    recent = sorted(deals, key=lambda x: x.get('date_added', ''), reverse=True)[:5]

    return dash_table.DataTable(
        data=[{
            'Name': d['name'],
            'Strategy': d['strategy'],
            'Size': f"${d['size']:.0f}M",
            'IRR': f"{d['target_irr']:.1%}",
            'Vintage': d['vintage']
        } for d in recent],
        columns=[{"name": col, "id": col} for col in ['Name', 'Strategy', 'Size', 'IRR', 'Vintage']],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white', 'fontWeight': 'bold'}
    )


# Deals table
@app.callback(
    [Output('deals-table-container', 'children'),
     Output('filter-strategy', 'options'),
     Output('filter-vintage', 'options')],
    [Input('deals-store', 'data'),
     Input('filter-strategy', 'value'),
     Input('filter-vintage', 'value'),
     Input('sort-deals', 'value')]
)
def update_deals_table(deals, filter_strat, filter_vint, sort_by):
    if not deals:
        return html.P("No deals yet. Click 'Add New Deal' to start.", className="text-muted"), [], []

    # Get unique values for filters
    strategies = sorted(list(set(d['strategy'] for d in deals)))
    vintages = sorted(list(set(d['vintage'] for d in deals)), reverse=True)

    strat_options = [{'label': s, 'value': s} for s in strategies]
    vint_options = [{'label': str(v), 'value': v} for v in vintages]

    # Apply filters
    filtered = deals.copy()
    if filter_strat:
        filtered = [d for d in filtered if d['strategy'] in filter_strat]
    if filter_vint:
        filtered = [d for d in filtered if d['vintage'] in filter_vint]

    # Sort
    if sort_by == 'size_desc':
        filtered = sorted(filtered, key=lambda x: x['size'], reverse=True)
    elif sort_by == 'irr_desc':
        filtered = sorted(filtered, key=lambda x: x['target_irr'], reverse=True)
    elif sort_by == 'name_asc':
        filtered = sorted(filtered, key=lambda x: x['name'])
    else:  # date_desc
        filtered = sorted(filtered, key=lambda x: x.get('date_added', ''), reverse=True)

    # Create table
    table_data = [{
        'Name': d['name'],
        'Strategy': d['strategy'],
        'Size ($mm)': f"{d['size']:.1f}",
        'IRR': f"{d['target_irr']:.1%}",
        'MOIC': f"{(1 + d['target_irr']) ** d['hold_period']:.2f}x",
        'Vintage': d['vintage'],
        'Sector': d['sector'],
        'Geography': d.get('geography', 'N/A')
    } for d in filtered]

    table = dash_table.DataTable(
        data=table_data,
        columns=[{"name": col, "id": col} for col in table_data[0].keys()] if table_data else [],
        page_size=20,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '12px'},
        style_header={
            'backgroundColor': COLORS['dark'],
            'color': 'white',
            'fontWeight': 'bold',
            'textAlign': 'left'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': '#f8f9fa'
            }
        ]
    )

    return table, strat_options, vint_options


# Pacing model calculations and display
@app.callback(
    [Output('pacing-target-size', 'children'),
     Output('pacing-current-nav', 'children'),
     Output('pacing-remaining', 'children'),
     Output('pacing-self-sustain', 'children'),
     Output('pacing-tab-content', 'children')],
    [Input('deals-store', 'data'),
     Input('config-store', 'data'),
     Input('pacing-tabs', 'active_tab')]
)
def update_pacing_model(deals, config, active_tab):
    metrics = calculate_portfolio_metrics(deals)

    # Update config with current NAV
    config['fund_parameters']['current_nav'] = metrics['total_nav']

    # Run model
    model = EvergreenCommitmentPacingModel(config)
    results = model.calculate_pacing_schedule()
    summary = model.get_summary_metrics()

    target = f"${summary['target_fund_size']}M"
    current = f"${summary['current_nav']:.0f}M"
    remaining = f"${summary['remaining_to_deploy']:.0f}M"
    self_sustain = f"Year {summary.get('self_sustaining_year', 'N/A')}" if summary.get(
        'self_sustaining_year') else "Not Yet"

    # Tab content
    if active_tab == 'tab-commitments':
        content = dcc.Graph(figure=create_commitment_waterfall(results))
    elif active_tab == 'tab-nav':
        content = dcc.Graph(figure=create_nav_trajectory(results, config))
    elif active_tab == 'tab-liquidity':
        content = dcc.Graph(figure=create_liquidity_buffer(results))
    else:  # deal flow
        content = html.P("Deal flow chart coming soon...")

    return target, current, remaining, self_sustain, content


# Export CSV
@app.callback(
    Output("download-csv", "data"),
    Input("btn-export", "n_clicks"),
    State("deals-store", "data"),
    prevent_initial_call=True
)
def export_deals(n_clicks, deals):
    if not deals:
        return None

    df = pd.DataFrame(deals)
    return dcc.send_data_frame(df.to_csv, f"portfolio_{date.today()}.csv", index=False)


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)
