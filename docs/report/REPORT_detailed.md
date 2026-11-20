# PhishGuard: What Does a Phishing URL Detector Really Learn?

**Machine learning course project, 2026.** Manan, Shaurya and Abhishek.
Code, notebooks and data: https://github.com/AIShaurya777/PhishGuard · A plain-language version: [`REPORT.md`](REPORT.md)

---

## Abstract

Published work on the PhiUSIIL phishing URL dataset reports 99.8–99.99% accuracy. We reproduce these results under a stricter protocol: a train/validation/test split grouped by website owner, settings and thresholds chosen on validation only, and every result repeated on five splits. We then show that the scores mainly reflect how the dataset was collected. Every legitimate URL is a bare `https://www.` homepage, and a one-line rule with no learning scores 99.08%. Once the scheme, `www.` and the path are removed and models see only the domain, the best URL-only accuracy falls to about 86–87%. A hybrid network (character CNN plus 40 handcrafted features, trained jointly) is best at 86.72 ± 0.99%, but by under half a point.

We explain the models (TreeSHAP; character and feature occlusion, checked with a deletion test) and test them outside the dataset. On about 25,000 popular real websites, the hybrid flags 15% of plain domains and 81% of sites with a subdomain. Cheap edits cut phishing caught from 86% to 20%. We trace these failures to the data: missing legitimate subdomains, country priors from the phishing feed, and labels that mark shared services such as `google.com` (782 rows) as phishing. Retraining with more realistic data reduces false alarms on real sites by a quarter to a half, consistently across splits, for about one point of in-dataset accuracy. But it fixes biases only where the added data contains counter-examples. We conclude that the limit is the data, not the model, and that a usable detector needs representative legitimate data and signals beyond the domain name. We also release a website that shows, for any link, what the model reads and which of our measured weaknesses apply.

---

## 1. Introduction

Phishing websites imitate legitimate ones to steal passwords and payment details. A detector that judges a link from its text alone is attractive: it is fast, needs no page download, and can run before the user clicks. Public datasets make such detectors easy to train, and PhiUSIIL (Prasad and Chandra, 2024) has become a popular benchmark, with reported accuracies from 99.79% to 99.99%.

Near-perfect scores on a security task should prompt a question: what has the model learned? Machine learning in security is prone to spurious correlations, sampling bias and data snooping (Arp et al., 2022). A model can learn how a dataset was assembled instead of the phenomenon it is meant to detect, and score perfectly while being useless in practice.

This project set out to build a phishing URL detector. It turned into a study of what such detectors learn from this dataset. Our contributions:

1. **A careful reproduction** of the published results under a stricter protocol (Section 3).
2. **A shortcut audit** showing why the scores are near-perfect, and a shortcut-reduced task, domain only, giving a realistic URL-only number (Section 4).
3. **Character-level deep models and a hybrid model** evaluated on that task with statistical tests (Section 5).
4. **Faithfulness-checked explanations** (Section 6).
5. **Out-of-distribution and adversarial tests** on real websites, with the causes of the failures measured (Section 7).
6. **A data-centric fix**, tested on sites and phishing never seen in training (Section 8), and **five further checks** on labels, calibration, thresholds, ordinary websites and allowlists (Section 9).
7. **A website** that makes the model's behaviour and limits visible for any link (Section 10).

---

## 2. Data

### 2.1 PhiUSIIL
PhiUSIIL (UCI dataset 967) holds 235,795 URLs, each labelled phishing or legitimate, plus 54 columns computed by its authors. Fifty of those columns are numeric. We sorted them by origin (`src/phishguard/columns.py`):

| Group | Columns | Example |
|---|---|---|
| URL | 19 | `URLLength`, `IsHTTPS` |
| Page (needs the downloaded HTML) | 28 | `LineOfCode`, `NoOfImage` |
| Statistic | 3 | `URLSimilarityIndex` |

An application that receives a link from a user can compute only the URL group, and only from the URL string.

### 2.2 Exploration and cleaning
All loading and cleaning is in `load_clean()` (`src/phishguard/data.py`), so every notebook uses identical rows.

| Step | Finding | Action |
|---|---|---|
| Completeness | A shared copy of the file was truncated (196,403 rows) | The loader checks the shape (235,795 × 55) and stops otherwise |
| Label direction | `label = 1` means legitimate | New target `is_phishing` (1 = phishing), so precision and recall describe phishing detection |
| Trailing `/` | 36.5% of phishing URLs end in `/`, 0% of legitimate | Removed, so it can't act as a shortcut |
| Conflicting labels | `https://www.education.gouv.fr` appears with both labels | Both rows dropped |
| Duplicates | 1,589 repeated URLs after normalisation | Dropped, so no URL is in both train and test |

**Result:** 234,204 rows: 134,849 legitimate (57.6%) and 99,355 phishing (42.4%).

### 2.3 External data (testing and Milestone 7b only)
| Source | Use |
|---|---|
| Chrome UX Report top 10k origins (2026-10) | popular real websites, including subdomains |
| Tranco list GQ3QK (Le Pochat et al., 2019): top 20k, top 100k, and 20,000 sampled from ranks 100k–1M | popular and less popular real websites; an allowlist |
| PhishTank verified online phishing (snapshot 2026-11-19) | phishing reported in 2025–26 |
| Phishing.Database active phishing domains (snapshot 2026-11-19) | additional phishing for training (7b) |

All external files are frozen snapshots with SHA-256 checksums (`DataSets/external/README.md`).

---

## 3. Evaluation protocol

### 3.1 Splitting by site owner
Attackers create many URLs under one domain. With a stratified random split, **39%** of phishing test URLs had a "sibling" from the same owner in training, so a model could recognise the site instead of detecting phishing (Pendlebury et al., 2019 make the same point for malware). We therefore group URLs by **site owner**: the registered domain under the Public Suffix List (`tldextract` 5.4.0, pinned), with hosting-platform customers (`x.web.app`) as separate owners. Owners are shuffled per class and assigned 70/15/15 to train, validation and test. For seed 42 that gives 164,045 / 35,029 / 35,130 rows. A test checks that no owner appears in two parts, and a fingerprint test guards the split against accidental change.

One bug mattered here. Our first host parser read `http://www.paypal.com:911@evil.top/…` as belonging to `paypal.com`. Browsers go to the host after `@`, a classic phishing trick. We switched to Python's `urlsplit`, added tests, and re-made the split once, on purpose (decision D11).

### 3.2 One routine for every model
`experiment.run()` applies the same steps to every model (D6):
1. Train each hyperparameter setting on train; keep the one with the lowest **validation log-loss**.
2. Choose the decision threshold with the fewest **validation** errors.
3. Score **test once**.
4. Repeat on **five splits** (seeds 42, 0, 1, 2, 3). Report mean ± standard deviation, plus a 95% confidence interval for seed 42 that resamples whole owners (a bootstrap).

Models are compared with **McNemar's test** on the links where they disagree, and by how many of the five splits each one wins. A senior review after Milestone 3 introduced the five-split reporting. Our first domain-only result (88.6%) had come from a favourable single split; the five-split mean is 86.3 ± 0.9%.

---

## 4. Baselines and the shortcut

### 4.1 Reproducing the published results (Milestone 2)
| Model | Input | Accuracy (5 splits) |
|---|---|---|
| Logistic Regression | all 50 columns | 99.99 ± 0.00% |
| Random Forest (300 trees) | all 50 columns | 100.00 ± 0.00% |
| XGBoost | all 50 columns | 100.00 ± 0.00% |
| XGBoost | 40 features computed from the URL string | 99.64 ± 0.03% |
| Character 1–4-gram TF-IDF + Logistic Regression | raw URL | 99.69 ± 0.05% |
| Log-odds average of the two above | raw URL | 99.70 ± 0.03% |

With 0–6 errors out of 35,130 test URLs, the all-column models are indistinguishable from perfect: even zero errors only bounds accuracy above about 99.99% (the rule of three). The URL-only models match the best published URL-only results (Ahamed et al., 2026: XGBoost 99.74%, host-disjoint split). The character-based models beat the feature-based ones significantly but slightly (McNemar p < 0.05 for each pair, 20–30 links). The ties are within groups.

Reading the n-gram weights already showed a problem. The strongest phishing chunks were `p://`, `tp:` and `ttp:`, that is, `http://` without an `s`. The strongest legitimate chunks were `www` and `//ww`. The model had learned how URLs *start*.

### 4.2 Why the scores are so high (Milestone 3)
Simple rules with no learning, scored on the test split:

| Rule | Accuracy |
|---|---|
| `URLSimilarityIndex < 100` → phishing | **99.66%** |
| URL doesn't start with `https://www.` → phishing | **99.08%** |
| `IsHTTPS = 0` → phishing | 79.43% |
| URL has a path → phishing | 72.51% |

**Every** legitimate URL in PhiUSIIL is a bare `https://www.` homepage. Only 2.4% of phishing URLs look like that. XGBoost on any single column group alone scores about 99.7% (URL columns 99.74%, page 99.71%, statistic 99.66%). We also found two leaks hidden inside the URL columns: the HTTPS prefix can be recovered from `URLLength` minus the counted characters, and the removed trailing slash survives in `URLLength`. Independent, non-peer-reviewed audits of the dataset report the same shortcuts (docs/references.md).

### 4.3 A shortcut-reduced task
We define four **views** of each URL (`URL_VIEWS`, D10) and report every URL model on them:

| View | Example | n-grams | XGBoost (40 features) |
|---|---|---|---|
| Raw URL | `https://www.a.b.com/x` | 99.70% | 99.64% |
| No scheme or `www.` | `a.b.com/x` | 89.18% | 85.95% |
| **Domain only** | `a.b.com` | **86.27 ± 0.89%** | 81.43 ± 1.15% |
| Registered domain | `b.com` | 82.49% | 72.82% |

The path still leaks the collection pattern, so **domain only** is our main task from here on. We call it *shortcut-reduced*, not "honest": the domain still carries a collection difference. Only 6.2% of legitimate domains have a subdomain, a hosting platform, an IP address, a digit or `xn--`, against 56.9% of phishing domains, and a no-learning rule on that alone scores 78%. An independent host-only model reports a similar ROC-AUC (0.919) to ours (≈ 0.92).

---

## 5. Deep and hybrid models

### 5.1 Character-level networks (Milestone 4)
- **Char-CNN** (in the spirit of URLNet, Le et al., 2018): each character becomes a learned 32-dimensional embedding. Convolution filters of widths 3–6 (128 each) slide over the domain, with padding masked; max-pooling keeps each filter's strongest match (512 values), and a dense layer outputs P(phishing).
- **BiLSTM:** reads the characters in both directions.
- **Training:** PyTorch with Adam, early stopping on a held-out 10% of *training* owners (so validation stays untouched), dropout tuned in {0.3, 0.5}, length-bucketed batches, on the Apple GPU (MPS).

| Model | Raw URL | Domain only | Registered domain |
|---|---|---|---|
| Character n-grams | 99.70% | 86.27% | **82.49%** |
| Char-CNN | 99.68% | **86.58 ± 0.92%** | 80.85% |
| BiLSTM | 99.68% | 85.55 ± 1.35% | 80.95% |

On raw URLs every model hits the ceiling. On the domain, the CNN is higher on 4 of 5 splits (seed 42: McNemar p = 0.0001), but its ROC-AUC equals the n-gram model's (0.9165 vs 0.9162). The gain comes from fewer false alarms at the threshold (3.3% vs 4.3%), not better ranking. On the registered domain, the simpler model wins.

### 5.2 Hybrid model (Milestone 5)
The **hybrid network** passes the domain through the char-CNN (512 values) and through the 40 handcrafted features, which are log-transformed and standardised on training rows (a 64-unit layer). The two are concatenated and passed through a dense head. Both branches are trained **jointly** (early fusion). We compare it with **late fusion**: a log-odds average of a separately trained CNN and XGBoost.

| Domain only, 5 splits | Accuracy |
|---|---|
| XGBoost, 40 features | 81.4 ± 1.1% |
| BiLSTM | 85.6 ± 1.3% |
| Character n-grams | 86.3 ± 0.9% |
| Char-CNN | 86.6 ± 0.9% |
| **Hybrid (joint)** | **86.72 ± 0.99%** |

The hybrid beats the n-gram model on 4 of 5 splits (+0.45 points; seed 42 p < 0.0001) and the CNN on 4 of 5 (+0.14; p = 0.027). The gain is smaller than the split-to-split spread: small but consistent. Late fusion was *worse* than the CNN alone, so training the parts together is what makes the combination work. On registered domains, the n-gram model remains best (82.49% vs 82.01%).

---

## 6. Explainability (Milestone 6)

- **TreeSHAP** for XGBoost gives each feature its exact share of a prediction. We verify that the shares add up to the model output (largest gap 2·10⁻⁵). On raw URLs, the top features are `is_https` (mean |SHAP| 4.18) and `has_www` (2.51): the shortcut, seen from inside the model.
- **Occlusion** for the hybrid: blank one character (or reset one standardised feature to its mean) and measure the change in the raw log-odds. We explain log-odds rather than probabilities because a probability near 1 barely moves even when an input matters. The hybrid's feature branch relies mostly on *number of subdomains* and *on a hosting platform*. Its per-suffix scores agree with the n-gram weights (Spearman ρ = 0.89).
- **Faithfulness (deletion test):** on phishing domains the hybrid caught, hiding the five characters the explanation marks as most phishing-like flips the verdict for **20%** of them; hiding five random characters flips **2.8%**. The explanations point at what really drives the prediction.

The explanations also exposed the first real-world warning sign: `accounts.google.com` is scored 0.999 phishing.

---

## 7. Robustness and distribution shift (Milestone 7)

We tested the saved seed-42 models **without retraining** (`src/phishguard/robustness.py`, each edit unit-tested).

**Attacks on phishing URLs:**

| Change | Model | Caught before → after |
|---|---|---|
| `http` → `https` | raw-URL n-grams | 100% → 35.5% |
| rewrite as `https://www.<host>` | raw-URL n-grams | 100% → 17.8% |
| every cheap domain edit (own `.com`, no subdomain, no digits/hyphens, look-alike digits → letters) | hybrid | 86% → 20% |
| same | n-grams | 83% → 32% |

The domain-only models are immune to the first two by construction, but domain edits evade them.

**Legitimate sites:** adding `mail.` to PhiUSIIL's legitimate test domains raises the hybrid's false-alarm rate from 3.3% to 89%.

**Popular real websites outside PhiUSIIL**, every owner seen in PhiUSIIL removed:

| | Hybrid | n-grams |
|---|---|---|
| CrUX plain domains (5,975) | 15% | 22% |
| CrUX with a subdomain (2,584) | **81%** | 52% |
| Tranco top domains (16,840) | 19% | 26% |

**Causes:**
1. PhiUSIIL's legitimate side has almost no subdomains, so "has a subdomain" became evidence of phishing.
2. The phishing feed over-represents some countries: 79% of `.ru` training rows are phishing, and 37% of popular `.ru` sites are flagged (`.ir` 34%, `.in` 33%; `.org` and `.de` 0%).
3. The labels mark shared services as phishing (Section 9).

No model is robust across the board: n-grams cope better with subdomains and edits, the hybrid with plain domains.

---

## 8. Does better data fix it? (Milestone 7b)

If the data causes the failures, better data should reduce them. We tested this directly (`src/phishguard/datafix.py`, D18).

**Training additions:**
- half of the Tranco top 20k as legitimate (a fixed, owner-hashed half);
- copies of 25% of legitimate training domains with prefixes such as `app.`, `docs.` and `help.`, chosen **disjoint** from the prefixes we test with;
- 25,000 Phishing.Database domains, one per owner;
- copies of 25% of phishing training domains with one Milestone 7 edit.

Each addition is split 85/15 into train and validation by owner.

**Tests:** PhiUSIIL's test split; CrUX; the *other* Tranco half; PhishTank phishing submitted from 2025 on (7,518 domains); and the Milestone 7 attacks. **No test site shares an owner with any training data** (checked: 0 overlap).

Same protocol, five splits. The n-gram model ran on a laptop CPU (≈ 8 min). The hybrid ran on the lab's NVIDIA H100 (≈ 30 s per model).

| Mean of 5 splits, before → after | Hybrid | n-grams |
|---|---|---|
| PhiUSIIL accuracy | 86.8 → 85.7% | 86.3 → 85.7% |
| False alarms, popular sites with a subdomain | **76.8 → 62.8%** (5/5) | **53.4 → 38.7%** (5/5) |
| False alarms, Tranco test half | **18.0 → 9.8%** (5/5) | **25.4 → 15.7%** (5/5) |
| False alarms, popular plain domains | 15.8 → 12.0% (5/5) | 22.2 → 17.2% (4/5) |
| New 2025–26 phishing caught | 81.7 → 81.4% | 82.1 → 81.3% |
| Edited phishing caught | **19.9 → 27.4%** (5/5) | **30.6 → 38.7%** (5/5) |
| False alarms, legitimate + `mail.` | **86.4 → 92.2%** (worse, 5/5) | 67.1 → 65.8% |

"(5/5)" means the change went the same way on every split.

Better data consistently reduces real-world false alarms by a quarter to a half and evasion by edits, for about one point of in-dataset accuracy, with no loss on new phishing. The `mail.` result went the other way, and the reason is in the data. In the improved training set, subdomains starting with `mail.` appear 597 times as phishing and once as legitimate. The added phishing feed brought more of them, and our legitimate prefixes deliberately excluded `mail.`. **Adding data removes a bias only where the new data contains counter-examples.**

---

## 9. Further checks (D19)

1. **Label audit.** Of 68 popular owners (Tranco top 20k) with at least 20 PhiUSIIL rows, **44 are labelled mostly phishing, 6,932 rows in all**: file hosting (`ipfs.io`, 1,441), Google Docs and Sites (`google.com`, 782, all phishing, 7 of them on `accounts.google.com`), website builders (`godaddysites.com`, `weebly.com`), cloud storage (`windows.net`, `aliyuncs.com`) and shorteners (`bit.ly`, `tinyurl.com`). Attackers host pages on these services. A domain-only model cannot separate honest and phishing pages there. This is why the real `google.com` scores higher than the fake `g0ogle.com` (81.5% vs 70.4%), and why `goog1e.com` and `paypa1.com` pass the hybrid: the models never learned what a brand is.
2. **Calibration.** On PhiUSIIL's test set, the expected calibration error is about 0.02 for both domain-only models. On popular legitimate sites with a subdomain, the hybrid flags 80%, and 77% of those wrong flags have probability ≥ 0.9. **Calibration holds only under the training distribution.**
3. **Strict thresholds.** Choosing the threshold on validation for at most 1% false alarms, the models catch 64% (hybrid) and 67% (n-grams) of test phishing; for at most 0.1%, 51% and 54%. At realistic base rates this matters. At a 0.1% phishing rate, our best raw-URL model's precision would be 64.7% despite 99.7% accuracy (Whittaker et al., 2010 make the same argument).
4. **Ordinary websites.** On 19,321 sites from Tranco ranks 100k–1M, false alarms are 18.3% (hybrid) and 23.9% (n-grams). The 7b-retrained n-grams reach 23.2%: popular-site data does not fix ordinary sites.
5. **Allowlist.** Never flagging owners in the Tranco top 100k removes false alarms on popular sites (79.8% → 0.1%, a partly circular test). It leaves ordinary sites unchanged (18.3%) and lowers new phishing caught from 82.1% to 77.3%, because 5.1% of new phishing sits on top-100k owners.

---

## 10. System

**Architecture.** Shared logic lives in `src/phishguard/` (data, split, URL parsing, features, models, explanations, robustness, data fixes, audits). Notebooks 01–13 only call it and keep their outputs. Every model writes a JSON result to `results/`, and the README's results table and the website's charts are generated from those files; a test fails if the README drifts.

**Website (Milestone 8, D16).** `phishguard.web` (FastAPI, served by uvicorn on 127.0.0.1) with a hand-written HTML/CSS/JavaScript page. For any link, it:
- crosses out the parts the model ignores;
- shades each character of the domain by its occlusion score;
- shows the verdicts of the hybrid and the n-gram model with their thresholds, and the features that moved the hybrid;
- lists warnings that apply to this link, each with a measured number: the owner is in the training data, the link has a subdomain, the suffix had a lopsided phishing share in training, or the two models disagree.

A separate **look-alike rule** (D17), clearly labelled as a rule, compares the name with the top 1,000 Tranco sites. It catches only 1.9% of PhiUSIIL phishing, which contains few look-alikes, and fires on 1.6–2.8% of popular sites. The page's "What we found" section tells the story above with numbers read from the result files. The site is deliberately **not hosted publicly**: every screen says it is a course project, not a safety tool.

**Engineering practice.**
- 117 automated tests: parsing, split, features, models, explanations, edits, data fixes, audits, website API.
- Pinned dependencies (`requirements.lock`, Python 3.12) and fixed seeds.
- A decision log (D1–D19) recording every choice with its evidence, and plain-language guides with viva questions for every milestone.
- Two cross-platform issues were fixed: PyTorch and XGBoost load different OpenMP runtimes on macOS (resolved by limiting OpenMP threads), and the deep models select CUDA, then MPS, then CPU automatically, so the same code ran on a laptop and on the lab GPU.

---

## 11. Discussion

**What the numbers mean.** On PhiUSIIL, near-perfect accuracy is achievable without learning anything about phishing. With the collection shortcut removed, a URL-only model reaches about 86–87%, and architecture choice moves that by less than a point. The gap between the 99.9% reported in the literature and the behaviour we measured on real websites is not a modelling problem: the dataset's legitimate class does not resemble legitimate traffic, and some of its phishing labels describe hosting services rather than sites.

**Trade-offs we chose.**
- *In-dataset accuracy vs real-world behaviour:* the 7b data costs about one point on PhiUSIIL and cuts real-site false alarms by a quarter to a half. We prefer it.
- *Domain only vs full URL:* less information, but immune to the scheme and `www.` shortcut and to the HTTPS attack.
- *Hybrid vs n-grams:* the hybrid is slightly more accurate and has fewer false alarms on plain domains. The n-gram model is faster, transparent, and copes better with subdomains and edits.

**What a usable detector would need.**
- Legitimate training data drawn from real browsing, including inner pages, subdomains and ordinary sites, collected the same way and at the same time as the phishing.
- Explicit counter-examples for each known bias.
- Signals beyond the domain, such as page content, domain age and certificate data, at least for shared hosting.
- Thresholds set for very low false-alarm rates.
- Regular retraining on fresh feeds.

**Limitations.**
- One training dataset, whose labels we take as given except where audited.
- Only the domain is read.
- Our added legitimate data and most legitimate test sets are popular sites.
- Hosting platforms missing from the Public Suffix List are treated as single owners (e.g. `ipfs.io`), which makes a few edits unrealistic.
- External feeds are single-day snapshots.
- The audits we cite in support are not peer-reviewed; our claims rest on our own measurements.

---

## 12. Conclusion

We reproduced PhiUSIIL's published 99.9%+ accuracy and showed that it comes from how the dataset was collected. The best shortcut-reduced URL-only model, a jointly trained hybrid of a character CNN and handcrafted features, reaches 86.7%, but fails on real websites: up to 81% false alarms on popular sites with subdomains, 18% on ordinary sites, and easy evasion. The causes are measurable properties of the data. Retraining with more realistic data reduces these failures consistently, but only where the new data provides counter-examples. A phishing detector trained on this dataset learns the dataset. Building one that works requires data that looks like the web it will be used on.

---

## References

- A. Prasad, S. Chandra. PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning. *Computers & Security* 136 (2024) 103545. Dataset: UCI Machine Learning Repository, id 967.
- T. Ahamed et al. An integrated evaluation protocol for adversarial robustness, generalization, and explanation stability in URL-based phishing detection. *Frontiers in Computer Science* 8 (2026). doi:10.3389/fcomp.2026.1834407.
- Bao et al. *Computers, Materials & Continua* 87(2), 2026 (Random Forest on PhiUSIIL, 99.99%).
- D. Arp et al. Dos and Don'ts of Machine Learning in Computer Security. *USENIX Security* 2022.
- F. Pendlebury et al. TESSERACT: Eliminating Experimental Bias in Malware Classification. *USENIX Security* 2019.
- C. Whittaker, B. Ryner, M. Nazif. Large-Scale Automatic Classification of Phishing Pages. *NDSS* 2010.
- H. Le et al. URLNet: Learning a URL Representation with Deep Learning for Malicious URL Detection. arXiv:1802.03162, 2018.
- K. Sabir et al. An Evasion Attack against ML-based Phishing URL Detectors (URLBUG). arXiv:2005.08454.
- V. Le Pochat et al. Tranco: A Research-Oriented Top Sites Ranking Hardened Against Manipulation. *NDSS* 2019.
- Google. Chrome UX Report (CrUX) top origins.
- PhishTank (phishtank.org); Phishing.Database (github.com/Phishing-Database/Phishing.Database); OpenPhish (openphish.com).
- Independent, non-peer-reviewed audits of PhiUSIIL (GitHub, Hugging Face, SSRN), listed with their findings in `docs/references.md`.

---

## Appendix A · Reproducing the results

```bash
uv venv --python 3.12 .venv
uv pip sync --python .venv requirements.lock
uv pip install --python .venv --no-deps -e .
.venv/bin/pytest                                  # 117 tests
# notebooks 01–13 in the order of notebooks/readme.md (≈ 4–5 h on a laptop; outputs are saved)
.venv/bin/python -m phishguard.datafix --model ngram     # Milestone 7b, CPU
.venv/bin/python -m phishguard.datafix --model hybrid    # Milestone 7b, GPU recommended
.venv/bin/python -m phishguard.web                       # website at http://127.0.0.1:8000
```

## Appendix B · Where to find each result

| Section | Notebook | Decision | Results |
|---|---|---|---|
| 2 Data | 01, 01b | D1–D5, D11 | — |
| 4.1 Baselines | 02–05 | D6–D8 | `results/m2/` |
| 4.2–4.3 Shortcuts | 06, 07 | D9, D10 | `results/m3_columns/`, `results/m3_views/` |
| 5 Deep and hybrid | 08, 09 | D12, D13 | `results/m4_deep/`, `results/m5_hybrid/` |
| 6 Explanations | 10 | D14 | — |
| 7 Robustness | 11 | D15 | `models/site_numbers.json` |
| 8 Better data | 12 | D18 | `results/m7b/` |
| 9 Further checks | 13 | D19 | — |
| 10 Website | — | D16, D17 | `models/` |
