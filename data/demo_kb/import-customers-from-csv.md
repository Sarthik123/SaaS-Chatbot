# Import customers from a CSV file

## Before you start
Prepare a CSV file saved with UTF-8 encoding. The first row must be a header row with column names. To get a ready-made example, go to Customers > Import > Download sample file.

## Columns
Two columns are required: name and email. These columns are optional: company, phone, address, country, tax_id and currency. Extra columns are ignored.

## Limits
One file can have up to 5,000 rows and be up to 5 MB. If you have more customers than that, split them into several files and import them one after another.

## Run the import
1. Go to Customers > Import and choose your file.
2. Check that each column is matched to the right field.
3. Click Preview to see how the first rows will look.
4. Click Import.

## Duplicates
By default, a row whose email already exists in your account is skipped. If you would rather overwrite the existing customer, choose "Update existing customers" before you import.

## If rows fail
After the import you get a report. You can download the failed rows with the reason for each one, fix them and import again. Common error codes are explained in "Troubleshooting common problems".

## Web only
Importing is available on the website only, not in the mobile app.
