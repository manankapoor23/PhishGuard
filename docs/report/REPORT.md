# PhishGuard: Can a Computer Spot a Fake Website from Its Link?

**Machine learning course project, 2026.** Manan, Shaurya and Abhishek<br>
Code and data: https://github.com/AIShaurya777/PhishGuard · A more technical version of this report: [`REPORT_detailed.md`](REPORT_detailed.md)

---

## Summary

Phishing websites are fake copies of real sites that trick people into typing their passwords. We tried to build a machine learning model that spots them from the link alone, using a popular public dataset called PhiUSIIL.

At first our models scored **99.9%**, just like published research. Then we found out why: in this dataset, **every safe link looks like `https://www.something.com`**, and phishing links almost never do. A simple rule with no machine learning at all gets 99%. The models had learned how the data was collected, not what phishing looks like.

When we removed that giveaway and gave the models only the website's name, the honest score was about **87%**. Our best model, a "hybrid" neural network, reached 86.7%, only slightly better than simpler ones.

We then tested the models on real websites they had never seen. They wrongly called **81%** of popular sites with a subdomain (like `mail.yahoo.com`) phishing, and about **1 in 5** ordinary sites. Simple tricks let most phishing through. Retraining with better data helped, but only partly.

**Our main finding:** a model trained on this dataset learns the dataset, not phishing. To build a detector that works, you need training data that looks like the real web.

---

## 1. The problem

A phishing link takes you to a fake page, for example a copy of a bank's login page, to steal your details. Browsers and email services try to warn people before they click. Doing that from the link alone is fast and safe, because you never have to open the page.

Many research papers use a dataset called **PhiUSIIL** and report 99.8–99.99% accuracy. We wanted to see whether we could build a detector this good, and understand what it learns.

---

## 2. The data

- **PhiUSIIL:** 235,795 links, each labelled *phishing* or *legitimate* (safe), plus 54 extra columns the authors computed, some from the link and some from the downloaded web page.
- **Cleaning:**
  - we checked the file wasn't cut off;
  - we made "phishing" the class we try to detect;
  - we removed a trailing `/` that only phishing links had;
  - we dropped 1,589 duplicate links and one link labelled both ways.

  That leaves **234,204 links**: 58% safe and 42% phishing.
- **Extra data for testing:** lists of popular real websites (Chrome's and Tranco's top sites), a sample of ordinary less popular websites, and fresh phishing reported in 2025–26 (PhishTank).

---

## 3. A fair test

Two rules make our results trustworthy.

**1. Never test on a website the model has already seen.** Attackers make many links on the same website. If we split the links randomly, 39% of the phishing links in the test set had a "sibling" from the same website in training, so the model could just remember the website. We keep every website's links together: 70% of websites for training, 15% for choosing settings (validation), 15% for the final test.

**2. Repeat everything.** We repeat the whole experiment on 5 different splits and report the average. One lucky split can't fool us. Settings are always chosen on validation, and the test set is used only once.

---

## 4. First result: too good to be true

| Model | What it looks at | Accuracy |
|---|---|---|
| Logistic Regression, Random Forest, XGBoost | all 50 numeric columns | 99.99–100% |
| XGBoost | 40 measurements we compute from the link (length, digits, hyphens…) | 99.6% |
| Letter chunks + Logistic Regression | the link's letters | 99.7% |

These match the published papers. But when even the simplest model is nearly perfect, something is usually giving the answer away.

---

## 5. The shortcut

We tried simple rules with **no machine learning**:

| Rule | Right |
|---|---|
| "The link doesn't start with `https://www.` → phishing" | **99.08%** |
| "The similarity score is below 100 → phishing" | 99.66% |

The reason: **every** safe link in PhiUSIIL is a plain homepage like `https://www.example.org`. Only 2.4% of phishing links look like that. So the models learned "looks like a homepage = safe". That works on this dataset but means nothing in real life: real attackers get free `https` certificates, and real safe links have paths and subdomains. This is called a **shortcut**: a pattern that predicts the answer in one dataset but not in the real world. Independent reviews of this dataset found the same thing.

---

## 6. The honest test: only the website name

We removed the giveaway parts (`https://`, `www.` and everything after the domain) and gave models **only the website name**, like `login.example.top`. Then we tried five kinds of model:

| Model (website name only, average of 5 splits) | Accuracy |
|---|---|
| XGBoost on 40 measurements | 81.4% |
| BiLSTM: a neural network that reads letters in order | 85.6% |
| Letter chunks + Logistic Regression | 86.3% |
| CNN: a neural network that learns letter patterns | 86.6% |
| **Hybrid: the CNN plus the 40 measurements, trained together** | **86.7%** |

The honest score is about **86–87%**. The hybrid is best on 4 of 5 splits, but only by half a point. **The type of model matters much less than the data.**

---

## 7. Looking inside the models

We explain each prediction to see what the model relies on:
- **For the tree model (SHAP):** on full links, the most important features were "uses https" and "has www": the shortcut again.
- **For the neural network:** we hide one letter at a time and see how the score changes. That shows which letters push towards "phishing" (red on our website) or "safe" (blue).
- **We checked the explanations are honest.** Hiding the 5 letters the explanation calls most suspicious changes the model's answer 7 times more often than hiding 5 random letters.

The explanations also showed something strange: Google's real sign-in page, `accounts.google.com`, is called **99.9% phishing**.

---

## 8. The real-world test

We tested the trained models, without retraining, on websites that aren't in the dataset:

| Test | Result |
|---|---|
| Popular real websites with a subdomain (`mail.yahoo.com`) | **81%** wrongly called phishing |
| Popular real websites, plain name (`github.com`) | 15% wrongly called phishing |
| Ordinary, less popular real websites | **18–24%** wrongly called phishing |
| Phishing links switched from `http` to `https` (full-link model) | caught drops from 100% to 36% |
| Phishing website names given cheap edits (e.g. a `.com` name) | caught drops from 86% to 20% |

**Why it fails: the data.**
1. Safe links in the dataset almost never have a subdomain, so the model thinks "subdomain = phishing".
2. Phishing in the dataset comes mostly from certain countries: 79% of `.ru` links are phishing, so popular Russian sites get flagged.
3. Shared services are labelled as phishing. All 782 `google.com` links are phishing pages hosted on Google Docs or Google Sites, and 44 popular services (Weebly, IPFS, bit.ly, Azure…) are labelled almost entirely phishing. That's why the model distrusts Google itself, and why it calls the real `google.com` *more* suspicious than the fake `g0ogle.com`: it never learned what a brand is.

The model is also **confidently wrong**: on real popular sites, 77% of its wrong alarms come with 90%+ confidence.

---

## 9. Can better data fix it?

If the data is the cause, better data should help, so we tested it. We added to training:
- real safe websites;
- safe links with subdomains;
- 25,000 newer phishing websites from another source;
- phishing with deliberate edits.

We tested only on websites that share **no owner** with anything in training, and on phishing reported in 2025–26. The neural network was trained on the lab's **NVIDIA H100 GPU**.

| Best model (hybrid), average of 5 splits | Before | After |
|---|---|---|
| Wrong alarms on popular sites with a subdomain | 77% | **63%** |
| Wrong alarms on Tranco top sites | 18% | **10%** |
| Edited phishing caught | 20% | **27%** |
| New 2025–26 phishing caught | 82% | 81% |
| Accuracy on the original dataset | 86.8% | 85.7% |

**It helps, consistently on every split, for about 1 point of accuracy. But it's only a partial fix.**
- Wrong alarms are still far too high.
- Ordinary websites barely improved, because the safe sites we added were all popular ones.
- One problem got worse. Links starting with `mail.` are almost always phishing in the training data (597 phishing vs 1 safe), and the data we added contained more phishing `mail.` sites and no safe ones. **Better data only fixes a bias if it contains counter-examples.**

We also tried an **allowlist** ("never flag well-known sites"). It removes wrong alarms on the sites it lists, but does nothing for ordinary sites, and lets through phishing hosted on well-known services.

---

## 10. What we built

- **Code:** a tested Python package (pandas, scikit-learn, XGBoost, PyTorch) and 13 notebooks with saved results.
- **Trust:**
  - 117 automatic tests;
  - every number in our documents is read from saved result files;
  - 19 decisions written down with their reasons and evidence;
  - a plain-language guide for every step.
- **Website:** paste a link to see which part the model reads, which letters mattered, the two models' verdicts, and warnings when one of our measured weak spots applies. We kept it offline on purpose: it isn't safe to use as a real phishing detector, and every page says so.

---

## 11. Conclusion

1. **The 99.9% reported on PhiUSIIL is a shortcut** that comes from how the safe links were collected.
2. **From the website name alone, the honest score is about 87%**, and fancier models add less than a point.
3. **The models fail on real websites**, for reasons we can measure in the data. Better data helps, but only partly.

**Our lesson:** a model trained on this dataset learns the dataset, not phishing. A real detector would need training data that looks like the whole web (including ordinary sites, subdomains and inner pages), and information beyond the link, such as the page itself or how old the website is.

**Limitations:**
- We used one main dataset and trusted its labels.
- We only read the website name, not the page.
- The safe sites we added were all popular ones.

---

## References

- A. Prasad and S. Chandra. *PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning.* Computers & Security 136 (2024). Dataset: UCI Machine Learning Repository, id 967.
- T. Ahamed et al. *An integrated evaluation protocol for adversarial robustness, generalization, and explanation stability in URL-based phishing detection.* Frontiers in Computer Science 8 (2026).
- D. Arp et al. *Dos and Don'ts of Machine Learning in Computer Security.* USENIX Security 2022.
- H. Le et al. *URLNet: Learning a URL Representation with Deep Learning for Malicious URL Detection.* arXiv:1802.03162, 2018.
- V. Le Pochat et al. *Tranco: A Research-Oriented Top Sites Ranking Hardened Against Manipulation.* NDSS 2019.
- Google Chrome UX Report; PhishTank; Phishing.Database.
- Independent reviews of PhiUSIIL (GitHub, Hugging Face, SSRN), listed in `docs/references.md`.

The detailed numbers, methods and per-split results are in [`REPORT_detailed.md`](REPORT_detailed.md), `docs/DECISIONS.md` and the notebooks.
