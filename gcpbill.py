#!/usr/bin/env python3

import argparse
import sys
import json
import csv
import warnings
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

warnings.filterwarnings('ignore', category=FutureWarning, module='google.api_core._python_version_support')

try:
    from google.cloud import billing_v1
    from google.cloud import bigquery
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError, RefreshError
    from tabulate import tabulate
except ImportError as e:
    print(f"Error: Missing required dependency: {e}")
    print("\nPlease install dependencies with:")
    print("  uv pip install -r requirements.txt")
    sys.exit(1)


class GCPBillingViewer:
    def __init__(self):
        self.credentials = None
        self.project_id = None
        self._authenticate()
        self.billing_client = billing_v1.CloudBillingClient(credentials=self.credentials)
        self.bq_client = bigquery.Client(credentials=self.credentials, project=self.project_id)

    def _authenticate(self):
        try:
            self.credentials, self.project_id = default()
        except (DefaultCredentialsError, RefreshError) as e:
            print("Error: Not authenticated with Google Cloud.")
            print(f"\nDetails: {e}")
            print("\nPlease authenticate using one of these methods:")
            print("  1. gcloud auth application-default login")
            print("  2. gcloud auth login")
            print("  3. Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            print("\nIf you see 'Reauthentication is needed', run:")
            print("  gcloud auth application-default login")
            sys.exit(1)
        except Exception as e:
            print(f"Error during authentication: {e}")
            print("\nPlease run: gcloud auth application-default login")
            sys.exit(1)

    def list_billing_accounts(self, account_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        accounts = []
        try:
            request = billing_v1.ListBillingAccountsRequest()
            page_result = self.billing_client.list_billing_accounts(request=request)
            
            for account in page_result:
                account_id = account.name.split('/')[-1]
                if account_filter and account_filter not in account.name:
                    continue
                
                accounts.append({
                    'id': account_id,
                    'name': account.name,
                    'display_name': account.display_name,
                    'open': account.open,
                    'currency': account.currency_code if hasattr(account, 'currency_code') else 'N/A'
                })
        except RefreshError as e:
            print(f"Error: Authentication expired or invalid.")
            print(f"\nDetails: {e}")
            print("\nPlease re-authenticate:")
            print("  gcloud auth application-default login")
            sys.exit(1)
        except Exception as e:
            print(f"Error listing billing accounts: {e}")
            print("\nCommon issues:")
            print("  - Insufficient permissions (need billing.accounts.list)")
            print("  - No billing accounts associated with your account")
            print("  - Authentication expired (run: gcloud auth application-default login)")
            sys.exit(1)
        
        return accounts

    def list_projects_with_billing(self, billing_account: Optional[str] = None) -> List[Dict[str, Any]]:
        projects = []
        try:
            if billing_account:
                if not billing_account.startswith('billingAccounts/'):
                    billing_account = f'billingAccounts/{billing_account}'
                
                request = billing_v1.ListProjectBillingInfoRequest(name=billing_account)
                page_result = self.billing_client.list_project_billing_info(request=request)
                
                for project_billing_info in page_result:
                    project_id = project_billing_info.project_id
                    projects.append({
                        'project_id': project_id,
                        'billing_account': project_billing_info.billing_account_name.split('/')[-1] if project_billing_info.billing_account_name else 'None',
                        'billing_enabled': project_billing_info.billing_enabled
                    })
            else:
                accounts = self.list_billing_accounts()
                for account in accounts:
                    account_name = account['name']
                    request = billing_v1.ListProjectBillingInfoRequest(name=account_name)
                    page_result = self.billing_client.list_project_billing_info(request=request)
                    
                    for project_billing_info in page_result:
                        project_id = project_billing_info.project_id
                        projects.append({
                            'project_id': project_id,
                            'billing_account': account['id'],
                            'billing_enabled': project_billing_info.billing_enabled
                        })
        except Exception as e:
            print(f"Error listing projects: {e}")
        
        return projects

    def detect_bigquery_export(self, billing_account_id: str, verbose: bool = False) -> Optional[str]:
        clean_id = billing_account_id.replace('-', '_')
        
        common_patterns = [
            f'gcp_billing_export_v1_{clean_id}',
            f'gcp_billing_export_resource_v1_{clean_id}',
        ]
        
        common_datasets = ['billing_export', 'billing_data', 'billing']
        
        try:
            datasets = list(self.bq_client.list_datasets())
            
            if verbose:
                print(f"\nDebug: Searching for billing export table...")
                print(f"Debug: Looking for patterns: {common_patterns}")
                print(f"Debug: Found {len(datasets)} datasets in project '{self.project_id}'")
            
            for dataset in datasets:
                dataset_id = dataset.dataset_id
                if verbose:
                    print(f"Debug: Checking dataset '{dataset_id}'")
                
                if dataset_id in common_datasets:
                    tables = list(self.bq_client.list_tables(dataset_id))
                    if verbose:
                        print(f"Debug:   Found {len(tables)} tables in '{dataset_id}'")
                    for table in tables:
                        if verbose:
                            print(f"Debug:     - {table.table_id}")
                        for pattern in common_patterns:
                            if pattern in table.table_id:
                                return f'{self.project_id}.{dataset_id}.{table.table_id}'
            
            for dataset in datasets:
                tables = list(self.bq_client.list_tables(dataset.dataset_id))
                for table in tables:
                    for pattern in common_patterns:
                        if pattern in table.table_id:
                            return f'{self.project_id}.{dataset.dataset_id}.{table.table_id}'
            
            if verbose:
                print(f"\nDebug: No matching billing export table found")
                print(f"Debug: Expected table name like: gcp_billing_export_v1_{clean_id}")
                
        except Exception as e:
            if verbose:
                print(f"Debug: Error during detection: {e}")
            pass
        
        return None

    def get_costs_from_bigquery(
        self,
        billing_account_id: str,
        start_date: str,
        end_date: str,
        project_filter: Optional[str] = None,
        group_by: str = 'service',
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        table_id = self.detect_bigquery_export(billing_account_id, verbose=verbose)
        
        if not table_id:
            print(f"\nBigQuery billing export not found for account: {billing_account_id}")
            print("\nTo enable billing export:")
            print("  1. Run: uv run setup_bigquery_export.py --setup --billing-account {} --project YOUR_PROJECT".format(billing_account_id))
            print("  2. Or manually configure in GCP Console → Billing → Billing export")
            print("\nNote: Billing data becomes available ~24 hours after export is enabled.")
            print("\nTip: Run with --debug flag to see what datasets/tables were found")
            return []
        
        print(f"Using BigQuery table: {table_id}")
        
        table_creation_info = self._get_table_creation_time(table_id, verbose)
        
        table_has_data = self._check_table_has_data(table_id, verbose)
        if not table_has_data:
            print("\nTable exists but contains no data.")
            if table_creation_info:
                hours_since_creation = table_creation_info['hours_since_creation']
                created_at = table_creation_info['created_at']
                
                print(f"Table created: {created_at}")
                print(f"Time elapsed: {hours_since_creation:.1f} hours")
                
                if hours_since_creation < 24:
                    hours_remaining = 24 - hours_since_creation
                    print(f"\nData should be available in ~{hours_remaining:.1f} hours (24 hours after creation).")
                    print("Billing data export typically takes up to 24 hours after table creation.")
                else:
                    print(f"\nIt's been over 24 hours since table creation.")
                    print("Possible issues:")
                    print("  1. Billing export not configured in GCP Console (only dataset/table created)")
                    print("  2. No usage/costs have been incurred yet")
                    print("  3. Export configuration error")
                    print("\nVerify billing export is enabled:")
                    print(f"  https://console.cloud.google.com/billing/{billing_account_id.replace('_', '-')}")
            else:
                print("Billing data export may not be configured or data hasn't been exported yet.")
                print("Wait ~24 hours after configuring export in GCP Console.")
            return []
        
        date_range_info = self._check_date_range_coverage(table_id, start_date, end_date, verbose)
        
        group_fields = {
            'service': 'service.description',
            'project': 'project.id',
            'day': 'DATE(usage_start_time)',
            'month': 'FORMAT_DATE("%Y-%m", usage_start_time)'
        }
        
        group_field = group_fields.get(group_by, 'service.description')
        group_label = group_by
        
        query = f"""
        SELECT
            {group_field} as category,
            ROUND(SUM(cost), 2) as total_cost,
            currency
        FROM `{table_id}`
        WHERE usage_start_time >= TIMESTAMP('{start_date}')
            AND usage_start_time < TIMESTAMP('{end_date}')
        """
        
        if project_filter:
            query += f" AND project.id = '{project_filter}'"
        
        query += f"""
        GROUP BY category, currency
        ORDER BY total_cost DESC
        """
        
        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            costs = []
            for row in results:
                costs.append({
                    group_label: row.category or 'Unknown',
                    'cost': float(row.total_cost),
                    'currency': row.currency
                })
            
            if not costs and date_range_info:
                print(f"\nNo costs found in requested range: {start_date} to {end_date}")
                if date_range_info['has_data']:
                    print(f"Available data range: {date_range_info['min_date']} to {date_range_info['max_date']}")
                    if date_range_info['outside_range']:
                        print("Your requested date range is outside the available billing data.")
            
            return costs
        except Exception as e:
            print(f"Error querying BigQuery: {e}")
            return []
    
    def _check_table_has_data(self, table_id: str, verbose: bool = False) -> bool:
        try:
            query = f"SELECT COUNT(*) as row_count FROM `{table_id}` LIMIT 1"
            if verbose:
                print(f"Debug: Checking if table has data...")
            
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            for row in results:
                row_count = row.row_count
                if verbose:
                    print(f"Debug: Table has {row_count} rows")
                return row_count > 0
            
            return False
        except Exception as e:
            if verbose:
                print(f"Debug: Error checking table data: {e}")
            return False
    
    def _get_table_creation_time(self, table_id: str, verbose: bool = False) -> Optional[Dict[str, Any]]:
        try:
            parts = table_id.split('.')
            if len(parts) == 3:
                project_id, dataset_id, table_name = parts
            else:
                return None
            
            if verbose:
                print(f"Debug: Getting table creation time for {table_id}")
            
            table_ref = self.bq_client.dataset(dataset_id, project=project_id).table(table_name)
            table = self.bq_client.get_table(table_ref)
            
            created_time = table.created
            now = datetime.now(created_time.tzinfo)
            time_diff = now - created_time
            hours_since_creation = time_diff.total_seconds() / 3600
            
            created_at_str = created_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            
            if verbose:
                print(f"Debug: Table created at {created_at_str}")
                print(f"Debug: {hours_since_creation:.1f} hours ago")
            
            return {
                'created_at': created_at_str,
                'hours_since_creation': hours_since_creation,
                'created_timestamp': created_time
            }
        except Exception as e:
            if verbose:
                print(f"Debug: Error getting table creation time: {e}")
            return None
    
    def _check_date_range_coverage(self, table_id: str, start_date: str, end_date: str, verbose: bool = False) -> Optional[Dict[str, Any]]:
        try:
            query = f"""
            SELECT 
                MIN(DATE(usage_start_time)) as min_date,
                MAX(DATE(usage_start_time)) as max_date
            FROM `{table_id}`
            """
            
            if verbose:
                print(f"Debug: Checking date range coverage...")
            
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            for row in results:
                if row.min_date and row.max_date:
                    min_date_str = row.min_date.strftime('%Y-%m-%d')
                    max_date_str = row.max_date.strftime('%Y-%m-%d')
                    
                    if verbose:
                        print(f"Debug: Data available from {min_date_str} to {max_date_str}")
                    
                    requested_start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    requested_end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    outside_range = (requested_end < row.min_date or requested_start > row.max_date)
                    
                    return {
                        'has_data': True,
                        'min_date': min_date_str,
                        'max_date': max_date_str,
                        'outside_range': outside_range
                    }
            
            return {'has_data': False, 'min_date': None, 'max_date': None, 'outside_range': True}
        except Exception as e:
            if verbose:
                print(f"Debug: Error checking date range: {e}")
            return None

    def format_output(self, data: List[Dict[str, Any]], output_format: str):
        if not data:
            print("No data to display.")
            return
        
        if output_format == 'json':
            print(json.dumps(data, indent=2))
        elif output_format == 'csv':
            if data:
                writer = csv.DictWriter(sys.stdout, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        else:
            print(tabulate(data, headers='keys', tablefmt='grid'))


def main():
    parser = argparse.ArgumentParser(
        description='GCP Billing Viewer - View billing accounts, projects, and costs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list-accounts
  %(prog)s --list-projects --billing-account 01234-ABCDEF-56789
  %(prog)s --costs --billing-account 01234-ABCDEF-56789
  %(prog)s --costs --billing-account 01234-ABCDEF-56789 --start-date 2025-01-01 --group-by service
  %(prog)s --costs --billing-account 01234-ABCDEF-56789 --format csv > costs.csv
        """
    )
    
    parser.add_argument('--list-accounts', action='store_true',
                        help='List all billing accounts')
    parser.add_argument('--list-projects', action='store_true',
                        help='List projects and their billing status')
    parser.add_argument('--costs', action='store_true',
                        help='Retrieve actual billing costs (requires BigQuery export)')
    parser.add_argument('--billing-account', type=str,
                        help='Billing account ID to filter/query')
    parser.add_argument('--project', type=str,
                        help='Filter costs by specific project ID')
    parser.add_argument('--start-date', type=str,
                        help='Start date for cost analysis (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                        help='End date for cost analysis (YYYY-MM-DD)')
    parser.add_argument('--group-by', type=str, 
                        choices=['service', 'project', 'day', 'month'],
                        default='service',
                        help='Group costs by dimension (default: service)')
    parser.add_argument('--format', type=str,
                        choices=['table', 'csv', 'json'],
                        default='table',
                        help='Output format (default: table)')
    parser.add_argument('--debug', action='store_true',
                        help='Show debug information for troubleshooting')
    
    args = parser.parse_args()
    
    if not any([args.list_accounts, args.list_projects, args.costs]):
        parser.print_help()
        sys.exit(0)
    
    viewer = GCPBillingViewer()
    
    if args.list_accounts:
        print("\n=== Billing Accounts ===\n")
        accounts = viewer.list_billing_accounts(args.billing_account)
        viewer.format_output(accounts, args.format)
    
    if args.list_projects:
        print("\n=== Projects with Billing Status ===\n")
        projects = viewer.list_projects_with_billing(args.billing_account)
        viewer.format_output(projects, args.format)
    
    if args.costs:
        if not args.billing_account:
            print("Error: --billing-account is required for cost analysis")
            sys.exit(1)
        
        end_date = args.end_date or datetime.now().strftime('%Y-%m-%d')
        start_date = args.start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print("Error: Dates must be in YYYY-MM-DD format")
            sys.exit(1)
        
        print(f"\n=== Billing Costs ({start_date} to {end_date}) ===\n")
        costs = viewer.get_costs_from_bigquery(
            args.billing_account,
            start_date,
            end_date,
            args.project,
            args.group_by,
            verbose=args.debug
        )
        
        if costs:
            viewer.format_output(costs, args.format)
            
            if args.format == 'table':
                total = sum(c['cost'] for c in costs)
                currency = costs[0]['currency'] if costs else 'USD'
                print(f"\nTotal: {total:.2f} {currency}")
        else:
            if args.format == 'table':
                print("\nTotal: 0.00 USD")


if __name__ == '__main__':
    main()
