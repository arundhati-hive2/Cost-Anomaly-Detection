# Invoice Anomaly Checker

A Streamlit tool that catches freight overbilling. It reads carrier invoices from Excel, works out what each shipment should have cost under your rate card, and flags every row where the bill does not match.

> All carriers, rates, fees, zones and hub codes in this repository are invented for demonstration. They do not describe any real company or contract.

## The problem

Logistics teams receive monthly invoices from several carriers, and each carrier prices differently. Some charge per kilogram, some by distance band, some by destination zone, and some by a table that combines origin and destination. Every carrier also names its columns differently. Checking thousands of rows by hand is slow, and small overcharges hide easily inside large invoices.

## What it does

1. **Maps messy headers** onto standard names, so "Waybill No", "AWB No" and "Docket No" all mean the same thing.
2. **Prices each shipment** with a rule matched to the carrier.
3. **Compares expected with billed** and labels each row Overcharged, Undercharged or OK, using a tolerance you set.
4. **Never guesses.** A row with an unknown state, a missing weight or an unrecognised hub goes to a review list with the reason, instead of being priced wrongly.
5. **Tracks freight as a share of invoice value**, with an optional target.
6. **Exports everything** to Excel: a summary, one sheet per carrier, and the review rows.

## Rule types

| Rule | How the freight is priced | Demo carrier |
| --- | --- | --- |
| Per kilogram | One flat rate times billable weight | Courier A |
| Distance slab | Rate depends on the distance band | Courier B |
| State zone | Destination state maps to a zone, each zone has a rate | Courier C |
| Zone matrix | Origin hub and destination state combine into a rate grade | Courier D |

Every rule supports a minimum billable weight and a minimum freight charge. On top of the rule, each carrier can add a fixed fee per shipment, a fuel surcharge percentage and remote area charges from the invoice.

## Run it

```bash
pip install -r requirements.txt
python sample_data/make_sample_data.py
streamlit run app.py
```

Tick "Use the built in sample workbook" to see it work straight away. The sample has deliberate overcharges, undercharges and unpriceable rows for the app to find.

Run the tests with:

```bash
pytest
```

## Use it on real invoices

1. Copy `checker/config.py` and put your own carriers and rate cards in it.
2. Name each Excel sheet exactly like the carrier key in the config.
3. Add any new header spellings to `COLUMN_ALIASES`.
4. **Keep your real config and invoices out of version control.** The `.gitignore` already blocks workbooks outside `sample_data`, but a rate card committed inside a Python file is just as sensitive as a spreadsheet.

## Project layout

```
app.py                    Streamlit interface
checker/rules.py          The four pricing rules
checker/engine.py         Header mapping, checking, summary
checker/config.py         Demo carriers and column aliases
sample_data/              Synthetic invoices and the script that makes them
tests/                    Unit tests for each rule and edge case
```

## Design notes

- Rules are small classes that return a rate and an expected freight. Adding a new carrier style means adding one class, not editing the engine.
- Headers are matched after stripping case, spaces and symbols, so "ODA Charges", "oda_charges" and " ODA " all match.
- The tolerance is a percentage so one setting works for small and large shipments alike.

## Ideas for next steps

- Load rate cards from a spreadsheet instead of Python code
- Month on month trend of overcharges per carrier
- A dispute letter generator for flagged rows
