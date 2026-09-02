"""Statistical analysis engine: bootstrap CI, permutation testing, BH correction."""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from ledger.models import Trade


@dataclass
class CutResult:
    """Result of a statistical cut analysis."""
    cut_name: str
    group_name: str
    count: int
    mean_r: float
    ci_lower: float
    ci_upper: float
    p_value: Optional[float] = None
    bh_verdict: str = "NOT DEFINED"  # "holding", "not distinguishable", "too little data"
    

@dataclass
class StatsReport:
    """Complete statistics report for all trades."""
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    mean_r: float
    mean_r_ci_lower: float
    mean_r_ci_upper: float
    cuts: List[CutResult]
    
    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "total_trades": self.total_trades,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": self.win_rate,
            "mean_r": self.mean_r,
            "mean_r_ci_lower": self.mean_r_ci_lower,
            "mean_r_ci_upper": self.mean_r_ci_upper,
            "cuts": [
                {
                    "cut_name": c.cut_name,
                    "group_name": c.group_name,
                    "count": c.count,
                    "mean_r": c.mean_r,
                    "ci_lower": c.ci_lower,
                    "ci_upper": c.ci_upper,
                    "p_value": c.p_value,
                    "verdict": c.bh_verdict,
                }
                for c in self.cuts
            ],
        }


class StatsEngine:
    """Statistical analysis for trades."""
    
    MIN_SAMPLE_SIZE = 30  # Trades required for significance
    BOOTSTRAP_SAMPLES = 10000
    PERMUTATION_SAMPLES = 10000
    BH_FDR = 0.10  # Benjamini-Hochberg q-value
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)
    
    def analyse(self, trades: List[Trade]) -> StatsReport:
        """
        Perform complete statistical analysis on trades.
        
        Excludes backtests and trades without R values.
        """
        # Filter: no backtests, must have R
        trades = [t for t in trades if not t.is_backtest() and t.r_value is not None]
        
        if not trades:
            return StatsReport(
                total_trades=0,
                win_count=0,
                loss_count=0,
                win_rate=0.0,
                mean_r=0.0,
                mean_r_ci_lower=0.0,
                mean_r_ci_upper=0.0,
                cuts=[],
            )
        
        # Overall statistics
        r_values = [t.r_value for t in trades]
        win_count = sum(1 for t in trades if t.is_win())
        loss_count = sum(1 for t in trades if t.is_loss())
        win_rate = win_count / len(trades) if trades else 0.0
        
        mean_r, ci_lower, ci_upper = self._bootstrap_ci(r_values)
        
        # Perform all cuts
        cuts = []
        cuts.extend(self._cut_killzone(trades))
        cuts.extend(self._cut_macro(trades))
        cuts.extend(self._cut_grade(trades))
        cuts.extend(self._cut_premises(trades))
        cuts.extend(self._cut_day_of_week(trades))
        
        # Apply Benjamini-Hochberg correction
        cuts = self._apply_bh_correction(cuts)
        
        return StatsReport(
            total_trades=len(trades),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            mean_r=mean_r,
            mean_r_ci_lower=ci_lower,
            mean_r_ci_upper=ci_upper,
            cuts=cuts,
        )
    
    def _bootstrap_ci(
        self, values: List[float], alpha: float = 0.05
    ) -> Tuple[float, float, float]:
        """
        Calculate bootstrap confidence interval.
        
        Returns: (mean, ci_lower, ci_upper)
        """
        if not values:
            return 0.0, 0.0, 0.0
        
        values = np.array(values)
        mean = np.mean(values)
        
        # Bootstrap resamples
        np.random.seed(self.seed)
        bootstrap_means = []
        for _ in range(self.BOOTSTRAP_SAMPLES):
            resample = np.random.choice(values, size=len(values), replace=True)
            bootstrap_means.append(np.mean(resample))
        
        bootstrap_means = np.array(bootstrap_means)
        ci_lower = np.percentile(bootstrap_means, (alpha / 2) * 100)
        ci_upper = np.percentile(bootstrap_means, (1 - alpha / 2) * 100)
        
        return float(mean), float(ci_lower), float(ci_upper)
    
    def _permutation_test(self, group1: List[float], group2: List[float]) -> float:
        """
        Permutation test comparing two groups.
        
        Returns: p-value
        """
        if len(group1) < 1 or len(group2) < 1:
            return 1.0
        
        group1 = np.array(group1)
        group2 = np.array(group2)
        
        # Observed difference
        obs_diff = abs(np.mean(group1) - np.mean(group2))
        
        # Permutation test
        combined = np.concatenate([group1, group2])
        np.random.seed(self.seed)
        perm_diffs = []
        
        for _ in range(self.PERMUTATION_SAMPLES):
            perm = np.random.permutation(combined)
            perm1 = perm[:len(group1)]
            perm2 = perm[len(group1):]
            perm_diffs.append(abs(np.mean(perm1) - np.mean(perm2)))
        
        p_value = sum(d >= obs_diff for d in perm_diffs) / len(perm_diffs)
        return float(p_value)
    
    def _cut_killzone(self, trades: List[Trade]) -> List[CutResult]:
        """Analyse killzone cut."""
        groups = {}
        for t in trades:
            kz = t.ny_killzone
            if kz not in groups:
                groups[kz] = []
            if t.r_value is not None:
                groups[kz].append(t.r_value)
        
        results = []
        for group_name, values in sorted(groups.items()):
            if len(values) >= self.MIN_SAMPLE_SIZE:
                mean, ci_lower, ci_upper = self._bootstrap_ci(values)
                results.append(CutResult(
                    cut_name="Killzone",
                    group_name=group_name,
                    count=len(values),
                    mean_r=mean,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    p_value=None,  # Will be computed in pairwise comparison
                ))
            else:
                results.append(CutResult(
                    cut_name="Killzone",
                    group_name=group_name,
                    count=len(values),
                    mean_r=np.mean(values) if values else 0.0,
                    ci_lower=0.0,
                    ci_upper=0.0,
                    p_value=None,
                    bh_verdict="too little data",
                ))
        
        # Pairwise permutation tests
        group_list = [(name, values) for name, values in sorted(groups.items()) if len(values) >= self.MIN_SAMPLE_SIZE]
        if len(group_list) >= 2:
            # Compare best vs. worst
            best_group = max(group_list, key=lambda x: np.mean(x[1]))[1]
            worst_group = min(group_list, key=lambda x: np.mean(x[1]))[1]
            if best_group is not worst_group:
                p = self._permutation_test(best_group, worst_group)
                for r in results:
                    if r.bh_verdict != "too little data":
                        r.p_value = p
        
        return results
    
    def _cut_macro(self, trades: List[Trade]) -> List[CutResult]:
        """Analyse macro session cut."""
        groups = {}
        for t in trades:
            macro = t.ny_macro
            if macro not in groups:
                groups[macro] = []
            if t.r_value is not None:
                groups[macro].append(t.r_value)
        
        results = []
        for group_name, values in sorted(groups.items()):
            if len(values) >= self.MIN_SAMPLE_SIZE:
                mean, ci_lower, ci_upper = self._bootstrap_ci(values)
                results.append(CutResult(
                    cut_name="Macro",
                    group_name=group_name,
                    count=len(values),
                    mean_r=mean,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    p_value=None,
                ))
            else:
                results.append(CutResult(
                    cut_name="Macro",
                    group_name=group_name,
                    count=len(values),
                    mean_r=np.mean(values) if values else 0.0,
                    ci_lower=0.0,
                    ci_upper=0.0,
                    p_value=None,
                    bh_verdict="too little data",
                ))
        
        return results
    
    def _cut_grade(self, trades: List[Trade]) -> List[CutResult]:
        """Analyse grade cut."""
        groups = {}
        for t in trades:
            if t.grade:
                grade = t.grade
                if grade not in groups:
                    groups[grade] = []
                if t.r_value is not None:
                    groups[grade].append(t.r_value)
        
        results = []
        for group_name in ["A", "B", "C", "D"]:
            values = groups.get(group_name, [])
            if len(values) >= self.MIN_SAMPLE_SIZE:
                mean, ci_lower, ci_upper = self._bootstrap_ci(values)
                results.append(CutResult(
                    cut_name="Grade",
                    group_name=group_name,
                    count=len(values),
                    mean_r=mean,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    p_value=None,
                ))
            elif values:
                results.append(CutResult(
                    cut_name="Grade",
                    group_name=group_name,
                    count=len(values),
                    mean_r=np.mean(values),
                    ci_lower=0.0,
                    ci_upper=0.0,
                    p_value=None,
                    bh_verdict="too little data",
                ))
        
        return results
    
    def _cut_premises(self, trades: List[Trade]) -> List[CutResult]:
        """Analyse premises cut."""
        groups = {
            "0-2": [],
            "3-4": [],
            "5-7": [],
        }
        
        for t in trades:
            if t.r_value is not None:
                count = len(t.premises_met)
                if count <= 2:
                    groups["0-2"].append(t.r_value)
                elif count <= 4:
                    groups["3-4"].append(t.r_value)
                else:
                    groups["5-7"].append(t.r_value)
        
        results = []
        for group_name in ["0-2", "3-4", "5-7"]:
            values = groups[group_name]
            if len(values) >= self.MIN_SAMPLE_SIZE:
                mean, ci_lower, ci_upper = self._bootstrap_ci(values)
                results.append(CutResult(
                    cut_name="Premises",
                    group_name=group_name,
                    count=len(values),
                    mean_r=mean,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    p_value=None,
                ))
            elif values:
                results.append(CutResult(
                    cut_name="Premises",
                    group_name=group_name,
                    count=len(values),
                    mean_r=np.mean(values),
                    ci_lower=0.0,
                    ci_upper=0.0,
                    p_value=None,
                    bh_verdict="too little data",
                ))
        
        return results
    
    def _cut_day_of_week(self, trades: List[Trade]) -> List[CutResult]:
        """Analyse day-of-week cut."""
        groups = {day: [] for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for t in trades:
            if t.r_value is not None:
                day_idx = t.entry_time.weekday()
                if 0 <= day_idx < 7:
                    groups[day_names[day_idx]].append(t.r_value)
        
        results = []
        for day in day_names:
            values = groups[day]
            if len(values) >= self.MIN_SAMPLE_SIZE:
                mean, ci_lower, ci_upper = self._bootstrap_ci(values)
                results.append(CutResult(
                    cut_name="Day of Week",
                    group_name=day,
                    count=len(values),
                    mean_r=mean,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    p_value=None,
                ))
            elif values:
                results.append(CutResult(
                    cut_name="Day of Week",
                    group_name=day,
                    count=len(values),
                    mean_r=np.mean(values),
                    ci_lower=0.0,
                    ci_upper=0.0,
                    p_value=None,
                    bh_verdict="too little data",
                ))
        
        return results
    
    def _apply_bh_correction(self, cuts: List[CutResult]) -> List[CutResult]:
        """
        Apply Benjamini-Hochberg correction to all cuts.
        
        Modifies verdict in-place.
        """
        # Collect all p-values
        p_values = []
        indices = []
        for i, cut in enumerate(cuts):
            if cut.p_value is not None and cut.bh_verdict == "NOT DEFINED":
                p_values.append((cut.p_value, i))
        
        if not p_values:
            # No p-values to correct; mark underpowered as "too little data"
            for cut in cuts:
                if cut.bh_verdict == "NOT DEFINED":
                    if cut.count < self.MIN_SAMPLE_SIZE:
                        cut.bh_verdict = "too little data"
                    else:
                        cut.bh_verdict = "not distinguishable from chance"
            return cuts
        
        # Sort by p-value
        p_values.sort()
        
        # Find largest i where p[i] <= (i+1)/m * q
        m = len(p_values)
        threshold_idx = -1
        for i, (p, _) in enumerate(p_values):
            threshold = ((i + 1) / m) * self.BH_FDR
            if p <= threshold:
                threshold_idx = i
        
        # Mark results
        significant_indices = set(idx for _, idx in p_values[:threshold_idx + 1])
        
        for cut in cuts:
            if cut.bh_verdict == "NOT DEFINED":
                if cut.count < self.MIN_SAMPLE_SIZE:
                    cut.bh_verdict = "too little data"
                else:
                    cut_id = id(cut)
                    # Find index of this cut in original list
                    for i, c in enumerate(cuts):
                        if id(c) == cut_id:
                            if i in significant_indices:
                                cut.bh_verdict = "holding"
                            else:
                                cut.bh_verdict = "not distinguishable from chance"
                            break
        
        return cuts
