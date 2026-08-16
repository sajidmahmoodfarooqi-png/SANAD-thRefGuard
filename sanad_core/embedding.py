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
import importlib.util
import math
import re
from collections import OrderedDict


def semantic_available() -> bool:
    """True if the real semantic backend (sentence-transformers) is installed, so
    R8 runs as a true semantic check rather than the lexical fallback. Cheap and
    side-effect-free: it only checks the package is importable, never loads a
    model. Lets the UI and API state honestly which mode is in effect."""
    return importlib.util.find_spec("sentence_transformers") is not None

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


class CachingEmbedding:
    """Wraps any provider with a persistent per-text vector cache.

    A reference's title+abstract doesn't change between scans, yet R8 re-embeds
    the whole library pool on every scan (see integrity.r8_context_misalignment).
    For the lexical fallback that's cheap; for the real sentence-transformers
    model it's the dominant cost. This memoizes each distinct text -> vector for
    the life of the Core process, so re-scans only embed genuinely new text
    (edited sentences, newly added sources). Bounded and FIFO-evicted so a huge
    library can't grow the cache without limit. Returns byte-identical vectors,
    so determinism (tests, re-scan flag suppression) is preserved."""

    def __init__(self, inner, max_entries: int = 20_000):
        self._inner = inner
        self.name = inner.name
        self._cache: "OrderedDict[str, list[float]]" = OrderedDict()
        self._max = max_entries

    def embed(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            for t, v in zip(missing, self._inner.embed(missing)):
                self._cache[t] = v
                if len(self._cache) > self._max:
                    self._cache.popitem(last=False)  # evict oldest
        else:
            # keep hot entries fresh-ish for eviction ordering only when we didn't
            # just insert; cheap and keeps re-scanned refs from aging out first.
            for t in dict.fromkeys(texts):
                self._cache.move_to_end(t)
        return [self._cache[t] for t in texts]


def get_embedding_provider(prefer_semantic: bool = True, cache: bool = True):
    """Return the best available provider: the real semantic model if installed,
    otherwise the lexical fallback. Never raises — a missing torch is a
    degradation, not a failure. Wrapped in a persistent per-text cache by default
    (harmless for the lexical proxy, a large win for the real model on re-scan)."""
    provider = None
    if prefer_semantic:
        try:
            provider = SentenceTransformerEmbedding()
        except Exception:
            provider = None
    if provider is None:
        provider = HashingEmbedding()
    return CachingEmbedding(provider) if cache else provider
