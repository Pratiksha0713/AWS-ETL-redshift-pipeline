# Power BI Dashboard Setup

## Overview
This directory contains Power BI dashboard configuration and screenshots for the Sales Analytics pipeline.

## Connection Setup

### 1. Connect Power BI to Redshift

**Step 1:** Open Power BI Desktop

**Step 2:** Click "Get Data" → "Database" → "Amazon Redshift"

**Step 3:** Enter connection details:
```
Server: your-redshift-cluster.region.redshift.amazonaws.com:5439
Database: your_database_name
```

**Step 4:** Choose authentication method:
- IAM Credentials (Recommended)
- Username/Password

**Step 5:** Select tables to import:
- `customer_dim`
- `product_dim`
- `location_dim`
- `date_dim`
- `sales_fact`
- `mv_monthly_sales` (materialized view)
- `mv_customer_summary` (materialized view)

### 2. Data Model Configuration

**Relationships:**
```
sales_fact.customer_key → customer_dim.customer_key (Many-to-One)
sales_fact.product_key → product_dim.product_key (Many-to-One)
sales_fact.location_key → location_dim.location_key (Many-to-One)
sales_fact.date_key → date_dim.date_key (Many-to-One)
```

**Mark date table:**
Right-click `date_dim` → "Mark as Date Table" → Select `date_value` column

### 3. DAX Measures

Create the following measures in Power BI:

```dax
-- Total Sales
Total Sales = SUM(sales_fact[net_amount])

-- Total Transactions
Total Transactions = COUNT(sales_fact[sale_key])

-- Average Transaction Value
Avg Transaction Value = AVERAGE(sales_fact[net_amount])

-- Unique Customers
Unique Customers = DISTINCTCOUNT(sales_fact[customer_key])

-- Total Discount
Total Discount = SUM(sales_fact[discount_amount])

-- Discount Rate
Discount Rate = DIVIDE([Total Discount], SUM(sales_fact[gross_amount]), 0)

-- Year-over-Year Growth
YoY Sales Growth = 
VAR CurrentYearSales = [Total Sales]
VAR PreviousYearSales = 
    CALCULATE(
        [Total Sales],
        SAMEPERIODLASTYEAR(date_dim[date_value])
    )
RETURN
    DIVIDE(CurrentYearSales - PreviousYearSales, PreviousYearSales, 0)

-- Top 10 Products
Top 10 Products = 
CALCULATE(
    [Total Sales],
    TOPN(10, ALL(product_dim[product_name]), [Total Sales], DESC)
)

-- Customer Lifetime Value
Customer LTV = 
SUMX(
    VALUES(customer_dim[customer_key]),
    CALCULATE(SUM(sales_fact[net_amount]))
)

-- Moving Average (30 days)
Sales MA 30 = 
AVERAGEX(
    DATESINPERIOD(date_dim[date_value], LASTDATE(date_dim[date_value]), -30, DAY),
    [Total Sales]
)
```

### 4. Dashboard Pages

#### Page 1: Executive Summary
- **KPI Cards:**
  - Total Sales (current month vs last month)
  - Total Transactions
  - Average Transaction Value
  - Unique Customers
  
- **Charts:**
  - Line Chart: Monthly Sales Trend (last 12 months)
  - Column Chart: Sales by Category
  - Map: Sales by Location/Region
  - Pie Chart: Sales by Product Category

#### Page 2: Product Analytics
- **Charts:**
  - Bar Chart: Top 10 Products by Revenue
  - Matrix: Product Performance (Category → Subcategory → Product)
  - Scatter Plot: Price vs Sales Volume
  - Waterfall Chart: Sales breakdown by category
  
- **Filters:**
  - Date Range Slicer
  - Category Dropdown
  - Brand Dropdown

#### Page 3: Customer Analytics
- **Charts:**
  - Bar Chart: Top 20 Customers by Lifetime Value
  - Histogram: Customer Purchase Frequency Distribution
  - Scatter Plot: Recency vs Frequency vs Monetary (RFM)
  - Table: Customer Segment Summary
  
- **Customer Segments:**
  - VIP (Top 10% by LTV)
  - Regular (11-50%)
  - Occasional (51-100%)

#### Page 4: Geographic Analysis
- **Charts:**
  - Filled Map: Sales by State
  - Bar Chart: Top 10 Stores by Revenue
  - Line Chart: Regional Sales Trend
  - Table: Store Performance Metrics
  
- **Filters:**
  - Region Slicer
  - State Multi-select

#### Page 5: Time Intelligence
- **Charts:**
  - Line Chart: Daily Sales with Moving Average
  - Matrix: Year-Month-Day hierarchy sales
  - Column Chart: Weekday vs Weekend sales
  - KPI: Year-over-Year Growth Rate
  
- **Date Filters:**
  - Relative Date Filter
  - Fiscal Year Slicer

### 5. Refresh Schedule

**For Power BI Service:**

1. Publish report to Power BI Service
2. Configure Gateway (for on-premises Redshift connection)
3. Set up scheduled refresh:
   - Daily at 4:00 AM (after ETL completes at 2-3 AM)
   - Email notifications on failure

**Gateway Configuration:**
```
Data Source: Amazon Redshift
Server: your-cluster.region.redshift.amazonaws.com
Database: your_database
Authentication: Username/Password or IAM
```

### 6. Performance Optimization

**Best Practices:**

1. **Use DirectQuery for real-time data:**
   - Good for large datasets
   - Queries go directly to Redshift

2. **Use Import mode for better performance:**
   - Faster visualizations
   - Requires scheduled refresh
   - Recommended for datasets < 1GB

3. **Use Aggregations:**
   - Leverage materialized views (`mv_monthly_sales`, `mv_customer_summary`)
   - Create Power BI aggregation tables

4. **Query Reduction:**
   - Enable "Reduce number of queries sent" in Options
   - Use query folding where possible

### 7. Row-Level Security (RLS)

If implementing user-level access control:

```dax
-- RLS Rule for Regional Managers
[region] = USERNAME()

-- RLS Rule for Store Managers
[location_id] IN VALUES(user_store_mapping[location_id])
```

### 8. Publishing Checklist

- [ ] All data sources configured
- [ ] Relationships validated
- [ ] DAX measures tested
- [ ] Filters and slicers working
- [ ] Performance optimized
- [ ] Refresh schedule configured
- [ ] Row-level security implemented (if needed)
- [ ] Shared with stakeholders
- [ ] Gateway configured (if required)

### 9. Sample Dashboard Screenshots

Place your Power BI dashboard screenshots here:
- `executive_summary.png`
- `product_analytics.png`
- `customer_analytics.png`
- `geographic_analysis.png`
- `time_intelligence.png`

### 10. Troubleshooting

**Connection Issues:**
```
Error: Cannot connect to Redshift
Solution: Check security groups, VPC, and firewall rules
```

**Slow Performance:**
```
Issue: Dashboard loads slowly
Solution: 
1. Switch to DirectQuery
2. Use materialized views
3. Optimize Redshift queries (vacuum, analyze)
4. Implement aggregations
```

**Refresh Failures:**
```
Issue: Scheduled refresh fails
Solution:
1. Verify gateway is online
2. Check credentials
3. Test connection manually
4. Review activity log
```

---

## Additional Resources

- [Power BI Documentation](https://docs.microsoft.com/power-bi/)
- [Amazon Redshift Connector](https://docs.aws.amazon.com/redshift/latest/mgmt/connecting-via-client-tools.html)
- [DAX Guide](https://dax.guide/)

