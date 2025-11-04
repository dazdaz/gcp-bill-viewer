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
- Intelligent diagnostics:
  - Detects if billing export table exists
  - Checks when table was created and calculates wait time
  - Validates date range against available data
  - Distinguishes between $0 bills and missing data
  - Debug mode for troubleshooting

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

# Debug mode (troubleshooting)
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --debug
```

### Debug Mode

Use `--debug` flag to see detailed diagnostic information:

```bash
uv run gcpbill.py --costs --billing-account 01234-ABCDEF-56789 --debug
```

Debug output includes:
- All datasets and tables found in your project
- Table creation timestamp and elapsed time
- Date range coverage of available billing data
- Detailed error messages

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
  - The script automatically checks when the export table was created
  - Shows exact time elapsed and estimated wait time remaining
- **One-time setup**: Run `setup_bigquery_export.py` once, then billing data updates automatically daily
- **API limitations**: Cloud Billing API does not support programmatic export configuration (must use Console)
- **Permissions required**:
  - `billing.accounts.list` - List billing accounts
  - `billing.accounts.getSpendingInformation` - View billing data
  - `bigquery.datasets.create` - Create datasets
  - `bigquery.jobs.create` - Query BigQuery
  - `bigquery.tables.get` - Get table metadata
- **Cross-platform**: Works on macOS, Linux, and Windows
- **$0 bills**: The script correctly reports $0.00 when you have no usage costs

## How It Works

1. **Setup** (one-time):
   - Run `setup_bigquery_export.py --setup` to create BigQuery dataset
   - Complete manual configuration in GCP Console (GCP API limitation)
   - Wait ~24 hours for first data export

2. **Daily Updates** (automatic):
   - GCP exports billing data to BigQuery daily
   - No manual action required
   - Data accumulates over time

3. **View Costs** (anytime):
   - Run `gcpbill.py --costs` to query costs
   - Specify date ranges, grouping, filters
   - Export to CSV/JSON for analysis

## Troubleshooting

### No billing accounts found
- Verify you have billing account access
- Check you have `Billing Account Viewer` or `Billing Account Administrator` role

### BigQuery export not detected
- Run with `--debug` flag to see what datasets/tables were found
- Ensure export is configured in GCP Console (not just dataset created)
- Verify the dataset and table exist in BigQuery
- Check you're using the correct billing account ID

### Table exists but no data
The script will automatically detect this and show:
- When the table was created
- Time elapsed since creation
- Estimated wait time (if < 24 hours)
- Troubleshooting steps (if > 24 hours)

**If < 24 hours**: Wait for GCP to export data  
**If > 24 hours**: Verify export is enabled in GCP Console

### Date range outside available data
The script detects this automatically and shows:
- Your requested date range
- Available data range in BigQuery
- Clear message that dates don't overlap

### Authentication errors
- Run `gcloud auth application-default login`
- Verify credentials are valid: `gcloud auth list`
- If you see "Reauthentication is needed", your credentials have expired - re-run the login command
- Set a quota project if needed: `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`

### Python version warning
- The warning about Python 3.10 reaching end-of-life is suppressed automatically
- Consider upgrading to Python 3.11+ for continued support

### General troubleshooting
Always run with `--debug` flag first:
```bash
uv run gcpbill.py --costs --billing-account YOUR_ACCOUNT_ID --debug
```

This shows detailed diagnostics about:
- Table detection process
- Table creation time
- Data availability
- Date range coverage
