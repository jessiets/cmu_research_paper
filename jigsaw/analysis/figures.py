"""Static figures for the analysis (PNG, light mode, for the paper).

Colors follow the dataviz reference palette: the first three categorical
slots (validated all-pairs in light mode), used only for reference level.
Method identity is carried by marker shape and direct labels, never by color
alone; every figure has a CSV table next to it.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
LEVEL_COLOR = {"none": "#2a78d6", "exact": "#eb6834", "degraded": "#1baf7a"}  # slots 1-3
METHOD_MARKER = {"GEO": "o", "COLOR": "s", "GRAD": "^", "HYB-GC": "D", "HYB-FILTER": "v", "REF-ONLY": "X"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": TEXT, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "grid.linestyle": "-", "font.size": 8, "axes.titlesize": 9, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.5,
})


def _cond(t: dict) -> str:
    return f"{t['grid']} c{t['complexity']} w{t['wear']}"


def _split_arm(arm: str) -> tuple[str, str]:
    if arm.startswith("REF-ONLY"):
        return "REF-ONLY", arm.split("(")[1].rstrip(")")
    if "+R (" in arm:
        method, rest = arm.split("+R (")
        return method, rest.rstrip(")")
    return arm, "none"


def _frame(fig, title: str, label: str, handles: list, ncol: int) -> None:
    """Title (and data label) at the top left, legend in its own row at the bottom."""
    fig.suptitle(title, x=0.01, y=0.995, ha="left", va="top", fontsize=10, fontweight="bold")
    if label:
        fig.text(0.01, 0.955, label, color=TEXT_2, fontsize=7, ha="left", va="top")
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=ncol, frameon=False, fontsize=7)


def _plain_log_axis(ax) -> None:
    ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())


def forest(out: Path, tests: list[dict], family: str, metric: str, conditions: list, label: str) -> str | None:
    rows = [t for t in tests if t["family"] == family and t["metric"] == metric]
    if not rows:
        return None
    if family == "C3":
        panels = list(dict.fromkeys(t["baseline_arm"] for t in rows))  # one panel per method
    else:
        panels = list(dict.fromkeys(t["comparison"] if family == "C1" else t["arm"] for t in rows))
    names = [f"{c[0]} c{c[1]} w{c[2]}" for c in conditions]
    fig, axes = plt.subplots(1, len(panels), figsize=(2.3 * len(panels) + 0.8, 0.28 * len(names) + 1.4),
                             sharey=True, squeeze=False)
    for ax, panel in zip(axes[0], panels):
        ax.axvline(0, color=TEXT_2, linewidth=0.8)
        series = [("exact", 0.15), ("degraded", -0.15)] if family == "C3" else [(None, 0.0)]
        for level, offset in series:
            for t in rows:
                key = t["baseline_arm"] if family == "C3" else (t["comparison"] if family == "C1" else t["arm"])
                if key != panel or (level and not t["arm"].endswith(f"({level})")):
                    continue
                y = len(names) - 1 - names.index(_cond(t)) + offset
                color = LEVEL_COLOR[level] if level else LEVEL_COLOR["none"]
                ax.plot([t["ci_low"], t["ci_high"]], [y, y], color=color, linewidth=1.5, solid_capstyle="round")
                ax.plot(t["median_diff"], y, marker="o", markersize=5, color=color,
                        markerfacecolor=color if t["significant"] else SURFACE, markeredgewidth=1.2,
                        markeredgecolor=color, zorder=3)
        title = panel if family != "C2" else f"{panel} − better component"
        ax.set_title(f"{title}+R − {panel}" if family == "C3" else title, loc="left")
        ax.set_xlabel(f"median Δ {metric.upper() if metric == 'ap' else 'top-1'} (95% CI)")
    axes[0][0].set_yticks(range(len(names)), list(reversed(names)))
    handles = [Line2D([], [], marker="o", color=TEXT_2, markerfacecolor=TEXT_2, linestyle="", label="significant (Holm)"),
               Line2D([], [], marker="o", color=TEXT_2, markerfacecolor=SURFACE, linestyle="", label="not significant")]
    if family == "C3":
        handles = [Line2D([], [], color=LEVEL_COLOR[lv], marker="o", label=f"{lv} reference") for lv in LEVELS_C3] + handles
    _frame(fig, {"C1": "C1 · visual vs. geometric evidence", "C2": "C2 · hybrids vs. their better component",
                 "C3": "C3 · what the reference adds"}[family], label, handles, len(handles))
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    name = f"{family.lower()}_{metric}.png"
    fig.savefig(out / name, dpi=200)
    plt.close(fig)
    return name


LEVELS_C3 = ("exact", "degraded")


def pareto_grid(out: Path, trade: list[dict], conditions: list, label: str) -> str | None:
    if not trade:
        return None
    grids = list(dict.fromkeys(c[0] for c in conditions))
    variants = list(dict.fromkeys((c[1], c[2]) for c in conditions))
    fig, axes = plt.subplots(len(grids), len(variants), figsize=(2.6 * len(variants), 2.4 * len(grids)),
                             sharey=True, squeeze=False)
    for i, grid in enumerate(grids):
        for j, (cx, wear) in enumerate(variants):
            ax = axes[i][j]
            pts = [r for r in trade if (r["grid"], r["complexity"], r["wear"]) == (grid, cx, wear)
                   and math.isfinite(r["median_ap"]) and math.isfinite(r["median_t_total"]) and r["median_t_total"] > 0]
            front = sorted((r for r in pts if r["front_ap_time"]), key=lambda r: r["median_t_total"])
            if len(front) > 1:
                ax.plot([r["median_t_total"] for r in front], [r["median_ap"] for r in front],
                        color=GRID, linewidth=1.5, zorder=1)
            for r in pts:
                method, level = _split_arm(r["arm"])
                ax.scatter(r["median_t_total"], r["median_ap"], marker=METHOD_MARKER[method], s=30,
                           color=LEVEL_COLOR[level], edgecolors=SURFACE, linewidths=1.0, zorder=3)
            for r in front:
                ax.annotate(r["arm"].replace(" (", "\n("), (r["median_t_total"], r["median_ap"]),
                            textcoords="offset points", xytext=(4, -2), fontsize=5.5, color=TEXT_2)
            ax.set_xscale("log")
            _plain_log_axis(ax)
            ax.set_ylim(0, 1.02)
            ax.set_title(f"{grid} · complexity {cx}% · wear {wear}", loc="left", fontsize=7.5)
            if i == len(grids) - 1:
                ax.set_xlabel("median t_total (s, log)")
            if j == 0:
                ax.set_ylabel("median AP")
    handles = [Line2D([], [], color=c, marker="o", linestyle="", label=f"{lv} reference") for lv, c in LEVEL_COLOR.items()]
    handles += [Line2D([], [], color=TEXT_2, marker=m, linestyle="", label=k) for k, m in METHOD_MARKER.items()]
    _frame(fig, "C5 · quality vs. runtime (labeled: Pareto front)", label, handles, 3)
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    name = "c5_pareto_time.png"
    fig.savefig(out / name, dpi=200)
    plt.close(fig)
    return name


def draw_all(out: Path, tests: list[dict], trade: list[dict], conditions: list, label: str) -> list[str]:
    names = []
    for family in ("C1", "C2", "C3"):
        for metric in ("ap", "top1"):
            name = forest(out, tests, family, metric, conditions, label)
            if name:
                names.append(name)
    name = pareto_grid(out, trade, conditions, label)
    if name:
        names.append(name)
    return names
