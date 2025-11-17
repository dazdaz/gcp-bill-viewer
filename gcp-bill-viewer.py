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
            sys.exit(1)
        except Exception as e:
            print(f"Error during authentication: {e}")
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
        except Exception as e:
            print(f"Error listing billing accounts: {e}")
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
                    projects.append({
                        'project_id': project_billing_info.project_id,
                        'billing_account': project_billing_info.billing_account_name.split('/')[-1] if project_billing_info.billing_account_name else 'None',
                        'billing_enabled': project_billing_info.billing_enabled
                    })
            else:
                accounts = self.list_billing_accounts()
                for account in accounts:
                    request = billing_v1.ListProjectBillingInfoRequest(name=account['name'])
                    page_result = self.billing_client.list_project_billing_info(request=request)
                    for project_billing_info in page_result:
                        projects.append({
                            'project_id': project_billing_info.project_id,
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
            for dataset in datasets:
                if dataset.dataset_id in common_datasets:
                    tables = list(self.bq_client.list_tables(dataset.dataset_id))
                    for table in tables:
                        for pattern in common_patterns:
                            if pattern in table.table_id:
                                return f'{self.project_id}.{dataset.dataset_id}.{table.table_id}'
            
            # Fallback deep search
            for dataset in datasets:
                tables = list(self.bq_client.list_tables(dataset.dataset_id))
                for table in tables:
                    for pattern in common_patterns:
                        if pattern in table.table_id:
                            return f'{self.project_id}.{dataset.dataset_id}.{table.table_id}'
        except Exception as e:
            if verbose: print(f"Debug: Error during detection: {e}")
            pass
        return None

    def _get_category_sql(self, group_by: str) -> str:
        """Generate SQL for smart categorization without joining UNNEST(labels)"""
        
        # Logic to extract Model ID from System Labels (Standard for Vertex AI)
        system_label_model_extraction = """
            (SELECT value FROM UNNEST(system_labels) WHERE key = 'goog-vertex-ai-model-id' LIMIT 1)
        """

        # Logic to extract Model Name from SKU Description (Fallback if system label missing)
        sku_model_extraction = """
            CASE
                WHEN LOWER(sku.description) LIKE '%gemini 1.5 pro%' THEN 'Gemini 1.5 Pro'
                WHEN LOWER(sku.description) LIKE '%gemini 1.5 flash%' THEN 'Gemini 1.5 Flash'
                WHEN LOWER(sku.description) LIKE '%gemini pro%' THEN 'Gemini Pro'
                WHEN LOWER(sku.description) LIKE '%gemini flash%' THEN 'Gemini Flash'
                WHEN LOWER(sku.description) LIKE '%gemini ultra%' THEN 'Gemini Ultra'
                WHEN LOWER(sku.description) LIKE '%claude 3.5 sonnet%' THEN 'Claude 3.5 Sonnet'
                WHEN LOWER(sku.description) LIKE '%claude 3.5 haiku%' THEN 'Claude 3.5 Haiku'
                WHEN LOWER(sku.description) LIKE '%claude 3 opus%' THEN 'Claude 3 Opus'
                WHEN LOWER(sku.description) LIKE '%claude 3 sonnet%' THEN 'Claude 3 Sonnet'
                WHEN LOWER(sku.description) LIKE '%claude 3 haiku%' THEN 'Claude 3 Haiku'
                WHEN LOWER(sku.description) LIKE '%llama%' THEN 'Llama'
                ELSE NULL
            END
        """

        if group_by == 'model':
            return f"""
            COALESCE(
                -- 1. Try System Label (Most Accurate for Vertex)
                {system_label_model_extraction},
                
                -- 2. Try SKU Description Parsing
                {sku_model_extraction},
                
                -- 3. Fallback: If it's Vertex AI but unknown model, show SKU
                CASE 
                    WHEN LOWER(service.description) LIKE '%vertex ai%' THEN CONCAT('Vertex AI - ', sku.description)
                    -- 4. General Fallback for non-AI services
                    ELSE service.description
                END
            )
            """
        elif group_by == 'ai':
            return f"""
            CASE 
                WHEN {system_label_model_extraction} IS NOT NULL OR {sku_model_extraction} IS NOT NULL OR LOWER(service.description) LIKE '%vertex ai%' THEN 'AI/ML Services'
                ELSE 'Infrastructure & Other'
            END
            """
        elif group_by == 'project':
            return "project.name"
        else:
            return "service.description"

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
            return []
        
        print(f"Using BigQuery table: {table_id}")
        
        # Dynamic SQL Generation
        category_expr = self._get_category_sql(group_by)
        
        query = f"""
        SELECT
            {category_expr} as category,
            ROUND(SUM(cost), 2) as total_cost,
            currency
        FROM `{table_id}`
        WHERE usage_start_time >= TIMESTAMP('{start_date}')
            AND usage_start_time < TIMESTAMP('{end_date}')
        """
        
        if project_filter:
            query += f" AND project.id = '{project_filter}'"
            
        query += """
        GROUP BY category, currency
        ORDER BY total_cost DESC
        """
        
        if verbose:
            print("\nGenerated Query:")
            print(query)

        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()
            
            costs = []
            for row in results:
                costs.append({
                    group_by: row.category or 'Unknown',
                    'cost': float(row.total_cost),
                    'currency': row.currency
                })
            return costs
        except Exception as e:
            print(f"Error querying BigQuery: {e}")
            return []

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
    parser = argparse.ArgumentParser(description='GCP Billing Viewer')
    parser.add_argument('--list-accounts', action='store_true', help='List billing accounts')
    parser.add_argument('--list-projects', action='store_true', help='List projects')
    parser.add_argument('--costs', action='store_true', help='Get costs')
    parser.add_argument('--billing-account', type=str, help='Billing Account ID')
    parser.add_argument('--project', type=str, help='Project ID filter')
    parser.add_argument('--start-date', type=str, help='YYYY-MM-DD')
    parser.add_argument('--end-date', type=str, help='YYYY-MM-DD')
    parser.add_argument('--group-by', type=str, choices=['service', 'project', 'ai', 'model'], default='service')
    parser.add_argument('--format', type=str, choices=['table', 'csv', 'json'], default='table')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    if not any([args.list_accounts, args.list_projects, args.costs]):
        parser.print_help()
        sys.exit(0)
    
    viewer = GCPBillingViewer()
    
    if args.list_accounts:
        print("\n=== Billing Accounts ===\n")
        viewer.format_output(viewer.list_billing_accounts(args.billing_account), args.format)
    
    if args.list_projects:
        print("\n=== Projects ===\n")
        viewer.format_output(viewer.list_projects_with_billing(args.billing_account), args.format)
    
    if args.costs:
        if not args.billing_account:
            print("Error: --billing-account required")
            sys.exit(1)
        
        end = args.end_date or datetime.now().strftime('%Y-%m-%d')
        start = args.start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        costs = viewer.get_costs_from_bigquery(args.billing_account, start, end, args.project, args.group_by, args.debug)
        viewer.format_output(costs, args.format)
        
        if costs and args.format == 'table':
            total = sum(c['cost'] for c in costs)
            print(f"\nTotal: {total:.2f} {costs[0]['currency']}")

if __name__ == '__main__':
    main()
