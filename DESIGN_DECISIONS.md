# Design Decisions & Technical Rationale

This document explains the key architectural and technical decisions made in this project.

## 1. Why Star Schema?

**Decision:** Implemented star schema instead of normalized 3NF design

**Rationale:**
- ✅ Optimized for analytical queries (not OLTP)
- ✅ Simpler joins for business users
- ✅ Better query performance in Redshift
- ✅ Easier to understand for BI tools

**Trade-offs:**
- ❌ Data redundancy in dimensions
- ❌ Update complexity (but we use batch loads)

## 2. Why AWS Glue Over EMR?

**Decision:** Used AWS Glue instead of EMR for ETL

**Rationale:**
- ✅ Serverless - no cluster management
- ✅ Automatic scaling
- ✅ Pay only for job runtime
- ✅ Built-in Data Catalog
- ✅ Easier for this project size

**When I'd Use EMR:**
- For very large datasets (TB+)
- Need custom Spark configurations
- Long-running interactive analysis

## 3. Airflow for Orchestration

**Decision:** Apache Airflow instead of AWS Step Functions

**Rationale:**
- ✅ More flexible task dependencies
- ✅ Rich UI for monitoring
- ✅ Python-based DAG definition
- ✅ Extensive operator library
- ✅ Industry standard

**Alternative Considered:**
- AWS Step Functions (simpler but less flexible)
- Prefect (modern but less mature)

## 4. Distribution Keys in Redshift

**Decision:** 
- `sales_fact` distributed by `customer_key`
- Dimensions use `DISTSTYLE ALL`

**Rationale:**
- ✅ `customer_key` has high cardinality
- ✅ Most queries join facts with dimensions
- ✅ Dimensions are small enough to broadcast
- ✅ Reduces data movement during joins

**Performance Impact:**
- Query time reduced by ~60% vs default distribution

## 5. Data Quality with Pandera

**Decision:** Pandera + Great Expectations for validation

**Rationale:**
- ✅ Schema validation at compile time
- ✅ Pythonic API (familiar to me)
- ✅ Detailed error reporting
- ✅ Integration with pandas/PySpark

**Why Not Just SQL Checks:**
- Harder to maintain
- Less expressive for complex rules
- No reusability

## 6. CSV vs Parquet for Curated Zone

**Decision:** Used CSV for curated data (for Redshift COPY)

**Rationale:**
- ✅ Redshift COPY command works efficiently with CSV
- ✅ Simple to inspect and debug
- ✅ Small dataset size

**When I'd Use Parquet:**
- Larger datasets (columnar format is more efficient)
- Need schema evolution
- Using Athena for querying S3 directly

## 7. SCD Type 1 for Dimensions

**Decision:** Implemented SCD Type 1 (update in place)

**Rationale:**
- ✅ Simpler implementation
- ✅ Sufficient for this use case
- ✅ Lower storage costs

**When I'd Use SCD Type 2:**
- Need historical tracking
- Regulatory requirements
- Trend analysis on dimension changes

## 8. Materialized Views

**Decision:** Created 2 materialized views for common aggregations

**Rationale:**
- ✅ Pre-compute expensive aggregations
- ✅ Faster dashboard loading
- ✅ Reduce Redshift compute costs

**Views Created:**
- `mv_monthly_sales` - Time-based aggregations
- `mv_customer_summary` - Customer metrics

## 9. CI/CD Pipeline

**Decision:** GitHub Actions with 8 jobs

**Rationale:**
- ✅ Free for public repos
- ✅ Tight GitHub integration
- ✅ YAML-based configuration
- ✅ Extensive marketplace

**Pipeline Stages:**
1. Code quality (linting, formatting)
2. Security scanning
3. Data quality tests
4. SQL validation
5. Unit tests
6. Build & package
7. Deploy to dev
8. Notifications

## 10. Error Handling Strategy

**Decision:** Retries with exponential backoff + alerting

**Implementation:**
- Airflow: 2 retries with 5-minute delay
- Glue: 1 retry (built-in)
- Email notifications on failure

**Rationale:**
- ✅ Handle transient failures
- ✅ Don't retry indefinitely
- ✅ Alert humans for persistent issues

---

## Metrics & Performance

| Operation | Current | Target | Status |
|-----------|---------|--------|--------|
| Glue ETL | 5 min | <10 min | ✅ |
| Redshift COPY | 30 sec | <1 min | ✅ |
| End-to-end | 10 min | <15 min | ✅ |
| Data Quality | 1 min | <2 min | ✅ |

---

## Future Improvements

### Short Term
1. Add incremental loading (CDC)
2. Implement alerting to Slack
3. Add more data quality rules

### Long Term
1. Real-time streaming with Kinesis
2. dbt for transformation layer
3. Terraform for IaC
4. Multi-environment setup (Dev/QA/Prod)

---

**These decisions reflect my understanding of:**
- Data warehousing principles
- AWS service capabilities
- Trade-offs in distributed systems
- Production deployment best practices

