# The Polite Scraper

## Target Classification

This project targets Books to Scrape:

https://books.toscrape.com/

Books to Scrape is a public practice sandbox specifically created for learning and testing web scraping. The scraper processes only the first three catalogue pages, which contain 20 books each, for a total of 60 book pages.

The scraper collects only the information required by the assignment: book title, product URL, price text, availability text, rating text, description, source catalogue page, and fetch timestamp. These values are then normalized, validated, and stored as JSON.

The current robots.txt check returned 404, so no robots file was found. The missing file is not treated as permission to scrape other websites.

This limited scraping scope is appropriate because the target is explicitly provided as a scraping practice sandbox.

I will not reuse this code on another site without checking its rules and terms first.
