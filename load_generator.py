"""
load_generator.py
Synthetic workload generator so you can demonstrate low -> medium ->
high -> burst load phases on the machine you're monitoring.

Run this in a SECOND terminal while main.py is running in the first one.
"""

import argparse
import multiprocessing
import time


def cpu_burn(seconds):
    end = time.time() + seconds
    x = 0
    while time.time() < end:
        x = (x + 1) * 2 % 999999999


def memory_hog(mb, seconds):
    block = bytearray(mb * 1024 * 1024)
    time.sleep(seconds)
    del block


def run_phase(name, workers, seconds, mem_mb=0):
    print(f"--- Phase: {name} ({workers} CPU workers, {seconds}s) ---")
    procs = [multiprocessing.Process(target=cpu_burn, args=(seconds,)) for _ in range(workers)]
    if mem_mb:
        procs.append(multiprocessing.Process(target=memory_hog, args=(mem_mb, seconds)))
    for p in procs:
        p.start()
    for p in procs:
        p.join()


def main():
    parser = argparse.ArgumentParser(description="Generate low/medium/high/burst workload phases")
    parser.add_argument("--phase-seconds", type=int, default=20)
    args = parser.parse_args()

    cores = multiprocessing.cpu_count()
    run_phase("LOW", workers=max(1, cores // 4), seconds=args.phase_seconds)
    run_phase("MEDIUM", workers=max(1, cores // 2), seconds=args.phase_seconds, mem_mb=100)
    run_phase("HIGH", workers=cores, seconds=args.phase_seconds, mem_mb=300)
    run_phase("BURST", workers=cores * 2, seconds=args.phase_seconds // 2, mem_mb=500)
    print("Workload generation complete.")


if __name__ == "__main__":
    main()
