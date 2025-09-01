#!/usr/bin/env python3
"""
Lead Intelligence Dashboard
Generates interactive HTML dashboards for lead intelligence data
"""

import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as offline


class IntelligenceDashboard:
    """Generates interactive dashboards for lead intelligence"""

    def __init__(self, data_dir: str = "lead_intelligence/data"):
        self.data_dir = Path(data_dir)
        self.reports_dir = self.data_dir.parent / "reporting" / "dashboards"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def load_latest_data(self) -> Dict[str, Any]:
        """Load the most recent intelligence data"""
        processed_dir = self.data_dir / "processed"

        if not processed_dir.exists():
            raise FileNotFoundError(f"No processed data found in {processed_dir}")

        # Find latest processed file
        json_files = list(processed_dir.glob("intelligent_leads*.json"))
        if not json_files:
            raise FileNotFoundError("No intelligent leads data found")

        latest_file = max(json_files, key=lambda x: x.stat().st_mtime)

        with open(latest_file, 'r') as f:
            return json.load(f)

    def generate_overview_dashboard(self, data: List[Dict[str, Any]]) -> str:
        """Generate main overview dashboard"""
        df = pd.DataFrame(data)

        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Intelligence Score Distribution', 'Engagement Potential',
                          'Top Companies', 'Quality Signals'),
            specs=[[{'type': 'histogram'}, {'type': 'pie'}],
                   [{'type': 'bar'}, {'type': 'bar'}]]
        )

        # Intelligence Score Distribution
        fig.add_trace(
            go.Histogram(x=df['intelligence_score'], nbinsx=20, name="Scores"),
            row=1, col=1
        )

        # Engagement Potential Pie Chart
        potential_counts = df['engagement_potential'].value_counts()
        fig.add_trace(
            go.Pie(labels=potential_counts.index, values=potential_counts.values,
                  name="Engagement Potential"),
            row=1, col=2
        )

        # Top Companies
        company_counts = df['company'].dropna().value_counts().head(10)
        fig.add_trace(
            go.Bar(x=company_counts.index, y=company_counts.values,
                  name="Company Distribution"),
            row=2, col=1
        )

        # Quality Signals (simplified)
        signal_counts = {}
        for signals_str in df['quality_signals'].dropna():
            for signal in signals_str.split(','):
                signal = signal.strip()
                if signal:
                    signal_counts[signal] = signal_counts.get(signal, 0) + 1

        top_signals = sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        signal_names, signal_values = zip(*top_signals)

        fig.add_trace(
            go.Bar(x=signal_names, y=signal_values, name="Quality Signals"),
            row=2, col=2
        )

        # Update layout
        fig.update_layout(
            height=800,
            title_text="Lead Intelligence Overview Dashboard",
            showlegend=False
        )

        return offline.plot(fig, include_plotlyjs=True, output_type='div')

    def generate_quality_dashboard(self, data: List[Dict[str, Any]]) -> str:
        """Generate quality analysis dashboard"""
        df = pd.DataFrame(data)

        # Calculate quality metrics
        quality_metrics = {
            'Has Email': df['email_profile'].notna() | df['email_public_commit'].notna(),
            'Has Company': df['company'].notna(),
            'Has Location': df['location'].notna(),
            'Has Bio': df['bio'].notna(),
            'High Followers': df['followers'] > 50,
            'Active Contributor': df['public_repos'] > 10
        }

        quality_df = pd.DataFrame({k: v.sum() for k, v in quality_metrics.items()},
                                index=['Count']).T
        quality_df['Percentage'] = (quality_df['Count'] / len(df) * 100).round(1)

        # Create quality chart
        fig = go.Figure(data=[
            go.Bar(
                x=quality_df.index,
                y=quality_df['Percentage'],
                text=quality_df['Percentage'].astype(str) + '%',
                textposition='auto',
            )
        ])

        fig.update_layout(
            title="Lead Quality Metrics",
            xaxis_title="Quality Metric",
            yaxis_title="Percentage of Leads (%)",
            height=500
        )

        return offline.plot(fig, include_plotlyjs=True, output_type='div')

    def generate_opportunity_dashboard(self, data: List[Dict[str, Any]]) -> str:
        """Generate opportunity analysis dashboard"""
        df = pd.DataFrame(data)

        # Technology distribution
        tech_counts = df['language'].dropna().value_counts().head(10)

        # Company concentration
        company_counts = df['company'].dropna().value_counts().head(10)

        # Create subplot
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Technology Distribution', 'Company Concentration')
        )

        # Technology bar chart
        fig.add_trace(
            go.Bar(x=tech_counts.index, y=tech_counts.values, name="Technologies"),
            row=1, col=1
        )

        # Company bar chart
        fig.add_trace(
            go.Bar(x=company_counts.index, y=company_counts.values, name="Companies"),
            row=1, col=2
        )

        fig.update_layout(
            height=500,
            title_text="Opportunity Analysis Dashboard",
            showlegend=False
        )

        return offline.plot(fig, include_plotlyjs=True, output_type='div')

    def generate_lead_detail_view(self, data: List[Dict[str, Any]], top_n: int = 20) -> str:
        """Generate detailed lead view for top performers"""
        df = pd.DataFrame(data)
        top_leads = df.nlargest(top_n, 'intelligence_score')

        # Create detailed table
        table_data = []
        for _, lead in top_leads.iterrows():
            table_data.append({
                'Login': lead['login'],
                'Score': lead['intelligence_score'],
                'Email': lead.get('email_profile') or lead.get('email_public_commit') or 'N/A',
                'Company': lead.get('company') or 'N/A',
                'Location': lead.get('location') or 'N/A',
                'Followers': lead.get('followers') or 0,
                'Stars': lead.get('stars') or 0,
                'Repository': lead.get('repo_full_name') or 'N/A'
            })

        table_df = pd.DataFrame(table_data)

        fig = go.Figure(data=[go.Table(
            header=dict(values=list(table_df.columns),
                       fill_color='paleturquoise',
                       align='left'),
            cells=dict(values=[table_df[col] for col in table_df.columns],
                      fill_color='lavender',
                      align='left'))
        ])

        fig.update_layout(
            title=f"Top {top_n} Lead Performers",
            height=600
        )

        return offline.plot(fig, include_plotlyjs=True, output_type='div')

    def generate_html_dashboard(self, data: List[Dict[str, Any]]) -> str:
        """Generate complete HTML dashboard"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Generate all dashboard components
        overview_chart = self.generate_overview_dashboard(data)
        quality_chart = self.generate_quality_dashboard(data)
        opportunity_chart = self.generate_opportunity_dashboard(data)
        detail_view = self.generate_lead_detail_view(data)

        # Create HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Lead Intelligence Dashboard</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #e0e0e0;
                    padding-bottom: 20px;
                }}
                .dashboard-section {{
                    margin-bottom: 40px;
                }}
                .chart-container {{
                    margin: 20px 0;
                    padding: 15px;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                    background-color: #fafafa;
                }}
                .stats {{
                    display: flex;
                    justify-content: space-around;
                    margin: 20px 0;
                    flex-wrap: wrap;
                }}
                .stat-card {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    text-align: center;
                    min-width: 150px;
                    margin: 10px;
                }}
                .stat-number {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #007acc;
                }}
                .stat-label {{
                    font-size: 14px;
                    color: #666;
                    margin-top: 5px;
                }}
            </style>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 Lead Intelligence Dashboard</h1>
                    <p>Generated on {timestamp}</p>
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number">{len(data)}</div>
                            <div class="stat-label">Total Leads</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len([d for d in data if d.get('engagement_potential') == 'high'])}</div>
                            <div class="stat-label">High Potential</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{len([d for d in data if d.get('email_profile') or d.get('email_public_commit')])}</div>
                            <div class="stat-label">With Email</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{round(sum(d.get('intelligence_score', 0) for d in data) / len(data), 1) if data else 0}</div>
                            <div class="stat-label">Avg Score</div>
                        </div>
                    </div>
                </div>

                <div class="dashboard-section">
                    <h2>📊 Overview</h2>
                    <p>
                        This overview shows how intelligence scores are distributed, the split of engagement potential,
                        which companies appear most among leads, and the most common quality signals. Use it to quickly
                        assess overall lead quality and concentration.
                    </p>
                    <div class="chart-container">
                        {overview_chart}
                    </div>
                </div>

                <div class="dashboard-section">
                    <h2>✅ Quality Analysis</h2>
                    <p>
                        The quality analysis summarizes the presence of key attributes (email, company, location, bio)
                        and activity indicators (followers, repositories). Higher percentages indicate richer, more
                        contactable leads.
                    </p>
                    <div class="chart-container">
                        {quality_chart}
                    </div>
                </div>

                <div class="dashboard-section">
                    <h2>🎯 Opportunity Analysis</h2>
                    <p>
                        Opportunity analysis highlights top technologies and company clusters represented in your lead set.
                        Use this to align messaging and potential cohort campaigns.
                    </p>
                    <div class="chart-container">
                        {opportunity_chart}
                    </div>
                </div>

                <div class="dashboard-section">
                    <h2>🏆 Top Performers</h2>
                    <p>
                        The table lists the top-scoring leads with key attributes for quick outreach prioritization.
                    </p>
                    <div class="chart-container">
                        {detail_view}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html_template

    def save_dashboard(self, data: List[Dict[str, Any]], filename: str = None) -> str:
        """Save dashboard to HTML file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"intelligence_dashboard_{timestamp}.html"

        dashboard_html = self.generate_html_dashboard(data)

        dashboard_path = self.reports_dir / filename
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_html)

        return str(dashboard_path)


def main():
    """Generate dashboard from latest intelligence data"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate Lead Intelligence Dashboard')
    parser.add_argument('--data-dir', default='lead_intelligence/data',
                       help='Directory containing intelligence data')
    parser.add_argument('--output', help='Output filename (optional)')

    args = parser.parse_args()

    try:
        dashboard = IntelligenceDashboard(args.data_dir)
        data = dashboard.load_latest_data()

        output_path = dashboard.save_dashboard(data, args.output)

        print(f"✅ Dashboard generated: {output_path}")
        print(f"📊 Total leads analyzed: {len(data)}")

        # Print summary stats
        high_potential = len([d for d in data if d.get('engagement_potential') == 'high'])
        with_email = len([d for d in data if d.get('email_profile') or d.get('email_public_commit')])

        print("📈 Summary:")
        print(f"   • High potential leads: {high_potential}")
        print(f"   • Leads with email: {with_email}")
        print(f"   • Average intelligence score: {round(sum(d.get('intelligence_score', 0) for d in data) / len(data), 1) if data else 0}")

    except Exception as e:
        print(f"❌ Error generating dashboard: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
