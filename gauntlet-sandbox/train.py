"""Train a simple baseline classifier for the current prototype dataset."""

from __future__ import annotations

from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split


def train_model(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Fit a baseline logistic-regression classifier with explicit preprocessing."""
    feature_frame = data["feature_frame"]
    target_series = data["target_series"]
    target_column = data["target_column"]

    modeling_config = config.get("modeling", {})
    random_seed = int(modeling_config.get("random_seed", 42))
    test_size = float(modeling_config.get("train_test_split", 0.2))

    X_train, X_test, y_train, y_test = train_test_split(
        feature_frame,
        target_series,
        test_size=test_size,
        random_state=random_seed,
        stratify=target_series,
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                data["numeric_feature_columns"],
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                data["categorical_feature_columns"],
            ),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=random_seed,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]

    return {
        "status": "completed",
        "model": model,
        "target_column": target_column,
        "model_name": "logistic_regression",
        "summary": {
            "status": "completed",
            "target_column": target_column,
            "model_name": "logistic_regression",
            "train_size": int(len(X_train)),
            "test_size": int(len(X_test)),
            "feature_column_count": int(len(data["feature_columns"])),
            "numeric_feature_column_count": int(len(data["numeric_feature_columns"])),
            "categorical_feature_column_count": int(len(data["categorical_feature_columns"])),
            "class_weight": "balanced",
        },
        "evaluation_inputs": {
            "y_test": [int(value) for value in y_test.tolist()],
            "y_pred": [int(value) for value in predictions.tolist()],
            "y_score": [float(value) for value in probabilities.tolist()],
        },
        "notes": [
            "The prototype baseline uses logistic regression with balanced class weights.",
            "Feature engineering is limited to standard preprocessing inside the sklearn pipeline.",
        ],
    }
