"""
adaptive_manager.py
Adaptive Decision Engine.

Given the analyzer's verdict, decides on SAFE, REVERSIBLE management
actions, so this is safe to run on your own laptop or an EC2 instance
without risking a crash:

  1. RE-PRIORITIZE (CPU overload) - lower the OS scheduling priority
     ("niceness") of the top CPU-consuming, non-critical process, so it
     yields CPU time to everything else. Demonstrates CPU scheduling:
     the OS scheduler gives lower-priority (higher nice value) processes
     less CPU time.
  2. OOM-SCORE ADJUST (RAM overload, Linux only) - raise the top
     memory-consuming process's /proc/[pid]/oom_score_adj, making it a
     more likely candidate if the kernel's OOM killer ever has to act,
     WITHOUT killing anything itself. This is the memory-management
     analogue of #1: it doesn't free RAM by itself, but it correctly
     targets the resource that's actually under pressure (earlier
     versions of this script always looked at the top CPU process even
     when RAM was the overloaded resource, which fixed nothing).
  3. SCALE (simulated) - when overload is sustained across several
     samples, log a "scale-up" recommendation. In a real cloud
     deployment this is where you'd call the AWS/Azure API to resize
     the instance or add a node (see README for the real boto3 call).

IMPORTANT: action #2 only works on Linux with permission to write to
/proc/[pid]/oom_score_adj (your own processes qualify without root).
On Windows/macOS, or without permission, it's logged as unavailable
instead of silently failing.
"""

import os
import platform
import psutil

# Kernel threads and core system daemons we never want to touch.
CRITICAL_NAMES = {
    # Linux
    "systemd", "init", "sshd", "kthreadd", "kworker", "ksoftirqd",
    "migration", "rcu_sched", "rcu_gp", "watchdog",
    # Windows - protected/system-critical processes psutil usually can't
    # (and shouldn't) touch anyway; excluding them avoids repeated
    # AccessDenied noise in the action log.
    "MsMpEng.exe", "svchost.exe", "dwm.exe", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "smss.exe", "System",
}

IS_WINDOWS = platform.system() == "Windows"

# Windows only understands 6 fixed priority CLASSES, not arbitrary
# integers like Unix nice values. Ordered from highest to lowest so we
# can step down the ladder instead of doing Unix-style arithmetic on it
# (that mismatch - adding a Unix-style delta to a Windows class constant
# - is what caused WinError 87 in earlier versions of this script).
if IS_WINDOWS:
    PRIORITY_LADDER = [
        psutil.REALTIME_PRIORITY_CLASS,
        psutil.HIGH_PRIORITY_CLASS,
        psutil.ABOVE_NORMAL_PRIORITY_CLASS,
        psutil.NORMAL_PRIORITY_CLASS,
        psutil.BELOW_NORMAL_PRIORITY_CLASS,
        psutil.IDLE_PRIORITY_CLASS,
    ]


class AdaptiveManager:
    def __init__(self, sustained_threshold=3, own_pid=None):
        self.sustained_threshold = sustained_threshold
        self._overload_streak = 0
        # Never de-prioritize our own monitoring process.
        self.own_pid = own_pid or os.getpid()

    def decide(self, verdict, adaptive_enabled=True):
        actions = []
        status = verdict["status"]
        triggers = verdict["triggers"]  # which resource(s) actually crossed a threshold

        if status == "NORMAL":
            self._overload_streak = 0
            actions.append("No action needed - workload normal.")
            return actions

        if not adaptive_enabled:
            # Baseline mode: monitor only, take no corrective action.
            # This mode exists so you can run the SAME workload twice
            # and compare "with" vs "without" adaptive management.
            actions.append(f"[baseline] {status} detected, no action taken.")
            return actions

        delta = 5 if status == "HIGH" else 10

        # Act on whichever resource(s) actually triggered this status -
        # never on CPU alone just because that's the easiest signal.
        if "cpu" in triggers:
            target = self._pick_target_process(verdict["top_processes_cpu"])
            if target:
                self._renice(target, delta=delta)
                actions.append(f"CPU {status.lower()}: lowered scheduling priority of "
                                f"PID {target[0]} ({target[1]}).")
            else:
                actions.append(f"CPU {status.lower()}, but no safe process to de-prioritize.")

        if "ram" in triggers:
            target = self._pick_target_process(verdict["top_processes_mem"])
            if target:
                ok = self._adjust_oom_score(target, delta=delta * 20)
                if ok:
                    actions.append(f"RAM {status.lower()}: raised OOM-kill priority of "
                                    f"PID {target[0]} ({target[1]}).")
                else:
                    actions.append(f"RAM {status.lower()}: top memory consumer is "
                                    f"PID {target[0]} ({target[1]}) (OOM-score adjustment "
                                    f"unavailable on this OS/without permission).")
            else:
                actions.append(f"RAM {status.lower()}, but no safe process to flag.")

        if status == "OVERLOAD":
            self._overload_streak += 1
            if self._overload_streak >= self.sustained_threshold:
                actions.append("Sustained overload -> RECOMMEND CLOUD SCALE-UP "
                                "(e.g. resize EC2 instance / add a node).")
        else:
            self._overload_streak = 0

        return actions

    def _pick_target_process(self, top_processes):
        for pid, name, cpu, mem in top_processes:
            # Skip PID 1 (init), kernel threads/system daemons, low PIDs
            # (typically boot-time system processes), and our own process.
            if pid in (1, self.own_pid) or pid < 10 or name in CRITICAL_NAMES:
                continue
            return (pid, name, cpu, mem)
        return None

    def _renice(self, target, delta):
        """Lower a process's scheduling priority so it yields CPU to
        everything else. delta is a Unix-style nice-step (5 = 'high'
        alert, 10 = 'overload' alert); on Windows it's translated into
        steps down the fixed priority-class ladder instead."""
        pid = target[0]
        try:
            p = psutil.Process(pid)
            if IS_WINDOWS:
                current = p.nice()
                try:
                    idx = PRIORITY_LADDER.index(current)
                except ValueError:
                    idx = PRIORITY_LADDER.index(psutil.NORMAL_PRIORITY_CLASS)
                steps = 1 if delta <= 5 else 2
                new_idx = min(idx + steps, len(PRIORITY_LADDER) - 1)
                p.nice(PRIORITY_LADDER[new_idx])
            else:
                current = p.nice()
                new_val = min(current + delta, 19)
                p.nice(new_val)
        except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError, OSError):
            # OSError catches Windows-specific failures (e.g. trying to
            # touch a protected system process like antivirus/kernel
            # helpers) so a single bad target never crashes the loop.
            pass

    def _adjust_oom_score(self, target, delta):
        """Raise (never lower) a process's /proc/[pid]/oom_score_adj on
        Linux. Only works on Linux; returns False anywhere else (or if
        permission is denied) so the caller can log that honestly instead
        of pretending it worked."""
        pid = target[0]
        path = f"/proc/{pid}/oom_score_adj"
        try:
            with open(path, "r") as f:
                current = int(f.read().strip())
            new_val = max(-1000, min(1000, current + delta))
            with open(path, "w") as f:
                f.write(str(new_val))
            return True
        except (FileNotFoundError, PermissionError, OSError, ValueError):
            return False