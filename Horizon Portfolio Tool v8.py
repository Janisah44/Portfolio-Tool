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
            html.I(className="fas fa-chart-line me-3", style={'fontSize': '32px'}),
            dbc.NavbarBrand("ULTIMATE Evergreen Fund Manager", style={'fontSize': '24px', 'fontWeight': 'bold'})
        ]),
        html.Div(id='live-clock', style={'fontSize': '14px', 'color': '#CCC'})
    ], fluid=True),
    color=COLORS['dark'], dark=True, className="mb-4", style={'padding': '1.2rem 2rem'}
)

sidebar = dbc.Card([
    dbc.CardBody([
        html.H5("📊 Navigation", className="mb-4", style={'fontWeight': 'bold'}),
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
            dbc.NavLink([html.I(className="fas fa-funnel-dollar me-2"), "Pipeline"], href="/pipeline", active="exact"),
            dbc.NavLink([html.I(className="fas fa-chart-bar me-2"), "Analytics"], href="/analytics", active="exact"),
            dbc.NavLink([html.I(className="fas fa-cog me-2"), "Settings"], href="/settings", active="exact"),
        ], vertical=True, pills=True),
        html.Hr(),
        html.H6("📈 Quick Stats", className="mb-3", style={'fontWeight': 'bold'}),
        html.Div(id='sidebar-stats'),
        html.Hr(),
        dbc.Button("📥 Export All", id="btn-export", color="secondary", size="sm", className="w-100"),
        dcc.Download(id="download-csv"),
    ])
], style={'position': 'sticky', 'top': '20px'})

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='deals-store', data=[]),
    dcc.Store(id='placeholder-deals-store', data=[]),
    dcc.Store(id='pipeline-store', data=[]),
    dcc.Store(id='config-store', data=DEFAULT_CONFIG),
    dcc.Interval(id='clock-interval', interval=1000),
    navbar,
    dbc.Row([
        dbc.Col(sidebar, width=2),
        dbc.Col(html.Div(id="page-content"), width=10)
    ])
], fluid=True, style={'backgroundColor': '#F8F9FA'})


# ==================== PAGE LAYOUTS ====================

def dashboard_page():
    return html.Div([
        html.H2("📊 Fund Dashboard", className="mb-4", style={'fontWeight': 'bold'}),

        # Top KPIs
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("💰 Current NAV", className="text-muted mb-2"),
                html.H3(id="dash-nav", style={'color': COLORS['success'], 'fontWeight': 'bold'}),
                html.Small(id="dash-num-deals", className="text-muted")
            ])], className="shadow-sm border-0"), width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("💵 Dry Powder", className="text-muted mb-2"),
                html.H3(id="dash-dry-powder", style={'color': COLORS['primary'], 'fontWeight': 'bold'}),
                html.Small("Available", className="text-muted")
            ])], className="shadow-sm border-0"), width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("📊 Total Fund", className="text-muted mb-2"),
                html.H3(id="dash-total", style={'color': COLORS['dark'], 'fontWeight': 'bold'}),
                html.Small("NAV + Powder", className="text-muted")
            ])], className="shadow-sm border-0"), width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("🎯 Portfolio IRR", className="text-muted mb-2"),
                html.H3(id="dash-current-irr", style={'color': COLORS['success'], 'fontWeight': 'bold'}),
                html.Small("Weighted", className="text-muted")
            ])], className="shadow-sm border-0"), width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("🚀 Required IRR", className="text-muted mb-2"),
                html.H3(id="dash-req-irr", style={'color': COLORS['warning'], 'fontWeight': 'bold'}),
                html.Small("Future Deals", className="text-muted")
            ])], className="shadow-sm border-0"), width=2),

            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("📅 Placeholders", className="text-muted mb-2"),
                html.H3(id="dash-placeholders", style={'color': COLORS['info'], 'fontWeight': 'bold'}),
                html.Small(id="dash-placeholder-value", className="text-muted")
            ])], className="shadow-sm border-0"), width=2),
        ], className="mb-4"),

        # Charts Row
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Portfolio Allocation",
                                   style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
                    dbc.CardBody([dcc.Graph(id='dash-allocation-chart', config={'displayModeBar': False})])
                ], className="shadow-sm border-0")
            ], width=4),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Dry Powder Forecast (12 Months)",
                                   style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
                    dbc.CardBody([dcc.Graph(id='dash-forecast-chart', config={'displayModeBar': False})])
                ], className="shadow-sm border-0")
            ], width=4),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Deal Bite Sizing Guide",
                                   style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
                    dbc.CardBody([html.Div(id='dash-bite-sizing')])
                ], className="shadow-sm border-0")
            ], width=4),
        ], className="mb-4"),

        # Recent Activity
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Portfolio Activity",
                                   style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
                    dbc.CardBody([html.Div(id='dash-recent-activity')])
                ], className="shadow-sm border-0")
            ], width=6),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Pipeline Status", style={'fontWeight': 'bold', 'backgroundColor': COLORS['light']}),
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
    elif pathname == '/pipeline':
        return pipeline_page()
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
        style_cell={'textAlign': 'left', 'padding': '12px'},
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white', 'fontWeight': 'bold'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}]
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
        fig_alloc = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
        fig_alloc.update_layout(height=300, margin=dict(t=20, b=0, l=0, r=0))
    else:
        fig_alloc = go.Figure()

    # Forecast
    forecast = forecast_dry_powder(m['total_nav'], dry_powder, deals, placeholders, config, 12)
    months = [f['month'] for f in forecast]
    dp_values = [f['dry_powder'] for f in forecast]

    fig_forecast = go.Figure()
    fig_forecast.add_trace(go.Scatter(
        x=months, y=dp_values, mode='lines+markers', name='Dry Powder',
        line=dict(color=COLORS['primary'], width=3), fill='tozeroy'
    ))
    fig_forecast.update_layout(
        height=300, margin=dict(t=20, b=40, l=40, r=20),
        xaxis_title="Month", yaxis_title="Dry Powder ($mm)",
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
    fig.add_trace(
        go.Scatter(x=months, y=dp_vals, name='Dry Powder', line=dict(color=COLORS['primary'], width=3), fill='tozeroy'),
        secondary_y=False)
    fig.add_trace(go.Bar(x=months, y=calls, name='Capital Calls', marker_color=COLORS['danger']), secondary_y=True)
    fig.add_trace(go.Bar(x=months, y=dists, name='Distributions', marker_color=COLORS['success']), secondary_y=True)

    fig.update_xaxes(title_text="Month")
    fig.update_yaxes(title_text="Dry Powder ($mm)", secondary_y=False)
    fig.update_yaxes(title_text="Flows ($mm)", secondary_y=True)
    fig.update_layout(height=400, hovermode='x unified')

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
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white', 'fontWeight': 'bold'},
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
