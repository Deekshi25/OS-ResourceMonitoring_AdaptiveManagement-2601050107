"""
monitor.py
Resource Monitoring Agent.

Uses separate threads to continuously sample CPU, RAM, Disk, Network and
Process information (this is the "Thread 1..4" design from the project
brief: each resource type is watched by its own thread). Every thread
writes its latest reading into one shared, lock-protected dictionary so
the rest of the pipeline always reads a consistent snapshot.

OS concepts used here:
  - Concurrency (threading, shared state + locking)
  - Process management (psutil.process_iter)
  - Memory management (psutil.virtual_memory)
  - CPU scheduling visibility (psutil.cpu_percent, os load average)
"""

import threading
import time
import psutil


class ResourceMonitor:
    def __init__(self, interval=1.0):
        self.interval = interval
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.metrics = {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "disk_percent": 0.0,
            "net_sent_kbps": 0.0,
            "net_recv_kbps": 0.0,
            "process_count": 0,
            "load_avg": (0.0, 0.0, 0.0),
            "top_processes_cpu": [],  # top 5 by CPU%, list of (pid, name, cpu%, mem%)
            "top_processes_mem": [],  # top 5 by RAM%, same tuple shape
        }
        self._threads = []

    # ---- individual sampling threads ------------------------------
    def _cpu_loop(self):
        while not self._stop_event.is_set():
            val = psutil.cpu_percent(interval=self.interval)  # this call itself blocks/sleeps
            with self._lock:
                self.metrics["cpu_percent"] = val
                try:
                    self.metrics["load_avg"] = psutil.getloadavg()
                except (AttributeError, OSError):
                    pass

    def _ram_loop(self):
        while not self._stop_event.is_set():
            vm = psutil.virtual_memory()
            with self._lock:
                self.metrics["ram_percent"] = vm.percent
            time.sleep(self.interval)

    def _disk_loop(self):
        while not self._stop_event.is_set():
            du = psutil.disk_usage("/")
            with self._lock:
                self.metrics["disk_percent"] = du.percent
            time.sleep(self.interval)

    def _network_loop(self):
        prev = psutil.net_io_counters()
        while not self._stop_event.is_set():
            time.sleep(self.interval)
            cur = psutil.net_io_counters()
            sent_kbps = (cur.bytes_sent - prev.bytes_sent) / 1024.0 / self.interval
            recv_kbps = (cur.bytes_recv - prev.bytes_recv) / 1024.0 / self.interval
            with self._lock:
                self.metrics["net_sent_kbps"] = sent_kbps
                self.metrics["net_recv_kbps"] = recv_kbps
            prev = cur

    def _process_loop(self):
        while not self._stop_event.is_set():
            procs = []
            for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    name = info["name"] or f"pid-{info['pid']}"  # some OSes return blank names
                    procs.append((info["pid"], name, info["cpu_percent"] or 0.0,
                                  info["memory_percent"] or 0.0))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            top_cpu = sorted(procs, key=lambda x: x[2], reverse=True)[:5]
            top_mem = sorted(procs, key=lambda x: x[3], reverse=True)[:5]
            with self._lock:
                self.metrics["process_count"] = len(procs)
                self.metrics["top_processes_cpu"] = top_cpu
                self.metrics["top_processes_mem"] = top_mem
            time.sleep(self.interval)

    # ---- control ----------------------------------------------------
    def start(self):
        loops = [self._cpu_loop, self._ram_loop, self._disk_loop,
                 self._network_loop, self._process_loop]
        for loop in loops:
            t = threading.Thread(target=loop, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=2)

    def snapshot(self):
        with self._lock:
            return dict(self.metrics)
