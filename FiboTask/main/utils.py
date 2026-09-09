"""Pure helpers (kept separate so they are trivially testable)."""


def fibonacci_series(n_terms: int) -> list[int]:
    """Return the first ``n_terms`` Fibonacci numbers starting at 0."""
    if n_terms <= 0:
        return []
    series: list[int] = []
    a, b = 0, 1
    for _ in range(n_terms):
        series.append(a)
        a, b = b, a + b
    return series
