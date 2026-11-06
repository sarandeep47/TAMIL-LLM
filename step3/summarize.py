#!/usr/bin/env python3
"""
Summarize results from all model_compare runs.
Reads all results_*.csv, computes stats, and writes step3/summary.md.
"""

import csv
import statistics
from pathlib import Path
from collections import defaultdict

def read_results(csv_file):
    """Read results CSV, skip comment header lines, extract duplicate reply comment."""
    cases = []
    duplicate_reply = None
    
    with open(csv_file, encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("# most common reply"):
                # Extract: "# most common reply x14: ..."
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    duplicate_reply = parts[1].strip()
                continue
            
            if line.startswith("#"):
                continue
            if line.startswith("id,"):
                continue
            if not line.strip():
                continue
            
            # Parse CSV line manually to handle quoted cells with commas
            reader = csv.reader([line])
            row = next(reader)
            if len(row) < 26:
                continue
            
            try:
                timeout = int(row[22]) if len(row) > 22 else 0
                
                cases.append({
                    "id": int(row[0]),
                    "category": row[1],
                    "input": row[2],
                    "reply": row[3],
                    "ttft_ms": int(row[4]) if row[4] else 0,
                    "total_ms": int(row[5]) if row[5] else 0,
                    "prefill_ms": int(row[6]) if len(row) > 6 and row[6] else 0,
                    "eval_count": int(row[7]) if len(row) > 7 and row[7] else 0,
                    "prompt_eval_count": int(row[8]) if len(row) > 8 and row[8] else 0,
                    "tokens_per_sec": float(row[9]) if len(row) > 9 and row[9] else 0,
                    "think_chars": int(row[10]) if len(row) > 10 and row[10] else 0,
                    "empty": int(row[11]) if len(row) > 11 and row[11] else 0,
                    "no_tamil_script": int(row[12]) if len(row) > 12 and row[12] else 0,
                    "not_english": int(row[13]) if len(row) > 13 and row[13] else 0,
                    "has_cjk": int(row[14]) if len(row) > 14 and row[14] else 0,
                    "other_script": int(row[15]) if len(row) > 15 and row[15] else 0,
                    "fallback_phrase": int(row[16]) if len(row) > 16 and row[16] else 0,
                    "too_long": int(row[17]) if len(row) > 17 and row[17] else 0,
                    "repetition": int(row[18]) if len(row) > 18 and row[18] else 0,
                    "role_prefix_leak": int(row[19]) if len(row) > 19 and row[19] else 0,
                    "mixed_script_noise": int(row[20]) if len(row) > 20 and row[20] else 0,
                    "reasoning_leak": int(row[21]) if len(row) > 21 and row[21] else 0,
                    "timeout": timeout,
                    "meaning": float(row[23]) if len(row) > 23 and row[23].strip() else None,
                    "grammar": float(row[24]) if len(row) > 24 and row[24].strip() else None,
                    "natural": float(row[25]) if len(row) > 25 and row[25].strip() else None,
                })
            except (ValueError, IndexError):
                continue
    
    return cases, duplicate_reply

def compute_stats(cases):
    """Compute statistics from cases, skipping timeout rows."""
    # Skip timeout cases for timing averages
    valid_cases = [c for c in cases if c["timeout"] == 0]
    
    total_ms = [c["total_ms"] for c in valid_cases if c["total_ms"] > 0]
    prefill_ms = [c["prefill_ms"] for c in valid_cases if c["prefill_ms"] > 0]
    ttft_ms = [c["ttft_ms"] for c in valid_cases if c["ttft_ms"] > 0]
    tokens_per_sec = [c["tokens_per_sec"] for c in valid_cases if c["tokens_per_sec"] > 0]
    
    # Timeouts
    timeout_count = sum(1 for c in cases if c["timeout"] == 1)
    
    manual_scores = []
    for c in cases:
        scores = [c["meaning"], c["grammar"], c["natural"]]
        scores = [s for s in scores if s is not None]
        if scores:
            manual_scores.extend(scores)
    
    stats = {
        "count": len(cases),
        "timeout_count": timeout_count,
        "avg_total_ms": round(statistics.mean(total_ms), 1) if total_ms else 0,
        "median_total_ms": round(statistics.median(total_ms), 1) if total_ms else 0,
        "p90_total_ms": round(statistics.quantiles(total_ms, n=10)[8], 1) if len(total_ms) >= 10 else 0,
        "avg_prefill_ms": round(statistics.mean(prefill_ms), 1) if prefill_ms else 0,
        "avg_ttft_ms": round(statistics.mean(ttft_ms), 1) if ttft_ms else 0,
        "avg_tokens_per_sec": round(statistics.mean(tokens_per_sec), 2) if tokens_per_sec else 0,
        "mean_manual_score": round(statistics.mean(manual_scores), 2) if manual_scores else None,
    }
    
    # Count flags
    flags = {
        "empty": sum(1 for c in cases if c["empty"]),
        "no_tamil_script": sum(1 for c in cases if c["no_tamil_script"]),
        "not_english": sum(1 for c in cases if c["not_english"]),
        "has_cjk": sum(1 for c in cases if c["has_cjk"]),
        "other_script": sum(1 for c in cases if c["other_script"]),
        "fallback_phrase": sum(1 for c in cases if c["fallback_phrase"]),
        "too_long": sum(1 for c in cases if c["too_long"]),
        "repetition": sum(1 for c in cases if c["repetition"]),
        "role_prefix_leak": sum(1 for c in cases if c["role_prefix_leak"]),
        "mixed_script_noise": sum(1 for c in cases if c["mixed_script_noise"]),
        "reasoning_leak": sum(1 for c in cases if c["reasoning_leak"]),
        "timeout": timeout_count,
    }
    stats["flags"] = flags
    
    return stats

def get_worst_cases(cases, n=5):
    """Get worst-graded cases (by manual score, then by flags)."""
    # Sort by manual score (ascending = worse first), then by flag count
    def case_score(c):
        scores = [c["meaning"], c["grammar"], c["natural"]]
        scores = [s for s in scores if s is not None]
        if scores:
            avg_score = statistics.mean(scores)
        else:
            avg_score = 1.0  # Default to low score if no manual grading
        
        flag_count = (c["empty"] + c["no_tamil_script"] + c["not_english"] + c["has_cjk"] +
                     c["fallback_phrase"] + c["too_long"] + c["repetition"] + c["mixed_script_noise"])
        
        return (avg_score, -flag_count)  # Sort by score ascending, then flags descending
    
    sorted_cases = sorted(cases, key=case_score)
    return sorted_cases[:n]

def main():
    step3_dir = Path(__file__).parent
    results_files = sorted([f for f in step3_dir.glob("results_*.csv") if "old" not in f.parent.name])
    
    if not results_files:
        print("No results_*.csv files found in step3/")
        return
    
    summary_md = ""
    summary_md += "# Step 3: Model Comparison Summary\n\n"
    
    model_stats = {}
    for csv_file in results_files:
        label = csv_file.stem.replace("results_", "")
        print(f"Reading {csv_file.name}...")
        cases, duplicate_reply = read_results(csv_file)
        stats = compute_stats(cases)
        model_stats[label] = (stats, cases, duplicate_reply)
    
    # Print table of stats
    summary_md += "## Summary Statistics\n\n"
    summary_md += "| Model | Cases | Avg Total (ms) | Median Total (ms) | P90 Total (ms) | Avg Prefill (ms) | Avg TTFT (ms) | Avg Tokens/sec | Mean Manual Score | Timeouts |\n"
    summary_md += "|-------|-------|---|---|---|---|---|---|---|---|\n"
    
    for label in sorted(model_stats.keys()):
        stats, _ = model_stats[label]
        manual_score = stats["mean_manual_score"] if stats["mean_manual_score"] is not None else "—"
        summary_md += f"| {label} | {stats['count']} | {stats['avg_total_ms']} | {stats['median_total_ms']} | {stats['p90_total_ms']} | {stats['avg_prefill_ms']} | {stats['avg_ttft_ms']} | {stats['avg_tokens_per_sec']} | {manual_score} | {stats['timeout_count']} |\n"
    
    summary_md += "\n"
    
    # Per-model details
    summary_md += "## Per-Model Details\n\n"
    
    for label in sorted(model_stats.keys()):
        stats, cases, duplicate_reply = model_stats[label]
        summary_md += f"### {label}\n\n"
        summary_md += f"- Cases: {stats['count']}\n"
        summary_md += f"- Avg Total: {stats['avg_total_ms']}ms (Median: {stats['median_total_ms']}ms, P90: {stats['p90_total_ms']}ms)\n"
        summary_md += f"- Avg Prefill: {stats['avg_prefill_ms']}ms\n"
        summary_md += f"- Avg TTFT: {stats['avg_ttft_ms']}ms\n"
        summary_md += f"- Avg Tokens/sec: {stats['avg_tokens_per_sec']}\n"
        summary_md += f"- Mean Manual Score: {stats['mean_manual_score']}\n"
        summary_md += f"- Timeouts: {stats['timeout_count']}\n"
        
        if duplicate_reply:
            summary_md += f"- Most Common Reply: {duplicate_reply}\n"
        
        summary_md += f"- Auto Flags:\n"
        
        for flag_name, flag_count in stats["flags"].items():
            if flag_count > 0:
                summary_md += f"  - {flag_name}: {flag_count}\n"
        
        # Worst cases
        worst = get_worst_cases(cases, 5)
        if worst:
            summary_md += f"\n**5 Worst-Graded Cases:**\n\n"
            for c in worst:
                scores = [c["meaning"], c["grammar"], c["natural"]]
                scores_str = ", ".join(str(s) if s is not None else "?" for s in scores)
                summary_md += f"- Case {c['id']} ({c['category']}): meaning={c['meaning']}, grammar={c['grammar']}, natural={c['natural']}\n"
                summary_md += f"  Input: {c['input'][:60]}...\n"
                summary_md += f"  Reply: {c['reply'][:60]}...\n\n"
        
        summary_md += "\n"
    
    # Write summary
    summary_file = step3_dir / "summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary_md)
    
    print(f"\nSummary written to {summary_file}")
    print(summary_md)

if __name__ == "__main__":
    main()
