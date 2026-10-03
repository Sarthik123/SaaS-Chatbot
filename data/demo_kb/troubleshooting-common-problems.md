# Troubleshooting common problems

## My customer did not receive the invoice email
Ask your customer to check their spam or junk folder. Open the invoice and check that the email address is correct, then click Resend. If the problem continues, ask your customer to add our sending address to their allow list.

## The invoice PDF will not download
The error ERR-6001 means the PDF took too long to create. Wait a minute and try again. Invoices with many line items or large attachments take longer. If it keeps failing, contact support and include the invoice number.

## CSV import errors
- ERR-4102: the header row is missing or the column names are not recognised. The first row must contain the column names, and at least name and email.
- ERR-4108: the file is larger than 5 MB or has more than 5,000 rows. Split it into smaller files.
- ERR-4115: the file is not saved as UTF-8. Re-save it with UTF-8 encoding and try again.

## The accounting integration stopped syncing
The error ERR-5003 means the access token has expired. Go to Settings > Integrations and click Reconnect.

## The totals look wrong
Check whether the invoice is set to "Prices include tax" or "Prices exclude tax". Remember that tax is rounded for each line, not on the total.

## I cannot sign in
Use "Forgot password?" on the sign-in page. After 5 failed attempts the account is locked for 15 minutes.

## Still stuck?
Contact support. The article "Support hours and how to contact us" has the details.
