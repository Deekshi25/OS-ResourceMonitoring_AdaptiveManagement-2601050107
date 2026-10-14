# Resource-Aware Monitoring and Adaptive Management of Linux Workloads

A working implementation of the project: a Python agent that monitors a
Linux machine's CPU/RAM/Disk/Network/Processes, classifies the workload,
and automatically takes corrective action when things get overloaded —
then lets you prove it worked by comparing "with" vs "without" adaptive
management.

## ⚠️ Run this on Linux (VM, WSL2, or EC2) — not native Windows

`psutil` runs on Windows too, so the script won't crash there, but it
loses its point: process priority (`nice`) and OOM-score adjustment are
Unix concepts, and on native Windows you'll just see it de-prioritizing
`Code.exe`, `svchost.exe`, `dwm.exe`, etc. — not a meaningful demo, and
mildly annoying since it targets your own editor. Always run it inside
your Linux VM, WSL2, or an EC2 instance.

## 1. How the pieces map to the architecture diagram

| File                  | Role                          | OS concept it demonstrates          |
|------------------------|-------------------------------|--------------------------------------|
| `monitor.py`           | Resource Monitoring Agent     | Concurrency (threads), process mgmt, memory mgmt |
| `analyzer.py`          | Resource Analyzer             | Threshold-based decision logic      |
| `adaptive_manager.py`  | Adaptive Decision Engine      | CPU scheduling (nice/priority)      |
| `main.py`              | Orchestrator + logger         | Ties everything together, writes CSV |
| `load_generator.py`    | Synthetic workload            | Lets you *create* low/medium/high/burst load on demand |
| `analyze_results.py`   | Results comparison            | Produces the chart for your report  |

Data flow (matches the brief's diagram exactly):
`Monitor → Analyzer → Adaptive Manager → (log actions + CSV)`

## 2. Set up the environment

You can do this on your own laptop first, then move to a cloud VM later —
the code is identical either way.

**Step 1 — Get a Linux machine.** Ubuntu 22.04+ is assumed. If you're on
Windows/Mac, use WSL2, a VirtualBox VM, or skip straight to the AWS
section below.

**Step 2 — Install Python and dependencies.**
```bash
sudo apt update
sudo apt install -y python3 python3-pip
pip3 install -r requirements.txt --break-system-packages
```
(`requirements.txt` just contains `psutil` and `matplotlib`.)

**Step 3 — Copy the project files** onto the machine (all 6 `.py` files +
`requirements.txt`), e.g. via `scp`, `git clone`, or simply pasting them.

## 3. Run it

**Quick single run** (adaptive mode, 60 seconds, sampling every 1s):
```bash
python3 main.py --mode adaptive --duration 60 --interval 1 --out adaptive.csv
```
You'll see live output like:
```
t= 12s  CPU= 91.0%  RAM= 42.3%  [OVERLOAD]  Overload: aggressively lowered priority of PID 4821 (stress_worker).
```

**Generate a workload to react to** — open a second terminal on the same
machine and run:
```bash
python3 load_generator.py --phase-seconds 20
```
This burns CPU and allocates memory in four phases (LOW → MEDIUM → HIGH →
BURST) so your monitor has something real to detect and act on.

## 4. Produce the "before vs after" comparison (the interesting part)

Run the *same* workload twice — once with the Adaptive Manager switched
off (baseline), once with it on (adaptive) — and compare:

```bash
# Terminal A                              # Terminal B
python3 main.py --mode baseline \         python3 load_generator.py --phase-seconds 20
  --duration 90 --out baseline.csv

# (wait for it to finish, then repeat with adaptive mode + a fresh workload run)

python3 main.py --mode adaptive \         python3 load_generator.py --phase-seconds 20
  --duration 90 --out adaptive.csv
```

Then plot the comparison:
```bash
python3 analyze_results.py --baseline baseline.csv --adaptive adaptive.csv --out comparison.png
```
This prints summary stats (average CPU, number of overloaded samples) and
saves a two-panel chart — exactly the kind of "with vs without" evidence
the project brief asks for.

> Note: on a single machine, "adaptive" mode mainly demonstrates
> *scheduling-level* relief (lowering a process's OS priority so it
> yields CPU to everything else) — you'll see it in reduced overload
> *duration* and in the recommended-action log, more than in a dramatic
> CPU % drop, since total CPU demand hasn't changed. That's expected and
> worth explaining in your report: adaptive management at the OS level
> improves *fairness and responsiveness* under load; the "scale the
> cloud" action is what actually adds capacity (see below).

## 5. Deploying on AWS EC2 (the "Cloud" part of the project)

1. Launch a `t2.micro` or `t3.small` Ubuntu 22.04 EC2 instance (free tier
   eligible). Open port 22 for SSH in the security group.
2. `ssh -i your-key.pem ubuntu@<public-ip>`
3. Repeat the setup steps in Section 2 on the instance.
4. Run the same commands as in Sections 3–4, over SSH.
5. Optional, to make the "scale" action real instead of simulated: install
   `boto3` (`pip3 install boto3 --break-system-packages`), give the
   instance an IAM role with EC2 permissions, and replace the print
   statement in `adaptive_manager.py`'s "RECOMMEND CLOUD SCALE-UP" branch
   with a real call, e.g.:
   ```python
   import boto3
   ec2 = boto3.client("ec2", region_name="us-east-1")
   ec2.modify_instance_attribute(InstanceId="i-xxxx",
                                  InstanceType={"Value": "t3.medium"})
   ```
   (Note: resizing requires stopping the instance first in real EC2 — for
   a live demo, logging the *recommendation* as this project already
   does is usually enough and is much safer to demo live.)

## 6. What to put in your project report

- **Architecture diagram** — reuse the one from the brief; label it with
  your actual filenames.
- **Methodology** — explain the three thresholds (`NORMAL` < 70%,
  `HIGH` 70–85%, `OVERLOAD` ≥ 85%) and why you chose them.
- **Results** — the `comparison.png` chart plus the printed summary
  stats (avg CPU, overloaded-sample count) for baseline vs adaptive.
- **OS concepts discussion** — process management (`psutil.process_iter`),
  CPU scheduling (`nice`/priority adjustment), memory management
  (`virtual_memory()`), concurrency (the 5 monitoring threads + lock).
- **Limitations / future work** — single-node only; real elastic scaling
  needs cloud IAM permissions and careful safety checks; thresholds are
  static rather than learned.

## 7. Extending it further (optional, for extra credit)

- Swap the CSV log for **Prometheus** + **Grafana** for a live dashboard.
- Add a Flask endpoint (`/status`) that returns the current snapshot as
  JSON, so multiple nodes can be monitored from one place.
- Containerize `main.py` with **Docker** so it's trivial to redeploy on
  any cloud VM.
- Replace the fixed thresholds in `analyzer.py` with a simple moving
  average / anomaly detector.
