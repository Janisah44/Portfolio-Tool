"""
ULTIMATE EVERGREEN FUND DASHBOARD - INSTITUTIONAL GRADE
Integrates all features from your Excel Portfolio Management Tool

Features:
✓ Current Portfolio Management (add/delete deals)
✓ Pro Forma Portfolio (placeholder/future deals)
✓ Dry Powder Forecasting & Bite Sizing
✓ Pipeline Management
✓ Return Calculator with Waterfall
✓ Pacing Model with Multi-Year Forecasts
✓ Portfolio Construction Analytics
✓ Deal Sizing Recommendations (Min/Desired/Max)

Run: python ULTIMATE_Evergreen_Fund_Dashboard.py
Open: http://localhost:8050
"""

import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json

# ==================== COLORS ====================

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

# Legacy color mappings for compatibility
COLORS = {
    'primary': C['blue'],
    'secondary': C['purple'],
    'accent': C['amber'],
    'success': C['green'],
    'danger': C['red'],
    'dark': C['bg'],
    'light': C['panel'],
    'warning': C['amber'],
    'info': C['sky']
}


# ==================== HELPER FUNCTIONS ====================

def calculate_required_future_irr(current_portfolio_irr, current_nav, dry_powder, config):
    """Calculate IRR needed on future deals to hit target net TWR"""
    target_twr = config['fund_parameters']['target_net_twr']
    mgmt_fee = config['fund_parameters']['management_fee']
    carry_rate = config['fund_parameters']['carry_rate']
    hurdle = config['fund_parameters']['hurdle_rate']
    loss_drag = config['fund_parameters']['loss_drag']
    cash_reserve = config['fund_parameters']['liquidity_reserve_pct']
    cash_yield = config['fund_parameters'].get('cash_yield', 0.03)

    # Calculate invested ratio
    total_fund = current_nav + dry_powder
    if total_fund == 0:
        return 0.25

    invested_ratio = max(0, 1 - cash_reserve)
    idle_ratio = cash_reserve

    # Gross return needed before carry
    gross_needed = (target_twr + mgmt_fee + loss_drag - (idle_ratio * cash_yield)) / invested_ratio

    # Add carry drag if above hurdle
    if gross_needed > hurdle:
        carry_drag = (gross_needed - hurdle) * carry_rate
        gross_needed += carry_drag

    # Calculate weighted average
    if dry_powder == 0:
        return gross_needed

    current_weight = current_nav / total_fund
    future_weight = dry_powder / total_fund

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


def calculate_bite_sizes(dry_powder, config):
    """Calculate recommended deal sizes (min/desired/max) for each strategy"""
    bite_sizes = {}

    for strategy_name in ['GP-Led (Multi-Asset)', 'GP-Led (Single-Asset)', 'Diversified LP-Led', 'Co-Investments']:
        if 'Multi-Asset' in strategy_name:
            min_pct, desired_pct, max_pct = 0.005, 0.0275, 0.05
        elif 'Single-Asset' in strategy_name:
            min_pct, desired_pct, max_pct = 0.005, 0.0225, 0.04
        elif 'LP-Led' in strategy_name:
            min_pct, desired_pct, max_pct = 0.005, 0.0275, 0.05
        else:  # Co-Investments
            min_pct, desired_pct, max_pct = 0.005, 0.0175, 0.03

        bite_sizes[strategy_name] = {
            'min': dry_powder * min_pct,
            'desired': dry_powder * desired_pct,
            'max': dry_powder * max_pct,
            'min_pct': min_pct,
            'desired_pct': desired_pct,
            'max_pct': max_pct
        }

    return bite_sizes


def forecast_dry_powder(current_nav, dry_powder, deals, placeholder_deals, config, months=12):
    """Forecast dry powder availability over next N months"""
    forecast = []
    nav = current_nav
    powder = dry_powder

    for month in range(months):
        month_date = datetime.now() + relativedelta(months=month)

        # Simple monthly growth on NAV
        monthly_return = config['fund_parameters']['target_net_twr'] / 12
        nav_growth = nav * monthly_return

        # Distributions (20% annually = 1.67% monthly)
        monthly_dist = nav * (config['fund_parameters']['distribution_rate'] / 12)

        # Capital calls from placeholder deals in this month
        calls_this_month = 0
        for pd_deal in placeholder_deals:
            if pd_deal.get('expected_month') == month:
                calls_this_month += pd_deal['size']

        # Update
        powder = powder + monthly_dist - calls_this_month
        nav = nav + nav_growth + calls_this_month - monthly_dist

        forecast.append({
            'month': month_date.strftime('%b %Y'),
            'dry_powder': powder,
            'nav': nav,
            'distributions': monthly_dist,
            'calls': calls_this_month
        })

    return forecast


# ==================== DASH APP ====================

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)

app.title = "Ultimate Evergreen Fund Manager"
server = app.server

# Custom CSS for dark theme
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

            body {
                background-color: ''' + C['bg'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
                font-family: ''' + C['sans'] + ''' !important;
            }

            .card {
                background-color: ''' + C['panel'] + ''' !important;
                border: 1px solid ''' + C['border'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .card-header {
                background-color: ''' + C['surface'] + ''' !important;
                border-bottom: 1px solid ''' + C['border'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .card-body {
                background-color: ''' + C['panel'] + ''' !important;
            }

            .nav-pills .nav-link {
                color: ''' + C['muted'] + ''' !important;
                background-color: transparent !important;
                border-radius: 8px !important;
                font-family: ''' + C['sans'] + ''' !important;
            }

            .nav-pills .nav-link:hover {
                background-color: ''' + C['surface'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .nav-pills .nav-link.active {
                background: linear-gradient(135deg, ''' + C['blue'] + ''' 0%, ''' + C['sky'] + ''' 100%) !important;
                color: white !important;
                font-weight: 600 !important;
            }

            .navbar {
                background: linear-gradient(135deg, ''' + C['bg'] + ''' 0%, ''' + C['surface'] + ''' 100%) !important;
                border-bottom: 2px solid ''' + C['border'] + ''' !important;
            }

            .btn-primary {
                background: linear-gradient(135deg, ''' + C['blue'] + ''' 0%, ''' + C['sky'] + ''' 100%) !important;
                border: none !important;
                font-weight: 600 !important;
                font-family: ''' + C['sans'] + ''' !important;
            }

            .btn-primary:hover {
                background: linear-gradient(135deg, ''' + C['sky'] + ''' 0%, ''' + C['teal'] + ''' 100%) !important;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px ''' + rgba(C['blue'], 0.3) + ''' !important;
            }

            .btn-success {
                background: linear-gradient(135deg, ''' + C['green'] + ''' 0%, ''' + C['teal'] + ''' 100%) !important;
                border: none !important;
            }

            .btn-danger {
                background-color: ''' + C['red'] + ''' !important;
                border: none !important;
            }

            .btn-secondary {
                background-color: ''' + C['surface'] + ''' !important;
                border: 1px solid ''' + C['border'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .btn-info {
                background: linear-gradient(135deg, ''' + C['purple'] + ''' 0%, ''' + C['pink'] + ''' 100%) !important;
                border: none !important;
            }

            .modal-content {
                background-color: ''' + C['panel'] + ''' !important;
                border: 1px solid ''' + C['border'] + ''' !important;
            }

            .modal-header {
                background-color: ''' + C['surface'] + ''' !important;
                border-bottom: 1px solid ''' + C['border'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .modal-body {
                background-color: ''' + C['panel'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .modal-footer {
                background-color: ''' + C['surface'] + ''' !important;
                border-top: 1px solid ''' + C['border'] + ''' !important;
            }

            .form-control, .form-select {
                background-color: ''' + C['surface'] + ''' !important;
                border: 1px solid ''' + C['border'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
                font-family: ''' + C['mono'] + ''' !important;
            }

            .form-control:focus, .form-select:focus {
                background-color: ''' + C['surface'] + ''' !important;
                border-color: ''' + C['blue'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
                box-shadow: 0 0 0 0.2rem ''' + rgba(C['blue'], 0.25) + ''' !important;
            }

            .form-label {
                color: ''' + C['text'] + ''' !important;
                font-weight: 600 !important;
                font-family: ''' + C['sans'] + ''' !important;
            }

            .text-muted {
                color: ''' + C['muted'] + ''' !important;
            }

            .alert-info {
                background-color: ''' + rgba(C['blue'], 0.1) + ''' !important;
                border-color: ''' + C['blue'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            h1, h2, h3, h4, h5, h6 {
                color: ''' + C['text'] + ''' !important;
                font-family: ''' + C['sans'] + ''' !important;
            }

            .shadow-sm {
                box-shadow: 0 2px 8px ''' + rgba(C['bg'], 0.4) + ''' !important;
            }

            .border-0 {
                border: 1px solid ''' + C['border'] + ''' !important;
            }

            small {
                color: ''' + C['muted'] + ''' !important;
            }

            /* Dash DataTable */
            .dash-table-container {
                font-family: ''' + C['mono'] + ''' !important;
            }

            .dash-spreadsheet {
                background-color: ''' + C['panel'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
            }

            .dash-spreadsheet td {
                background-color: ''' + C['panel'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
                border: 1px solid ''' + C['border'] + ''' !important;
            }

            .dash-spreadsheet th {
                background-color: ''' + C['surface'] + ''' !important;
                color: ''' + C['text'] + ''' !important;
                border: 1px solid ''' + C['border'] + ''' !important;
            }

            /* Tab styling */
            .nav-tabs .nav-link {
                color: ''' + C['muted'] + ''' !important;
                background-color: transparent !important;
                border: none !important;
                border-bottom: 2px solid transparent !important;
            }

            .nav-tabs .nav-link.active {
                color: ''' + C['blue'] + ''' !important;
                border-bottom: 2px solid ''' + C['blue'] + ''' !important;
                background-color: transparent !important;
            }

            /* Scrollbar */
            ::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }

            ::-webkit-scrollbar-track {
                background: ''' + C['surface'] + ''';
            }

            ::-webkit-scrollbar-thumb {
                background: ''' + C['border2'] + ''';
                border-radius: 5px;
            }

            ::-webkit-scrollbar-thumb:hover {
                background: ''' + C['muted'] + ''';
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

DEFAULT_CONFIG = {
    'fund_parameters': {
        'dry_powder': 450,
        'target_net_twr': 0.13,
        'management_fee': 0.0125,
        'carry_rate': 0.125,
        'hurdle_rate': 0.10,
        'loss_drag': 0.01,
        'liquidity_reserve_pct': 0.05,
        'distribution_rate': 0.20,
        'cash_yield': 0.03,
        'avg_hold_period': 5.0
    },
    'bite_sizing': {
        'enabled': True
    }
}

# ==================== LAYOUT ====================

navbar = dbc.Navbar(
    dbc.Container([
        html.Div([
            html.I(className="fas fa-chart-line me-3", style={'fontSize': '32px', 'color': C['blue']}),
            dbc.NavbarBrand("ULTIMATE Evergreen Fund Manager", style={
                'fontSize': '24px',
                'fontWeight': 'bold',
                'fontFamily': C['sans'],
                'background': f'linear-gradient(135deg, {C["blue"]} 0%, {C["sky"]} 100%)',
                '-webkit-background-clip': 'text',
                '-webkit-text-fill-color': 'transparent'
            })
        ]),
        html.Div(id='live-clock', style={
            'fontSize': '14px',
            'color': C['muted'],
            'fontFamily': C['mono']
        })
    ], fluid=True),
    style={
        'background': f'linear-gradient(135deg, {C["bg"]} 0%, {C["surface"]} 100%)',
        'borderBottom': f'2px solid {C["border"]}',
        'padding': '1.2rem 2rem'
    },
    dark=True,
    className="mb-4"
)

sidebar = dbc.Card([
    dbc.CardBody([
        html.H5("📊 Navigation", className="mb-4", style={
            'fontWeight': 'bold',
            'color': C['text'],
            'fontFamily': C['sans']
        }),
        dbc.Nav([
            dbc.NavLink([html.I(className="fas fa-home me-2"), "Dashboard"], href="/", active="exact"),
            dbc.NavLink([html.I(className="fas fa-briefcase me-2"), "Current Portfolio"], href="/portfolio",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-calendar-plus me-2"), "Future Deals"], href="/future",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-water me-2"), "Dry Powder Forecast"], href="/drypowder",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-bullseye me-2"), "Return Calculator"], href="/calculator",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-chart-area me-2"), "TWR Forecaster"], href="/twr", active="exact"),
            dbc.NavLink([html.I(className="fas fa-dollar-sign me-2"), "Deal Cashflows"], href="/cashflows",
                        active="exact"),
            dbc.NavLink([html.I(className="fas fa-magic me-2"), "Pro Forma"], href="/proforma", active="exact"),
            dbc.NavLink([html.I(className="fas fa-funnel-dollar me-2"), "Pipeline"], href="/pipeline", active="exact"),
            dbc.NavLink([html.I(className="fas fa-chart-bar me-2"), "Analytics"], href="/analytics", active="exact"),
            dbc.NavLink([html.I(className="fas fa-cog me-2"), "Settings"], href="/settings", active="exact"),
        ], vertical=True, pills=True),
        html.Hr(style={'borderColor': C['border']}),
        html.H6("📈 Quick Stats", className="mb-3", style={
            'fontWeight': 'bold',
            'color': C['text'],
            'fontFamily': C['sans']
        }),
        html.Div(id='sidebar-stats'),
        html.Hr(style={'borderColor': C['border']}),
        dbc.Button("📥 Export All", id="btn-export", color="secondary", size="sm", className="w-100"),
        dcc.Download(id="download-csv"),
    ], style={'backgroundColor': C['panel']})
], style={
    'position': 'sticky',
    'top': '20px',
    'backgroundColor': C['panel'],
    'border': f'1px solid {C["border"]}'
})

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='deals-store', data=[]),
    dcc.Store(id='placeholder-deals-store', data=[]),
    dcc.Store(id='pipeline-store', data=[]),
    dcc.Store(id='cashflows-store', data=[]),  # NEW: Real cashflows per deal
    dcc.Store(id='proforma-scenario-store', data=[]),  # NEW: Pro forma scenarios
    dcc.Store(id='config-store', data=DEFAULT_CONFIG),
    dcc.Interval(id='clock-interval', interval=1000),
    navbar,
    dbc.Row([
        dbc.Col(sidebar, width=2),
        dbc.Col(html.Div(id="page-content"), width=10)
    ])
], fluid=True, style={'backgroundColor': C['bg'], 'minHeight': '100vh'})


# ==================== PAGE LAYOUTS ====================

def dashboard_page():
    return html.Div([
        html.H2("📊 Fund Dashboard", className="mb-4", style={
            'fontWeight': 'bold',
            'fontFamily': C['sans'],
            'color': C['text']
        }),

        # Top KPIs
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("💰 Current NAV", className="text-muted mb-2"),
                html.H3(id="dash-nav", style={'color': C['green'], 'fontWeight': 'bold', 'fontFamily': C['mono']}),
                html.Small(id="dash-num-deals", className="text-muted")
            ])], className="shadow-sm border-0",
                style={'background': f'linear-gradient(135deg, {rgba(C["green"], 0.1)} 0%, {C["panel"]} 100%)'}),
                width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("💵 Dry Powder", className="text-muted mb-2"),
                html.H3(id="dash-dry-powder",
                        style={'color': C['blue'], 'fontWeight': 'bold', 'fontFamily': C['mono']}),
                html.Small("Available", className="text-muted")
            ])], className="shadow-sm border-0",
                style={'background': f'linear-gradient(135deg, {rgba(C["blue"], 0.1)} 0%, {C["panel"]} 100%)'}),
                width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("📊 Total Fund", className="text-muted mb-2"),
                html.H3(id="dash-total", style={'color': C['sky'], 'fontWeight': 'bold', 'fontFamily': C['mono']}),
                html.Small("NAV + Powder", className="text-muted")
            ])], className="shadow-sm border-0",
                style={'background': f'linear-gradient(135deg, {rgba(C["sky"], 0.1)} 0%, {C["panel"]} 100%)'}),
                width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("🎯 Portfolio IRR", className="text-muted mb-2"),
                html.H3(id="dash-current-irr",
                        style={'color': C['teal'], 'fontWeight': 'bold', 'fontFamily': C['mono']}),
                html.Small("Weighted", className="text-muted")
            ])], className="shadow-sm border-0",
                style={'background': f'linear-gradient(135deg, {rgba(C["teal"], 0.1)} 0%, {C["panel"]} 100%)'}),
                width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("🚀 Required IRR", className="text-muted mb-2"),
                html.H3(id="dash-req-irr", style={'color': C['amber'], 'fontWeight': 'bold', 'fontFamily': C['mono']}),
                html.Small("Future Deals", className="text-muted")
            ])], className="shadow-sm border-0",
                style={'background': f'linear-gradient(135deg, {rgba(C["amber"], 0.1)} 0%, {C["panel"]} 100%)'}),
                width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("📅 Placeholders", className="text-muted mb-2"),
                html.H3(id="dash-placeholders",
                        style={'color': C['purple'], 'fontWeight': 'bold', 'fontFamily': C['mono']}),
                html.Small(id="dash-placeholder-value", className="text-muted")
            ])], className="shadow-sm border-0",
                style={'background': f'linear-gradient(135deg, {rgba(C["purple"], 0.1)} 0%, {C["panel"]} 100%)'}),
                width=2),
        ], className="mb-4"),

        # Charts Row
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Portfolio Allocation", style={
                        'fontWeight': 'bold',
                        'backgroundColor': C['surface'],
                        'borderBottom': f'1px solid {C["border"]}'
                    }),
                    dbc.CardBody([dcc.Graph(id='dash-allocation-chart', config={'displayModeBar': False})])
                ], className="shadow-sm border-0")
            ], width=4),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Dry Powder Forecast (12 Months)", style={
                        'fontWeight': 'bold',
                        'backgroundColor': C['surface'],
                        'borderBottom': f'1px solid {C["border"]}'
                    }),
                    dbc.CardBody([dcc.Graph(id='dash-forecast-chart', config={'displayModeBar': False})])
                ], className="shadow-sm border-0")
            ], width=4),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Deal Bite Sizing Guide", style={
                        'fontWeight': 'bold',
                        'backgroundColor': C['surface'],
                        'borderBottom': f'1px solid {C["border"]}'
                    }),
                    dbc.CardBody([html.Div(id='dash-bite-sizing')])
                ], className="shadow-sm border-0")
            ], width=4),
        ], className="mb-4"),

        # Recent Activity
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Portfolio Activity", style={
                        'fontWeight': 'bold',
                        'backgroundColor': C['surface'],
                        'borderBottom': f'1px solid {C["border"]}'
                    }),
                    dbc.CardBody([html.Div(id='dash-recent-activity')])
                ], className="shadow-sm border-0")
            ], width=6),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Pipeline Status", style={
                        'fontWeight': 'bold',
                        'backgroundColor': C['surface'],
                        'borderBottom': f'1px solid {C["border"]}'
                    }),
                    dbc.CardBody([html.Div(id='dash-pipeline-status')])
                ], className="shadow-sm border-0")
            ], width=6),
        ])
    ])


def portfolio_page():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("💼 Current Portfolio", style={'fontWeight': 'bold'}), width=8),
            dbc.Col(dbc.Button("➕ Add Deal", id="btn-open-deal", color="primary", className="float-end", size="lg"),
                    width=4)
        ], className="mb-3"),

        # Fund Status Cards
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("💰 Current NAV", className="text-muted"),
                html.H4(id="port-nav", style={'color': COLORS['success']}),
                html.Small("Invested Capital", className="text-muted")
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("💵 Dry Powder", className="text-muted"),
                html.H4(id="port-dry-powder", style={'color': COLORS['primary']}),
                html.Small("Available to Deploy", className="text-muted")
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("📊 Total Fund Size", className="text-muted"),
                html.H4(id="port-total-fund", style={'color': COLORS['dark']}),
                html.Small("NAV + Dry Powder", className="text-muted")
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("🎯 Target Return", className="text-muted"),
                html.H4(id="port-target-return", style={'color': COLORS['warning']}),
                html.Small("Required Deal IRR", className="text-muted")
            ])], className="shadow-sm"), width=3),
        ], className="mb-4"),

        # Add Deal Modal
        dbc.Modal([
            dbc.ModalHeader("Add New Deal to Current Portfolio"),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Deal Name *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="in-name", type="text", placeholder="e.g., Vista GP-Led 2024")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Strategy Type *", style={'fontWeight': 'bold'}),
                        dbc.Select(id="in-strategy", options=[
                            {"label": "GP-Led (Multi-Asset)", "value": "GP-Led (Multi-Asset)"},
                            {"label": "GP-Led (Single-Asset)", "value": "GP-Led (Single-Asset)"},
                            {"label": "Diversified LP-Led", "value": "Diversified LP-Led"},
                            {"label": "Co-Investments", "value": "Co-Investments"},
                        ])
                    ], width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Size ($mm) *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="in-size", type="number", step=0.1, placeholder="25.0"),
                        html.Small(id="bite-size-warning", className="text-muted")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Target Gross IRR (%) *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="in-irr", type="number", step=0.5, placeholder="22.0")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Hold Period (years)", style={'fontWeight': 'bold'}),
                        dbc.Input(id="in-hold", type="number", value=5, step=0.5)
                    ], width=4),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Vintage Year", style={'fontWeight': 'bold'}),
                        dbc.Select(id="in-vintage", options=[
                            {"label": str(y), "value": y} for y in range(2025, 2019, -1)
                        ], value=2024)
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Sector", style={'fontWeight': 'bold'}),
                        dbc.Select(id="in-sector", options=[
                            {"label": s, "value": s} for s in
                            ["Technology", "Healthcare", "Consumer", "Industrials", "Financials", "Other"]
                        ], value="Technology")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Geography", style={'fontWeight': 'bold'}),
                        dbc.Select(id="in-geo", options=[
                            {"label": g, "value": g} for g in ["North America", "Europe", "Asia", "Global"]
                        ], value="North America")
                    ], width=4),
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel", color="secondary"),
                dbc.Button("Add Deal", id="btn-submit", color="primary")
            ])
        ], id="modal-deal", size="lg", is_open=False),

        html.Div(id='portfolio-table')
    ])


def future_deals_page():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("📅 Pro Forma Portfolio (Future/Placeholder Deals)", style={'fontWeight': 'bold'}), width=8),
            dbc.Col(dbc.Button("➕ Add Placeholder", id="btn-open-placeholder", color="success", className="float-end",
                               size="lg"), width=4)
        ], className="mb-3"),

        dbc.Alert([
            html.I(className="fas fa-lightbulb me-2"),
            "Plan future deals to forecast dry powder usage and ensure you stay within bite size limits. These are NOT in your current portfolio."
        ], color="info", className="mb-4"),

        # Add Placeholder Modal
        dbc.Modal([
            dbc.ModalHeader("Add Placeholder Deal (Future Commitment)"),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Deal Name *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="in-ph-name", type="text", placeholder="e.g., GP-Led (Multi-Asset) 1")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Strategy Type *", style={'fontWeight': 'bold'}),
                        dbc.Select(id="in-ph-strategy", options=[
                            {"label": "GP-Led (Multi-Asset)", "value": "GP-Led (Multi-Asset)"},
                            {"label": "GP-Led (Single-Asset)", "value": "GP-Led (Single-Asset)"},
                            {"label": "Diversified LP-Led", "value": "Diversified LP-Led"},
                            {"label": "Co-Investments", "value": "Co-Investments"},
                        ])
                    ], width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Expected Size ($mm) *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="in-ph-size", type="number", step=0.1, placeholder="15.0"),
                        html.Small(id="ph-bite-warning", className="text-muted")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Expected Month *", style={'fontWeight': 'bold'}),
                        dbc.Select(id="in-ph-month", options=[
                            {"label": f"Month {i + 1}", "value": i} for i in range(12)
                        ], value=0)
                    ], width=6),
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel-ph", color="secondary"),
                dbc.Button("Add Placeholder", id="btn-submit-ph", color="success")
            ])
        ], id="modal-placeholder", size="lg", is_open=False),

        html.Div(id='placeholder-table')
    ])


def drypowder_page():
    return html.Div([
        html.H2("💧 Dry Powder Forecaster", className="mb-4", style={'fontWeight': 'bold'}),

        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Current Dry Powder", className="text-muted"),
                html.H3(id="dp-current", style={'color': COLORS['primary']})
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Planned Deployments", className="text-muted"),
                html.H3(id="dp-planned", style={'color': COLORS['warning']})
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Expected Distributions", className="text-muted"),
                html.H3(id="dp-distributions", style={'color': COLORS['success']})
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("12-Month Forecast", className="text-muted"),
                html.H3(id="dp-forecast-12m", style={'color': COLORS['info']})
            ])], className="shadow-sm"), width=3),
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader("12-Month Dry Powder Forecast",
                           style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
            dbc.CardBody([
                dcc.Graph(id='dp-forecast-chart', config={'displayModeBar': True})
            ])
        ], className="shadow-sm mb-4"),

        dbc.Card([
            dbc.CardHeader("Monthly Breakdown", style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
            dbc.CardBody([
                html.Div(id='dp-monthly-table')
            ])
        ], className="shadow-sm")
    ])


def calculator_page():
    return html.Div([
        html.H2("🧮 Return Calculator & Waterfall", className="mb-4", style={'fontWeight': 'bold'}),

        dbc.Card([dbc.CardBody([
            html.H5("Calculate required deal IRR to achieve target net TWR", className="text-muted mb-4"),

            html.Hr(),
            html.H4("📊 Current Portfolio", className="mt-4", style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
            dbc.Row([
                dbc.Col([
                    html.H6("Current NAV:", className="text-muted"),
                    html.H3(id="calc-current-nav", style={'color': COLORS['success']})
                ], width=4),
                dbc.Col([
                    html.H6("Weighted IRR:", className="text-muted"),
                    html.H3(id="calc-current-irr", style={'color': COLORS['success']})
                ], width=4),
                dbc.Col([
                    html.H6("Number of Deals:", className="text-muted"),
                    html.H3(id="calc-num-deals", style={'color': COLORS['success']})
                ], width=4),
            ], className="mb-4"),

            html.Hr(),
            html.H4("🎯 Evergreen Fund Structure", className="mt-4",
                    style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
            dbc.Row([
                dbc.Col([
                    html.H6("Total Fund Size:", className="text-muted"),
                    html.H3(id="calc-total-fund", style={'color': COLORS['primary']}),
                    html.Small("NAV + Dry Powder", className="text-muted")
                ], width=4),
                dbc.Col([
                    html.H6("Target Net TWR:", className="text-muted"),
                    html.H3(id="calc-target-twr", style={'color': COLORS['warning']})
                ], width=4),
                dbc.Col([
                    html.H6("Dry Powder:", className="text-muted"),
                    html.H3(id="calc-dry-powder", style={'color': COLORS['info']}),
                    html.Small("Available to Deploy", className="text-muted")
                ], width=4),
            ], className="mb-4"),

            html.Hr(),
            html.Div([
                html.H3("✅ REQUIRED FUTURE DEAL IRR", className="text-center mb-3",
                        style={'color': COLORS['success'], 'fontWeight': 'bold'}),
                html.H1(id="calc-required-irr", className="text-center mb-2",
                        style={'fontSize': '80px', 'fontWeight': 'bold', 'color': COLORS['success']}),
                html.P(id="calc-explanation", className="text-center text-muted mb-4", style={'fontSize': '18px'}),
            ], style={'backgroundColor': '#F0F8F0', 'padding': '2rem', 'borderRadius': '10px',
                      'border': f'3px solid {COLORS["success"]}'}),

            html.Hr(className="mt-4"),
            html.H5("💡 Return Waterfall Breakdown", className="mb-3",
                    style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
            html.Div(id="calc-waterfall")
        ])], className="shadow-sm")
    ])


def twr_forecaster_page():
    return html.Div([
        html.H2("📈 TWR Returns Forecaster", className="mb-4",
                style={'fontWeight': 'bold', 'fontFamily': C['sans'], 'color': C['text']}),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Monte Carlo Simulation Parameters",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Current Portfolio IRR",
                                          style={'fontWeight': 'bold', 'fontFamily': C['sans']}),
                                html.H4(id="twr-current-irr", style={'color': C['green'], 'fontFamily': C['mono']})
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Future Deals Mean IRR (%)", style={'fontWeight': 'bold'}),
                                dbc.Input(id="twr-future-mean", type="number", value=25, step=0.5,
                                          style={'fontFamily': C['mono']})
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Future Deals Std Dev (%)", style={'fontWeight': 'bold'}),
                                dbc.Input(id="twr-future-std", type="number", value=5, step=0.5,
                                          style={'fontFamily': C['mono']})
                            ], width=4),
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("# Simulations", style={'fontWeight': 'bold'}),
                                dbc.Select(id="twr-n-sims", options=[
                                    {"label": "1,000", "value": 1000},
                                    {"label": "5,000", "value": 5000},
                                    {"label": "10,000", "value": 10000},
                                ], value=5000, style={'fontFamily': C['mono']})
                            ], width=6),
                            dbc.Col([
                                dbc.Button("🎲 Run Simulation", id="btn-run-twr", color="primary", size="lg",
                                           className="w-100")
                            ], width=6)
                        ])
                    ])
                ], className="shadow-sm mb-4")
            ], width=12),
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Probability Distribution",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='twr-distribution-chart', config={'displayModeBar': True})])
                ], className="shadow-sm")
            ], width=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Key Statistics", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([html.Div(id='twr-statistics')])
                ], className="shadow-sm")
            ], width=4),
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Sensitivity Analysis",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='twr-sensitivity-chart', config={'displayModeBar': True})])
                ], className="shadow-sm")
            ], width=12),
        ])
    ])


def cashflows_page():
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.H2("💰 Deal Cashflows", style={'fontWeight': 'bold', 'fontFamily': C['sans'], 'color': C['text']}),
                width=8),
            dbc.Col([
                dbc.Button("➕ Add Cashflow", id="btn-open-cashflow", color="success", className="float-end me-2"),
                dbc.Button("📥 Import CSV", id="btn-import-cf", color="info", className="float-end")
            ], width=4)
        ], className="mb-4"),

        dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "Enter ACTUAL cashflows for each deal. IRR is calculated from your real data - no assumptions!"
        ], color="info", className="mb-4"),

        # Add Cashflow Modal
        dbc.Modal([
            dbc.ModalHeader("Add Cashflow"),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Deal *", style={'fontWeight': 'bold'}),
                        dbc.Select(id="cf-deal", options=[])  # Populated dynamically
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Date *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="cf-date", type="date", style={'fontFamily': C['mono']})
                    ], width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Type *", style={'fontWeight': 'bold'}),
                        dbc.Select(id="cf-type", options=[
                            {"label": "Capital Call", "value": "Call"},
                            {"label": "Distribution", "value": "Distribution"},
                        ], style={'fontFamily': C['mono']})
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Amount ($mm) *", style={'fontWeight': 'bold'}),
                        dbc.Input(id="cf-amount", type="number", step=0.1, style={'fontFamily': C['mono']})
                    ], width=6)
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel-cf", color="secondary"),
                dbc.Button("Add Cashflow", id="btn-submit-cf", color="success")
            ])
        ], id="modal-cashflow", size="lg", is_open=False),

        # Summary Cards
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Total Calls", className="text-muted"),
                html.H4(id="cf-total-calls", style={'color': C['red'], 'fontFamily': C['mono']})
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Total Distributions", className="text-muted"),
                html.H4(id="cf-total-dists", style={'color': C['green'], 'fontFamily': C['mono']})
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Net Cashflow", className="text-muted"),
                html.H4(id="cf-net", style={'color': C['blue'], 'fontFamily': C['mono']})
            ])], className="shadow-sm"), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Actual Portfolio IRR", className="text-muted"),
                html.H4(id="cf-actual-irr", style={'color': C['amber'], 'fontFamily': C['mono']})
            ])], className="shadow-sm"), width=3),
        ], className="mb-4"),

        # Cashflows Table
        dbc.Card([
            dbc.CardHeader("All Cashflows", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
            dbc.CardBody([html.Div(id='cashflows-table')])
        ], className="shadow-sm mb-4"),

        # Per-Deal Summary
        dbc.Card([
            dbc.CardHeader("IRR by Deal (from Real Cashflows)",
                           style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
            dbc.CardBody([html.Div(id='cashflows-per-deal')])
        ], className="shadow-sm")
    ])


def proforma_page():
    return html.Div([
        html.H2("🔮 Pro Forma Analyzer", className="mb-4",
                style={'fontWeight': 'bold', 'fontFamily': C['sans'], 'color': C['text']}),

        dbc.Alert([
            html.I(className="fas fa-lightbulb me-2"),
            "Build 'What-If' scenarios. Add pipeline deals to see how your portfolio would change."
        ], color="info", className="mb-4"),

        # Scenario Builder
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Scenario Builder", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([
                        dbc.Label("Select Deal to Add", style={'fontWeight': 'bold'}),
                        dbc.Select(id="pf-deal-select", options=[], style={'fontFamily': C['mono']}),
                        html.Small("Or create custom deal:", className="text-muted d-block mt-3 mb-2"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Input(id="pf-custom-name", placeholder="Deal name", type="text",
                                          style={'fontFamily': C['mono']})
                            ], width=4),
                            dbc.Col([
                                dbc.Input(id="pf-custom-size", placeholder="Size ($mm)", type="number", step=0.1,
                                          style={'fontFamily': C['mono']})
                            ], width=4),
                            dbc.Col([
                                dbc.Input(id="pf-custom-irr", placeholder="IRR (%)", type="number", step=0.5,
                                          style={'fontFamily': C['mono']})
                            ], width=4),
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Button("➕ Add to Scenario", id="btn-add-to-pf", color="primary", className="w-100")
                            ], width=6),
                            dbc.Col([
                                dbc.Button("🔄 Reset Scenario", id="btn-reset-pf", color="secondary", className="w-100")
                            ], width=6)
                        ])
                    ])
                ], className="shadow-sm")
            ], width=4),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Current Scenario", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([
                        html.Div(id='pf-scenario-deals')
                    ])
                ], className="shadow-sm")
            ], width=8),
        ], className="mb-4"),

        # Before/After Comparison
        dbc.Card([
            dbc.CardHeader("Before vs After Comparison", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
            dbc.CardBody([
                html.Div(id='pf-comparison-table')
            ])
        ], className="shadow-sm mb-4"),

        # Impact Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Strategy Allocation Impact",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='pf-strategy-chart', config={'displayModeBar': False})])
                ], className="shadow-sm")
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Concentration Impact",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='pf-concentration-chart', config={'displayModeBar': False})])
                ], className="shadow-sm")
            ], width=6),
        ])
    ])


def analytics_page():
    return html.Div([
        html.H2("📊 Portfolio Analytics", className="mb-4",
                style={'fontWeight': 'bold', 'fontFamily': C['sans'], 'color': C['text']}),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Concentration Risk", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='analytics-concentration', config={'displayModeBar': False})])
                ], className="shadow-sm mb-4")
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Diversification Metrics",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([html.Div(id='analytics-diversification')])
                ], className="shadow-sm mb-4")
            ], width=6),
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Strategy Allocation",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='analytics-strategy', config={'displayModeBar': False})])
                ], className="shadow-sm mb-4")
            ], width=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Vintage Distribution",
                                   style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='analytics-vintage', config={'displayModeBar': False})])
                ], className="shadow-sm mb-4")
            ], width=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Sector Breakdown", style={'fontWeight': 'bold', 'backgroundColor': C['surface']}),
                    dbc.CardBody([dcc.Graph(id='analytics-sector', config={'displayModeBar': False})])
                ], className="shadow-sm mb-4")
            ], width=4),
        ])
    ])


def pipeline_page():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("🔍 Deal Pipeline", style={'fontWeight': 'bold'}), width=8),
            dbc.Col(
                dbc.Button("➕ Add to Pipeline", id="btn-open-pipeline", color="info", className="float-end", size="lg"),
                width=4)
        ], className="mb-3"),

        # Add Pipeline Modal
        dbc.Modal([
            dbc.ModalHeader("Add Deal to Pipeline"),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Deal Name *"),
                        dbc.Input(id="in-pipe-name", type="text", placeholder="Project Sigil")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Deal Type *"),
                        dbc.Select(id="in-pipe-type", options=[
                            {"label": "GP-Led (Multi-Asset)", "value": "GP-Led (Multi-Asset)"},
                            {"label": "GP-Led (Single-Asset)", "value": "GP-Led (Single-Asset)"},
                            {"label": "Diversified LP-Led", "value": "Diversified LP-Led"},
                            {"label": "Co-Investments", "value": "Co-Investments"},
                        ])
                    ], width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Stage"),
                        dbc.Select(id="in-pipe-stage", options=[
                            {"label": "Screening", "value": "Screening"},
                            {"label": "Due Diligence", "value": "Due Diligence"},
                            {"label": "Term Sheet", "value": "Term Sheet"},
                            {"label": "Final Docs", "value": "Final Docs"},
                        ], value="Screening")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Target Size ($mm)"),
                        dbc.Input(id="in-pipe-size", type="number", step=0.1, placeholder="7.5")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Target IRR (%)"),
                        dbc.Input(id="in-pipe-irr", type="number", step=0.5, placeholder="16")
                    ], width=4),
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel-pipe", color="secondary"),
                dbc.Button("Add to Pipeline", id="btn-submit-pipe", color="info")
            ])
        ], id="modal-pipeline", size="lg", is_open=False),

        html.Div(id='pipeline-table')
    ])


def settings_page():
    return html.Div([
        html.H2("⚙️ Fund Settings", className="mb-4", style={'fontWeight': 'bold'}),

        dbc.Card([dbc.CardBody([
            html.H5("💰 Fund Parameters", className="mb-4", style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
            dbc.Row([
                dbc.Col([
                    dbc.Label("💵 Dry Powder ($mm)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-dry-powder", type="number", value=450, step=10),
                    html.Small("Available capital to deploy", className="text-muted")
                ], width=4),
                dbc.Col([
                    dbc.Label("🎯 Target Net TWR (%)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-twr", type="number", value=13, step=0.5),
                    html.Small("Net return to LPs", className="text-muted")
                ], width=4),
                dbc.Col([
                    dbc.Label("📊 Average Hold Period (years)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-hold", type="number", value=5.0, step=0.5),
                    html.Small("For MOIC translation", className="text-muted")
                ], width=4),
            ], className="mb-4"),

            html.Hr(),
            html.H5("💼 Fee Structure", className="mb-4", style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Management Fee (% p.a.)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-fee", type="number", value=1.25, step=0.05),
                    html.Small("Annual fee on NAV", className="text-muted")
                ], width=4),
                dbc.Col([
                    dbc.Label("Carry Rate (%)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-carry", type="number", value=12.5, step=0.5),
                    html.Small("Performance fee", className="text-muted")
                ], width=4),
                dbc.Col([
                    dbc.Label("Hurdle Rate (%)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-hurdle", type="number", value=10, step=0.5),
                    html.Small("Return before carry", className="text-muted")
                ], width=4),
            ], className="mb-4"),

            html.Hr(),
            html.H5("🔧 Portfolio Assumptions", className="mb-4", style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Liquidity Reserve (%)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-liq", type="number", value=5, step=1),
                    html.Small("Cash buffer", className="text-muted")
                ], width=4),
                dbc.Col([
                    dbc.Label("Loss Drag (%)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-loss", type="number", value=1, step=0.5),
                    html.Small("Expected annual impairment", className="text-muted")
                ], width=4),
                dbc.Col([
                    dbc.Label("Cash Yield (%)", style={'fontWeight': 'bold'}),
                    dbc.Input(id="set-cash-yield", type="number", value=3, step=0.5),
                    html.Small("Return on uninvested cash", className="text-muted")
                ], width=4),
            ], className="mb-4"),

            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Button("💾 Save Settings", id="btn-save-settings", color="primary", size="lg", className="me-2"),
                    dbc.Button("🔄 Reset to Default", id="btn-reset-settings", color="secondary", size="lg")
                ])
            ])
        ])], className="shadow-sm")
    ])


# ==================== CALLBACKS ====================

@app.callback(Output('live-clock', 'children'), Input('clock-interval', 'n_intervals'))
def update_clock(n):
    return datetime.now().strftime('%H:%M:%S')


@app.callback(Output('sidebar-stats', 'children'),
              [Input('deals-store', 'data'), Input('config-store', 'data')])
def update_sidebar(deals, config):
    m = calculate_portfolio_metrics(deals)
    dry_powder = config['fund_parameters']['dry_powder']
    return [
        html.Small("💰 NAV", className="text-muted"),
        html.H6(f"${m['total_nav']:.0f}M", className="mb-2", style={'fontWeight': 'bold'}),
        html.Small("💵 Dry Powder", className="text-muted"),
        html.H6(f"${dry_powder:.0f}M", className="mb-2", style={'fontWeight': 'bold'}),
        html.Small("📊 Deals", className="text-muted"),
        html.H6(str(m['num_deals']), className="mb-2", style={'fontWeight': 'bold'}),
        html.Small("📈 Avg IRR", className="text-muted"),
        html.H6(f"{m['weighted_irr']:.1%}", style={'fontWeight': 'bold'})
    ]


@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/portfolio':
        return portfolio_page()
    elif pathname == '/future':
        return future_deals_page()
    elif pathname == '/drypowder':
        return drypowder_page()
    elif pathname == '/calculator':
        return calculator_page()
    elif pathname == '/twr':
        return twr_forecaster_page()
    elif pathname == '/cashflows':
        return cashflows_page()
    elif pathname == '/proforma':
        return proforma_page()
    elif pathname == '/pipeline':
        return pipeline_page()
    elif pathname == '/analytics':
        return analytics_page()
    elif pathname == '/settings':
        return settings_page()
    else:
        return dashboard_page()


# Deal Modal
@app.callback(
    Output('modal-deal', 'is_open'),
    [Input('btn-open-deal', 'n_clicks'), Input('btn-cancel', 'n_clicks'), Input('btn-submit', 'n_clicks')],
    State('modal-deal', 'is_open'), prevent_initial_call=True
)
def toggle_deal_modal(o, c, s, is_open):
    return not is_open


# Placeholder Modal
@app.callback(
    Output('modal-placeholder', 'is_open'),
    [Input('btn-open-placeholder', 'n_clicks'), Input('btn-cancel-ph', 'n_clicks'), Input('btn-submit-ph', 'n_clicks')],
    State('modal-placeholder', 'is_open'), prevent_initial_call=True
)
def toggle_placeholder_modal(o, c, s, is_open):
    return not is_open


# Pipeline Modal
@app.callback(
    Output('modal-pipeline', 'is_open'),
    [Input('btn-open-pipeline', 'n_clicks'), Input('btn-cancel-pipe', 'n_clicks'),
     Input('btn-submit-pipe', 'n_clicks')],
    State('modal-pipeline', 'is_open'), prevent_initial_call=True
)
def toggle_pipeline_modal(o, c, s, is_open):
    return not is_open


# Add Deal
@app.callback(
    Output('deals-store', 'data', allow_duplicate=True),
    Input('btn-submit', 'n_clicks'),
    [State('in-name', 'value'), State('in-strategy', 'value'), State('in-size', 'value'),
     State('in-irr', 'value'), State('in-hold', 'value'), State('in-vintage', 'value'),
     State('in-sector', 'value'), State('in-geo', 'value'), State('deals-store', 'data'),
     State('config-store', 'data')],
    prevent_initial_call=True
)
def add_deal(n, name, strat, size, irr, hold, vint, sec, geo, deals, config):
    if not all([name, strat, size, irr]):
        return deals

    # Update dry powder
    config['fund_parameters']['dry_powder'] -= float(size)

    return deals + [{
        'name': name, 'strategy': strat, 'size': float(size), 'target_irr': float(irr) / 100,
        'hold_period': float(hold) if hold else 5.0,
        'moic': (1 + float(irr) / 100) ** (float(hold) if hold else 5.0),
        'vintage': int(vint) if vint else 2024, 'sector': sec or 'Technology',
        'geography': geo or 'Global', 'date_added': datetime.now().isoformat()
    }]


# Add Placeholder
@app.callback(
    Output('placeholder-deals-store', 'data', allow_duplicate=True),
    Input('btn-submit-ph', 'n_clicks'),
    [State('in-ph-name', 'value'), State('in-ph-strategy', 'value'),
     State('in-ph-size', 'value'), State('in-ph-month', 'value'),
     State('placeholder-deals-store', 'data')],
    prevent_initial_call=True
)
def add_placeholder(n, name, strat, size, month, placeholders):
    if not all([name, strat, size is not None, month is not None]):
        return placeholders

    return placeholders + [{
        'name': name, 'strategy': strat, 'size': float(size),
        'expected_month': int(month),
        'date_added': datetime.now().isoformat()
    }]


# Add Pipeline Deal
@app.callback(
    Output('pipeline-store', 'data', allow_duplicate=True),
    Input('btn-submit-pipe', 'n_clicks'),
    [State('in-pipe-name', 'value'), State('in-pipe-type', 'value'),
     State('in-pipe-stage', 'value'), State('in-pipe-size', 'value'),
     State('in-pipe-irr', 'value'), State('pipeline-store', 'data')],
    prevent_initial_call=True
)
def add_pipeline(n, name, ptype, stage, size, irr, pipeline):
    if not all([name, ptype]):
        return pipeline

    return pipeline + [{
        'name': name, 'type': ptype, 'stage': stage or 'Screening',
        'size': float(size) if size else 0, 'target_irr': float(irr) / 100 if irr else 0,
        'date_added': datetime.now().isoformat()
    }]


# Delete Deal
@app.callback(
    Output('deals-store', 'data', allow_duplicate=True),
    Input({'type': 'delete-deal', 'index': ALL}, 'n_clicks'),
    State('deals-store', 'data'),
    prevent_initial_call=True
)
def delete_deal(n_clicks, deals):
    if not any(n_clicks):
        return deals
    ctx = callback_context
    if not ctx.triggered:
        return deals
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == '':
        return deals
    button_info = json.loads(button_id)
    delete_idx = button_info['index']
    if 0 <= delete_idx < len(deals):
        deals.pop(delete_idx)
    return deals


# Delete Placeholder
@app.callback(
    Output('placeholder-deals-store', 'data', allow_duplicate=True),
    Input({'type': 'delete-placeholder', 'index': ALL}, 'n_clicks'),
    State('placeholder-deals-store', 'data'),
    prevent_initial_call=True
)
def delete_placeholder(n_clicks, placeholders):
    if not any(n_clicks):
        return placeholders
    ctx = callback_context
    if not ctx.triggered:
        return placeholders
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == '':
        return placeholders
    button_info = json.loads(button_id)
    delete_idx = button_info['index']
    if 0 <= delete_idx < len(placeholders):
        placeholders.pop(delete_idx)
    return placeholders


# Portfolio Table
@app.callback(Output('portfolio-table', 'children'), Input('deals-store', 'data'))
def update_portfolio_table(deals):
    if not deals:
        return dbc.Alert("📝 No deals yet. Click 'Add Deal' to start.", color="info")
    rows = []
    for idx, d in enumerate(deals):
        rows.append(dbc.Card([dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H5(d['name'], className="mb-1"),
                    html.Small(f"{d['strategy']} • {d['sector']} • {d['geography']}", className="text-muted")
                ], width=5),
                dbc.Col([
                    html.Div([
                        html.Strong("Size: "), f"${d['size']:.1f}M", html.Br(),
                        html.Strong("IRR: "), f"{d['target_irr']:.1%}", html.Br(),
                        html.Strong("MOIC: "), f"{d.get('moic', 0):.2f}x"
                    ])
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.Strong("Hold: "), f"{d.get('hold_period', 5):.1f}y", html.Br(),
                        html.Strong("Vintage: "), str(d.get('vintage', 2024))
                    ])
                ], width=2),
                dbc.Col([
                    dbc.Button("🗑️", id={'type': 'delete-deal', 'index': idx},
                               color="danger", size="sm", outline=True)
                ], width=2, className="text-end")
            ])
        ])], className="mb-2 shadow-sm"))
    return html.Div(rows)


# Placeholder Table
@app.callback(Output('placeholder-table', 'children'), Input('placeholder-deals-store', 'data'))
def update_placeholder_table(placeholders):
    if not placeholders:
        return dbc.Alert("📝 No placeholder deals yet. Add future deals to forecast dry powder.", color="info")
    rows = []
    for idx, pd in enumerate(placeholders):
        month_name = (datetime.now() + relativedelta(months=pd['expected_month'])).strftime('%B %Y')
        rows.append(dbc.Card([dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H5(pd['name'], className="mb-1"),
                    html.Small(f"{pd['strategy']} • Expected: {month_name}", className="text-muted")
                ], width=8),
                dbc.Col([
                    html.H5(f"${pd['size']:.1f}M", className="text-end mb-1", style={'color': COLORS['success']})
                ], width=2),
                dbc.Col([
                    dbc.Button("🗑️", id={'type': 'delete-placeholder', 'index': idx},
                               color="danger", size="sm", outline=True)
                ], width=2, className="text-end")
            ])
        ])], className="mb-2 shadow-sm"))
    return html.Div(rows)


# Pipeline Table
@app.callback(Output('pipeline-table', 'children'), Input('pipeline-store', 'data'))
def update_pipeline_table(pipeline):
    if not pipeline:
        return dbc.Alert("📝 No pipeline deals yet.", color="info")

    data = [{
        'Deal': p['name'],
        'Type': p['type'],
        'Stage': p['stage'],
        'Size': f"${p['size']:.1f}M" if p['size'] > 0 else "TBD",
        'IRR': f"{p['target_irr']:.1%}" if p['target_irr'] > 0 else "TBD"
    } for p in pipeline]

    return dash_table.DataTable(
        data=data,
        columns=[{"name": c, "id": c} for c in data[0].keys()] if data else [],
        style_cell={'textAlign': 'left', 'padding': '12px', 'fontFamily': C['mono'], 'fontSize': '11px'},
        style_header={
            'backgroundColor': C['surface'],
            'color': C['text'],
            'fontWeight': 'bold',
            'border': f'1px solid {C["border"]}'
        },
        style_data={
            'backgroundColor': C['panel'],
            'color': C['text'],
            'border': f'1px solid {C["border"]}'
        },
        style_data_conditional=[{
            'if': {'row_index': 'odd'},
            'backgroundColor': C['surface']
        }]
    )


# Dashboard KPIs
@app.callback(
    [Output('dash-nav', 'children'), Output('dash-num-deals', 'children'),
     Output('dash-dry-powder', 'children'), Output('dash-total', 'children'),
     Output('dash-current-irr', 'children'), Output('dash-req-irr', 'children'),
     Output('dash-placeholders', 'children'), Output('dash-placeholder-value', 'children')],
    [Input('deals-store', 'data'), Input('placeholder-deals-store', 'data'), Input('config-store', 'data')]
)
def update_dashboard_kpis(deals, placeholders, config):
    m = calculate_portfolio_metrics(deals)
    dry_powder = config['fund_parameters']['dry_powder']
    req_irr = calculate_required_future_irr(m['weighted_irr'], m['total_nav'], dry_powder, config)

    num_placeholders = len(placeholders)
    total_placeholder_value = sum(p['size'] for p in placeholders)

    return (
        f"${m['total_nav']:.1f}M",
        f"{m['num_deals']} deals",
        f"${dry_powder:.0f}M",
        f"${m['total_nav'] + dry_powder:.0f}M",
        f"{m['weighted_irr']:.1%}",
        f"{req_irr:.1%}",
        str(num_placeholders),
        f"${total_placeholder_value:.0f}M"
    )


# Dashboard Charts
@app.callback(
    [Output('dash-allocation-chart', 'figure'), Output('dash-forecast-chart', 'figure'),
     Output('dash-bite-sizing', 'children')],
    [Input('deals-store', 'data'), Input('placeholder-deals-store', 'data'), Input('config-store', 'data')]
)
def update_dashboard_charts(deals, placeholders, config):
    m = calculate_portfolio_metrics(deals)
    dry_powder = config['fund_parameters']['dry_powder']

    # Allocation Pie
    if m['by_strategy']:
        labels = list(m['by_strategy'].keys())
        values = [m['by_strategy'][s]['nav'] for s in labels]
        colors_pie = [C['blue'], C['purple'], C['teal'], C['green']][:len(labels)]

        fig_alloc = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=0.4,
            marker=dict(colors=colors_pie, line=dict(color=C['border'], width=1)),
            textfont=dict(color=C['text'], family=C['mono'])
        )])
        fig_alloc.update_layout(**CHART_BASE, height=300, margin=dict(t=20, b=0, l=0, r=0), showlegend=False)
    else:
        fig_alloc = go.Figure()
        fig_alloc.update_layout(**CHART_BASE)

    # Forecast
    forecast = forecast_dry_powder(m['total_nav'], dry_powder, deals, placeholders, config, 12)
    months = [f['month'] for f in forecast]
    dp_values = [f['dry_powder'] for f in forecast]

    fig_forecast = go.Figure()
    fig_forecast.add_trace(go.Scatter(
        x=months, y=dp_values, mode='lines+markers', name='Dry Powder',
        line=dict(color=C['blue'], width=3),
        fill='tozeroy',
        fillcolor=rgba(C['blue'], 0.2),
        marker=dict(size=6, color=C['sky'], line=dict(color=C['blue'], width=2))
    ))
    fig_forecast.update_layout(
        **CHART_BASE,
        height=300,
        xaxis_title="Month",
        yaxis_title="Dry Powder ($mm)",
        hovermode='x unified'
    )

    # Bite Sizing
    bite_sizes = calculate_bite_sizes(dry_powder, config)
    bite_cards = []
    for strategy, sizes in bite_sizes.items():
        bite_cards.append(html.Div([
            html.H6(strategy, style={'fontSize': '12px', 'fontWeight': 'bold'}),
            html.Small(f"Min: ${sizes['min']:.1f}M ({sizes['min_pct']:.1%})", className="d-block text-muted"),
            html.Small(f"Desired: ${sizes['desired']:.1f}M ({sizes['desired_pct']:.1%})",
                       className="d-block text-success"),
            html.Small(f"Max: ${sizes['max']:.1f}M ({sizes['max_pct']:.1%})", className="d-block text-danger"),
            html.Hr(className="my-2")
        ]))

    return fig_alloc, fig_forecast, html.Div(bite_cards)


# Portfolio Page Metrics
@app.callback(
    [Output('port-nav', 'children'), Output('port-dry-powder', 'children'),
     Output('port-total-fund', 'children'), Output('port-target-return', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data')]
)
def update_portfolio_metrics(deals, config):
    m = calculate_portfolio_metrics(deals)
    dry_powder = config['fund_parameters']['dry_powder']
    req_irr = calculate_required_future_irr(m['weighted_irr'], m['total_nav'], dry_powder, config)
    return (
        f"${m['total_nav']:.1f}M",
        f"${dry_powder:.0f}M",
        f"${m['total_nav'] + dry_powder:.0f}M",
        f"{req_irr:.1%}"
    )


# Calculator Page
@app.callback(
    [Output('calc-current-nav', 'children'), Output('calc-current-irr', 'children'),
     Output('calc-num-deals', 'children'), Output('calc-total-fund', 'children'),
     Output('calc-target-twr', 'children'), Output('calc-dry-powder', 'children'),
     Output('calc-required-irr', 'children'), Output('calc-explanation', 'children'),
     Output('calc-waterfall', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data')]
)
def update_calculator(deals, config):
    m = calculate_portfolio_metrics(deals)
    dry_powder = config['fund_parameters']['dry_powder']
    total_fund = m['total_nav'] + dry_powder
    target_twr = config['fund_parameters']['target_net_twr']

    req_irr = calculate_required_future_irr(m['weighted_irr'], m['total_nav'], dry_powder, config)
    gap = req_irr - m['weighted_irr'] if m['total_nav'] > 0 else 0
    explanation = f"{'Higher' if gap > 0 else 'Lower'} than current portfolio by {abs(gap):.1%}" if m[
                                                                                                        'total_nav'] > 0 else "Add deals to calculate"

    # Waterfall
    invested_ratio = max(0, 1 - config['fund_parameters']['liquidity_reserve_pct'])
    idle_ratio = config['fund_parameters']['liquidity_reserve_pct']

    waterfall_steps = [
        ("1. Target Net TWR (to LPs)", f"{target_twr:.1%}"),
        ("2. + Management Fee", f"{config['fund_parameters']['management_fee']:.2%}"),
        ("3. + Loss Drag (impairments)", f"{config['fund_parameters']['loss_drag']:.1%}"),
        ("4. - Cash Yield on reserves", f"-{idle_ratio * config['fund_parameters']['cash_yield']:.2%}"),
        ("5. ÷ Invested Ratio", f"÷ {invested_ratio:.1%}"),
        ("6. + Carry Drag (if > hurdle)", f"+Variable ({config['fund_parameters']['carry_rate']:.0%})"),
        ("═══════════════════════", "═══════════"),
        ("REQUIRED GROSS DEAL RETURN", f"{req_irr:.1%}")
    ]

    waterfall_div = dbc.Table([
        html.Tbody([
            html.Tr([
                html.Td(step, style={'fontSize': '14px', 'fontWeight': 'bold' if '═' in step else 'normal'}),
                html.Td(val, className="text-end", style={
                    'fontSize': '14px',
                    'fontWeight': 'bold',
                    'color': COLORS['success'] if '═' in step else COLORS['dark']
                })
            ]) for step, val in waterfall_steps
        ])
    ], bordered=True, striped=True, hover=True, className="shadow-sm")

    return (
        f"${m['total_nav']:.1f}M",
        f"{m['weighted_irr']:.1%}",
        str(m['num_deals']),
        f"${total_fund:.0f}M",
        f"{target_twr:.1%}",
        f"${dry_powder:.0f}M",
        f"{req_irr:.1%}",
        explanation,
        waterfall_div
    )


# Dry Powder Page
@app.callback(
    [Output('dp-current', 'children'), Output('dp-planned', 'children'),
     Output('dp-distributions', 'children'), Output('dp-forecast-12m', 'children'),
     Output('dp-forecast-chart', 'figure'), Output('dp-monthly-table', 'children')],
    [Input('deals-store', 'data'), Input('placeholder-deals-store', 'data'), Input('config-store', 'data')]
)
def update_drypowder_page(deals, placeholders, config):
    m = calculate_portfolio_metrics(deals)
    dry_powder = config['fund_parameters']['dry_powder']

    total_planned = sum(p['size'] for p in placeholders)
    annual_dist = m['total_nav'] * config['fund_parameters']['distribution_rate']

    forecast = forecast_dry_powder(m['total_nav'], dry_powder, deals, placeholders, config, 12)
    forecast_12m = forecast[-1]['dry_powder']

    # Chart
    months = [f['month'] for f in forecast]
    dp_vals = [f['dry_powder'] for f in forecast]
    calls = [f['calls'] for f in forecast]
    dists = [f['distributions'] for f in forecast]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=months, y=dp_vals, name='Dry Powder',
        line=dict(color=C['blue'], width=3),
        fill='tozeroy',
        fillcolor=rgba(C['blue'], 0.2),
        marker=dict(size=6, color=C['sky'])
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=months, y=calls, name='Capital Calls',
        marker_color=C['red'],
        opacity=0.7
    ), secondary_y=True)
    fig.add_trace(go.Bar(
        x=months, y=dists, name='Distributions',
        marker_color=C['green'],
        opacity=0.7
    ), secondary_y=True)

    fig.update_xaxes(title_text="Month", gridcolor=C['border'])
    fig.update_yaxes(title_text="Dry Powder ($mm)", secondary_y=False, gridcolor=C['border'])
    fig.update_yaxes(title_text="Flows ($mm)", secondary_y=True, gridcolor=C['border'])
    fig.update_layout(**CHART_BASE, height=400, hovermode='x unified')

    # Table
    table_data = [{
        'Month': f['month'],
        'Dry Powder': f"${f['dry_powder']:.1f}M",
        'NAV': f"${f['nav']:.1f}M",
        'Distributions': f"${f['distributions']:.1f}M",
        'Calls': f"${f['calls']:.1f}M" if f['calls'] > 0 else "-"
    } for f in forecast]

    table = dash_table.DataTable(
        data=table_data,
        columns=[{"name": c, "id": c} for c in table_data[0].keys()],
        style_cell={'textAlign': 'left', 'padding': '10px', 'fontFamily': C['mono'], 'fontSize': '11px'},
        style_header={
            'backgroundColor': C['surface'],
            'color': C['text'],
            'fontWeight': 'bold',
            'border': f'1px solid {C["border"]}'
        },
        style_data={
            'backgroundColor': C['panel'],
            'color': C['text'],
            'border': f'1px solid {C["border"]}'
        },
        style_data_conditional=[{
            'if': {'row_index': 'odd'},
            'backgroundColor': C['surface']
        }],
        page_size=12
    )

    return (
        f"${dry_powder:.0f}M",
        f"${total_planned:.0f}M",
        f"${annual_dist:.0f}M",
        f"${forecast_12m:.0f}M",
        fig,
        table
    )


# ==================== TWR FORECASTER CALLBACKS ====================

@app.callback(
    Output('twr-current-irr', 'children'),
    Input('deals-store', 'data')
)
def update_twr_current_irr(deals):
    m = calculate_portfolio_metrics(deals)
    return f"{m['weighted_irr']:.1%}"


@app.callback(
    [Output('twr-distribution-chart', 'figure'), Output('twr-statistics', 'children'),
     Output('twr-sensitivity-chart', 'figure')],
    Input('btn-run-twr', 'n_clicks'),
    [State('deals-store', 'data'), State('config-store', 'data'),
     State('twr-future-mean', 'value'), State('twr-future-std', 'value'),
     State('twr-n-sims', 'value')],
    prevent_initial_call=True
)
def run_twr_simulation(n, deals, config, future_mean, future_std, n_sims):
    m = calculate_portfolio_metrics(deals)
    current_irr = m['weighted_irr']
    current_nav = m['total_nav']
    dry_powder = config['fund_parameters']['dry_powder']
    target_twr = config['fund_parameters']['target_net_twr']

    # Run Monte Carlo
    np.random.seed(42)
    future_irrs = np.random.normal(future_mean / 100, future_std / 100, n_sims)

    results = []
    for future_irr in future_irrs:
        # Blended portfolio IRR
        total = current_nav + dry_powder
        if total > 0:
            blended = (current_nav * current_irr + dry_powder * future_irr) / total
        else:
            blended = 0

        # Apply fees and drag
        mgmt_fee = config['fund_parameters']['management_fee']
        loss_drag = config['fund_parameters']['loss_drag']
        liq_reserve = config['fund_parameters']['liquidity_reserve_pct']
        cash_yield = config['fund_parameters']['cash_yield']
        carry_rate = config['fund_parameters']['carry_rate']
        hurdle = config['fund_parameters']['hurdle_rate']

        invested_ratio = 1 - liq_reserve
        gross_before_carry = (blended * invested_ratio) + (cash_yield * liq_reserve) - mgmt_fee - loss_drag

        # Carry drag
        if gross_before_carry > hurdle:
            carry_drag = (gross_before_carry - hurdle) * carry_rate
            net_twr = gross_before_carry - carry_drag
        else:
            net_twr = gross_before_carry

        results.append(net_twr)

    results = np.array(results)

    # Distribution chart
    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(
        x=results * 100, nbinsx=50,
        marker_color=C['blue'], opacity=0.7,
        name='Simulated TWR'
    ))
    fig_dist.add_vline(x=target_twr * 100, line_color=C['red'], line_width=3, line_dash='dash',
                       annotation_text=f"Target: {target_twr:.1%}", annotation_position="top right")
    fig_dist.add_vline(x=np.median(results) * 100, line_color=C['green'], line_width=3,
                       annotation_text=f"Median: {np.median(results):.1%}", annotation_position="top left")
    fig_dist.update_layout(
        **CHART_BASE,
        xaxis_title="Net TWR (%)", yaxis_title="Frequency",
        title=f"Distribution of Net TWR ({n_sims:,} Simulations)",
        height=400
    )

    # Statistics
    prob_above_target = (results >= target_twr).sum() / len(results)
    percentile_5 = np.percentile(results, 5)
    percentile_95 = np.percentile(results, 95)
    sharpe = (np.mean(results) - 0.03) / np.std(results)  # Assuming 3% risk-free

    stats_div = html.Div([
        html.Div([
            html.Strong("Probability of Hitting Target:", style={'color': C['text'], 'fontFamily': C['sans']}),
            html.H3(f"{prob_above_target:.1%}", style={
                'color': C['green'] if prob_above_target >= 0.75 else C['amber'] if prob_above_target >= 0.5 else C[
                    'red'],
                'fontFamily': C['mono'], 'marginTop': '0.5rem'
            })
        ], className="mb-3"),
        html.Hr(style={'borderColor': C['border']}),
        html.Div([
            html.P([html.Strong("Mean TWR: "),
                    html.Span(f"{np.mean(results):.2%}", style={'color': C['blue'], 'fontFamily': C['mono']})]),
            html.P([html.Strong("Median TWR: "),
                    html.Span(f"{np.median(results):.2%}", style={'color': C['green'], 'fontFamily': C['mono']})]),
            html.P([html.Strong("Std Dev: "),
                    html.Span(f"{np.std(results):.2%}", style={'color': C['muted'], 'fontFamily': C['mono']})]),
            html.P([html.Strong("5th Percentile: "),
                    html.Span(f"{percentile_5:.2%}", style={'color': C['red'], 'fontFamily': C['mono']})]),
            html.P([html.Strong("95th Percentile: "),
                    html.Span(f"{percentile_95:.2%}", style={'color': C['green'], 'fontFamily': C['mono']})]),
            html.P([html.Strong("Sharpe Ratio: "),
                    html.Span(f"{sharpe:.2f}", style={'color': C['purple'], 'fontFamily': C['mono']})]),
        ], style={'fontSize': '14px'})
    ])

    # Sensitivity Analysis
    future_irr_range = np.linspace(0.15, 0.35, 20)
    twr_sensitivity = []
    for fir in future_irr_range:
        total = current_nav + dry_powder
        blended = (current_nav * current_irr + dry_powder * fir) / total if total > 0 else 0
        invested_ratio = 1 - liq_reserve
        gross = (blended * invested_ratio) + (cash_yield * liq_reserve) - mgmt_fee - loss_drag
        if gross > hurdle:
            net = gross - (gross - hurdle) * carry_rate
        else:
            net = gross
        twr_sensitivity.append(net)

    fig_sens = go.Figure()
    fig_sens.add_trace(go.Scatter(
        x=future_irr_range * 100, y=np.array(twr_sensitivity) * 100,
        mode='lines+markers', name='Net TWR',
        line=dict(color=C['blue'], width=3),
        marker=dict(size=6, color=C['sky'])
    ))
    fig_sens.add_hline(y=target_twr * 100, line_color=C['red'], line_dash='dash',
                       annotation_text=f"Target: {target_twr:.1%}")
    fig_sens.update_layout(
        **CHART_BASE,
        xaxis_title="Future Deal IRR (%)", yaxis_title="Net TWR (%)",
        title="How Net TWR Changes with Future Deal Performance",
        height=400
    )

    return fig_dist, stats_div, fig_sens


# ==================== CASHFLOWS CALLBACKS ====================

# Populate deal dropdown
@app.callback(
    Output('cf-deal', 'options'),
    Input('deals-store', 'data')
)
def populate_cf_deals(deals):
    if not deals:
        return []
    return [{"label": d['name'], "value": d['name']} for d in deals]


# Toggle cashflow modal
@app.callback(
    Output('modal-cashflow', 'is_open'),
    [Input('btn-open-cashflow', 'n_clicks'), Input('btn-cancel-cf', 'n_clicks'), Input('btn-submit-cf', 'n_clicks')],
    State('modal-cashflow', 'is_open'),
    prevent_initial_call=True
)
def toggle_cf_modal(o, c, s, is_open):
    return not is_open


# Add cashflow
@app.callback(
    Output('cashflows-store', 'data', allow_duplicate=True),
    Input('btn-submit-cf', 'n_clicks'),
    [State('cf-deal', 'value'), State('cf-date', 'value'),
     State('cf-type', 'value'), State('cf-amount', 'value'),
     State('cashflows-store', 'data')],
    prevent_initial_call=True
)
def add_cashflow(n, deal, date, cf_type, amount, cashflows):
    if not all([deal, date, cf_type, amount]):
        return cashflows

    return cashflows + [{
        'deal': deal,
        'date': date,
        'type': cf_type,
        'amount': float(amount),
        'timestamp': datetime.now().isoformat()
    }]


# Delete cashflow
@app.callback(
    Output('cashflows-store', 'data', allow_duplicate=True),
    Input({'type': 'delete-cashflow', 'index': ALL}, 'n_clicks'),
    State('cashflows-store', 'data'),
    prevent_initial_call=True
)
def delete_cashflow(n_clicks, cashflows):
    if not any(n_clicks):
        return cashflows
    ctx = callback_context
    if not ctx.triggered:
        return cashflows
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == '':
        return cashflows
    button_info = json.loads(button_id)
    delete_idx = button_info['index']
    if 0 <= delete_idx < len(cashflows):
        cashflows.pop(delete_idx)
    return cashflows


# Update cashflow metrics
@app.callback(
    [Output('cf-total-calls', 'children'), Output('cf-total-dists', 'children'),
     Output('cf-net', 'children'), Output('cf-actual-irr', 'children')],
    Input('cashflows-store', 'data')
)
def update_cf_metrics(cashflows):
    if not cashflows:
        return "$0.0M", "$0.0M", "$0.0M", "N/A"

    total_calls = sum(cf['amount'] for cf in cashflows if cf['type'] == 'Call')
    total_dists = sum(cf['amount'] for cf in cashflows if cf['type'] == 'Distribution')
    net = total_dists - total_calls

    # Calculate IRR (simplified - would need numpy_financial.irr for real calc)
    irr_text = "Add more CFs"
    if len(cashflows) >= 2:
        # Sort by date
        sorted_cfs = sorted(cashflows, key=lambda x: x['date'])
        dates = [
            datetime.fromisoformat(cf['date'].replace('Z', '+00:00') if 'T' in cf['date'] else cf['date'] + 'T00:00:00')
            for cf in sorted_cfs]
        amounts = [-cf['amount'] if cf['type'] == 'Call' else cf['amount'] for cf in sorted_cfs]

        # Simple approximate IRR
        if len(amounts) >= 2 and amounts[0] < 0:
            days = [(d - dates[0]).days for d in dates]
            years = [d / 365.25 for d in days]
            # Try simple approximation
            try:
                total_in = sum(abs(a) for a in amounts if a < 0)
                total_out = sum(a for a in amounts if a > 0)
                if total_in > 0 and len(years) > 0 and years[-1] > 0:
                    simple_return = (total_out / total_in) - 1
                    annualized = (1 + simple_return) ** (1 / years[-1]) - 1
                    irr_text = f"{annualized:.1%}"
            except:
                irr_text = "Calc Error"

    return f"${total_calls:.1f}M", f"${total_dists:.1f}M", f"${net:.1f}M", irr_text


# Cashflows table
@app.callback(
    Output('cashflows-table', 'children'),
    Input('cashflows-store', 'data')
)
def update_cf_table(cashflows):
    if not cashflows:
        return html.P("No cashflows yet. Add cashflows to track actual performance.", className="text-muted")

    rows = []
    for idx, cf in enumerate(sorted(cashflows, key=lambda x: x['date'], reverse=True)):
        rows.append(dbc.Card([dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Strong(cf['deal'], style={'color': C['blue'], 'fontFamily': C['mono']}),
                    html.Br(),
                    html.Small(cf['date'], style={'color': C['muted'], 'fontFamily': C['mono']})
                ], width=4),
                dbc.Col([
                    html.Span(cf['type'], style={
                        'color': C['red'] if cf['type'] == 'Call' else C['green'],
                        'fontFamily': C['sans'], 'fontWeight': 'bold'
                    })
                ], width=2),
                dbc.Col([
                    html.H5(f"${cf['amount']:.1f}M", style={
                        'color': C['red'] if cf['type'] == 'Call' else C['green'],
                        'fontFamily': C['mono'], 'marginBottom': 0
                    })
                ], width=4),
                dbc.Col([
                    dbc.Button("🗑️", id={'type': 'delete-cashflow', 'index': idx},
                               color="danger", size="sm", outline=True)
                ], width=2, className="text-end")
            ])
        ])], className="mb-2 shadow-sm"))

    return html.Div(rows)


# Per-deal summary
@app.callback(
    Output('cashflows-per-deal', 'children'),
    Input('cashflows-store', 'data')
)
def update_cf_per_deal(cashflows):
    if not cashflows:
        return html.P("No cashflows to analyze", className="text-muted")

    # Group by deal
    by_deal = {}
    for cf in cashflows:
        deal = cf['deal']
        if deal not in by_deal:
            by_deal[deal] = {'calls': 0, 'dists': 0, 'count': 0}
        if cf['type'] == 'Call':
            by_deal[deal]['calls'] += cf['amount']
        else:
            by_deal[deal]['dists'] += cf['amount']
        by_deal[deal]['count'] += 1

    cards = []
    for deal, data in by_deal.items():
        net = data['dists'] - data['calls']
        cards.append(dbc.Card([dbc.CardBody([
            html.H6(deal, style={'color': C['text'], 'fontFamily': C['sans']}),
            dbc.Row([
                dbc.Col([html.Small("Calls:", className="text-muted"), html.Br(),
                         html.Strong(f"${data['calls']:.1f}M", style={'color': C['red'], 'fontFamily': C['mono']})],
                        width=4),
                dbc.Col([html.Small("Dists:", className="text-muted"), html.Br(),
                         html.Strong(f"${data['dists']:.1f}M", style={'color': C['green'], 'fontFamily': C['mono']})],
                        width=4),
                dbc.Col([html.Small("Net:", className="text-muted"), html.Br(),
                         html.Strong(f"${net:.1f}M", style={'color': C['blue'], 'fontFamily': C['mono']})], width=4),
            ])
        ])], className="mb-2", style={'backgroundColor': C['surface']}))

    return html.Div(cards)


# ==================== PRO FORMA CALLBACKS ====================

# Populate deal dropdown
@app.callback(
    Output('pf-deal-select', 'options'),
    Input('pipeline-store', 'data')
)
def populate_pf_deals(pipeline):
    if not pipeline:
        return [{"label": "No pipeline deals", "value": ""}]
    return [{"label": f"{p['name']} (${p['size']:.1f}M @ {p['target_irr']:.1%})", "value": i}
            for i, p in enumerate(pipeline)]


# Add deal to scenario
@app.callback(
    Output('proforma-scenario-store', 'data', allow_duplicate=True),
    Input('btn-add-to-pf', 'n_clicks'),
    [State('pf-deal-select', 'value'), State('pipeline-store', 'data'),
     State('pf-custom-name', 'value'), State('pf-custom-size', 'value'),
     State('pf-custom-irr', 'value'), State('proforma-scenario-store', 'data')],
    prevent_initial_call=True
)
def add_to_proforma(n, selected_idx, pipeline, custom_name, custom_size, custom_irr, scenario):
    if custom_name and custom_size and custom_irr:
        # Add custom deal
        return scenario + [{
            'name': custom_name,
            'size': float(custom_size),
            'target_irr': float(custom_irr) / 100,
            'strategy': 'GP-Led (Multi-Asset)',  # Default
            'source': 'custom'
        }]
    elif selected_idx and selected_idx != '':
        # Add pipeline deal
        idx = int(selected_idx)
        if 0 <= idx < len(pipeline):
            p = pipeline[idx]
            return scenario + [{
                'name': p['name'],
                'size': p['size'],
                'target_irr': p['target_irr'],
                'strategy': p['type'],
                'source': 'pipeline'
            }]
    return scenario


# Reset scenario
@app.callback(
    Output('proforma-scenario-store', 'data', allow_duplicate=True),
    Input('btn-reset-pf', 'n_clicks'),
    prevent_initial_call=True
)
def reset_proforma(n):
    return []


# Show scenario deals
@app.callback(
    Output('pf-scenario-deals', 'children'),
    Input('proforma-scenario-store', 'data')
)
def show_pf_scenario(scenario):
    if not scenario:
        return html.P("No deals in scenario yet. Add deals above.", className="text-muted",
                      style={'fontFamily': C['mono']})

    items = []
    for i, deal in enumerate(scenario):
        items.append(html.Div([
            html.Strong(f"{i + 1}. {deal['name']}", style={'color': C['blue'], 'fontFamily': C['mono']}),
            html.Span(f" — ${deal['size']:.1f}M @ {deal['target_irr']:.1%}",
                      style={'color': C['muted'], 'fontFamily': C['mono']}),
            html.Br()
        ]))

    total_size = sum(d['size'] for d in scenario)
    items.append(html.Hr(style={'borderColor': C['border']}))
    items.append(html.P([
        html.Strong("Total Scenario Size: ", style={'fontFamily': C['sans'], 'color': C['text']}),
        html.Span(f"${total_size:.1f}M", style={'fontFamily': C['mono'], 'color': C['green']})
    ]))

    return html.Div(items)


# Comparison table
@app.callback(
    Output('pf-comparison-table', 'children'),
    [Input('proforma-scenario-store', 'data'), Input('deals-store', 'data'), Input('config-store', 'data')]
)
def update_pf_comparison(scenario, deals, config):
    # Current metrics
    current_m = calculate_portfolio_metrics(deals)
    current_nav = current_m['total_nav']
    current_irr = current_m['weighted_irr']
    current_deals_count = current_m['num_deals']
    current_top1 = current_m['concentration_top1']
    current_eff_n = current_m['effective_n']
    dry_powder = config['fund_parameters']['dry_powder']
    current_req_irr = calculate_required_future_irr(current_irr, current_nav, dry_powder, config)

    # Pro forma metrics (current + scenario)
    if scenario:
        proforma_deals = deals + scenario
        pf_m = calculate_portfolio_metrics(proforma_deals)
        pf_nav = pf_m['total_nav']
        pf_irr = pf_m['weighted_irr']
        pf_deals_count = pf_m['num_deals']
        pf_top1 = pf_m['concentration_top1']
        pf_eff_n = pf_m['effective_n']
        scenario_size = sum(d['size'] for d in scenario)
        pf_dry_powder = dry_powder - scenario_size
        pf_req_irr = calculate_required_future_irr(pf_irr, pf_nav, pf_dry_powder, config)
    else:
        pf_nav = current_nav
        pf_irr = current_irr
        pf_deals_count = current_deals_count
        pf_top1 = current_top1
        pf_eff_n = current_eff_n
        pf_req_irr = current_req_irr

    # Build comparison table
    comparison_data = [
        {"Metric": "Total NAV ($mm)", "Current": f"${current_nav:.1f}", "Pro Forma": f"${pf_nav:.1f}",
         "Change": f"+${pf_nav - current_nav:.1f}" if pf_nav > current_nav else "$0.0"},
        {"Metric": "Weighted IRR", "Current": f"{current_irr:.2%}", "Pro Forma": f"{pf_irr:.2%}",
         "Change": f"+{pf_irr - current_irr:.2%}" if pf_irr > current_irr else "0.0%"},
        {"Metric": "Required Future IRR", "Current": f"{current_req_irr:.2%}", "Pro Forma": f"{pf_req_irr:.2%}",
         "Change": f"{pf_req_irr - current_req_irr:+.2%}"},
        {"Metric": "Number of Deals", "Current": str(current_deals_count), "Pro Forma": str(pf_deals_count),
         "Change": f"+{pf_deals_count - current_deals_count}" if pf_deals_count > current_deals_count else "0"},
        {"Metric": "Top 1 Concentration", "Current": f"{current_top1:.1%}", "Pro Forma": f"{pf_top1:.1%}",
         "Change": f"{pf_top1 - current_top1:+.1%}"},
        {"Metric": "Effective # Positions", "Current": f"{current_eff_n:.1f}", "Pro Forma": f"{pf_eff_n:.1f}",
         "Change": f"+{pf_eff_n - current_eff_n:.1f}" if pf_eff_n > current_eff_n else "0.0"},
    ]

    return dash_table.DataTable(
        data=comparison_data,
        columns=[{"name": c, "id": c} for c in ["Metric", "Current", "Pro Forma", "Change"]],
        style_cell={'textAlign': 'left', 'padding': '12px', 'fontFamily': C['mono'], 'fontSize': '13px'},
        style_header={'backgroundColor': C['surface'], 'color': C['text'], 'fontWeight': 'bold',
                      'border': f'1px solid {C["border"]}'},
        style_data={'backgroundColor': C['panel'], 'color': C['text'], 'border': f'1px solid {C["border"]}'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': C['surface']},
            {'if': {'column_id': 'Change'}, 'fontWeight': 'bold', 'color': C['blue']}
        ]
    )


# Pro forma charts
@app.callback(
    [Output('pf-strategy-chart', 'figure'), Output('pf-concentration-chart', 'figure')],
    [Input('proforma-scenario-store', 'data'), Input('deals-store', 'data')]
)
def update_pf_charts(scenario, deals):
    # Current
    current_m = calculate_portfolio_metrics(deals)

    # Pro forma
    if scenario:
        proforma_deals = deals + scenario
        pf_m = calculate_portfolio_metrics(proforma_deals)
    else:
        pf_m = current_m

    # Strategy comparison
    fig_strat = go.Figure()
    if current_m['by_strategy']:
        current_strats = list(current_m['by_strategy'].keys())
        current_vals = [current_m['by_strategy'][s]['nav'] for s in current_strats]
        fig_strat.add_trace(go.Bar(name='Current', x=current_strats, y=current_vals, marker_color=C['blue']))

    if pf_m['by_strategy']:
        pf_strats = list(pf_m['by_strategy'].keys())
        pf_vals = [pf_m['by_strategy'][s]['nav'] for s in pf_strats]
        fig_strat.add_trace(go.Bar(name='Pro Forma', x=pf_strats, y=pf_vals, marker_color=C['green']))

    fig_strat.update_layout(**CHART_BASE, barmode='group', yaxis_title="NAV ($mm)", height=350)

    # Concentration comparison
    fig_conc = go.Figure()
    current_conc = [current_m['concentration_top1'] * 100, current_m['concentration_top3'] * 100,
                    current_m['concentration_top5'] * 100]
    pf_conc = [pf_m['concentration_top1'] * 100, pf_m['concentration_top3'] * 100, pf_m['concentration_top5'] * 100]

    cats = ['Top 1', 'Top 3', 'Top 5']
    fig_conc.add_trace(go.Bar(name='Current', x=cats, y=current_conc, marker_color=C['blue']))
    fig_conc.add_trace(go.Bar(name='Pro Forma', x=cats, y=pf_conc, marker_color=C['green']))

    fig_conc.add_hline(y=15, line_color=C['red'], line_dash='dash', opacity=0.5)
    fig_conc.add_hline(y=40, line_color=C['red'], line_dash='dash', opacity=0.5)
    fig_conc.add_hline(y=60, line_color=C['red'], line_dash='dash', opacity=0.5)

    fig_conc.update_layout(**CHART_BASE, barmode='group', yaxis_title="% of NAV", height=350)

    return fig_strat, fig_conc


# Analytics Page Callbacks
@app.callback(
    [Output('analytics-concentration', 'figure'), Output('analytics-diversification', 'children'),
     Output('analytics-strategy', 'figure'), Output('analytics-vintage', 'figure'),
     Output('analytics-sector', 'figure')],
    Input('deals-store', 'data')
)
def update_analytics(deals):
    m = calculate_portfolio_metrics(deals)

    # Concentration chart
    cats = ['Top 1 Deal', 'Top 3 Deals', 'Top 5 Deals']
    vals = [m['concentration_top1'] * 100, m['concentration_top3'] * 100, m['concentration_top5'] * 100]
    limits = [15, 40, 60]
    colors_conc = [C['red'] if v > l else C['green'] for v, l in zip(vals, limits)]

    fig_conc = go.Figure(data=[go.Bar(
        x=cats, y=vals, marker_color=colors_conc,
        text=[f"{v:.1f}%" for v in vals], textposition='outside',
        textfont=dict(color=C['text'], family=C['mono'])
    )])
    for limit in limits:
        fig_conc.add_hline(y=limit, line_dash='dash', line_color=C['red'], opacity=0.5)
    fig_conc.update_layout(**CHART_BASE, yaxis_title="% of NAV", height=300)

    # Diversification metrics
    div_div = html.Div([
        html.P([html.Strong("Effective # of Positions: ", style={'fontFamily': C['sans'], 'color': C['text']}),
                html.Span(f"{m['effective_n']:.1f}", style={'fontFamily': C['mono'], 'color': C['blue']})]),
        html.P([html.Strong("Target: ", style={'fontFamily': C['sans'], 'color': C['text']}),
                html.Span("≥ 10 positions", style={'fontFamily': C['mono'], 'color': C['muted']})]),
        html.P([html.Strong("Status: ", style={'fontFamily': C['sans'], 'color': C['text']}),
                html.Span("✓ Well Diversified" if m['effective_n'] >= 10 else "⚠ Low Diversification",
                          style={'color': C['green'] if m['effective_n'] >= 10 else C['red'],
                                 'fontFamily': C['sans']})])
    ])

    # Strategy chart
    if m['by_strategy']:
        strat_labels = list(m['by_strategy'].keys())
        strat_vals = [m['by_strategy'][s]['nav'] for s in strat_labels]
        colors_strat = [C['blue'], C['purple'], C['teal'], C['green']][:len(strat_labels)]
        fig_strat = go.Figure(data=[go.Pie(
            labels=strat_labels, values=strat_vals, hole=0.3,
            marker=dict(colors=colors_strat),
            textfont=dict(color=C['text'], family=C['mono'])
        )])
        fig_strat.update_layout(**CHART_BASE, height=300, margin=dict(t=20, b=0, l=0, r=0), showlegend=False)
    else:
        fig_strat = go.Figure()
        fig_strat.update_layout(**CHART_BASE)

    # Vintage chart
    if m['by_vintage']:
        vint_labels = [str(v) for v in sorted(m['by_vintage'].keys())]
        vint_vals = [m['by_vintage'][int(v)]['nav'] for v in vint_labels]
        fig_vint = go.Figure(data=[go.Bar(
            x=vint_labels, y=vint_vals, marker_color=C['blue'],
            textfont=dict(color=C['text'], family=C['mono'])
        )])
        fig_vint.update_layout(**CHART_BASE, yaxis_title="NAV ($mm)", height=300)
    else:
        fig_vint = go.Figure()
        fig_vint.update_layout(**CHART_BASE)

    # Sector chart
    if m['by_sector']:
        sec_labels = list(m['by_sector'].keys())
        sec_vals = [m['by_sector'][s]['nav'] for s in sec_labels]
        colors_sec = [C['teal'], C['purple'], C['amber'], C['green'], C['pink']][:len(sec_labels)]
        fig_sec = go.Figure(data=[go.Pie(
            labels=sec_labels, values=sec_vals, hole=0.3,
            marker=dict(colors=colors_sec),
            textfont=dict(color=C['text'], family=C['mono'])
        )])
        fig_sec.update_layout(**CHART_BASE, height=300, margin=dict(t=20, b=0, l=0, r=0), showlegend=False)
    else:
        fig_sec = go.Figure()
        fig_sec.update_layout(**CHART_BASE)

    return fig_conc, div_div, fig_strat, fig_vint, fig_sec


# Dashboard Recent Activity & Pipeline Status callbacks
@app.callback(
    [Output('dash-recent-activity', 'children'), Output('dash-pipeline-status', 'children')],
    [Input('deals-store', 'data'), Input('pipeline-store', 'data')]
)
def update_dashboard_activity(deals, pipeline):
    # Recent Activity
    if not deals:
        recent = html.P("No deals yet", className="text-muted", style={'fontFamily': C['mono']})
    else:
        recent_deals = sorted(deals, key=lambda x: x.get('date_added', ''), reverse=True)[:5]
        activity_items = []
        for d in recent_deals:
            activity_items.append(html.Div([
                html.Strong(d['name'], style={'color': C['blue'], 'fontFamily': C['mono']}),
                html.Br(),
                html.Small(f"${d['size']:.1f}M • {d['target_irr']:.1%} IRR",
                           style={'color': C['muted'], 'fontFamily': C['mono']}),
                html.Hr(style={'borderColor': C['border'], 'margin': '0.5rem 0'})
            ]))
        recent = html.Div(activity_items)

    # Pipeline Status
    if not pipeline:
        pipe_status = html.P("No pipeline deals", className="text-muted", style={'fontFamily': C['mono']})
    else:
        stage_counts = {}
        for p in pipeline:
            stage = p.get('stage', 'Screening')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        pipe_items = []
        stage_colors = {
            'Screening': C['muted'],
            'Due Diligence': C['amber'],
            'Term Sheet': C['blue'],
            'Final Docs': C['green']
        }
        for stage, count in stage_counts.items():
            pipe_items.append(html.Div([
                html.Span("●", style={'color': stage_colors.get(stage, C['muted']), 'marginRight': '0.5rem'}),
                html.Strong(f"{stage}: ", style={'fontFamily': C['sans'], 'color': C['text']}),
                html.Span(f"{count} deals", style={'fontFamily': C['mono'], 'color': C['muted']})
            ], style={'marginBottom': '0.5rem'}))
        pipe_status = html.Div(pipe_items)

    return recent, pipe_status


# Export CSV
@app.callback(
    Output("download-csv", "data"),
    Input("btn-export", "n_clicks"),
    [State("deals-store", "data"), State("placeholder-deals-store", "data"), State("pipeline-store", "data")],
    prevent_initial_call=True
)
def export_all(n, deals, placeholders, pipeline):
    if deals:
        df_deals = pd.DataFrame(deals)
        df_deals.to_csv('current_portfolio.csv', index=False)
    if placeholders:
        df_ph = pd.DataFrame(placeholders)
        df_ph.to_csv('placeholder_deals.csv', index=False)
    if pipeline:
        df_pipe = pd.DataFrame(pipeline)
        df_pipe.to_csv('pipeline.csv', index=False)

    return dcc.send_data_frame(pd.DataFrame(deals).to_csv if deals else pd.DataFrame().to_csv,
                               f"portfolio_{date.today()}.csv", index=False)


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("ULTIMATE EVERGREEN FUND DASHBOARD")
    print("=" * 80)
    print("\n✅ Starting on http://localhost:8050")
    print("\n🎯 Features:")
    print("   • Current Portfolio Management")
    print("   • Pro Forma Portfolio (Placeholder Deals)")
    print("   • 12-Month Dry Powder Forecasting")
    print("   • Deal Bite Sizing (Min/Desired/Max)")
    print("   • Pipeline Management")
    print("   • Return Calculator with Waterfall")
    print("   • Comprehensive Analytics")
    print("\nPress CTRL+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=8050)
