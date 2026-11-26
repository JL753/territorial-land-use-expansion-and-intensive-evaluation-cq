"""Evaluate construction-land expansion and intensive use from a district panel."""

import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


METRICS = {
    "population_density": "population",
    "gdp_density": "gdp_10k_cny",
    "secondary_density": "secondary_10k_cny",
}
INPUTS = {"code", "district", "year", "admin_km2", "built_km2", *METRICS.values()}


def load_panel(path):
    panel = pd.read_csv(path, dtype={"district": "string", "code": "string"})
    missing = INPUTS.difference(panel.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    panel["district"] = panel["district"].str.strip()
    if panel.empty or panel["district"].isna().any() or panel["district"].eq("").any():
        raise ValueError("Provide observations with nonempty district names.")
    if not panel["code"].str.fullmatch(r"[0-9]{6}", na=False).all():
        raise ValueError("code must contain six digits.")
    if panel.groupby("code")["district"].nunique().gt(1).any():
        raise ValueError("Use one district name per code.")
    for column in sorted(INPUTS - {"district", "code"}):
        panel[column] = pd.to_numeric(panel[column], errors="raise")
        if not np.isfinite(panel[column].to_numpy(dtype=float)).all():
            raise ValueError(f"{column} must contain only finite numbers.")
    years = panel["year"]
    if ((years < 1) | (years > 9999) | (years % 1 != 0)).any():
        raise ValueError("year must contain integer calendar years.")
    panel["year"] = years.astype(int)
    if panel.duplicated(["code", "year"]).any():
        raise ValueError("Each district and year must be unique.")
    if (panel["built_km2"] <= 0).any() or (panel["built_km2"] > panel["admin_km2"]).any():
        raise ValueError("Require 0 < built_km2 <= admin_km2.")
    for source in METRICS.values():
        if (panel[source] <= 0).any():
            raise ValueError(f"{source} must be positive.")
    if panel["year"].nunique() < 2:
        raise ValueError("Supply at least two distinct years.")
    if panel.groupby("code")["year"].nunique().ne(panel["year"].nunique()).any():
        raise ValueError("Each district must cover the same set of years.")
    if panel.groupby("code")["admin_km2"].nunique().gt(1).any():
        raise ValueError("Use constant administrative area per district across years.")
    return panel.sort_values(["code", "year"]).reset_index(drop=True)


def evaluate(panel):
    results = panel.copy()
    by_district = results.groupby("code", sort=False)
    years = by_district["year"].diff()
    baseline = by_district["built_km2"].shift()
    growth = results["built_km2"] - baseline
    results["interval_start"] = by_district["year"].shift().astype("Int64")
    results["expansion_km2"] = growth
    results["annual_growth_pct"] = 100 * ((results["built_km2"] / baseline) ** (1 / years) - 1)
    results["annual_expansion_intensity_pct"] = 100 * growth / (results["admin_km2"] * years)

    normalized = pd.DataFrame(index=results.index)
    for metric, source in METRICS.items():
        values = results[source] / results["built_km2"]
        results[metric] = values
        span = values.max() - values.min()
        if span > 0:
            normalized[metric] = (values - values.min()) / span
    if normalized.empty:
        raise ValueError("All indicators are constant across the study panel.")

    proportions = normalized / normalized.sum()
    log_proportions = np.log(proportions.where(proportions > 0, 1))
    divergence = 1 + (proportions * log_proportions).sum() / np.log(len(normalized))
    weights = (divergence / divergence.sum()).reindex(METRICS.keys(), fill_value=0)
    active_weights = weights.loc[normalized.columns]
    results["intensive_score"] = topsis(normalized, active_weights)
    results["equal_weight_score"] = topsis(normalized, 1 / len(active_weights))
    results["rank"] = results.groupby("year")["intensive_score"].rank(method="min", ascending=False).astype(int)
    results["equal_weight_rank"] = results.groupby("year")["equal_weight_score"].rank(method="min", ascending=False).astype(int)
    return results, weights


def topsis(normalized, weights):
    weighted = normalized * weights
    positive = np.sqrt(((weighted - weighted.max()) ** 2).sum(axis=1))
    negative = np.sqrt(((weighted - weighted.min()) ** 2).sum(axis=1))
    return negative / (positive + negative)


def write_outputs(results, weights, directory, data_kind):
    directory.mkdir(parents=True, exist_ok=True)
    results.insert(0, "data_kind", data_kind)
    results.to_csv(directory / "district_year.csv", index=False)
    weights.rename_axis("indicator").rename("weight").reset_index().assign(
        data_kind=data_kind
    ).to_csv(directory / "weights.csv", index=False)
    fig, (expansion, use) = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for code, rows in results.groupby("code", sort=False):
        expansion.plot(rows["year"], rows["built_km2"], marker="o", label=code)
        use.plot(rows["year"], rows["intensive_score"], marker="o")
    for axis in (expansion, use):
        axis.set_xticks(sorted(results["year"].unique()))
        axis.set_xlabel("Year")
        axis.grid(alpha=0.25)
    expansion.set_ylabel("Construction land (km²)")
    use.set_ylabel("Intensive-use score")
    fig.legend(*expansion.get_legend_handles_labels(), loc="outside lower center", ncol=min(7, results["code"].nunique()))
    fig.suptitle(f"{data_kind.upper()} DATA | Land expansion and intensive use")
    intervals = results.dropna(subset=["interval_start"])
    associations = [
        {"start": start, "end": end, "districts": len(rows), "data_kind": data_kind,
         "spearman_rho": rows["annual_expansion_intensity_pct"].rank().corr(rows["intensive_score"].rank())}
        for (start, end), rows in intervals.groupby(["interval_start", "year"])
    ]
    pd.DataFrame(associations).to_csv(directory / "association.csv", index=False)
    fig.savefig(directory / "trends.png", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-kind", choices=("demo", "observed"), required=True)
    args = parser.parse_args()
    try:
        results, weights = evaluate(load_panel(args.panel))
        write_outputs(results, weights, args.output, args.data_kind)
    except (ValueError, OSError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
