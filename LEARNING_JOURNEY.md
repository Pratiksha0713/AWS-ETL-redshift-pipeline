# My Data Engineering Learning Journey

## Project Overview
This project represents my journey into data engineering, building a complete AWS ETL pipeline from scratch.

## What I Built
A production-ready data pipeline that processes sales data through AWS services, implementing industry best practices for data engineering.

## My Learning Process

### Week 1: Understanding the Requirements
- Researched ETL pipeline architecture
- Studied star schema design patterns
- Learned about AWS Glue and Redshift capabilities

### Week 2: Building the Foundation
- Set up AWS account and configured services
- Created sample datasets for testing
- Designed the star schema (4 dimensions + 1 fact table)

### Week 3: Development
- Developed PySpark ETL transformations in AWS Glue
- Built Airflow DAG for orchestration
- Implemented data quality checks with Pandera

### Week 4: Testing & Documentation
- Added comprehensive data validation
- Set up CI/CD pipeline with GitHub Actions
- Created detailed documentation and diagrams

## Key Challenges & Solutions

### Challenge 1: PySpark Transformations
**Problem:** Struggled with joining multiple tables and handling null values
**Solution:** Learned to use window functions and coalesce for null handling

### Challenge 2: Redshift Performance
**Problem:** Initial queries were slow
**Solution:** Implemented distribution keys and sort keys based on query patterns

### Challenge 3: Data Quality
**Problem:** Needed automated validation
**Solution:** Integrated Pandera schemas for comprehensive testing

## Technical Skills Developed
- ✅ AWS Services (S3, Glue, Redshift, IAM)
- ✅ PySpark data transformations
- ✅ SQL optimization (distribution/sort keys)
- ✅ Apache Airflow orchestration
- ✅ Data quality validation (Pandera)
- ✅ CI/CD with GitHub Actions
- ✅ Star schema design

## What I'd Do Differently
1. Start with incremental loading instead of full refresh
2. Implement SCD Type 2 for historical tracking
3. Add more comprehensive monitoring with CloudWatch
4. Use Terraform for infrastructure as code

## Next Steps
- [ ] Deploy to actual AWS environment
- [ ] Add incremental loading
- [ ] Implement real-time streaming with Kinesis
- [ ] Create Power BI dashboards with real data
- [ ] Add dbt for transformation layer

## Resources That Helped Me
- AWS Glue Documentation
- Apache Airflow Best Practices
- Star Schema: The Complete Reference (book)
- YouTube tutorials on PySpark
- Data Engineering communities on Reddit/Discord

---

**Author:** Pratiksha
**Date:** November 2025
**Contact:** [Your LinkedIn/Email]




