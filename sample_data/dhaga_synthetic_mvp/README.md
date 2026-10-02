# Dhaga & Co. synthetic MVP data

Deterministic, entirely fictional fixtures generated with seed `20261002`. These are suitable for local/staging demos; they are not customer records. CSV columns follow `app/db/models.py`, and `order_items.csv` is included to satisfy the returns-to-order-item foreign key. Re-run `python scripts/generate_synthetic_data.py` from the repository root to regenerate.

## Volumes and exact proportions

| Dataset | Rows | Constraint |
|---|---:|---|
| Vendors | 12 | 6 Tiruppur, 6 Jaipur |
| Products | 500 | INR 399–1,499 inclusive |
| Customers | 1,000 | 640 tier 2/3 (64%) |
| Orders | 10,000 | 6,100 COD (61%), 3,900 prepaid (39%) |
| Order items | 10,000 | One line per order for straightforward return linkage |
| Returns | 3,100 | 31% of orders; 1,364 `Other` (44%) |
| Support tickets | 1,000 | 580 WISMO (58%), 420 sizing/quality |
| Vendor purchase orders | 50 | Lead times vary by vendor |
| App search events | 2,000 | Hinglish and occasion searches |

## Loading order

Run these commands from the repository root after applying the Alembic migrations. The order respects the database foreign keys:

```powershell
python -m app.ingestion.cli load vendors sample_data/dhaga_synthetic_mvp/vendors.csv
python -m app.ingestion.cli load customers sample_data/dhaga_synthetic_mvp/customers.csv
python -m app.ingestion.cli load products sample_data/dhaga_synthetic_mvp/products.csv
python -m app.ingestion.cli load orders sample_data/dhaga_synthetic_mvp/orders.csv
python -m app.ingestion.cli load order_items sample_data/dhaga_synthetic_mvp/order_items.csv
python -m app.ingestion.cli load returns sample_data/dhaga_synthetic_mvp/returns.csv
python -m app.ingestion.cli load vendor_purchase_orders sample_data/dhaga_synthetic_mvp/vendor_purchase_orders.csv
python -m app.ingestion.cli load support_tickets sample_data/dhaga_synthetic_mvp/support_tickets.csv
python -m app.ingestion.cli load app_search_events sample_data/dhaga_synthetic_mvp/app_search_events.csv
```

## Schemas and sample CSV blocks

### `vendors.csv`

Vendor master; `vendor_id` primary key. Exactly 12 vendors, six each in Tiruppur and Jaipur.

Fields: `vendor_id`, `vendor_name`, `city`, `lead_time_days`.

```csv
vendor_id,vendor_name,city,lead_time_days
VEND-001,Kaveri Knitwear Works,Tiruppur,13
VEND-002,Sri Amman Apparels,Tiruppur,12
```

### `products.csv`

SKU master; `sku_id` primary key; `vendor_id` references vendors. Messy colour/fabric text is deliberate.

Fields: `sku_id`, `product_name`, `category`, `subcategory`, `price`, `colour`, `fabric`, `size`, `vendor_id`, `size_chart_id`, `product_created_at`, `product_active`, `image_url`.

```csv
sku_id,product_name,category,subcategory,price,colour,fabric,size,vendor_id,size_chart_id,product_created_at,product_active,image_url
SKU-0001,Festive Straight Kurti 001,Kurti,Straight Kurti,399.00,Ivory,Rayon,M,VEND-011,CHART-011,2023-12-01T10:00:00+00:00,true,
SKU-0002,Everyday Anarkali Kurti 002,Kurti,Anarkali Kurti,1499.00,Maroon,modal cotton,XS,VEND-009,CHART-009,2024-12-06T10:00:00+00:00,true,
```

### `customers.csv`

Customer master; `customer_id` primary key. 640/1,000 are tier 2 or tier 3.

Fields: `customer_id`, `customer_created_at`, `customer_city`, `customer_state`, `customer_tier`.

```csv
customer_id,customer_created_at,customer_city,customer_state,customer_tier
CUST-0001,2023-05-18T10:00:00+00:00,Surat,Gujarat,Tier 2
CUST-0002,2022-12-13T10:00:00+00:00,Nagpur,Maharashtra,Tier 2
```

### `orders.csv`

Order headers; `order_id` primary key; `customer_id` references customers. One product line per order in this fixture.

Fields: `order_id`, `customer_id`, `order_created_at`, `payment_mode`, `order_status`, `order_value`, `delivery_pincode`, `delivery_city`, `delivery_state`, `fulfilment_center`, `carrier`.

```csv
order_id,customer_id,order_created_at,payment_mode,order_status,order_value,delivery_pincode,delivery_city,delivery_state,fulfilment_center,carrier
ORD-00001,CUST-0910,2025-12-30T11:25:00+00:00,Cash on Delivery (COD),Delivered,974.00,110490,Delhi,Delhi,Jaipur FC,Ecom Express
ORD-00002,CUST-0423,2025-11-09T08:01:00+00:00,Cash on Delivery (COD),Delivered,1310.00,305267,Ajmer,Rajasthan,Tiruppur FC,Delhivery
```

### `order_items.csv`

Order lines; `order_item_id` primary key; `order_id` references orders and `sku_id` references products.

Fields: `order_item_id`, `order_id`, `sku_id`, `quantity`, `unit_price`, `size`, `colour`, `discount`.

```csv
order_item_id,order_id,sku_id,quantity,unit_price,size,colour,discount
ITEM-00001,ORD-00001,SKU-0221,1,974.00,XXL,Terracotta,0.00
ITEM-00002,ORD-00002,SKU-0296,1,1310.00,XS,NAVY_BLUE,0.00
```

### `returns.csv`

Return records; `return_id` primary key; customer, order, item, and SKU keys match their parent rows. 3,100 returns; 1,364 have reason `Other`.

Fields: `return_id`, `order_id`, `order_item_id`, `sku_id`, `customer_id`, `return_created_at`, `return_reason`, `return_reason_text`, `return_status`, `refund_amount`, `return_quantity`.

```csv
return_id,order_id,order_item_id,sku_id,customer_id,return_created_at,return_reason,return_reason_text,return_status,refund_amount,return_quantity
RET-00010,ORD-00010,ITEM-00010,SKU-0179,CUST-0566,2025-12-23T11:36:00+00:00,Other,Length is not as shown,Refunded,1327.00,1
RET-00012,ORD-00012,ITEM-00012,SKU-0307,CUST-0375,2025-05-15T20:42:00+00:00,Other,"Bahut tight hai, size bada chahiye",Refunded,1315.00,1
```

### `support_tickets.csv`

Support tickets; `ticket_id` primary key; customer and optional order keys reference their parent rows. 580/1,000 tagged `wismo`.

Fields: `ticket_id`, `customer_id`, `order_id`, `created_at`, `channel`, `query_text`, `category_tag`, `resolution_status`.

```csv
ticket_id,customer_id,order_id,created_at,channel,query_text,category_tag,resolution_status
TICKET-0001,CUST-0301,ORD-04972,2025-07-30T16:04:00+00:00,phone,Delivery agent ne call nahi kiya.,wismo,Pending Customer
TICKET-0002,CUST-0536,ORD-08278,2025-01-09T08:01:00+00:00,phone,My parcel is delayed. Please check.,wismo,Pending Customer
```

### `vendor_purchase_orders.csv`

PO lines; `po_id` primary key; vendor and SKU both match the product's vendor relationship. 50 rows.

Fields: `po_id`, `vendor_id`, `sku_id`, `quantity_ordered`, `order_date`, `expected_delivery_date`, `actual_delivery_date`, `po_status`.

```csv
po_id,vendor_id,sku_id,quantity_ordered,order_date,expected_delivery_date,actual_delivery_date,po_status
PO-001,VEND-001,SKU-0017,248,2026-06-20T10:00:00+00:00,2026-07-03T10:00:00+00:00,2026-07-10T10:00:00+00:00,Fulfilled
PO-002,VEND-009,SKU-0089,395,2026-05-10T10:00:00+00:00,2026-05-26T10:00:00+00:00,2026-06-02T10:00:00+00:00,Fulfilled
```

### `app_search_events.csv`

Search events; `event_id` primary key; `customer_id` references customers. 2,000 rows.

Fields: `event_id`, `customer_id`, `search_timestamp`, `raw_search_query`, `detected_language`, `occasion_intent`, `results_count`.

```csv
event_id,customer_id,search_timestamp,raw_search_query,detected_language,occasion_intent,results_count
SEARCH-00001,CUST-0322,2026-05-02T16:56:00+00:00,vacation beach dress,English,vacation,40
SEARCH-00002,CUST-0790,2025-07-16T20:20:00+00:00,eid special kurti,Hinglish,festive,3
```

