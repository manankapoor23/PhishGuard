# 10 · Extra checks (after Milestone 7b)

Code: `src/phishguard/audit.py`. Notebook: `13_extra_checks.ipynb`. Decision: D19.

Five short questions an examiner, or a real user, would ask next. Each is answered with models and results we already have.

## 1. Is `google.com` the only popular site labelled phishing?
No. Of the popular websites (Tranco top 20k) with at least 20 rows in PhiUSIIL, **44 are labelled mostly or entirely phishing**, 6,932 rows in all:

| Owner | Rows | What it is |
|---|---|---|
| `ipfs.io` | 1,441 | file hosting |
| `google.com` | 782 | Docs, Sites |
| `godaddysites.com`, `weebly.com` | 769, 552 | website builders |
| `windows.net`, `aliyuncs.com` | 326, 219 | cloud storage |
| `bit.ly`, `tinyurl.com` | 150, 135 | link shorteners |

Attackers host phishing **on** these services, and the dataset labels the whole link as phishing. A model that reads only the domain can't tell an honest page from a phishing page on the same service.

## 2. Can we trust the probabilities?
A model is **calibrated** if, of all links it gives 0.9, about 90% really are phishing.
- **On PhiUSIIL's test data, yes:** the average gap (expected calibration error) is about 2 points.
- **On real popular sites with a subdomain, no:** the hybrid flags 80% of them, and **77% of those wrong flags come with a probability of 0.9 or more**.

**Lesson:** calibration only holds on data like the training data. Under distribution shift, a model can be confidently wrong.

## 3. What would a real browser warning catch?
A browser must almost never warn on a real site. So we chose the threshold for a fixed false-alarm rate:

| False alarms allowed | Hybrid catches | n-grams catch |
|---|---|---|
| usual threshold (~2.6%) | 75% | 76% |
| 1 in 100 | 64% | 67% |
| 1 in 1,000 | 51% | 54% |

## 4. What about ordinary websites, not just popular ones?
On 19,321 sites from Tranco ranks 100,001–1,000,000: **18% (hybrid) and 24% (n-grams) false alarms**. The 7b better-data model is barely better (23%), because 7b only added *popular* legitimate sites.

**Lesson:** fixed data must look like the sites you'll be tested on.

## 5. Would an allowlist fix it?
Rule: never flag a site whose owner is in the Tranco top N.

| Allowlist | False alarms, popular sites with a subdomain | False alarms, ordinary sites | New phishing caught |
|---|---|---|---|
| none | 80% | 18% | 82% |
| top 10,000 | 38% | 18% | 82% |
| top 100,000 | 0.1% | 18% | 77% |

It fixes only the sites on the list, and the popular-site row is partly circular: those test sites *are* popular. It does nothing for ordinary sites, and it lets through phishing hosted on popular services (5% of new phishing).

## Likely viva questions
**Q: Your model says 99.9%. Is it sure?**
A: Inside PhiUSIIL its probabilities are well calibrated, but on real sites it's confidently wrong: 77% of its wrong flags on popular sites have probability ≥ 0.9. Confidence isn't correctness under distribution shift.

**Q: Why not just allowlist big sites?**
A: We measured it. It removes false alarms only for the listed sites, does nothing for ordinary ones (still 18%), and lets through phishing hosted on big services like Google Docs or Weebly. That's why real systems also look at page content and domain age.

**Q: What accuracy would a browser see?**
A: At 1 false alarm per 1,000 legitimate links, the models catch about half of phishing. And that's inside PhiUSIIL; on real sites it would be worse.
