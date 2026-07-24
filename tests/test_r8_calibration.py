"""Regression guard for the R8 (Tier-B) lexical threshold.

The threshold in integrity.R8_THRESHOLDS["lexical-hash"] was calibrated against
the labelled on-topic/off-topic set in eval/r8_calibration.py. This test locks in
that the shipped threshold still separates that set: it must never false-alarm on
a correctly-cited source, and must catch the large majority of misattributions.
If a future change to the embedder or the threshold breaks this, it fails loudly.
"""
from eval.r8_calibration import DATASET
from sanad_core import embedding, integrity


def _sim_matrix():
    emb = embedding.HashingEmbedding()
    refs = [emb.embed([r])[0] for r, _ in DATASET]
    sents = [emb.embed([s])[0] for _, s in DATASET]
    return refs, sents


def test_no_false_alarms_on_topic():
    """An on-topic citation must never be flagged (sim strictly above threshold)."""
    refs, sents = _sim_matrix()
    t = integrity.R8_THRESHOLDS["lexical-hash"]
    for i in range(len(DATASET)):
        sim = embedding.cosine(sents[i], refs[i])
        assert sim > t, f"on-topic pair {i} would false-alarm at {t}: sim={sim:.3f}"


def test_catches_the_vast_majority_of_misattributions():
    refs, sents = _sim_matrix()
    t = integrity.R8_THRESHOLDS["lexical-hash"]
    flagged = total = 0
    for i in range(len(DATASET)):
        for j in range(len(DATASET)):
            if i == j:
                continue
            total += 1
            if embedding.cosine(sents[i], refs[j]) <= t:
                flagged += 1
    assert flagged / total >= 0.97, f"only {flagged}/{total} off-topic pairs flagged at {t}"
