"""
EVERGREEN FUND INTERACTIVE DASHBOARD - COMPLETE
Professional portfolio management system

Run with: python evergreen_fund_dashboard.py
Access at: http://localhost:8050
"""

import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, date
import json


# ==================== COMMITMENT PACING MODEL ====================

class EvergreenCommitmentPacingModel:
    """Commitment pacing model for evergreen secondaries and co-investment funds"""

    def __init__(self, config=None):
        if config is None:
            config = self.default_config()
        self.config = config
        self.results = None

    @staticmethod
    def default_config():
        return {
            'fund_parameters': {
                'target_fund_size': 500,
                'current_nav': 50,
                'deployment_timeline_years': 5,
                'liquidity_reserve_pct': 0.10,
                'target_twr': 0.13,
                'distribution_rate': 0.20,
            },
            'strategies': {
                'GP-Led Secondaries': {
                    'allocation': 0.40,
                    'avg_deal_size': 30,
                    'draw_period_years': 0.5,
                    'pct_drawn_at_close': 0.90,
                },
                'LP-Led Secondaries': {
                    'allocation': 0.30,
                    'avg_deal_size': 40,
                    'draw_period_years': 1.0,
                    'pct_drawn_at_close': 0.80,
                },
                'Co-Investments': {
                    'allocation': 0.30,
                    'avg_deal_size': 20,
                    'draw_period_years': 2.0,
                    'pct_drawn_at_close': 0.50,
                },
            },
            'pacing': {
                'annual_commitment_pct': [0.25, 0.25, 0.20, 0.15, 0.15],
            }
        }

    def calculate_pacing_schedule(self):
        fp = self.config['fund_parameters']
        strategies = self.config['strategies']
        pacing_pct = self.config['pacing']['annual_commitment_pct']

        remaining = fp['target_fund_size'] - fp['current_nav']
        years = [f'Year {i + 1}' for i in range(5)]

        results = {
            'years': years,
            'remaining_to_deploy': remaining,
            'commitments': {},
            'draws': {},
            'distributions': [],
            'nav_projection': [],
            'liquidity_analysis': {},
            'deal_flow_requirements': {},
        }

        total_commitments = [remaining * pct for pct in pacing_pct]
        results['commitments']['total'] = total_commitments

        for strategy_name, strategy_config in strategies.items():
            alloc = strategy_config['allocation']
            avg_size = strategy_config['avg_deal_size']
            draw_period = strategy_config['draw_period_years']
            pct_close = strategy_config['pct_drawn_at_close']

            strategy_commits = [commit * alloc for commit in total_commitments]
            results['commitments'][strategy_name] = strategy_commits

            if draw_period <= 1:
                strategy_draws = [[commit * pct_close if j == i else 0
                                   for j in range(5)] for i, commit in enumerate(strategy_commits)]
            else:
                strategy_draws = []
                for i, commit in enumerate(strategy_commits):
                    year_draws = [0] * 5
                    year_draws[i] = commit * pct_close
                    if i < 4:
                        year_draws[i + 1] = commit * (1 - pct_close) / 2
                    if i < 3 and draw_period > 1.5:
                        year_draws[i + 2] = commit * (1 - pct_close) / 2
                    strategy_draws.append(year_draws)

            total_strategy_draws = [sum(draws[j] for draws in strategy_draws)
                                    for j in range(5)]
            results['draws'][strategy_name] = total_strategy_draws

            deals_per_year = [commit / avg_size for commit in strategy_commits]
            results['deal_flow_requirements'][strategy_name] = deals_per_year

        results['draws']['total'] = [
            sum(results['draws'][s][i] for s in strategies.keys())
            for i in range(5)
        ]

        nav = fp['current_nav']
        for i in range(5):
            dist = nav * fp['distribution_rate']
            results['distributions'].append(dist)

            draws = results['draws']['total'][i]
            growth = (nav + (nav + draws - dist)) / 2 * fp['target_twr']
            nav = nav + draws - dist + growth
            results['nav_projection'].append(nav)

        for i in range(5):
            year = years[i]
            cash_needed = results['draws']['total'][i]
            beg_nav = fp['current_nav'] if i == 0 else results['nav_projection'][i - 1]
            cash_available = results['distributions'][i] + beg_nav * fp['liquidity_reserve_pct']
            buffer = cash_available - cash_needed
            buffer_pct = buffer / cash_needed if cash_needed > 0 else 0

            results['liquidity_analysis'][year] = {
                'cash_needed': cash_needed,
                'cash_available': cash_available,
                'buffer': buffer,
                'buffer_pct': buffer_pct,
                'status': 'OK' if buffer >= 0 else 'SHORTFALL'
            }

        self.results = results
        return results

    def get_summary_metrics(self):
        if self.results is None:
            self.calculate_pacing_schedule()

        r = self.results
        fp = self.config['fund_parameters']

        return {
            'target_fund_size': fp['target_fund_size'],
            'current_nav': fp['current_nav'],
            'remaining_to_deploy': r['remaining_to_deploy'],
            'total_5yr_commitments': sum(r['commitments']['total']),
            'total_5yr_draws': sum(r['draws']['total']),
            'total_5yr_distributions': sum(r['distributions']),
            'ending_nav': r['nav_projection'][-1],
            'avg_annual_deals': sum(sum(deals) for deals in r['deal_flow_requirements'].values()) / 5,
            'self_sustaining_year': next((i + 1 for i in range(5)
                                          if r['distributions'][i] > r['draws']['total'][i]),
                                         None),
        }


# ==================== DASH APP ====================

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)

app.title = "Evergreen Fund Manager"
server = app.server  # For deployment

deals_data = []
config_data = EvergreenCommitmentPacingModel.default_config()

COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'accent': '#F18F01',
    'success': '#06A77D',
    'danger': '#D62828',
    'dark': '#1F4E78',
}


# ==================== HELPER FUNCTIONS ====================

def calculate_portfolio_metrics(deals):
    if not deals:
        return {'total_nav': 0, 'num_deals': 0, 'weighted_irr': 0, 'by_strategy': {}}

    total_nav = sum(d['size'] for d in deals)
    num_deals = len(deals)
    weighted_irr = sum(d['size'] * d['target_irr'] for d in deals) / total_nav if total_nav > 0 else 0

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

    return {'total_nav': total_nav, 'num_deals': num_deals, 'weighted_irr': weighted_irr, 'by_strategy': by_strategy}


def create_commitment_waterfall(model_results):
    strategies = list(config_data['strategies'].keys())
    years = model_results['years']
    colors = [COLORS['primary'], COLORS['secondary'], COLORS['accent']]

    fig = go.Figure()
    for i, strategy in enumerate(strategies):
        fig.add_trace(go.Bar(
            name=strategy, x=years, y=model_results['commitments'][strategy],
            marker_color=colors[i],
            hovertemplate='<b>%{x}</b><br>%{fullData.name}: $%{y:.1f}M<extra></extra>'
        ))

    fig.update_layout(
        barmode='stack', title='Annual Commitment Pacing by Strategy',
        xaxis_title='Year', yaxis_title='Commitments ($mm)',
        font=dict(size=12), hovermode='x unified',
        plot_bgcolor='white', height=400
    )
    return fig


def create_nav_trajectory(model_results, config):
    nav_path = [config['fund_parameters']['current_nav']] + model_results['nav_projection']
    years_extended = ['Start'] + model_results['years']
    target = config['fund_parameters']['target_fund_size']

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years_extended, y=nav_path, fill='tozeroy', mode='lines+markers',
        name='Projected NAV', line=dict(color=COLORS['success'], width=3),
        marker=dict(size=10, color='white', line=dict(color=COLORS['success'], width=3))
    ))

    fig.add_trace(go.Scatter(
        x=years_extended, y=[target] * len(years_extended), mode='lines',
        name=f'Target (${target}M)', line=dict(color=COLORS['danger'], width=2, dash='dash')
    ))

    fig.update_layout(
        title='NAV Growth Trajectory', xaxis_title='Timeline', yaxis_title='NAV ($mm)',
        font=dict(size=12), plot_bgcolor='white', height=400
    )
    return fig


def create_liquidity_buffer(model_results):
    years = model_results['years']
    liq = model_results['liquidity_analysis']
    buffer_pcts = [liq[year]['buffer_pct'] * 100 for year in years]
    colors_buffer = [COLORS['success'] if b >= 0 else COLORS['danger'] for b in buffer_pcts]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=buffer_pcts, marker_color=colors_buffer,
        text=[f"{b:.1f}%" for b in buffer_pcts], textposition='outside'
    ))

    fig.add_hline(y=0, line_color='black', line_width=2)
    fig.add_hline(y=10, line_color=COLORS['success'], line_width=2, line_dash='dash')

    fig.update_layout(
        title='Liquidity Buffer Analysis', xaxis_title='Year', yaxis_title='Buffer (%)',
        font=dict(size=12), plot_bgcolor='white', height=400
    )
    return fig


def create_strategy_pie(metrics):
    if not metrics['by_strategy']:
        return go.Figure()

    strategies = list(metrics['by_strategy'].keys())
    navs = [metrics['by_strategy'][s]['nav'] for s in strategies]
    colors = [COLORS['primary'], COLORS['secondary'], COLORS['accent']][:len(strategies)]

    fig = go.Figure(data=[go.Pie(
        labels=strategies, values=navs, hole=0.4, marker_colors=colors,
        textinfo='label+percent', textfont_size=12
    )])

    fig.update_layout(title='Portfolio by Strategy', font=dict(size=12), height=350, showlegend=False)
    return fig


# ==================== LAYOUT ====================

navbar = dbc.Navbar(
    dbc.Container([
        html.I(className="fas fa-briefcase me-2", style={'fontSize': '24px'}),
        dbc.NavbarBrand("Evergreen Fund Manager", style={'fontSize': '20px', 'fontWeight': 'bold'}),
        html.Div(id='live-clock', style={'fontSize': '14px', 'color': '#6c757d'})
    ], fluid=True),
    color=COLORS['dark'], dark=True, className="mb-4"
)

sidebar = dbc.Card([
    dbc.CardBody([
        html.H5("Navigation", className="mb-4"),
        dbc.Nav([
            dbc.NavLink([html.I(className="fas fa-home me-2"), "Overview"], href="/", active="exact"),
            dbc.NavLink([html.I(className="fas fa-folder-plus me-2"), "Manage Deals"], href="/deals", active="exact"),
            dbc.NavLink([html.I(className="fas fa-chart-line me-2"), "Pacing Model"], href="/pacing", active="exact"),
        ], vertical=True, pills=True),
        html.Hr(),
        html.H6("Quick Stats", className="mt-4 mb-3"),
        html.Div(id='sidebar-stats'),
        html.Hr(),
        dbc.Button([html.I(className="fas fa-download me-2"), "Export CSV"],
                   id="btn-export", color="secondary", size="sm", className="w-100"),
        dcc.Download(id="download-csv"),
    ])
])

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='deals-store', data=[]),
    dcc.Store(id='config-store', data=config_data),
    dcc.Interval(id='clock-interval', interval=1000, n_intervals=0),
    navbar,
    dbc.Row([
        dbc.Col(sidebar, width=2),
        dbc.Col(html.Div(id="page-content"), width=10)
    ])
], fluid=True)


# ==================== PAGE LAYOUTS ====================

def overview_layout():
    return html.Div([
        html.H2("Portfolio Overview", className="mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Total NAV"), html.H3(id="metric-total-nav"),
                html.Small(id="metric-num-deals")
            ])], color="primary", outline=True), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Weighted IRR"), html.H3(id="metric-weighted-irr")
            ])], color="success", outline=True), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Required Future IRR"), html.H3(id="metric-required-irr")
            ])], color="warning", outline=True), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("Remaining"), html.H3(id="metric-remaining")
            ])], color="info", outline=True), width=3),
        ], className="mb-4"),
        dbc.Row([
            dbc.Col([dbc.Card([dbc.CardBody([dcc.Graph(id='overview-pie-chart')])])], width=6),
            dbc.Col([dbc.Card([dbc.CardBody([html.H5("Strategy Breakdown"), html.Div(id='strategy-breakdown')])])],
                    width=6)
        ], className="mb-4"),
        dbc.Card([dbc.CardBody([html.H5("Recent Deals"), html.Div(id='recent-deals-table')])])
    ])


def deals_layout():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("Deal Management"), width=8),
            dbc.Col([dbc.Button([html.I(className="fas fa-plus me-2"), "Add Deal"],
                                id="btn-open-add-deal", color="primary", className="float-end")], width=4)
        ], className="mb-4"),

        dbc.Modal([
            dbc.ModalHeader("Add New Deal"),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([dbc.Label("Deal Name *"), dbc.Input(id="input-deal-name", type="text")], width=6),
                    dbc.Col([dbc.Label("Strategy *"), dbc.Select(id="input-strategy", options=[
                        {"label": "GP-Led Secondaries", "value": "GP-Led Secondaries"},
                        {"label": "LP-Led Secondaries", "value": "LP-Led Secondaries"},
                        {"label": "Co-Investments", "value": "Co-Investments"},
                    ])], width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Size ($mm) *"), dbc.Input(id="input-size", type="number", min=0.1, step=0.5)],
                            width=6),
                    dbc.Col(
                        [dbc.Label("IRR (%) *"), dbc.Input(id="input-irr", type="number", min=0, max=100, step=0.5)],
                        width=6)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Vintage *"), dbc.Select(id="input-vintage", options=[
                        {"label": str(y), "value": y} for y in range(2024, 2018, -1)])], width=6),
                    dbc.Col([dbc.Label("Sector *"), dbc.Select(id="input-sector", options=[
                        {"label": "Technology", "value": "Technology"},
                        {"label": "Healthcare", "value": "Healthcare"},
                        {"label": "Consumer", "value": "Consumer"},
                    ])], width=6)
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-cancel-deal", color="secondary"),
                dbc.Button("Add Deal", id="btn-submit-deal", color="primary")
            ])
        ], id="modal-add-deal", size="lg", is_open=False),

        html.Div(id='deals-table-container')
    ])


def pacing_layout():
    return html.Div([
        html.H2("Commitment Pacing Model", className="mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Target"), html.H4(id="pacing-target-size")])]), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Current"), html.H4(id="pacing-current-nav")])]), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Remaining"), html.H4(id="pacing-remaining")])]), width=3),
            dbc.Col(dbc.Card([dbc.CardBody([html.H6("Self-Sustaining"), html.H4(id="pacing-self-sustain")])]), width=3)
        ], className="mb-4"),
        dbc.Tabs([
            dbc.Tab(label="Commitments", tab_id="tab-commitments"),
            dbc.Tab(label="NAV Growth", tab_id="tab-nav"),
            dbc.Tab(label="Liquidity", tab_id="tab-liquidity"),
        ], id="pacing-tabs", active_tab="tab-commitments"),
        html.Div(id='pacing-tab-content', className="mt-4")
    ])


# ==================== CALLBACKS ====================

@app.callback(Output('live-clock', 'children'), Input('clock-interval', 'n_intervals'))
def update_clock(n):
    return datetime.now().strftime('%H:%M:%S')


@app.callback(Output('sidebar-stats', 'children'), Input('deals-store', 'data'))
def update_sidebar(deals):
    m = calculate_portfolio_metrics(deals)
    return [
        html.Div([html.Small("NAV"), html.H6(f"${m['total_nav']:.0f}M")], className="mb-2"),
        html.Div([html.Small("Deals"), html.H6(str(m['num_deals']))], className="mb-2"),
        html.Div([html.Small("IRR"), html.H6(f"{m['weighted_irr']:.1%}")])
    ]


@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/deals':
        return deals_layout()
    elif pathname == '/pacing':
        return pacing_layout()
    else:
        return overview_layout()


@app.callback(
    Output('modal-add-deal', 'is_open'),
    [Input('btn-open-add-deal', 'n_clicks'), Input('btn-cancel-deal', 'n_clicks'),
     Input('btn-submit-deal', 'n_clicks')],
    State('modal-add-deal', 'is_open'), prevent_initial_call=True
)
def toggle_modal(o, c, s, is_open):
    return not is_open


@app.callback(
    Output('deals-store', 'data'),
    Input('btn-submit-deal', 'n_clicks'),
    [State('input-deal-name', 'value'), State('input-strategy', 'value'), State('input-size', 'value'),
     State('input-irr', 'value'), State('input-vintage', 'value'), State('input-sector', 'value'),
     State('deals-store', 'data')],
    prevent_initial_call=True
)
def add_deal(n, name, strat, size, irr, vint, sec, deals):
    if not all([name, strat, size, irr]):
        return deals
    return deals + [{
        'name': name, 'strategy': strat, 'size': float(size), 'target_irr': float(irr) / 100,
        'vintage': int(vint) if vint else 2024, 'sector': sec or 'Other',
        'date_added': datetime.now().isoformat(), 'hold_period': 5.0
    }]


@app.callback(
    [Output('metric-total-nav', 'children'), Output('metric-num-deals', 'children'),
     Output('metric-weighted-irr', 'children'), Output('metric-required-irr', 'children'),
     Output('metric-remaining', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data')]
)
def update_metrics(deals, config):
    m = calculate_portfolio_metrics(deals)
    target = config['fund_parameters']['target_fund_size']
    return (
        f"${m['total_nav']:.1f}M", f"{m['num_deals']} deals",
        f"{m['weighted_irr']:.1%}", "25.0%", f"${target - m['total_nav']:.0f}M"
    )


@app.callback(Output('overview-pie-chart', 'figure'), Input('deals-store', 'data'))
def update_pie(deals):
    return create_strategy_pie(calculate_portfolio_metrics(deals))


@app.callback(Output('strategy-breakdown', 'children'), Input('deals-store', 'data'))
def update_breakdown(deals):
    m = calculate_portfolio_metrics(deals)
    if not m['by_strategy']:
        return html.P("No deals yet")

    cards = []
    for s, d in m['by_strategy'].items():
        cards.append(dbc.Card([dbc.CardBody([
            html.H6(s), html.P([html.Strong(f"${d['nav']:.1f}M"), html.Br(),
                                f"{d['count']} deals • {d['weighted_irr']:.1%}"])
        ])], className="mb-2"))
    return cards


@app.callback(Output('recent-deals-table', 'children'), Input('deals-store', 'data'))
def update_recent(deals):
    if not deals:
        return html.P("No deals yet")
    recent = sorted(deals, key=lambda x: x.get('date_added', ''), reverse=True)[:5]
    return dash_table.DataTable(
        data=[{'Name': d['name'], 'Strategy': d['strategy'], 'Size': f"${d['size']:.0f}M",
               'IRR': f"{d['target_irr']:.1%}", 'Vintage': d['vintage']} for d in recent],
        columns=[{"name": c, "id": c} for c in ['Name', 'Strategy', 'Size', 'IRR', 'Vintage']],
        style_cell={'padding': '10px'},
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white', 'fontWeight': 'bold'}
    )


@app.callback(Output('deals-table-container', 'children'), Input('deals-store', 'data'))
def update_table(deals):
    if not deals:
        return html.P("No deals yet")
    data = [{'Name': d['name'], 'Strategy': d['strategy'], 'Size': f"{d['size']:.1f}",
             'IRR': f"{d['target_irr']:.1%}", 'Vintage': d['vintage']}
            for d in sorted(deals, key=lambda x: x.get('date_added', ''), reverse=True)]
    return dash_table.DataTable(
        data=data,
        columns=[{"name": c, "id": c} for c in data[0].keys()] if data else [],
        page_size=20,
        style_cell={'padding': '10px'},
        style_header={'backgroundColor': COLORS['dark'], 'color': 'white'}
    )


@app.callback(
    [Output('pacing-target-size', 'children'), Output('pacing-current-nav', 'children'),
     Output('pacing-remaining', 'children'), Output('pacing-self-sustain', 'children'),
     Output('pacing-tab-content', 'children')],
    [Input('deals-store', 'data'), Input('config-store', 'data'), Input('pacing-tabs', 'active_tab')]
)
def update_pacing(deals, config, tab):
    m = calculate_portfolio_metrics(deals)
    config['fund_parameters']['current_nav'] = m['total_nav']

    model = EvergreenCommitmentPacingModel(config)
    results = model.calculate_pacing_schedule()
    summary = model.get_summary_metrics()

    if tab == 'tab-commitments':
        content = dcc.Graph(figure=create_commitment_waterfall(results))
    elif tab == 'tab-nav':
        content = dcc.Graph(figure=create_nav_trajectory(results, config))
    else:
        content = dcc.Graph(figure=create_liquidity_buffer(results))

    return (
        f"${summary['target_fund_size']}M",
        f"${summary['current_nav']:.0f}M",
        f"${summary['remaining_to_deploy']:.0f}M",
        f"Year {summary.get('self_sustaining_year', 'N/A')}" if summary.get('self_sustaining_year') else "Not Yet",
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
    print("EVERGREEN FUND DASHBOARD")
    print("=" * 70)
    print("\n✅ Starting on http://localhost:8050")
    print("✅ Press CTRL+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=8050)
