import numpy as np
import pandas as pd

from phishguard.audit import (expected_calibration_error, popular_owner_labels, rates_at, reliability_table,
                              threshold_for_fpr, with_allowlist)


def test_perfectly_calibrated_scores_have_no_gap():
    rng = np.random.default_rng(0)
    prob = rng.uniform(size=200_000)
    y = rng.uniform(size=prob.size) < prob                      # phishing exactly as often as predicted
    assert expected_calibration_error(y, prob) < 0.01
    assert expected_calibration_error(y, np.clip(prob + 0.3, 0, 1)) > 0.2   # overconfident scores


def test_reliability_table_counts_every_link():
    table = reliability_table([0, 1, 1, 0], [0.05, 0.95, 0.9, 0.5], bins=10)
    assert table["links"].sum() == 4 and table.iloc[-1]["observed"] == 1.0


def test_threshold_for_fpr_keeps_false_alarms_under_the_limit():
    rng = np.random.default_rng(1)
    y = np.r_[np.zeros(10_000), np.ones(10_000)]
    prob = np.r_[rng.beta(2, 5, 10_000), rng.beta(5, 2, 10_000)]
    for max_fpr in (0.01, 0.001):
        t = threshold_for_fpr(y, prob, max_fpr)
        assert rates_at(y, prob, t)["false_alarms"] <= max_fpr


def test_allowlist_unflags_owners_only():
    domains = pd.Series(["mail.google.com", "google.evil.top", "example.org"])
    assert with_allowlist(domains, np.array([True, True, True]), {"google.com"}).tolist() == [False, True, True]


def test_popular_owner_labels():
    df = pd.DataFrame({"URL": ["https://docs.google.com/a"] * 25 + ["https://www.example.org"] * 25,
                       "is_phishing": [1] * 25 + [0] * 25})
    ranking = pd.DataFrame({"rank": [1, 50], "domain": ["google.com", "example.org"]})
    table = popular_owner_labels(df, "is_phishing", ranking)
    assert table.loc["google.com", "phishing_share"] == 1.0 and table.loc["example.org", "tranco_rank"] == 50
