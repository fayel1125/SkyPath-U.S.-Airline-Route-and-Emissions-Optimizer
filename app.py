from __future__ import annotations
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import networkx as nx
from networkx.algorithms.simple_paths import shortest_simple_paths

CACHE = Path("cache")

@st.cache_data
def load_edges_nodes():
    e = pd.read_json(CACHE / "edges_min_2025.json")
    n = pd.read_json(CACHE / "nodes_2025.json")

    defaults = {
        "avg_distance_miles": np.nan,
        "wavg_itin_fare_usd": np.nan,
        "delay_rate": np.nan,
        "est_emissions_kgco2": np.nan,
        "quarter_tag": "",
        "primary_carrier": "",
        "carriers": "",            
    }
    for c, v in defaults.items():
        if c not in e.columns:
            e[c] = v

    need_pc = (e["primary_carrier"].astype(str).str.strip() == "") & (e["carriers"].astype(str).str.strip() != "")
    e.loc[need_pc, "primary_carrier"] = (
        e.loc[need_pc, "carriers"].astype(str).str.split(",").str[0].str.strip()
    )
    return e, n

def build_graph(edges: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    for _, r in edges.iterrows():
        u, v = r["Origin"], r["Dest"]
        if isinstance(u, str) and isinstance(v, str):
            G.add_edge(
                u, v,
                distance=float(r.get("avg_distance_miles") or 0.0),
                fare=float(r.get("wavg_itin_fare_usd") or 0.0),
                delay=float(r.get("delay_rate") if pd.notna(r.get("delay_rate")) else 0.0),
                co2=float(r.get("est_emissions_kgco2") or 0.0),
                primary_carrier=(r.get("primary_carrier") or ""),
                carriers=(r.get("carriers") or ""),
            )
    return G

def metric_key(name: str) -> str:
    return {
        "Distance (miles)": "distance",
        "Fare (USD)": "fare",
        "Delay rate": "delay",
        "Emissions (kgCO2)": "co2",
    }[name]

def route_cost(G: nx.DiGraph, path: list[str], weight: str) -> float:
    return float(sum(G[path[i]][path[i+1]].get(weight, 0.0) for i in range(len(path)-1)))

def leg_carrier(edges_df: pd.DataFrame, u: str, v: str) -> str:
    mask = (edges_df["Origin"] == u) & (edges_df["Dest"] == v)
    if not mask.any():
        return ""
    if "primary_carrier" in edges_df.columns:
        s = edges_df.loc[mask, "primary_carrier"].dropna()
        if not s.empty and s.iloc[0].strip():
            return s.iloc[0].strip()
    if "carriers" in edges_df.columns:
        s = edges_df.loc[mask, "carriers"].dropna()
        if not s.empty and s.iloc[0].strip():
            return s.iloc[0].split(",")[0].strip()
    return ""

def summarize_carriers(leg_carriers: list[str], topn: int = 3) -> str:
    counts = Counter([c for c in leg_carriers if c])
    if not counts:
        return "N/A"
    top = counts.most_common(topn)
    if len(top) == 1 or top[0][1] > top[1][1]:
        return top[0][0]
    return "No clear winner · top-3: " + ", ".join([c for c, _ in top])

def k_shortest_with_fallbacks(
    edges_raw: pd.DataFrame,
    edges_filtered: pd.DataFrame,
    s: str,
    t: str,
    weight: str,
    k: int,
    price_range: tuple[int, int],
    max_delay: float,
):
    attempts = []
    attempts.append(("filtered", edges_filtered))

    e_price_only = edges_raw[
        (edges_raw["wavg_itin_fare_usd"].fillna(np.inf) >= price_range[0]) &
        (edges_raw["wavg_itin_fare_usd"].fillna(np.inf) <= price_range[1])
    ]
    attempts.append(("price-only", e_price_only))

    e_delay_only = edges_raw[(edges_raw["delay_rate"].fillna(0.0) <= 1.0)]
    attempts.append(("delay-only", e_delay_only))

    attempts.append(("no-filters", edges_raw))

    for label, e in attempts:
        G_try = build_graph(e)
        if s not in G_try.nodes or t not in G_try.nodes:
            continue
        try:
            gen = shortest_simple_paths(G_try, s, t, weight=weight)
            paths = [p for _, p in zip(range(k), gen)]
            if paths:
                return paths, label, G_try
        except nx.NetworkXNoPath:
            pass

    G_all_und = build_graph(edges_raw).to_undirected()
    if s in G_all_und and t in G_all_und:
        try:
            path = nx.shortest_path(G_all_und, s, t)
            return [path], "undirected-fallback", G_all_und
        except nx.NetworkXNoPath:
            pass

    return [], "no-path", None

st.set_page_config(page_title="SkyPath — Route & Emissions Optimizer", layout="wide")

edges_raw, nodes = load_edges_nodes()
if edges_raw.empty:
    st.error("No edges found. Run your builder to generate cache/edges_min_2025.json.")
    st.stop()

st.markdown("## SkyPath — U.S. Airline Route & Emissions Optimizer")

all_airports = sorted(set(edges_raw["Origin"]).union(edges_raw["Dest"]))
c1, c2, c3, c4 = st.columns([1.1, 1.1, 1.0, 1.0])
with c1:
    origin = st.selectbox("Origin", options=all_airports, index=0)
with c2:
    dest = st.selectbox("Destination", options=all_airports, index=min(1, len(all_airports)-1))
with c3:
    metric_choice = st.selectbox("Optimize for", ["Distance (miles)", "Fare (USD)", "Delay rate", "Emissions (kgCO2)"])
    weight = metric_key(metric_choice)
with c4:
    k_routes = st.number_input("How many routes?", min_value=1, max_value=10, value=5, step=1)

c5, c6 = st.columns([2,2])
with c5:
    pmin = float(np.nanmin(edges_raw["wavg_itin_fare_usd"]))
    pmax = float(np.nanmax(edges_raw["wavg_itin_fare_usd"]))
    if not np.isfinite(pmin): pmin = 0.0
    if not np.isfinite(pmax): pmax = 2000.0
    price_range = st.slider("Price range (USD)", int(pmin), int(pmax), (int(pmin), min(800, int(pmax))))
with c6:
    max_delay = st.slider("Max delay rate", 0.0, 1.0, 0.4, 0.01)

edges_filtered = edges_raw[
    (edges_raw["wavg_itin_fare_usd"].fillna(np.inf) >= price_range[0]) &
    (edges_raw["wavg_itin_fare_usd"].fillna(np.inf) <= price_range[1]) &
    (edges_raw["delay_rate"].fillna(0.0) <= max_delay)
].copy()

G_filtered = build_graph(edges_filtered)
st.caption(f"**Airports remaining (filtered):** {G_filtered.number_of_nodes()}  |  **Routes remaining:** {G_filtered.number_of_edges()}")

st.divider()

st.subheader("Suggested routes (k-shortest by selected metric)")
paths, used_label, G_used = k_shortest_with_fallbacks(
    edges_raw, edges_filtered, origin, dest, weight, k_routes, price_range, max_delay
)
if not paths:
    st.error("No path exists between these airports in the dataset.")
else:
    rows = []
    G_cost = build_graph(edges_raw)
    for path in paths:
        leg_carriers = [leg_carrier(edges_raw, path[i], path[i+1]) for i in range(len(path)-1)]
        leg_carriers = [c for c in leg_carriers if c]
        suggested = summarize_carriers(leg_carriers, topn=3)
        rows.append({
            "Route": " → ".join(path),
            "Stops": max(0, len(path)-2),
            "Suggested airline": suggested,
            metric_choice: round(route_cost(G_cost, path, weight), 3),
        })
    st.dataframe(pd.DataFrame(rows))
    if used_label != "filtered":
        st.caption(f"Used fallback search: **{used_label}** (filters relaxed to guarantee a path).")

st.divider()

st.subheader("Best path details")
if paths:
    best = paths[0]
    G_cost = G_used if isinstance(G_used, (nx.DiGraph, nx.MultiDiGraph)) else build_graph(edges_raw)
    cost = route_cost(G_cost, best, weight)

    legs, leg_carriers = [], []
    for i in range(len(best)-1):
        u, v = best[i], best[i+1]
        d = (G_cost[u][v] if G_cost.has_edge(u, v) else
             {"distance": np.nan, "fare": np.nan, "delay": np.nan, "co2": np.nan})
        pc = leg_carrier(edges_raw, u, v)
        if pc: leg_carriers.append(pc)
        legs.append({
            "From": u, "To": v, "Carrier": pc if pc else "(n/a)",
            "Distance": d.get("distance", np.nan),
            "FareUSD": d.get("fare", np.nan),
            "DelayRate": d.get("delay", np.nan),
            "CO2 (kg)": d.get("co2", np.nan),
        })
    st.info(f"Best path ({metric_choice}): **{' → '.join(best)}**  |  Stops: {max(0, len(best)-2)}  |  Total {metric_choice}: **{round(cost,3)}**")
    st.write(f"Suggested airline: **{summarize_carriers(leg_carriers, topn=3)}**")
    st.dataframe(pd.DataFrame(legs))

st.divider()

st.subheader(f"Direct connections from {origin} (after filters)")
out_rows = []
if origin in G_filtered:
    for _, v, d in G_filtered.out_edges(origin, data=True):
        out_rows.append({
            "To": v,
            "Carrier": leg_carrier(edges_raw, origin, v) or "(n/a)",
            "Distance": d.get("distance", np.nan),
            "FareUSD": d.get("fare", np.nan),
            "DelayRate": d.get("delay", np.nan),
            "CO2 (kg)": d.get("co2", np.nan),
        })
if out_rows:
    df = pd.DataFrame(out_rows)
    sort_cols = [c for c in ["FareUSD", "Distance"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, na_position="last")
    st.dataframe(df)
else:
    st.info("No direct routes after current filters.")

st.divider()

st.subheader("Airport ranking (degree, filtered)")
und = G_filtered.to_undirected()
deg = pd.Series(dict(und.degree())).rename("degree").sort_values(ascending=False)
st.dataframe(deg.head(20).to_frame())

st.divider()

st.subheader("Sample of filtered edges")
show_cols = [c for c in [
    "Origin","Dest","avg_distance_miles","wavg_itin_fare_usd",
    "delay_rate","est_emissions_kgco2","quarter_tag","primary_carrier","carriers"
] if c in edges_filtered.columns]
st.dataframe(edges_filtered[show_cols].head(300))
