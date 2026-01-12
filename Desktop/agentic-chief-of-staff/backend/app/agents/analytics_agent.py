"""Analytics Agent - Provides data analysis, metrics, and business intelligence."""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse


class AnalyticsAgent(BaseAgent):
    """
    Analytics Agent - Data Analysis and Business Intelligence.

    Handles:
    - Data analysis and visualization recommendations
    - KPI tracking and reporting
    - Trend identification
    - Performance metrics
    - Dashboard creation
    - Predictive insights
    """

    SYSTEM_PROMPT = """You are the Analytics Agent - an expert at data analysis and business intelligence for executives.

Your capabilities:
1. Analyze data and identify patterns
2. Track and report on KPIs
3. Create executive dashboards and reports
4. Identify trends and anomalies
5. Provide predictive insights
6. Recommend data-driven decisions

Analytics Guidelines:
- Present data clearly with context
- Highlight significant trends and changes
- Compare against benchmarks
- Provide actionable insights
- Use appropriate visualizations
- Explain complex metrics simply

Response Format (JSON):
{
    "action": "analyze|report|compare|forecast|alert",
    "analysis_type": "financial|performance|operational|customer|market",
    "metrics": [
        {
            "name": "Metric name",
            "value": 1234,
            "unit": "currency|percent|count|time",
            "trend": "up|down|stable",
            "change_percent": 5.2,
            "period": "daily|weekly|monthly|quarterly",
            "benchmark": 1000,
            "status": "above_target|on_target|below_target"
        }
    ],
    "insights": [
        {
            "title": "Insight title",
            "description": "Detailed insight",
            "impact": "high|medium|low",
            "recommended_action": "Action to take"
        }
    ],
    "visualizations": [
        {
            "type": "line|bar|pie|table|gauge",
            "title": "Chart title",
            "data_description": "What the chart shows"
        }
    ],
    "forecast": {
        "metric": "Metric name",
        "predicted_value": 1500,
        "confidence": "high|medium|low",
        "timeframe": "Next quarter"
    },
    "response_to_user": "Natural language response with key findings"
}"""

    def __init__(self):
        super().__init__(
            name="analytics",
            display_name="Analytics Expert",
            description="Provides data analysis, metrics, KPIs, and business intelligence insights",
            capabilities=[
                "data_analysis",
                "kpi_tracking",
                "trend_analysis",
                "performance_reporting",
                "dashboard_creation",
                "predictive_analytics"
            ],
            system_prompt=self.SYSTEM_PROMPT
        )

    async def process(self, state: AgentState) -> AgentResponse:
        """Process analytics-related requests."""

        context = self._build_context(state)

        # Retrieve relevant analytics memories
        memories = await self.retrieve_memories(state['task'], limit=3)
        memory_context = ""
        if memories:
            memory_context = "\n\nPrevious Analytics Context:\n" + "\n".join([
                f"- {m['content']}" for m in memories
            ])

        # Sample data context (in production, connect to real data sources)
        sample_data_context = self._get_sample_data_context()

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
{context}
{memory_context}

Available Data Context:
{sample_data_context}

User's Analytics Request: {state['task']}

Analyze this request and provide your response in the specified JSON format.
Include relevant metrics, insights, and visualization recommendations.
""")
        ]

        response_text = await self._call_llm(messages)

        # Parse response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                result = json.loads(response_text[json_start:json_end])
            else:
                result = self._create_default_response(state['task'])
        except json.JSONDecodeError:
            result = self._create_default_response(state['task'])

        # Store important insights in memory
        if result.get('insights'):
            insights_summary = "; ".join([i.get('title', '') for i in result.get('insights', [])[:3]])
            await self.store_memory(
                content=f"Analytics insights for '{state['task'][:50]}': {insights_summary}",
                memory_type='semantic',
                conversation_id=state.get('conversation_id'),
                importance=0.8
            )

        user_response = result.get('response_to_user', 'Analytics report generated.')

        # Format metrics for display
        if result.get('metrics'):
            metrics_display = self._format_metrics_display(result['metrics'])
            user_response = f"{user_response}\n\n{metrics_display}"

        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=user_response,
            thoughts=[
                f"Analysis type: {result.get('analysis_type', '')}",
                f"Metrics analyzed: {len(result.get('metrics', []))}",
                f"Insights generated: {len(result.get('insights', []))}"
            ],
            tool_calls=[{'tool': 'analytics_engine', 'action': result.get('action', ''), 'type': result.get('analysis_type', '')}],
            data=result
        )

    def _get_sample_data_context(self) -> str:
        """Get sample data context for analysis."""
        return """
Sample Available Metrics:
- Revenue: Monthly tracking, YoY comparison
- User Engagement: DAU, MAU, session duration
- Conversion Rates: By channel, by product
- Customer Satisfaction: NPS, CSAT scores
- Operational Metrics: Response time, throughput
- Team Performance: Tasks completed, velocity

Data can be filtered by:
- Time period (daily, weekly, monthly, quarterly, yearly)
- Department/Team
- Product/Service
- Region/Market
- Customer segment
"""

    def _format_metrics_display(self, metrics: List[Dict]) -> str:
        """Format metrics for display."""
        lines = ["📊 **Key Metrics**\n"]
        for metric in metrics[:6]:
            trend_emoji = {'up': '📈', 'down': '📉', 'stable': '➡️'}.get(metric.get('trend', 'stable'), '📊')
            status_emoji = {'above_target': '✅', 'on_target': '🎯', 'below_target': '⚠️'}.get(metric.get('status', ''), '')

            value = metric.get('value', 'N/A')
            unit = metric.get('unit', '')
            if unit == 'currency':
                value = f"${value:,.0f}" if isinstance(value, (int, float)) else value
            elif unit == 'percent':
                value = f"{value}%"

            change = metric.get('change_percent', 0)
            change_str = f" ({'+' if change > 0 else ''}{change}%)" if change else ""

            lines.append(f"{trend_emoji} **{metric.get('name', 'Metric')}**: {value}{change_str} {status_emoji}")

        return "\n".join(lines)

    def _create_default_response(self, task: str) -> Dict[str, Any]:
        """Create default response when parsing fails."""
        return {
            'action': 'analyze',
            'analysis_type': 'general',
            'metrics': [],
            'insights': [
                {
                    'title': 'Analysis in Progress',
                    'description': f'Analyzing: {task}',
                    'impact': 'medium',
                    'recommended_action': 'Review the detailed analysis'
                }
            ],
            'response_to_user': f"I'm analyzing your request: '{task[:50]}'. What specific metrics or data would you like me to focus on?"
        }
