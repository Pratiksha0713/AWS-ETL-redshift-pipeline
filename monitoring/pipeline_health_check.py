"""
Custom Pipeline Health Check Script
Author: Pratiksha
Description: Monitors ETL pipeline health and data quality metrics
"""

import boto3
import psycopg2
from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineHealthMonitor:
    """
    Custom monitoring class for AWS ETL Redshift pipeline
    Checks:
    - Glue job status
    - Redshift data freshness
    - Data quality metrics
    - Table row counts
    """
    
    def __init__(self, region='us-east-1'):
        self.glue_client = boto3.client('glue', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        
    def check_glue_job_health(self, job_name: str) -> Dict:
        """Check recent Glue job runs"""
        try:
            response = self.glue_client.get_job_runs(
                JobName=job_name,
                MaxResults=5
            )
            
            recent_runs = response['JobRuns']
            
            health_status = {
                'job_name': job_name,
                'last_run_status': recent_runs[0]['JobRunState'] if recent_runs else 'NO_RUNS',
                'last_run_time': recent_runs[0]['StartedOn'] if recent_runs else None,
                'success_rate': self._calculate_success_rate(recent_runs),
                'avg_duration_minutes': self._calculate_avg_duration(recent_runs)
            }
            
            logger.info(f"✓ Glue Job Health: {health_status}")
            return health_status
            
        except Exception as e:
            logger.error(f"✗ Failed to check Glue job health: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_success_rate(self, runs: List) -> float:
        """Calculate success rate from recent runs"""
        if not runs:
            return 0.0
        
        successful = sum(1 for run in runs if run['JobRunState'] == 'SUCCEEDED')
        return (successful / len(runs)) * 100
    
    def _calculate_avg_duration(self, runs: List) -> float:
        """Calculate average run duration in minutes"""
        if not runs:
            return 0.0
        
        durations = []
        for run in runs:
            if 'CompletedOn' in run and 'StartedOn' in run:
                duration = (run['CompletedOn'] - run['StartedOn']).total_seconds() / 60
                durations.append(duration)
        
        return sum(durations) / len(durations) if durations else 0.0
    
    def check_s3_data_freshness(self, bucket: str, prefix: str, 
                                max_age_hours: int = 24) -> Dict:
        """Check if S3 data is fresh"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=1
            )
            
            if 'Contents' not in response:
                return {'status': 'NO_DATA', 'fresh': False}
            
            last_modified = response['Contents'][0]['LastModified']
            age_hours = (datetime.now(last_modified.tzinfo) - last_modified).total_seconds() / 3600
            
            is_fresh = age_hours <= max_age_hours
            
            status = {
                'bucket': bucket,
                'prefix': prefix,
                'last_modified': last_modified,
                'age_hours': round(age_hours, 2),
                'fresh': is_fresh,
                'threshold_hours': max_age_hours
            }
            
            if is_fresh:
                logger.info(f"✓ S3 Data Fresh: {status}")
            else:
                logger.warning(f"⚠ S3 Data Stale: {status}")
            
            return status
            
        except Exception as e:
            logger.error(f"✗ Failed to check S3 freshness: {str(e)}")
            return {'error': str(e)}


class RedshiftHealthMonitor:
    """Monitor Redshift data warehouse health"""
    
    def __init__(self, host: str, port: int, database: str, 
                 user: str, password: str):
        self.conn_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
    
    def check_table_row_counts(self) -> pd.DataFrame:
        """Get row counts for all tables"""
        query = """
        SELECT 
            schemaname,
            tablename,
            n_live_tup as row_count,
            last_vacuum,
            last_analyze
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            df = pd.read_sql(query, conn)
            conn.close()
            
            logger.info(f"✓ Retrieved row counts for {len(df)} tables")
            return df
            
        except Exception as e:
            logger.error(f"✗ Failed to get row counts: {str(e)}")
            return pd.DataFrame()
    
    def check_data_quality_metrics(self) -> Dict:
        """Run data quality checks on fact table"""
        checks = {
            'null_keys': self._check_null_foreign_keys(),
            'negative_values': self._check_negative_values(),
            'future_dates': self._check_future_dates(),
            'orphaned_records': self._check_orphaned_records()
        }
        
        all_passed = all(check['passed'] for check in checks.values())
        
        status = {
            'overall_status': 'PASSED' if all_passed else 'FAILED',
            'checks': checks,
            'timestamp': datetime.now().isoformat()
        }
        
        if all_passed:
            logger.info("✓ All data quality checks passed")
        else:
            logger.warning("⚠ Some data quality checks failed")
        
        return status
    
    def _check_null_foreign_keys(self) -> Dict:
        """Check for null foreign keys in fact table"""
        query = """
        SELECT 
            COUNT(*) as total_rows,
            SUM(CASE WHEN customer_key IS NULL THEN 1 ELSE 0 END) as null_customers,
            SUM(CASE WHEN product_key IS NULL THEN 1 ELSE 0 END) as null_products,
            SUM(CASE WHEN location_key IS NULL THEN 1 ELSE 0 END) as null_locations,
            SUM(CASE WHEN date_key IS NULL THEN 1 ELSE 0 END) as null_dates
        FROM sales_fact;
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            
            total_nulls = sum(result[1:])
            
            return {
                'check_name': 'Null Foreign Keys',
                'passed': total_nulls == 0,
                'null_count': total_nulls,
                'details': {
                    'total_rows': result[0],
                    'null_customers': result[1],
                    'null_products': result[2],
                    'null_locations': result[3],
                    'null_dates': result[4]
                }
            }
            
        except Exception as e:
            return {'check_name': 'Null Foreign Keys', 'passed': False, 'error': str(e)}
    
    def _check_negative_values(self) -> Dict:
        """Check for negative amounts/quantities"""
        query = """
        SELECT 
            COUNT(*) as negative_quantity,
            SUM(CASE WHEN net_amount < 0 THEN 1 ELSE 0 END) as negative_amount
        FROM sales_fact
        WHERE quantity < 0 OR net_amount < 0;
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            
            return {
                'check_name': 'Negative Values',
                'passed': result[0] == 0 and result[1] == 0,
                'negative_quantity': result[0],
                'negative_amount': result[1]
            }
            
        except Exception as e:
            return {'check_name': 'Negative Values', 'passed': False, 'error': str(e)}
    
    def _check_future_dates(self) -> Dict:
        """Check for dates in the future"""
        query = """
        SELECT COUNT(*)
        FROM sales_fact sf
        JOIN date_dim dd ON sf.date_key = dd.date_key
        WHERE dd.date_value > CURRENT_DATE;
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]
            conn.close()
            
            return {
                'check_name': 'Future Dates',
                'passed': count == 0,
                'future_date_count': count
            }
            
        except Exception as e:
            return {'check_name': 'Future Dates', 'passed': False, 'error': str(e)}
    
    def _check_orphaned_records(self) -> Dict:
        """Check for orphaned records in fact table"""
        query = """
        SELECT 
            'customer' as dim,
            COUNT(*) as orphaned_count
        FROM sales_fact sf
        LEFT JOIN customer_dim cd ON sf.customer_key = cd.customer_key
        WHERE cd.customer_key IS NULL
        
        UNION ALL
        
        SELECT 
            'product',
            COUNT(*)
        FROM sales_fact sf
        LEFT JOIN product_dim pd ON sf.product_key = pd.product_key
        WHERE pd.product_key IS NULL;
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            
            total_orphaned = sum(row[1] for row in results)
            
            return {
                'check_name': 'Orphaned Records',
                'passed': total_orphaned == 0,
                'orphaned_count': total_orphaned,
                'details': {row[0]: row[1] for row in results}
            }
            
        except Exception as e:
            return {'check_name': 'Orphaned Records', 'passed': False, 'error': str(e)}


def generate_health_report():
    """Generate comprehensive health report"""
    print("=" * 80)
    print("AWS ETL REDSHIFT PIPELINE - HEALTH CHECK REPORT")
    print("Author: Pratiksha")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # NOTE: Update these with your actual AWS credentials and endpoints
    # For demo purposes, these are placeholders
    
    print("\n📊 Pipeline Health Monitoring")
    print("-" * 80)
    print("✓ Custom monitoring script created")
    print("✓ Automated health checks implemented")
    print("✓ Data quality metrics defined")
    print("\nTo run actual health checks:")
    print("1. Configure AWS credentials")
    print("2. Update Redshift connection parameters")
    print("3. Run: python monitoring/pipeline_health_check.py")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    generate_health_report()




