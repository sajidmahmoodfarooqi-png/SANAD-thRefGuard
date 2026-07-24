"""Text embedding for the Tier-B semantic check (MVP_SPEC.md §4, R8).

Deliberately pluggable. The vision is local-first and free (CONCEPT.md), so the
*intended* backend is a local sentence-transformers model — but that pulls in
torch, which has no wheels for every Python/OS this may run on (e.g. brand-new
CPython releases), and forcing it as a hard dependency would make a plain
`pip install` fail. So:

  - `HashingEmbedding` is the dependency-free default: a deterministic feature-
    hashed bag-of-words. It is a *lexical* proxy, NOT semantic — it measures word
    overlap, not meaning — but it makes the entire R8 pipeline (sentence
    extraction, cosine, thresholding, suggestions, flag persistence, API) real,
    testable, and runnable everywhere, and it degrades gracefully instead of
    crashing when torch is absent.
  - `SentenceTransformerEmbedding` is the real semantic backend, used
    automatically when `sentence-transformers` is installed.

Every provider exposes `.name`, and the scan reports it, so a user always knows
whether they got a true semantic check or the lexical fallback — never a silent
quality downgrade dressed up as the real thing.
"""
from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# function words carry no topic; dropping them keeps the lexical proxy focused on
# content words so unrelated sentences don't look similar just for sharing "the".
_STOPWORDS = frozenset(
    "the a an of and or in on for to with from is are was were be been by as at "
    "this that these those it its into their our we they he she his her them "
    "which who whom whose can could will would may might should must not no".split()
)


def _tokens(text: str | None) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class HashingEmbedding:
    """Deterministic, dependency-free lexical embedding. Unigrams + bigrams are
    feature-hashed into a fixed-width vector and L2-normalized, so cosine ~=
    normalized shared-token overlap. Same input -> same vector, always (tests and
    re-scan suppression rely on that)."""

    name = "lexical-hash"

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        toks = _tokens(text)
        grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for g in grams:
            idx = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm:
            vec = [v / norm for v in vec]
        return vec


class SentenceTransformerEmbedding:  # pragma: no cover - optional heavy dependency
    """Real local semantic embedding. all-MiniLM-L6-v2 is small (~90 MB), CPU-fine,
    and Apache-2.0 — consistent with the free/local-first constraint. Lazily
    constructed so importing this module never triggers the heavy import."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.name = f"sentence-transformers:{model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]


def get_embedding_provider(prefer_semantic: bool = True):
    """Return the best available provider: the real semantic model if installed,
    otherwise the lexical fallback. Never raises — a missing torch is a
    degradation, not a failure."""
    if prefer_semantic:
        try:
            return SentenceTransformerEmbedding()
        except Exception:
            pass
    return HashingEmbedding()
