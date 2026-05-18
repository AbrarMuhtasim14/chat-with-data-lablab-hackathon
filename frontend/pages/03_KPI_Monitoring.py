# frontend/pages/03_KPI_Monitoring.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

"""
KPI Monitoring & Anomaly Detection — AtliQ Hospitality

Features:
  1. Threshold-based alerts (configurable per KPI)
  2. WoW trend detection (consecutive declines)
  3. Statistical anomaly detection (z-score across properties)
  4. Per-property health scoring
  5. Alert severity system (Critical / Warning / Watch)
  6. Drill-down: which property, which metric, which week
  7. Forecasting: 3-week linear projection per metric
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from utils.metrics_engine import (
    get_core_metrics,
    get_all_wow_deltas,
    get_latest_full_week,
    get_db_context,
    get_trend_data,
    get_metric_by_dimension,
    get_multi_metric_by_dimension,
    get_property_table,
    build_dashboard_filters,
)


# ════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════



st.markdown("""
<style>
    .alert-critical {
        background-color: #FFE0E0;
        border-left: 5px solid #FF4444;
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 4px;
    }
    .alert-warning {
        background-color: #FFF3E0;
        border-left: 5px solid #FF9800;
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 4px;
    }
    .alert-watch {
        background-color: #E3F2FD;
        border-left: 5px solid #2196F3;
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════
# THRESHOLD CONFIGURATION
# ════════════════════════════════════════════════

DEFAULT_THRESHOLDS = {
    "occupancy_pct": {
        "label": "Occupancy %",
        "critical_low": 45.0,
        "warning_low": 55.0,
        "target": 65.0,
        "format": "{:.1f}%",
    },
    "adr": {
        "label": "ADR",
        "critical_low": 8000.0,
        "warning_low": 10000.0,
        "target": 12500.0,
        "format": "₹{:,.0f}",
    },
    "revpar": {
        "label": "RevPAR",
        "critical_low": 4000.0,
        "warning_low": 5500.0,
        "target": 7500.0,
        "format": "₹{:,.0f}",
    },
    "realisation_pct": {
        "label": "Realisation %",
        "critical_low": 65.0,
        "warning_low": 70.0,
        "target": 75.0,
        "format": "{:.1f}%",
    },
    "cancellation_pct": {
        "label": "Cancellation %",
        "critical_high": 30.0,
        "warning_high": 25.0,
        "target": 20.0,
        "format": "{:.1f}%",
        "inverse": True,
    },
    "average_rating": {
        "label": "Avg Rating",
        "critical_low": 3.0,
        "warning_low": 3.5,
        "target": 4.0,
        "format": "{:.2f}",
    },
}


# ════════════════════════════════════════════════
# LOAD DATA
# ════════════════════════════════════════════════

@st.cache_data(ttl=120)
def load_monitoring_data():
    ctx = get_db_context()
    if "error" in ctx:
        return None, None, None, None, ctx
    latest_week = ctx.get("latest_full_week")
    overall = get_core_metrics()
    wow = get_all_wow_deltas(latest_week) if latest_week else {}
    prop_table = get_property_table()
    trend_metrics = ["revenue", "occupancy_pct", "adr", "revpar", "realisation_pct"]
    trends = {}
    for m in trend_metrics:
        df = get_trend_data(m)
        if df is not None and not df.empty:
            df["week_sort"] = df["week_no"].astype(int)
            df = df.sort_values("week_sort")
            trends[m] = df
    return overall, wow, prop_table, trends, ctx


overall, wow, prop_table, trends, ctx = load_monitoring_data()

if overall is None:
    st.error(f"Failed to load data: {ctx.get('error', 'Unknown error')}")
    st.stop()

latest_week = ctx.get("latest_full_week", "N/A")


# ════════════════════════════════════════════════
# ALERT ENGINE
# ════════════════════════════════════════════════

def run_threshold_alerts(metrics, thresholds):
    alerts = []
    for key, config in thresholds.items():
        val = metrics.get(key, 0)
        label = config["label"]
        fmt = config["format"]
        formatted_val = fmt.format(val) if val else "N/A"
        if config.get("inverse", False):
            if "critical_high" in config and val >= config["critical_high"]:
                alerts.append({"severity": "critical", "icon": "🔴", "kpi": label,
                    "message": f"{label} at {formatted_val} — exceeds critical threshold ({fmt.format(config['critical_high'])})",
                    "value": val, "threshold": config["critical_high"]})
            elif "warning_high" in config and val >= config["warning_high"]:
                alerts.append({"severity": "warning", "icon": "🟡", "kpi": label,
                    "message": f"{label} at {formatted_val} — above warning threshold ({fmt.format(config['warning_high'])})",
                    "value": val, "threshold": config["warning_high"]})
        else:
            if "critical_low" in config and val <= config["critical_low"]:
                alerts.append({"severity": "critical", "icon": "🔴", "kpi": label,
                    "message": f"{label} at {formatted_val} — below critical threshold ({fmt.format(config['critical_low'])})",
                    "value": val, "threshold": config["critical_low"]})
            elif "warning_low" in config and val <= config["warning_low"]:
                alerts.append({"severity": "warning", "icon": "🟡", "kpi": label,
                    "message": f"{label} at {formatted_val} — below warning threshold ({fmt.format(config['warning_low'])})",
                    "value": val, "threshold": config["warning_low"]})
    return alerts


def run_wow_alerts(wow_deltas):
    alerts = []
    wow_thresholds = {
        "revenue": ("Revenue", -10.0, -5.0), "occupancy": ("Occupancy", -8.0, -4.0),
        "adr": ("ADR", -10.0, -5.0), "revpar": ("RevPAR", -12.0, -6.0),
        "realisation": ("Realisation", -5.0, -3.0),
    }
    for key, (label, critical_drop, warning_drop) in wow_thresholds.items():
        delta_str = wow_deltas.get(key, "N/A")
        if delta_str == "N/A":
            continue
        try:
            val = float(delta_str.replace("%", "").replace("+", ""))
        except (ValueError, AttributeError):
            continue
        if val <= critical_drop:
            alerts.append({"severity": "critical", "icon": "📉", "kpi": f"{label} WoW",
                "message": f"{label} dropped {delta_str} WoW (critical: {critical_drop}%)",
                "value": val, "threshold": critical_drop})
        elif val <= warning_drop:
            alerts.append({"severity": "warning", "icon": "📉", "kpi": f"{label} WoW",
                "message": f"{label} dropped {delta_str} WoW (warning: {warning_drop}%)",
                "value": val, "threshold": warning_drop})
    return alerts


def run_trend_alerts(trends):
    alerts = []
    trend_labels = {
        "revenue": "Revenue", "occupancy_pct": "Occupancy",
        "adr": "ADR", "revpar": "RevPAR", "realisation_pct": "Realisation",
    }
    for key, label in trend_labels.items():
        df = trends.get(key)
        if df is None or len(df) < 3:
            continue
        val_col = [c for c in df.columns if c not in ("week_no", "week_sort", "week_label")][0]
        values = df[val_col].tolist()
        decline_streak = 0
        for i in range(len(values) - 1, 0, -1):
            if values[i] < values[i - 1]:
                decline_streak += 1
            else:
                break
        if decline_streak >= 4:
            alerts.append({"severity": "critical", "icon": "📊", "kpi": f"{label} Trend",
                "message": f"{label} declined {decline_streak} consecutive weeks — investigate root cause",
                "value": decline_streak, "threshold": 4})
        elif decline_streak >= 3:
            alerts.append({"severity": "warning", "icon": "📊", "kpi": f"{label} Trend",
                "message": f"{label} declined {decline_streak} consecutive weeks — monitor closely",
                "value": decline_streak, "threshold": 3})
    return alerts


def run_property_anomaly_detection(prop_table):
    alerts = []
    if prop_table is None or prop_table.empty:
        return alerts
    anomaly_metrics = {
        "occupancy_pct": ("Occupancy", "{:.1f}%"),
        "adr": ("ADR", "₹{:,.0f}"),
        "revpar": ("RevPAR", "₹{:,.0f}"),
        "realisation_pct": ("Realisation", "{:.1f}%"),
        "average_rating": ("Rating", "{:.2f}"),
    }
    for col, (label, fmt) in anomaly_metrics.items():
        if col not in prop_table.columns:
            continue
        values = pd.to_numeric(prop_table[col], errors="coerce").dropna()
        if len(values) < 3:
            continue
        mean_val = values.mean()
        std_val = values.std()
        if std_val == 0:
            continue
        for idx in values.index:
            val = values[idx]
            z_score = (val - mean_val) / std_val
            prop_name = prop_table.loc[idx, "property_name"] if "property_name" in prop_table.columns else f"Property {idx}"
            if z_score <= -2.0:
                alerts.append({"severity": "critical", "icon": "🏨",
                    "kpi": f"{label} — {prop_name}",
                    "message": f"{prop_name}: {label} at {fmt.format(val)} — significantly below average ({fmt.format(mean_val)}), z={z_score:.1f}",
                    "value": val, "threshold": mean_val - 2 * std_val,
                    "property": prop_name, "z_score": z_score})
            elif z_score <= -1.5:
                alerts.append({"severity": "watch", "icon": "🏨",
                    "kpi": f"{label} — {prop_name}",
                    "message": f"{prop_name}: {label} at {fmt.format(val)} — below average ({fmt.format(mean_val)}), z={z_score:.1f}",
                    "value": val, "threshold": mean_val - 1.5 * std_val,
                    "property": prop_name, "z_score": z_score})
    return alerts


def compute_property_health_scores(prop_table):
    if prop_table is None or prop_table.empty:
        return pd.DataFrame()
    weights = {
        "occupancy_pct": 0.25, "revpar": 0.25, "adr": 0.15,
        "realisation_pct": 0.15, "average_rating": 0.20,
    }
    result = prop_table.copy()
    score_total = pd.Series(0.0, index=result.index)
    weight_total = 0.0
    for col, weight in weights.items():
        if col not in result.columns:
            continue
        values = pd.to_numeric(result[col], errors="coerce")
        max_val, min_val = values.max(), values.min()
        normalized = pd.Series(50.0, index=result.index) if max_val == min_val else \
                     ((values - min_val) / (max_val - min_val)) * 100
        score_total += normalized.fillna(0) * weight
        weight_total += weight
    result["health_score"] = (score_total / weight_total).round(1) if weight_total > 0 else 0.0
    result["health_status"] = result["health_score"].apply(
        lambda s: "🟢 Healthy" if s >= 80 else ("🟡 Concern" if s >= 60 else "🔴 Critical")
    )
    return result.sort_values("health_score", ascending=True)


# ════════════════════════════════════════════════
# FORECASTING ENGINE
# ════════════════════════════════════════════════

def forecast_metric(values: list, periods_ahead: int = 3):
    """Linear regression forecast using numpy polyfit."""
    y = np.array(values, dtype=float)
    mask = ~np.isnan(y)
    if mask.sum() < 3:
        return []
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    future_x = np.arange(len(y), len(y) + periods_ahead)
    return (slope * future_x + intercept).tolist()


def render_forecast_chart(trend_df, metric_key, periods_ahead=3):
    """Trend chart with historical actuals + dashed forecast. No new data fetch needed."""
    if trend_df is None or trend_df.empty:
        st.info("No trend data available.")
        return

    val_col = [c for c in trend_df.columns
               if c not in ("week_no", "week_sort", "week_label")][0]
    trend_df = trend_df.copy()
    trend_df["week_label"] = "W" + trend_df["week_no"].astype(str)

    hist_values = trend_df[val_col].tolist()
    hist_labels = trend_df["week_label"].tolist()

    fcast_values = forecast_metric(hist_values, periods_ahead)
    last_week_no = int(trend_df["week_no"].iloc[-1])
    fcast_labels = [f"W{last_week_no + i + 1}" for i in range(periods_ahead)]

    connect_x = [hist_labels[-1]] + fcast_labels
    connect_y = [hist_values[-1]] + fcast_values
    baseline_mean = np.nanmean(hist_values)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=hist_labels, y=hist_values,
        mode="lines+markers", name="Actual",
        line=dict(color="#5D5FEF", width=3),
        marker=dict(size=8),
        hovertemplate="Week %{x}<br>Actual: %{y:,.2f}<extra></extra>",
    ))

    if fcast_values:
        fig.add_trace(go.Scatter(
            x=connect_x, y=connect_y,
            mode="lines+markers", name="Forecast",
            line=dict(color="#FF6B6B", width=2.5, dash="dash"),
            marker=dict(size=8, symbol="diamond"),
            hovertemplate="Week %{x}<br>Forecast: %{y:,.2f}<extra></extra>",
        ))
        fig.add_vrect(
            x0=connect_x[0], x1=connect_x[-1],
            fillcolor="rgba(255,107,107,0.07)", line_width=0,
            annotation_text="Forecast zone", annotation_position="top left",
            annotation_font_size=11, annotation_font_color="#FF6B6B",
        )

    fig.add_hline(
        y=baseline_mean, line_dash="dot", line_color="#888888", line_width=1,
        annotation_text=f"Avg: {baseline_mean:,.1f}",
        annotation_position="bottom right", annotation_font_size=10,
    )

    threshold = DEFAULT_THRESHOLDS.get(metric_key, {})
    if "warning_low" in threshold:
        fig.add_hline(y=threshold["warning_low"], line_dash="dash", line_color="#FF9800",
                      annotation_text="Warning", annotation_position="top right")
    if "critical_low" in threshold:
        fig.add_hline(y=threshold["critical_low"], line_dash="dash", line_color="#FF4444",
                      annotation_text="Critical", annotation_position="top right")
    if "target" in threshold:
        fig.add_hline(y=threshold["target"], line_dash="dot", line_color="#4CAF50",
                      annotation_text="Target", annotation_position="top right")

    fig.update_layout(
        xaxis_title="Week",
        yaxis_title=metric_key.replace("_", " ").title(),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=370, margin=dict(t=40, b=40, l=60, r=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    if fcast_values:
        fcast_df = pd.DataFrame({
            "Week": fcast_labels,
            "Forecast": [f"{v:,.2f}" for v in fcast_values],
            "vs Historical Avg": [
                f"{'▲' if v > baseline_mean else '▼'} {abs(v - baseline_mean) / baseline_mean * 100:.1f}%"
                for v in fcast_values
            ],
        })
        st.dataframe(fcast_df, hide_index=True, use_container_width=True)


# ════════════════════════════════════════════════
# RUN ALL ALERTS
# ════════════════════════════════════════════════

all_alerts = []
all_alerts.extend(run_threshold_alerts(overall, DEFAULT_THRESHOLDS))
all_alerts.extend(run_wow_alerts(wow))
all_alerts.extend(run_trend_alerts(trends))
all_alerts.extend(run_property_anomaly_detection(prop_table))

severity_order = {"critical": 0, "warning": 1, "watch": 2}
all_alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

critical_count = sum(1 for a in all_alerts if a["severity"] == "critical")
warning_count  = sum(1 for a in all_alerts if a["severity"] == "warning")
watch_count    = sum(1 for a in all_alerts if a["severity"] == "watch")


# ════════════════════════════════════════════════
# PAGE LAYOUT
# ════════════════════════════════════════════════

st.title("🔍 KPI Monitoring & Anomaly Detection")
st.caption(f"Last analysis: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Latest full week: {latest_week}")
st.markdown("---")

# ── SECTION 1: Alert Summary ──
st.subheader("📋 Alert Summary")
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Total Alerts", len(all_alerts))
with c2: st.metric("🔴 Critical",  critical_count)
with c3: st.metric("🟡 Warning",   warning_count)
with c4: st.metric("🔵 Watch",     watch_count)
st.markdown("---")

# ── SECTION 2: Active Alerts ──
st.subheader("🚨 Active Alerts")
if not all_alerts:
    st.success("✅ All KPIs within normal range. No alerts triggered.")
else:
    severity_filter = st.multiselect(
        "Filter by severity:",
        options=["critical", "warning", "watch"],
        default=["critical", "warning"],
        format_func=lambda x: {"critical": "🔴 Critical", "warning": "🟡 Warning", "watch": "🔵 Watch"}[x],
    )
    filtered = [a for a in all_alerts if a["severity"] in severity_filter]
    for alert in filtered:
        st.markdown(
            f'<div class="alert-{alert["severity"]}">'
            f'{alert["icon"]} <strong>{alert["kpi"]}</strong>: {alert["message"]}'
            f'</div>', unsafe_allow_html=True,
        )
    if not filtered:
        st.info("No alerts match the selected severity filters.")
st.markdown("---")

# ── SECTION 3: KPI Health vs Thresholds ──
st.subheader("📊 KPI Health vs Thresholds")
h1, h2, h3 = st.columns(3)
kpi_display = [
    ("occupancy_pct",    "Occupancy %",    "{:.1f}%"),
    ("adr",              "ADR",            "₹{:,.0f}"),
    ("revpar",           "RevPAR",         "₹{:,.0f}"),
    ("realisation_pct",  "Realisation %",  "{:.1f}%"),
    ("cancellation_pct", "Cancellation %", "{:.1f}%"),
    ("average_rating",   "Avg Rating",     "{:.2f}"),
]
for i, (key, label, fmt) in enumerate(kpi_display):
    col = [h1, h2, h3][i % 3]
    val = overall.get(key, 0)
    ti = DEFAULT_THRESHOLDS.get(key, {})
    inv = ti.get("inverse", False)
    status = ("🔴" if val >= ti.get("critical_high", float("inf")) else
              "🟡" if val >= ti.get("warning_high", float("inf")) else "🟢") if inv else \
             ("🔴" if val <= ti.get("critical_low", 0) else
              "🟡" if val <= ti.get("warning_low", 0) else "🟢")
    wow_key = {"occupancy_pct": "occupancy", "realisation_pct": "realisation"}.get(key, key)
    wow_val = wow.get(wow_key, "N/A")
    with col:
        st.metric(label=f"{status} {label}", value=fmt.format(val),
                  delta=wow_val if wow_val != "N/A" else None)
        target = ti.get("target")
        if target:
            gap = val - target if not inv else target - val
            st.caption(f"Target: {fmt.format(target)} ({abs(gap):.1f} {'above' if gap >= 0 else 'below'})")
st.markdown("---")

# ── SECTION 4: Trend Analysis ──
st.subheader("📈 Trend Analysis")
trend_metric = st.selectbox(
    "Select metric:",
    options=["revenue", "occupancy_pct", "adr", "revpar", "realisation_pct"],
    format_func=lambda x: {"revenue": "Revenue", "occupancy_pct": "Occupancy %",
                            "adr": "ADR", "revpar": "RevPAR", "realisation_pct": "Realisation %"}[x],
)
trend_df = trends.get(trend_metric)
if trend_df is not None and not trend_df.empty:
    val_col = [c for c in trend_df.columns if c not in ("week_no", "week_sort", "week_label")][0]
    trend_df = trend_df.copy()
    trend_df["week_label"] = "W" + trend_df["week_no"].astype(str)
    trend_df["prev_val"]   = trend_df[val_col].shift(1)
    trend_df["wow_change"] = ((trend_df[val_col] / trend_df["prev_val"]) - 1) * 100
    trend_df["color"]      = trend_df["wow_change"].apply(
        lambda x: "#4CAF50" if pd.notna(x) and x >= 0 else "#FF4444")

    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(
        x=trend_df["week_label"], y=trend_df[val_col],
        mode="lines+markers", line=dict(color="#5D5FEF", width=3),
        marker=dict(size=10, color=trend_df["color"].tolist()),
        hovertemplate="Week %{x}<br>Value: %{y:,.2f}<extra></extra>", name=trend_metric,
    ))
    thr = DEFAULT_THRESHOLDS.get(trend_metric, {})
    if "warning_low" in thr:
        fig_t.add_hline(y=thr["warning_low"], line_dash="dash", line_color="#FF9800",
                        annotation_text="Warning", annotation_position="top right")
    if "critical_low" in thr:
        fig_t.add_hline(y=thr["critical_low"], line_dash="dash", line_color="#FF4444",
                        annotation_text="Critical", annotation_position="top right")
    if "target" in thr:
        fig_t.add_hline(y=thr["target"], line_dash="dot", line_color="#4CAF50",
                        annotation_text="Target", annotation_position="top right")
    fig_t.update_layout(xaxis_title="Week", yaxis_title=trend_metric.replace("_", " ").title(),
                        height=350, margin=dict(t=30, b=40, l=60, r=20), hovermode="x unified")
    st.plotly_chart(fig_t, use_container_width=True)

    wow_data = trend_df.dropna(subset=["wow_change"])
    if not wow_data.empty:
        fig_w = go.Figure()
        fig_w.add_trace(go.Bar(
            x=wow_data["week_label"], y=wow_data["wow_change"],
            marker_color=wow_data["color"].tolist(),
            text=wow_data["wow_change"].apply(lambda x: f"{x:+.1f}%"), textposition="outside",
        ))
        fig_w.update_layout(xaxis_title="Week", yaxis_title="WoW Change %",
                             height=250, margin=dict(t=20, b=40, l=60, r=20))
        fig_w.add_hline(y=0, line_color="gray", line_width=1)
        st.plotly_chart(fig_w, use_container_width=True)
else:
    st.info("No trend data available for selected metric.")
st.markdown("---")

# ── SECTION 4b: Forecasting ──
st.subheader("🔮 3-Week Forecast")
st.caption(
    "Linear regression projection based on historical weekly trend. "
    "Dashed line = predicted direction. Use for early planning, not precision targets."
)
forecast_metric_key = st.selectbox(
    "Select metric to forecast:",
    options=["revenue", "occupancy_pct", "adr", "revpar", "realisation_pct"],
    format_func=lambda x: {"revenue": "Revenue", "occupancy_pct": "Occupancy %",
                            "adr": "ADR", "revpar": "RevPAR", "realisation_pct": "Realisation %"}[x],
    key="forecast_selector",
)
render_forecast_chart(trends.get(forecast_metric_key), forecast_metric_key, periods_ahead=3)
st.markdown("---")

# ── SECTION 5: Property Health Scores ──
st.subheader("🏢 Property Health Scores")
health_df = compute_property_health_scores(prop_table)
if not health_df.empty:
    ph1, ph2 = st.columns([2, 1])
    with ph1:
        display_cols = ["property_name", "city", "health_score", "health_status"]
        for extra in ["occupancy_pct", "revpar", "adr", "realisation_pct", "average_rating"]:
            if extra in health_df.columns:
                display_cols.append(extra)
        display_health = health_df[[c for c in display_cols if c in health_df.columns]].copy()
        rename_map = {
            "property_name": "Property", "city": "City", "health_score": "Score",
            "health_status": "Status", "occupancy_pct": "Occupancy", "revpar": "RevPAR",
            "adr": "ADR", "realisation_pct": "Realisation", "average_rating": "Rating",
        }
        display_health = display_health.rename(
            columns={k: v for k, v in rename_map.items() if k in display_health.columns})
        st.dataframe(display_health, hide_index=True, use_container_width=True, height=400)
    with ph2:
        health_counts = health_df["health_status"].value_counts()
        fig_pie = px.pie(
            values=health_counts.values, names=health_counts.index,
            color=health_counts.index,
            color_discrete_map={"🟢 Healthy": "#4CAF50", "🟡 Concern": "#FF9800", "🔴 Critical": "#FF4444"},
            hole=0.5,
        )
        fig_pie.update_traces(textposition="inside", textinfo="value+label")
        fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=300)
        st.plotly_chart(fig_pie, use_container_width=True)
        total = len(health_df)
        st.caption(f"Healthy: {len(health_df[health_df['health_score'] >= 80])}/{total}")
        st.caption(f"Concern: {len(health_df[(health_df['health_score'] >= 60) & (health_df['health_score'] < 80)])}/{total}")
        st.caption(f"Critical: {len(health_df[health_df['health_score'] < 60])}/{total}")
else:
    st.info("No property data available for health scoring.")
st.markdown("---")

# ── SECTION 6: Threshold Configuration ──
with st.expander("⚙️ Configure Alert Thresholds", expanded=False):
    st.markdown("Adjust thresholds to match your business targets.")
    st.caption("Changes apply only for the current session.")
    config_cols = st.columns(3)
    for i, (key, config) in enumerate(DEFAULT_THRESHOLDS.items()):
        col = config_cols[i % 3]
        with col:
            st.markdown(f"**{config['label']}**")
            if config.get("inverse"):
                DEFAULT_THRESHOLDS[key]["warning_high"] = st.number_input(
                    "Warning (≥)", value=float(config.get("warning_high", 25.0)), key=f"warn_{key}", step=1.0)
                DEFAULT_THRESHOLDS[key]["critical_high"] = st.number_input(
                    "Critical (≥)", value=float(config.get("critical_high", 30.0)), key=f"crit_{key}", step=1.0)
            else:
                DEFAULT_THRESHOLDS[key]["warning_low"] = st.number_input(
                    "Warning (≤)", value=float(config.get("warning_low", 0.0)), key=f"warn_{key}", step=1.0)
                DEFAULT_THRESHOLDS[key]["critical_low"] = st.number_input(
                    "Critical (≤)", value=float(config.get("critical_low", 0.0)), key=f"crit_{key}", step=1.0)
            DEFAULT_THRESHOLDS[key]["target"] = st.number_input(
                "Target", value=float(config.get("target", 0.0)), key=f"target_{key}", step=1.0)
            st.markdown("---")
    if st.button("🔄 Re-run Analysis with New Thresholds"):
        st.rerun()

# ════════════════════════════════════════════════
# FOOTER
# ════════════════════════════════════════════════
st.markdown("---")
st.caption(
    f"📊 Monitoring {len(prop_table) if prop_table is not None else 0} properties | "
    f"{len(all_alerts)} alerts active | "
    f"Data through week {latest_week} | "
    f"Powered by Gemini 2.5 Flash"
)