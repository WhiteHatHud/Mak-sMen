"""
Advanced Threshold Optimization for Anomaly Detection
Implements multiple strategies to find optimal threshold for reducing false positives
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    precision_recall_curve, roc_curve, auc,
    confusion_matrix
)


class ThresholdOptimizer:
    """
    Comprehensive threshold optimization for anomaly detection.
    Implements multiple strategies to find optimal threshold.
    """

    def __init__(self, y_true, anomaly_scores):
        """
        Args:
            y_true: Ground truth labels (0=benign, 1=malicious)
            anomaly_scores: Anomaly scores (e.g., reconstruction errors)
        """
        self.y_true = y_true
        self.anomaly_scores = anomaly_scores
        self.results = {}

    def optimize_f1(self):
        """Find threshold that maximizes F1 score."""
        print("\n1. F1-Score Maximization")
        print("-" * 50)

        # Get precision-recall curve
        precision, recall, thresholds = precision_recall_curve(
            self.y_true, self.anomaly_scores
        )

        # Calculate F1 for each threshold
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)

        # Find best threshold
        best_idx = np.argmax(f1_scores)
        best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else thresholds[-1]
        best_f1 = f1_scores[best_idx]

        print(f"  Optimal threshold: {best_threshold:.6f}")
        print(f"  F1 Score: {best_f1:.4f}")
        print(f"  Precision: {precision[best_idx]:.4f}")
        print(f"  Recall: {recall[best_idx]:.4f}")

        self.results['f1_max'] = {
            'threshold': best_threshold,
            'f1': best_f1,
            'precision': precision[best_idx],
            'recall': recall[best_idx]
        }

        return best_threshold

    def optimize_precision_target(self, target_precision=0.80):
        """Find threshold that achieves target precision while maximizing recall."""
        print(f"\n2. Target Precision Optimization (Target: {target_precision:.0%})")
        print("-" * 50)

        precision, recall, thresholds = precision_recall_curve(
            self.y_true, self.anomaly_scores
        )

        # Find thresholds that meet target precision
        valid_idx = np.where(precision >= target_precision)[0]

        if len(valid_idx) == 0:
            print(f"  WARNING: Cannot achieve {target_precision:.0%} precision")
            print(f"  Max achievable precision: {precision.max():.2%}")
            # Use highest precision available
            best_idx = np.argmax(precision)
        else:
            # Among valid, choose highest recall
            best_idx = valid_idx[np.argmax(recall[valid_idx])]

        best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else thresholds[-1]

        print(f"  Optimal threshold: {best_threshold:.6f}")
        print(f"  Precision: {precision[best_idx]:.4f}")
        print(f"  Recall: {recall[best_idx]:.4f}")
        print(f"  F1 Score: {2 * precision[best_idx] * recall[best_idx] / (precision[best_idx] + recall[best_idx]):.4f}")

        self.results['precision_target'] = {
            'threshold': best_threshold,
            'precision': precision[best_idx],
            'recall': recall[best_idx],
            'target': target_precision
        }

        return best_threshold

    def optimize_recall_target(self, target_recall=0.90):
        """Find threshold that achieves target recall while maximizing precision."""
        print(f"\n3. Target Recall Optimization (Target: {target_recall:.0%})")
        print("-" * 50)

        precision, recall, thresholds = precision_recall_curve(
            self.y_true, self.anomaly_scores
        )

        # Find thresholds that meet target recall
        valid_idx = np.where(recall >= target_recall)[0]

        if len(valid_idx) == 0:
            print(f"  WARNING: Cannot achieve {target_recall:.0%} recall")
            print(f"  Max achievable recall: {recall.max():.2%}")
            best_idx = np.argmax(recall)
        else:
            # Among valid, choose highest precision
            best_idx = valid_idx[np.argmax(precision[valid_idx])]

        best_threshold = thresholds[best_idx] if best_idx < len(thresholds) else thresholds[-1]

        print(f"  Optimal threshold: {best_threshold:.6f}")
        print(f"  Precision: {precision[best_idx]:.4f}")
        print(f"  Recall: {recall[best_idx]:.4f}")
        print(f"  F1 Score: {2 * precision[best_idx] * recall[best_idx] / (precision[best_idx] + recall[best_idx]):.4f}")

        self.results['recall_target'] = {
            'threshold': best_threshold,
            'precision': precision[best_idx],
            'recall': recall[best_idx],
            'target': target_recall
        }

        return best_threshold

    def optimize_youden(self):
        """Find threshold that maximizes Youden's J statistic (TPR - FPR)."""
        print("\n4. Youden's J Statistic Optimization")
        print("-" * 50)

        fpr, tpr, thresholds = roc_curve(self.y_true, self.anomaly_scores)

        # Youden's J = TPR - FPR = Sensitivity + Specificity - 1
        j_scores = tpr - fpr

        # Find best threshold
        best_idx = np.argmax(j_scores)
        best_threshold = thresholds[best_idx]

        # Calculate metrics at this threshold
        y_pred = (self.anomaly_scores >= best_threshold).astype(int)
        precision = precision_score(self.y_true, y_pred)
        recall = recall_score(self.y_true, y_pred)
        f1 = f1_score(self.y_true, y_pred)

        print(f"  Optimal threshold: {best_threshold:.6f}")
        print(f"  Youden's J: {j_scores[best_idx]:.4f}")
        print(f"  TPR: {tpr[best_idx]:.4f}")
        print(f"  FPR: {fpr[best_idx]:.4f}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  F1 Score: {f1:.4f}")

        self.results['youden'] = {
            'threshold': best_threshold,
            'j_score': j_scores[best_idx],
            'tpr': tpr[best_idx],
            'fpr': fpr[best_idx],
            'precision': precision,
            'recall': recall,
            'f1': f1
        }

        return best_threshold

    def optimize_roc_distance(self):
        """Find threshold closest to perfect classifier (0, 1) on ROC curve."""
        print("\n5. ROC Distance Optimization (Closest to Perfect)")
        print("-" * 50)

        fpr, tpr, thresholds = roc_curve(self.y_true, self.anomaly_scores)

        # Distance to perfect classifier (0, 1)
        distances = np.sqrt((1 - tpr)**2 + fpr**2)

        # Find best threshold
        best_idx = np.argmin(distances)
        best_threshold = thresholds[best_idx]

        # Calculate metrics
        y_pred = (self.anomaly_scores >= best_threshold).astype(int)
        precision = precision_score(self.y_true, y_pred)
        recall = recall_score(self.y_true, y_pred)
        f1 = f1_score(self.y_true, y_pred)

        print(f"  Optimal threshold: {best_threshold:.6f}")
        print(f"  Distance to (0,1): {distances[best_idx]:.4f}")
        print(f"  TPR: {tpr[best_idx]:.4f}")
        print(f"  FPR: {fpr[best_idx]:.4f}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  F1 Score: {f1:.4f}")

        self.results['roc_distance'] = {
            'threshold': best_threshold,
            'distance': distances[best_idx],
            'tpr': tpr[best_idx],
            'fpr': fpr[best_idx],
            'precision': precision,
            'recall': recall,
            'f1': f1
        }

        return best_threshold

    def optimize_cost_based(self, fp_cost=1, fn_cost=10):
        """
        Find threshold that minimizes total cost.

        Args:
            fp_cost: Cost of false positive (default: 1)
            fn_cost: Cost of false negative (default: 10)
                    Higher FN cost = prioritize catching malicious (higher recall)
        """
        print(f"\n6. Cost-Based Optimization (FP_cost={fp_cost}, FN_cost={fn_cost})")
        print("-" * 50)

        # Test range of thresholds
        thresholds = np.percentile(self.anomaly_scores, np.arange(50, 100, 0.5))

        min_cost = float('inf')
        best_threshold = None
        best_metrics = None

        for threshold in thresholds:
            y_pred = (self.anomaly_scores >= threshold).astype(int)
            cm = confusion_matrix(self.y_true, y_pred)
            tn, fp, fn, tp = cm.ravel()

            # Calculate total cost
            total_cost = (fp * fp_cost) + (fn * fn_cost)

            if total_cost < min_cost:
                min_cost = total_cost
                best_threshold = threshold
                best_metrics = {
                    'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
                    'precision': precision_score(self.y_true, y_pred),
                    'recall': recall_score(self.y_true, y_pred),
                    'f1': f1_score(self.y_true, y_pred)
                }

        print(f"  Optimal threshold: {best_threshold:.6f}")
        print(f"  Total cost: {min_cost:.0f}")
        print(f"  FP: {best_metrics['fp']}, FN: {best_metrics['fn']}")
        print(f"  Precision: {best_metrics['precision']:.4f}")
        print(f"  Recall: {best_metrics['recall']:.4f}")
        print(f"  F1 Score: {best_metrics['f1']:.4f}")

        self.results['cost_based'] = {
            'threshold': best_threshold,
            'total_cost': min_cost,
            'fp_cost': fp_cost,
            'fn_cost': fn_cost,
            **best_metrics
        }

        return best_threshold

    def optimize_percentile_search(self):
        """Grid search over different percentiles."""
        print("\n7. Percentile Grid Search")
        print("-" * 50)

        percentiles = [90, 92, 94, 95, 96, 97, 98, 99, 99.5, 99.9]
        best_f1 = 0
        best_percentile = None
        best_threshold = None
        best_metrics = None

        print(f"\n{'Percentile':<12} {'Threshold':<12} {'Precision':<12} {'Recall':<12} {'F1':<12} {'FPR':<12}")
        print("-" * 72)

        for pct in percentiles:
            threshold = np.percentile(self.anomaly_scores, pct)
            y_pred = (self.anomaly_scores >= threshold).astype(int)

            precision = precision_score(self.y_true, y_pred)
            recall = recall_score(self.y_true, y_pred)
            f1 = f1_score(self.y_true, y_pred)

            cm = confusion_matrix(self.y_true, y_pred)
            tn, fp, fn, tp = cm.ravel()
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

            print(f"{pct:<12.1f} {threshold:<12.6f} {precision:<12.4f} {recall:<12.4f} {f1:<12.4f} {fpr:<12.4f}")

            if f1 > best_f1:
                best_f1 = f1
                best_percentile = pct
                best_threshold = threshold
                best_metrics = {
                    'precision': precision,
                    'recall': recall,
                    'f1': f1,
                    'fpr': fpr
                }

        print("\n" + "=" * 72)
        print(f"  Best percentile: {best_percentile}")
        print(f"  Best threshold: {best_threshold:.6f}")
        print(f"  F1 Score: {best_metrics['f1']:.4f}")
        print(f"  Precision: {best_metrics['precision']:.4f}")
        print(f"  Recall: {best_metrics['recall']:.4f}")
        print(f"  FPR: {best_metrics['fpr']:.4f}")

        self.results['percentile_search'] = {
            'threshold': best_threshold,
            'percentile': best_percentile,
            **best_metrics
        }

        return best_threshold

    def run_all_optimizations(self, target_precision=0.80, target_recall=0.90,
                              fp_cost=1, fn_cost=10):
        """Run all optimization strategies and compare."""
        print("\n" + "=" * 70)
        print("COMPREHENSIVE THRESHOLD OPTIMIZATION")
        print("=" * 70)

        # Run all methods
        self.optimize_f1()
        self.optimize_precision_target(target_precision)
        self.optimize_recall_target(target_recall)
        self.optimize_youden()
        self.optimize_roc_distance()
        self.optimize_cost_based(fp_cost, fn_cost)
        self.optimize_percentile_search()

        # Create comparison table
        print("\n" + "=" * 70)
        print("COMPARISON OF ALL METHODS")
        print("=" * 70)

        comparison_data = []
        for method, data in self.results.items():
            threshold = data['threshold']
            y_pred = (self.anomaly_scores >= threshold).astype(int)

            cm = confusion_matrix(self.y_true, y_pred)
            tn, fp, fn, tp = cm.ravel()

            comparison_data.append({
                'Method': method,
                'Threshold': threshold,
                'Precision': data.get('precision', precision_score(self.y_true, y_pred)),
                'Recall': data.get('recall', recall_score(self.y_true, y_pred)),
                'F1': data.get('f1', f1_score(self.y_true, y_pred)),
                'FP': fp,
                'FN': fn,
                'FPR': fp / (fp + tn)
            })

        comparison_df = pd.DataFrame(comparison_data)
        comparison_df = comparison_df.sort_values('F1', ascending=False)

        print("\n" + comparison_df.to_string(index=False))

        # Recommend best method
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)

        best_f1_method = comparison_df.iloc[0]
        lowest_fp_method = comparison_df.loc[comparison_df['FP'].idxmin()]

        print(f"\n1. BEST F1 SCORE: {best_f1_method['Method']}")
        print(f"   Threshold: {best_f1_method['Threshold']:.6f}")
        print(f"   F1: {best_f1_method['F1']:.4f}, Precision: {best_f1_method['Precision']:.4f}, Recall: {best_f1_method['Recall']:.4f}")
        print(f"   FP: {best_f1_method['FP']:.0f}, FN: {best_f1_method['FN']:.0f}")

        print(f"\n2. LOWEST FALSE POSITIVES: {lowest_fp_method['Method']}")
        print(f"   Threshold: {lowest_fp_method['Threshold']:.6f}")
        print(f"   F1: {lowest_fp_method['F1']:.4f}, Precision: {lowest_fp_method['Precision']:.4f}, Recall: {lowest_fp_method['Recall']:.4f}")
        print(f"   FP: {lowest_fp_method['FP']:.0f}, FN: {lowest_fp_method['FN']:.0f}")

        print("\n3. BUSINESS CONTEXT RECOMMENDATIONS:")
        print("   - For balanced performance → Use 'f1_max' or 'youden'")
        print("   - For reducing false alarms → Use 'precision_target' (high precision)")
        print("   - For catching all threats → Use 'recall_target' (high recall)")
        print("   - For custom cost model → Use 'cost_based' (adjust FP/FN costs)")

        return comparison_df

    def plot_threshold_analysis(self, save_path='threshold_optimization.png'):
        """Create comprehensive visualization of threshold optimization."""
        fig = plt.figure(figsize=(18, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # 1. Precision-Recall vs Threshold
        ax1 = fig.add_subplot(gs[0, :2])
        precision, recall, thresholds_pr = precision_recall_curve(
            self.y_true, self.anomaly_scores
        )
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)

        # Align arrays
        thresholds_pr = np.append(thresholds_pr, thresholds_pr[-1])

        ax1.plot(thresholds_pr, precision, label='Precision', linewidth=2, color='blue')
        ax1.plot(thresholds_pr, recall, label='Recall', linewidth=2, color='green')
        ax1.plot(thresholds_pr, f1_scores, label='F1 Score', linewidth=2, color='red', linestyle='--')

        # Mark optimal points
        for method, data in self.results.items():
            if method in ['f1_max', 'youden', 'roc_distance']:
                ax1.axvline(data['threshold'], linestyle=':', alpha=0.5, label=f"{method}: {data['threshold']:.3f}")

        ax1.set_xlabel('Threshold', fontsize=12)
        ax1.set_ylabel('Score', fontsize=12)
        ax1.set_title('Precision, Recall, F1 vs Threshold', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=9)
        ax1.grid(alpha=0.3)
        ax1.set_ylim([0, 1.05])

        # 2. ROC Curve
        ax2 = fig.add_subplot(gs[0, 2])
        fpr, tpr, _ = roc_curve(self.y_true, self.anomaly_scores)
        roc_auc = auc(fpr, tpr)

        ax2.plot(fpr, tpr, linewidth=2, label=f'ROC (AUC={roc_auc:.3f})')
        ax2.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
        ax2.set_xlabel('FPR', fontsize=11)
        ax2.set_ylabel('TPR', fontsize=11)
        ax2.set_title('ROC Curve', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9)
        ax2.grid(alpha=0.3)

        # 3. False Positives vs Threshold
        ax3 = fig.add_subplot(gs[1, :2])
        thresholds_test = np.percentile(self.anomaly_scores, np.arange(50, 100, 0.5))
        fp_counts = []
        fn_counts = []

        for threshold in thresholds_test:
            y_pred = (self.anomaly_scores >= threshold).astype(int)
            cm = confusion_matrix(self.y_true, y_pred)
            tn, fp, fn, tp = cm.ravel()
            fp_counts.append(fp)
            fn_counts.append(fn)

        ax3.plot(thresholds_test, fp_counts, label='False Positives', linewidth=2, color='orange')
        ax3.plot(thresholds_test, fn_counts, label='False Negatives', linewidth=2, color='red')
        ax3.set_xlabel('Threshold', fontsize=12)
        ax3.set_ylabel('Count', fontsize=12)
        ax3.set_title('False Positives/Negatives vs Threshold', fontsize=14, fontweight='bold')
        ax3.legend(fontsize=10)
        ax3.grid(alpha=0.3)

        # 4. Method Comparison - F1 Scores
        ax4 = fig.add_subplot(gs[1, 2])
        methods = list(self.results.keys())
        f1_values = []

        for method in methods:
            threshold = self.results[method]['threshold']
            y_pred = (self.anomaly_scores >= threshold).astype(int)
            f1_values.append(f1_score(self.y_true, y_pred))

        colors = plt.cm.viridis(np.linspace(0, 1, len(methods)))
        ax4.barh(methods, f1_values, color=colors)
        ax4.set_xlabel('F1 Score', fontsize=11)
        ax4.set_title('F1 Comparison', fontsize=12, fontweight='bold')
        ax4.set_xlim([0, 1])
        for i, v in enumerate(f1_values):
            ax4.text(v + 0.01, i, f'{v:.3f}', va='center', fontsize=9)
        ax4.grid(alpha=0.3, axis='x')

        # 5. Threshold Values Comparison
        ax5 = fig.add_subplot(gs[2, :])
        thresholds_vals = [self.results[m]['threshold'] for m in methods]

        ax5.bar(methods, thresholds_vals, color=colors, alpha=0.7)
        ax5.set_ylabel('Threshold Value', fontsize=12)
        ax5.set_xlabel('Method', fontsize=12)
        ax5.set_title('Threshold Values by Method', fontsize=14, fontweight='bold')
        ax5.tick_params(axis='x', rotation=45)
        for i, v in enumerate(thresholds_vals):
            ax5.text(i, v, f'{v:.4f}', ha='center', va='bottom', fontsize=9)
        ax5.grid(alpha=0.3, axis='y')

        plt.suptitle('Threshold Optimization Analysis', fontsize=16, fontweight='bold', y=0.995)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

        print(f"\nVisualization saved to {save_path}")


def main():
    """Example usage with autoencoder results."""
    print("=" * 70)
    print("THRESHOLD OPTIMIZATION FOR AUTOENCODER")
    print("=" * 70)

    # Load data
    print("\nLoading autoencoder results...")
    y_test = np.load('y_test.npy')
    test_mse = np.load('test_mse.npy')
    current_threshold = np.load('threshold.npy')

    print(f"Test samples: {len(y_test)}")
    print(f"Current threshold (95th percentile): {current_threshold:.6f}")

    # Create optimizer
    optimizer = ThresholdOptimizer(y_test, test_mse)

    # Run all optimizations
    comparison_df = optimizer.run_all_optimizations(
        target_precision=0.80,  # 80% precision target
        target_recall=0.90,     # 90% recall target
        fp_cost=1,              # Cost of false positive
        fn_cost=10              # Cost of false negative (10x higher = prioritize recall)
    )

    # Create visualizations
    print("\nCreating visualizations...")
    optimizer.plot_threshold_analysis()

    # Save comparison
    comparison_df.to_csv('threshold_comparison.csv', index=False)
    print("\nComparison saved to 'threshold_comparison.csv'")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("\n1. Review the comparison table above")
    print("2. Choose the method that best fits your needs:")
    print("   - Low FP → Use 'precision_target' threshold")
    print("   - Balanced → Use 'f1_max' or 'youden' threshold")
    print("   - Catch all threats → Use 'recall_target' threshold")
    print("\n3. Update your threshold in autoencoder_model.py")
    print("4. Re-run evaluation with the new threshold")


if __name__ == '__main__':
    main()
