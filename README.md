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
- **AI Usage Tracking**: Detailed breakdown of Vertex AI services, Chirp2, Chirp3, and computer use models
- Intelligent diagnostics:
  - Detects if billing export table exists
  - Checks when table was created and calculates wait time
  - Validates date range against available data
  - Distinguishes between $0 bills and missing data
  - Debug mode for troubleshooting

## Example
```text
+----------------+--------+------------+
| service        |   cost | currency   |
+================+========+============+
| Compute Engine |   5.92 | USD        |
+----------------+--------+------------+
| Cloud Storage  |   3.01 | USD        |
+----------------+--------+------------+
| Networking     |   0.4  | USD        |
+----------------+--------+------------+
| Gemini API     |   0.09 | USD        |
+----------------+--------+------------+
| BigQuery       |   0    | USD        |
+----------------+--------+------------+
| Cloud Logging  |   0    | USD        |
+----------------+--------+------------+

Total: 9.42 USD
```

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

1. ./setup_bigquery_export.py --billing-account $BILLING_ID --project $PROJECT_ID --setup
2. ./check_bigquery.py
3. ./gcp-bill-viewer.py --costs --billing-account $BILLING_ID

## BigQuery Billing Export Setup

To retrieve actual cost data, you need to configure BigQuery billing export.

**Important**: Google Cloud Platform does not provide an API to programmatically enable billing export. A brief manual step in the GCP Console is required (the script will guide you through it).

### Setup BigQuery Export

Run the setup script for each project which you want to export billing data - it will create the dataset and open your browser to the configuration page:

```bash
uv run setup_bigquery_export.py --setup \
  --billing-account 01234-ABCDEF-56789 \
  --project my-billing-project
```

The script will:
1. Create the BigQuery dataset
2. **Automatically open your browser** to the billing export configuration page
3. Show you step-by-step instructions
4. Wait for you to complete the configuration
5. Verify the export table was created

**What you need to do in the browser:**
- Click the "BIGQUERY EXPORT" tab
- Under "Detailed usage cost", click "EDIT SETTINGS"  
- Enable the export and select your project/dataset
- Click "SAVE"
- Return to terminal and press ENTER

That's it! The script handles everything else.

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
   - Run `gcp-bill-viewer.py --costs` to query costs
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

### View Billing Accounts
```bash
uv run gcp-bill-viewer.py --list-accounts
```

### View Projects with Billing Status
```bash
uv run gcp-bill-viewer.py --list-projects

# Filter by billing account
uv run gcp-bill-viewer.py --list-projects --billing-account 01234-ABCDEF-56789
```

### View Actual Billing Costs
Requires BigQuery billing export to be configured (see Setup below).

```bash
# Last 30 days (default)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789

# Specific date range
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 \
  --start-date 2025-01-01 --end-date 2025-01-31

# Group by service (default)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by service

# Group by project
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by project

# Group by day or month
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by day
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by month

# Group by AI services (new feature)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai

# Export AI usage to CSV
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai --format csv > ai_usage.csv

# Debug AI categorization
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai --debug

# Filter by project
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --project my-project-id

# Export to CSV
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --format csv > costs.csv

# Export to JSON
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --format json > costs.json

# Debug mode (troubleshooting)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --debug
```

## AI Usage Tracking

The enhanced billing viewer includes specialized AI usage tracking that provides deep insights into your AI spending patterns with two levels of granularity:

### AI Service Categories (`--group-by ai`)

When using `--group-by ai`, costs are categorized into:

- **Gemini 1.5 Pro/Provisional**: Gemini Pro models, gemini-1.5-pro
- **Gemini 1.5 Flash**: Gemini Flash models, gemini-1.5-flash
- **Gemini 1.5 Pro Vision**: Gemini Pro Vision models, gemini1provisional-vision
- **Gemini Ultra**: Gemini Ultra models, gemini-ultra
- **Gemini Code**: Gemini Code models, gemini-code
- **Gemini (Other Models)**: General Gemini models without specific version
- **Vertex AI - Cirp2**: Specific Cirp2 model usage tracking
- **Vertex AI - Chirp3**: Specific Chirp3 model usage tracking
- **Vertex AI - Computer Use**: Computer use model services
- **Vertex AI - Other Models**: General Vertex AI services and models
- **AI Platform (Legacy)**: Legacy AI Platform services
- **AutoML**: Automated machine learning services
- **Machine Learning**: General ML services and platforms
- **Natural Language API**: Text analysis and sentiment analysis
- **Speech Services**: Speech-to-text and text-to-speech
- **Vision API**: Image and video analysis services
- **Translation API**: Language translation services
- **Non-AI Services**: All non-AI services for comparison

### Model-Level Breakdown (`--group-by model`)

When using `--group-by model`, you'll get maximum granularity showing:
- **Service - Model combinations**: Vertex AI - gemini-1.5-pro, Vertex AI - cirp2, etc.
- **Unknown Model tracking**: For services without specific model identification
- **Full model visibility**: See exactly which models were used and their individual costs

### AI Usage Examples

```bash
# View detailed AI usage breakdown by service type
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai

# View maximum model-level granularity (shows exact models used)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by model

# Export AI usage data to CSV for analysis
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai --format csv > ai_usage.csv

# Export specific Gemini model usage
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by model --format csv > gemini_models.csv

# Filter AI usage by date range
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai --start-date 2025-01-01 --end-date 2025-01-31

# Debug AI categorization (shows detailed diagnostic info)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai --debug

# Debug model-level analysis (shows specific model detection)
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by model --debug

# Filter AI usage by specific project
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by ai --project my-ai-project

# Compare costs between different Gemini models
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --group-by model --format csv > model_comparison.csv
```

### Expected Output Examples

**AI Service Grouping (`--group-by ai`):**
```
+----------------------+--------+------------+
| ai                   |   cost | currency   |
+======================+========+============+
| Gemini 1.5 Pro       |  12.45 | USD        |
+----------------------+--------+------------+
| Vertex AI - Cirp2    |   8.32 | USD        |
+----------------------+--------+------------+
| Gemini 1.5 Flash     |   4.67 | USD        |
+----------------------+--------+------------+
| Vision API           |   2.10 | USD        |
+----------------------+--------+------------+
| Machine Learning     |   1.50 | USD        |
+----------------------+--------+------------+
| Non-AI Services      | 156.90 | USD        |
+----------------------+--------+------------+
```

**Model-Level Grouping (`--group-by model`):**
```
+--------------------------------+--------+------------+
| model                          |   cost | currency   |
+================================+========+============+
| Vertex AI - gemini-1.5-pro     |  12.45 | USD        |
+--------------------------------+--------+------------+
| Vertex AI - cirp2              |   8.32 | USD        |
+--------------------------------+--------+------------+
| Vertex AI - gemini-1.5-flash   |   4.67 | USD        |
+--------------------------------+--------+------------+
| Vision API - Unknown Model     |   2.10 | USD        |
+--------------------------------+--------+------------+
| Compute Engine - Unknown Model | 156.90 | USD        |
+--------------------------------+--------+------------+
```

### AI Tracking Benefits

- **Model-Specific Cost Analysis**: Track spending on exact Gemini models (1.5 Pro, 1.5 Flash, Ultra, etc.)
- **Cost Optimization**: Identify which AI models drive the most costs
- **Usage Patterns**: Compare costs between different AI model categories
- **Budget Management**: Set AI-specific budgets based on detailed breakdowns
- **Performance vs Cost Analysis**: Balance model performance with cost efficiency
- **Compliance**: Monitor AI usage for governance and compliance requirements
- **Future Planning**: Plan for model upgrades or migrations based on cost patterns

## Debug Mode

Use `--debug` flag to see detailed diagnostic information:

```bash
uv run gcp-bill-viewer.py --costs --billing-account 01234-ABCDEF-56789 --debug
```

Debug output includes:
- All datasets and tables found in your project
- Table creation timestamp and elapsed time
- Date range coverage of available billing data
- Detailed error messages

## Authentication errors
- Run `gcloud auth application-default login`
- Verify credentials are valid: `gcloud auth list`
- If you see "Reauthentication is needed", your credentials have expired - re-run the login command
- Set a quota project if needed: `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`

## Python version warning
- The warning about Python 3.10 reaching end-of-life is suppressed automatically
- Consider upgrading to Python 3.11+ for continued support

## General troubleshooting
Always run with `--debug` flag first:
```bash
uv run gcp-bill-viewer.py --costs --billing-account YOUR_ACCOUNT_ID --debug
```

This shows detailed diagnostics about:
- Table detection process
- Table creation time
- Data availability
- Date range coverage
