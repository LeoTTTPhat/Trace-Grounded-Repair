"""Toy bug from the Trace-Grounded Repair paper."""


def rolling_max(xs: list[int], k: int) -> list[int]:
    out, window = [], []
    for i, x in enumerate(xs):
        window.append(x)
        if len(window) > k:
            window.pop()
        if i >= k - 1:
            out.append(max(window))
    return out
