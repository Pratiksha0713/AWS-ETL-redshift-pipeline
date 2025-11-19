"""
AWS Glue ETL Job: Transform Raw Data to Curated Star Schema
Transforms: Raw CSV files → Clean, validated, star schema ready data
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *
from datetime import datetime, timedelta
import logging

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'SOURCE_BUCKET',
    'TARGET_BUCKET',
    'DATABASE_NAME'
])

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configuration
SOURCE_BUCKET = args['SOURCE_BUCKET']
TARGET_BUCKET = args['TARGET_BUCKET']
DATABASE_NAME = args['DATABASE_NAME']

logger.info(f"Starting ETL Job: {args['JOB_NAME']}")
logger.info(f"Source: s3://{SOURCE_BUCKET}")
logger.info(f"Target: s3://{TARGET_BUCKET}")


def read_from_catalog(table_name):
    """Read data from Glue Data Catalog"""
    try:
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=DATABASE_NAME,
            table_name=table_name,
            transformation_ctx=f"read_{table_name}"
        )
        df = dynamic_frame.toDF()
        logger.info(f"✓ Read {df.count()} rows from {table_name}")
        return df
    except Exception as e:
        logger.error(f"✗ Failed to read {table_name}: {str(e)}")
        raise


def write_to_s3(df, path, table_name):
    """Write DataFrame to S3 as Parquet/CSV"""
    try:
        # Convert to DynamicFrame for Glue optimizations
        dynamic_frame = DynamicFrame.fromDF(df, glueContext, f"write_{table_name}")
        
        # Write as CSV for Redshift COPY
        glueContext.write_dynamic_frame.from_options(
            frame=dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": f"s3://{TARGET_BUCKET}/{path}",
                "partitionKeys": []
            },
            format="csv",
            format_options={
                "quoteChar": '"',
                "separator": ",",
                "writeHeader": True
            },
            transformation_ctx=f"write_{table_name}"
        )
        
        logger.info(f"✓ Wrote {df.count()} rows to s3://{TARGET_BUCKET}/{path}")
    except Exception as e:
        logger.error(f"✗ Failed to write {table_name}: {str(e)}")
        raise


def build_customer_dimension(customers_df):
    """
    Transform raw customer data to SCD Type 1 dimension
    """
    logger.info("Building customer dimension...")
    
    # Data cleansing and transformation
    customer_dim = customers_df \
        .withColumn("customer_key", F.monotonically_increasing_id()) \
        .withColumn("customer_id", F.col("customer_id").cast("string")) \
        .withColumn("full_name", F.trim(F.concat_ws(" ", F.col("first_name"), F.col("last_name")))) \
        .withColumn("email", F.lower(F.trim(F.col("email")))) \
        .withColumn("phone", F.regexp_replace(F.col("phone"), "[^0-9]", "")) \
        .withColumn("created_date", F.coalesce(F.col("created_date"), F.current_date())) \
        .withColumn("is_active", F.coalesce(F.col("is_active"), F.lit(True))) \
        .withColumn("etl_inserted_date", F.current_timestamp()) \
        .select(
            "customer_key",
            "customer_id",
            "full_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "created_date",
            "is_active",
            "etl_inserted_date"
        )
    
    # Remove duplicates - keep most recent
    window_spec = Window.partitionBy("customer_id").orderBy(F.desc("created_date"))
    customer_dim = customer_dim \
        .withColumn("row_num", F.row_number().over(window_spec)) \
        .filter(F.col("row_num") == 1) \
        .drop("row_num")
    
    # Data quality validations
    null_count = customer_dim.filter(F.col("customer_id").isNull()).count()
    if null_count > 0:
        logger.warning(f"Found {null_count} customers with null IDs - filtering out")
        customer_dim = customer_dim.filter(F.col("customer_id").isNotNull())
    
    logger.info(f"✓ Built customer dimension with {customer_dim.count()} records")
    return customer_dim


def build_product_dimension(products_df):
    """
    Transform raw product data to SCD Type 1 dimension
    """
    logger.info("Building product dimension...")
    
    product_dim = products_df \
        .withColumn("product_key", F.monotonically_increasing_id()) \
        .withColumn("product_id", F.col("product_id").cast("string")) \
        .withColumn("product_name", F.trim(F.col("product_name"))) \
        .withColumn("category", F.upper(F.trim(F.col("category")))) \
        .withColumn("subcategory", F.upper(F.trim(F.col("subcategory")))) \
        .withColumn("unit_price", F.col("unit_price").cast("decimal(10,2)")) \
        .withColumn("cost", F.col("cost").cast("decimal(10,2)")) \
        .withColumn("margin", 
            F.when(F.col("unit_price") > 0, 
                ((F.col("unit_price") - F.col("cost")) / F.col("unit_price")) * 100
            ).otherwise(0)
        ) \
        .withColumn("is_active", F.coalesce(F.col("is_active"), F.lit(True))) \
        .withColumn("etl_inserted_date", F.current_timestamp()) \
        .select(
            "product_key",
            "product_id",
            "product_name",
            "category",
            "subcategory",
            "brand",
            "unit_price",
            "cost",
            "margin",
            "is_active",
            "etl_inserted_date"
        )
    
    # Remove duplicates
    window_spec = Window.partitionBy("product_id").orderBy(F.desc("etl_inserted_date"))
    product_dim = product_dim \
        .withColumn("row_num", F.row_number().over(window_spec)) \
        .filter(F.col("row_num") == 1) \
        .drop("row_num")
    
    # Validation
    product_dim = product_dim.filter(
        (F.col("product_id").isNotNull()) & 
        (F.col("unit_price") >= 0)
    )
    
    logger.info(f"✓ Built product dimension with {product_dim.count()} records")
    return product_dim


def build_location_dimension(locations_df):
    """
    Transform raw location data to dimension
    """
    logger.info("Building location dimension...")
    
    location_dim = locations_df \
        .withColumn("location_key", F.monotonically_increasing_id()) \
        .withColumn("location_id", F.col("location_id").cast("string")) \
        .withColumn("store_name", F.trim(F.col("store_name"))) \
        .withColumn("city", F.trim(F.col("city"))) \
        .withColumn("state", F.upper(F.trim(F.col("state")))) \
        .withColumn("region", F.upper(F.trim(F.col("region")))) \
        .withColumn("country", F.upper(F.trim(F.col("country")))) \
        .withColumn("etl_inserted_date", F.current_timestamp()) \
        .select(
            "location_key",
            "location_id",
            "store_name",
            "address",
            "city",
            "state",
            "zip_code",
            "region",
            "country",
            "etl_inserted_date"
        )
    
    # Remove duplicates
    window_spec = Window.partitionBy("location_id").orderBy(F.desc("etl_inserted_date"))
    location_dim = location_dim \
        .withColumn("row_num", F.row_number().over(window_spec)) \
        .filter(F.col("row_num") == 1) \
        .drop("row_num")
    
    location_dim = location_dim.filter(F.col("location_id").isNotNull())
    
    logger.info(f"✓ Built location dimension with {location_dim.count()} records")
    return location_dim


def build_date_dimension(start_date='2020-01-01', end_date='2030-12-31'):
    """
    Generate a complete date dimension table
    """
    logger.info("Building date dimension...")
    
    # Generate date range
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    date_list = [(start + timedelta(days=x)).strftime('%Y-%m-%d') 
                 for x in range((end - start).days + 1)]
    
    dates_df = spark.createDataFrame([(d,) for d in date_list], ["date_value"])
    
    date_dim = dates_df \
        .withColumn("date_value", F.to_date(F.col("date_value"))) \
        .withColumn("date_key", F.date_format(F.col("date_value"), "yyyyMMdd").cast("int")) \
        .withColumn("year", F.year(F.col("date_value"))) \
        .withColumn("quarter", F.quarter(F.col("date_value"))) \
        .withColumn("month", F.month(F.col("date_value"))) \
        .withColumn("month_name", F.date_format(F.col("date_value"), "MMMM")) \
        .withColumn("day", F.dayofmonth(F.col("date_value"))) \
        .withColumn("day_of_week", F.dayofweek(F.col("date_value"))) \
        .withColumn("day_name", F.date_format(F.col("date_value"), "EEEE")) \
        .withColumn("week_of_year", F.weekofyear(F.col("date_value"))) \
        .withColumn("is_weekend", 
            F.when(F.col("day_of_week").isin([1, 7]), True).otherwise(False)
        ) \
        .withColumn("fiscal_year", 
            F.when(F.col("month") >= 7, F.col("year") + 1).otherwise(F.col("year"))
        ) \
        .withColumn("etl_inserted_date", F.current_timestamp()) \
        .select(
            "date_key",
            "date_value",
            "year",
            "quarter",
            "month",
            "month_name",
            "day",
            "day_of_week",
            "day_name",
            "week_of_year",
            "is_weekend",
            "fiscal_year",
            "etl_inserted_date"
        )
    
    logger.info(f"✓ Built date dimension with {date_dim.count()} records")
    return date_dim


def build_sales_fact(sales_df, customer_dim, product_dim, location_dim, date_dim):
    """
    Build sales fact table with foreign keys to dimensions
    """
    logger.info("Building sales fact table...")
    
    # Prepare sales data
    sales_prep = sales_df \
        .withColumn("sale_date", F.to_date(F.col("sale_date"))) \
        .withColumn("date_key", F.date_format(F.col("sale_date"), "yyyyMMdd").cast("int")) \
        .withColumn("quantity", F.col("quantity").cast("int")) \
        .withColumn("unit_price", F.col("unit_price").cast("decimal(10,2)")) \
        .withColumn("discount_amount", F.coalesce(F.col("discount_amount").cast("decimal(10,2)"), F.lit(0))) \
        .withColumn("tax_amount", F.coalesce(F.col("tax_amount").cast("decimal(10,2)"), F.lit(0)))
    
    # Join with dimensions to get surrogate keys
    sales_fact = sales_prep \
        .join(customer_dim.select("customer_key", "customer_id"), "customer_id", "left") \
        .join(product_dim.select("product_key", "product_id"), "product_id", "left") \
        .join(location_dim.select("location_key", "location_id"), "location_id", "left") \
        .join(date_dim.select("date_key"), "date_key", "left")
    
    # Calculate measures
    sales_fact = sales_fact \
        .withColumn("gross_amount", F.col("quantity") * F.col("unit_price")) \
        .withColumn("net_amount", 
            F.col("gross_amount") - F.col("discount_amount") + F.col("tax_amount")
        ) \
        .withColumn("etl_inserted_date", F.current_timestamp()) \
        .select(
            F.monotonically_increasing_id().alias("sale_key"),
            "customer_key",
            "product_key",
            "location_key",
            "date_key",
            "quantity",
            "unit_price",
            "gross_amount",
            "discount_amount",
            "tax_amount",
            "net_amount",
            "etl_inserted_date"
        )
    
    # Data quality checks
    null_keys = sales_fact.filter(
        F.col("customer_key").isNull() | 
        F.col("product_key").isNull() | 
        F.col("location_key").isNull() | 
        F.col("date_key").isNull()
    ).count()
    
    if null_keys > 0:
        logger.warning(f"Found {null_keys} sales records with missing dimension keys - filtering out")
        sales_fact = sales_fact.filter(
            F.col("customer_key").isNotNull() &
            F.col("product_key").isNotNull() &
            F.col("location_key").isNotNull() &
            F.col("date_key").isNotNull()
        )
    
    logger.info(f"✓ Built sales fact with {sales_fact.count()} records")
    return sales_fact


# ============= MAIN ETL FLOW =============

try:
    # Step 1: Read raw data from Glue Catalog
    logger.info("=" * 80)
    logger.info("STEP 1: Reading raw data from Glue Data Catalog")
    logger.info("=" * 80)
    
    customers_raw = read_from_catalog("customers")
    products_raw = read_from_catalog("products")
    locations_raw = read_from_catalog("locations")
    sales_raw = read_from_catalog("sales")
    
    # Step 2: Build dimension tables
    logger.info("=" * 80)
    logger.info("STEP 2: Building dimension tables")
    logger.info("=" * 80)
    
    customer_dim = build_customer_dimension(customers_raw)
    product_dim = build_product_dimension(products_raw)
    location_dim = build_location_dimension(locations_raw)
    date_dim = build_date_dimension()
    
    # Step 3: Build fact table
    logger.info("=" * 80)
    logger.info("STEP 3: Building fact table")
    logger.info("=" * 80)
    
    sales_fact = build_sales_fact(sales_raw, customer_dim, product_dim, location_dim, date_dim)
    
    # Step 4: Write to S3
    logger.info("=" * 80)
    logger.info("STEP 4: Writing curated data to S3")
    logger.info("=" * 80)
    
    write_to_s3(customer_dim, "curated/customer_dim", "customer_dim")
    write_to_s3(product_dim, "curated/product_dim", "product_dim")
    write_to_s3(location_dim, "curated/location_dim", "location_dim")
    write_to_s3(date_dim, "curated/date_dim", "date_dim")
    write_to_s3(sales_fact, "curated/sales_fact", "sales_fact")
    
    # Step 5: Final summary
    logger.info("=" * 80)
    logger.info("ETL JOB COMPLETED SUCCESSFULLY!")
    logger.info("=" * 80)
    logger.info(f"Customer Dimension: {customer_dim.count()} records")
    logger.info(f"Product Dimension: {product_dim.count()} records")
    logger.info(f"Location Dimension: {location_dim.count()} records")
    logger.info(f"Date Dimension: {date_dim.count()} records")
    logger.info(f"Sales Fact: {sales_fact.count()} records")
    logger.info("=" * 80)
    
except Exception as e:
    logger.error(f"ETL Job Failed: {str(e)}")
    raise

finally:
    job.commit()




