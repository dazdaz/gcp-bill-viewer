# GCP Billing Viewer

Python-based tool to view GCP billing accounts, projects, and actual costs via BigQuery billing export.

## Features

- List billing accounts with status and currency
- View projects and their billing status
- Retrieve actual billing costs from BigQuery (when export is configured)
- Support for date range filtering
- Multiple output formats: table, CSV, JSON
- Cross-platform date handling
- Automatic BigQuery export detection

## Prerequisites

- Python 3.7+
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer
- Google Cloud SDK (gcloud CLI)
- Authenticated GCP account
- For cost data: BigQuery billing export configured

## Installation

1. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:
```bash
uv pip install -r requirements.txt
```

Or install dependencies in a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

3. Authenticate with Google Cloud:
```bash
gcloud auth application-default login
```

**Important**: After authentication, you may need to set a quota project:
```bash
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Or authenticate with an existing project:
```bash
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
```

## Usage

### View Billing Accounts
```bash
uv run gcpbill.py --list-accounts
```

### View Projects with Billing Status
```bash
uv run gcpbill.py --list-projects

# Filter by billing account
uv run gcpbill.py --list-projects --billing-account 01234-ABCDEF-56789
```

### View Actual Billing Costs
Requires BigQuery billing export to be configured (see Setup below).

```bash
# Last 30 days (default)
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789

# Specific date range
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 \
  --start-date 2025-01-01 --end-date 2025-01-31

# Group by service (default)
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --group-by service

# Group by project
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --group-by project

# Group by day or month
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --group-by day
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --group-by month

# Filter by project
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --project my-project-id

# Export to CSV
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --format csv > costs.csv

# Export to JSON
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --format json > costs.json
```

## BigQuery Billing Export Setup

To retrieve actual cost data, you need to configure BigQuery billing export.

### Setup BigQuery Export

1. Create the BigQuery dataset:
```bash
uv run setup_bigquery_export.py --setup \
  --billing-account 01234-ABCDEF-56789 \
  --project my-billing-project
```

2. Follow the manual configuration instructions printed by the script to enable export in GCP Console.

### Custom Configuration
```bash
# Custom dataset name and location
uv run setup_bigquery_export.py --setup \
  --billing-account 01234-ABCDEF-56789 \
  --project my-billing-project \
  --dataset custom_billing \
  --location EU
```

### Destroy BigQuery Export

```bash
# Disable export but keep dataset
uv run setup_bigquery_export.py --destroy \
  --billing-account 01234-ABCDEF-56789 \
  --project my-billing-project

# Disable export and delete dataset
uv run setup_bigquery_export.py --destroy \
  --billing-account 01234-ABCDEF-56789 \
  --project my-billing-project \
  --delete-dataset
```

## Important Notes

- **Billing data delay**: Data appears in BigQuery ~24 hours after export is enabled
- **API limitations**: Cloud Billing API does not support programmatic export configuration (must use Console)
- **Permissions required**:
  - `billing.accounts.list` - List billing accounts
  - `billing.accounts.getSpendingInformation` - View billing data
  - `bigquery.datasets.create` - Create datasets
  - `bigquery.jobs.create` - Query BigQuery
- **Cross-platform**: Works on macOS, Linux, and Windows

## Troubleshooting

### No billing accounts found
- Verify you have billing account access
- Check you have `Billing Account Viewer` or `Billing Account Administrator` role

### BigQuery export not detected
- Ensure export is configured in GCP Console
- Verify the dataset and table exist
- Check you're using the correct billing account ID

### Authentication errors
- Run `gcloud auth application-default login`
- Verify credentials are valid: `gcloud auth list`
- If you see "Reauthentication is needed", your credentials have expired - re-run the login command
- Set a quota project if needed: `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`

### Python version warning
- The warning about Python 3.10 reaching end-of-life can be ignored (it's suppressed in the code)
- Consider upgrading to Python 3.11+ for continued support
