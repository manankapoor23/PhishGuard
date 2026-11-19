# 9 · Better training data (Milestone 7b)

Code: `src/phishguard/datafix.py`. Notebook: `12_better_data.ipynb`. Decision: D18. Data: `DataSets/external/` (feeds frozen on 2026-11-19).

## The question
In Milestone 7 we said the models fail on real websites because of the **data**: PhiUSIIL's legitimate links have almost no subdomains, and its phishing comes from one feed. That was an explanation, not a test. If it's true, giving the models better data should make the failures smaller. So we tried it.

## What we added to training
| Addition | Label | Why |
|---|---|---|
| Half of the Tranco top 20k sites | legitimate | real, popular websites, not just PhiUSIIL's homepages |
| Legitimate domains with `app.`, `docs.`, `help.` … in front | legitimate | teach that subdomains are normal |
| 25,000 Phishing.Database domains (one per site owner) | phishing | newer phishing from another source |
| Phishing domains with one attacker edit | phishing | teach the model the cheap tricks from Milestone 7 |

**Two fairness rules:**
1. **We test with different subdomain words** (`mail.`, `blog.`, `login.`) from the ones we trained with. Otherwise we'd be testing on what we taught.
2. **No test website shares an owner with anything in training.** We check this, and the overlap is 0.

```python
from phishguard.datafix import build_pools, make_sets
pools = build_pools(df)                              # fixed training and test sets
sets = make_sets(df, pools, seed=42, variant="PhiUSIIL + fixes")
X_train, y_train = sets["train"]                     # 225,928 domains (164,045 before)
```

## Where it ran
- **Character n-grams:** on a laptop CPU, about 8 minutes for both versions × 5 splits.
- **Hybrid:** on the **lab's NVIDIA H100 GPU**, about 30 seconds per model, 25 minutes in total. The code picks the GPU automatically (`pick_device()`: CUDA, then Apple GPU, then CPU).

```bash
python -m phishguard.datafix --model ngram     # writes results/m7b/ngram__*.json
python -m phishguard.datafix --model hybrid    # writes results/m7b/hybrid__*.json
```

## Results (mean over 5 splits, before → after)
| Test | n-grams | Hybrid |
|---|---|---|
| Accuracy on PhiUSIIL | 86.3 → 85.7% | 86.8 → 85.7% |
| False alarms: popular sites with a subdomain | 53 → **39%** | 77 → **63%** |
| False alarms: Tranco test sites | 25 → **16%** | 18 → **10%** |
| False alarms: popular plain domains | 22 → 17% | 16 → 12% |
| New 2025–26 phishing caught (PhishTank) | 82 → 81% | 82 → 81% |
| Edited phishing caught | 31 → **39%** | 20 → **27%** |
| False alarms: legitimate + `mail.` | 67 → 66% | 86 → **92% (worse)** |

The main gains hold on **every one of the 5 splits** (notebook 12, step 3).

**In plain words:**
- **Better data works where it applies.** False alarms on real sites fall by a quarter to a half, and edited phishing is caught more often.
- **The cost is small:** about 1 point of accuracy on the original dataset, and new phishing is caught just as often.
- **It's not enough for real use.** 39–63% false alarms on sites with a subdomain is still far too many.

## The surprise: `mail.` got worse
In the new training data, subdomains starting with `mail.` appear **597 times as phishing and once as legitimate**. Webmail login pages are a favourite phishing target, and the phishing feed we added brought more of them. Our legitimate subdomains deliberately didn't use `mail.`, to keep the test fair. So the model saw even more evidence that "`mail.` means phishing".

**Lesson:** more data only removes a bias if it contains **counter-examples**. You have to check what new data teaches.

## Likely viva questions
**Q: Did the fix work?**
A: Partly. False alarms on real sites fell by a quarter to a half on every split, for about 1 point of accuracy. But 39–63% false alarms on sites with a subdomain is still far too high, and one bias (`mail.`) got worse.

**Q: How do you know the test is fair?**
A: Test websites share no site owner with any training data (checked: 0 overlap), the tested subdomain words are different from the trained ones, and the new phishing test uses PhishTank reports from 2025 on, from a different source than the phishing we added.

**Q: Why did accuracy on PhiUSIIL go down?**
A: The model no longer leans on PhiUSIIL's quirks, such as "no subdomain means legitimate". Losing a shortcut costs a little in-dataset accuracy and gains a lot on real sites. That's the trade we want.

**Q: Why use the lab GPU?**
A: The hybrid is a neural network. On the H100 each model trains in about 30 seconds, against several minutes on a laptop. We train 20 of them (2 versions × 5 splits × 2 dropout settings).

**Q: So how would you make it a real detector?**
A: Legitimate data that looks like what people actually visit, with real subdomains and inner pages, collected the same way as the phishing; checking every addition for counter-examples; and probably more than the domain, such as page content or the domain's age. See the report's "next steps".
