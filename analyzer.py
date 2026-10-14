"""
analyzer.py
Resource Analyzer: turns raw metrics from monitor.py into a workload
classification (NORMAL / HIGH / OVERLOAD), which is what the Adaptive
Manager will react to.
"""

NORMAL = "NORMAL"
HIGH = "HIGH"
OVERLOAD = "OVERLOAD"


class ResourceAnalyzer:
    def __init__(self, high_cpu=70, high_ram=70, overload_cpu=85, overload_ram=85):
        self.high_cpu = high_cpu
        self.high_ram = high_ram
        self.overload_cpu = overload_cpu
        self.overload_ram = overload_ram

    def classify(self, metrics):
        cpu = metrics["cpu_percent"]
        ram = metrics["ram_percent"]

        cpu_over = cpu >= self.overload_cpu
        ram_over = ram >= self.overload_ram
        cpu_high = cpu >= self.high_cpu
        ram_high = ram >= self.high_ram

        if cpu_over or ram_over:
            status = OVERLOAD
        elif cpu_high or ram_high:
            status = HIGH
        else:
            status = NORMAL

        # Which resource(s) actually triggered this status - the manager
        # uses this to pick a target process from the RIGHT top-N list
        # (no point de-prioritizing a CPU hog when RAM is what's maxed out).
        triggers = []
        if cpu_over or cpu_high:
            triggers.append("cpu")
        if ram_over or ram_high:
            triggers.append("ram")

        return {
            "status": status,
            "triggers": triggers,
            "cpu_percent": cpu,
            "ram_percent": ram,
            "disk_percent": metrics["disk_percent"],
            "top_processes_cpu": metrics["top_processes_cpu"],
            "top_processes_mem": metrics["top_processes_mem"],
        }
