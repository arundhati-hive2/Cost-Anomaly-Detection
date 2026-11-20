"""Streamlit front end for the invoice anomaly checker."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from checker import COURIERS, check_courier, summarise

SAMPLE_FILE = Path(__file__).parent / "sample_data" / "sample_invoices.xlsx"

st.set_page_config(page_title="Invoice Anomaly Checker", page_icon="🧾", layout="wide")

st.title("Invoice Anomaly Checker")
st.caption(
    "Compare what carriers billed with what your rate cards say they should have billed. "
    "Rows that look wrong are flagged. Rows that cannot be priced go to a review list."
)

with st.sidebar:
    st.header("Settings")
    tolerance = st.slider(
        "Flag when billed differs from expected by more than (%)", 0.0, 15.0, 2.0, 0.5
    )
    target = st.number_input(
        "Target freight cost as % of invoice value (0 to skip)", 0.0, 50.0, 3.0, 0.5
    )
    st.markdown("**Carriers set up**")
    for name in COURIERS:
        st.markdown(f"- {name}")
    st.caption(
        "The demo rate cards in checker/config.py are invented. Replace them with your own "
        "and keep that file private."
    )

uploaded = st.file_uploader("Upload an Excel workbook, one sheet per carrier", type=["xlsx"])
use_sample = st.checkbox("Use the built in sample workbook instead", value=not uploaded)

source = None
label = ""
if uploaded:
    source, label = uploaded, uploaded.name
elif use_sample and SAMPLE_FILE.exists():
    source, label = SAMPLE_FILE, SAMPLE_FILE.name

if source is None:
    st.info("Upload a workbook, or tick the sample option, to begin.")
    st.stop()

if st.button("Run checks", type="primary"):
    workbook = pd.ExcelFile(source)
    results, reviews, skipped, failed = {}, {}, [], {}

    for sheet in workbook.sheet_names:
        courier = COURIERS.get(sheet)
        if courier is None:
            skipped.append(sheet)
            continue
        try:
            raw = pd.read_excel(workbook, sheet_name=sheet)
            res, rev = check_courier(
                raw,
                courier,
                tolerance_pct=tolerance,
                target_cost_pct=target or None,
            )
            results[sheet] = res
            reviews[sheet] = rev
        except Exception as exc:  # keep going so one bad sheet does not stop the rest
            failed[sheet] = str(exc)

    st.session_state["run"] = {
        "label": label,
        "results": results,
        "reviews": reviews,
        "skipped": skipped,
        "failed": failed,
    }

run = st.session_state.get("run")
if not run:
    st.stop()

st.subheader(f"Results for {run['label']}")

summary = summarise(run["results"], run["reviews"])
if summary.empty:
    st.warning("No sheet matched a configured carrier name.")
else:
    totals = st.columns(4)
    totals[0].metric("Shipments checked", int(summary["Shipments checked"].sum()))
    totals[1].metric("Overcharged", int(summary["Overcharged"].sum()))
    totals[2].metric("Total overcharge", f"{summary['Total overcharge'].sum():,.2f}")
    totals[3].metric("Needs review", int(summary["Needs review"].sum()))
    st.dataframe(summary, hide_index=True, width="stretch")

if run["skipped"]:
    st.caption("Skipped sheets with no matching carrier: " + ", ".join(run["skipped"]))
if run["failed"]:
    st.error("Some sheets failed and were skipped.")
    st.json(run["failed"])

for name, res in run["results"].items():
    with st.expander(name, expanded=False):
        flagged = res[res["status"].isin(["Overcharged", "Undercharged"])] if len(res) else res
        st.markdown(f"**{len(flagged)} flagged** of {len(res)} checked")
        st.dataframe(flagged if len(flagged) else res.head(10), width="stretch")
        rev = run["reviews"].get(name)
        if rev is not None and len(rev):
            st.markdown(f"**{len(rev)} need review**")
            st.dataframe(rev, width="stretch")

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="Summary", index=False)
    for name, res in run["results"].items():
        res.to_excel(writer, sheet_name=name[:31], index=False)
    for name, rev in run["reviews"].items():
        if len(rev):
            rev.to_excel(writer, sheet_name=(name + " review")[:31], index=False)

st.download_button(
    "Download results as Excel",
    data=buffer.getvalue(),
    file_name="invoice_check_results.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
