# CEEKAY Finance Manager

A Streamlit personal-finance application using Google Sheets as its database.

## Main features

- Secure admin login
- Asset management
- Income tracking
- Salary and income allocation
- Expense tracking
- Liability management
- Principal and interest payment tracking
- Current outstanding liability calculation
- Monthly budgets
- Savings goals
- Dashboard and charts
- CSV report downloads
- Google Sheets worksheet creation on first run

## GitHub files

Upload these files to a new GitHub repository:

- `app.py`
- `requirements.txt`
- `.gitignore`

Do not upload your real Google JSON key or `secrets.toml`.

## Google setup

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable Google Sheets API and Google Drive API.
4. Create a service account.
5. Create a new JSON key for the service account.
6. Create a Google Sheet named `CEEKAY_Personal_Finance`.
7. Share the Google Sheet with the `client_email` inside the JSON key and give Editor access.
8. Copy the JSON values into Streamlit Secrets using `secrets_example.toml` as the format.

The application automatically creates these worksheets:

- Assets
- Income
- SalaryAllocation
- Expenses
- Liabilities
- LiabilityPayments
- Budgets
- SavingsGoals
- Categories
- Settings

## Streamlit deployment

1. Create a new public or private GitHub repository.
2. Upload `app.py`, `requirements.txt`, and `.gitignore`.
3. Open Streamlit Community Cloud.
4. Create a new app from the GitHub repository.
5. Set the main file as `app.py`.
6. Open App Settings → Secrets.
7. Paste the completed secret values.
8. Save and restart the application.

## Local testing

Create `.streamlit/secrets.toml` using the example file, then run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important

Do not rename the Google Sheet worksheet tabs after the app starts using them.
