#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Pipeline Runner
Executes all steps: preprocessing -> training -> evaluation -> reporting
"""

import sys
import time
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def print_step(step_num, total_steps, description):
    """Print step information"""
    print(f"\n{'-'*70}")
    print(f"STEP {step_num}/{total_steps}: {description}")
    print(f"{'-'*70}\n")


def main():
    """Run complete pipeline"""
    start_time = time.time()

    print_header("BETH AUTOENCODER ANOMALY DETECTION - COMPLETE PIPELINE")

    print("This pipeline will:")
    print("  1. Preprocess data into sequences")
    print("  2. Train the autoencoder model")
    print("  3. Evaluate model performance")
    print("  4. Perform cyber triage")
    print("  5. Generate executive reports and visualizations")
    print("\nEstimated time: 15-30 minutes (depending on hardware)")
    print("GPU recommended but not required.")

    input("\nPress Enter to start...")

    # Check if data exists
    data_path = Path('../Beta dataset/labelled_training_data.csv')
    if not data_path.exists():
        print("\nERROR: BETH dataset not found!")
        print(f"Expected location: {data_path.absolute()}")
        print("\nPlease ensure the Beta dataset is in the correct location.")
        sys.exit(1)

    try:
        # Step 1: Preprocessing
        print_step(1, 3, "Data Preprocessing")
        print("Creating sequences from system call traces...")
        import data_preprocessing
        data_preprocessing.main()

        # Step 2: Training
        print_step(2, 3, "Model Training")
        print("Training autoencoder on benign sequences...")
        import autoencoder_model
        autoencoder_model.main()

        # Step 3: Evaluation and Reporting
        print_step(3, 3, "Evaluation and Reporting")
        print("Evaluating model and generating reports...")
        import evaluate_and_report
        evaluate_and_report.main()

        # Summary
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)

        print_header("PIPELINE COMPLETE!")

        print("SUCCESS: All steps completed successfully!")
        print(f"\nTotal time: {minutes}m {seconds}s")

        print("\nGenerated Outputs:")
        print("\nModels:")
        print("  - autoencoder_final.h5")
        print("  - best_autoencoder.h5")
        print("  - preprocessor.pkl")

        print("\nReports:")
        print("  - full_results.csv")
        print("  - detected_anomalies.csv")
        print("  - critical_anomalies_top100.csv")

        print("\nVisualizations:")
        print("  - executive_dashboard.png (Main presentation)")
        print("  - confusion_matrix.png")
        print("  - roc_curve.png")
        print("  - priority_distribution.png")
        print("  - training_history.png")
        print("  - reconstruction_error_dist.png")

        print("\nNext Steps:")
        print("  1. Review executive_dashboard.png for high-level insights")
        print("  2. Check critical_anomalies_top100.csv for top threats")
        print("  3. Analyze full_results.csv for detailed investigation")
        print("  4. Use model justification from README.md in presentation")

        print("\n" + "="*70)

    except KeyboardInterrupt:
        print("\n\nWARNING: Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: Pipeline failed with error:")
        print(f"   {str(e)}")
        print("\nCheck the error message above and try again.")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
