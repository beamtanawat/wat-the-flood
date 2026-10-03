"""Evaluation report helpers for the synthetic classifier."""

from collections import Counter
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


LABELS = ("NORMAL", "MONITOR", "HIGH", "CRITICAL")


def evaluate_model(
    model: Any,
    x_train: Sequence[Sequence[float]],
    y_train: Sequence[str],
    x_test: Sequence[Sequence[float]],
    y_test: Sequence[str],
    feature_names: Sequence[str],
    duplicate_count: int,
) -> Dict[str, Any]:
    predictions = model.predict(x_test)
    report = classification_report(
        y_test,
        predictions,
        labels=list(LABELS),
        target_names=list(LABELS),
        output_dict=True,
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "per_class": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in LABELS
        },
        "confusion_matrix": confusion_matrix(
            y_test,
            predictions,
            labels=list(LABELS),
        ).tolist(),
        "labels": list(LABELS),
        "class_counts": {
            "train": dict(Counter(y_train)),
            "test": dict(Counter(y_test)),
        },
        "feature_importance": {
            name: float(importance)
            for name, importance in zip(feature_names, model.feature_importances_)
        },
        "duplicate_feature_rows_across_split": duplicate_count,
    }


def save_confusion_matrix(metrics: Dict[str, Any], output_path: Path) -> None:
    output_path = Path(output_path)
    cache_path = output_path.parent / ".matplotlib"
    cache_path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_path))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(6, 5))
    matrix = metrics["confusion_matrix"]
    image = axis.imshow(matrix, cmap="Blues")
    axis.set(
        xticks=range(len(LABELS)),
        yticks=range(len(LABELS)),
        xticklabels=LABELS,
        yticklabels=LABELS,
        xlabel="Predicted label",
        ylabel="True label",
        title="Synthetic label confusion matrix",
    )
    figure.colorbar(image, ax=axis)
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            axis.text(column_index, row_index, value, ha="center", va="center")
    figure.tight_layout()
    figure.savefig(output_path, dpi=140)
    plt.close(figure)
