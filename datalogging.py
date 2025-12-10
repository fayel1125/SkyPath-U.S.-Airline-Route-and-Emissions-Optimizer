from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(".")
DATA = ROOT / "dataset"
CACHE = ROOT / "cache"
CACHE.mkdir(exist_ok=True)

COUPON_CSV = DATA / "Origin_and_Destination_Survey_DB1BCoupon_2025_1.csv"
TICKET_CSV = DATA / "Origin_and_Destination_Survey_DB1BTicket_2025_1.csv"
FLIGHTS_CSV = DATA / "Copy of U.S. Flights Data - 2022 to 2025 - Flight Dataset.csv"


def quarter_from_year_month(year: int, month: int) -> str:
    q = (int(month) - 1) // 3 + 1
    return f"{int(year)}_Q{q}"

def quarter_from_year_quarter(year: int, quarter: int) -> str:
    return f"{int(year)}_Q{int(quarter)}"

def safe_read_csv(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    if usecols is not None:
        head = pd.read_csv(path, nrows=0)
        keep = [c for c in usecols if c in head.columns]
        return pd.read_csv(path, usecols=keep)
    return pd.read_csv(path)


def load_coupon_2025() -> pd.DataFrame:

    use = [
        "ItinID","Origin","Dest","TkCarrier","Distance",
        "Year","Quarter"
    ]
    df = safe_read_csv(COUPON_CSV, use)
    for c in ["Origin","Dest","TkCarrier"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    df["quarter_tag"] = df.apply(
        lambda r: quarter_from_year_quarter(r["Year"], r["Quarter"]), axis=1
    )
    return df

def load_ticket_2025() -> pd.DataFrame:

    use = ["ItinID","Passengers","ItinFare","Distance","MilesFlown"]
    t = safe_read_csv(TICKET_CSV, use)
    if "Distance" not in t.columns and "MilesFlown" in t.columns:
        t = t.rename(columns={"MilesFlown":"Distance"})
    return t

def load_flights_delay_2022_2025() -> pd.DataFrame:

    use = ["Date","Carrier","Origin","Dest","Delay","Cancelled"]
    f = safe_read_csv(FLIGHTS_CSV, use)
    # parse date
    dt = pd.to_datetime(f["Date"], errors="coerce")
    f["Year"] = dt.dt.year
    f["Month"] = dt.dt.month
    f["quarter_tag"] = [quarter_from_year_month(y, m) if pd.notna(y) and pd.notna(m) else None
                        for y, m in zip(f["Year"], f["Month"])]
    f = f.dropna(subset=["Origin","Dest","quarter_tag"])

    f["is_delayed"] = (f["Delay"].fillna(0) > 0).astype(int)
    f["is_cancelled"] = f["Cancelled"].fillna(0).astype(int)
    f["is_bad"] = ((f["is_delayed"] == 1) | (f["is_cancelled"] == 1)).astype(int)

    agg = (f.groupby(["Origin","Dest","quarter_tag"], as_index=False)
             .agg(flights=("is_bad","size"),
                  bad=("is_bad","sum"),
                  avg_delay=("Delay", lambda s: pd.to_numeric(s, errors="coerce").clip(lower=0).mean())))
    agg["delay_rate"] = (agg["bad"] / agg["flights"]).replace([np.inf, -np.inf], np.nan)
    return agg


def build_edges_2025() -> pd.DataFrame:
    c = load_coupon_2025()
    t = load_ticket_2025()
    m = c.merge(t, on="ItinID", how="left", suffixes=("", "_t"))

    m["fare_x_pax"] = pd.to_numeric(m["ItinFare"], errors="coerce") * pd.to_numeric(m["Passengers"], errors="coerce")
    carriers = (m.groupby(["Origin","Dest","quarter_tag"])["TkCarrier"]
                  .apply(lambda s: ",".join(sorted(pd.Series(s).dropna().astype(str).str.strip().unique())))
                  .reset_index()
                  .rename(columns={"TkCarrier":"carriers"}))

    cpax = (m.dropna(subset=["TkCarrier"])
              .groupby(["Origin","Dest","quarter_tag","TkCarrier"], as_index=False)["Passengers"].sum())
    if not cpax.empty:
        idx = cpax.groupby(["Origin","Dest","quarter_tag"])["Passengers"].idxmax()
        primary = (cpax.loc[idx, ["Origin","Dest","quarter_tag","TkCarrier"]]
                        .rename(columns={"TkCarrier":"primary_carrier"}))
    else:
        primary = pd.DataFrame(columns=["Origin","Dest","quarter_tag","primary_carrier"])

    agg_db1b = (m.groupby(["Origin","Dest","quarter_tag"], as_index=False)
                  .agg(passengers=("Passengers","sum"),
                       fare_num=("fare_x_pax","sum"),
                       coupon_avg_miles=("Distance","mean")))

    agg_db1b["wavg_itin_fare_usd"] = (agg_db1b["fare_num"] / agg_db1b["passengers"]).replace([np.inf, -np.inf], np.nan)
    agg_db1b["avg_distance_miles"] = agg_db1b["coupon_avg_miles"]

    otp = load_flights_delay_2022_2025()

    edges = (agg_db1b.merge(otp, on=["Origin","Dest","quarter_tag"], how="left")
                      .merge(carriers, on=["Origin","Dest","quarter_tag"], how="left")
                      .merge(primary, on=["Origin","Dest","quarter_tag"], how="left"))

    km = pd.to_numeric(edges["avg_distance_miles"], errors="coerce") * 1.60934
    edges["est_emissions_kgco2"] = km * 0.115

    need_pc = edges["primary_carrier"].isna() | (edges["primary_carrier"].astype(str).str.strip() == "")
    edges.loc[need_pc & edges["carriers"].notna(), "primary_carrier"] = (
        edges.loc[need_pc & edges["carriers"].notna(), "carriers"].astype(str).str.split(",").str[0].str.strip()
    )

    keep = [
        "Origin","Dest","quarter_tag","passengers","wavg_itin_fare_usd","avg_distance_miles",
        "est_emissions_kgco2","flights","bad","avg_delay","delay_rate","carriers","primary_carrier"
    ]
    for col in keep:
        if col not in edges.columns:
            edges[col] = np.nan
    return edges[keep].sort_values(["Origin","Dest","quarter_tag"]).reset_index(drop=True)


def build_nodes_from_edges(edges: pd.DataFrame) -> pd.DataFrame:

    origins = edges[["Origin"]].rename(columns={"Origin":"Airport"})
    dests   = edges[["Dest"]].rename(columns={"Dest":"Airport"})
    airports = pd.concat([origins, dests], axis=0).dropna().drop_duplicates().reset_index(drop=True)

    def explode_carriers(df, col_air):
        df2 = df[[col_air, "carriers","primary_carrier"]].copy()
        lst = []
        for _, r in df2.iterrows():
            items = []
            if isinstance(r.get("carriers"), str) and r["carriers"].strip():
                items.extend([x.strip() for x in r["carriers"].split(",") if x.strip()])
            pc = r.get("primary_carrier")
            if isinstance(pc, str) and pc.strip():
                items.append(pc.strip())
            items = sorted(set(items))
            lst.append(items)
        df2["carrier_list"] = lst
        return df2

    out_car = explode_carriers(edges.rename(columns={"Origin":"Airport"}), "Airport")
    in_car  = explode_carriers(edges.rename(columns={"Dest":"Airport"}), "Airport")

    def union_lists(series):
        s = set()
        for lst in series:
            s |= set(lst or [])
        return sorted(s)

    out_car_g = (out_car.groupby("Airport")["carrier_list"]
                      .apply(union_lists).reset_index().rename(columns={"carrier_list":"carriers_out"}))
    in_car_g  = (in_car.groupby("Airport")["carrier_list"]
                      .apply(union_lists).reset_index().rename(columns={"carrier_list":"carriers_in"}))

    node_df = airports.merge(out_car_g, on="Airport", how="left").merge(in_car_g, on="Airport", how="left")
    node_df["carriers_out"] = node_df["carriers_out"].apply(lambda x: x if isinstance(x, list) else [])
    node_df["carriers_in"]  = node_df["carriers_in"].apply(lambda x: x if isinstance(x, list) else [])
    node_df["carriers_serving"] = node_df.apply(lambda r: sorted(set(r["carriers_out"]) | set(r["carriers_in"])), axis=1)

    def top3_for_airport(ap):
        mask = (edges["Origin"] == ap) | (edges["Dest"] == ap)
        s = []
        for _, r in edges.loc[mask, ["carriers","primary_carrier"]].iterrows():
            if isinstance(r["carriers"], str) and r["carriers"].strip():
                s += [x.strip() for x in r["carriers"].split(",") if x.strip()]
            if isinstance(r["primary_carrier"], str) and r["primary_carrier"].strip():
                s.append(r["primary_carrier"].strip())
        if not s:
            return []
        counts = pd.Series(s).value_counts()
        return counts.index.tolist()[:3]

    node_df["top3_carriers"] = node_df["Airport"].apply(top3_for_airport)

    deg_out = (edges.groupby("Origin")["Dest"].nunique().rename("deg_out")).reset_index().rename(columns={"Origin":"Airport"})
    deg_in  = (edges.groupby("Dest")["Origin"].nunique().rename("deg_in")).reset_index().rename(columns={"Dest":"Airport"})
    node_df = node_df.merge(deg_out, on="Airport", how="left").merge(deg_in, on="Airport", how="left")
    node_df["deg_out"] = node_df["deg_out"].fillna(0).astype(int)
    node_df["deg_in"]  = node_df["deg_in"].fillna(0).astype(int)
    node_df["deg"]     = node_df["deg_out"] + node_df["deg_in"]

    out_stats = (edges.groupby("Origin", as_index=False)
                      .agg(avg_out_fare=("wavg_itin_fare_usd","mean"),
                           avg_out_delay=("delay_rate","mean"),
                           avg_out_distance=("avg_distance_miles","mean")))
    out_stats = out_stats.rename(columns={"Origin":"Airport"})
    node_df = node_df.merge(out_stats, on="Airport", how="left")

    cols = [
        "Airport","deg","deg_out","deg_in",
        "carriers_serving","top3_carriers","carriers_out","carriers_in",
        "avg_out_fare","avg_out_delay","avg_out_distance"
    ]
    for c in cols:
        if c not in node_df.columns:
            node_df[c] = np.nan
    return node_df[cols].sort_values("Airport").reset_index(drop=True)


def to_json_records(df: pd.DataFrame, path: Path):
    path.parent.mkdir(exist_ok=True)
    df.to_json(path, orient="records")


def main():
    print(f"[DB1B] Loading {COUPON_CSV.name} + {TICKET_CSV.name}")
    print(f"[OTP ] Loading {FLIGHTS_CSV.name}")

    edges = build_edges_2025()
    nodes = build_nodes_from_edges(edges)

    rich_cols = [
        "Origin","Dest","quarter_tag","passengers","wavg_itin_fare_usd","avg_distance_miles",
        "delay_rate","avg_delay","flights","bad","est_emissions_kgco2","carriers","primary_carrier"
    ]
    edges_rich = edges[rich_cols]

    min_cols = [
        "Origin","Dest","avg_distance_miles","wavg_itin_fare_usd",
        "delay_rate","est_emissions_kgco2","quarter_tag","primary_carrier"
    ]
    edges_min = edges[min_cols]

    to_json_records(edges_rich, CACHE / "edges_2025.json")
    to_json_records(edges_min,  CACHE / "edges_min_2025.json")
    to_json_records(nodes,      CACHE / "nodes_2025.json")

    print("wrote cache/edges_2025.json and cache/edges_min_2025.json")
    print("wrote cache/nodes_2025.json (nodes include carriers_serving & top3_carriers)")

if __name__ == "__main__":
    main()
