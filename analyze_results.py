"""
analyze_results.py
Compare baseline.csv vs adaptive.csv and produce a comparison chart +
summary statistics for your project report / demo.

    python3 analyze_results.py --baseline baseline.csv --adaptive adaptive.csv --out comparison.png
"""

import argparse
import csv
import matplotlib.pyplot as plt


def load_csv(path):
    times, cpu, ram, overloaded = [], [], [], []
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return times, cpu, ram, overloaded
    t0 = float(rows[0]["timestamp"])
    for row in rows:
        times.append(float(row["timestamp"]) - t0)
        cpu.append(float(row["cpu_percent"]))
        ram.append(float(row["ram_percent"]))
        overloaded.append(int(row["overloaded"]))
    return times, cpu, ram, overloaded


def summarize(label, cpu, overloaded):
    avg_cpu = sum(cpu) / len(cpu) if cpu else 0
    overload_periods = sum(overloaded)
    print(f"{label}: avg CPU={avg_cpu:.1f}%  overloaded samples={overload_periods}/{len(cpu)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="baseline.csv")
    parser.add_argument("--adaptive", default="adaptive.csv")
    parser.add_argument("--out", default="comparison.png")
    args = parser.parse_args()

    bt, bcpu, bram, bover = load_csv(args.baseline)
    at, acpu, aram, aover = load_csv(args.adaptive)

    summarize("Baseline", bcpu, bover)
    summarize("Adaptive", acpu, aover)

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(bt, bcpu, label="Baseline CPU %")
    axes[0].plot(at, acpu, label="Adaptive CPU %")
    axes[0].axhline(85, color="red", linestyle="--", linewidth=0.8, label="Overload threshold")
    axes[0].set_ylabel("CPU %")
    axes[0].legend()
    axes[0].set_title("CPU Utilization: Baseline vs Adaptive Management")

    axes[1].plot(bt, bram, label="Baseline RAM %")
    axes[1].plot(at, aram, label="Adaptive RAM %")
    axes[1].set_ylabel("RAM %")
    axes[1].set_xlabel("Time (s)")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(args.out)
    print("Saved chart to", args.out)


if __name__ == "__main__":
    main()
