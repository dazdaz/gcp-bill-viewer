#!/usr/bin/env python3

import sys
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore', category=FutureWarning, module='google.api_core._python_version_support')

from google.cloud import bigquery
from google.cloud import billing_v1
from google.auth import default

def check_authentication():
    print("=" * 70)
    print("STEP 1: Authentication Check")
    print("=" * 70)
    try:
        credentials, project_id = default()
        print(f"✓ Authenticated successfully")
        print(f"  Default project: {project_id}")
        print(f"  Credential type: {type(credentials).__name__}")
        return credentials, project_id
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        print("\nRun: gcloud auth application-default login")
        sys.exit(1)

def check_billing_accounts(credentials):
    print("\n" + "=" * 70)
    print("STEP 2: Billing Accounts Check")
    print("=" * 70)
    try:
        billing_client = billing_v1.CloudBillingClient(credentials=credentials)
        request = billing_v1.ListBillingAccountsRequest()
        accounts = list(billing_client.list_billing_accounts(request=request))
        
        if not accounts:
            print("✗ No billing accounts found")
            print("  You need a billing account to use billing export")
            return None
        
        print(f"✓ Found {len(accounts)} billing account(s):")
        for i, account in enumerate(accounts, 1):
            account_id = account.name.split('/')[-1]
            status = "Open" if account.open else "Closed"
            print(f"  {i}. {account.display_name}")
            print(f"     ID: {account_id}")
            print(f"     Status: {status}")
            if hasattr(account, 'currency_code'):
                print(f"     Currency: {account.currency_code}")
        
        return accounts
    except Exception as e:
        print(f"✗ Failed to list billing accounts: {e}")
        print("  Check permissions: need 'billing.accounts.list'")
        return None

def check_bigquery_api(client, project_id):
    print("\n" + "=" * 70)
    print("STEP 3: BigQuery API Access Check")
    print("=" * 70)
    try:
        datasets = list(client.list_datasets(max_results=1))
        print(f"✓ BigQuery API is enabled and accessible")
        return True
    except Exception as e:
        print(f"✗ BigQuery API error: {e}")
        print(f"\nTo enable BigQuery API:")
        print(f"  gcloud services enable bigquery.googleapis.com --project={project_id}")
        return False

def check_datasets_and_tables(client, project_id, billing_accounts):
    print("\n" + "=" * 70)
    print("STEP 4: Datasets and Tables Check")
    print("=" * 70)
    
    datasets = list(client.list_datasets())
    
    if not datasets:
        print("✗ No datasets found in project")
        print(f"\nTo create a billing export dataset:")
        print(f"  ./setup_bigquery_export.py --setup --billing-account YOUR_BILLING_ID --project {project_id}")
        return None, None
    
    print(f"✓ Found {len(datasets)} dataset(s):")
    
    billing_export_found = False
    billing_tables = []
    
    for dataset in datasets:
        print(f"\n  Dataset: {dataset.dataset_id}")
        
        try:
            dataset_ref = client.get_dataset(dataset.dataset_id)
            print(f"    Location: {dataset_ref.location}")
            print(f"    Created: {dataset_ref.created.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except Exception as e:
            print(f"    Could not get dataset details: {e}")
        
        tables = list(client.list_tables(dataset.dataset_id))
        
        if not tables:
            print(f"    Tables: 0 (empty dataset)")
            
            if dataset.dataset_id in ['billing_export', 'billing_data', 'billing']:
                billing_export_found = False
                print(f"\n    ⚠ This looks like a billing dataset but has no tables!")
                print(f"    Billing export is NOT configured yet.")
        else:
            print(f"    Tables: {len(tables)}")
            for table in tables:
                print(f"      - {table.table_id}")
                
                try:
                    table_ref = client.get_table(f"{project_id}.{dataset.dataset_id}.{table.table_id}")
                    created = table_ref.created.strftime('%Y-%m-%d %H:%M:%S %Z')
                    hours_ago = (datetime.now(table_ref.created.tzinfo) - table_ref.created).total_seconds() / 3600
                    
                    print(f"        Created: {created} ({hours_ago:.1f} hours ago)")
                    print(f"        Rows: {table_ref.num_rows:,}")
                    print(f"        Size: {table_ref.num_bytes / 1024 / 1024:.2f} MB")
                    
                    if 'gcp_billing_export' in table.table_id:
                        billing_export_found = True
                        billing_tables.append({
                            'dataset': dataset.dataset_id,
                            'table': table.table_id,
                            'created': table_ref.created,
                            'rows': table_ref.num_rows,
                            'hours_ago': hours_ago
                        })
                        
                        # Check date range
                        try:
                            query = f"""
                            SELECT 
                                MIN(DATE(usage_start_time)) as min_date,
                                MAX(DATE(usage_start_time)) as max_date,
                                COUNT(*) as row_count
                            FROM `{project_id}.{dataset.dataset_id}.{table.table_id}`
                            """
                            result = client.query(query).result()
                            for row in result:
                                if row.min_date and row.max_date:
                                    print(f"        Data range: {row.min_date} to {row.max_date}")
                                    days_of_data = (row.max_date - row.min_date).days + 1
                                    print(f"        Coverage: {days_of_data} days")
                                else:
                                    print(f"        Data range: No data yet")
                        except Exception as e:
                            print(f"        Could not check data range: {e}")
                            
                except Exception as e:
                    print(f"        Error getting table details: {e}")
    
    return billing_export_found, billing_tables

def check_billing_export_configuration(billing_export_found, billing_tables, billing_accounts, project_id):
    print("\n" + "=" * 70)
    print("STEP 5: Billing Export Configuration Status")
    print("=" * 70)
    
    if billing_export_found:
        print(f"✓ Billing export table(s) found: {len(billing_tables)}")
        for bt in billing_tables:
            print(f"\n  Table: {bt['dataset']}.{bt['table']}")
            print(f"  Created: {bt['created'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"  Time elapsed: {bt['hours_ago']:.1f} hours ({bt['hours_ago']/24:.1f} days)")
            print(f"  Rows: {bt['rows']:,}")
            
            if bt['rows'] == 0:
                if bt['hours_ago'] < 24:
                    print(f"  Status: ⏳ Waiting for first data export")
                    print(f"  Expected in: ~{24 - bt['hours_ago']:.1f} hours")
                else:
                    print(f"  Status: ⚠ Table is empty after 24+ hours")
                    print(f"  Issue: Billing export may not be properly configured")
                    print(f"  Action: Verify export is enabled in GCP Console")
            else:
                print(f"  Status: ✓ Export is working correctly")
    else:
        print("✗ No billing export tables found")
        print("\nPossible reasons:")
        print("  1. Billing export not configured in GCP Console")
        print("  2. Dataset exists but export not enabled")
        print("  3. Wrong billing account ID")
        
        if billing_accounts:
            print("\nTo configure billing export:")
            print("  1. Choose a billing account from above")
            print("  2. Run:")
            for account in billing_accounts[:1]:  # Show first account as example
                account_id = account.name.split('/')[-1]
                print(f"     ./setup_bigquery_export.py --setup \\")
                print(f"       --billing-account {account_id} \\")
                print(f"       --project {project_id}")
                break

def provide_recommendations(billing_export_found, billing_tables, project_id):
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if not billing_export_found:
        print("\n❌ Billing export is NOT configured")
        print("\nNext steps:")
        print("  1. Run the setup script:")
        print(f"     ./setup_bigquery_export.py --setup \\")
        print(f"       --billing-account YOUR_BILLING_ID --project {project_id}")
        print("  2. Complete the manual configuration in GCP Console")
        print("  3. Run this check script again to verify")
    
    elif billing_tables:
        table_has_data = any(bt['rows'] > 0 for bt in billing_tables)
        
        if table_has_data:
            print("\n✅ Billing export is fully configured and working!")
            print("\nYou can now query costs with:")
            for bt in billing_tables:
                if bt['rows'] > 0:
                    billing_id = bt['table'].replace('gcp_billing_export_v1_', '').replace('_', '-')
                    # Try to format billing ID
                    if len(billing_id) >= 18:
                        formatted_id = f"{billing_id[:6]}-{billing_id[6:12]}-{billing_id[12:]}"
                    else:
                        formatted_id = billing_id
                    print(f"  ./gcp-bill-viewer.py --costs --billing-account {formatted_id}")
                    break
        else:
            youngest_table = min(billing_tables, key=lambda x: x['hours_ago'])
            
            if youngest_table['hours_ago'] < 24:
                print("\n⏳ Billing export is configured, waiting for data")
                print(f"\nEstimated wait time: ~{24 - youngest_table['hours_ago']:.1f} hours")
                print("\nData export typically takes up to 24 hours after configuration.")
            else:
                print("\n⚠ Billing export table exists but has no data after 24+ hours")
                print("\nTroubleshooting steps:")
                print("  1. Verify billing export is enabled in GCP Console:")
                print("     https://console.cloud.google.com/billing")
                print("  2. Check that you selected the correct project and dataset")
                print("  3. Verify your GCP account has incurred some costs")
                print("  4. Wait another 12-24 hours (sometimes takes longer)")

def main():
    print("\n" + "=" * 70)
    print("GCP BILLING EXPORT DIAGNOSTIC TOOL")
    print("=" * 70)
    print()
    
    credentials, project_id = check_authentication()
    
    billing_accounts = check_billing_accounts(credentials)
    
    client = bigquery.Client(credentials=credentials, project=project_id)
    
    if not check_bigquery_api(client, project_id):
        sys.exit(1)
    
    billing_export_found, billing_tables = check_datasets_and_tables(client, project_id, billing_accounts)
    
    check_billing_export_configuration(billing_export_found, billing_tables, billing_accounts, project_id)
    
    provide_recommendations(billing_export_found, billing_tables, project_id)
    
    print("\n" + "=" * 70)
    print()

if __name__ == '__main__':
    main()
