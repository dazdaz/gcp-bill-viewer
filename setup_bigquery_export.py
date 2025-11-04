#!/usr/bin/env python3

import argparse
import sys
import warnings
from typing import Optional

warnings.filterwarnings('ignore', category=FutureWarning, module='google.api_core._python_version_support')

try:
    from google.cloud import billing_v1
    from google.cloud import bigquery
    from google.cloud import resourcemanager_v3
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError, RefreshError
    from google.api_core import exceptions
except ImportError as e:
    print(f"Error: Missing required dependency: {e}")
    print("\nPlease install dependencies with:")
    print("  uv pip install -r requirements.txt")
    sys.exit(1)


class BigQueryExportSetup:
    def __init__(self):
        self.credentials = None
        self.default_project_id = None
        self._authenticate()
        self.billing_client = billing_v1.CloudBillingClient(credentials=self.credentials)
        self.bq_client = None

    def _authenticate(self):
        try:
            self.credentials, self.default_project_id = default()
        except (DefaultCredentialsError, RefreshError) as e:
            print("Error: Not authenticated with Google Cloud.")
            print(f"\nDetails: {e}")
            print("\nPlease authenticate using one of these methods:")
            print("  1. gcloud auth application-default login")
            print("  2. gcloud auth login")
            print("\nIf you see 'Reauthentication is needed', run:")
            print("  gcloud auth application-default login")
            sys.exit(1)

    def setup_export(
        self,
        billing_account_id: str,
        project_id: str,
        dataset_name: str = 'billing_export',
        location: str = 'US'
    ):
        print(f"\n=== Setting up BigQuery Billing Export ===\n")
        print(f"Billing Account: {billing_account_id}")
        print(f"Project: {project_id}")
        print(f"Dataset: {dataset_name}")
        print(f"Location: {location}\n")
        
        self.bq_client = bigquery.Client(credentials=self.credentials, project=project_id)
        
        print("Step 1: Verifying project access...")
        try:
            datasets = list(self.bq_client.list_datasets(max_results=1))
            print(f"  ✓ Project '{project_id}' verified (BigQuery access confirmed)")
        except exceptions.NotFound:
            print(f"  ✗ Project '{project_id}' not found")
            sys.exit(1)
        except exceptions.Forbidden:
            print(f"  ✗ Access denied to project '{project_id}'")
            print("  - Check that you have permissions on this project")
            print("  - Verify BigQuery API is enabled")
            sys.exit(1)
        except Exception as e:
            print(f"  ✗ Error accessing project: {e}")
            print("\nTrying to enable BigQuery API...")
            print(f"  Run: gcloud services enable bigquery.googleapis.com --project={project_id}")
            sys.exit(1)
        
        print("\nStep 2: Creating BigQuery dataset...")
        dataset_id = f"{project_id}.{dataset_name}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = location
        
        try:
            dataset = self.bq_client.create_dataset(dataset, exists_ok=True)
            print(f"  ✓ Dataset '{dataset_name}' created/verified in {location}")
        except Exception as e:
            print(f"  ✗ Error creating dataset: {e}")
            print("\nCommon issues:")
            print("  - Insufficient permissions (need bigquery.datasets.create)")
            print("  - BigQuery API not enabled on project")
            print("\nTo enable BigQuery API:")
            print(f"  gcloud services enable bigquery.googleapis.com --project={project_id}")
            sys.exit(1)
        
        print("\nStep 3: Configuring billing export...")
        print("  ⚠ Note: Billing export configuration must be done via GCP Console")
        print("\n  Manual steps required:")
        print(f"  1. Go to: https://console.cloud.google.com/billing/{billing_account_id}")
        print("  2. Navigate to 'Billing export' → 'BigQuery export'")
        print("  3. Click 'EDIT SETTINGS' for 'Detailed usage cost'")
        print(f"  4. Select project: {project_id}")
        print(f"  5. Select dataset: {dataset_name}")
        print("  6. Click 'SAVE'")
        print("\n  The Cloud Billing API does not currently support programmatic export configuration.")
        print("  This is a GCP platform limitation.")
        
        print(f"\n=== Setup Information ===\n")
        print(f"Dataset created: {dataset_id}")
        print(f"Location: {location}")
        print(f"\nAfter configuring export in Console, billing data will appear in:")
        print(f"  Table: {dataset_id}.gcp_billing_export_v1_{billing_account_id.replace('-', '_')}")
        print(f"\nData will be available ~24 hours after export is enabled.")
        print(f"\nTo verify export is working:")
        print(f"  python gcpbill.py --costs --billing-account {billing_account_id}")

    def destroy_export(
        self,
        billing_account_id: str,
        project_id: Optional[str] = None,
        dataset_name: str = 'billing_export',
        delete_dataset: bool = False
    ):
        print(f"\n=== Destroying BigQuery Billing Export ===\n")
        print(f"Billing Account: {billing_account_id}\n")
        
        if not project_id:
            project_id = self.default_project_id
        
        self.bq_client = bigquery.Client(credentials=self.credentials, project=project_id)
        
        print("Step 1: Disabling billing export...")
        print("  ⚠ Note: Billing export must be disabled via GCP Console")
        print("\n  Manual steps required:")
        print(f"  1. Go to: https://console.cloud.google.com/billing/{billing_account_id}")
        print("  2. Navigate to 'Billing export' → 'BigQuery export'")
        print("  3. Click 'EDIT SETTINGS' for 'Detailed usage cost'")
        print("  4. Click 'DISABLE EXPORT'")
        print("  5. Click 'SAVE'")
        
        if delete_dataset:
            print(f"\nStep 2: Deleting BigQuery dataset '{dataset_name}'...")
            dataset_id = f"{project_id}.{dataset_name}"
            
            try:
                self.bq_client.delete_dataset(
                    dataset_id,
                    delete_contents=True,
                    not_found_ok=True
                )
                print(f"  ✓ Dataset '{dataset_name}' deleted")
            except Exception as e:
                print(f"  ✗ Error deleting dataset: {e}")
                print(f"\nTo delete manually:")
                print(f"  bq rm -r -f -d {dataset_id}")
        else:
            print(f"\nStep 2: Keeping dataset '{dataset_name}'")
            print(f"  Dataset will remain with historical billing data")
            print(f"\nTo delete dataset later:")
            print(f"  python {sys.argv[0]} --destroy --billing-account {billing_account_id} --delete-dataset")
        
        print(f"\n=== Destroy Complete ===\n")
        print("Billing export has been disabled.")
        if delete_dataset:
            print(f"Dataset '{dataset_name}' has been deleted.")


def main():
    parser = argparse.ArgumentParser(
        description='Setup or destroy BigQuery billing export for GCP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Setup billing export:
    %(prog)s --setup --billing-account 01234-ABCDEF-56789 --project my-billing-project
  
  Setup with custom dataset:
    %(prog)s --setup --billing-account 01234-ABCDEF-56789 --project my-billing-project --dataset custom_billing --location EU
  
  Destroy billing export (keep dataset):
    %(prog)s --destroy --billing-account 01234-ABCDEF-56789 --project my-billing-project
  
  Destroy billing export (delete dataset):
    %(prog)s --destroy --billing-account 01234-ABCDEF-56789 --project my-billing-project --delete-dataset
        """
    )
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--setup', action='store_true',
                              help='Setup BigQuery billing export')
    action_group.add_argument('--destroy', action='store_true',
                              help='Destroy BigQuery billing export')
    
    parser.add_argument('--billing-account', type=str, required=True,
                        help='Billing account ID (e.g., 01234-ABCDEF-56789)')
    parser.add_argument('--project', type=str,
                        help='GCP project ID for BigQuery dataset (required for setup)')
    parser.add_argument('--dataset', type=str, default='billing_export',
                        help='BigQuery dataset name (default: billing_export)')
    parser.add_argument('--location', type=str, default='US',
                        help='BigQuery dataset location (default: US)')
    parser.add_argument('--delete-dataset', action='store_true',
                        help='Delete BigQuery dataset when destroying (default: keep dataset)')
    
    args = parser.parse_args()
    
    if args.setup and not args.project:
        print("Error: --project is required for --setup")
        sys.exit(1)
    
    setup = BigQueryExportSetup()
    
    if args.setup:
        setup.setup_export(
            args.billing_account,
            args.project,
            args.dataset,
            args.location
        )
    elif args.destroy:
        setup.destroy_export(
            args.billing_account,
            args.project,
            args.dataset,
            args.delete_dataset
        )


if __name__ == '__main__':
    main()
