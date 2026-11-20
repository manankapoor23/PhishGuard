"""Extra checks for the report (notebook 13, decision D19).

- popular_owner_labels: site owners that are popular real websites (Tranco) yet labelled
  phishing in PhiUSIIL, e.g. google.com, whose Docs and Sites host phishing pages;
- reliability_table / expected_calibration_error: does "90% phishing" mean 90%?
- threshold_for_fpr: the threshold a browser warning would need (few false alarms);
- with_allowlist: never flag a site whose owner is on an allowlist of popular sites.
"""

import numpy as np
import pandas as pd

from phishguard.split import site_owner


def popular_owner_labels(df: pd.DataFrame, target: str, ranking: pd.DataFrame, min_rows: int = 20) -> pd.DataFrame:
    """Owners in a popularity ranking (columns rank, domain) with their PhiUSIIL row count and phishing share."""
    owners = site_owner(df["URL"])
    stats = df[target].groupby(owners.to_numpy()).agg(rows="size", phishing_share="mean")
    rank = ranking.drop_duplicates("domain").set_index("domain")["rank"]
    popular = stats[stats.index.isin(rank.index) & (stats["rows"] >= min_rows)]
    return popular.assign(tranco_rank=rank.reindex(popular.index)).sort_values("rows", ascending=False)


def reliability_table(y_true, y_prob, bins: int = 10) -> pd.DataFrame:
    """Per probability bin: links in it, average predicted probability, share actually phishing."""
    y_true, y_prob = np.asarray(y_true), np.asarray(y_prob)
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(y_prob, edges[1:-1]), 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = which == b
        if mask.any():
            rows.append({"bin": f"{edges[b]:.1f}–{edges[b + 1]:.1f}", "links": int(mask.sum()),
                         "predicted": float(y_prob[mask].mean()), "observed": float(y_true[mask].mean())})
    return pd.DataFrame(rows)


def expected_calibration_error(y_true, y_prob, bins: int = 10) -> float:
    """Average gap between predicted and observed phishing share, weighted by how many links each bin holds."""
    table = reliability_table(y_true, y_prob, bins)
    return float((table["links"] * (table["predicted"] - table["observed"]).abs()).sum() / table["links"].sum())


def threshold_for_fpr(y_true, y_prob, max_fpr: float) -> float:
    """Lowest threshold whose false-alarm rate on these (validation) links is at most max_fpr."""
    y_true, y_prob = np.asarray(y_true), np.asarray(y_prob)
    legit = np.sort(y_prob[y_true == 0])
    allowed = int(np.floor(max_fpr * len(legit)))      # legitimate links we may flag
    # flag p >= t; the threshold sits just above the (allowed+1)-th highest legitimate score
    return float(np.nextafter(legit[len(legit) - allowed - 1], 1.0)) if allowed < len(legit) else 0.0


def rates_at(y_true, y_prob, threshold: float) -> dict:
    """Share of phishing caught and of legitimate links flagged at a threshold."""
    y_true, flagged = np.asarray(y_true), np.asarray(y_prob) >= threshold
    return {"caught": float(flagged[y_true == 1].mean()), "false_alarms": float(flagged[y_true == 0].mean())}


def with_allowlist(domains: pd.Series, flagged: np.ndarray, allowlist: set[str]) -> np.ndarray:
    """Un-flag every domain whose site owner is on the allowlist."""
    return np.asarray(flagged) & ~site_owner(pd.Series(domains)).isin(allowlist).to_numpy()
