"""
EVERGREEN FUND INTERACTIVE DASHBOARD
Built with Streamlit for real-time portfolio management

Run with: streamlit run interactive_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, date
import json
from evergreen_pacing_model import EvergreenCommitmentPacingModel

# Page configuration
st.set_page_config(
    page_title="Evergreen Fund Manager",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1F4E78;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #2E86AB;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .stButton>button {
        background-color: #2E86AB;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.5rem 2rem;
    }
    .deal-card {
        border: 2px solid #E0E0E0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: #F8F9FA;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'deals' not in st.session_state:
    st.session_state.deals = []

if 'config' not in st.session_state:
    st.session_state.config = EvergreenCommitmentPacingModel.default_config()

if 'show_add_deal' not in st.session_state:
    st.session_state.show_add_deal = False


# Helper functions
def add_deal_to_portfolio(deal_data):
    """Add a new deal to the portfolio"""
    st.session_state.deals.append(deal_data)
    st.success(f"✅ Added {deal_data['name']} to portfolio!")


def remove_deal(index):
    """Remove a deal from portfolio"""
    removed = st.session_state.deals.pop(index)
    st.success(f"🗑️ Removed {removed['name']} from portfolio")


def calculate_portfolio_metrics():
    """Calculate current portfolio metrics"""
    if not st.session_state.deals:
        return {
            'total_nav': 0,
            'num_deals': 0,
            'weighted_irr': 0,
            'by_strategy': {}
        }

    total_nav = sum(d['size'] for d in st.session_state.deals)
    num_deals = len(st.session_state.deals)

    if total_nav > 0:
        weighted_irr = sum(d['size'] * d['target_irr'] for d in st.session_state.deals) / total_nav
    else:
        weighted_irr = 0

    # By strategy
    by_strategy = {}
    for deal in st.session_state.deals:
        strategy = deal['strategy']
        if strategy not in by_strategy:
            by_strategy[strategy] = {'nav': 0, 'count': 0, 'irr_sum': 0}
        by_strategy[strategy]['nav'] += deal['size']
        by_strategy[strategy]['count'] += 1
        by_strategy[strategy]['irr_sum'] += deal['size'] * deal['target_irr']

    # Calculate weighted IRR per strategy
    for strategy in by_strategy:
        if by_strategy[strategy]['nav'] > 0:
            by_strategy[strategy]['weighted_irr'] = by_strategy[strategy]['irr_sum'] / by_strategy[strategy]['nav']

    return {
        'total_nav': total_nav,
        'num_deals': num_deals,
        'weighted_irr': weighted_irr,
        'by_strategy': by_strategy
    }


def export_deals_to_csv():
    """Export deals to CSV"""
    if st.session_state.deals:
        df = pd.DataFrame(st.session_state.deals)
        return df.to_csv(index=False)
    return None


def import_deals_from_csv(uploaded_file):
    """Import deals from CSV"""
    try:
        df = pd.read_csv(uploaded_file)
        required_columns = ['name', 'strategy', 'size', 'target_irr', 'vintage', 'sector']

        if all(col in df.columns for col in required_columns):
            new_deals = df.to_dict('records')
            st.session_state.deals.extend(new_deals)
            return len(new_deals)
        else:
            st.error(f"CSV must contain columns: {required_columns}")
            return 0
    except Exception as e:
        st.error(f"Error importing CSV: {str(e)}")
        return 0


# ========== HEADER ==========
st.markdown('<div class="main-header">💼 EVERGREEN FUND INTERACTIVE DASHBOARD</div>', unsafe_allow_html=True)
st.markdown("### Real-time Portfolio Management & Commitment Pacing")

# ========== SIDEBAR ==========
with st.sidebar:
    st.image("https://via.placeholder.com/200x80/2E86AB/FFFFFF?text=Your+Fund+Logo", use_container_width=True)

    st.markdown("## 📊 Dashboard Controls")

    # Navigation
    page = st.radio(
        "Navigate to:",
        ["🏠 Overview", "➕ Manage Deals", "📈 Pacing Model", "⚙️ Settings"],
        index=0
    )

    st.markdown("---")

    # Quick Stats
    metrics = calculate_portfolio_metrics()
    st.metric("Total NAV", f"${metrics['total_nav']:.0f}M")
    st.metric("Active Deals", metrics['num_deals'])
    st.metric("Avg IRR", f"{metrics['weighted_irr']:.1%}")

    st.markdown("---")

    # Import/Export
    st.markdown("### 💾 Data Management")

    if st.button("📥 Export Deals (CSV)", use_container_width=True):
        csv_data = export_deals_to_csv()
        if csv_data:
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=f"portfolio_{date.today()}.csv",
                mime="text/csv"
            )

    uploaded_file = st.file_uploader("📤 Import Deals (CSV)", type=['csv'])
    if uploaded_file:
        num_imported = import_deals_from_csv(uploaded_file)
        if num_imported > 0:
            st.success(f"Imported {num_imported} deals!")

# ========== MAIN CONTENT ==========

if page == "🏠 Overview":
    # Key Metrics Row
    col1, col2, col3, col4 = st.columns(4)

    metrics = calculate_portfolio_metrics()

    with col1:
        st.metric(
            "📊 Total Portfolio NAV",
            f"${metrics['total_nav']:.1f}M",
            delta=f"{metrics['num_deals']} deals"
        )

    with col2:
        st.metric(
            "🎯 Weighted Avg IRR",
            f"{metrics['weighted_irr']:.1%}",
            delta="Portfolio Level"
        )

    target_irr = 0.25  # From Quick Calculator
    with col3:
        gap = metrics['weighted_irr'] - target_irr
        st.metric(
            "📈 Required Future IRR",
            f"{target_irr:.1%}",
            delta=f"{gap:.1%} vs current" if metrics['total_nav'] > 0 else None,
            delta_color="normal" if gap >= 0 else "inverse"
        )

    with col4:
        target_fund_size = st.session_state.config['fund_parameters']['target_fund_size']
        remaining = target_fund_size - metrics['total_nav']
        st.metric(
            "💰 Remaining to Deploy",
            f"${remaining:.0f}M",
            delta=f"{remaining / target_fund_size:.0%} of target"
        )

    st.markdown("---")

    # Portfolio Composition
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📊 Portfolio Composition by Strategy")

        if metrics['by_strategy']:
            # Create pie chart
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

            # By NAV
            strategies = list(metrics['by_strategy'].keys())
            navs = [metrics['by_strategy'][s]['nav'] for s in strategies]
            colors = ['#2E86AB', '#A23B72', '#F18F01', '#06A77D', '#C73E1D'][:len(strategies)]

            ax1.pie(navs, labels=strategies, autopct='%1.1f%%', colors=colors, startangle=90)
            ax1.set_title('By NAV ($mm)', fontweight='bold')

            # By count
            counts = [metrics['by_strategy'][s]['count'] for s in strategies]
            ax2.pie(counts, labels=strategies, autopct='%1.0f', colors=colors, startangle=90)
            ax2.set_title('By Deal Count', fontweight='bold')

            st.pyplot(fig)
            plt.close()
        else:
            st.info("👆 Add deals to see portfolio composition")

    with col2:
        st.markdown("### 📋 Strategy Breakdown")

        if metrics['by_strategy']:
            for strategy, data in metrics['by_strategy'].items():
                with st.expander(f"**{strategy}**", expanded=True):
                    st.write(f"NAV: ${data['nav']:.1f}M")
                    st.write(f"Deals: {data['count']}")
                    st.write(f"Avg IRR: {data['weighted_irr']:.1%}")
                    st.write(f"Allocation: {data['nav'] / metrics['total_nav']:.1%}")
        else:
            st.info("No deals yet")

    # Recent Deals
    st.markdown("---")
    st.markdown("### 🆕 Recent Deals")

    if st.session_state.deals:
        recent_deals = sorted(st.session_state.deals,
                              key=lambda x: x.get('date_added', datetime.now()),
                              reverse=True)[:5]

        for deal in recent_deals:
            cols = st.columns([3, 2, 1.5, 1.5, 1])
            cols[0].write(f"**{deal['name']}**")
            cols[1].write(deal['strategy'])
            cols[2].write(f"${deal['size']:.0f}M")
            cols[3].write(f"{deal['target_irr']:.1%} IRR")
            cols[4].write(deal['vintage'])
    else:
        st.info("No deals in portfolio yet. Add your first deal in '➕ Manage Deals'")

elif page == "➕ Manage Deals":
    st.markdown("## 💼 Deal Management")

    # Add Deal Button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Your Deal Portfolio")
    with col2:
        if st.button("➕ Add New Deal", type="primary", use_container_width=True):
            st.session_state.show_add_deal = True

    # Add Deal Form (Modal-style)
    if st.session_state.show_add_deal:
        with st.form("add_deal_form", clear_on_submit=True):
            st.markdown("#### ➕ Add New Deal")

            col1, col2 = st.columns(2)

            with col1:
                deal_name = st.text_input("Deal Name*", placeholder="e.g., Acme GP-Led 2024")
                strategy = st.selectbox(
                    "Strategy Type*",
                    ["GP-Led Secondaries", "LP-Led Secondaries", "Co-Investments", "Direct Secondary", "Other"]
                )
                deal_size = st.number_input("Deal Size ($mm)*", min_value=0.1, value=25.0, step=0.5)
                target_irr = st.slider("Target Gross IRR*", 0.0, 0.50, 0.20, 0.01, format="%.1f%%")

            with col2:
                vintage = st.selectbox("Vintage Year*", list(range(2024, 2018, -1)))
                sector = st.selectbox(
                    "Sector*",
                    ["Technology", "Healthcare", "Consumer", "Industrials", "Financials",
                     "Energy", "Real Estate", "Other"]
                )
                geography = st.selectbox("Geography", ["North America", "Europe", "Asia", "Global", "Other"])
                hold_period = st.number_input("Expected Hold (years)", min_value=1.0, value=5.0, step=0.5)

            notes = st.text_area("Notes", placeholder="Additional deal information...")

            col1, col2, col3 = st.columns([2, 1, 1])
            with col2:
                submitted = st.form_submit_button("✅ Add Deal", type="primary", use_container_width=True)
            with col3:
                cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)

            if submitted:
                if deal_name and strategy and deal_size > 0:
                    new_deal = {
                        'name': deal_name,
                        'strategy': strategy,
                        'size': deal_size,
                        'target_irr': target_irr,
                        'vintage': vintage,
                        'sector': sector,
                        'geography': geography,
                        'hold_period': hold_period,
                        'notes': notes,
                        'date_added': datetime.now()
                    }
                    add_deal_to_portfolio(new_deal)
                    st.session_state.show_add_deal = False
                    st.rerun()
                else:
                    st.error("Please fill in all required fields (*)")

            if cancelled:
                st.session_state.show_add_deal = False
                st.rerun()

    st.markdown("---")

    # Display Current Deals
    if st.session_state.deals:
        st.markdown(f"### 📁 Current Portfolio ({len(st.session_state.deals)} deals)")

        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_strategy = st.multiselect(
                "Filter by Strategy",
                options=list(set(d['strategy'] for d in st.session_state.deals)),
                default=None
            )
        with col2:
            filter_vintage = st.multiselect(
                "Filter by Vintage",
                options=sorted(list(set(d['vintage'] for d in st.session_state.deals)), reverse=True),
                default=None
            )
        with col3:
            sort_by = st.selectbox("Sort by", ["Date Added", "Size", "IRR", "Name"])

        # Apply filters
        filtered_deals = st.session_state.deals.copy()
        if filter_strategy:
            filtered_deals = [d for d in filtered_deals if d['strategy'] in filter_strategy]
        if filter_vintage:
            filtered_deals = [d for d in filtered_deals if d['vintage'] in filter_vintage]

        # Sort
        if sort_by == "Size":
            filtered_deals = sorted(filtered_deals, key=lambda x: x['size'], reverse=True)
        elif sort_by == "IRR":
            filtered_deals = sorted(filtered_deals, key=lambda x: x['target_irr'], reverse=True)
        elif sort_by == "Name":
            filtered_deals = sorted(filtered_deals, key=lambda x: x['name'])
        else:  # Date Added
            filtered_deals = sorted(filtered_deals, key=lambda x: x.get('date_added', datetime.now()), reverse=True)

        # Display deals
        for idx, deal in enumerate(filtered_deals):
            with st.expander(f"**{deal['name']}** - ${deal['size']:.0f}M @ {deal['target_irr']:.1%} IRR"):
                col1, col2, col3 = st.columns([2, 2, 1])

                with col1:
                    st.write(f"**Strategy:** {deal['strategy']}")
                    st.write(f"**Size:** ${deal['size']:.1f}M")
                    st.write(f"**Target IRR:** {deal['target_irr']:.1%}")
                    st.write(f"**MOIC (implied):** {(1 + deal['target_irr']) ** deal.get('hold_period', 5):.2f}x")

                with col2:
                    st.write(f"**Vintage:** {deal['vintage']}")
                    st.write(f"**Sector:** {deal['sector']}")
                    st.write(f"**Geography:** {deal.get('geography', 'N/A')}")
                    st.write(f"**Hold Period:** {deal.get('hold_period', 5):.1f} years")

                with col3:
                    # Find original index for removal
                    original_idx = st.session_state.deals.index(deal)
                    if st.button(f"🗑️ Remove", key=f"remove_{original_idx}"):
                        remove_deal(original_idx)
                        st.rerun()

                if deal.get('notes'):
                    st.info(f"📝 Notes: {deal['notes']}")
    else:
        st.info("👆 Click 'Add New Deal' to start building your portfolio")

elif page == "📈 Pacing Model":
    st.markdown("## 📈 Commitment Pacing Model")

    # Update config with current portfolio
    metrics = calculate_portfolio_metrics()
    st.session_state.config['fund_parameters']['current_nav'] = metrics['total_nav']

    # Create and run model
    model = EvergreenCommitmentPacingModel(config=st.session_state.config)
    results = model.calculate_pacing_schedule()
    summary = model.get_summary_metrics()

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Target Fund Size", f"${summary['target_fund_size']}M")
    with col2:
        st.metric("Current NAV", f"${summary['current_nav']:.0f}M")
    with col3:
        st.metric("Remaining to Deploy", f"${summary['remaining_to_deploy']:.0f}M")
    with col4:
        self_sustain = summary.get('self_sustaining_year', 'N/A')
        st.metric("Self-Sustaining", f"Year {self_sustain}" if self_sustain != 'N/A' else "Not Yet")

    st.markdown("---")

    # Visualizations
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Commitments", "📈 NAV Growth", "💧 Liquidity", "🎯 Deal Flow"])

    with tab1:
        st.markdown("### Annual Commitment Pacing by Strategy")
        fig, ax = plt.subplots(figsize=(10, 6))
        model.plot_commitment_waterfall(ax)
        st.pyplot(fig)
        plt.close()

        # Data table
        st.markdown("#### Commitment Schedule")
        commit_df = pd.DataFrame({
            'Year': results['years'],
            'Total Commitments': [f"${c:.1f}M" for c in results['commitments']['total']],
            'GP-Led': [f"${c:.1f}M" for c in results['commitments']['GP-Led Secondaries']],
            'LP-Led': [f"${c:.1f}M" for c in results['commitments']['LP-Led Secondaries']],
            'Co-Inv': [f"${c:.1f}M" for c in results['commitments']['Co-Investments']],
        })
        st.dataframe(commit_df, use_container_width=True)

    with tab2:
        st.markdown("### NAV Growth Trajectory")
        fig, ax = plt.subplots(figsize=(10, 6))
        model.plot_nav_trajectory(ax)
        st.pyplot(fig)
        plt.close()

        # NAV projection table
        st.markdown("#### NAV Projection")
        nav_df = pd.DataFrame({
            'Year': results['years'],
            'Ending NAV': [f"${n:.1f}M" for n in results['nav_projection']],
            'Growth': [
                f"${(results['nav_projection'][i] - (summary['current_nav'] if i == 0 else results['nav_projection'][i - 1])):.1f}M"
                for i in range(len(results['nav_projection']))],
        })
        st.dataframe(nav_df, use_container_width=True)

    with tab3:
        st.markdown("### Liquidity Buffer Analysis")
        fig, ax = plt.subplots(figsize=(10, 6))
        model.plot_liquidity_buffer(ax)
        st.pyplot(fig)
        plt.close()

        # Liquidity table
        st.markdown("#### Liquidity Analysis")
        liq_data = []
        for year in results['years']:
            liq = results['liquidity_analysis'][year]
            liq_data.append({
                'Year': year,
                'Cash Needed': f"${liq['cash_needed']:.1f}M",
                'Cash Available': f"${liq['cash_available']:.1f}M",
                'Buffer': f"${liq['buffer']:.1f}M",
                'Buffer %': f"{liq['buffer_pct']:.1%}",
                'Status': '✅' if liq['status'] == 'OK' else '⚠️'
            })
        liq_df = pd.DataFrame(liq_data)
        st.dataframe(liq_df, use_container_width=True)

    with tab4:
        st.markdown("### Deal Flow Requirements by Strategy")

        fig, ax = plt.subplots(figsize=(10, 6))
        strategies = list(st.session_state.config['strategies'].keys())
        years = results['years']
        x = np.arange(len(years))
        width = 0.6

        bottom = np.zeros(len(years))
        colors = ['#2E86AB', '#A23B72', '#F18F01']

        for i, strategy in enumerate(strategies):
            values = results['deal_flow_requirements'][strategy]
            ax.bar(x, values, width, label=strategy, bottom=bottom, color=colors[i], alpha=0.9)
            bottom += values

        ax.set_ylabel('Number of Deals', fontweight='bold')
        ax.set_title('Annual Deal Flow Requirements', fontweight='bold', fontsize=13)
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        st.pyplot(fig)
        plt.close()

        # Deal flow table
        st.markdown("#### Deal Flow Breakdown")
        deal_flow_data = []
        for i, year in enumerate(results['years']):
            row = {'Year': year}
            total = 0
            for strategy in strategies:
                deals = results['deal_flow_requirements'][strategy][i]
                row[strategy] = f"{deals:.1f}"
                total += deals
            row['Total'] = f"{total:.1f}"
            deal_flow_data.append(row)

        deal_flow_df = pd.DataFrame(deal_flow_data)
        st.dataframe(deal_flow_df, use_container_width=True)

else:  # Settings
    st.markdown("## ⚙️ Model Settings")

    with st.form("settings_form"):
        st.markdown("### 💰 Fund Parameters")

        col1, col2 = st.columns(2)

        with col1:
            target_size = st.number_input(
                "Target Fund Size ($mm)",
                min_value=100.0,
                value=float(st.session_state.config['fund_parameters']['target_fund_size']),
                step=50.0
            )

            deployment_years = st.number_input(
                "Deployment Timeline (years)",
                min_value=3,
                max_value=10,
                value=st.session_state.config['fund_parameters']['deployment_timeline_years']
            )

            liquidity_reserve = st.slider(
                "Liquidity Reserve (%)",
                0.0, 0.25,
                st.session_state.config['fund_parameters']['liquidity_reserve_pct'],
                0.01, format="%.1f%%"
            )

        with col2:
            target_twr = st.slider(
                "Target TWR (%)",
                0.08, 0.20,
                st.session_state.config['fund_parameters']['target_twr'],
                0.01, format="%.1f%%"
            )

            distribution_rate = st.slider(
                "Distribution Rate (% of NAV)",
                0.10, 0.30,
                st.session_state.config['fund_parameters']['distribution_rate'],
                0.01, format="%.1f%%"
            )

        st.markdown("---")
        st.markdown("### 🎯 Strategy Allocations")

        col1, col2, col3 = st.columns(3)

        strategies = st.session_state.config['strategies']

        with col1:
            st.markdown("**GP-Led Secondaries**")
            gpled_alloc = st.slider("Allocation", 0.0, 1.0,
                                    strategies['GP-Led Secondaries']['allocation'],
                                    0.05, key="gpled_alloc", format="%.0f%%")
            gpled_size = st.number_input("Avg Deal Size ($mm)", 10.0, 100.0,
                                         float(strategies['GP-Led Secondaries']['avg_deal_size']),
                                         5.0, key="gpled_size")

        with col2:
            st.markdown("**LP-Led Secondaries**")
            lpled_alloc = st.slider("Allocation", 0.0, 1.0,
                                    strategies['LP-Led Secondaries']['allocation'],
                                    0.05, key="lpled_alloc", format="%.0f%%")
            lpled_size = st.number_input("Avg Deal Size ($mm)", 10.0, 100.0,
                                         float(strategies['LP-Led Secondaries']['avg_deal_size']),
                                         5.0, key="lpled_size")

        with col3:
            st.markdown("**Co-Investments**")
            coinv_alloc = st.slider("Allocation", 0.0, 1.0,
                                    strategies['Co-Investments']['allocation'],
                                    0.05, key="coinv_alloc", format="%.0f%%")
            coinv_size = st.number_input("Avg Deal Size ($mm)", 10.0, 100.0,
                                         float(strategies['Co-Investments']['avg_deal_size']),
                                         5.0, key="coinv_size")

        # Check allocation sums to 100%
        total_alloc = gpled_alloc + lpled_alloc + coinv_alloc
        if abs(total_alloc - 1.0) > 0.01:
            st.warning(f"⚠️ Total allocation is {total_alloc:.0%} - should be 100%")

        st.markdown("---")
        st.markdown("### 📅 Pacing Strategy")

        pacing_preset = st.selectbox(
            "Pacing Preset",
            ["Front-Loaded (Recommended)", "Even", "Back-Loaded", "Custom"]
        )

        if pacing_preset == "Front-Loaded (Recommended)":
            pacing = [0.25, 0.25, 0.20, 0.15, 0.15]
        elif pacing_preset == "Even":
            pacing = [0.20, 0.20, 0.20, 0.20, 0.20]
        elif pacing_preset == "Back-Loaded":
            pacing = [0.15, 0.15, 0.20, 0.25, 0.25]
        else:  # Custom
            col1, col2, col3, col4, col5 = st.columns(5)
            y1 = col1.number_input("Year 1 %", 0.0, 1.0, 0.25, 0.05)
            y2 = col2.number_input("Year 2 %", 0.0, 1.0, 0.25, 0.05)
            y3 = col3.number_input("Year 3 %", 0.0, 1.0, 0.20, 0.05)
            y4 = col4.number_input("Year 4 %", 0.0, 1.0, 0.15, 0.05)
            y5 = col5.number_input("Year 5 %", 0.0, 1.0, 0.15, 0.05)
            pacing = [y1, y2, y3, y4, y5]

            if abs(sum(pacing) - 1.0) > 0.01:
                st.warning(f"⚠️ Pacing sums to {sum(pacing):.0%} - should be 100%")

        # Show pacing
        st.bar_chart(pd.DataFrame({'Year': [f'Y{i + 1}' for i in range(5)],
                                   'Pacing %': pacing}).set_index('Year'))

        # Submit button
        col1, col2, col3 = st.columns([2, 1, 1])
        with col2:
            submitted = st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)
        with col3:
            reset = st.form_submit_button("🔄 Reset to Default", use_container_width=True)

        if submitted:
            # Update config
            st.session_state.config['fund_parameters']['target_fund_size'] = target_size
            st.session_state.config['fund_parameters']['deployment_timeline_years'] = deployment_years
            st.session_state.config['fund_parameters']['liquidity_reserve_pct'] = liquidity_reserve
            st.session_state.config['fund_parameters']['target_twr'] = target_twr
            st.session_state.config['fund_parameters']['distribution_rate'] = distribution_rate

            st.session_state.config['strategies']['GP-Led Secondaries']['allocation'] = gpled_alloc
            st.session_state.config['strategies']['GP-Led Secondaries']['avg_deal_size'] = gpled_size
            st.session_state.config['strategies']['LP-Led Secondaries']['allocation'] = lpled_alloc
            st.session_state.config['strategies']['LP-Led Secondaries']['avg_deal_size'] = lpled_size
            st.session_state.config['strategies']['Co-Investments']['allocation'] = coinv_alloc
            st.session_state.config['strategies']['Co-Investments']['avg_deal_size'] = coinv_size

            st.session_state.config['pacing']['annual_commitment_pct'] = pacing

            st.success("✅ Settings saved successfully!")
            st.balloons()

        if reset:
            st.session_state.config = EvergreenCommitmentPacingModel.default_config()
            st.success("🔄 Reset to default settings")
            st.rerun()

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8rem;'>
    💼 Evergreen Fund Interactive Dashboard | Built with Streamlit | 
    Last updated: {} | 
    <a href='#' style='color: #2E86AB;'>Documentation</a> | 
    <a href='#' style='color: #2E86AB;'>Support</a>
    </div>
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M")),
    unsafe_allow_html=True
)
