import csv

import pytest

from app.ingestion.csv_loader import DATASETS, CSVValidationError, parse_csv


def write_csv(tmp_path, name, headers, row):
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerow(row)
    return path


def test_parse_product_trims_strings_and_converts_types(tmp_path):
    path = write_csv(tmp_path, "products.csv",
                     ["sku_id", "product_name", "category", "subcategory", "price", "colour", "fabric", "size", "vendor_id", "product_active"],
                     [" SKU1 ", " Kurti ", "Womenswear", "Kurti", "899.50", " Navy ", "Cotton", "M", "VEN1", "true"])
    row = parse_csv(path, "products")[0]
    assert row["sku_id"] == "SKU1"
    assert str(row["price"]) == "899.50"
    assert row["product_active"] is True
    assert row["size_chart_id"] is None


def test_other_is_accepted_as_return_reason(tmp_path):
    path = write_csv(tmp_path, "returns.csv",
                     ["return_id", "order_id", "order_item_id", "sku_id", "customer_id", "return_created_at", "return_reason", "return_status", "return_quantity"],
                     ["R1", "O1", "I1", "S1", "C1", "2025-01-01T00:00:00Z", "Other", "Received", "1"])
    assert parse_csv(path, "returns")[0]["return_reason"] == "Other"


def test_required_field_and_unknown_column_fail_visibly(tmp_path):
    missing = write_csv(tmp_path, "bad.csv", ["sku_id"], ["S1"])
    with pytest.raises(CSVValidationError, match="Missing required columns"):
        parse_csv(missing, "products")
    extra = write_csv(tmp_path, "extra.csv", ["sku_id", "surprise"], ["S1", "x"])
    with pytest.raises(CSVValidationError, match="Unknown columns"):
        parse_csv(extra, "products")


def test_operational_and_vendor_datasets_are_loadable():
    assert {"vendors", "vendor_purchase_orders", "support_tickets", "app_search_events"} <= set(DATASETS)


def test_parse_vendor_trims_values_and_keeps_optional_lead_time_null(tmp_path):
    path = write_csv(tmp_path, "vendors.csv", ["vendor_id", "vendor_name", "city", "lead_time_days"],
                     [" VEN1 ", " Jaipur Crafts ", " Jaipur ", ""])
    row = parse_csv(path, "vendors")[0]
    assert row == {"vendor_id": "VEN1", "vendor_name": "Jaipur Crafts", "city": "Jaipur", "lead_time_days": None, "created_at": None}


def test_parse_csv_normalizes_whitespace_in_headers(tmp_path):
    path = write_csv(tmp_path, "customers.csv", [" customer_id ", " customer_city "], [" C1 ", " Jaipur "])
    row = parse_csv(path, "customers")[0]
    assert row["customer_id"] == "C1"
    assert row["customer_city"] == "Jaipur"
