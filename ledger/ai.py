"""AI analyst interface."""

from typing import Optional
from ledger.stats import StatsReport
import requests
import json


class Analyst:
    """AI analyst using Anthropic Claude."""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"
    
    def is_configured(self) -> bool:
        """Return True if API key is set."""
        return bool(self.api_key)
    
    def analyse(self, report: StatsReport) -> Optional[str]:
        """
        Generate analysis from statistical report.
        
        Returns prose analysis (max 250 words), or None if error.
        Never suggests trades, direction, or prices.
        """
        if not self.is_configured():
            return None
        
        try:
            prompt = self._build_prompt(report)
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            
            data = {
                "model": self.model,
                "max_tokens": 500,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
            
            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=data,
                timeout=30,
            )
            response.raise_for_status()
            
            result = response.json()
            text = result["content"][0]["text"]
            
            # Truncate to 250 words
            words = text.split()
            if len(words) > 250:
                text = " ".join(words[:250]) + "..."
            
            return text
        
        except Exception as e:
            print(f"Analyst error: {e}")
            return None
    
    def _build_prompt(self, report: StatsReport) -> str:
        """
        Build prompt for analyst (no raw trades, only statistics).
        """
        prompt = f"""
Analyse this trading performance report. Limit your response to 250 words.

Do NOT suggest trades, prices, or direction. Do NOT predict price movement.

Report:
- Total trades: {report.total_trades}
- Wins: {report.win_count}, Losses: {report.loss_count}
- Win rate: {report.win_rate:.1%}
- Mean R: {report.mean_r:.2f} [CI: {report.mean_r_ci_lower:.2f} to {report.mean_r_ci_upper:.2f}]

Key findings:
"""
        
        # Add significant findings only
        findings = [c for c in report.cuts if c.bh_verdict == "holding"]
        if findings:
            for f in findings[:5]:  # Top 5 findings
                prompt += f"\n- {f.cut_name} {f.group_name}: mean R {f.mean_r:.2f} (n={f.count})"
        else:
            prompt += "\n- No statistically significant findings (after BH correction)"
        
        # Add underpowered groups
        underpowered = [c for c in report.cuts if c.bh_verdict == "too little data"]
        if underpowered:
            prompt += f"\n\nUnderpowered groups (n<30): {len(underpowered)}"
        
        prompt += "\n\nProvide a brief interpretation. Do not suggest trading decisions."
        
        return prompt
