import statistics
import subprocess
import time
import re
from typing import List


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def extract_duration(output: str) -> float:
    # Primary pattern
    m = re.search(r"Total parallel execution time:\s*([0-9]+(?:\.[0-9]+)?)s", output)
    if m:
        return float(m.group(1))
    # Fallback: last "Run X/Y finished in Ys"
    matches = re.findall(r"Run\s+\d+/\d+\s+finished\s+in\s+([0-9]+(?:\.[0-9]+)?)s", output)
    if matches:
        return float(matches[-1])
    raise RuntimeError("Could not parse duration from test output")


def run_single() -> float:
    proc = subprocess.run(
        ["python3", "optimized_parallel_test.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return extract_duration(output)


def main(iterations: int = 20, sleep_between: float = 0.0) -> None:
    durations: List[float] = []
    print(f"Running optimized parallel test {iterations} times...")
    start_all = time.time()
    for i in range(1, iterations + 1):
        iter_start = time.time()
        total_duration = run_single()
        durations.append(total_duration)
        iter_elapsed = time.time() - iter_start
        print(f"Run {i}/{iterations} finished in {total_duration:.2f}s (wall {iter_elapsed:.2f}s)")
        if sleep_between > 0 and i < iterations:
            time.sleep(sleep_between)

    total_wall = time.time() - start_all

    print("\n=== STATS (seconds) ===")
    print(f"count: {len(durations)}")
    print(f"avg:   {statistics.mean(durations):.3f}")
    print(f"median:{statistics.median(durations):.3f}")
    print(f"min:   {min(durations):.3f}")
    print(f"p90:   {percentile(durations, 90):.3f}")
    print(f"p95:   {percentile(durations, 95):.3f}")
    print(f"p99:   {percentile(durations, 99):.3f}")
    print(f"max:   {max(durations):.3f}")
    if len(durations) > 1:
        print(f"stdev: {statistics.stdev(durations):.3f}")
    print(f"Total wall time: {total_wall:.2f}s for {iterations} runs")


if __name__ == "__main__":
    main()


