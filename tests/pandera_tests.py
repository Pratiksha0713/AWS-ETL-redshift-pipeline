"""
Data Quality Tests using Pandera and Great Expectations
Tests data quality before and after ETL transformations
"""

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check, Index
from datetime import datetime
import great_expectations as gx
from great_expectations.core.batch import RuntimeBatchRequest
import logging
import boto3
from io import StringIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# PANDERA SCHEMAS FOR RAW DATA VALIDATION
# ============================================================

# Schema for raw customer data
customer_raw_schema = DataFrameSchema(
    {
        "customer_id": Column(str, checks=[
            Check.str_matches(r"^CUST\d+$"),  # Format: CUST12345
            Check(lambda s: ~s.duplicated().any(), error="Duplicate customer IDs found"),
        ], nullable=False),
        "first_name": Column(str, checks=[
            Check.str_length(min_value=1, max_value=100),
        ], nullable=False),
        "last_name": Column(str, checks=[
            Check.str_length(min_value=1, max_value=100),
        ], nullable=False),
        "email": Column(str, checks=[
            Check.str_matches(r"^[\w\.-]+@[\w\.-]+\.\w+$"),  # Email format
        ], nullable=False),
        "phone": Column(str, nullable=True),
        "address": Column(str, nullable=True),
        "city": Column(str, nullable=True),
        "state": Column(str, checks=[
            Check.str_length(min_value=2, max_value=50),
        ], nullable=True),
        "zip_code": Column(str, nullable=True),
        "country": Column(str, nullable=True),
        "created_date": Column(pd.DatetimeTZDtype(tz="UTC") | "datetime64[ns]", 
                              nullable=True),
        "is_active": Column(bool, nullable=True),
    },
    strict=False,  # Allow additional columns
    coerce=True,   # Attempt type coercion
)


# Schema for raw product data
product_raw_schema = DataFrameSchema(
    {
        "product_id": Column(str, checks=[
            Check.str_matches(r"^PROD\d+$"),
            Check(lambda s: ~s.duplicated().any()),
        ], nullable=False),
        "product_name": Column(str, checks=[
            Check.str_length(min_value=1, max_value=255),
        ], nullable=False),
        "category": Column(str, nullable=False),
        "subcategory": Column(str, nullable=True),
        "brand": Column(str, nullable=True),
        "unit_price": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
            Check.less_than(100000),  # Reasonable upper limit
        ], nullable=False),
        "cost": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
        ], nullable=True),
        "is_active": Column(bool, nullable=True),
    },
    strict=False,
    coerce=True,
)


# Schema for raw sales data
sales_raw_schema = DataFrameSchema(
    {
        "sale_id": Column(str, nullable=False),
        "customer_id": Column(str, checks=[
            Check.str_matches(r"^CUST\d+$"),
        ], nullable=False),
        "product_id": Column(str, checks=[
            Check.str_matches(r"^PROD\d+$"),
        ], nullable=False),
        "location_id": Column(str, checks=[
            Check.str_matches(r"^LOC\d+$"),
        ], nullable=False),
        "sale_date": Column(pd.DatetimeTZDtype(tz="UTC") | "datetime64[ns]", 
                           nullable=False),
        "quantity": Column(int, checks=[
            Check.greater_than(0),
            Check.less_than(10000),
        ], nullable=False),
        "unit_price": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
        ], nullable=False),
        "discount_amount": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
        ], nullable=True),
        "tax_amount": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
        ], nullable=True),
    },
    strict=False,
    coerce=True,
)


# Schema for location data
location_raw_schema = DataFrameSchema(
    {
        "location_id": Column(str, checks=[
            Check.str_matches(r"^LOC\d+$"),
            Check(lambda s: ~s.duplicated().any()),
        ], nullable=False),
        "store_name": Column(str, nullable=False),
        "address": Column(str, nullable=True),
        "city": Column(str, nullable=False),
        "state": Column(str, nullable=False),
        "zip_code": Column(str, nullable=True),
        "region": Column(str, checks=[
            Check.isin(["NORTH", "SOUTH", "EAST", "WEST", "CENTRAL"]),
        ], nullable=True),
        "country": Column(str, nullable=False),
    },
    strict=False,
    coerce=True,
)


# ============================================================
# PANDERA SCHEMAS FOR CURATED DATA VALIDATION
# ============================================================

customer_dim_schema = DataFrameSchema(
    {
        "customer_key": Column(int, checks=[
            Check.greater_than_or_equal_to(0),
            Check(lambda s: ~s.duplicated().any()),
        ], nullable=False),
        "customer_id": Column(str, checks=[
            Check(lambda s: ~s.duplicated().any()),
        ], nullable=False),
        "full_name": Column(str, nullable=True),
        "email": Column(str, checks=[
            Check.str_matches(r"^[\w\.-]+@[\w\.-]+\.\w+$"),
        ], nullable=True),
        "etl_inserted_date": Column(pd.DatetimeTZDtype(tz="UTC") | "datetime64[ns]"),
    },
    strict=False,
)


sales_fact_schema = DataFrameSchema(
    {
        "sale_key": Column(int, checks=[
            Check.greater_than_or_equal_to(0),
            Check(lambda s: ~s.duplicated().any()),
        ], nullable=False),
        "customer_key": Column(int, nullable=False),
        "product_key": Column(int, nullable=False),
        "location_key": Column(int, nullable=False),
        "date_key": Column(int, nullable=False),
        "quantity": Column(int, checks=[
            Check.greater_than(0),
        ], nullable=False),
        "gross_amount": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
        ], nullable=False),
        "net_amount": Column(float, checks=[
            Check.greater_than_or_equal_to(0),
        ], nullable=False),
    },
    strict=False,
)


# ============================================================
# VALIDATION FUNCTIONS
# ============================================================

def validate_raw_data(df: pd.DataFrame, schema: DataFrameSchema, data_name: str) -> bool:
    """
    Validate raw data against Pandera schema
    
    Args:
        df: DataFrame to validate
        schema: Pandera schema
        data_name: Name of the dataset for logging
    
    Returns:
        bool: True if validation passes, raises exception otherwise
    """
    try:
        logger.info(f"Validating {data_name} - Shape: {df.shape}")
        validated_df = schema.validate(df, lazy=True)
        logger.info(f"✓ {data_name} validation PASSED")
        return True
    except pa.errors.SchemaErrors as err:
        logger.error(f"✗ {data_name} validation FAILED")
        logger.error(f"Schema errors:\n{err.failure_cases}")
        logger.error(f"Data sample:\n{err.data.head()}")
        raise


def validate_curated_data(df: pd.DataFrame, schema: DataFrameSchema, data_name: str) -> bool:
    """Validate curated/transformed data"""
    try:
        logger.info(f"Validating curated {data_name} - Shape: {df.shape}")
        validated_df = schema.validate(df, lazy=True)
        logger.info(f"✓ Curated {data_name} validation PASSED")
        return True
    except pa.errors.SchemaErrors as err:
        logger.error(f"✗ Curated {data_name} validation FAILED")
        logger.error(f"Schema errors:\n{err.failure_cases}")
        raise


def cross_table_validation(sales_df: pd.DataFrame, 
                          customer_df: pd.DataFrame,
                          product_df: pd.DataFrame,
                          location_df: pd.DataFrame) -> bool:
    """
    Validate referential integrity across tables
    """
    logger.info("Running cross-table validation...")
    
    # Check if all customer IDs in sales exist in customer table
    invalid_customers = set(sales_df['customer_id']) - set(customer_df['customer_id'])
    if invalid_customers:
        logger.error(f"Found {len(invalid_customers)} invalid customer IDs in sales")
        logger.error(f"Sample: {list(invalid_customers)[:5]}")
        raise ValueError("Referential integrity violation: invalid customer IDs")
    
    # Check products
    invalid_products = set(sales_df['product_id']) - set(product_df['product_id'])
    if invalid_products:
        logger.error(f"Found {len(invalid_products)} invalid product IDs in sales")
        raise ValueError("Referential integrity violation: invalid product IDs")
    
    # Check locations
    invalid_locations = set(sales_df['location_id']) - set(location_df['location_id'])
    if invalid_locations:
        logger.error(f"Found {len(invalid_locations)} invalid location IDs in sales")
        raise ValueError("Referential integrity violation: invalid location IDs")
    
    logger.info("✓ Cross-table validation PASSED")
    return True


# ============================================================
# GREAT EXPECTATIONS VALIDATION
# ============================================================

def create_gx_expectation_suite():
    """
    Create Great Expectations suite for data validation
    """
    context = gx.get_context()
    
    # Create expectation suite for sales fact
    suite = context.add_expectation_suite(
        expectation_suite_name="sales_fact_suite"
    )
    
    # Add expectations
    expectations = [
        # Column existence
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "customer_key"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "product_key"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "net_amount"}},
        
        # Null checks
        {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "customer_key"}},
        {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "product_key"}},
        {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "date_key"}},
        
        # Value ranges
        {"expectation_type": "expect_column_values_to_be_between", 
         "kwargs": {"column": "quantity", "min_value": 1, "max_value": 10000}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "net_amount", "min_value": 0}},
        
        # Uniqueness
        {"expectation_type": "expect_column_values_to_be_unique", 
         "kwargs": {"column": "sale_key"}},
        
        # Table-level expectations
        {"expectation_type": "expect_table_row_count_to_be_between",
         "kwargs": {"min_value": 1}},
    ]
    
    for exp in expectations:
        suite.add_expectation(**exp)
    
    logger.info("✓ Created Great Expectations suite")
    return suite


def run_gx_validation(df: pd.DataFrame) -> bool:
    """
    Run Great Expectations validation on DataFrame
    """
    try:
        context = gx.get_context()
        
        # Create datasource
        datasource = context.sources.add_pandas("pandas_datasource")
        data_asset = datasource.add_dataframe_asset(name="sales_fact_df")
        
        # Create batch request
        batch_request = data_asset.build_batch_request(dataframe=df)
        
        # Get expectation suite
        suite = create_gx_expectation_suite()
        
        # Run validation
        validator = context.get_validator(
            batch_request=batch_request,
            expectation_suite_name="sales_fact_suite"
        )
        
        results = validator.validate()
        
        if results.success:
            logger.info("✓ Great Expectations validation PASSED")
            return True
        else:
            logger.error("✗ Great Expectations validation FAILED")
            logger.error(f"Results: {results}")
            return False
            
    except Exception as e:
        logger.error(f"Great Expectations validation error: {str(e)}")
        raise


# ============================================================
# MAIN TEST RUNNER
# ============================================================

def run_all_validations(s3_bucket_raw: str = None, 
                       s3_bucket_curated: str = None,
                       use_local_files: bool = True):
    """
    Run all data quality tests
    
    Args:
        s3_bucket_raw: S3 bucket with raw data
        s3_bucket_curated: S3 bucket with curated data
        use_local_files: If True, use local sample files instead of S3
    """
    logger.info("=" * 80)
    logger.info("STARTING DATA QUALITY VALIDATION PIPELINE")
    logger.info("=" * 80)
    
    try:
        if use_local_files:
            # Load from local sample files
            logger.info("Loading data from local files...")
            customers_df = pd.read_csv("data_samples/customers.csv")
            products_df = pd.read_csv("data_samples/products.csv")
            locations_df = pd.read_csv("data_samples/locations.csv")
            sales_df = pd.read_csv("data_samples/sales.csv")
        else:
            # Load from S3
            logger.info(f"Loading data from S3: {s3_bucket_raw}")
            s3 = boto3.client('s3')
            # Implementation for S3 loading...
            pass
        
        # Validate raw data
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Validating Raw Data")
        logger.info("=" * 80)
        
        validate_raw_data(customers_df, customer_raw_schema, "customers")
        validate_raw_data(products_df, product_raw_schema, "products")
        validate_raw_data(locations_df, location_raw_schema, "locations")
        validate_raw_data(sales_df, sales_raw_schema, "sales")
        
        # Cross-table validation
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Cross-Table Validation")
        logger.info("=" * 80)
        
        cross_table_validation(sales_df, customers_df, products_df, locations_df)
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ ALL VALIDATIONS PASSED SUCCESSFULLY!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n✗ VALIDATION FAILED: {str(e)}")
        raise


if __name__ == "__main__":
    # Run validations
    try:
        run_all_validations(use_local_files=True)
    except Exception as e:
        logger.error(f"Test suite failed: {str(e)}")
        exit(1)




