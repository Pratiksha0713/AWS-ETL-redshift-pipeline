-- ============================================================
-- AWS Redshift Star Schema for Sales Analytics
-- Schema: Star Schema with 4 dimension tables + 1 fact table
-- ============================================================

-- Drop tables if they exist (for development/testing)
-- Comment out in production for safety
DROP TABLE IF EXISTS sales_fact CASCADE;
DROP TABLE IF EXISTS customer_dim CASCADE;
DROP TABLE IF EXISTS product_dim CASCADE;
DROP TABLE IF EXISTS location_dim CASCADE;
DROP TABLE IF EXISTS date_dim CASCADE;

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

-- Customer Dimension (SCD Type 1)
CREATE TABLE IF NOT EXISTS customer_dim (
    customer_key BIGINT PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(200),
    email VARCHAR(100),
    phone VARCHAR(20),
    address VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    country VARCHAR(50),
    created_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    etl_inserted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_customer_id UNIQUE (customer_id)
)
DISTSTYLE KEY
DISTKEY (customer_key)
SORTKEY (customer_id, created_date);

-- Add column comments
COMMENT ON TABLE customer_dim IS 'Customer dimension table with SCD Type 1 logic';
COMMENT ON COLUMN customer_dim.customer_key IS 'Surrogate key for customer dimension';
COMMENT ON COLUMN customer_dim.customer_id IS 'Natural business key from source system';


-- Product Dimension (SCD Type 1)
CREATE TABLE IF NOT EXISTS product_dim (
    product_key BIGINT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(255),
    category VARCHAR(100),
    subcategory VARCHAR(100),
    brand VARCHAR(100),
    unit_price DECIMAL(10,2),
    cost DECIMAL(10,2),
    margin DECIMAL(5,2),
    is_active BOOLEAN DEFAULT TRUE,
    etl_inserted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_product_id UNIQUE (product_id),
    CONSTRAINT ck_unit_price CHECK (unit_price >= 0),
    CONSTRAINT ck_cost CHECK (cost >= 0)
)
DISTSTYLE ALL
SORTKEY (category, subcategory, product_id);

COMMENT ON TABLE product_dim IS 'Product dimension with category hierarchy';
COMMENT ON COLUMN product_dim.margin IS 'Profit margin percentage';


-- Location Dimension
CREATE TABLE IF NOT EXISTS location_dim (
    location_key BIGINT PRIMARY KEY,
    location_id VARCHAR(50) NOT NULL UNIQUE,
    store_name VARCHAR(200),
    address VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    region VARCHAR(50),
    country VARCHAR(50),
    etl_inserted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_location_id UNIQUE (location_id)
)
DISTSTYLE ALL
SORTKEY (region, state, city);

COMMENT ON TABLE location_dim IS 'Store/location dimension with geographic hierarchy';


-- Date Dimension
CREATE TABLE IF NOT EXISTS date_dim (
    date_key INTEGER PRIMARY KEY,
    date_value DATE NOT NULL UNIQUE,
    year SMALLINT,
    quarter SMALLINT,
    month SMALLINT,
    month_name VARCHAR(20),
    day SMALLINT,
    day_of_week SMALLINT,
    day_name VARCHAR(20),
    week_of_year SMALLINT,
    is_weekend BOOLEAN,
    fiscal_year SMALLINT,
    etl_inserted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_date_value UNIQUE (date_value),
    CONSTRAINT ck_quarter CHECK (quarter BETWEEN 1 AND 4),
    CONSTRAINT ck_month CHECK (month BETWEEN 1 AND 12),
    CONSTRAINT ck_day CHECK (day BETWEEN 1 AND 31),
    CONSTRAINT ck_dow CHECK (day_of_week BETWEEN 1 AND 7)
)
DISTSTYLE ALL
SORTKEY (date_key);

COMMENT ON TABLE date_dim IS 'Pre-generated date dimension covering 2020-2030';
COMMENT ON COLUMN date_dim.date_key IS 'Integer date key in YYYYMMDD format';


-- ============================================================
-- FACT TABLE
-- ============================================================

-- Sales Fact Table
CREATE TABLE IF NOT EXISTS sales_fact (
    sale_key BIGINT PRIMARY KEY,
    customer_key BIGINT NOT NULL,
    product_key BIGINT NOT NULL,
    location_key BIGINT NOT NULL,
    date_key INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    gross_amount DECIMAL(12,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    net_amount DECIMAL(12,2) NOT NULL,
    etl_inserted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_customer FOREIGN KEY (customer_key) 
        REFERENCES customer_dim(customer_key),
    CONSTRAINT fk_product FOREIGN KEY (product_key) 
        REFERENCES product_dim(product_key),
    CONSTRAINT fk_location FOREIGN KEY (location_key) 
        REFERENCES location_dim(location_key),
    CONSTRAINT fk_date FOREIGN KEY (date_key) 
        REFERENCES date_dim(date_key),
    
    -- Business rule constraints
    CONSTRAINT ck_quantity CHECK (quantity > 0),
    CONSTRAINT ck_gross_amount CHECK (gross_amount >= 0),
    CONSTRAINT ck_net_amount CHECK (net_amount >= 0)
)
DISTSTYLE KEY
DISTKEY (customer_key)
SORTKEY (date_key, customer_key);

COMMENT ON TABLE sales_fact IS 'Sales transaction fact table - grain: one row per sale line item';
COMMENT ON COLUMN sales_fact.gross_amount IS 'Quantity * Unit Price';
COMMENT ON COLUMN sales_fact.net_amount IS 'Gross - Discount + Tax';


-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

-- Note: Redshift uses sort keys instead of traditional indexes
-- Already defined above in table definitions


-- ============================================================
-- MATERIALIZED VIEWS FOR COMMON AGGREGATIONS
-- ============================================================

-- Monthly Sales Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_sales AS
SELECT 
    d.year,
    d.month,
    d.month_name,
    p.category,
    p.subcategory,
    l.region,
    l.state,
    COUNT(DISTINCT s.customer_key) AS unique_customers,
    COUNT(s.sale_key) AS total_transactions,
    SUM(s.quantity) AS total_quantity_sold,
    SUM(s.gross_amount) AS total_gross_sales,
    SUM(s.discount_amount) AS total_discounts,
    SUM(s.net_amount) AS total_net_sales,
    AVG(s.net_amount) AS avg_transaction_value
FROM sales_fact s
JOIN date_dim d ON s.date_key = d.date_key
JOIN product_dim p ON s.product_key = p.product_key
JOIN location_dim l ON s.location_key = l.location_key
GROUP BY 
    d.year, d.month, d.month_name,
    p.category, p.subcategory,
    l.region, l.state;

COMMENT ON MATERIALIZED VIEW mv_monthly_sales IS 'Pre-aggregated monthly sales by product and location';


-- Customer Sales Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_customer_summary AS
SELECT 
    c.customer_key,
    c.customer_id,
    c.full_name,
    c.city,
    c.state,
    COUNT(s.sale_key) AS total_purchases,
    SUM(s.quantity) AS total_items_purchased,
    SUM(s.net_amount) AS lifetime_value,
    AVG(s.net_amount) AS avg_order_value,
    MAX(d.date_value) AS last_purchase_date,
    MIN(d.date_value) AS first_purchase_date
FROM customer_dim c
LEFT JOIN sales_fact s ON c.customer_key = s.customer_key
LEFT JOIN date_dim d ON s.date_key = d.date_key
GROUP BY 
    c.customer_key, c.customer_id, c.full_name,
    c.city, c.state;

COMMENT ON MATERIALIZED VIEW mv_customer_summary IS 'Customer lifetime value and purchase history';


-- ============================================================
-- GRANTS (Adjust based on your IAM/user setup)
-- ============================================================

-- Grant read access to analytics users/roles
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_role;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO powerbi_user;


-- ============================================================
-- VACUUM AND ANALYZE
-- ============================================================

-- Run after initial data load to optimize query performance
VACUUM FULL sales_fact;
VACUUM FULL customer_dim;
VACUUM FULL product_dim;
VACUUM FULL location_dim;
VACUUM FULL date_dim;

ANALYZE sales_fact;
ANALYZE customer_dim;
ANALYZE product_dim;
ANALYZE location_dim;
ANALYZE date_dim;


-- ============================================================
-- VALIDATION QUERIES
-- ============================================================

-- Check row counts
SELECT 'customer_dim' AS table_name, COUNT(*) AS row_count FROM customer_dim
UNION ALL
SELECT 'product_dim', COUNT(*) FROM product_dim
UNION ALL
SELECT 'location_dim', COUNT(*) FROM location_dim
UNION ALL
SELECT 'date_dim', COUNT(*) FROM date_dim
UNION ALL
SELECT 'sales_fact', COUNT(*) FROM sales_fact;

-- Check for orphaned records in fact table
SELECT 
    'Orphaned Customers' AS check_type,
    COUNT(*) AS orphan_count
FROM sales_fact s
LEFT JOIN customer_dim c ON s.customer_key = c.customer_key
WHERE c.customer_key IS NULL

UNION ALL

SELECT 
    'Orphaned Products',
    COUNT(*)
FROM sales_fact s
LEFT JOIN product_dim p ON s.product_key = p.product_key
WHERE p.product_key IS NULL

UNION ALL

SELECT 
    'Orphaned Locations',
    COUNT(*)
FROM sales_fact s
LEFT JOIN location_dim l ON s.location_key = l.location_key
WHERE l.location_key IS NULL

UNION ALL

SELECT 
    'Orphaned Dates',
    COUNT(*)
FROM sales_fact s
LEFT JOIN date_dim d ON s.date_key = d.date_key
WHERE d.date_key IS NULL;

-- Schema created successfully!




