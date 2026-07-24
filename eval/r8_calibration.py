"""Calibrate the Tier-B (R8) context-misalignment threshold.

R8 flags a citation when the citing sentence is only weakly related to the
source it cites: it flags iff the best cited-source similarity is <= threshold.
So a good threshold sits between the *off-topic* similarity distribution (a
sentence vs an unrelated source) and the *on-topic* one (a sentence vs the
source it is actually about).

This script runs the shipped embedder over a small labelled set of neutral,
cross-domain reference/sentence pairs, reports both distributions, and sweeps
the threshold to find the value that best separates them (max balanced
accuracy, tie-broken toward fewer false alarms). Run:  python eval/r8_calibration.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sanad_core import embedding  # noqa: E402

# (title + abstract, an on-topic citing sentence) across distinct domains.
# All invented; no real bibliography data.
DATASET = [
    ("Tides and the lunar cycle. Coastal water levels rise and fall with the moon's gravitational pull across the lunar month.",
     "Ocean tide heights around the coast follow the phase of the moon each month."),
    ("Foundations of typography. The study of letterforms, kerning, and ligatures in printed type on the page.",
     "Careful kerning and ligature choices shape the texture of printed type on a page."),
    ("A framework for distributed caching. Caching data across distributed server nodes reduces read latency in large clusters.",
     "Distributing cache entries across server nodes cuts read latency in a large cluster."),
    ("The art of memory. Techniques for improving human memory and the recall of long, structured lists of information.",
     "Structured mnemonic techniques improve human recall of long lists."),
    ("Consumer credit and interest rates. Central bank interest rate decisions affect inflation and lending in the banking sector.",
     "Higher central-bank interest rates tighten consumer lending and cool inflation."),
    ("Map projections and distortion. Methods for projecting the curved earth onto flat map sheets while managing distortion.",
     "Choosing a map projection trades off area, shape, and distance distortion on a flat sheet."),
    ("Photosynthesis in leaves. Chloroplasts convert sunlight and carbon dioxide into sugars inside plant leaves.",
     "In plant leaves, chloroplasts turn sunlight and carbon dioxide into sugar."),
    ("Honeybee colony management. The management of honeybee colonies for pollination and honey production in hives.",
     "Managing hive and colony health is central to honey production and pollination."),
    ("Predicting volcanic eruptions. The study of magma movement and seismic swarms used to predict volcanic eruptions.",
     "Rising magma and seismic swarms often precede a volcanic eruption."),
    ("King and pawn chess endgames. The theory of king and pawn endgames and the role of the opposition in chess.",
     "In king and pawn endgames, taking the opposition often decides the chess result."),
    ("A survey of distributed ledger systems. Consensus mechanisms in blockchain and distributed ledger technology.",
     "Consensus mechanisms are the core design choice in a distributed ledger."),
    ("The chemistry of coffee roasting. Roasting green coffee beans develops acidity, body, and flavour through heat.",
     "Roast temperature curves develop the acidity and body of roasted coffee beans."),
]


def main() -> int:
    emb = embedding.HashingEmbedding()
    refs = [emb.embed([r])[0] for r, _ in DATASET]
    sents = [emb.embed([s])[0] for _, s in DATASET]

    positives, negatives = [], []
    for i in range(len(DATASET)):
        for j in range(len(DATASET)):
            sim = embedding.cosine(sents[i], refs[j])
            (positives if i == j else negatives).append(sim)

    def stats(xs):
        xs = sorted(xs)
        return min(xs), sum(xs) / len(xs), xs[len(xs) // 2], max(xs)

    p_min, p_mean, p_med, p_max = stats(positives)
    n_min, n_mean, n_med, n_max = stats(negatives)
    print(f"on-topic  (n={len(positives)}):  min={p_min:.3f}  mean={p_mean:.3f}  median={p_med:.3f}  max={p_max:.3f}")
    print(f"off-topic (n={len(negatives)}):  min={n_min:.3f}  mean={n_mean:.3f}  median={n_med:.3f}  max={n_max:.3f}")

    # sweep thresholds: R8 flags when a cited similarity <= t.
    # A correct NON-flag on an on-topic pair needs sim > t; a correct flag on an
    # off-topic pair needs sim <= t.
    best = None
    t = 0.0
    while t <= 0.60:
        tp = sum(1 for s in negatives if s <= t)   # off-topic correctly flagged
        fn = len(negatives) - tp                   # off-topic missed
        tn = sum(1 for s in positives if s > t)    # on-topic correctly left alone
        fp = len(positives) - tn                   # on-topic falsely flagged
        recall = tp / len(negatives)
        specificity = tn / len(positives)
        bal_acc = (recall + specificity) / 2
        # prefer higher balanced accuracy; tie-break toward fewer false alarms (fp)
        key = (round(bal_acc, 4), -fp)
        if best is None or key > best[0]:
            best = (key, round(t, 3), bal_acc, fp, fn)
        t += 0.005

    _, t_star, bal_acc, fp, fn = best
    print(f"\nrecommended lexical-hash threshold: {t_star:.3f}")
    print(f"  balanced accuracy {bal_acc:.3f}  ·  false alarms {fp}/{len(positives)}  ·  missed {fn}/{len(negatives)}")
    print(f"  (separation window: off-topic max {n_max:.3f} .. on-topic min {p_min:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
