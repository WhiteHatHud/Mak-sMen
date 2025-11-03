"""
Model Evaluation, Cyber Triage, and Executive Reporting
Complete analysis pipeline for autoencoder anomaly detection
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    confusion_matrix, classification_report,
    precision_score, recall_score, f1_score,
    roc_curve, auc
)
import pickle


def evaluate_model(y_true, y_pred, y_scores):
    """
    Comprehensive model evaluation with all required metrics.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_scores: Anomaly scores (reconstruction errors)

    Returns:
        dict with all metrics
    """
    print("="*60)
    print("MODEL EVALUATION")
    print("="*60)

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()

    print("\nConfusion Matrix:")
    print(cm)
    print(f"\nTrue Negatives (TN): {tn}")
    print(f"False Positives (FP): {fp}")
    print(f"False Negatives (FN): {fn}")
    print(f"True Positives (TP): {tp}")

    # Calculate metrics
    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)

    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    tnr = tn / (tn + fp) if (tn + fp) > 0 else 0

    # ROC AUC
    fpr_roc, tpr_roc, thresholds = roc_curve(y_true, y_scores)
    roc_auc = auc(fpr_roc, tpr_roc)

    print("\n" + "="*60)
    print("PERFORMANCE METRICS")
    print("="*60)
    print(f"Precision: {precision:.4f}")
    print(f"Recall (TPR): {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    print(f"False Positive Rate (FPR): {fpr:.4f}")
    print(f"True Negative Rate (Specificity): {tnr:.4f}")
    print(f"ROC AUC: {roc_auc:.4f}")
    print("="*60)

    print("\nDetailed Classification Report:")
    print(classification_report(y_true, y_pred, target_names=['Benign', 'Malicious']))

    metrics = {
        'confusion_matrix': cm,
        'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
        'precision': precision,
        'recall': recall,
        'tpr': tpr,
        'f1': f1,
        'fpr': fpr,
        'tnr': tnr,
        'roc_auc': roc_auc,
        'fpr_roc': fpr_roc,
        'tpr_roc': tpr_roc
    }

    return metrics


def perform_triage(test_metadata, test_mse, y_test, y_pred):
    """
    Perform cyber triage and prioritization.

    Args:
        test_metadata: Process metadata
        test_mse: Reconstruction errors
        y_test: True labels
        y_pred: Predicted labels

    Returns:
        DataFrame with triage information
    """
    print("\n" + "="*60)
    print("CYBER TRIAGE AND PRIORITIZATION")
    print("="*60)

    # Create results dataframe
    results_df = pd.DataFrame(test_metadata)
    results_df['reconstruction_error'] = test_mse
    results_df['predicted_evil'] = y_pred
    results_df['actual_evil'] = y_test

    # Get detected anomalies
    detected_anomalies = results_df[results_df['predicted_evil'] == 1].copy()
    detected_anomalies = detected_anomalies.sort_values('reconstruction_error', ascending=False)

    print(f"\nTotal detected anomalies: {len(detected_anomalies)}")
    print(f"Correctly identified malicious: {detected_anomalies['actual_evil'].sum()}")
    print(f"False positives: {len(detected_anomalies) - detected_anomalies['actual_evil'].sum()}")

    # Assign priority based on reconstruction error quartiles
    if len(detected_anomalies) > 0:
        error_quartiles = detected_anomalies['reconstruction_error'].quantile([0.25, 0.5, 0.75])

        def assign_priority(error):
            if error >= error_quartiles[0.75]:
                return 'CRITICAL'
            elif error >= error_quartiles[0.5]:
                return 'HIGH'
            elif error >= error_quartiles[0.25]:
                return 'MEDIUM'
            else:
                return 'LOW'

        detected_anomalies['priority'] = detected_anomalies['reconstruction_error'].apply(assign_priority)

        # Priority summary
        print("\nTriage Priority Summary:")
        priority_summary = detected_anomalies.groupby('priority').agg({
            'processId': 'count',
            'actual_evil': 'sum',
            'reconstruction_error': 'mean'
        }).rename(columns={'processId': 'count', 'actual_evil': 'actual_malicious'})

        priority_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        priority_summary = priority_summary.reindex(priority_order)
        print(priority_summary)

        # Top anomalies
        print("\nTop 20 Most Critical Anomalies:")
        print(detected_anomalies.head(20)[['processId', 'hostName', 'priority',
                                            'reconstruction_error', 'actual_evil']])

    else:
        priority_summary = None
        print("\nNo anomalies detected!")

    return results_df, detected_anomalies, priority_summary


def create_visualizations(metrics, test_mse, y_test, y_pred, detected_anomalies,
                          priority_summary, threshold):
    """Create all visualization plots."""

    print("\n" + "="*60)
    print("CREATING VISUALIZATIONS")
    print("="*60)

    # 1. Confusion Matrix
    print("\n1. Confusion Matrix...")
    plt.figure(figsize=(8, 6))
    sns.heatmap(metrics['confusion_matrix'], annot=True, fmt='d', cmap='RdYlGn_r',
                xticklabels=['Benign', 'Malicious'],
                yticklabels=['Benign', 'Malicious'])
    plt.title('Confusion Matrix - Autoencoder', fontsize=16, fontweight='bold')
    plt.ylabel('Actual Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    plt.savefig('confusion_matrix.png', dpi=300, bbox_inches='tight')
    plt.show()

    # 2. ROC Curve
    print("2. ROC Curve...")
    plt.figure(figsize=(10, 8))
    plt.plot(metrics['fpr_roc'], metrics['tpr_roc'], color='darkorange',
             lw=2, label=f'ROC curve (AUC = {metrics["roc_auc"]:.3f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random Classifier')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate', fontsize=12)
    plt.ylabel('True Positive Rate', fontsize=12)
    plt.title('ROC Curve - Autoencoder Anomaly Detection', fontsize=14, fontweight='bold')
    plt.legend(loc="lower right", fontsize=12)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('roc_curve.png', dpi=300, bbox_inches='tight')
    plt.show()

    # 3. Priority Distribution
    if priority_summary is not None and len(detected_anomalies) > 0:
        print("3. Priority Distribution...")
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        priority_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        priority_summary['count'].plot(kind='bar', ax=axes[0],
                                        color=['red', 'orange', 'yellow', 'lightblue'])
        axes[0].set_title('Detected Anomalies by Priority', fontsize=14, fontweight='bold')
        axes[0].set_xlabel('Priority')
        axes[0].set_ylabel('Count')
        axes[0].set_xticklabels(priority_order, rotation=0)
        axes[0].grid(alpha=0.3)

        priority_summary['actual_malicious'].plot(kind='bar', ax=axes[1],
                                                   color=['darkred', 'darkorange', 'gold', 'steelblue'])
        axes[1].set_title('Confirmed Malicious by Priority', fontsize=14, fontweight='bold')
        axes[1].set_xlabel('Priority')
        axes[1].set_ylabel('Count')
        axes[1].set_xticklabels(priority_order, rotation=0)
        axes[1].grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig('priority_distribution.png', dpi=300, bbox_inches='tight')
        plt.show()

    # 4. Executive Dashboard
    print("4. Executive Summary Dashboard...")
    create_executive_dashboard(metrics, y_test, y_pred, test_mse, threshold,
                                 detected_anomalies, priority_summary)

    print("\n All visualizations created!")


def create_executive_dashboard(metrics, y_test, y_pred, test_mse, threshold,
                                detected_anomalies, priority_summary):
    """Create comprehensive executive dashboard."""

    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 1. Model Performance Metrics
    ax1 = fig.add_subplot(gs[0:2, 0:2])
    metric_names = ['Precision', 'Recall\n(TPR)', 'F1 Score', 'Specificity\n(TNR)']
    values = [metrics['precision'], metrics['recall'], metrics['f1'], metrics['tnr']]
    colors = ['#2ecc71' if v > 0.7 else '#f39c12' if v > 0.5 else '#e74c3c' for v in values]
    bars = ax1.barh(metric_names, values, color=colors)
    ax1.set_xlim([0, 1])
    ax1.set_xlabel('Score', fontsize=12)
    ax1.set_title('Autoencoder Performance Metrics', fontsize=14, fontweight='bold')
    ax1.axvline(x=0.7, color='green', linestyle='--', alpha=0.5, label='Good (>0.7)')
    ax1.axvline(x=0.5, color='orange', linestyle='--', alpha=0.5, label='Moderate (>0.5)')
    for i, v in enumerate(values):
        ax1.text(v + 0.02, i, f'{v:.3f}', va='center', fontweight='bold')
    ax1.legend(loc='lower right')
    ax1.grid(alpha=0.3)

    # 2. Detection Breakdown (Pie)
    ax2 = fig.add_subplot(gs[0, 2])
    detection_data = [metrics['tp'], metrics['fn'], metrics['fp'], metrics['tn']]
    detection_labels = [f'True Pos\n{metrics["tp"]}', f'False Neg\n{metrics["fn"]}',
                        f'False Pos\n{metrics["fp"]}', f'True Neg\n{metrics["tn"]}']
    detection_colors = ['#27ae60', '#e74c3c', '#f39c12', '#95a5a6']
    ax2.pie(detection_data, labels=detection_labels, autopct='%1.1f%%',
            colors=detection_colors, startangle=90)
    ax2.set_title('Detection Breakdown', fontsize=12, fontweight='bold')

    # 3. Priority Distribution (Pie)
    ax3 = fig.add_subplot(gs[1, 2])
    if priority_summary is not None and len(detected_anomalies) > 0:
        priority_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        priority_colors = ['#e74c3c', '#f39c12', '#f1c40f', '#3498db']

        # Filter out NaN and zero values
        valid_counts = []
        valid_labels = []
        valid_colors = []
        for i, label in enumerate(priority_order):
            if label in priority_summary.index:
                count = priority_summary.loc[label, 'count']
                if pd.notna(count) and count > 0:
                    valid_counts.append(count)
                    valid_labels.append(label)
                    valid_colors.append(priority_colors[i])

        if valid_counts:
            ax3.pie(valid_counts, labels=valid_labels, autopct='%1.1f%%',
                    colors=valid_colors, startangle=90)
            ax3.set_title('Anomalies by Priority', fontsize=12, fontweight='bold')
        else:
            ax3.text(0.5, 0.5, 'No Valid\nPriorities', ha='center', va='center',
                     fontsize=14, transform=ax3.transAxes)
            ax3.axis('off')
    else:
        ax3.text(0.5, 0.5, 'No Anomalies\nDetected', ha='center', va='center',
                 fontsize=14, transform=ax3.transAxes)
        ax3.axis('off')

    # 4. Reconstruction Error Distribution
    ax4 = fig.add_subplot(gs[2, 0])
    test_benign_mse = test_mse[y_test == 0]
    test_malicious_mse = test_mse[y_test == 1]
    ax4.hist(test_benign_mse, bins=50, alpha=0.6, label='Benign', color='green')
    ax4.hist(test_malicious_mse, bins=50, alpha=0.6, label='Malicious', color='red')
    ax4.axvline(threshold, color='black', linestyle='--', linewidth=2,
                label=f'Threshold={threshold:.3f}')
    ax4.set_xlabel('Reconstruction Error', fontsize=10)
    ax4.set_ylabel('Frequency', fontsize=10)
    ax4.set_title('Error Distribution', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.set_yscale('log')
    ax4.grid(alpha=0.3)

    # 5. Performance Comparison
    ax5 = fig.add_subplot(gs[2, 1])
    comparison_metrics = ['Precision', 'Recall', 'F1', 'Specificity']
    comparison_values = [metrics['precision'], metrics['recall'],
                          metrics['f1'], metrics['tnr']]
    bars = ax5.bar(comparison_metrics, comparison_values,
                    color=['steelblue', 'coral', 'mediumpurple', 'lightgreen'])
    ax5.set_ylim([0, 1])
    ax5.set_ylabel('Score', fontsize=10)
    ax5.set_title('Metrics Summary', fontsize=12, fontweight='bold')
    ax5.axhline(y=0.7, color='green', linestyle='--', alpha=0.5)
    ax5.axhline(y=0.5, color='orange', linestyle='--', alpha=0.5)
    for i, v in enumerate(comparison_values):
        ax5.text(i, v + 0.03, f'{v:.2f}', ha='center', fontweight='bold')
    ax5.grid(alpha=0.3, axis='y')

    # 6. Key Statistics
    ax6 = fig.add_subplot(gs[2, 2])
    ax6.axis('off')
    stats_text = f"""
KEY STATISTICS
{'='*30}

Total Sequences: {len(y_test):,}
Anomalies Detected: {y_pred.sum():,}
Detection Rate: {(y_pred.sum()/len(y_test)*100):.1f}%

True Malicious: {y_test.sum():,}
Successfully Detected: {metrics['tp']:,}
Missed (False Neg): {metrics['fn']:,}

False Positive Rate: {(metrics['fpr']*100):.2f}%
F1 Score: {metrics['f1']:.3f}
ROC AUC: {metrics['roc_auc']:.3f}

Threshold: {threshold:.4f}
"""
    ax6.text(0.1, 0.5, stats_text, fontsize=11, family='monospace',
             verticalalignment='center',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    fig.suptitle('BETH Autoencoder Anomaly Detection - Executive Dashboard',
                 fontsize=18, fontweight='bold', y=0.98)

    plt.savefig('executive_dashboard.png', dpi=300, bbox_inches='tight')
    plt.show()


def export_reports(results_df, detected_anomalies):
    """Export CSV reports."""
    print("\n" + "="*60)
    print("EXPORTING REPORTS")
    print("="*60)

    # Export all results
    results_df.to_csv('full_results.csv', index=False)
    print("\n Full results saved to 'full_results.csv'")

    # Export detected anomalies
    if len(detected_anomalies) > 0:
        detected_anomalies.to_csv('detected_anomalies.csv', index=False)
        print(" Detected anomalies saved to 'detected_anomalies.csv'")

        # Export critical anomalies
        critical = detected_anomalies[detected_anomalies['priority'] == 'CRITICAL']
        if len(critical) > 0:
            critical.head(100).to_csv('critical_anomalies_top100.csv', index=False)
            print(" Top 100 critical anomalies saved to 'critical_anomalies_top100.csv'")


def main():
    """Complete evaluation and reporting pipeline."""
    print("="*60)
    print("BETH AUTOENCODER - EVALUATION AND REPORTING")
    print("="*60)

    # Load data
    print("\n1. Loading data...")
    y_test = np.load('y_test.npy')
    y_pred = np.load('y_pred.npy')
    test_mse = np.load('test_mse.npy')
    threshold = np.load('threshold.npy')

    with open('test_metadata.pkl', 'rb') as f:
        test_metadata = pickle.load(f)

    print(f"Test sequences: {len(y_test)}")
    print(f"Predictions: {len(y_pred)}")
    print(f"Threshold: {threshold:.4f}")

    # Evaluate model
    print("\n2. Evaluating model...")
    metrics = evaluate_model(y_test, y_pred, test_mse)

    # Perform triage
    print("\n3. Performing triage...")
    results_df, detected_anomalies, priority_summary = perform_triage(
        test_metadata, test_mse, y_test, y_pred
    )

    # Create visualizations
    print("\n4. Creating visualizations...")
    create_visualizations(metrics, test_mse, y_test, y_pred,
                           detected_anomalies, priority_summary, threshold)

    # Export reports
    print("\n5. Exporting reports...")
    export_reports(results_df, detected_anomalies)

    print("\n" + "="*60)
    print(" EVALUATION COMPLETE!")
    print("="*60)
    print("\nGenerated files:")
    print("  - confusion_matrix.png")
    print("  - roc_curve.png")
    print("  - priority_distribution.png")
    print("  - executive_dashboard.png")
    print("  - full_results.csv")
    print("  - detected_anomalies.csv")
    print("  - critical_anomalies_top100.csv")


if __name__ == '__main__':
    main()
