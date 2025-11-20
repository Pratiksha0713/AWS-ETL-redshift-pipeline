-- ============================================================
-- Redshift COPY Commands for Loading Data from S3
-- Uses CSV format with IAM role authentication
-- ============================================================

-- Prerequisites:
-- 1. IAM Role with S3 read permissions attached to Redshift cluster
-- 2. Data files uploaded to S3 in specified paths
-- 3. Schema created (run create_redshift_schema.sql first)

-- Configuration variables (replace with your actual values)
-- SET s3_bucket = 'your-curated-data-bucket';
-- SET iam_role = 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole';

-- Note: In production, use Airflow/orchestration to pass these as parameters


-- ============================================================
-- TRUNCATE TABLES (Optional - for full refresh)
-- ============================================================

-- WARNING: This will delete all data!
-- Uncomment only if doing a full reload

-- TRUNCATE TABLE sales_fact;
-- TRUNCATE TABLE customer_dim;
-- TRUNCATE TABLE product_dim;
-- TRUNCATE TABLE location_dim;
-- TRUNCATE TABLE date_dim;


-- ============================================================
-- LOAD DIMENSION TABLES
-- ============================================================

-- Load Customer Dimension
COPY customer_dim (
    customer_key,
    customer_id,
    full_name,
    email,
    phone,
    address,
    city,
    state,
    zip_code,
    country,
    created_date,
    is_active,
    etl_inserted_date
)
FROM 's3://your-curated-data-bucket/curated/customer_dim/'
IAM_ROLE 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole'
FORMAT AS CSV
IGNOREHEADER 1
DATEFORMAT 'auto'
TIMEFORMAT 'auto'
REGION 'us-east-1'
MAXERROR 100
COMPUPDATE ON
STATUPDATE ON;

-- Verify load
SELECT 'customer_dim loaded' AS status, COUNT(*) AS row_count FROM customer_dim;


-- Load Product Dimension
COPY product_dim (
    product_key,
    product_id,
    product_name,
    category,
    subcategory,
    brand,
    unit_price,
    cost,
    margin,
    is_active,
    etl_inserted_date
)
FROM 's3://your-curated-data-bucket/curated/product_dim/'
IAM_ROLE 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole'
FORMAT AS CSV
IGNOREHEADER 1
REGION 'us-east-1'
MAXERROR 100
COMPUPDATE ON
STATUPDATE ON;

SELECT 'product_dim loaded' AS status, COUNT(*) AS row_count FROM product_dim;


-- Load Location Dimension
COPY location_dim (
    location_key,
    location_id,
    store_name,
    address,
    city,
    state,
    zip_code,
    region,
    country,
    etl_inserted_date
)
FROM 's3://your-curated-data-bucket/curated/location_dim/'
IAM_ROLE 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole'
FORMAT AS CSV
IGNOREHEADER 1
REGION 'us-east-1'
MAXERROR 100
COMPUPDATE ON
STATUPDATE ON;

SELECT 'location_dim loaded' AS status, COUNT(*) AS row_count FROM location_dim;


-- Load Date Dimension
COPY date_dim (
    date_key,
    date_value,
    year,
    quarter,
    month,
    month_name,
    day,
    day_of_week,
    day_name,
    week_of_year,
    is_weekend,
    fiscal_year,
    etl_inserted_date
)
FROM 's3://your-curated-data-bucket/curated/date_dim/'
IAM_ROLE 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole'
FORMAT AS CSV
IGNOREHEADER 1
DATEFORMAT 'auto'
TIMEFORMAT 'auto'
REGION 'us-east-1'
MAXERROR 100
COMPUPDATE ON
STATUPDATE ON;

SELECT 'date_dim loaded' AS status, COUNT(*) AS row_count FROM date_dim;


-- ============================================================
-- LOAD FACT TABLE
-- ============================================================

-- Load Sales Fact (must load dimensions first due to FK constraints)
COPY sales_fact (
    sale_key,
    customer_key,
    product_key,
    location_key,
    date_key,
    quantity,
    unit_price,
    gross_amount,
    discount_amount,
    tax_amount,
    net_amount,
    etl_inserted_date
)
FROM 's3://your-curated-data-bucket/curated/sales_fact/'
IAM_ROLE 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole'
FORMAT AS CSV
IGNOREHEADER 1
DATEFORMAT 'auto'
TIMEFORMAT 'auto'
REGION 'us-east-1'
MAXERROR 100
COMPUPDATE ON
STATUPDATE ON;

SELECT 'sales_fact loaded' AS status, COUNT(*) AS row_count FROM sales_fact;


-- ============================================================
-- POST-LOAD VALIDATION
-- ============================================================

-- Check for load errors
SELECT * FROM stl_load_errors 
WHERE starttime > DATEADD(hour, -1, GETDATE())
ORDER BY starttime DESC;

-- Check all table counts
SELECT 
    'Summary' AS description,
    (SELECT COUNT(*) FROM customer_dim) AS customers,
    (SELECT COUNT(*) FROM product_dim) AS products,
    (SELECT COUNT(*) FROM location_dim) AS locations,
    (SELECT COUNT(*) FROM date_dim) AS dates,
    (SELECT COUNT(*) FROM sales_fact) AS sales_transactions;


-- ============================================================
-- DATA QUALITY CHECKS
-- ============================================================

-- Check for NULL foreign keys in fact table
SELECT 
    COUNT(*) AS total_rows,
    COUNT(customer_key) AS valid_customers,
    COUNT(product_key) AS valid_products,
    COUNT(location_key) AS valid_locations,
    COUNT(date_key) AS valid_dates,
    COUNT(*) - COUNT(customer_key) AS null_customers,
    COUNT(*) - COUNT(product_key) AS null_products,
    COUNT(*) - COUNT(location_key) AS null_locations,
    COUNT(*) - COUNT(date_key) AS null_dates
FROM sales_fact;


-- Check for referential integrity violations
SELECT 'FK Check: Customer' AS check_type, COUNT(*) AS violations
FROM sales_fact s
LEFT JOIN customer_dim c ON s.customer_key = c.customer_key
WHERE c.customer_key IS NULL

UNION ALL

SELECT 'FK Check: Product', COUNT(*)
FROM sales_fact s
LEFT JOIN product_dim p ON s.product_key = p.product_key
WHERE p.product_key IS NULL

UNION ALL

SELECT 'FK Check: Location', COUNT(*)
FROM sales_fact s
LEFT JOIN location_dim l ON s.location_key = l.location_key
WHERE l.location_key IS NULL

UNION ALL

SELECT 'FK Check: Date', COUNT(*)
FROM sales_fact s
LEFT JOIN date_dim d ON s.date_key = d.date_key
WHERE d.date_key IS NULL;


-- Check for data anomalies
SELECT 
    'Negative Quantities' AS anomaly_type,
    COUNT(*) AS count
FROM sales_fact
WHERE quantity < 0

UNION ALL

SELECT 'Negative Prices', COUNT(*)
FROM sales_fact
WHERE unit_price < 0

UNION ALL

SELECT 'Zero Sales Amount', COUNT(*)
FROM sales_fact
WHERE net_amount = 0

UNION ALL

SELECT 'Gross < Net (Invalid)', COUNT(*)
FROM sales_fact
WHERE gross_amount < net_amount;


-- ============================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================

-- Analyze tables for query planner
ANALYZE customer_dim;
ANALYZE product_dim;
ANALYZE location_dim;
ANALYZE date_dim;
ANALYZE sales_fact;

-- Vacuum to reclaim space and sort rows
VACUUM FULL sales_fact;
VACUUM FULL customer_dim;
VACUUM FULL product_dim;
VACUUM FULL location_dim;
VACUUM FULL date_dim;


-- ============================================================
-- REFRESH MATERIALIZED VIEWS
-- ============================================================

REFRESH MATERIALIZED VIEW mv_monthly_sales;
REFRESH MATERIALIZED VIEW mv_customer_summary;


-- ============================================================
-- SAMPLE ANALYTICS QUERIES
-- ============================================================

-- Top 10 customers by lifetime value
SELECT 
    c.customer_id,
    c.full_name,
    c.city,
    c.state,
    COUNT(s.sale_key) AS total_purchases,
    SUM(s.net_amount) AS lifetime_value
FROM customer_dim c
JOIN sales_fact s ON c.customer_key = s.customer_key
GROUP BY c.customer_id, c.full_name, c.city, c.state
ORDER BY lifetime_value DESC
LIMIT 10;


-- Monthly sales trend
SELECT 
    d.year,
    d.month_name,
    COUNT(DISTINCT s.customer_key) AS unique_customers,
    SUM(s.quantity) AS units_sold,
    SUM(s.net_amount) AS total_revenue,
    AVG(s.net_amount) AS avg_transaction_value
FROM sales_fact s
JOIN date_dim d ON s.date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


-- Top selling products by category
SELECT 
    p.category,
    p.product_name,
    SUM(s.quantity) AS units_sold,
    SUM(s.net_amount) AS total_revenue
FROM sales_fact s
JOIN product_dim p ON s.product_key = p.product_key
GROUP BY p.category, p.product_name
ORDER BY total_revenue DESC
LIMIT 20;


-- Regional performance
SELECT 
    l.region,
    l.state,
    COUNT(DISTINCT s.customer_key) AS unique_customers,
    COUNT(s.sale_key) AS transactions,
    SUM(s.net_amount) AS total_sales
FROM sales_fact s
JOIN location_dim l ON s.location_key = l.location_key
GROUP BY l.region, l.state
ORDER BY total_sales DESC;


-- Weekend vs Weekday sales
SELECT 
    CASE WHEN d.is_weekend THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(s.sale_key) AS transactions,
    SUM(s.net_amount) AS total_sales,
    AVG(s.net_amount) AS avg_transaction
FROM sales_fact s
JOIN date_dim d ON s.date_key = d.date_key
GROUP BY d.is_weekend
ORDER BY day_type;


-- Data load completed successfully!
SELECT 'ALL TABLES LOADED AND VALIDATED' AS status;




