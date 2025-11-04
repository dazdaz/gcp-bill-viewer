#!/usr/bin/env python3

import sys
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

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
