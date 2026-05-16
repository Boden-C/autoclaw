---
title: Foreign Accounts
row_advance: PgDn
columns: ["TSJ", "Account is For", "Financial institution", "Account number", "Max account value", "Unknown max account value (bool)", "Street address", "City", "Province/state", "IRS Country code", "Postal code", "Do not update address (bool)", "Part II - Separately Owned (bool)", "Part III - Jointly Owned (bool)", "Part IV - No Financial Interest (bool)", "Type of Account - Bank (bool)", "Type of Account - Securities (bool)", "Type of Account - Other (text)", "Principal Joint Owner - TIN Unknown (bool)", "Principal Joint Owner - TIN U.S. (text)", "Principal Joint Owner - TIN Foreign (text)", "Principal Joint Owner - First Name (text)", "Principal Joint Owner - MI (text)", "Principal Joint Owner - Last Name (text)", "Principal Joint Owner - Entity Name (text)", "Principal Joint Owner - Street Address (text)", "Principal Joint Owner - U.S. ZIP Code (text)", "Principal Joint Owner - Foreign Province/State (text)", "Principal Joint Owner - Foreign Country (text)", "Principal Joint Owner - Foreign Postal Code (text)", "Number of Joint Owners Excluding Filer (number)", "Filer Job Title Giving Authority (text)", "Form 8938 - Deposit (bool)", "Form 8938 - Custodial (bool)", "Form 8938 - Account Opened During Tax Year (bool)", "Form 8938 - Account Closed During Tax Year (bool)", "Form 8938 - Account Jointly Owned With Spouse (bool)", "Form 8938 - No Tax Item Reported in Part III With Respect to This Asset (bool)", "Financial Institution GIIN - 1 (text)", "Financial Institution GIIN - 2 (text)", "Financial Institution GIIN (LE/SL/ME/BR/SP)", "Financial Institution GIIN - 3 (text)", "Foreign Currency Maintained In (text)", "Foreign Currency Exchange Rate to U.S. Dollars (text)", "Source of Exchange Rate (text)"]
---
# Foreign Accounts

## Notes

- For any bool, assume "-" means FALSE and "=" means TRUE. However, only set bools for NEW accounts, if an account already exists, then leave it blank.

- This section overwrites previous Foreign Accounts entries unless an existing-screen image is provided.
- If an existing-account image is provided, keep the existing order exactly in the CSV
- Put new accounts after existing accounts; do not insert them before or between existing accounts.
- Do not add new accounts if their amount is 0, but do keep and follow the existing order if it is provided.

- If there is NOT enough information to determine:
  - Single or Married 
  - T (Taxpayer), S (Spouse), or J (Joint)
  - You MUST ask first and not continue.
- For `Account is For`:
  - `F114`: All aggregate accounts are <$50,000 for Single, <$10,000 for Married
  - `8938`: F114 is filed separately (RARELY used, warn if you think you should fill it out)
  - `BOTH`: All aggregate accounts are $50,000+ for Single, $100,00 for Married
  - `NONE`: All aggregate accounts are less than $10,000 (RARELY used, warn if you think you should fill it out)
- Max account value will be in USD, if you need to exchange follow the instructions below
- For `Unknown max account value`, usually leave blank, otherwise set to TRUE
- If there is no City or Province/state, then just leave blank. Postal code is usually required, if not provided then search it up.
- Do not include punctuation any string fields.
- Attempt to summarize long addresses
- Any column afterwards that is NOT listed below is usually not important, warn if you think you should fill it out
- FinCEN Form 114 is usually Separately Owned, so set `Part II - Separately Owned (bool)` to TRUE
- Type of account is usually Bank, so set `Type of Account - Bank (bool)` to TRUE
- Form 8938 is usually Deposit, so set `Form 8938 - Deposit (bool)` to TRUE
- If the currency is USD then leave the exchange section blank, otherwise fetch this website for the exchange rates https://www.irs.gov/individuals/international-taxpayers/yearly-average-currency-exchange-rates
  - `Foreign currency` should be Country + Currency (like "Taiwan	Dollar" or "China Yuan")
  - `Exchange rate` use the rate from the website
  - `Source of exchange rate` should be "IRS"
