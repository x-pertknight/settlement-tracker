#!/usr/bin/env python3
"""Draw the four release charts. Every number below is copied from a result file named next to it.
Usage: python3 -I 13_charts.py <out_dir>"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
BG, BLUE, ORANGE, INK, MUTED, GRID = "#fcfcfb", "#2a78d6", "#ea6a35", "#111111", "#555555", "#e2e2e2"
plt.rcParams.update({"text.parse_math": False, "font.family": "DejaVu Sans", "font.size": 14, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": INK, "figure.facecolor": BG, "axes.facecolor": BG})


def hbar(ax, labels, values, color, fmt, xmax):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=color, height=0.6, zorder=2)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels)
    for yi, v in zip(y, values):
        ax.text(v + xmax * 0.015, yi, fmt(v), va="center", fontsize=13, color=INK)
    ax.set_xlim(0, xmax); ax.grid(axis="x", color=GRID, zorder=0)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)


def finish(fig, title, note, name):
    fig.text(0.01, 0.97, title, fontsize=19, fontweight="bold", va="top", color=INK)
    fig.text(0.01, 0.02, note, fontsize=11, color=MUTED, va="bottom", wrap=True)
    fig.savefig(os.path.join(OUT, name), dpi=110); plt.close(fig)


# 1. Path mix. Source: data/stage2/s2_summary.json path_share_s1 (n = 53,801).
fig, ax = plt.subplots(figsize=(16.4, 7.8)); fig.subplots_adjust(left=0.36, right=0.97, top=0.82, bottom=0.2)
hbar(ax, ["UMA, direct adapter (inferred)", "UMA, neg-risk route, operator no delay (inferred)",
          "No resolver in Gamma data (short crypto up/down)", "Protocol V2 aggregator (documented)",
          "UMA, legacy route, operator 1 h delay (inferred)", "Other"],
     [64.8, 16.8, 15.4, 2.0, 0.9, 0.1], BLUE, lambda v: f"{v:.1f}%", 78)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
finish(fig, "Who resolves Polymarket markets",
       "Share of Polymarket markets closed 17 Nov 2025 to 17 Nov 2026, equal-probability sample, n = 53,801. Inferred = mapped from "
       "verified contract source and on-chain pointers, not confirmed by Polymarket. The aggregator path is documented by Polymarket.",
       "1_path_mix.png")

# 2. Outcome changed after a dispute. Source: data/disputes/disputes_final.json.
fig, ax = plt.subplots(figsize=(16.4, 7.1)); fig.subplots_adjust(left=0.31, right=0.97, top=0.8, bottom=0.21)
hbar(ax, ["UMA direct (n = 636)", "UMA neg-risk route (n = 283)", "UMA legacy route (n = 11)", "All (n = 930)"],
     [28.6, 14.5, 9.1, 24.1], BLUE, lambda v: f"{v:.1f}%", 36)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
finish(fig, "Disputed Polymarket markets: 24% settled on a different outcome than first proposed",
       "Of disputed markets that had settled by 17 Nov 2026 (930 of 1,037; 107 still open are not counted), the share whose final outcome "
       "differs from the first proposed answer. On-chain UMA events, 11 Oct to 17 Nov 2026. Disputes are 0.07% of 1.43M questions proposed in the same window.",
       "2_disputes.png")

# 3. Median lag by category. Polymarket: data/stage7/s7_pm_lag.json pm_lag_by_cat. Kalshi: data/stage4/kalshi_trades.jsonl.gz.
LOG_T = [3, 15, 60, 240, 1440, 5760]; LOG_L = ["3 min", "15 min", "1 h", "4 h", "1 d", "4 d"]
def fmt_min(v):
    return f"{v:.0f} min" if v < 60 else f"{v/60:.1f} h"
fig, axes = plt.subplots(1, 2, figsize=(20, 7.6)); fig.subplots_adjust(left=0.1, right=0.98, top=0.8, bottom=0.2, wspace=0.4)
pm = [("Crypto (n 391)", 12.6), ("Macro (n 50)", 122.4), ("Sports (n 553)", 241.8), ("Weather (n 269)", 622.8), ("Politics (n 31)", 1453.8)]
ka = [("Crypto (n 25)", 2.5), ("Sports (n 25)", 4.0), ("Commodities (n 25)", 63.8), ("Weather (n 43)", 70.6),
      ("Economics (n 25)", 561.2), ("Entertainment (n 25)", 1072.5)]
for ax, data, color, sub in ((axes[0], pm, BLUE, "Polymarket: end date to settlement"), (axes[1], ka, ORANGE, "Kalshi: close to settlement")):
    labels = [a for a, _ in data]; vals = [b for _, b in data]; y = list(range(len(labels)))[::-1]
    ax.barh(y, vals, color=color, height=0.6, zorder=2)
    ax.set_xscale("log"); ax.set_xlim(1, 8000); ax.set_xticks(LOG_T); ax.set_xticklabels(LOG_L)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    for yi, v in zip(y, vals): ax.text(v * 1.25, yi, fmt_min(v), va="center", fontsize=13, color=INK)
    ax.grid(axis="x", color=GRID, zorder=0); ax.tick_params(axis="y", length=0)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.set_title(sub, loc="left", fontsize=15, color=INK)
finish(fig, "Median settlement lag by category (two venues, two different start points)",
       "Polymarket: scheduled markets on the two main UMA paths, closed 17 Nov 2025 to 17 Nov 2026, weighted. Kalshi: category-balanced sample of "
       "traded non-combo markets closed 18 Sep to 17 Nov 2026 (25 per category, 43 weather). Polymarket counts from the end date, Kalshi from "
       "the close, and categories are defined differently on each venue: read each panel on its own. Small n per bar.",
       "3_lag_by_category.png")

# 4. Money waiting. Source: data/stage6/s6_pm_limbo.json and data/stage4/s4_kalshi_results.json (snapshot).
fig, ax = plt.subplots(figsize=(16.4, 6.5)); fig.subplots_adjust(left=0.36, right=0.97, top=0.78, bottom=0.25)
hbar(ax, ["Polymarket: one election-results market", "Polymarket: the other 59 markets", "Kalshi: closed > 3 days, not settled"],
     [5.03, 0.04, 0.70], BLUE, lambda v: f"${v:.2f}M", 6.2)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:.0f}M"))
finish(fig, "Waiting more than 3 days for settlement: $5.8M, and $5.0M of it is one market",
       "Snapshot 18 Nov 2026 ~06:00 UTC. Polymarket: priced open interest in markets proposed or disputed on UMA more than 3 days after the end date; "
       "the large one is a multi-state election-results market whose end date is election day. Kalshi: contracts x notional. "
       "A further ~$5.2M is in normal settlement (under 3 days) or in early proposals on markets not yet past their end date.",
       "4_money_waiting.png")
print("charts written to", OUT)
