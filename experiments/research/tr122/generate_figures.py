from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Paths
DATA_DIR = Path("PublishReady/data/tr122_v2")
FIGURES_DIR = DATA_DIR / "figures"
POWER_TRACE_PATH = DATA_DIR / "power_trace.csv"
METADATA_PATH = DATA_DIR / "run_metadata.json"
BASELINE_PATH = DATA_DIR / "baseline.json"

FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Set style
plt.style.use("seaborn-v0_8-darkgrid")
sns.set_context("paper", font_scale=1.4)


def load_data():
    print(f"Loading data from {POWER_TRACE_PATH}...")
    df = pd.read_csv(POWER_TRACE_PATH)
    # Relative time in seconds
    df["time_rel_s"] = (df["t_ns"] - df["t_ns"].iloc[0]) / 1e9
    return df


def plot_baseline_power(df):
    """Plot 1: Baseline Power Time Series with Floor Marking"""
    print("Generating Figure 1: Baseline Power Time Series...")

    # Assume baseline is first ~204 seconds (2041 samples)
    # Or strict cutoff: t < 205
    baseline_df = df[df["time_rel_s"] <= 205].copy()

    plt.figure(figsize=(12, 6))

    # Plot all points
    plt.plot(
        baseline_df["time_rel_s"],
        baseline_df["power_w"],
        alpha=0.6,
        label="Power (W)",
        color="#2c3e50",
        linewidth=1,
    )

    # Highlight floor samples
    floor_mask = baseline_df["power_w"] < 5.0
    plt.scatter(
        baseline_df.loc[floor_mask, "time_rel_s"],
        baseline_df.loc[floor_mask, "power_w"],
        color="#e74c3c",
        s=20,
        label="Floor/Suspect (<5W)",
        zorder=5,
    )

    plt.title("Baseline Power Calibration (V2.0)")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (W)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig1_baseline_time_series.png", dpi=300)
    plt.close()


def plot_baseline_histogram(df):
    """Plot 2: Baseline Power Histogram/KDE"""
    print("Generating Figure 2: Baseline Power Histogram...")

    baseline_df = df[df["time_rel_s"] <= 205].copy()

    plt.figure(figsize=(10, 6))

    sns.histplot(
        baseline_df["power_w"],
        bins=50,
        kde=True,
        color="#3498db",
        edgecolor="white",
        alpha=0.7,
    )

    # Annotate modes
    mean_val = baseline_df["power_w"].mean()
    plt.axvline(
        mean_val, color="#e74c3c", linestyle="--", label=f"Mean: {mean_val:.2f}W"
    )
    plt.axvline(
        1.2, color="#f1c40f", linestyle=":", linewidth=2, label="Sensor Floor (1.2W)"
    )

    plt.title("Baseline Power Distribution (N=2041)")
    plt.xlabel("Power (W)")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig2_baseline_histogram.png", dpi=300)
    plt.close()


def plot_heat_soak(df):
    """Plot 3: Heat Soak Temperature & Slope"""
    print("Generating Figure 3: Heat Soak Thermal Profile...")

    # Heat soak is likely the whole trace or the segment after baseline/response
    # We'll plot the whole trace Temp

    plt.figure(figsize=(12, 8))

    # Primary Axis: Temperature
    ax1 = plt.gca()
    ax1.plot(
        df["time_rel_s"],
        df["temp_c"],
        color="#e67e22",
        linewidth=2,
        label="Temperature (°C)",
    )
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Temperature (°C)", color="#e67e22")
    ax1.tick_params(axis="y", labelcolor="#e67e22")

    # Secondary Axis: Slope (dT/dt) - Rolling 60s
    # Calculate slope: delta_T / delta_t over 60s window (600 samples)
    # Simple finite diff is noisy. Use rolling LinReg slope if possible, or simple delta.
    # We'll use simple delta over 60s for visualization

    df["dt_60s"] = df["temp_c"].diff(periods=600) * (
        60.0 / 60.0
    )  # Deg per minute approx if 10Hz
    # Actually: (T[i] - T[i-600]) / (t[i] - t[i-600]) * 60

    # More robust:
    # slope = df['temp_c'].rolling(600).apply(lambda x: np.polyfit(np.arange(len(x)), x, 1)[0] * 600, raw=True)
    # That's slow. Let's stick to simple delta over 1 minute window (600 samples)

    samples_per_min = 600
    df["rolling_slope"] = df["temp_c"].diff(samples_per_min)  # delta T over 1 min

    ax2 = ax1.twinx()
    ax2.plot(
        df["time_rel_s"],
        df["rolling_slope"],
        color="#95a5a6",
        alpha=0.5,
        label="Slope (°C/min)",
    )
    ax2.axhline(
        0.5, color="red", linestyle="--", alpha=0.5, label="Stability Threshold (0.5)"
    )
    ax2.set_ylabel("Slope (°C/min)", color="#7f8c8d")
    ax2.tick_params(axis="y", labelcolor="#7f8c8d")

    plt.title("Heat Soak: Temperature & Stability")

    # Combine legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig3_heat_soak.png", dpi=300)
    plt.close()


def plot_dt_histogram(df):
    """Plot 4: Poller dt Histogram"""
    print("Generating Figure 4: Poller dt Histogram...")

    # Filter dt (remove init gap > 0.5)
    dt_ms = df["dt_s"] * 1000
    dt_clean = dt_ms[dt_ms < 500]

    plt.figure(figsize=(10, 6))
    sns.histplot(dt_clean, bins=100, color="#8e44ad", kde=False)

    plt.axvline(
        100.0, color="green", linestyle="-", linewidth=2, label="Target (100ms)"
    )

    plt.title("Poller Scheduling Jitter (Bimodal Correction)")
    plt.xlabel("Delta Time (ms)")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fig4_dt_histogram.png", dpi=300)
    plt.close()


def main():
    if not POWER_TRACE_PATH.exists():
        print(f"Error: {POWER_TRACE_PATH} not found.")
        return

    df = load_data()

    plot_baseline_power(df)
    plot_baseline_histogram(df)
    plot_heat_soak(df)
    plot_dt_histogram(df)

    print(f"All figures saved to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
