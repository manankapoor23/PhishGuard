<!--
Source of the course report (docs/report/PhishGuard_Course_Report.pdf), in the
chapter format of the course's "Machine Learning Project Report Format".
Build: uv run --no-project --with mistune --with pypdf python docs/report/make_report.py
Conventions read by make_report.py:
  "# Chapter N: Title" starts a chapter on a new page; "## N.M Title" is a section.
  "Table: caption" on the line before a table numbers and captions it.
  "![caption](figures/x.png)" becomes a numbered figure with that caption.
-->

# Abstract

Phishing websites copy real ones to steal passwords and payment details. Detecting them from the link alone is fast and safe, and public datasets such as PhiUSIIL report accuracies of 99.8–99.99%. This project set out to build such a detector and to understand what it learns. We split the data by website owner, tuned every model on validation data and repeated every experiment on five splits. Under this protocol we reproduced the published results (99.99–100%). We then showed that they come from a shortcut: every legitimate link in the dataset is a bare `https://www.` homepage, and a one-line rule with no learning scores 99.08%. Using only the website name, the realistic accuracy is about 86–87%. A hybrid network that combines a character-level CNN with 40 handcrafted features is best (86.72 ± 0.99%), but only by half a point. Tested on real websites outside the dataset, the models wrongly flag 81% of popular sites with a subdomain and about one in five ordinary sites, and cheap edits evade them. Retraining with more realistic data reduces these failures but does not remove them. We conclude that a model trained on this dataset learns the dataset rather than phishing.

# Chapter 1: Introduction

## 1.1 Background and Overview of the Project

Phishing is one of the most common forms of online fraud. An attacker builds a website that looks like a bank, an email provider or a shop, and sends people a link to it. Victims who type their password or card number into the fake page hand it to the attacker.

Browsers, email services and security tools try to warn users before they open such a link. One way is a **blocklist** of known phishing addresses, but new phishing sites appear every day and live for only hours, so lists are always behind. Machine learning offers a second way: learn what phishing links look like from examples, and judge new links the model has never seen.

Judging a link from its **text alone** (its URL) is attractive. It needs no page download, so it is fast and cannot expose the user to the page. Many research papers do this with public datasets. One of the most popular recent ones is **PhiUSIIL** [1], on which published models report 99.8–99.99% accuracy [1], [2].

**PhishGuard** is our machine learning course project. We started by building a URL-based phishing detector on PhiUSIIL. Along the way the project became a careful study of *what such a detector actually learns*. It covers classical models, deep learning, a hybrid model, explanations, tests on real websites, an attempt to fix the data, and a small website that shows the model's reasoning for any link.

## 1.2 Problem Statement

Given a URL, decide whether it leads to a phishing website or a legitimate one, using only the text of the URL.

Near-perfect published scores raise a second question: **do these scores measure phishing detection, or something else about the dataset?** A model can score highly by learning how a dataset was assembled rather than the property it is meant to detect. This is a known pitfall of machine learning in security [4]. So our problem has two parts:
1. build and fairly evaluate URL-based phishing classifiers on PhiUSIIL;
2. find out what those classifiers rely on, and whether they work on websites outside the dataset.

## 1.3 Objectives of the Project

1. Prepare the PhiUSIIL data carefully: clean it and split it so that no website appears in both training and testing.
2. Reproduce the published accuracy with standard models, under a strict and repeatable evaluation protocol.
3. Build models that use only the URL, since that is all a real application receives.
4. Find out why the scores are so high, and define an honest version of the task.
5. Compare classical models, character-level deep learning models and a hybrid model on that task, using statistical tests.
6. Explain what the models look at, and check that the explanations are faithful.
7. Test the models on real websites and on attacker edits they were not trained on.
8. Test whether better training data fixes the failures.
9. Build a website that shows the model's reasoning and its known weaknesses for any link.

## 1.4 Scope and Applications

**In scope:** URL-only classification of phishing vs legitimate links; the PhiUSIIL dataset for training; public lists of real websites and public phishing feeds for testing; models from logistic regression to neural networks; explanations; robustness tests; a demonstration website.

**Out of scope:** downloading or analysing web page content, email text, or images; collecting new labelled data at scale; deploying a public service.

**Applications:** URL classifiers like these are used in browser warnings, email filters and link scanners. Our findings apply to anyone who trains or evaluates such a classifier on public datasets. They show how to check whether a high score will hold up in practice. The demonstration website is a teaching tool, not a safety tool.

# Chapter 2: Literature Review

## 2.1 Overview of Existing Approaches

Phishing detection approaches fall into four broad groups.

1. **Blocklists.** Services such as PhishTank and Google Safe Browsing keep lists of known phishing URLs. They are precise but always one step behind new sites.
2. **Rule-based heuristics.** Hand-written rules flag suspicious signs: an IP address instead of a name, an `@` in the URL, very long URLs, many subdomains, or words like "login" and "verify".
3. **Feature-based machine learning.** Researchers compute features from the URL, the web page (HTML, forms, links) or external sources (domain age, search engine rank), and train classifiers such as logistic regression, random forests or gradient boosting. Whittaker et al. [6] built Google's large-scale classifier this way, combining URL, page and hosting features.
4. **Deep learning on the raw URL.** Instead of hand-made features, a neural network reads the URL character by character. URLNet [7] uses convolutional neural networks on characters and words of the URL; recurrent networks such as LSTMs are also used.

## 2.2 Review of Relevant Research Papers / Existing Solutions

Table: Published work most relevant to this project.

| Work | Approach | Reported result | Evaluation |
|---|---|---|---|
| Prasad and Chandra, 2024 [1] (PhiUSIIL) | URL and page features, a similarity index, incremental learning | 99.79% accuracy | Split not described in the abstract |
| Bao et al., 2026 [2] | Random Forest on all PhiUSIIL columns | 99.99% | Random 80/20 split |
| Ahamed et al., 2026 [3] | LR, XGBoost, CharCNN, BERT on PhiUSIIL URLs; robustness and explanation tests | URL only: XGBoost 99.74%, CharCNN 99.81% | Host-disjoint 70/15/15 split |
| Le et al., 2018 [7] (URLNet) | Character and word CNN on URLs | Strong results on large URL sets | — |
| Sabir et al. (URLBUG) [8] | Evasion attacks that edit phishing URLs | Large drops in detection | — |
| Arp et al., 2022 [4] | Survey of pitfalls in security ML | Sampling bias, shortcuts, base-rate fallacy | — |
| Pendlebury et al., 2019 [5] (TESSERACT) | Evaluation bias in malware detection | Related samples must not cross the train/test split | — |

PhiUSIIL [1] contains 235,795 URLs with 54 columns the authors computed: some from the URL, some from the downloaded page, and a "URL similarity index" that compares a URL with a list of known legitimate sites. Later work reports near-perfect accuracy on it [2], [3].

Several independent, non-peer-reviewed audits of PhiUSIIL (on GitHub, Hugging Face and SSRN) report that legitimate URLs all share one format, that some columns almost contain the label, and that models trained on it misfire on real sites. A Hugging Face model card, for example, notes that `accounts.google.com/signin` is scored as phishing. We list these in our repository and use them only as supporting evidence.

## 2.3 Limitations of Existing Approaches

1. **Random splits leak information.** Phishing campaigns create many URLs under one domain. If URLs are split at random, the same website appears in training and testing, and the model can recognise the site instead of detecting phishing [5].
2. **Shortcuts in the data.** If one class was collected differently from the other, a model can learn the collection method. Near-perfect scores are a warning sign, not proof of quality [4].
3. **Little testing outside the dataset.** Most papers report accuracy on a held-out part of the same dataset. Few test on real websites from other sources, where the data looks different (*distribution shift*).
4. **Accuracy on balanced data hides real-world cost.** In real browsing only a small fraction of links are phishing, so even a small false-alarm rate produces many wrong warnings [6].
5. **Single splits and no significance tests.** Small differences between models are often reported as improvements without checking whether they are larger than split-to-split noise.

This project addresses each of these points.

# Chapter 3: Dataset Description and Preprocessing

## 3.1 Dataset Source and Description

The main dataset is **PhiUSIIL** (UCI Machine Learning Repository, dataset 967) [1]. Each row is one URL with a label (phishing or legitimate) and 54 computed columns. The raw file has 235,795 rows and 55 columns (with the label).

For testing outside PhiUSIIL, and for the data fix in Section 6.2, we also used the sources in Table 3.1. Each was downloaded once and frozen with a checksum, so results can be repeated.

Table: External data used for testing and for retraining.

| Source | What it contains | Used for |
|---|---|---|
| Chrome UX Report (CrUX) top 10,000 origins | The most-visited websites in Chrome, including subdomains | Testing false alarms on popular sites |
| Tranco list GQ3QK [9] | A research ranking of the top 1 million websites | Popular sites (top 20k), an allowlist (top 100k), less popular sites (ranks 100k–1M); half of the top 20k for retraining |
| PhishTank (snapshot of 19 Nov 2026) | 43,703 verified phishing URLs, with dates | Testing on phishing reported in 2025–26 |
| Phishing.Database (snapshot of 19 Nov 2026) | 392,178 active phishing domains | Extra phishing for retraining |

## 3.2 Dataset Features and Characteristics

PhiUSIIL's 50 numeric columns come from three places (Table 3.2). A link typed by a user only allows the first group, and only if we compute it from the URL ourselves.

Table: Origin of PhiUSIIL's 50 numeric columns.

| Group | Columns | Examples |
|---|---|---|
| URL | 19 | `URLLength`, `NoOfSubDomain`, `IsHTTPS` |
| Page (needs the downloaded HTML) | 28 | `LineOfCode`, `NoOfImage` |
| Statistic | 3 | `URLSimilarityIndex` |

We therefore also computed **40 features of our own from the URL text alone**, such as length, numbers of digits, hyphens and subdomains, whether the host is an IP address or a hosting platform, suspicious words, and character randomness (entropy). These are listed in our code (`features.py`).

After cleaning, the dataset is moderately balanced (Figure 3.1).

![Class balance after cleaning.](figures/fig_class_balance.png)

## 3.3 Data Preprocessing Techniques

All preprocessing is in one function, so every experiment uses identical rows (Table 3.3).

Table: Cleaning steps.

| Step | What we found | What we did |
|---|---|---|
| Completeness check | A shared copy of the file had been cut off (196,403 rows) | The loader checks for 235,795 × 55 and stops otherwise |
| Label direction | `label = 1` meant legitimate | Created `is_phishing` (1 = phishing), so precision and recall describe phishing detection |
| Trailing slash | 36.5% of phishing URLs ended in `/`, 0% of legitimate ones | Removed it, so it cannot act as a giveaway |
| Conflicting labels | One URL labelled both ways | Removed both rows |
| Duplicates | 1,589 repeated URLs after normalisation | Removed, so no URL is in both training and testing |

**Result: 234,204 URLs, 134,849 legitimate (57.6%) and 99,355 phishing (42.4%).**

**Splitting by website owner.** Attackers create many URLs on one website. With a random split, 39% of phishing test URLs had a "sibling" from the same website in training. We therefore group URLs by **site owner**, the registered domain (e.g. `example.co.uk` for `login.example.co.uk`), using the Public Suffix List. Whole owners are assigned to training (70%), validation (15%) or test (15%), separately for each class so every part has 42.4% phishing. For the main split (seed 42) that is 164,045 / 35,029 / 35,130 URLs. An automatic test checks that no owner appears in two parts.

**URL views.** To control what a model can see, we define four views of each URL: the raw URL; the URL without the scheme and `www.`; the **domain only** (the host name); and the registered domain only.

## 3.4 Exploratory Data Analysis (EDA) and Visualizations

**Feature distributions.** Phishing URLs are longer, contain more digits and have more subdomains than legitimate ones (Figure 3.2). On average, legitimate URLs are 15 characters long against 37 for phishing.

![Distribution of three URL features for legitimate and phishing links (top 1% of values clipped).](figures/fig_eda_features.png)

**The most important finding of the EDA** is shown in Figure 3.3. **Every** legitimate URL starts with `https://www.` and has nothing after the domain, while only 2.4% of phishing URLs look like that. The legitimate side of the dataset is a list of homepages. This collection difference turns out to drive almost all of the published accuracy (Chapter 6).

![Share of legitimate and phishing URLs with three properties of the URL's format.](figures/fig_eda_shortcut.png)

Other observations from the EDA:
- **Some owners are very large.** For example, `ipfs.io` has about 1,400 phishing URLs, so one split can be luckier than another. This is why every result is repeated on five splits.
- **105 owners (560 rows) have both labels:** usually a real site with one abused page.
- **Popular shared services are labelled phishing.** All 782 `google.com` rows (phishing pages hosted on Google Docs and Sites) and 44 popular hosting services and link shorteners in total are labelled almost entirely phishing (Section 6.4).

# Chapter 4: Proposed Methodology

## 4.1 Overall System Architecture / Workflow Diagram

Figure 4.1 shows the workflow. Data is cleaned and split by website owner, then audited for shortcuts. Models are trained and evaluated under one fixed protocol, explained, and finally tested on real websites and attacks. The data fix and the website build on the results.

![Workflow of the project, from raw data to the website.](figures/fig_workflow.png)

The code follows the same structure. All logic lives in a tested Python package (`src/phishguard/`), and numbered notebooks (01–13) call it and keep their outputs. Every model writes its results to a file, and all reported numbers are read from those files.

## 4.2 Machine Learning Algorithms Used

Table: Models used, and what each one sees.

| Model | Type | Input |
|---|---|---|
| Logistic Regression | Linear classifier | All 50 columns |
| Random Forest | Ensemble of decision trees | All 50 columns; our 40 URL features |
| XGBoost | Gradient-boosted trees | All 50 columns; our 40 URL features |
| Character n-grams + Logistic Regression | Linear model on text chunks | URL text (any view) |
| Char-CNN | Convolutional neural network | URL characters (any view) |
| BiLSTM | Recurrent neural network | URL characters (any view) |
| Hybrid network | CNN + feature network, trained jointly | URL characters and our 40 features |
| Log-odds average | Late fusion of CNN and XGBoost | URL characters and our 40 features |

## 4.3 Brief Explanation of Selected Algorithms

**Logistic Regression.** Gives each input a weight, adds up weight × value, and turns the total into a probability with the sigmoid function. Simple, fast and easy to interpret, which makes it a good first baseline.

**Random Forest.** Builds many decision trees, each a flowchart of yes/no questions, on random samples of rows and columns, and lets them vote. Robust and needs little tuning.

**XGBoost.** Also builds trees, but one after another: each new tree focuses on the mistakes of the previous ones (gradient boosting). It is usually the strongest model for tabular data.

**Character n-grams.** Splits a URL into every chunk of 1–4 characters (`paypa1.top` → `pay`, `pa1`, `.top`, …). Each chunk gets a TF-IDF score (high if it is frequent in this URL but rare overall), and logistic regression learns one weight per chunk.

**Char-CNN.** Each character becomes a learned vector of 32 numbers (an *embedding*). Convolution filters of widths 3–6 (128 of each) slide over the URL and respond to letter patterns, such as a digit inside a word. Max-pooling keeps each filter's strongest response, and a final layer outputs the probability of phishing.

**BiLSTM.** A recurrent network that reads the characters one at a time, in both directions, keeping a memory of what it has seen.

**Hybrid network.** Feeds the domain to a char-CNN (512 outputs) and, in parallel, the 40 handcrafted features (log-scaled and standardised) to a small dense layer (64 outputs). The two are joined and passed through a final dense network. Both parts are trained **together**, so each can learn what the other misses.

## 4.4 Model Training and Testing Strategy

Every model goes through the same routine:
1. **Tune:** train one model per hyperparameter setting on the training part, and keep the setting with the lowest *log-loss* on validation. Log-loss changes smoothly, so one lucky validation URL cannot decide the winner.
2. **Threshold:** a model outputs a probability, and the threshold turns it into a decision. We choose the threshold with the fewest validation errors.
3. **Test once:** score the test part a single time.
4. **Repeat on five splits** (seeds 42, 0, 1, 2, 3) and report the mean ± standard deviation.

To compare two models we use **McNemar's test**, which looks only at the URLs where they disagree, and count how many of the five splits each one wins. For the main split we also report a 95% confidence interval, computed by resampling whole website owners.

**Beyond the test split,** the saved models are tested without retraining on: popular real websites (CrUX, Tranco), less popular websites, phishing reported in 2025–26, and attacker-style edits to URLs (switching to `https`, moving to a `.com` name, removing subdomains, digits and hyphens).

# Chapter 5: Implementation

## 5.1 Tools, Technologies, and Libraries Used

Table: Tools and libraries.

| Purpose | Tools |
|---|---|
| Language and environment | Python 3.12, `uv` with a pinned lock file |
| Data handling | pandas, NumPy |
| Classical models and metrics | scikit-learn, XGBoost, SciPy |
| Deep learning | PyTorch (Apple GPU on a laptop; NVIDIA H100 GPU on the lab server) |
| URL parsing | Python `urllib`, `tldextract` 5.4.0 (Public Suffix List) |
| Explanations | SHAP (TreeSHAP), our own occlusion code |
| Notebooks and plots | Jupyter, Matplotlib, Seaborn |
| Website | FastAPI, uvicorn, HTML/CSS/JavaScript |
| Testing and version control | pytest (117 tests), Git and GitHub |

## 5.2 Implementation Steps

1. **Data loading and cleaning:** `load_clean()` checks the file, flips the label, normalises URLs, and removes conflicts and duplicates (notebook 01).
2. **Owner-based split:** `get_splits()` groups URLs by site owner and assigns them to train, validation and test (notebook 01b). We found and fixed a URL-parsing bug: our first parser read `http://www.paypal.com:911@evil.top/…` as a PayPal URL, though browsers go to `evil.top`. We switched to Python's standard URL parser and re-made the split once.
3. **Feature extraction:** `extract_features()` computes the 40 URL features.
4. **Baseline models** on all columns and on URL features (notebooks 02–05).
5. **Shortcut audit and URL views** (notebooks 06–07).
6. **Deep models and the hybrid** in PyTorch (notebooks 08–09).
7. **Explanations:** TreeSHAP and occlusion, with a deletion test (notebook 10).
8. **Robustness tests** on real websites and edited URLs (notebook 11).
9. **Data fix:** retraining with additional data on the lab GPU, and further checks (notebooks 12–13).
10. **Website:** a FastAPI server that loads the saved models, and a page that explains each prediction.

## 5.3 Model Training and Hyperparameter Settings

All settings in Table 5.2 were chosen on validation data, separately for each of the five splits.

Table: Hyperparameters searched (the chosen value differs per split and view).

| Model | Hyperparameters searched |
|---|---|
| Logistic Regression (all columns) | C ∈ {0.01, 0.1, 1, 10}; standardised inputs |
| Random Forest | 300 trees; max depth ∈ {none, 20 or 30}; min samples per leaf ∈ {1, 3} |
| XGBoost (all columns) | max depth ∈ {4, 6, 8}; trees ∈ {200, 500}; learning rate 0.1 |
| XGBoost (URL features) | max depth ∈ {6, 10}; min child weight ∈ {1, 5}; 500 trees; 80% row and column sampling |
| Character n-grams | n-gram length 1–3 or 1–4; regularisation C tuned on validation |
| Char-CNN / BiLSTM / Hybrid | dropout ∈ {0.3, 0.5}; Adam, learning rate 0.001; batch 256; up to 15 epochs, early stopping (patience 2) on 10% of training owners; URLs up to 200 characters |

**Early stopping** uses a slice of the *training* owners, never the validation part, so validation stays clean for tuning and thresholds. Neural networks trained on the laptop's Apple GPU; the final retraining experiment ran on the lab's NVIDIA H100, about 30 seconds per model.

## 5.4 Implementation Screenshots / Outputs

The website (Figure 5.1) accepts any link and shows:
- the parts the model ignores, crossed out;
- each character of the domain shaded by how much it pushed the score towards phishing (red) or legitimate (blue);
- the verdicts of two models with their thresholds;
- warnings when one of our measured weaknesses applies;
- the measured properties that moved the score most.

It is deliberately not hosted publicly, and every page says it is a course project, not a safety tool.

![The PhishGuard website checking Google's real sign-in page. Both models call it phishing; the warnings explain why.](figures/fig_website.png)

# Chapter 6: Results and Performance Evaluation

## 6.1 Performance Evaluation Metrics

Table: Evaluation metrics (phishing is the positive class).

| Metric | Meaning |
|---|---|
| Accuracy | Share of URLs classified correctly |
| Precision | Of the URLs flagged as phishing, the share that really are |
| Recall (phishing caught) | Of the real phishing URLs, the share flagged |
| F1 | Balance of precision and recall |
| ROC-AUC | How well the model ranks phishing above legitimate, whatever the threshold (1 = perfect, 0.5 = guessing) |
| False-alarm rate | Share of legitimate URLs wrongly flagged |
| 95% confidence interval | Range the true accuracy probably lies in |
| McNemar p-value | Whether two models really differ (p < 0.05) |
| Calibration error | Average gap between predicted probability and observed share of phishing |

## 6.2 Experimental Results

**Reproducing the published results.** With all 50 columns, all three classical models are near-perfect on every split (Table 6.2). From our 40 URL features or the URL's characters alone, the models reach 99.6–99.7%, in line with the best published URL-only results [3].

Table: First results (test accuracy, mean ± sd over 5 splits).

| Model | Input | Accuracy |
|---|---|---|
| Logistic Regression | All 50 columns | 99.99 ± 0.00% |
| Random Forest | All 50 columns | 100.00 ± 0.00% |
| XGBoost | All 50 columns | 100.00 ± 0.00% |
| XGBoost | Our 40 URL features | 99.64 ± 0.03% |
| Character n-grams | Raw URL | 99.69 ± 0.05% |

**The shortcut.** When even logistic regression is almost perfect, something is usually giving the answer away. Simple rules with no learning confirm it (Table 6.3).

Table: Accuracy of one-line rules on the test split (no machine learning).

| Rule | Accuracy |
|---|---|
| `URLSimilarityIndex` below 100 → phishing | 99.66% |
| URL does not start with `https://www.` → phishing | 99.08% |
| Not HTTPS → phishing | 79.43% |
| URL has a path → phishing | 72.51% |

The models had learned how the legitimate URLs were collected (Figure 3.3), not what phishing looks like. Reading the character model's weights shows the same thing: its strongest phishing signals are `p://` (that is, `http://` without the `s`), and its strongest legitimate signals are `www`.

**The honest task.** Removing the scheme, `www.` and the path, and keeping only the domain, lowers accuracy from 99.7% to about 86% (Figure 6.1). We use the domain-only view as our main, more realistic task.

![Accuracy as more of the URL's format is removed (mean ± sd over 5 splits).](figures/fig_views.png)

## 6.3 Comparison of Different Models

Table 6.4 and Figure 6.2 compare all models on the domain-only task.

Table: Models on the domain-only task (test accuracy, mean ± sd over 5 splits).

| Model | Accuracy | ROC-AUC |
|---|---|---|
| XGBoost, 40 features | 81.43 ± 1.15% | 0.847 |
| BiLSTM | 85.55 ± 1.35% | 0.909 |
| Character n-grams | 86.27 ± 0.89% | 0.916 |
| Char-CNN | 86.58 ± 0.92% | 0.917 |
| **Hybrid (CNN + features)** | **86.72 ± 0.99%** | **0.917** |

![Domain-only accuracy of the five models (error bars: standard deviation over 5 splits).](figures/fig_models.png)

- **The hybrid is best,** ahead of the n-gram model on 4 of 5 splits (+0.45 points, McNemar p < 0.0001 on the main split) and of the CNN on 4 of 5 (+0.14 points, p = 0.027).
- **The gain is small,** less than the variation between splits. The CNN's gain over n-grams comes from fewer false alarms (3.3% vs 4.3%) with the same ranking quality (equal ROC-AUC).
- **Combining a CNN and XGBoost by averaging (late fusion) was worse than the CNN alone,** so training the two parts together is what makes the hybrid work.
- **On the registered domain view,** the simpler n-gram model wins (82.49% vs 82.01% for the hybrid).

**Explanations.** TreeSHAP shows that on full URLs XGBoost relies most on `is_https` and `has_www`: the shortcut, seen from inside the model. For the hybrid, hiding the 5 characters its explanation calls most suspicious changes its decision for 20% of caught phishing domains, against 2.8% for 5 random characters. So the explanations point at what really drives the decisions.

## 6.4 Graphical Representation and Discussion of Results

**Testing on real websites.** We tested the saved models on about 25,000 popular real websites that are not in PhiUSIIL (Figure 6.3).

![Popular real websites wrongly flagged as phishing (none of them are in the dataset).](figures/fig_real_world.png)

The hybrid wrongly flags 81% of popular sites with a subdomain (like `mail.yahoo.com`) and 15–19% of plain ones. On 19,321 ordinary, less popular websites, the false-alarm rate is 18% (hybrid) and 24% (n-grams). The models are also easy to evade:
- switching a phishing URL from `http` to `https` drops the full-URL model from catching 100% to 35.5%;
- cheap edits to a phishing domain (moving to `.com`, removing subdomains, digits and hyphens) drop the hybrid from 86% to 20%.

**Why the models fail.** The causes are in the data:
1. Legitimate URLs in PhiUSIIL almost never have subdomains, so the model treats a subdomain as evidence of phishing.
2. The phishing feed over-represents some countries: 79% of `.ru` training URLs are phishing, and 37% of popular `.ru` websites are flagged.
3. Popular shared services are labelled phishing. Forty-four of them, including Google, Weebly, IPFS and bit.ly, are labelled almost entirely phishing, because attackers host pages on them. A model that reads only the domain cannot separate those pages from honest ones. This is why it scores the real `google.com` *higher* than the fake `g0ogle.com` (81.5% vs 70.4%): it has learned the letters "google", not what a brand is.

**Calibration.** On PhiUSIIL's own test data the probabilities are honest (Figure 6.4, average gap about 2 points). On real popular sites, 77% of the hybrid's wrong alarms come with a probability of 0.9 or more. A model can be well calibrated and still be confidently wrong on data unlike its training data.

![Calibration of the domain-only models on PhiUSIIL's test data (seed 42).](figures/fig_calibration.png)

**Strict thresholds.** A browser warning must almost never fire on a real website. If the threshold is chosen for at most 1 false alarm per 100 legitimate URLs, the models catch about two thirds of phishing; at 1 per 1,000, about half.

**Can better data fix it?** We retrained both models with more realistic data:
- half of the Tranco top 20,000 websites as legitimate;
- legitimate URLs with subdomains, using prefixes different from those we test with;
- 25,000 phishing domains from another feed;
- deliberately edited phishing.

The test websites share no owner with any training data, and the new phishing test set contains only phishing reported in 2025–26.

![Before and after retraining with better data (mean of 5 splits).](figures/fig_better_data.png)

Table: Effect of better training data on the hybrid (mean of 5 splits).

| Measure | Before | After |
|---|---|---|
| False alarms, popular sites with a subdomain | 76.8% | 62.8% |
| False alarms, Tranco test sites | 18.0% | 9.8% |
| Edited phishing caught | 19.9% | 27.4% |
| New 2025–26 phishing caught | 81.7% | 81.4% |
| Accuracy on PhiUSIIL | 86.8% | 85.7% |

Better data reduced false alarms on real websites by a quarter to a half, consistently on every split, for about one point of PhiUSIIL accuracy (Figure 6.5, Table 6.5). It is only a partial fix:
- false alarms are still far too high;
- ordinary websites barely improved, because the added legitimate sites were all popular ones;
- one bias became worse. URLs starting with `mail.` are 597 times phishing and once legitimate in the training data, and the added phishing contained more of them. Better data only fixes a bias where it contains counter-examples.

An **allowlist** of the 100,000 most popular websites removes false alarms on those sites, but does nothing for ordinary ones and lets through phishing hosted on popular services (phishing caught falls from 82% to 77%).

# Chapter 7: Conclusion and Future Scope

## 7.1 Summary of the Project

We built and evaluated URL-based phishing classifiers on the PhiUSIIL dataset, from logistic regression to a hybrid neural network, under a strict protocol: splits by website owner, tuning on validation only, five repeated splits and statistical tests. We explained the models, tested them on real websites and attacks, tried to fix their failures with better data, and built a website that shows how the model reaches its decision for any link.

## 7.2 Key Findings and Achievements

1. **The published 99.9% accuracy on PhiUSIIL is a shortcut.** It comes from how the legitimate URLs were collected: every one is a bare `https://www.` homepage, and a one-line rule scores 99.08%.
2. **From the domain alone, the realistic accuracy is about 86–87%.** The hybrid network is the best model at 86.72%, but by less than half a point. The choice of model matters much less than the data.
3. **The models fail on real websites:** up to 81% false alarms on popular sites with subdomains, about one in five on ordinary sites, and easy evasion. We measured the causes: missing legitimate subdomains, country bias in the phishing feed, and labels that mark shared services such as Google as phishing.
4. **Better data helps, but only where it contains counter-examples.** It cut false alarms by a quarter to a half for about one point of accuracy.
5. **Achievements in practice:**
   - a reproducible codebase with 117 automatic tests;
   - 13 documented notebooks;
   - a log of 19 design decisions with their evidence;
   - a demonstration website that makes the model's reasoning and limits visible.

## 7.3 Limitations of the Project

- One training dataset, whose labels we mostly take as given.
- Only the URL (mainly the domain) is used; page content, which would separate phishing pages on shared services, is not.
- The legitimate data added in the retraining experiment, and most legitimate test sets, are popular websites.
- Hosting services missing from the Public Suffix List are treated as one owner, which makes a few attacker edits unrealistic.
- External data are single-day snapshots, and the independent audits we cite are not peer-reviewed.

## 7.4 Future Scope and Improvements

1. **Representative legitimate data:** URLs from real browsing, including ordinary sites, subdomains and inner pages, collected the same way and at the same time as the phishing.
2. **Counter-examples for every known bias,** for example real legitimate `mail.` websites.
3. **Signals beyond the URL:** page content, domain age and certificate information, especially for phishing on shared services.
4. **Thresholds for real use,** set for very low false-alarm rates, as a browser warning requires.
5. **Regular retraining** on fresh phishing feeds, since phishing changes month by month.

# References

[1] A. Prasad and S. Chandra, "PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning," *Computers & Security*, vol. 136, Art. no. 103545, 2024. Dataset: UCI Machine Learning Repository, id 967.

[2] Bao et al., Random Forest phishing detection on PhiUSIIL, *Computers, Materials & Continua*, vol. 87, no. 2, 2026.

[3] T. Ahamed, S. C. Kakon, F. Al Farid, J. Uddin and H. B. A. Karim, "An integrated evaluation protocol for adversarial robustness, generalization, and explanation stability in URL-based phishing detection," *Frontiers in Computer Science*, vol. 8, 2026, doi: 10.3389/fcomp.2026.1834407.

[4] D. Arp et al., "Dos and don'ts of machine learning in computer security," in *Proc. USENIX Security Symposium*, 2022.

[5] F. Pendlebury et al., "TESSERACT: Eliminating experimental bias in malware classification across space and time," in *Proc. USENIX Security Symposium*, 2019.

[6] C. Whittaker, B. Ryner and M. Nazif, "Large-scale automatic classification of phishing pages," in *Proc. NDSS*, 2010.

[7] H. Le, Q. Pham, D. Sahoo and S. C. H. Hoi, "URLNet: Learning a URL representation with deep learning for malicious URL detection," arXiv:1802.03162, 2018.

[8] K. Sabir et al., "An evasion attack against ML-based phishing URL detectors," arXiv:2005.08454.

[9] V. Le Pochat, T. Van Goethem, S. Tajalizadehkhoob, M. Korczyński and W. Joosen, "Tranco: A research-oriented top sites ranking hardened against manipulation," in *Proc. NDSS*, 2019.

[10] Google, "Chrome UX Report (CrUX)," developer.chrome.com/docs/crux.

[11] PhishTank, phishtank.org; Phishing.Database, github.com/Phishing-Database/Phishing.Database.

# Appendix

**Source code and data:** https://github.com/AIShaurya777/PhishGuard

**How to reproduce:** install the pinned packages (`uv pip sync --python .venv requirements.lock`, then `uv pip install --python .venv --no-deps -e .`); run the 117 tests with `.venv/bin/pytest`; run notebooks 01–13 in the order in `notebooks/readme.md` (their outputs are saved); start the website with `.venv/bin/python -m phishguard.web` and open http://127.0.0.1:8000.

**Supporting material:** `docs/DECISIONS.md` (every design decision with its evidence), `docs/guide/` (a plain-language guide to every step), `docs/report/REPORT_detailed.md` (a more technical write-up) and `results/` (the saved results of every experiment).
