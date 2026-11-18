# risks_for_food_companies
What are food companies afraid of? A text-analysis study of risk disclosures (Item 1A, Form 10-K) of 8 U.S. food &amp; beverage companies, FY2021–FY2025, using SEC EDGAR data and a dictionary-based risk classifier.

What Are Food Companies Afraid Of?
This repository contains the data, code and analysis for a study of how major U.S. food and beverage companies describe their business risks. We analyze the Risk Factors section (Item 1A) of Form 10-K annual reports filed with the SEC for 8 companies over FY2021–FY2025 (40 company-year observations).
Companies: Coca-Cola (KO), Conagra Brands (CAG), General Mills (GIS), Campbell’s (CPB), Mondelez (MDLZ), Hershey (HSY), Kraft Heinz (KHC), Tyson Foods (TSN).
Pipeline:
Filing registry. Collect 10-K filings from SEC EDGAR (CIK, fiscal year end, filing date, auditor) and cross-check them against the SEC API.
Extraction. Pull the full Item 1A text from each filing and check it for truncation.
Classification. Tag risk categories with a keyword dictionary (risk_dictionary.py). Every match keeps its supporting text evidence.
Validation. Compare automatic results with manual annotation (precision / recall), then refine and freeze the dictionary.
Analysis. Find industry-wide vs. company-specific risks, track year-over-year trends, spot emerging and disappearing risks, and link them to external events (inflation, supply chains, tariffs, geopolitics). Also look at Item 1A length and auditors (Big Four or not).
Outputs: a company × risk category heatmap, risk trend charts, an auditor table, and a final analytical report.
All results are reproducible from the final CSV and the versioned dictionary.
