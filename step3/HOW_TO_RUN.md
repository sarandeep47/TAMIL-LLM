# Step 3: Model Comparison - How to Run

## Prerequisites

- Close Kiro IDE, browser, and any heavy applications
- End leftover processes in Task Manager (Kiro, Claude, browser)
- System RAM should be at ~45% or lower before starting (~3.3 GB free)

## RAM Requirements by Model

Models to test (in order):

1. **qwen2.5:3b** (clean mode)
   - Minimum free RAM: 2000 MB
   - Expected: ≈4-5 minutes per 40 cases

2. **tamil-voice-qwen** (baked mode, control)
   - Minimum free RAM: 2000 MB
   - Expected: ≈4-5 minutes per 40 cases

3. **qwen3:4b** (clean mode, will be pulled)
   - Minimum free RAM: 3000 MB
   - Expected: ≈6-8 minutes per 40 cases + pull time

4. **gemma3:4b** (clean mode, will be pulled)
   - Minimum free RAM: 3600 MB
   - Expected: ≈6-8 minutes per 40 cases + pull time

5. **qwen3:1.7b** (clean mode, will be pulled)
   - Minimum free RAM: 2000 MB
   - Expected: ≈4-5 minutes per 40 cases + pull time

**Total expected duration: 1-1.5 hours including downloads**

## Step-by-Step Instructions

### 1. Prepare System

```powershell
# Close Kiro, browser, and heavy apps
# Check RAM in Task Manager (Ctrl+Shift+Esc)
# Aim for 45% usage or lower (≈3.3 GB free)
```

### 2. Open PowerShell and Navigate

```powershell
# Open PowerShell (Windows key + X, then "Windows PowerShell")
cd "c:\ROBO WEB TECHNOLOGIES\tamil-llama\step3"
```

### 3. Run All Models

```powershell
.\run_all.ps1
```

This will:
- Test qwen2.5:3b (already installed)
- Test tamil-voice-qwen (already installed, control)
- Pull and test qwen3:4b
- Pull and test gemma3:4b
- Pull and test qwen3:1.7b
- Stop each model after testing
- Save results to `results_<label>.csv`

Each model run takes 4-8 minutes depending on model size. Do not interrupt. Keep laptop plugged in.

### 4. Review Results

After all runs complete:

```powershell
# List all results files
ls results_*.csv

# Sample one CSV to verify format
head -5 results_qwen25-3b-clean.csv
```

### 5. Manual Grading (Required)

Open each `results_*.csv` file in a spreadsheet or text editor. Fill the last three columns for each case:

| Column | Score | Meaning |
|--------|-------|---------|
| `meaning_0_2` | 0 | Wrong/irrelevant/nonsense reply |
| | 1 | Partially correct, ambiguous, or off-topic |
| | 2 | Correct and relevant to the query |
| `grammar_0_2` | 0 | Severe grammar/spelling errors |
| | 1 | Minor grammar issues but understandable |
| | 2 | Correct grammar and spelling |
| `natural_0_2` | 0 | Awkward phrasing, unnatural for spoken Tamil |
| | 1 | Acceptable but slightly formal or repetitive |
| | 2 | Natural, fluent, colloquial (sounds native) |

**Tips:**
- For English replies (cases 24, 25, 40): score English quality
- For Tamil replies: score Tamil quality (script, grammar, naturalness)
- For errors/empty replies: score 0 across all three columns
- If a reply has multiple sentences, score the overall quality
- Use 0 sparingly (only for wrong/nonsense), 1 for acceptable, 2 for good

### 6. Run Summarize Script

Once manual scoring is complete:

```powershell
python summarize.py
```

This will:
- Read all `results_*.csv` files
- Compute statistics (avg/median/p90 latency, tokens/sec, flag counts)
- Compute mean manual scores
- Identify 5 worst-graded cases per model
- Write `summary.md`

### 7. Review Summary

```powershell
# View the summary
type summary.md
# or open in editor
notepad summary.md
```

## Troubleshooting

### "Free RAM under threshold" warning appears

- This is expected if you're running tight on memory
- The run will complete but timings may include disk swap
- Timings will be marked as "TIMINGS MAY BE INVALID (swapping)" in the CSV header

### Model fails to load

- Ensure free RAM is above the threshold for that model
- Close other applications and retry
- If it persists, model may require more resources than available

### Ollama connection error

- Ensure Ollama is running: `ollama serve` (in a separate PowerShell window)
- Verify with `ollama ps` showing at least one model loaded
- Try restarting Ollama if connection repeatedly fails

### CSV encoding issues

- All CSVs are written with UTF-8 BOM
- Manual scoring: save as UTF-8 in text editor
- If opening in Excel, use "Text Import" and select UTF-8

## Expected Output

After completion, you should have:

```
step3/
├── cases.json                      (40 test cases)
├── model_compare.py                (comparison script)
├── summarize.py                    (summary script)
├── run_all.ps1                     (automation script)
├── HOW_TO_RUN.md                   (this file)
├── results_qwen25-3b-clean.csv     (results for each model)
├── results_current-baked.csv
├── results_qwen3-4b.csv
├── results_gemma3-4b.csv
├── results_qwen3-1-7b.csv
├── ollama_ps_*.txt                 (ollama status per model)
└── summary.md                      (final summary after grading)
```

## Do Not Modify

- `server.py`, `router.py`, `Modelfile.qwen_tamil`, frontend, Step 1/2 files
- Everything stays in `step3/` folder
- Do not start Step 4 until explicitly instructed
