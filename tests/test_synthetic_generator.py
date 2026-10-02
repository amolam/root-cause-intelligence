from collections import Counter

from scripts.generate_synthetic_data import generate, validate


def test_returns_are_concentrated_on_seventy_skus(tmp_path):
    datasets = generate(tmp_path)
    validate(datasets)
    returns_per_sku = Counter(row["sku_id"] for row in datasets["returns"])

    assert len({row["return_id"] for row in datasets["returns"]}) == 3100
    assert len(returns_per_sku) == 70
    assert sum(count <= 2 for count in returns_per_sku.values()) == 5
    assert all(20 <= count <= 70 for count in returns_per_sku.values() if count > 2)