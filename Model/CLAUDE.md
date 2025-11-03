# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cybersecurity dataset repository containing labeled system call traces for intrusion detection and anomaly detection research. The datasets capture system events from Linux systems, including both benign and malicious (evil) behavior.

## Dataset Structure

### Beta Dataset

Located in `Beta dataset/`, contains labeled CSV files with system call traces:

- **Training/Testing/Validation splits**: Pre-split datasets for machine learning:
  - `labelled_training_data.csv` (~197MB)
  - `labelled_testing_data.csv` (~57MB)
  - `labelled_validation_data.csv` (~45MB)

- **Per-host datasets**: Individual traces from specific IP addresses:
  - `labelled_2021may-ip-10-100-1-{4,26,95,105,186}.csv` - Main event logs
  - `labelled_2021may-ip-10-100-1-{4,26,95,105,186}-dns.csv` - DNS-specific logs
  - `labelled_2021may-ubuntu.csv` and `labelled_2021may-ubuntu-dns.csv`

### CSV Schema

System event logs contain the following columns:

**Common fields across datasets:**
- `timestamp`: Event timestamp
- `processId`, `parentProcessId`, `userId`: Process identifiers
- `processName`, `hostName`: Process and host information
- `eventId`, `eventName`: System call identifier and name
- `argsNum`, `returnValue`, `args`: System call arguments (JSON-formatted)
- `sus`: Suspicious flag (0 or 1)
- `evil`: Malicious flag (0 or 1) - ground truth label

**Additional fields in training/testing/validation datasets:**
- `threadId`: Thread identifier
- `mountNamespace`: Namespace information
- `stackAddresses`: Stack trace information (JSON array)

### Event Types

System calls logged include: `security_file_open`, `socket`, `fstat`, `close`, `openat`, `prctl`, `access`, `sched_process_exit`, and others.

## Data Characteristics

- Events are timestamped with sub-second precision
- Arguments are stored as JSON-formatted strings with typed values
- Binary labels: `sus` (suspicious) and `evil` (malicious)
- Multi-host coverage capturing different system behaviors
- Contains both DNS-specific logs and general system call traces

## Anomaly Detection Implementations

This repository contains two unsupervised anomaly detection implementations for the BETH hackathon challenge:

### 1. Isolation Forest (Root Directory)

**File**: `anomaly_detection.ipynb`

**Approach**: Process-level feature aggregation with Isolation Forest
- Aggregates system calls by process to create behavioral features
- 14 engineered features (event frequencies, temporal patterns, error rates)
- Fast training and inference
- Highly interpretable results

**To run**: Open Jupyter notebook and execute all cells

### 2. Deep Learning Autoencoder (autoencoder/ Directory)

**Files**:
- `data_preprocessing.py` - Sequence creation
- `autoencoder_model.py` - Model training
- `evaluate_and_report.py` - Evaluation and reporting
- `run_pipeline.py` - Complete pipeline

**Approach**: Sequential pattern learning with neural network
- Converts system calls into fixed-length sequences (50 events)
- Learns to reconstruct normal behavior patterns
- Detects anomalies via reconstruction error
- Better for capturing temporal dependencies

**To run**:
```bash
cd autoencoder
pip install -r requirements.txt
python run_pipeline.py
```

### Comparison

| Aspect | Isolation Forest | Autoencoder |
|--------|-----------------|-------------|
| Speed | Fast (~minutes) | Slower (~15-30 min) |
| Setup | Simple | Requires TensorFlow |
| Interpretability | High | Medium |
| Temporal Patterns | Limited | Excellent |
| Hardware | CPU only | GPU recommended |
| Best For | Quick analysis | Deep sequence analysis |

Both approaches provide:
- F1, TPR, FPR, ROC AUC metrics
- Cyber triage prioritization (CRITICAL/HIGH/MEDIUM/LOW)
- Executive dashboards
- Detailed CSV reports

## Running the Models

**Isolation Forest** (faster, simpler):
```bash
pip install -r requirements.txt
jupyter notebook anomaly_detection.ipynb
```

**Autoencoder** (more sophisticated):
```bash
cd autoencoder
pip install -r requirements.txt
python run_pipeline.py
```

Both implementations are fully documented and ready for hackathon submission.
