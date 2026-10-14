"""
main.py
Ties Monitor -> Analyzer -> Adaptive Manager together and logs results.

Run it in two modes to produce the "with vs without adaptive management"
comparison the project asks for:

    python3 main.py --mode baseline --duration 60 --out baseline.csv
    python3 main.py --mode adaptive --duration 60 --out adaptive.csv

Then compare the two CSV files with analyze_results.py.
"""

import argparse
import csv
import time

from monitor import ResourceMonitor
from analyzer import ResourceAnalyzer
from adaptive_manager import AdaptiveManager


def main():
    parser = argparse.ArgumentParser(description="Resource-aware adaptive Linux monitor")
    parser.add_argument("--mode", choices=["baseline", "adaptive"], default="adaptive")
    parser.add_argument("--duration", type=int, default=60, help="seconds to run")
    parser.add_argument("--interval", type=float, default=1.0, help="sampling interval (s)")
    parser.add_argument("--out", default="results.csv")
    args = parser.parse_args()

    monitor = ResourceMonitor(interval=args.interval)
    analyzer = ResourceAnalyzer()
    manager = AdaptiveManager(own_pid=None)  # defaults to this process's own PID

    monitor.start()
    print(f"[{args.mode}] monitoring started for {args.duration}s -> {args.out}")

    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "cpu_percent", "ram_percent", "disk_percent",
                          "status", "triggers", "overloaded", "action"])

        start = time.time()
        try:
            while time.time() - start < args.duration:
                snap = monitor.snapshot()
                verdict = analyzer.classify(snap)
                actions = manager.decide(verdict, adaptive_enabled=(args.mode == "adaptive"))
                action_text = " | ".join(actions)

                print(f"t={int(time.time() - start):3d}s  "
                      f"CPU={verdict['cpu_percent']:5.1f}%  "
                      f"RAM={verdict['ram_percent']:5.1f}%  "
                      f"[{verdict['status']}]  {action_text}")

                writer.writerow([
                    round(time.time(), 2),
                    verdict["cpu_percent"],
                    verdict["ram_percent"],
                    verdict["disk_percent"],
                    verdict["status"],
                    "+".join(verdict["triggers"]),
                    int(verdict["status"] == "OVERLOAD"),
                    action_text,
                ])
                f.flush()
                time.sleep(max(0, args.interval))
        except KeyboardInterrupt:
            pass
    monitor.stop()
    print("Done. Results saved to", args.out)


if __name__ == "__main__":
    main()
