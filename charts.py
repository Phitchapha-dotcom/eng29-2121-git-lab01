"""Small dependency-free SVG line chart helper.

Only data produced by :mod:`spice_engine` is plotted; the module does not
compute any circuit physics.
"""

from __future__ import annotations

import html
import math

PALETTE = ("#0d9488", "#2563eb", "#b45309", "#7c3aed")


def _fmt(value: float, unit: str = "") -> str:
    magnitude = abs(value)
    if magnitude >= 1e9:
        text = f"{value / 1e9:g} G"
    elif magnitude >= 1e6:
        text = f"{value / 1e6:g} M"
    elif magnitude >= 1e3:
        text = f"{value / 1e3:g} k"
    elif 0 < magnitude < 1e-3:
        text = f"{value * 1e6:g} µ"
    elif 0 < magnitude < 1:
        text = f"{value * 1e3:g} m"
    else:
        text = f"{value:g}"
    return f"{text}{unit}" if unit else text


def _fmt_axis(value: float) -> str:
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1e6:
        return f"{value / 1e6:g}M"
    if magnitude >= 1e3:
        return f"{value / 1e3:g}k"
    if magnitude >= 1:
        return f"{value:.3g}"
    if magnitude >= 1e-3:
        return f"{value * 1e3:.3g}m"
    return f"{value:.2g}"


def _downsample(points: list[tuple[float, float]], limit: int = 260):
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    picked = [points[round(i * step)] for i in range(limit)]
    picked[-1] = points[-1]
    return picked


def _nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    if not math.isfinite(low) or not math.isfinite(high) or low == high:
        return [low]
    return [low + (high - low) * i / (count - 1) for i in range(count)]


def line_chart(
    series: list[dict],
    *,
    x_label: str,
    x_unit: str,
    y_label: str,
    y_unit: str,
    log_x: bool = False,
    title: str = "",
    width: int = 760,
    height: int = 330,
) -> str:
    """Render one chart as an accessible inline SVG string."""

    cleaned = []
    for index, item in enumerate(series):
        points = [
            (float(x), float(y))
            for x, y in item.get("points", [])
            if math.isfinite(float(x)) and math.isfinite(float(y))
        ]
        if log_x:
            points = [(x, y) for x, y in points if x > 0]
        if points:
            cleaned.append(
                {
                    "name": str(item.get("name", f"Series {index + 1}")),
                    "color": item.get("color", PALETTE[index % len(PALETTE)]),
                    "points": points,
                }
            )
    if not cleaned:
        return '<p class="empty-state">ไม่มีข้อมูลสำหรับวาดกราฟ</p>'

    xs = [x for item in cleaned for x, _ in item["points"]]
    ys = [y for item in cleaned for _, y in item["points"]]
    x_low, x_high = min(xs), max(xs)
    y_low, y_high = min(ys), max(ys)
    if log_x:
        x_low, x_high = max(x_low, 1e-12), max(x_high, 1e-11)
        if x_low == x_high:
            x_low, x_high = x_low / 10, x_high * 10
    elif x_low == x_high:
        x_low, x_high = x_low - 1, x_high + 1
    if y_low == y_high:
        pad = max(abs(y_low) * 0.1, 0.5)
        y_low, y_high = y_low - pad, y_high + pad
    else:
        pad = (y_high - y_low) * 0.08
        y_low, y_high = y_low - pad, y_high + pad

    pad_left, pad_right, pad_top, pad_bottom = 74, 16, 30, 46
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    def sx(value: float) -> float:
        if log_x:
            ratio = (math.log10(value) - math.log10(x_low)) / (
                math.log10(x_high) - math.log10(x_low)
            )
        else:
            ratio = (value - x_low) / (x_high - x_low)
        return pad_left + ratio * plot_w

    def sy(value: float) -> float:
        ratio = (value - y_low) / (y_high - y_low)
        return pad_top + (1.0 - ratio) * plot_h

    uid = f"chart-{abs(hash((x_label, y_label, title, tuple(xs[:4])))) % 100000}"
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="{uid}-title {uid}-desc" preserveAspectRatio="xMidYMid meet">',
        f'<title id="{uid}-title">{html.escape(title or y_label)}</title>',
        f'<desc id="{uid}-desc">กราฟ {html.escape(y_label)} ({html.escape(y_unit)}) '
        f'เทียบกับ {html.escape(x_label)} ({html.escape(x_unit)}) จากผล ngspice</desc>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fbfdfe" rx="10"/>',
    ]

    for tick in _nice_ticks(y_low, y_high):
        y = sy(tick)
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.2f}" x2="{pad_left + plot_w}" '
            f'y2="{y:.2f}" stroke="#e3edf3" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_left - 9}" y="{y + 4:.2f}" text-anchor="end" '
            f'class="chart-tick">{_fmt_axis(tick)}</text>'
        )
    if y_low < 0 < y_high:
        y = sy(0)
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.2f}" x2="{pad_left + plot_w}" '
            f'y2="{y:.2f}" stroke="#9db4c4" stroke-width="1.2"/>'
        )

    if log_x:
        lo, hi = math.log10(x_low), math.log10(x_high)
        ticks = _nice_ticks(lo, hi)
        x_ticks = [10**tick for tick in ticks]
    else:
        x_ticks = _nice_ticks(x_low, x_high)
    for tick in x_ticks:
        x = sx(tick)
        parts.append(
            f'<line x1="{x:.2f}" y1="{pad_top}" x2="{x:.2f}" '
            f'y2="{pad_top + plot_h}" stroke="#e3edf3" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{pad_top + plot_h + 18}" text-anchor="middle" '
            f'class="chart-tick">{_fmt_axis(tick)}</text>'
        )

    parts.append(
        f'<line x1="{pad_left}" y1="{pad_top + plot_h}" x2="{pad_left + plot_w}" '
        f'y2="{pad_top + plot_h}" stroke="#7d95a6" stroke-width="1.3"/>'
    )
    parts.append(
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" '
        f'y2="{pad_top + plot_h}" stroke="#7d95a6" stroke-width="1.3"/>'
    )
    parts.append(
        f'<text x="{pad_left + plot_w / 2:.2f}" y="{height - 8}" '
        f'text-anchor="middle" class="chart-axis">{html.escape(x_label)} '
        f'[{html.escape(x_unit)}]</text>'
    )
    parts.append(
        f'<text x="16" y="{pad_top + plot_h / 2:.2f}" text-anchor="middle" '
        f'class="chart-axis" transform="rotate(-90 16 {pad_top + plot_h / 2:.2f})">'
        f"{html.escape(y_label)} [{html.escape(y_unit)}]</text>"
    )

    for index, item in enumerate(cleaned):
        points = _downsample(item["points"])
        coords = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in points)
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="{item["color"]}" '
            f'stroke-width="2.1" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        legend_x = pad_left + 6 + index * 132
        parts.append(
            f'<line x1="{legend_x}" y1="{pad_top - 14}" x2="{legend_x + 20}" '
            f'y2="{pad_top - 14}" stroke="{item["color"]}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{legend_x + 26}" y="{pad_top - 10}" class="chart-legend">'
            f"{html.escape(item['name'])}</text>"
        )

    parts.append("</svg>")
    return "".join(parts)
