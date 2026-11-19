# Walkthrough: notebooks 04 and 05 (and how 02–05 fit together)

For presenting **Milestone 2, model training**, after data preprocessing (01, 01b). Notebooks 02 and 03 are covered in `WALKTHROUGH_02_03.md`. The notebooks themselves explain every step in plain words; this file adds the story, what to say, and likely questions.

**Don't re-run the notebooks live:** outputs are saved. For a live demo, run `.venv/bin/pytest`.

## The story of Milestone 2 in four notebooks
| Notebook | Question | Answer |
|---|---|---|
| 02 | Can we match the published 99.9%? | Yes: 99.99–100% using all 50 dataset columns |
| 03 | Can we do it from **the link only**, with 40 features we design? | 99.6% |
| 04 | Can the model learn from **the link's characters** itself? | 99.7%, and we can read what it learned |
| 05 | Are the differences real, and what would this mean in real use? | Tiny but some significant; real use is harder than 99.7% suggests |

**Opening line:** "After cleaning and splitting the data, we trained models in three ways: on all the dataset's columns, on features we compute from the link, and on the link's characters directly."

---

## Notebook 04 · Character n-grams

**What it does:** instead of us choosing 40 numbers to describe a link, the model gets **every 1–4 character chunk** of the link (`paypa1.top` → `pay`, `ayp`, `pa1`, `.top` …) and learns one weight per chunk.

- **TF-IDF:** each chunk gets a score that's high if it's in *this* link but rare overall.
- **Logistic Regression:** learns a weight per chunk (306,717 chunks).

**Step 1, results:** about 99.7% on every split. **Say:** "As good as the best published link-only results."

**Step 2, what it learned.** This is the most interesting part to show:
- Top phishing chunks: `p://`, `ttp:`, i.e. **`http://` without the s**.
- Top legitimate chunks: `www`, `//ww`.
- **Say:** "The model mostly learned how a link *starts*, not what the website's name is. That's suspicious, because a real attacker can also use `https://www.`. That's what we investigate next."

**Step 3, McNemar's test:** n-grams vs XGBoost on the same test links, counting only disagreements: 38 vs 16, **p = 0.004**. **Say:** "The difference is real, but it's 22 links out of 35,000."

**Step 4, combining:** average the two models' log-odds → **99.70%**, no meaningful gain. **Say:** "A first, simple combination. In Milestone 5 we build a proper hybrid that trains them together."

---

## Notebook 05 · All results, checked properly

**What it does:** it trains nothing. It reads the saved results of 02–04 from `results/m2/` and checks them.

**Step 1, results table:** all columns 99.99–100%; link only 99.6–99.7%. Point out the **95% confidence interval** column: "the range the true accuracy probably lies in. We resample whole websites, so one big site can't make us overconfident."

**Step 2, McNemar between all link-only models:**
- Character-based models (n-grams, combination) beat feature-based ones (XGBoost, Random Forest): all p < 0.05, but by only 20–30 links.
- **Ties:** combination vs n-grams (17 vs 17, p = 1.0); XGBoost vs Random Forest (p = 0.36).
- **Say:** "We only call a model better when a test says so, and even then the gap is tiny."

**Step 3, published comparison:** a context chart. **Say:** "Papers used different splits, so this is context, not a race."

**Step 4, real-world precision:** our best link-only model, if phishing were rarer:

| Share of links that are phishing | Share of its warnings that are correct |
|---|---|
| 42% (this dataset) | 99.9% |
| 10% | 99.5% |
| 1% | 94.9% |
| 0.1% (closer to real browsing) | **64.7%** |

**Say:** "In real browsing phishing is rare, so even a 0.05% false-alarm rate means about a third of warnings would be false. Accuracy on a balanced dataset overstates real usefulness."

**Closing line:** "Milestone 2: we reproduced the published results and reached 99.7% from the link alone. But the model mostly reads how the link starts, and almost every remaining mistake is a phishing link that looks like `https://www.site.com`. Next we find out why."

---

## If she asks …
**What's TF-IDF?** Term frequency × inverse document frequency: a chunk gets a high score if it's frequent in this link and rare across all links, so common chunks like `.com` count less.

**Why logistic regression on n-grams, not a neural network?** It's fast, a strong baseline, and every weight can be read, as Step 2 shows. The neural version (char-CNN) comes in Milestone 4.

**What does McNemar's test do?** It compares two models on the same test links, looking only where they disagree. If they were equally good, each would win about half of those links. The p-value says how surprising the actual split is.

**Why log-odds averaging instead of averaging probabilities?** Log-odds add up evidence fairly. If one model is generally more confident, averaging probabilities would let it dominate.

**Why does precision drop when phishing is rare?** When almost every link is legitimate, even a tiny false-alarm rate produces many false warnings compared with the few real phishing links.

**What's the 95% CI?** If we repeated the test on new websites like these, the true accuracy would fall in that range 95% of the time. It's computed by resampling whole site owners (bootstrap).

## Files to have open
- `notebooks/04_char_ngram_model.ipynb`, `notebooks/05_m2_results.ipynb`
- `src/phishguard/modeling.py` (the n-gram model), `src/phishguard/stats.py` (McNemar, bootstrap CI), `src/phishguard/ensemble.py` (log-odds average)
- `docs/DECISIONS.md`: D6 (testing routine), D8 (Milestone 2 results)
