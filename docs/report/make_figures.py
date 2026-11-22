"""Figures for the course report (docs/report/figures/), drawn from the data and saved results only.

Run:  .venv/bin/python docs/report/make_figures.py
"""

import json

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from phishguard.audit import reliability_table
from phishguard.data import REPO_ROOT, TARGET, load_clean
from phishguard.evaluate import RESULTS_DIR, load_results
from phishguard.experiment import load_predictions
from phishguard.features import extract_features

matplotlib.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
                            "font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
OUT = REPO_ROOT / "docs" / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
LEGIT, PHISH, GREY = "#235FA3", "#B8322A", "#8A97A8"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)


def workflow():
    steps = [("Raw data\nPhiUSIIL, 235,795 links", "#E8EDF3"), ("Cleaning\nlabels, duplicates, '/'", "#E8EDF3"),
             ("Split by website owner\n70 / 15 / 15, 5 seeds", "#E8EDF3"), ("Shortcut audit\nrules, column groups", "#FBEFD5"),
             ("URL views\nraw → domain only", "#FBEFD5"), ("Models\nLR, RF, XGBoost, n-grams,\nCNN, BiLSTM, hybrid", "#DCE6F2"),
             ("Evaluation\nvalidation tuning, test once,\nMcNemar, 95% CI", "#DCE6F2"), ("Explanations\nSHAP, occlusion,\ndeletion test", "#DCE6F2"),
             ("Real-world tests\nCrUX, Tranco, PhishTank,\nattacks", "#F3D9D6"), ("Better data (7b)\nretrain, re-test", "#F3D9D6"),
             ("Website\nFastAPI + HTML page", "#E8EDF3")]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 3)
    ax.axis("off")
    positions = [(0.5, 2.5), (1.5, 2.5), (2.5, 2.5), (3.5, 2.5), (3.5, 1.5), (2.5, 1.5), (1.5, 1.5), (0.5, 1.5),
                 (0.5, 0.5), (1.5, 0.5), (2.5, 0.5)]
    for (text, colour), (x, y) in zip(steps, positions):
        ax.add_patch(FancyBboxPatch((x - 0.44, y - 0.33), 0.88, 0.66, boxstyle="round,pad=0.02",
                                    facecolor=colour, edgecolor="#5A6577", linewidth=0.8))
        ax.text(x, y, text, ha="center", va="center", fontsize=9)
    for (x1, y1), (x2, y2) in zip(positions, positions[1:]):
        if y1 == y2:
            start, end = ((x1 + 0.45, y1), (x2 - 0.45, y2)) if x2 > x1 else ((x1 - 0.45, y1), (x2 + 0.45, y2))
        else:
            start, end = (x1, y1 - 0.34), (x2, y2 + 0.34)
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12, color="#5A6577", linewidth=1))
    save(fig, "fig_workflow")


def eda(df):
    y = df[TARGET]
    fig, ax = plt.subplots(figsize=(5, 3.2))
    counts = y.map({0: "Legitimate", 1: "Phishing"}).value_counts().reindex(["Legitimate", "Phishing"])
    bars = ax.bar(counts.index, counts.values, color=[LEGIT, PHISH], width=0.55)
    ax.bar_label(bars, labels=[f"{v:,}\n({v / len(y):.1%})" for v in counts.values], fontsize=10)
    ax.set_ylabel("Number of links")
    ax.set_ylim(0, counts.max() * 1.25)
    save(fig, "fig_class_balance")

    feats = extract_features(df["URL"])
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2))
    for ax, col, label in zip(axes, ["url_length", "num_digits", "num_subdomains"],
                              ["URL length (characters)", "Digits in the URL", "Number of subdomains"]):
        clip = feats[col].quantile(0.99)
        for cls, colour, name in [(0, LEGIT, "Legitimate"), (1, PHISH, "Phishing")]:
            values = feats.loc[y == cls, col].clip(upper=clip)
            ax.hist(values, bins=30, density=True, histtype="step", linewidth=1.6, color=colour, label=name)
        ax.set_xlabel(label)
    axes[0].set_ylabel("Share of links (density)")
    axes[0].legend(frameon=False)
    save(fig, "fig_eda_features")

    shares = pd.DataFrame({
        "starts with https://www.": df["URL"].str.startswith("https://www."),
        "uses HTTPS": df["URL"].str.lower().str.startswith("https://"),
        "has a path after the domain": df["URL"].str.replace(r"^[a-zA-Z]+://", "", regex=True).str.contains("/"),
    }).groupby(y.map({0: "Legitimate", 1: "Phishing"})).mean().T * 100
    fig, ax = plt.subplots(figsize=(7, 3.2))
    shares[["Legitimate", "Phishing"]].plot.barh(ax=ax, color=[LEGIT, PHISH], width=0.7)
    for c in ax.containers:
        ax.bar_label(c, fmt="%.1f%%", fontsize=9, padding=2)
    ax.set_xlabel("% of links")
    ax.set_xlim(0, 115)
    ax.legend(frameon=False, loc="lower right")
    ax.invert_yaxis()
    save(fig, "fig_eda_shortcut")


def views():
    t = load_results("m3_views").set_index("model")
    order = ["raw URL", "no scheme/www", "domain only", "registered domain"]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    for name, colour, label in [("Char n-gram LogReg", "#1A2230", "Character n-grams"), ("XGBoost URL features", GREY, "XGBoost, 40 features")]:
        means = [t.loc[f"{name} | {v}", "accuracy"] * 100 for v in order]
        sds = [t.loc[f"{name} | {v}", "accuracy_sd"] * 100 for v in order]
        ax.errorbar(order, means, yerr=sds, marker="o", color=colour, label=label, capsize=3)
        for x, m in zip(order, means):
            ax.annotate(f"{m:.1f}", (x, m), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=9, color=colour)
    ax.set_ylabel("Test accuracy (%), mean ± sd over 5 splits")
    ax.set_ylim(65, 103)
    ax.legend(frameon=False)
    save(fig, "fig_views")


def models():
    rows = [("m3_views", "XGBoost URL features | domain only", "XGBoost\n(40 features)"),
            ("m4_deep", "BiLSTM | domain only", "BiLSTM"),
            ("m3_views", "Char n-gram LogReg | domain only", "Character\nn-grams"),
            ("m4_deep", "Char-CNN | domain only", "Char-CNN"),
            ("m5_hybrid", "Hybrid CNN + features | domain only", "Hybrid\n(CNN + features)")]
    tables = {}
    means, sds, labels = [], [], []
    for group, name, label in rows:
        tables.setdefault(group, load_results(group).set_index("model"))
        means.append(tables[group].loc[name, "accuracy"] * 100)
        sds.append(tables[group].loc[name, "accuracy_sd"] * 100)
        labels.append(label)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    bars = ax.bar(labels, means, yerr=sds, capsize=4, color=[GREY] * 4 + [LEGIT], width=0.6)
    ax.bar_label(bars, labels=[f"{m:.1f}" for m in means], padding=4, fontsize=9)
    ax.set_ylim(75, 92)
    ax.set_ylabel("Test accuracy (%), domain only")
    save(fig, "fig_models")


def real_world():
    numbers = json.loads((REPO_ROOT / "models" / "site_numbers.json").read_text())["real_sites"]
    sets = [("CrUX top 10k: bare domain", "Popular sites,\nplain domain"), ("CrUX top 10k: with a subdomain", "Popular sites\nwith a subdomain"),
            ("Tranco top 20k: registered domains", "Tranco top\nsites")]
    x = np.arange(len(sets))
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    for i, (model, colour, label) in enumerate([("hybrid", PHISH, "Hybrid"), ("ngram", "#D98880", "Character n-grams")]):
        values = [numbers[key][model] * 100 for key, _ in sets]
        bars = ax.bar(x + (i - 0.5) * 0.36, values, 0.36, color=colour, label=label)
        ax.bar_label(bars, fmt="%.0f%%", fontsize=9, padding=2)
    ax.set_xticks(x, [label for _, label in sets])
    ax.set_ylabel("Wrongly flagged as phishing (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False)
    save(fig, "fig_real_world")


def better_data():
    keys = [("crux_subdomain", "False alarms:\npopular sites\nwith subdomain"), ("tranco_test", "False alarms:\nTranco sites"),
            ("phiusiil_phish_all_edits", "Edited\nphishing\ncaught"), ("phishtank_new", "New 2025–26\nphishing\ncaught")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, model, title in zip(axes, ["hybrid", "ngram"], ["Hybrid", "Character n-grams"]):
        before = json.loads((RESULTS_DIR / "m7b" / f"{model}__phiusiil_only.json").read_text())["summary"]
        after = json.loads((RESULTS_DIR / "m7b" / f"{model}__phiusiil_plus_fixes.json").read_text())["summary"]
        x = np.arange(len(keys))
        for i, (summary, colour, label) in enumerate([(before, GREY, "PhiUSIIL only"), (after, LEGIT, "PhiUSIIL + fixes")]):
            bars = ax.bar(x + (i - 0.5) * 0.38, [summary[k]["mean"] * 100 for k, _ in keys], 0.38, color=colour, label=label)
            ax.bar_label(bars, fmt="%.0f", fontsize=8, padding=2)
        ax.set_xticks(x, [label for _, label in keys], fontsize=9)
        ax.set_title(title)
        ax.set_ylim(0, 100)
    axes[0].set_ylabel("% of domains (mean of 5 splits)")
    axes[0].legend(frameon=False)
    save(fig, "fig_better_data")


def calibration(df):
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    ax.plot([0, 1], [0, 1], ":", color=GREY, label="perfect calibration")
    for group, name, label, colour in [("m5_hybrid", "Hybrid CNN + features | domain only", "Hybrid", LEGIT),
                                       ("m3_views", "Char n-gram LogReg | domain only", "Character n-grams", "#1A2230")]:
        p = load_predictions(group, name)
        table = reliability_table(df.loc[p["test_idx"], TARGET].to_numpy(), p["test_prob"])
        ax.plot(table["predicted"], table["observed"], marker="o", color=colour, label=label)
    ax.set_xlabel("Average predicted probability of phishing")
    ax.set_ylabel("Share that really is phishing")
    ax.legend(frameon=False)
    save(fig, "fig_calibration")


if __name__ == "__main__":
    df = load_clean()
    workflow()
    eda(df)
    views()
    models()
    real_world()
    better_data()
    calibration(df)
    print("figures written to", OUT)
