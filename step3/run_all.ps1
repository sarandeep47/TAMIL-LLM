# Run all model comparisons in sequence
# Usage: .\run_all.ps1 [-Only label1,label2,...]
# Examples: 
#   .\run_all.ps1                    # Run all models
#   .\run_all.ps1 -Only qwen3-4b,gemma3-4b,qwen3-1-7b  # Rerun only these

param(
    [string[]]$Only = @()
)

$ErrorActionPreference = "Continue"
$step3_dir = $PSScriptRoot

# Define models and their configurations
$models = @(
    @{name="qwen2.5:3b"; mode="clean"; label="qwen25-3b-clean"},
    @{name="tamil-voice-qwen"; mode="baked"; label="current-baked"},
    @{name="qwen3:4b-instruct-2507-q4_K_M"; mode="clean"; label="qwen3-4b-instruct"; pull=$true},
    @{name="gemma3:4b"; mode="clean"; label="gemma3-4b"; pull=$true}
)

# Filter models if -Only specified
if ($Only.Count -gt 0) {
    # Flatten comma-separated values from each element
    $only_labels = @()
    foreach ($item in $Only) {
        $only_labels += @($item -split ',').Trim()
    }
    
    # Check if any labels match
    $matching_models = $models | Where-Object { $_.label -in $only_labels }
    if ($matching_models.Count -eq 0) {
        $valid_labels = $models | ForEach-Object { $_.label }
        Write-Host "No matching labels. Valid labels: $($valid_labels -join ', ')" -ForegroundColor Red
        exit 1
    }
    
    $models = $matching_models
}

$results = @()

foreach ($model in $models) {
    $model_name = $model.name
    $mode = $model.mode
    $label = $model.label
    $should_pull = $model.pull -eq $true
    
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "Model: $model_name (mode: $mode, label: $label)" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    
    # Move old results file to step3/old/ if rerunning
    $old_results = "$step3_dir\results_$label.csv"
    if ((Test-Path $old_results) -and $Only) {
        if (!(Test-Path "$step3_dir\old")) {
            New-Item -ItemType Directory -Path "$step3_dir\old" | Out-Null
        }
        $old_file = "$step3_dir\old\results_${label}_old.csv"
        Move-Item -Path $old_results -Destination $old_file -Force
        Write-Host "Moved old results to $old_file"
    }
    
    try {
        # Stop any running model
        Write-Host "Stopping any running model..."
        ollama stop $model_name 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        
        # Pull if needed
        if ($should_pull) {
            Write-Host "Pulling model $model_name..."
            ollama pull $model_name
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR: Failed to pull $model_name" -ForegroundColor Red
                $results += @{model=$model_name; status="PULL_FAILED"}
                continue
            }
        }
        
        # Run model_compare.py
        Write-Host "Running model_compare.py for $model_name..."
        $python_cmd = "python"
        $args = @("model_compare.py", "--model", $model_name, "--label", $label, "--system-mode", $mode)
        
        & $python_cmd @args
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: model_compare.py failed for $model_name" -ForegroundColor Red
            $results += @{model=$model_name; status="FAILED"}
        } else {
            Write-Host "SUCCESS: $model_name completed" -ForegroundColor Green
            $results += @{model=$model_name; status="SUCCESS"}
        }
        
        # Save ollama ps output
        Write-Host "Saving ollama ps output..."
        $ps_output = ollama ps
        $ps_output | Out-File -FilePath "$step3_dir\ollama_ps_$label.txt" -Encoding UTF8
        
        # Stop the model
        Write-Host "Stopping $model_name..."
        ollama stop $model_name 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }
    catch {
        Write-Host "ERROR: Exception for $model_name : $_" -ForegroundColor Red
        $results += @{model=$model_name; status="ERROR"}
    }
}

# Summary
if ($results.Count -gt 0) {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "Summary" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan

    $succeeded = @($results | Where-Object {$_.status -eq "SUCCESS"}).Count
    $failed = @($results | Where-Object {$_.status -ne "SUCCESS"}).Count

    Write-Host "Succeeded: $succeeded" -ForegroundColor Green
    Write-Host "Failed: $failed" -ForegroundColor Red

    foreach ($result in $results) {
        $color = if ($result.status -eq "SUCCESS") { "Green" } else { "Red" }
        Write-Host "  $($result.model): $($result.status)" -ForegroundColor $color
    }

    Write-Host ""
    Write-Host "All runs completed. Check step3/results_*.csv for detailed results." -ForegroundColor Cyan
}
