#!/usr/bin/env python3

import sys
import warnings

warnings.filterwarnings('ignore', category=FutureWarning, module='google.api_core._python_version_support')

from google.cloud import bigquery
from google.auth import default

try:
    credentials, project_id = default()
    print(f"Using project: {project_id}")
    print()
    
    client = bigquery.Client(credentials=credentials, project=project_id)
    
    print("Datasets in project:")
    datasets = list(client.list_datasets())
    
    if not datasets:
        print("  No datasets found")
    else:
        for dataset in datasets:
            print(f"  - {dataset.dataset_id}")
            
            tables = list(client.list_tables(dataset.dataset_id))
            if tables:
                print(f"    Tables:")
                for table in tables:
                    print(f"      - {table.table_id}")
                    table_ref = client.get_table(f"{project_id}.{dataset.dataset_id}.{table.table_id}")
                    created = table_ref.created.strftime('%Y-%m-%d %H:%M:%S %Z')
                    print(f"        Created: {created}")
                    print(f"        Rows: {table_ref.num_rows:,}")
            else:
                print(f"    No tables (empty dataset)")
                print()
                print("    ⚠ BILLING EXPORT NOT CONFIGURED YET!")
                print()
                print("    The dataset exists but billing export hasn't been enabled.")
                print("    You need to complete the manual configuration in GCP Console:")
                print()
                print("    1. Go to: https://console.cloud.google.com/billing")
                print("    2. Select your billing account: 01EF07-CA2EE0-1C8B2F")
                print("    3. Click 'Billing export' → 'BigQuery export'")
                print("    4. Under 'Detailed usage cost', click 'EDIT SETTINGS'")
                print("    5. Toggle Enable to ON")
                print(f"    6. Select Project: {project_id}")
                print(f"    7. Select Dataset: {dataset.dataset_id}")
                print("    8. Click 'SAVE'")
                print()
                print("    Or run the setup script again and complete the browser step:")
                print("    ./setup_bigquery_export.py --setup \\")
                print(f"      --billing-account 01EF07-CA2EE0-1C8B2F --project {project_id}")
            print()

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
