"""
Airflow DAG for AWS Glue ETL and Redshift Data Pipeline
Orchestrates: S3 → Glue Crawler → Glue ETL Job → Redshift COPY
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.operators.glue_crawler import GlueCrawlerOperator
from airflow.providers.amazon.aws.operators.s3 import S3CreateBucketOperator
from airflow.providers.amazon.aws.sensors.glue import GlueJobSensor
from airflow.providers.amazon.aws.sensors.glue_crawler import GlueCrawlerSensor
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.amazon.aws.transfers.s3_to_redshift import S3ToRedshiftOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
import boto3
import logging

logger = logging.getLogger(__name__)

# Configuration
AWS_REGION = 'us-east-1'
S3_BUCKET_RAW = 'your-raw-data-bucket'
S3_BUCKET_CURATED = 'your-curated-data-bucket'
GLUE_DATABASE = 'sales_db'
GLUE_CRAWLER_NAME = 'raw-data-crawler'
GLUE_JOB_NAME = 'raw-to-curated-etl'
REDSHIFT_CONN_ID = 'redshift_default'
AWS_CONN_ID = 'aws_default'
IAM_ROLE_ARN = 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftCopyRole'

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}


def validate_s3_data(**context):
    """Validate that raw data exists in S3 before processing"""
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    execution_date = context['ds']
    
    prefixes = ['customers/', 'products/', 'sales/', 'locations/']
    
    for prefix in prefixes:
        try:
            response = s3_client.list_objects_v2(
                Bucket=S3_BUCKET_RAW,
                Prefix=prefix,
                MaxKeys=1
            )
            if 'Contents' not in response:
                raise ValueError(f"No data found in s3://{S3_BUCKET_RAW}/{prefix}")
            logger.info(f"✓ Validated data in {prefix}")
        except Exception as e:
            logger.error(f"✗ Validation failed for {prefix}: {str(e)}")
            raise
    
    logger.info("All S3 data validations passed!")
    return True


def check_glue_catalog_tables(**context):
    """Verify Glue Catalog has required tables after crawling"""
    glue_client = boto3.client('glue', region_name=AWS_REGION)
    
    required_tables = ['customers', 'products', 'sales', 'locations']
    
    try:
        response = glue_client.get_tables(DatabaseName=GLUE_DATABASE)
        existing_tables = [table['Name'] for table in response['TableList']]
        
        for table in required_tables:
            if table not in existing_tables:
                raise ValueError(f"Required table '{table}' not found in Glue Catalog")
            logger.info(f"✓ Found table: {table}")
        
        logger.info("All required tables exist in Glue Catalog!")
        return True
    except Exception as e:
        logger.error(f"Glue Catalog validation failed: {str(e)}")
        raise


def validate_curated_data(**context):
    """Validate curated data quality before loading to Redshift"""
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    
    curated_paths = [
        'curated/customer_dim/',
        'curated/product_dim/',
        'curated/date_dim/',
        'curated/location_dim/',
        'curated/sales_fact/'
    ]
    
    for path in curated_paths:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_CURATED,
            Prefix=path
        )
        
        if 'Contents' not in response:
            raise ValueError(f"No curated data found in {path}")
        
        # Check file size (should be > 0)
        total_size = sum(obj['Size'] for obj in response['Contents'])
        if total_size == 0:
            raise ValueError(f"Curated data in {path} is empty")
        
        logger.info(f"✓ Validated {path} - Size: {total_size / (1024*1024):.2f} MB")
    
    return True


with DAG(
    dag_id='aws_glue_redshift_etl_pipeline',
    default_args=default_args,
    description='Complete ETL pipeline: S3 → Glue → Redshift → Power BI',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False,
    max_active_runs=1,
    tags=['etl', 'glue', 'redshift', 'data-engineering'],
) as dag:

    # Task 1: Validate raw data in S3
    validate_raw_data = PythonOperator(
        task_id='validate_raw_data_in_s3',
        python_callable=validate_s3_data,
        provide_context=True,
    )

    # Task 2: Run Glue Crawler to catalog raw data
    run_glue_crawler = GlueCrawlerOperator(
        task_id='crawl_raw_s3_data',
        aws_conn_id=AWS_CONN_ID,
        config={
            'Name': GLUE_CRAWLER_NAME,
            'Role': IAM_ROLE_ARN,
            'DatabaseName': GLUE_DATABASE,
            'Targets': {
                'S3Targets': [
                    {'Path': f's3://{S3_BUCKET_RAW}/customers/'},
                    {'Path': f's3://{S3_BUCKET_RAW}/products/'},
                    {'Path': f's3://{S3_BUCKET_RAW}/sales/'},
                    {'Path': f's3://{S3_BUCKET_RAW}/locations/'},
                ]
            },
        },
        wait_for_completion=True,
        poll_interval=30,
    )

    # Task 3: Wait for crawler to complete
    wait_for_crawler = GlueCrawlerSensor(
        task_id='wait_for_crawler_completion',
        crawler_name=GLUE_CRAWLER_NAME,
        aws_conn_id=AWS_CONN_ID,
        poke_interval=30,
        timeout=600,
    )

    # Task 4: Validate Glue Catalog
    validate_catalog = PythonOperator(
        task_id='validate_glue_catalog_tables',
        python_callable=check_glue_catalog_tables,
        provide_context=True,
    )

    # Task 5: Run Glue ETL Job (PySpark)
    run_glue_etl = GlueJobOperator(
        task_id='transform_raw_to_curated',
        aws_conn_id=AWS_CONN_ID,
        job_name=GLUE_JOB_NAME,
        script_location=f's3://{S3_BUCKET_CURATED}/scripts/raw_to_curated.py',
        s3_bucket=S3_BUCKET_CURATED,
        iam_role_name=IAM_ROLE_ARN.split('/')[-1],
        create_job_kwargs={
            'GlueVersion': '4.0',
            'NumberOfWorkers': 10,
            'WorkerType': 'G.1X',
            'Timeout': 120,
            'MaxRetries': 1,
        },
        script_args={
            '--SOURCE_BUCKET': S3_BUCKET_RAW,
            '--TARGET_BUCKET': S3_BUCKET_CURATED,
            '--DATABASE_NAME': GLUE_DATABASE,
        },
        wait_for_completion=True,
    )

    # Task 6: Validate curated data
    validate_curated = PythonOperator(
        task_id='validate_curated_data_quality',
        python_callable=validate_curated_data,
        provide_context=True,
    )

    # Task Group: Redshift Operations
    with TaskGroup('redshift_load_operations') as redshift_tasks:
        
        # Create Redshift schema if not exists
        create_schema = PostgresOperator(
            task_id='create_redshift_schema',
            postgres_conn_id=REDSHIFT_CONN_ID,
            sql='sql/create_redshift_schema.sql',
        )

        # Load dimension tables
        load_customer_dim = S3ToRedshiftOperator(
            task_id='load_customer_dimension',
            aws_conn_id=AWS_CONN_ID,
            redshift_conn_id=REDSHIFT_CONN_ID,
            s3_bucket=S3_BUCKET_CURATED,
            s3_key='curated/customer_dim/',
            schema='public',
            table='customer_dim',
            copy_options=['CSV', 'IGNOREHEADER 1', 'DATEFORMAT \'auto\''],
            method='REPLACE',
        )

        load_product_dim = S3ToRedshiftOperator(
            task_id='load_product_dimension',
            aws_conn_id=AWS_CONN_ID,
            redshift_conn_id=REDSHIFT_CONN_ID,
            s3_bucket=S3_BUCKET_CURATED,
            s3_key='curated/product_dim/',
            schema='public',
            table='product_dim',
            copy_options=['CSV', 'IGNOREHEADER 1'],
            method='REPLACE',
        )

        load_location_dim = S3ToRedshiftOperator(
            task_id='load_location_dimension',
            aws_conn_id=AWS_CONN_ID,
            redshift_conn_id=REDSHIFT_CONN_ID,
            s3_bucket=S3_BUCKET_CURATED,
            s3_key='curated/location_dim/',
            schema='public',
            table='location_dim',
            copy_options=['CSV', 'IGNOREHEADER 1'],
            method='REPLACE',
        )

        load_date_dim = S3ToRedshiftOperator(
            task_id='load_date_dimension',
            aws_conn_id=AWS_CONN_ID,
            redshift_conn_id=REDSHIFT_CONN_ID,
            s3_bucket=S3_BUCKET_CURATED,
            s3_key='curated/date_dim/',
            schema='public',
            table='date_dim',
            copy_options=['CSV', 'IGNOREHEADER 1', 'DATEFORMAT \'auto\''],
            method='REPLACE',
        )

        # Load fact table (depends on dimensions)
        load_sales_fact = S3ToRedshiftOperator(
            task_id='load_sales_fact',
            aws_conn_id=AWS_CONN_ID,
            redshift_conn_id=REDSHIFT_CONN_ID,
            s3_bucket=S3_BUCKET_CURATED,
            s3_key='curated/sales_fact/',
            schema='public',
            table='sales_fact',
            copy_options=['CSV', 'IGNOREHEADER 1', 'DATEFORMAT \'auto\''],
            method='APPEND',
        )

        # Run data quality checks in Redshift
        redshift_quality_checks = PostgresOperator(
            task_id='run_redshift_quality_checks',
            postgres_conn_id=REDSHIFT_CONN_ID,
            sql="""
                -- Check for null keys in fact table
                SELECT CASE 
                    WHEN COUNT(*) > 0 THEN 'FAIL: Null keys found in sales_fact'
                    ELSE 'PASS'
                END as null_check
                FROM sales_fact
                WHERE customer_key IS NULL 
                   OR product_key IS NULL 
                   OR date_key IS NULL 
                   OR location_key IS NULL;
                
                -- Check row counts
                SELECT 'customer_dim' as table_name, COUNT(*) as row_count FROM customer_dim
                UNION ALL
                SELECT 'product_dim', COUNT(*) FROM product_dim
                UNION ALL
                SELECT 'location_dim', COUNT(*) FROM location_dim
                UNION ALL
                SELECT 'date_dim', COUNT(*) FROM date_dim
                UNION ALL
                SELECT 'sales_fact', COUNT(*) FROM sales_fact;
            """,
        )

        # Define dependencies within task group
        create_schema >> [load_customer_dim, load_product_dim, load_location_dim, load_date_dim]
        [load_customer_dim, load_product_dim, load_location_dim, load_date_dim] >> load_sales_fact
        load_sales_fact >> redshift_quality_checks

    # Define overall DAG flow
    (
        validate_raw_data
        >> run_glue_crawler
        >> wait_for_crawler
        >> validate_catalog
        >> run_glue_etl
        >> validate_curated
        >> redshift_tasks
    )




