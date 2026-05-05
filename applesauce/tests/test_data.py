from pathlib import Path

import pandas as pd

from applesauce.data import build_data_card, infer_and_clean, load_dataset


FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"


def test_cleaning_normalizes_types_and_profiles() -> None:
    raw = load_dataset(FIXTURE)
    cleaned, duplicates = infer_and_clean(raw)
    card = build_data_card(FIXTURE, cleaned, duplicates)

    assert duplicates == 1
    assert "order_id" in cleaned.columns
    assert "customer_segment" in cleaned.columns
    assert card.row_count == 6
    assert card.column_count == 8
    assert any(column.name == "revenue" and column.role == "numeric" for column in card.columns)
    assert any(column.name == "order_date" and column.role == "datetime" for column in card.columns)
    assert any(column.name == "returned" and column.role == "boolean" for column in card.columns)


def test_cleaning_parses_comma_formatted_numeric_text() -> None:
    raw = pd.DataFrame(
        {
            "Pounds": ["7,055", "50,706", None],
            "Dollars": ["11,886", "$34,338", "25"],
        }
    )

    cleaned, _ = infer_and_clean(raw)

    assert pd.api.types.is_numeric_dtype(cleaned["pounds"])
    assert pd.api.types.is_numeric_dtype(cleaned["dollars"])
    assert float(cleaned["pounds"].iloc[0]) == 7055.0
    assert float(cleaned["dollars"].iloc[1]) == 34338.0
