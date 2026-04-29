# Colab Control Workflow

This folder contains Python scripts meant to be run from Google Colab. The notebook should stay thin: clone the repo, install requirements, run a script, download/upload outputs.

## Basic Colab cells

### 1. Clone the repo

```python
!rm -rf Ai-Stuff
!git clone --branch CODING-AI https://github.com/xonoxo143-ux/Ai-Stuff.git
%cd Ai-Stuff
```

### 2. Install dependencies

```python
!pip -q install -r colab/requirements.txt
```

### 3. Run Android eval

Strict baseline:

```python
!python colab/run_android_eval.py --style strict --model HuggingFaceTB/SmolLM2-360M-Instruct
```

Code-first with correction examples:

```python
!python colab/run_android_eval.py --style codefirst --fewshots corrections --model HuggingFaceTB/SmolLM2-360M-Instruct
```

### 4. List outputs

```python
!ls -lh outputs
```

### 5. Download the JSON result

```python
from google.colab import files
files.download("outputs/android_eval_outputs_360m_codefirst_corrections_v1.json")
```

If the filename differs, use the exact name shown by `!ls -lh outputs`.

## Why this exists

The source of truth should live in GitHub, not in pasted notebook cells. This lets the assistant update the scripts and datasets in GitHub while the user only runs a small number of stable Colab commands.

## Current no-secret workflow

The current workflow does not need a GitHub token or PAT.

- Colab pulls code from public GitHub.
- Colab writes output files locally.
- The user manually uploads or pastes outputs for review.
- The assistant reviews and updates GitHub.

## Output files

`run_android_eval.py` writes both JSON and Markdown files under `outputs/`.

JSON is best for review and later processing. Markdown is useful if file download/upload is annoying and the user wants to paste results.

## Do not train yet

This folder currently supports eval, not fine-tuning. Training should be added only after the eval loop and seed dataset are stable.
