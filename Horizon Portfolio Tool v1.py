"""
EVERGREEN FUND COMMITMENT PACING MODEL
Interactive Python-based model for secondaries & co-investment funds
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import json


class EvergreenCommitmentPacingModel:
    """
    Sophisticated commitment pacing model for evergreen secondaries and co-investment funds.

    Features:
    - Strategy-specific draw modeling
    - Multi-year capital call projections
    - Liquidity buffer analysis
    - Deal flow requirements
    - Interactive visualizations
    """

    def __init__(self, config=None):
        """Initialize the model with configuration"""
        if config is None:
            config = self.default_config()

        self.config = config
        self.results = None

    @staticmethod
    def default_config():
        """Default configuration for the model"""
        return {
            'fund_parameters': {
                'target_fund_size': 500,  # $mm
                'current_nav': 50,  # $mm
                'deployment_timeline_years': 5,
                'liquidity_reserve_pct': 0.10,
                'target_twr': 0.13,  # 13% annual TWR
                'distribution_rate': 0.20,  # 20% of NAV distributed annually
            },
            'strategies': {
                'GP-Led Secondaries': {
                    'allocation': 0.40,
                    'avg_deal_size': 30,  # $mm
                    'draw_period_years': 0.5,
                    'pct_drawn_at_close': 0.90,
                },
                'LP-Led Secondaries': {
                    'allocation': 0.30,
                    'avg_deal_size': 40,  # $mm
                    'draw_period_years': 1.0,
                    'pct_drawn_at_close': 0.80,
                },
                'Co-Investments': {
                    'allocation': 0.30,
                    'avg_deal_size': 20,  # $mm
                    'draw_period_years': 2.0,
                    'pct_drawn_at_close': 0.50,
                },
            },
            'pacing': {
                # Front-loaded pacing for evergreen funds
                'annual_commitment_pct': [0.25, 0.25, 0.20, 0.15, 0.15],
            }
        }

    def calculate_pacing_schedule(self):
        """Calculate complete 5-year pacing schedule"""
        fp = self.config['fund_parameters']
        strategies = self.config['strategies']
        pacing_pct = self.config['pacing']['annual_commitment_pct']

        # Calculate remaining to deploy
        remaining = fp['target_fund_size'] - fp['current_nav']

        # Initialize results
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

        # Calculate annual commitments
        total_commitments = [remaining * pct for pct in pacing_pct]
        results['commitments']['total'] = total_commitments

        # Calculate strategy-specific commitments and draws
        for strategy_name, strategy_config in strategies.items():
            alloc = strategy_config['allocation']
            avg_size = strategy_config['avg_deal_size']
            draw_period = strategy_config['draw_period_years']
            pct_close = strategy_config['pct_drawn_at_close']

            # Commitments by strategy
            strategy_commits = [commit * alloc for commit in total_commitments]
            results['commitments'][strategy_name] = strategy_commits

            # Draws by strategy
            if draw_period <= 1:
                # Fast draw strategies - mostly at close
                strategy_draws = [[commit * pct_close if j == i else 0
                                   for j in range(5)] for i, commit in enumerate(strategy_commits)]
            else:
                # Slow draw strategies - spread over years
                strategy_draws = []
                for i, commit in enumerate(strategy_commits):
                    year_draws = [0] * 5
                    year_draws[i] = commit * pct_close  # Year 1 draw
                    if i < 4:
                        year_draws[i + 1] = commit * (1 - pct_close) / 2  # Year 2 draw
                    if i < 3 and draw_period > 1.5:
                        year_draws[i + 2] = commit * (1 - pct_close) / 2  # Year 3 draw
                    strategy_draws.append(year_draws)

            # Sum draws across all commitment vintages
            total_strategy_draws = [sum(draws[j] for draws in strategy_draws)
                                    for j in range(5)]
            results['draws'][strategy_name] = total_strategy_draws

            # Deal flow requirements
            deals_per_year = [commit / avg_size for commit in strategy_commits]
            results['deal_flow_requirements'][strategy_name] = deals_per_year

        # Calculate total draws
        results['draws']['total'] = [
            sum(results['draws'][s][i] for s in strategies.keys())
            for i in range(5)
        ]

        # Calculate distributions and NAV projection
        nav = fp['current_nav']
        for i in range(5):
            # Distribution = % of beginning NAV
            dist = nav * fp['distribution_rate']
            results['distributions'].append(dist)

            # New NAV = Old NAV + Draws - Distributions + Growth
            draws = results['draws']['total'][i]
            growth = (nav + (nav + draws - dist)) / 2 * fp['target_twr']  # Mid-year growth
            nav = nav + draws - dist + growth
            results['nav_projection'].append(nav)

        # Liquidity analysis
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
        """Get key summary metrics"""
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

    def plot_commitment_waterfall(self, ax=None):
        """Plot commitment waterfall by strategy"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        if self.results is None:
            self.calculate_pacing_schedule()

        strategies = list(self.config['strategies'].keys())
        years = self.results['years']
        x = np.arange(len(years))
        width = 0.7

        # Stack bars
        bottom = np.zeros(len(years))
        colors = ['#2E86AB', '#A23B72', '#F18F01']

        for i, strategy in enumerate(strategies):
            values = self.results['commitments'][strategy]
            ax.bar(x, values, width, label=strategy, bottom=bottom,
                   color=colors[i], alpha=0.9)
            bottom += values

        ax.set_ylabel('Commitments ($mm)', fontweight='bold')
        ax.set_title('Annual Commitment Pacing by Strategy', fontweight='bold', fontsize=13)
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)

        # Add total labels
        for i, total in enumerate(self.results['commitments']['total']):
            ax.text(i, total + 2, f'${total:.0f}M', ha='center', fontweight='bold')

        return ax

    def plot_nav_trajectory(self, ax=None):
        """Plot NAV growth trajectory"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        if self.results is None:
            self.calculate_pacing_schedule()

        fp = self.config['fund_parameters']
        nav_path = [fp['current_nav']] + self.results['nav_projection']
        years_extended = ['Start'] + self.results['years']
        x = np.arange(len(years_extended))

        # Plot NAV trajectory
        ax.fill_between(x, 0, nav_path, alpha=0.3, color='#06A77D')
        ax.plot(x, nav_path, marker='o', markersize=10, linewidth=3,
                color='#06A77D', markerfacecolor='white',
                markeredgewidth=2.5, label='Projected NAV')

        # Add target line
        ax.axhline(y=fp['target_fund_size'], color='#C73E1D',
                   linestyle='--', linewidth=2, label=f"Target (${fp['target_fund_size']}M)")

        # Shade gap
        ax.fill_between(x, nav_path, fp['target_fund_size'],
                        where=(np.array(nav_path) < fp['target_fund_size']),
                        alpha=0.15, color='red', label='Gap to Target')

        ax.set_xlabel('Timeline', fontweight='bold')
        ax.set_ylabel('NAV ($mm)', fontweight='bold')
        ax.set_title('NAV Growth Trajectory - Path to Target', fontweight='bold', fontsize=13)
        ax.set_xticks(x)
        ax.set_xticklabels(years_extended)
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)

        return ax

    def plot_liquidity_buffer(self, ax=None):
        """Plot liquidity buffer analysis"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))

        if self.results is None:
            self.calculate_pacing_schedule()

        years = self.results['years']
        liq = self.results['liquidity_analysis']

        buffer_pcts = [liq[year]['buffer_pct'] * 100 for year in years]
        colors_buffer = ['#06A77D' if b >= 0 else '#D62828' for b in buffer_pcts]

        x = np.arange(len(years))
        bars = ax.bar(x, buffer_pcts, color=colors_buffer, alpha=0.85,
                      edgecolor='black', linewidth=1.5)

        ax.axhline(y=0, color='black', linestyle='-', linewidth=2)
        ax.axhline(y=10, color='#06A77D', linestyle='--', linewidth=2, alpha=0.5, label='10% Target')

        ax.set_ylabel('Liquidity Buffer (%)', fontweight='bold')
        ax.set_title('Liquidity Buffer Analysis by Year', fontweight='bold', fontsize=13)
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        # Add value labels
        for i, (pct, year) in enumerate(zip(buffer_pcts, years)):
            buffer_amt = liq[year]['buffer']
            ax.text(i, pct + (2 if pct >= 0 else -5),
                    f'{pct:.1f}%\n(${buffer_amt:.1f}M)',
                    ha='center', va='bottom' if pct >= 0 else 'top',
                    fontweight='bold', fontsize=8)

        return ax

    def create_dashboard(self, save_path=None):
        """Create complete interactive dashboard"""
        if self.results is None:
            self.calculate_pacing_schedule()

        fig = plt.figure(figsize=(18, 12))
        fig.suptitle('EVERGREEN FUND COMMITMENT PACING MODEL\nInteractive Python Dashboard',
                     fontsize=18, fontweight='bold')

        # Create subplots
        gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.25,
                              left=0.08, right=0.95, top=0.92, bottom=0.08)

        # 1. Commitment waterfall
        ax1 = fig.add_subplot(gs[0, 0])
        self.plot_commitment_waterfall(ax1)

        # 2. NAV trajectory
        ax2 = fig.add_subplot(gs[0, 1])
        self.plot_nav_trajectory(ax2)

        # 3. Liquidity buffer
        ax3 = fig.add_subplot(gs[1, 0])
        self.plot_liquidity_buffer(ax3)

        # 4. Deal flow requirements
        ax4 = fig.add_subplot(gs[1, 1])
        strategies = list(self.config['strategies'].keys())
        years = self.results['years']
        x = np.arange(len(years))
        width = 0.6

        bottom = np.zeros(len(years))
        colors = ['#2E86AB', '#A23B72', '#F18F01']

        for i, strategy in enumerate(strategies):
            values = self.results['deal_flow_requirements'][strategy]
            ax4.bar(x, values, width, label=strategy, bottom=bottom,
                    color=colors[i], alpha=0.9)
            bottom += values

        ax4.set_ylabel('Number of Deals', fontweight='bold')
        ax4.set_title('Annual Deal Flow Requirements', fontweight='bold', fontsize=13)
        ax4.set_xticks(x)
        ax4.set_xticklabels(years)
        ax4.legend()
        ax4.grid(axis='y', alpha=0.3)

        # Add total labels
        for i in range(len(years)):
            total_deals = sum(self.results['deal_flow_requirements'][s][i]
                              for s in strategies)
            ax4.text(i, total_deals + 0.2, f'{total_deals:.1f}',
                     ha='center', fontweight='bold')

        # 5. Cash flow analysis
        ax5 = fig.add_subplot(gs[2, 0])
        draws = self.results['draws']['total']
        dists = self.results['distributions']
        net_cf = [d - c for d, c in zip(dists, draws)]

        colors_cf = ['#06A77D' if x >= 0 else '#D62828' for x in net_cf]
        ax5.bar(x, net_cf, width=0.7, color=colors_cf, alpha=0.85)
        ax5.axhline(y=0, color='black', linewidth=2)
        ax5.set_ylabel('Net Cash Flow ($mm)', fontweight='bold')
        ax5.set_title('Net Cash Flow (Distributions - Draws)', fontweight='bold', fontsize=13)
        ax5.set_xticks(x)
        ax5.set_xticklabels(years)
        ax5.grid(axis='y', alpha=0.3)

        # 6. Key metrics table
        ax6 = fig.add_subplot(gs[2, 1])
        ax6.axis('off')

        metrics = self.get_summary_metrics()
        table_data = [
            ['Target Fund Size', f"${metrics['target_fund_size']}M"],
            ['Current NAV', f"${metrics['current_nav']}M"],
            ['Remaining to Deploy', f"${metrics['remaining_to_deploy']:.0f}M"],
            ['Total 5Y Commitments', f"${metrics['total_5yr_commitments']:.0f}M"],
            ['Total 5Y Draws', f"${metrics['total_5yr_draws']:.0f}M"],
            ['Ending NAV (Year 5)', f"${metrics['ending_nav']:.0f}M"],
            ['Avg Annual Deals', f"{metrics['avg_annual_deals']:.1f}"],
            ['Self-Sustaining',
             f"Year {metrics['self_sustaining_year']}" if metrics['self_sustaining_year'] else 'Not Yet'],
        ]

        table = ax6.table(cellText=table_data, cellLoc='left',
                          colWidths=[0.6, 0.4], loc='center',
                          bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)

        # Style table
        for i in range(len(table_data)):
            table[(i, 0)].set_facecolor('#E8E8E8')
            table[(i, 0)].set_text_props(weight='bold')
            table[(i, 1)].set_facecolor('#F8F8F8')
            table[(i, 1)].set_text_props(weight='bold', color='#2E86AB')

        ax6.set_title('Key Metrics Summary', fontweight='bold', fontsize=13, pad=20)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
            print(f"Dashboard saved to: {save_path}")

        return fig

    def export_to_excel(self, filename='commitment_pacing_output.xlsx'):
        """Export results to Excel"""
        if self.results is None:
            self.calculate_pacing_schedule()

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Sheet 1: Summary
            summary_df = pd.DataFrame([self.get_summary_metrics()]).T
            summary_df.columns = ['Value']
            summary_df.to_excel(writer, sheet_name='Summary')

            # Sheet 2: Pacing Schedule
            pacing_data = {
                'Year': self.results['years'],
                'Total Commitments': self.results['commitments']['total'],
                'Total Draws': self.results['draws']['total'],
                'Distributions': self.results['distributions'],
                'Ending NAV': self.results['nav_projection'],
            }
            pacing_df = pd.DataFrame(pacing_data)
            pacing_df.to_excel(writer, sheet_name='Pacing Schedule', index=False)

            # Sheet 3: Strategy Details
            for strategy in self.config['strategies'].keys():
                strategy_data = {
                    'Year': self.results['years'],
                    'Commitments': self.results['commitments'][strategy],
                    'Draws': self.results['draws'][strategy],
                    'Deals Required': self.results['deal_flow_requirements'][strategy],
                }
                strategy_df = pd.DataFrame(strategy_data)
                sheet_name = strategy.replace(' ', '_')[:31]  # Excel sheet name limit
                strategy_df.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"Results exported to: {filename}")

    def export_config(self, filename='model_config.json'):
        """Export configuration as JSON"""
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=2)
        print(f"Configuration saved to: {filename}")

    @classmethod
    def load_config(cls, filename='model_config.json'):
        """Load configuration from JSON"""
        with open(filename, 'r') as f:
            config = json.load(f)
        return cls(config)


# Example usage
if __name__ == "__main__":
    # Create model with default configuration
    model = EvergreenCommitmentPacingModel()

    # Calculate pacing schedule
    results = model.calculate_pacing_schedule()

    # Get summary metrics
    metrics = model.get_summary_metrics()
    print("\n=== SUMMARY METRICS ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")

    # Create dashboard
    model.create_dashboard(save_path='commitment_pacing_dashboard.png')

    # Export to Excel
    model.export_to_excel('commitment_pacing_results.xlsx')

    # Save configuration
    model.export_config('model_config.json')

    print("\n✓ Model complete! All outputs generated.")
