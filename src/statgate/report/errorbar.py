from statgate.core.intervals import Interval

_DEFAULT_WIDTH = 61


def _column(value: float, axis_low: float, axis_high: float, width: int) -> int:
    span = axis_high - axis_low
    if span <= 0.0:
        return width // 2
    position = (value - axis_low) / span
    return min(width - 1, max(0, round(position * (width - 1))))


def _place_label(row: list[str], column: int, label: str, width: int) -> None:
    start = min(max(0, column - len(label) // 2), width - len(label))
    for offset, char in enumerate(label):
        if row[start + offset] == " ":
            row[start + offset] = char


def render_error_bar(
    interval: Interval,
    point: float,
    margin: float,
    width: int = _DEFAULT_WIDTH,
) -> str:
    """Draw an ASCII confidence interval against the margin and zero.

    The bar shows the interval as ``[---o---]`` on a ruler that marks the
    non-inferiority margin and zero, so the verdict is visible at a
    glance: an interval entirely right of the margin ships, entirely
    left of it blocks.
    """
    if width < 21:
        raise ValueError(f"width must be at least 21, got {width}")

    anchors = [interval.low, interval.high, point, -margin, 0.0]
    axis_low = min(anchors)
    axis_high = max(anchors)
    span = max(axis_high - axis_low, 1e-9)
    padding = span * 0.12
    axis_low -= padding
    axis_high += padding

    bar = [" "] * width
    low_col = _column(interval.low, axis_low, axis_high, width)
    high_col = _column(interval.high, axis_low, axis_high, width)
    point_col = _column(point, axis_low, axis_high, width)
    for col in range(low_col, high_col + 1):
        bar[col] = "-"
    bar[low_col] = "["
    bar[high_col] = "]"
    bar[point_col] = "o"

    ruler = ["."] * width
    margin_col = _column(-margin, axis_low, axis_high, width)
    zero_col = _column(0.0, axis_low, axis_high, width)
    ruler[margin_col] = "|"
    ruler[zero_col] = "|"

    labels = [" "] * width
    _place_label(labels, margin_col, f"-margin ({-margin:+.3g})", width)
    if zero_col != margin_col:
        _place_label(labels, zero_col, "0", width)

    legend = (
        f"diff {point:+.4f}   "
        f"{interval.confidence:.0%} CI [{interval.low:+.4f}, {interval.high:+.4f}]"
    )
    return "\n".join(
        ["".join(bar), "".join(ruler), "".join(labels).rstrip(), legend]
    )
