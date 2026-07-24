"""Tests for the pluggable embedding layer (MVP_SPEC.md §4, Tier-B)."""
from sanad_core import embedding


def test_hashing_embedding_is_deterministic():
    e = embedding.HashingEmbedding()
    v1 = e.embed(["coastal tides rise and fall with the lunar cycle"])[0]
    v2 = e.embed(["coastal tides rise and fall with the lunar cycle"])[0]
    assert v1 == v2                       # re-scan suppression depends on this
    assert len(v1) == e.dim


def test_cosine_ranks_related_text_higher_than_unrelated():
    e = embedding.HashingEmbedding()
    sentence = "Ocean tides rise and fall with the lunar cycle each month."
    on_topic = "Lunar cycles drive the rise and fall of coastal tides."
    off_topic = "Central bank interest rate policy and commercial lending."
    sv, on, off = e.embed([sentence, on_topic, off_topic])
    assert embedding.cosine(sv, on) > embedding.cosine(sv, off)


def test_cosine_of_disjoint_text_is_near_zero():
    e = embedding.HashingEmbedding()
    a, b = e.embed(["typography kerning ligatures serif", "quarterly revenue shareholders dividend"])
    assert embedding.cosine(a, b) < 0.2


def test_factory_falls_back_to_lexical_without_semantic_backend():
    # sentence-transformers is not a hard dependency; the factory must still work
    provider = embedding.get_embedding_provider()
    assert hasattr(provider, "embed") and provider.name
    # embeds without raising regardless of which backend was selected
    assert len(provider.embed(["hello world"])) == 1
