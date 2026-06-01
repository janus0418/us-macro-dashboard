#!/usr/bin/env python3
"""
US Macro Dashboard - self-contained builder (catalog + dashboard in one file).

Reads  : all_macro_data.parquet   (in this same folder)
Writes : indicator_catalog.json   (regenerated from the parquet)
         macro_dashboard.html     (the single-file dashboard)

Part 1 below is the indicator-catalog builder (was build_catalog.py); Part 2 is
the dashboard builder (was build_dashboard.py). All paths resolve to THIS file's
folder, so the folder is fully portable. Run:  python3 build_dashboard.py
"""

# ============================================================================
# PART 1 of 2 - INDICATOR CATALOG BUILDER (from build_catalog.py)
# ============================================================================

"""
Build the indicator research catalog from the data and the dashboard markdown.

Output: outputs/indicator_catalog.json — used by the dashboard for tooltips/info panels.

Each entry:
  {
    indicator: "CPI YoY",
    ticker: "CPI YOY Index",
    category: "18_CPI_PPI_PCE",
    theme: "Inflation",
    units: "%",
    frequency: "Monthly",
    source: "BLS",
    description: "...",
    importance: "...",
    signal_high: "...",
    signal_low: "...",
    related: ["Core CPI YoY", "PCE Deflator YoY"]
  }
"""
import pandas as pd
import json
import re
from pathlib import Path

# ROOT derives from this script's own location (outputs/build_catalog.py -> project
# root), so it runs in any sandbox or on the host with no per-session path edits.
ROOT = Path(__file__).resolve().parent
DATA_PARQUET = ROOT / "all_macro_data.parquet"
DATA_CSV = ROOT / "all_macro_data_long.csv"
DATA = DATA_PARQUET if DATA_PARQUET.exists() else DATA_CSV

def load_long():
    """Load the long-format dataset, preferring Parquet (47x smaller, 2x faster)."""
    if DATA_PARQUET.exists():
        d = pd.read_parquet(DATA_PARQUET)
    else:
        d = pd.read_csv(DATA_CSV)
    # category dtypes from parquet -> plain str so downstream string ops/json behave
    for c in ["category", "indicator", "ticker", "field"]:
        if c in d.columns:
            d[c] = d[c].astype(str)
    d["date"] = pd.to_datetime(d["date"])
    return d

# Theme assignment from category
THEME_MAP = {
    "01_GDP": "Growth",
    "02_IP_Headline": "Growth",
    "03_CapUtil_Detail": "Growth",
    "04_IP_Detail": "Growth",
    "05_Orders_Inventories": "Growth",
    "06_Retail": "Growth",
    "07_PMIs": "Surveys",
    "08_Regional_Fed": "Surveys",
    "09_SLOOS": "Credit",
    "10_Leading": "Surveys",
    "11_Nowcasts": "Surveys",
    "12_Cleveland_Nowcasts": "Inflation",
    "13_Employment": "Labor",
    "14_Payrolls": "Labor",
    "15_Wages": "Labor",
    "16_JOLTS": "Labor",
    "17_Claims_Cuts": "Labor",
    "18_CPI_PPI_PCE": "Inflation",
    "19_Inflation_Breadth": "Inflation",
    "20_Inflation_Expectations": "Inflation",
    "21_Consumer_Income": "Consumer",
    "22_Consumer_Sentiment": "Consumer",
    "23_Housing": "Housing",
    "24_NFIB": "Surveys",
    "25_Policy_Rates": "Rates",
    "26_Fed_BS_TopLevel": "Fed_BS",
    "27_Fed_BS_Securities": "Fed_BS",
    "28_Fed_BS_Repos_Loans": "Fed_BS",
    "29_Fed_BS_Other_Assets": "Fed_BS",
    "30_Fed_BS_Liabilities": "Fed_BS",
    "31_SOMA": "Fed_BS",
    "32_TOMO": "Fed_BS",
    "33_Repo_Overnight": "Fed_BS",
    "35_Money_Aggregates": "Fed_BS",
    "36_Treasury_Yields": "Rates",
    "37_Vol": "Markets",
    "38_FX_REER": "Markets",
    "39_Credit": "Credit",
    "40_FCI": "Credit",
    "41_Fiscal": "Fiscal",
    "42_Debt_Outstanding": "Fiscal",
    "43_External": "External",
    "44_Commodities": "Commodities",
    "45_Sentiment": "Markets",
    "46_CPI_Hierarchy_Values": "Inflation",
    "47_CPI_Hierarchy_Weights": "Inflation",
    "48_CorePCE_MoM_Values": "PCE",
    "49_CorePCE_MoM_Weights": "PCE",
    "50_CorePCE_YoY_Values": "PCE",
    "51_CorePCE_YoY_Weights": "PCE",
    "52_PCE_MoM_Values": "PCE",
    "53_PCE_YoY_Values": "PCE",
    "54_NFP_Hierarchy_Values": "Labor",
    "55_Employment_Ratio_Education": "Labor",
    "56_Consumer_Confidence_Survey_Indicators": "Consumer",
    "57_Consumer_Confidence_Index_Detail": "Consumer",
    "58_PMI_Surveys_Index_Detail": "Surveys",
    "59_PMI_Surveys_Component_Detail": "Surveys",
    "60_NFIB_Small_Business_Optimism_Detail": "Surveys",
    "61_Challenger_Job_Layoffs_Industry": "Labor",
    "62_JOLTS_Quits_Industry": "Labor",
    "63_JOLTS_Job_Vacancies_Industry": "Labor",
    "64_JOLTS_Hires_Industry": "Labor",
    "65_Labor_Force_Participation_Age_Gender": "Labor",
    "66_Challenger_Job_Layoffs_Region": "Labor",
}

CATEGORY_DESCRIPTIONS = {
    "01_GDP": "National accounts measures of US output, income, and aggregate demand. Released by BEA, primarily quarterly. Centerpiece of macro framework — anchor for the FOMC's GDP forecasts and the basis of recession dating.",
    "02_IP_Headline": "Federal Reserve G.17 Industrial Production — output of factories, mines, and utilities. Cyclical and used by NBER for recession dating. Capacity utilization measures slack vs potential.",
    "03_CapUtil_Detail": "Capacity utilization (% of productive capacity used) by NAICS industry. Identifies sector-specific tightness — e.g. semiconductors vs. autos vs. petroleum. Long-run avg ~80%; >82% inflationary, <78% slack.",
    "04_IP_Detail": "Industrial Production by industry — granular NAICS-level decomposition. Useful for capex/cycle decomposition, energy sector tracking, and tech-cycle (semis, computer equip).",
    "05_Orders_Inventories": "Forward-looking demand signals (orders) and supply-chain state (inventories). Inventory/sales ratios warn of overbuilding; ex-transport orders strip aircraft volatility.",
    "06_Retail": "Census Bureau monthly retail trade. Real-time consumer spending pulse; control group is the GDP nowcast input.",
    "07_PMIs": "Diffusion-index business surveys (ISM, S&P/Markit, NFIB, Chicago). 50 = expansion/contraction threshold. Most-watched leading cyclical signals.",
    "08_Regional_Fed": "Regional Federal Reserve Bank manufacturing surveys — Empire (NY), Philly, Richmond, Dallas. Released early in the month, useful for nowcasting ISM Mfg.",
    "09_SLOOS": "Senior Loan Officer Opinion Survey on Bank Lending Practices — quarterly Federal Reserve survey of bank credit standards. Leads credit cycle by 1–4 quarters.",
    "10_Leading": "Conference Board LEI and OECD CLI — composite leading indices designed to anticipate cyclical turning points by 6–12 months.",
    "11_Nowcasts": "Real-time GDP / activity nowcasts (Atlanta GDPNow, NY Fed WEI), data-surprise indices (Citi, Bloomberg), and broader activity indices (CFNAI).",
    "12_Cleveland_Nowcasts": "Cleveland Fed daily-updated CPI/PCE nowcasts. Anticipate the official BLS/BEA print 2–4 weeks ahead with high accuracy.",
    "13_Employment": "BLS Household Survey aggregate labor measures — labor force, employment level, unemployment rates (U-3, U-6), employment-population ratio.",
    "14_Payrolls": "BLS Establishment Survey — nonfarm payrolls, ADP private payrolls, hours, productivity. The headline 'jobs number' is NFP change.",
    "15_Wages": "Wage growth measures: AHE (timeliest, composition-biased), ECI (Fed's preferred), Atlanta WGT (cleanest, composition-controlled), productivity, unit labor costs.",
    "16_JOLTS": "Job Openings & Labor Turnover Survey — vacancies, hires, separations, quits, layoffs. Vacancies/Unemployed ratio is Fed tightness gauge.",
    "17_Claims_Cuts": "Weekly UI claims (initial + continuing) and Challenger-Gray-Christmas job-cut announcements. Highest-frequency labor signal.",
    "18_CPI_PPI_PCE": "Headline inflation measures — CPI (BLS), PPI (BLS), PCE (BEA). Core (ex food/energy) more relevant for Fed reaction function. PCE is the official 2% target.",
    "19_Inflation_Breadth": "Trimmed-mean and median inflation measures — filter outliers to reveal underlying inflation. Cleveland (CPI/PCE), Atlanta (Sticky CPI). Often diverge from headline at turning points.",
    "20_Inflation_Expectations": "Market-implied (TIPS breakevens, swaps, 5Y5Y forwards) and survey-based (Michigan, NY Fed SCE, Conf Board) inflation expectations. Anchored expectations are the bedrock of Fed credibility.",
    "21_Consumer_Income": "BEA monthly Personal Income & Outlays — wages, transfers, saving rate, real income ex transfers. Core consumer-sector data.",
    "22_Consumer_Sentiment": "Conference Board (labor-market-tilted) and U Michigan (inflation-tilted) sentiment surveys. Often diverge based on which factor dominates.",
    "23_Housing": "Starts/permits (Census), home sales (NAR/Census), prices (Case-Shiller, FHFA), homebuilder sentiment (NAHB), mortgage activity (MBA). Most rate-sensitive sector.",
    "24_NFIB": "National Federation of Independent Business survey — small-business optimism, hiring/capex/comp plans, prices. Captures dynamics weight-underrepresented in BLS samples.",
    "25_Policy_Rates": "FOMC-set policy rates and admin rates: target range, IORB, EFFR, SOFR, ON RRP, term SOFR. The plumbing of the rates market.",
    "26_Fed_BS_TopLevel": "Fed H.4.1 weekly balance sheet — total size, supplying vs absorbing factors, reserve balances. Liquidity regime gauge.",
    "27_Fed_BS_Securities": "Fed System Open Market Account (SOMA) securities held outright — Treasuries, MBS, agency. Drives QE/QT.",
    "28_Fed_BS_Repos_Loans": "Fed lending facilities — repurchase agreements, discount window, BTFP, and dormant emergency facilities (PDCF, MMLF, etc.).",
    "29_Fed_BS_Other_Assets": "Other Fed assets — central bank liquidity swaps, gold/SDRs, foreign currency assets, special-purpose vehicles (mostly historical).",
    "30_Fed_BS_Liabilities": "Fed liabilities — currency, ON RRP, TGA (Treasury account), bank reserves. Mechanical drivers of bank-system liquidity.",
    "31_SOMA": "Daily SOMA holdings detail — Treasury bills, notes/bonds, FRNs, TIPS, agency, MBS, CMBS. Feeds into QT pace and SOMA portfolio composition analysis.",
    "32_TOMO": "Temporary Open Market Operations — daily repo and reverse repo operations. Treasury collateral active; agency operations dormant.",
    "33_Repo_Overnight": "NY Fed overnight repo operational details — submitted/accepted by collateral type. Watched at quarter-/year-ends and around debt-ceiling resolutions.",
    "35_Money_Aggregates": "Federal Reserve H.6 monetary aggregates — monetary base, M1, M2. Less central post-QE but still useful for liquidity narratives.",
    "36_Treasury_Yields": "FRB H.15 constant-maturity Treasury yields and TIPS reals — 3M to 30Y. The risk-free curve. Curve slope and term-premium are key cycle signals.",
    "37_Vol": "Implied volatility — VIX (S&P 500), VVIX (vol of VIX), MOVE (Treasury options vol). Risk regime and stress gauges.",
    "38_FX_REER": "USD indices (DXY, BBDXY) and Federal Reserve Real Effective Exchange Rates (broad, AFE, EME). Trade-weighted USD strength.",
    "39_Credit": "Bloomberg US corporate credit indices — IG and HY OAS spreads and total return. HY OAS is the canonical risk-on/risk-off gauge.",
    "40_FCI": "Composite Financial Conditions Indices — Chicago Fed NFCI/ANFCI (and sub-components), GS US FCI, Bloomberg US FCI. Synthesize rates, credit, vol, equities into one stress gauge.",
    "41_Fiscal": "US federal budget balance — monthly Treasury statement. Deficit/surplus and % of GDP.",
    "42_Debt_Outstanding": "Treasury debt outstanding by instrument — bills, notes, bonds, TIPS, FRNs, FFB. Auction supply context.",
    "43_External": "International transactions — trade balance (goods, services), exports/imports, current account, TIC capital flows.",
    "44_Commodities": "Energy (WTI, Brent, NatGas, RBOB), inventories (EIA), rig count (Baker Hughes), broad indices (BCOM, GSCI), precious metals (gold, silver).",
    "45_Sentiment": "Investor positioning/sentiment — AAII retail survey, NAAIM active manager exposure, CBOE put/call ratios, SKEW (tail risk).",
    "54_NFP_Hierarchy_Values": "BLS Establishment Survey nonfarm payroll employment by industry hierarchy — monthly change (thousands). Drill into Leisure & Hospitality, Government (State/Local), Private Education & Health, etc.",
    "55_Employment_Ratio_Education": "Employment-population ratio by educational attainment (25 and over) — less than HS, HS grad, some college, bachelor's+. BLS Household Survey.",
    "56_Consumer_Confidence_Survey_Indicators": "Conference Board Consumer Confidence survey sub-indicators incl. jobs plentiful / hard-to-get and the Labor Market Differential (plentiful − hard-to-get).",
    "57_Consumer_Confidence_Index_Detail": "Conference Board Consumer Confidence index detail by demographic and age cohort.",
    "58_PMI_Surveys_Index_Detail": "ISM / S&P-Markit PMI survey sub-indices incl. manufacturing and services employment indices.",
    "59_PMI_Surveys_Component_Detail": "ISM / PMI component diffusion detail (higher / same / lower response shares).",
    "60_NFIB_Small_Business_Optimism_Detail": "NFIB Small Business Optimism Index components incl. hiring plans, compensation plans, capex plans, credit conditions.",
    "61_Challenger_Job_Layoffs_Industry": "Challenger, Gray & Christmas announced job cuts by industry (NAICS).",
    "62_JOLTS_Quits_Industry": "BLS JOLTS quits by industry — levels in thousands.",
    "63_JOLTS_Job_Vacancies_Industry": "BLS JOLTS job openings (vacancies) by industry — levels in thousands.",
    "64_JOLTS_Hires_Industry": "BLS JOLTS hires by industry — hires rate (% of employment).",
    "65_Labor_Force_Participation_Age_Gender": "BLS labor force participation rate by age cohort and gender (seasonally adjusted).",
    "66_Challenger_Job_Layoffs_Region": "Challenger, Gray & Christmas announced job cuts by US region.",
}

CATEGORY_LABELS = {
    "01_GDP": "GDP & National Accounts",
    "02_IP_Headline": "Industrial Production (Headline)",
    "03_CapUtil_Detail": "Capacity Utilization (Detail)",
    "04_IP_Detail": "Industrial Production (Industry Detail)",
    "05_Orders_Inventories": "Orders & Inventories",
    "06_Retail": "Retail Sales",
    "07_PMIs": "PMIs",
    "08_Regional_Fed": "Regional Fed Surveys",
    "09_SLOOS": "Senior Loan Officer Survey",
    "10_Leading": "Leading Indicators",
    "11_Nowcasts": "Activity Nowcasts",
    "12_Cleveland_Nowcasts": "Cleveland Inflation Nowcasts",
    "13_Employment": "Employment",
    "14_Payrolls": "Payrolls",
    "15_Wages": "Wages & Productivity",
    "16_JOLTS": "JOLTS",
    "17_Claims_Cuts": "Jobless Claims & Layoffs",
    "18_CPI_PPI_PCE": "CPI / PPI / PCE",
    "19_Inflation_Breadth": "Inflation Breadth",
    "20_Inflation_Expectations": "Inflation Expectations",
    "21_Consumer_Income": "Consumer Income & Spending",
    "22_Consumer_Sentiment": "Consumer Sentiment",
    "23_Housing": "Housing",
    "24_NFIB": "NFIB Small Business",
    "25_Policy_Rates": "Policy Rates",
    "26_Fed_BS_TopLevel": "Fed Balance Sheet (Top Level)",
    "27_Fed_BS_Securities": "Fed BS — Securities Held",
    "28_Fed_BS_Repos_Loans": "Fed BS — Repos & Loans",
    "29_Fed_BS_Other_Assets": "Fed BS — Other Assets",
    "30_Fed_BS_Liabilities": "Fed BS — Liabilities",
    "31_SOMA": "SOMA Holdings",
    "32_TOMO": "TOMO (Open Market Ops)",
    "33_Repo_Overnight": "Overnight Repo Operations",
    "35_Money_Aggregates": "Money Aggregates",
    "36_Treasury_Yields": "Treasury Yields",
    "37_Vol": "Volatility",
    "38_FX_REER": "FX & Real Effective Exchange Rates",
    "39_Credit": "Credit Spreads",
    "40_FCI": "Financial Conditions Indices",
    "41_Fiscal": "Fiscal Balance",
    "42_Debt_Outstanding": "Debt Outstanding",
    "43_External": "External Sector",
    "44_Commodities": "Commodities",
    "45_Sentiment": "Investor Sentiment",
    "46_CPI_Hierarchy_Values": "CPI Hierarchy (Values)",
    "47_CPI_Hierarchy_Weights": "CPI Hierarchy (Weights)",
    "48_CorePCE_MoM_Values": "Core PCE Hierarchy — MoM",
    "49_CorePCE_MoM_Weights": "Core PCE Hierarchy — MoM Weights",
    "50_CorePCE_YoY_Values": "Core PCE Hierarchy — YoY",
    "51_CorePCE_YoY_Weights": "Core PCE Hierarchy — YoY Weights",
    "52_PCE_MoM_Values": "PCE Hierarchy — MoM",
    "53_PCE_YoY_Values": "PCE Hierarchy — YoY",
    "54_NFP_Hierarchy_Values": "NFP by Industry (m/m)",
    "55_Employment_Ratio_Education": "Emp-Pop Ratio by Education",
    "56_Consumer_Confidence_Survey_Indicators": "Conf Board — Survey Indicators",
    "57_Consumer_Confidence_Index_Detail": "Conf Board — Index Detail",
    "58_PMI_Surveys_Index_Detail": "PMI Surveys — Index Detail",
    "59_PMI_Surveys_Component_Detail": "PMI Surveys — Component Detail",
    "60_NFIB_Small_Business_Optimism_Detail": "NFIB Optimism Detail",
    "61_Challenger_Job_Layoffs_Industry": "Challenger Layoffs by Industry",
    "62_JOLTS_Quits_Industry": "JOLTS Quits by Industry",
    "63_JOLTS_Job_Vacancies_Industry": "JOLTS Vacancies by Industry",
    "64_JOLTS_Hires_Industry": "JOLTS Hires by Industry",
    "65_Labor_Force_Participation_Age_Gender": "LFPR by Age & Gender",
    "66_Challenger_Job_Layoffs_Region": "Challenger Layoffs by Region",
}

# Detailed metadata for headline indicators
HEADLINE = {
    # === GDP ===
    "Real GDP QoQ SAAR": {
        "description": "Quarterly change in real GDP, seasonally adjusted at an annual rate. The single most-watched US growth measure, released by BEA.",
        "importance": "Anchor for FOMC growth forecasts, fiscal projections, and equity earnings expectations. >2% = above-trend, <0% = recession risk.",
        "units": "% SAAR", "frequency": "Quarterly", "source": "BEA",
        "signal_high": "Above-trend growth — pressure on Fed to keep rates restrictive; risk-on for equities, bear-flattener for curve",
        "signal_low": "Below-trend or contraction — Fed dovishness, bull-steepener, defensive rotation",
        "related": ["Real GDP YoY", "Atlanta Fed GDPNow", "GDI QoQ", "Personal Consumption QoQ"],
    },
    "Real GDP YoY": {
        "description": "Real GDP percent change vs. four quarters ago — smooths out quarterly volatility for trend signal.",
        "importance": "Better than QoQ SAAR for trend identification; cleaner for cross-country comparisons.",
        "units": "%", "frequency": "Quarterly", "source": "BEA",
        "signal_high": "Sustained expansion", "signal_low": "Trend deterioration",
        "related": ["Real GDP QoQ SAAR"],
    },
    "GDI QoQ": {
        "description": "Gross Domestic Income — the income-side analog to GDP. Theoretically equal to GDP in expenditure terms; the gap (statistical discrepancy) is a research signal.",
        "importance": "GDI/GDP wedge has historically led GDP at recession turning points (e.g., 2007). Persistent divergence is a yellow flag.",
        "units": "% QoQ", "frequency": "Quarterly", "source": "BEA",
        "signal_high": "Strong income generation", "signal_low": "Weakness; if << GDP, watch for negative GDP revisions",
        "related": ["Real GDP QoQ SAAR"],
    },
    "Personal Consumption QoQ": {
        "description": "Real PCE component of GDP — ~70% of US GDP.",
        "importance": "The dominant GDP driver. Weakness here = weakness everywhere.",
        "units": "% QoQ", "frequency": "Quarterly", "source": "BEA",
        "signal_high": "Strong consumer", "signal_low": "Consumer retrenchment",
        "related": ["Personal Spending MoM", "Retail Sales MoM"],
    },
    # === IP ===
    "Industrial Production Level": {
        "description": "Federal Reserve G.17 measure of US industrial output — manufacturing + mining + utilities. Index, 2017=100.",
        "importance": "Cyclical proxy with strong correlation to ISM Mfg. Used by NBER as one of four official recession-dating series.",
        "units": "Index (2017=100)", "frequency": "Monthly", "source": "Federal Reserve (G.17)",
        "signal_high": "Mfg expansion", "signal_low": "Mfg contraction — recession risk if 4-mo trend turns",
        "related": ["Industrial Production YoY", "ISM Manufacturing PMI", "Capacity Utilization Total"],
    },
    "Industrial Production YoY": {
        "description": "12-month % change in IP — preferred for cycle identification (filters seasonality artifacts).",
        "importance": "Watch crossings of 0 — historically a recession signal.",
        "units": "% YoY", "frequency": "Monthly", "source": "Federal Reserve (G.17)",
        "signal_high": "Above 2% = healthy", "signal_low": "<0% = contraction",
        "related": ["Industrial Production Level"],
    },
    "Capacity Utilization Total": {
        "description": "% of total productive capacity actually used. Long-run average ~80%.",
        "importance": "Below 78% = slack (disinflationary, easy Fed). Above 82% = tight (inflationary, hiking pressure).",
        "units": "%", "frequency": "Monthly", "source": "Federal Reserve (G.17)",
        "signal_high": "Capacity tightness — inflation risk", "signal_low": "Slack — disinflation",
        "related": ["Manufacturing Capacity Utilization"],
    },
    # === Orders ===
    "Durable Goods Orders MoM": {
        "description": "MoM change in new orders for durable goods (Census Bureau M3). Volatile due to aircraft.",
        "importance": "Forward indicator for capex and manufacturing activity. Strip aircraft via 'ex Transport' series.",
        "units": "% MoM", "frequency": "Monthly", "source": "Census Bureau",
        "signal_high": "Capex demand", "signal_low": "Capex retrenchment",
        "related": ["Durable Goods ex Transport MoM", "Factory Orders MoM"],
    },
    "Factory Orders MoM": {
        "description": "Total manufacturers' new orders — durable + nondurable.",
        "importance": "Broader than durables; smoother signal of mfg demand pulse.",
        "units": "% MoM", "frequency": "Monthly", "source": "Census Bureau",
        "signal_high": "Demand expansion", "signal_low": "Demand softening",
        "related": ["Durable Goods Orders MoM"],
    },
    # === Retail ===
    "Retail Sales MoM": {
        "description": "Census Bureau Advance Monthly Retail Trade — not inflation-adjusted. Big input to GDP nowcast.",
        "importance": "Real-time consumer pulse. Watch the control group (ex autos, gas, building materials, food svcs) — that's what feeds GDP.",
        "units": "% MoM", "frequency": "Monthly", "source": "Census Bureau",
        "signal_high": "Strong consumer spending", "signal_low": "Consumer pullback",
        "related": ["Retail Sales Control Group MoM", "Personal Spending MoM"],
    },
    "Total Vehicle Sales": {
        "description": "Total US light vehicle sales (cars + trucks + SUVs), seasonally adjusted annual rate (SAAR). Captures big-ticket consumer demand and has historically led recessions by 6–12 months.",
        "importance": "Sensitive to financing rates and consumer confidence. Pre-COVID norm ~17M; supply-constrained in 2021–22.",
        "units": "Million units SAAR", "frequency": "Monthly", "source": "BEA / WardsAuto",
        "signal_high": "Strong consumer durables demand", "signal_low": "Auto recession — credit & confidence stress",
        "related": ["Retail Sales MoM"],
    },
    # === PMIs ===
    "ISM Manufacturing PMI": {
        "description": "Diffusion index of manufacturing activity — 50 = contraction/expansion threshold. Composite of new orders, production, employment, supplier deliveries, inventories.",
        "importance": "Most-watched cyclical survey. <45 = recession territory historically; >55 = strong expansion. Releases first business day of month.",
        "units": "Index (50 = neutral)", "frequency": "Monthly", "source": "ISM",
        "signal_high": "Mfg expansion — risk-on, bear-flattener", "signal_low": "Mfg contraction — defensive, bull-steepener",
        "related": ["ISM Mfg New Orders", "ISM Mfg Prices Paid", "Markit Manufacturing PMI"],
    },
    "ISM Services PMI": {
        "description": "ISM Non-Manufacturing PMI — services sector diffusion index, 50 = neutral.",
        "importance": "Services dominate US economy (~70%). Often lags mfg but more relevant for consumer-driven cycles.",
        "units": "Index", "frequency": "Monthly", "source": "ISM",
        "signal_high": "Services strength — sticky inflation risk", "signal_low": "Services slowdown — broader recession signal",
        "related": ["Markit Services PMI"],
    },
    "ISM Mfg New Orders": {
        "description": "ISM Manufacturing — new orders sub-index. Most forward-looking PMI component.",
        "importance": "Leads headline PMI by ~1–3 months. Watch the new orders / inventories ratio.",
        "units": "Index", "frequency": "Monthly", "source": "ISM",
        "signal_high": "Demand pulse strengthening", "signal_low": "Pipeline weakening",
        "related": ["ISM Manufacturing PMI"],
    },
    "ISM Mfg Prices Paid": {
        "description": "ISM Mfg — prices paid sub-index. Leading indicator of goods PPI/CPI.",
        "importance": "Strong correlation with goods inflation. >60 = pipeline pressure; <40 = goods disinflation.",
        "units": "Index", "frequency": "Monthly", "source": "ISM",
        "signal_high": "Goods price pressure building", "signal_low": "Goods disinflation",
        "related": ["PPI Final Demand MoM", "CPI YoY"],
    },
    # === Employment ===
    "Unemployment Rate (U-3)": {
        "description": "Headline unemployment rate from BLS Household Survey. Officially U-3.",
        "importance": "FOMC dual-mandate variable. Sahm Rule: 0.5pp rise from 12-mo low triggers historically. <4% = tight labor market.",
        "units": "%", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Labor market loosening — Fed dovish", "signal_low": "Tight labor market — wage pressure, hawkish",
        "related": ["U-6 Underemployment Rate", "Initial Jobless Claims", "Nonfarm Payrolls Change"],
    },
    "U-6 Underemployment Rate": {
        "description": "Broader unemployment: U-3 plus marginally attached + part-time for economic reasons.",
        "importance": "Better gauge of underemployment / labor slack than U-3.",
        "units": "%", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Hidden slack high", "signal_low": "True full employment",
        "related": ["Unemployment Rate (U-3)"],
    },
    "Employment-Population Ratio": {
        "description": "Employed persons as % of civilian noninstitutional population. Less affected by participation swings than UR.",
        "importance": "Cleanest aggregate labor utilization measure.",
        "units": "%", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Strong labor utilization", "signal_low": "Job market weak",
        "related": ["Unemployment Rate (U-3)"],
    },
    "Nonfarm Payrolls Change": {
        "description": "Monthly change in nonfarm payroll employment from BLS Establishment Survey. The headline 'jobs number'.",
        "importance": "Single biggest market mover among data prints. Watch revisions, 3-mo MA, and breadth (diffusion index).",
        "units": "Thousands", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Strong hiring — yields up, USD up", "signal_low": "Hiring slowdown — yields down, dovish Fed pricing",
        "related": ["ADP Employment Change", "Private Payrolls Change", "NF Payroll Diffusion Index"],
    },
    "ADP Employment Change": {
        "description": "ADP/Stanford Digital Economy Lab private payrolls estimate, released 2 days before NFP.",
        "importance": "Imperfect predictor of NFP private — useful directionally but high standalone error.",
        "units": "Thousands", "frequency": "Monthly", "source": "ADP",
        "signal_high": "Private hiring momentum", "signal_low": "Hiring deceleration",
        "related": ["Nonfarm Payrolls Change", "Private Payrolls Change"],
    },
    "Avg Hourly Earnings YoY": {
        "description": "BLS Establishment Survey average hourly earnings YoY. Quickest wage signal.",
        "importance": "Composition-biased (mix shifts distort) but most timely. Historical neutral ~3.5% (2% inflation + 1.5% productivity).",
        "units": "% YoY", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Wage pressure — sticky services inflation risk", "signal_low": "Wage cooling — Fed comfort",
        "related": ["Atlanta Wage Growth Tracker", "Employment Cost Index YoY"],
    },
    "Atlanta Wage Growth Tracker": {
        "description": "Atlanta Fed median wage growth, computed from CPS micro-data, controls for composition shifts.",
        "importance": "Cleaner than AHE — tracks the same workers' wage changes year-over-year. Splits Switchers vs Stayers.",
        "units": "% YoY (median)", "frequency": "Monthly", "source": "Atlanta Fed",
        "signal_high": "Underlying wage pressure", "signal_low": "Wage growth normalizing",
        "related": ["Avg Hourly Earnings YoY", "Employment Cost Index YoY"],
    },
    "Employment Cost Index YoY": {
        "description": "BLS Employment Cost Index — total compensation including benefits. Quarterly.",
        "importance": "Fed's preferred wage measure (Powell cites repeatedly). Less noisy than AHE; includes benefits.",
        "units": "% YoY", "frequency": "Quarterly", "source": "BLS",
        "signal_high": "Compensation costs accelerating", "signal_low": "Comp growth normalizing",
        "related": ["Avg Hourly Earnings YoY", "Atlanta Wage Growth Tracker"],
    },
    "Initial Jobless Claims": {
        "description": "Weekly first-time UI claim filings, seasonally adjusted. Released Thursdays.",
        "importance": "Highest-frequency labor signal. Watch 4-wk MA. Recession threshold ~350k+ (rough).",
        "units": "Thousands", "frequency": "Weekly", "source": "DOL",
        "signal_high": "Layoffs picking up — labor market deterioration", "signal_low": "Hiring tight, layoffs minimal",
        "related": ["Initial Claims 4-Wk MA", "Continuing Claims"],
    },
    "JOLTS Total Job Openings": {
        "description": "Job openings (vacancies) on the last business day of month, BLS Job Openings & Labor Turnover Survey.",
        "importance": "Vacancies/Unemployed ratio (V/U) is Fed's tightness gauge. >1.5 = very tight.",
        "units": "Thousands", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Labor demand strong — wage pressure", "signal_low": "Labor demand cooling",
        "related": ["JOLTS Job Openings YoY"],
    },
    # === CPI/PPI/PCE ===
    "CPI YoY": {
        "description": "Consumer Price Index, all urban consumers, seasonally adjusted, vs 12 months ago. Headline CPI.",
        "importance": "Most cited inflation print. Drives TIPS breakevens, COLA, and Fed reaction function (less than core).",
        "units": "% YoY", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Inflation pressure — Fed hawkish", "signal_low": "Disinflation — Fed dovish",
        "related": ["CPI MoM", "Core CPI YoY", "PCE Deflator YoY"],
    },
    "Core CPI YoY": {
        "description": "CPI excluding food and energy. Less volatile; Fed-relevant.",
        "importance": "Closely watched as 'sticky' inflation gauge. Shelter is dominant component.",
        "units": "% YoY", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Underlying inflation embedded", "signal_low": "Sustainable disinflation",
        "related": ["CPI YoY", "Core PCE YoY"],
    },
    "Core PCE YoY": {
        "description": "Core Personal Consumption Expenditures price index, ex food/energy. Fed's preferred inflation target (2%).",
        "importance": "FOMC's official target measure. Differs from CPI: chained, different basket weights, OER calculation.",
        "units": "% YoY", "frequency": "Monthly", "source": "BEA",
        "signal_high": "Fed target overshoot — restrictive policy", "signal_low": "Approaching target — room to ease",
        "related": ["PCE Deflator YoY", "Core CPI YoY"],
    },
    "PPI Final Demand MoM": {
        "description": "Producer price index, final demand. Pipeline inflation pressure.",
        "importance": "Health-care and trade services components feed directly into Core PCE. Watch margin services.",
        "units": "% MoM", "frequency": "Monthly", "source": "BLS",
        "signal_high": "Pipeline price pressure", "signal_low": "Pipeline disinflation",
        "related": ["PPI Final Demand YoY", "PPI ex F&E MoM"],
    },
    "PCE Deflator YoY": {
        "description": "Headline PCE inflation YoY. Fed's preferred headline gauge.",
        "importance": "Lower volatility than CPI; chain-weighted; what FOMC SEP forecasts.",
        "units": "% YoY", "frequency": "Monthly", "source": "BEA",
        "signal_high": "Above 2% target", "signal_low": "Below target",
        "related": ["Core PCE YoY", "CPI YoY"],
    },
    # === Inflation breadth ===
    "Cleveland Median CPI YoY": {
        "description": "CPI median item — robust measure of central tendency. Cleveland Fed publishes alongside 16% trimmed mean.",
        "importance": "Trimmed/median measures filter outliers — better gauge of underlying inflation than headline or core.",
        "units": "% YoY", "frequency": "Monthly", "source": "Cleveland Fed",
        "signal_high": "Underlying inflation persistent", "signal_low": "Underlying inflation receding",
        "related": ["Cleveland 16% Trimmed CPI YoY", "Atlanta Sticky CPI 12mo"],
    },
    "Atlanta Sticky CPI 12mo": {
        "description": "CPI items that change prices infrequently — proxy for embedded inflation expectations.",
        "importance": "Anchored measure of structural inflation (rents, education, medical). Slow to move both up and down.",
        "units": "% YoY", "frequency": "Monthly", "source": "Atlanta Fed",
        "signal_high": "Inflation expectations un-anchored upward", "signal_low": "Inflation expectations re-anchoring",
        "related": ["Atlanta Sticky CPI 3mo annlz", "Cleveland Median CPI YoY"],
    },
    # === Inflation expectations ===
    "Fed 5Y5Y Forward Inflation Exp": {
        "description": "5-year forward, 5-year inflation expectation derived from TIPS curve. Fed monitors closely.",
        "importance": "Cleanest market-implied long-run inflation expectations. Anchored ~2.0–2.4% historically.",
        "units": "%", "frequency": "Daily", "source": "Federal Reserve",
        "signal_high": "Long-run expectations un-anchoring", "signal_low": "Anchored / falling",
        "related": ["5Y5Y Forward Inflation Swap", "10Y TIPS Breakeven"],
    },
    "10Y TIPS Breakeven": {
        "description": "10-year nominal Treasury yield minus 10-year TIPS yield = market-implied 10Y avg inflation.",
        "importance": "Real-time inflation-expectation gauge for tactical macro positioning.",
        "units": "%", "frequency": "Daily", "source": "Federal Reserve / Bloomberg",
        "signal_high": "Market pricing higher inflation", "signal_low": "Pricing disinflation",
        "related": ["5Y TIPS Breakeven", "30Y TIPS Breakeven"],
    },
    "Michigan 1Y Inflation Exp": {
        "description": "U Mich Survey of Consumers — median expected inflation 1 year ahead.",
        "importance": "Survey-based expectations. Powell mentioned 'noisy but watched'. Has been spikier than market measures since 2022.",
        "units": "%", "frequency": "Monthly", "source": "U Michigan",
        "signal_high": "Households expect higher inflation", "signal_low": "Expectations re-anchoring",
        "related": ["Michigan 5-10Y Inflation Exp", "NY Fed SCE 1Y Inflation Exp"],
    },
    # === Consumer ===
    "Personal Income MoM": {
        "description": "Total personal income MoM, BEA monthly release. Includes wages, transfers, rental, interest, dividend income.",
        "importance": "Drives spending capacity; transfer-payment-heavy in 2020–21 distorted the read.",
        "units": "% MoM", "frequency": "Monthly", "source": "BEA",
        "signal_high": "Income growth supporting spending", "signal_low": "Income squeeze",
        "related": ["Personal Spending MoM", "Real Personal Income ex Transfers"],
    },
    "Personal Saving Rate": {
        "description": "Personal saving as % of disposable personal income.",
        "importance": "Buffer for future consumption. Pre-COVID norm ~7–8%; <4% = consumer drawing down savings.",
        "units": "%", "frequency": "Monthly", "source": "BEA",
        "signal_high": "Consumer building buffer", "signal_low": "Consumer running down savings",
        "related": ["Personal Income MoM"],
    },
    "Conf Board Consumer Confidence": {
        "description": "Conference Board Consumer Confidence Index. Heavier weight on labor market questions than Michigan.",
        "importance": "Differs from Michigan because labor-market-tilted; more cyclical.",
        "units": "Index (1985=100)", "frequency": "Monthly", "source": "Conference Board",
        "signal_high": "Consumer confident", "signal_low": "Consumer anxiety — spending downside risk",
        "related": ["Michigan Consumer Sentiment"],
    },
    "Michigan Consumer Sentiment": {
        "description": "U Mich Survey of Consumers headline sentiment index.",
        "importance": "Inflation-sensitive — high gas prices drag it more than CB. Long history.",
        "units": "Index (1966Q1=100)", "frequency": "Monthly", "source": "U Michigan",
        "signal_high": "Consumer optimism", "signal_low": "Consumer pessimism",
        "related": ["Conf Board Consumer Confidence", "Michigan Current Conditions", "Michigan Expectations"],
    },
    # === Housing ===
    "Housing Starts": {
        "description": "Privately owned housing starts, SAAR (Census Bureau).",
        "importance": "Cyclical, rate-sensitive. Pre-COVID norm ~1.3M; deep recessions <800k.",
        "units": "Thousands SAAR", "frequency": "Monthly", "source": "Census Bureau",
        "signal_high": "Housing-led GDP support", "signal_low": "Housing recession",
        "related": ["Building Permits", "NAHB Housing Market Index"],
    },
    "Building Permits": {
        "description": "Authorized building permits, SAAR. Leads starts by 1–2 months.",
        "importance": "Truer leading indicator than starts (less weather noise). Component of LEI.",
        "units": "Thousands SAAR", "frequency": "Monthly", "source": "Census Bureau",
        "signal_high": "Construction pipeline filling", "signal_low": "Construction pipeline draining",
        "related": ["Housing Starts"],
    },
    "Existing Home Sales": {
        "description": "Existing single-family + condo + co-op sales SAAR (NAR).",
        "importance": "85%+ of housing transactions. Sensitive to mortgage rates; lock-in effects post-2022.",
        "units": "Million SAAR", "frequency": "Monthly", "source": "NAR",
        "signal_high": "Housing turnover healthy", "signal_low": "Frozen housing market",
        "related": ["Pending Home Sales MoM", "New Home Sales"],
    },
    "Case-Shiller 20-City HPI YoY": {
        "description": "S&P CoreLogic Case-Shiller home price index, 20-city composite, YoY.",
        "importance": "Most-watched home price benchmark. 2-month lag in publication.",
        "units": "% YoY", "frequency": "Monthly", "source": "S&P / CoreLogic",
        "signal_high": "Housing wealth effect supporting consumption", "signal_low": "Home price deflation — negative wealth effect",
        "related": ["Case-Shiller National HPI YoY", "FHFA HPI MoM"],
    },
    "NAHB Housing Market Index": {
        "description": "NAHB/Wells Fargo Housing Market Index — homebuilder sentiment, 50 = neutral.",
        "importance": "Most timely housing signal — released same month. Closely tracks single-family starts.",
        "units": "Index", "frequency": "Monthly", "source": "NAHB",
        "signal_high": "Builders optimistic — rising starts pipeline", "signal_low": "Builder pessimism",
        "related": ["Housing Starts"],
    },
    # === Policy rates ===
    "Fed Funds Target Mid": {
        "description": "Midpoint of FOMC fed funds target range.",
        "importance": "The policy rate. Anchor for entire yield curve.",
        "units": "%", "frequency": "Daily (FOMC-set)", "source": "Federal Reserve",
        "signal_high": "Restrictive policy", "signal_low": "Accommodative policy",
        "related": ["EFFR", "IORB", "SOFR"],
    },
    "EFFR": {
        "description": "Effective Federal Funds Rate — daily volume-weighted median of overnight fed funds transactions.",
        "importance": "Where fed funds actually trade vs target. Spread to IORB indicates reserve scarcity.",
        "units": "%", "frequency": "Daily", "source": "FRBNY",
        "signal_high": "Fed funds market tighter than admin rates", "signal_low": "Fed funds at floor",
        "related": ["Fed Funds Target Mid", "IORB"],
    },
    "IORB": {
        "description": "Interest on Reserve Balances — admin rate Fed pays banks on reserves. Effective floor for EFFR.",
        "importance": "FOMC adjusts IORB independently of target range as plumbing tool.",
        "units": "%", "frequency": "Daily (FOMC-set)", "source": "Federal Reserve",
        "signal_high": "Floor lifted", "signal_low": "Floor lowered",
        "related": ["EFFR"],
    },
    "SOFR": {
        "description": "Secured Overnight Financing Rate — Treasury repo rate, replaced LIBOR. Set by FRBNY.",
        "importance": "Reference rate for $T+ of derivatives. Spreads to fed funds = funding stress signal.",
        "units": "%", "frequency": "Daily", "source": "FRBNY",
        "signal_high": "Repo funding tighter — collateral scarcity", "signal_low": "Ample liquidity",
        "related": ["EFFR", "30-day Avg SOFR"],
    },
    # === Fed BS ===
    "Fed Total Balance Sheet": {
        "description": "Total assets on Fed's balance sheet (H.4.1, weekly Wednesday release).",
        "importance": "QE/QT direct read. Peaked ~$9T in 2022; runoff has been ongoing.",
        "units": "USD millions", "frequency": "Weekly", "source": "Federal Reserve (H.4.1)",
        "signal_high": "QE / liquidity expansion", "signal_low": "QT / drainage",
        "related": ["Reserve Balances at Fed Banks", "Securities Held Outright Total"],
    },
    "Reserve Balances at Fed Banks": {
        "description": "Bank reserves held at Fed — the most liquidity-sensitive Fed BS line.",
        "importance": "Watch as QT proceeds. Below ~$3T has historically triggered repo stress (cf. 2019 Sep).",
        "units": "USD millions", "frequency": "Weekly", "source": "Federal Reserve (H.4.1)",
        "signal_high": "Ample reserves — easy plumbing", "signal_low": "Scarce reserves — repo stress risk",
        "related": ["US Treasury General Account (TGA Weekly)", "Reverse Repurchase Agreements Total"],
    },
    "US Treasury General Account (TGA Weekly)": {
        "description": "Treasury's checking account at the Fed (H.4.1, weekly). Drains/refills affect bank reserves.",
        "importance": "Mechanical liquidity driver. TGA up = reserves down (other things equal). Big factor around debt ceiling resolutions.",
        "units": "USD millions", "frequency": "Weekly", "source": "Federal Reserve (H.4.1)",
        "signal_high": "Treasury hoarding cash — liquidity drag", "signal_low": "Treasury spending — liquidity tailwind",
        "related": ["TGA Daily", "Reserve Balances at Fed Banks"],
    },
    "Reverse Repurchase Agreements Total": {
        "description": "ON RRP — money market funds park excess cash with Fed at admin rate. Liquidity 'pressure release valve'.",
        "importance": "Key liquidity gauge. Drained from $2.5T in 2022 to <$200B in 2024. When near zero, QT starts pressuring reserves directly.",
        "units": "USD millions", "frequency": "Weekly", "source": "Federal Reserve (H.4.1)",
        "signal_high": "Excess MMF liquidity parked", "signal_low": "MMFs deploying — bill issuance absorbed",
        "related": ["Reserve Balances at Fed Banks"],
    },
    "BTFP": {
        "description": "Bank Term Funding Program — emergency facility from March 2023 SVB stress. Closed for new loans Mar 2024.",
        "importance": "Watch wind-down trajectory; spike would signal renewed bank stress.",
        "units": "USD millions", "frequency": "Weekly", "source": "Federal Reserve (H.4.1)",
        "signal_high": "Bank stress (rising)", "signal_low": "Wind-down progressing normally",
        "related": ["Loans (Discount Window total)"],
    },
    # === Treasury yields ===
    "10Y Treasury": {
        "description": "10-year Treasury constant maturity yield. The world's risk-free benchmark.",
        "importance": "Drives mortgages, equity discount rates, EM borrowing costs. Watch 4.5% as historical psychological level.",
        "units": "%", "frequency": "Daily", "source": "FRB H.15",
        "signal_high": "Term premium / growth + inflation pricing higher", "signal_low": "Recession/disinflation pricing or flight-to-quality",
        "related": ["2Y Treasury", "30Y Treasury", "10Y TIPS Real"],
    },
    "2Y Treasury": {
        "description": "2-year Treasury constant maturity. Most Fed-policy-sensitive maturity.",
        "importance": "Tracks SOFR forwards / Fed-path expectations.",
        "units": "%", "frequency": "Daily", "source": "FRB H.15",
        "signal_high": "Hawkish Fed pricing", "signal_low": "Dovish/cuts pricing",
        "related": ["10Y Treasury"],
    },
    "10Y TIPS Real": {
        "description": "10Y TIPS yield — real (inflation-protected) yield.",
        "importance": "True cost of capital. Above 1.5% historically restrictive; sub-zero accommodative.",
        "units": "%", "frequency": "Daily", "source": "FRB H.15",
        "signal_high": "Restrictive financial conditions", "signal_low": "Accommodative",
        "related": ["10Y Treasury", "10Y TIPS Breakeven"],
    },
    # === Vol ===
    "VIX": {
        "description": "CBOE S&P 500 30-day implied volatility. The 'fear gauge'.",
        "importance": "<15 = complacent, 15–20 = normal, 20–30 = stress, >30 = panic. Key risk regime gauge.",
        "units": "Vol points", "frequency": "Daily", "source": "CBOE",
        "signal_high": "Risk-off — equity stress", "signal_low": "Risk-on / complacency",
        "related": ["VVIX", "MOVE", "VIX 3-month"],
    },
    "MOVE": {
        "description": "ICE BofA MOVE index — Treasury options-implied vol (1-month, weighted across 2/5/10/30Y).",
        "importance": "Rates equivalent of VIX. Key gauge of bond market stress / Fed-path uncertainty.",
        "units": "bps annualized", "frequency": "Daily", "source": "ICE BofA",
        "signal_high": "Rates volatility — wider FX/credit spreads", "signal_low": "Rate market settled",
        "related": ["VIX"],
    },
    # === FX ===
    "DXY": {
        "description": "ICE US Dollar Index — USD vs basket of EUR, JPY, GBP, CAD, SEK, CHF.",
        "importance": "Most-watched USD gauge. EUR-heavy (~58%). Strong USD = headwind for EM, commodities, multinational EPS.",
        "units": "Index", "frequency": "Daily", "source": "ICE",
        "signal_high": "USD strength — risk-off / yield differential", "signal_low": "USD weakness — risk-on / Fed dovish vs RoW",
        "related": ["BBDXY", "Fed Real Broad Dollar"],
    },
    "BBDXY": {
        "description": "Bloomberg Dollar Index — broader USD basket including CNY, MXN, KRW, INR.",
        "importance": "More representative of US trade-weighted dollar than DXY (which is EUR-heavy).",
        "units": "Index", "frequency": "Daily", "source": "Bloomberg",
        "signal_high": "USD strength", "signal_low": "USD weakness",
        "related": ["DXY", "Fed Real Broad Dollar"],
    },
    # === Credit ===
    "Bloomberg US IG OAS": {
        "description": "Option-adjusted spread on Bloomberg US Investment Grade Corporate Bond Index. bps over Treasury.",
        "importance": "Investment-grade credit risk premium. <100 = tight, 150+ = stress, 250+ = recession-like.",
        "units": "bps", "frequency": "Daily", "source": "Bloomberg",
        "signal_high": "Credit stress — risk-off", "signal_low": "Credit complacency / search for yield",
        "related": ["Bloomberg US HY OAS"],
    },
    "Bloomberg US HY OAS": {
        "description": "Option-adjusted spread on Bloomberg US High Yield Corporate Bond Index.",
        "importance": "Most cyclically sensitive credit gauge. <300 = euphoria, 500 = normal, 800+ = recession.",
        "units": "bps", "frequency": "Daily", "source": "Bloomberg",
        "signal_high": "HY stress — recession risk pricing", "signal_low": "Risk-on credit conditions",
        "related": ["Bloomberg US IG OAS"],
    },
    # === FCI ===
    "Chicago Fed NFCI": {
        "description": "Chicago Fed National Financial Conditions Index. Z-score: 0 = average, + = tight, − = loose.",
        "importance": "Composite of 105 financial indicators. Above 0 historically tied to stress.",
        "units": "Z-score (0=avg)", "frequency": "Weekly", "source": "Chicago Fed",
        "signal_high": "Financial conditions tight", "signal_low": "Financial conditions loose",
        "related": ["Chicago Fed ANFCI", "GS US FCI", "Bloomberg US FCI"],
    },
    "Chicago Fed ANFCI": {
        "description": "Adjusted NFCI — controls for current economic activity (isolates pure financial stress).",
        "importance": "Better stress gauge than NFCI when activity is weak (which mechanically tightens FCI).",
        "units": "Z-score", "frequency": "Weekly", "source": "Chicago Fed",
        "signal_high": "True financial stress", "signal_low": "Easy conditions",
        "related": ["Chicago Fed NFCI"],
    },
    # === Nowcasts ===
    "Atlanta Fed GDPNow": {
        "description": "Atlanta Fed nowcast of current-quarter real GDP, updated as data flows in.",
        "importance": "Most-cited GDP nowcast. Useful signal but be aware of quarter-start initial-conditions noise.",
        "units": "% SAAR", "frequency": "Daily-updated", "source": "Atlanta Fed",
        "signal_high": "Current Q strong", "signal_low": "Current Q weak",
        "related": ["NY Fed Weekly Economic Index"],
    },
    "Citi US Economic Surprise": {
        "description": "Citi US Economic Surprise Index — actual data prints minus consensus, weighted, 3-mo decay.",
        "importance": "Tactical positioning gauge. Mean-reverting. Sustained negative = consensus too high.",
        "units": "Index", "frequency": "Daily", "source": "Citi",
        "signal_high": "Data beating expectations — yields up, USD up", "signal_low": "Data disappointing — yields down",
        "related": ["Bloomberg US Economic Surprise"],
    },
    "Chicago Fed National Activity": {
        "description": "Chicago Fed National Activity Index — weighted avg of 85 monthly indicators. 0 = trend.",
        "importance": "3-mo MA below -0.7 has signaled recession. Comprehensive 'cycle' read.",
        "units": "Index (0=trend)", "frequency": "Monthly", "source": "Chicago Fed",
        "signal_high": "Above trend growth", "signal_low": "Below trend / recession risk",
        "related": ["CFNAI 3-mo MA"],
    },
    # === Commodities ===
    "WTI Crude Front": {
        "description": "WTI Cushing front-month futures. North American crude benchmark.",
        "importance": "Drives gasoline, headline CPI. Watch backwardation/contango (curve shape).",
        "units": "$/bbl", "frequency": "Daily", "source": "NYMEX",
        "signal_high": "Energy inflation pulse / strong demand", "signal_low": "Demand weakening / supply glut",
        "related": ["Brent Crude Front", "RBOB Gasoline"],
    },
    "Gold": {
        "description": "Gold spot, $/oz.",
        "importance": "Hedges real-rates downside, USD weakness, geopolitical risk. CB demand has been a major driver.",
        "units": "$/oz", "frequency": "Daily", "source": "Bloomberg",
        "signal_high": "Risk-off / real rates falling / USD weakness", "signal_low": "Risk-on / USD strong",
        "related": ["Silver", "10Y TIPS Real", "DXY"],
    },
    "Bloomberg Commodity Index": {
        "description": "BCOM — broad commodity benchmark, balanced across energy, ag, metals.",
        "importance": "Cleanest commodities beta. Cycle-sensitive.",
        "units": "Index", "frequency": "Daily", "source": "Bloomberg",
        "signal_high": "Reflation / cycle accelerating", "signal_low": "Disinflation / cycle slowing",
        "related": ["S&P GSCI", "WTI Crude Front"],
    },
    # === Sentiment ===
    "AAII Bullish %": {
        "description": "American Association of Individual Investors weekly bullishness survey.",
        "importance": "Contrarian indicator at extremes. Above ~50% = retail euphoria; below ~20% = capitulation.",
        "units": "%", "frequency": "Weekly", "source": "AAII",
        "signal_high": "Retail bullish — contrarian bearish at extremes", "signal_low": "Retail bearish — contrarian bullish",
        "related": ["AAII Bearish %", "NAAIM Exposure Index"],
    },
    "CBOE Equity Put/Call": {
        "description": "CBOE equity-only put/call ratio.",
        "importance": "Spike high = fear (contrarian buy); below 0.5 = euphoria.",
        "units": "Ratio", "frequency": "Daily", "source": "CBOE",
        "signal_high": "Fear / hedging — contrarian bullish", "signal_low": "Greed — contrarian bearish",
        "related": ["CBOE Total Put/Call"],
    },
    # === Misc ===
    "OECD Leading Indicator": {
        "description": "OECD Composite Leading Indicator for the United States. 100 = trend.",
        "importance": "6–9 month leading indicator of cyclical turning points.",
        "units": "Index (100=trend)", "frequency": "Monthly", "source": "OECD",
        "signal_high": "Growth above trend ahead", "signal_low": "Growth below trend ahead",
        "related": ["Conf Board LEI Level"],
    },
    "Conf Board LEI Level": {
        "description": "Conference Board Leading Economic Index — 10-component composite.",
        "importance": "Six-month rate of change <-4% has called every US recession since 1959 (with a few false positives).",
        "units": "Index", "frequency": "Monthly", "source": "Conference Board",
        "signal_high": "Expansion ahead", "signal_low": "Recession risk rising",
        "related": ["Conf Board LEI YoY", "OECD Leading Indicator"],
    },
    "NY Fed Weekly Economic Index": {
        "description": "NY Fed WEI — weekly read of growth based on 10 high-frequency indicators.",
        "importance": "Most timely growth pulse. Scaled to roughly track YoY GDP %.",
        "units": "%", "frequency": "Weekly", "source": "NY Fed",
        "signal_high": "Activity accelerating", "signal_low": "Activity decelerating",
        "related": ["Atlanta Fed GDPNow"],
    },
    "Cleveland CPI Nowcast Current": {
        "description": "Cleveland Fed nowcast of current-month CPI YoY, updated daily.",
        "importance": "Anticipates the official CPI print 2–4 weeks ahead with high accuracy.",
        "units": "% YoY", "frequency": "Daily", "source": "Cleveland Fed",
        "signal_high": "Inflation upside risk for next print", "signal_low": "Print likely to surprise lower",
        "related": ["Cleveland Core CPI Nowcast Current", "CPI YoY"],
    },
    "Initial Claims 4-Wk MA": {
        "description": "4-week moving average of initial unemployment claims — smooths weekly noise.",
        "importance": "Trend signal preferred over weekly print. Recession threshold ~330k+.",
        "units": "Thousands", "frequency": "Weekly", "source": "DOL",
        "signal_high": "Layoff trend rising — labor cooling", "signal_low": "Tight labor market",
        "related": ["Initial Jobless Claims", "Continuing Claims"],
    },
    "Continuing Claims": {
        "description": "Continuing UI claims (insured unemployed) — those who remain on benefits in subsequent weeks.",
        "importance": "Captures hiring rate (how quickly people find new jobs). Rises = labor mkt loosening.",
        "units": "Thousands", "frequency": "Weekly", "source": "DOL",
        "signal_high": "People staying unemployed longer — labor weakness", "signal_low": "Tight labor mkt — quick re-hiring",
        "related": ["Initial Jobless Claims"],
    },
    "Retail Sales Control Group MoM": {
        "description": "Retail Sales ex autos, gasoline, building materials, food services. Direct GDP nowcast input.",
        "importance": "Cleanest read on durable consumer spending. The number that drives GDP-tracking models.",
        "units": "% MoM", "frequency": "Monthly", "source": "Census Bureau",
        "signal_high": "Strong consumer", "signal_low": "Consumer pulling back",
        "related": ["Retail Sales MoM"],
    },
    "Bloomberg US Economic Surprise": {
        "description": "Bloomberg ECO US Surprise Index — actual data prints minus survey median, weighted, decayed.",
        "importance": "Tactical alternate to Citi Surprise; mean-reverting. Useful for relative reading.",
        "units": "Index", "frequency": "Daily", "source": "Bloomberg",
        "signal_high": "Data beating expectations", "signal_low": "Data disappointing",
        "related": ["Citi US Economic Surprise"],
    },
    "CFNAI 3-mo MA": {
        "description": "3-month moving average of Chicago Fed National Activity Index. Smooths monthly volatility.",
        "importance": "Below -0.7 has historically signaled a US recession.",
        "units": "Index (0=trend)", "frequency": "Monthly", "source": "Chicago Fed",
        "signal_high": "Above-trend growth", "signal_low": "<-0.7 historically recessionary",
        "related": ["Chicago Fed National Activity"],
    },
    "SF Fed Labor Market Stress": {
        "description": "SF Fed daily Labor Market Stress Index — early warning gauge of labor market deterioration.",
        "importance": "Daily-frequency labor market stress. Useful for short-horizon risk monitoring.",
        "units": "Index", "frequency": "Daily", "source": "SF Fed",
        "signal_high": "Labor market stress rising", "signal_low": "Labor market healthy",
        "related": ["Initial Jobless Claims"],
    },
    "SF Fed Proxy Funds Rate": {
        "description": "SF Fed Proxy Funds Rate — a 'shadow' fed funds rate that reflects the broader stance of monetary policy (rates + balance sheet + forward guidance).",
        "importance": "Captures effective stance of policy when actual fed funds is at zero or stance is influenced by QE/forward guidance.",
        "units": "%", "frequency": "Daily", "source": "SF Fed",
        "signal_high": "Effective policy more restrictive than fed funds suggests", "signal_low": "Effective policy more accommodative",
        "related": ["Fed Funds Target Mid"],
    },
    "Personal Spending MoM": {
        "description": "BEA monthly Personal Consumption Expenditures, MoM. PCE = ~70% of GDP.",
        "importance": "Most direct GDP-component view of consumer.",
        "units": "% MoM", "frequency": "Monthly", "source": "BEA",
        "signal_high": "Spending strong", "signal_low": "Spending weak",
        "related": ["Personal Income MoM", "Retail Sales MoM"],
    },
}

# Patterns for unit / frequency / source inference for non-headline tickers
def infer_units(name):
    n = name.lower()
    if "yoy" in n or "% y" in n or "y/y" in n or "yo y" in n: return "% YoY"
    if "mom" in n or "% m" in n or "m/m" in n: return "% MoM"
    if "qoq" in n or "% q" in n or "saar" in n.replace("usd",""): return "% QoQ"
    if "rate" in n and ("unemp" in n or "saving" in n or "quit" in n or "labor" in n): return "%"
    if "%" in name: return "%"
    if "usd bn" in n or "billions" in n: return "USD bn"
    if "usd millions" in n: return "USD m"
    if "thousand" in n: return "Thousands"
    if "index" in n or "indicator" in n or "pmi" in n or "comfort" in n: return "Index"
    if "spread" in n or "oas" in n: return "bps"
    if "treasury" in n or "tips" in n or "sofr" in n or "iorb" in n or "yield" in n: return "%"
    if "rigs" in n: return "Count"
    if "vix" in n or "vvix" in n or "skew" in n or "move" in n: return "Vol"
    if "wti" in n or "crude" in n or "brent" in n or "rbob" in n: return "$/bbl"
    if "gold" in n or "silver" in n: return "$/oz"
    if "fed funds" in n or "effr" in n: return "%"
    return ""

def infer_frequency(name, n_obs):
    if n_obs > 400: return "Daily"
    if n_obs > 90: return "Weekly"
    if n_obs > 15: return "Monthly"
    return "Quarterly"

def infer_source(category, name):
    n = name.lower()
    if "atlanta" in n: return "Atlanta Fed"
    if "cleveland" in n: return "Cleveland Fed"
    if "ny fed" in n or "weekly economic" in n: return "NY Fed"
    if "sf fed" in n: return "SF Fed"
    if "chicago" in n or "nfci" in n or "cfnai" in n: return "Chicago Fed"
    if "philly" in n or "philadelphia" in n: return "Philly Fed"
    if "richmond" in n: return "Richmond Fed"
    if "dallas" in n: return "Dallas Fed"
    if "kansas" in n: return "KC Fed"
    if "empire" in n: return "NY Fed"
    if "ism" in n: return "ISM"
    if "markit" in n: return "S&P Global / Markit"
    if "lei" in n or "conf board" in n: return "Conference Board"
    if "michigan" in n: return "U Michigan"
    if "naim" in n: return "NAAIM"
    if "aaii" in n: return "AAII"
    if "cboe" in n: return "CBOE"
    if "vix" in n or "vvix" in n or "skew" in n: return "CBOE"
    if "move" in n: return "ICE BofA"
    if "oecd" in n: return "OECD"
    if "fhfa" in n: return "FHFA"
    if "case-shiller" in n or "case shiller" in n: return "S&P / CoreLogic"
    if "nahb" in n: return "NAHB"
    if "mba" in n: return "MBA"
    if "nar" in n or "existing home" in n or "pending home" in n: return "NAR"
    if "challenger" in n: return "Challenger Gray Christmas"
    if "nfp" in n or "payroll" in n or "ahe" in n or "hourly earnings" in n or "eci" in n or "jolts" in n or "u-3" in n or "u-6" in n or "unemployment" in n or "claims" in n.lower(): return "BLS"
    if "adp" in n: return "ADP"
    if "cpi" in n or "ppi" in n or "import price" in n or "productivity" in n: return "BLS"
    if "pce" in n or "personal income" in n or "personal spending" in n or "gdp" in n or "gdi" in n: return "BEA"
    if "trade balance" in n or "exports" in n or "imports" in n or "current account" in n: return "BEA / Census"
    if "tic" in n: return "Treasury TIC"
    if "debt" in n: return "Treasury"
    if "fed funds" in n or "iorb" in n or "effr" in n or "sofr" in n: return "Federal Reserve"
    if "sloos" in category or "tighter" in n or "stronger" in n: return "Federal Reserve (SLOOS)"
    if "treasury" in n or "tips" in n: return "FRB H.15"
    if "fed " in n or "soma" in n or "tomo" in n or "repo" in n or "rrp" in n or "btfp" in n or "tga" in n: return "Federal Reserve (H.4.1 / NY Fed)"
    if "money" in n or "monetary base" in n or "m1" in n or "m2" in n: return "Federal Reserve (H.6)"
    if "industrial production" in n or "capacity" in n or "ip " in n: return "Federal Reserve (G.17)"
    if "factory orders" in n or "durable goods" in n or "wholesale inv" in n or "business inv" in n or "retail" in n or "housing starts" in n or "building permits" in n or "new home" in n: return "Census Bureau"
    if "consumer confidence" in n or "conf board" in n: return "Conference Board"
    if "nfib" in n: return "NFIB"
    if "wti" in n or "brent" in n or "natural gas" in n or "rbob" in n: return "NYMEX / ICE"
    if "eia" in n: return "EIA"
    if "baker hughes" in n: return "Baker Hughes"
    if "bloomberg" in n: return "Bloomberg"
    if "gold" in n or "silver" in n: return "LBMA"
    if "gsci" in n: return "S&P"
    if "bcom" in n.lower() or "commodity index" in n: return "Bloomberg"
    if "dxy" in n or "bbdxy" in n: return "ICE / Bloomberg"
    if "reer" in n or "real broad" in n or "real reer" in n: return "Federal Reserve / BIS"
    if "credit" in n.lower() or "spread" in n.lower() or "oas" in n.lower() or "high yield" in n or "investment grade" in n or "ig " in n or "hy " in n: return "Bloomberg"
    if "fci" in n.lower() or "financial conditions" in n.lower(): return "GS / Bloomberg / Chicago Fed"
    if "gsci" in n or "commodity" in n: return "S&P / Bloomberg"
    return ""

def main():
    df = load_long()
    counts = df.groupby("indicator").size()

    # Build index
    catalog = {}
    cat_meta = {}
    for cat in sorted(df["category"].unique()):
        sub = df[df["category"] == cat]
        cat_meta[cat] = {
            "label": CATEGORY_LABELS.get(cat, cat),
            "theme": THEME_MAP.get(cat, "Other"),
            "indicator_count": int(sub["indicator"].nunique()),
            "description": CATEGORY_DESCRIPTIONS.get(cat, ""),
        }
        for ind in sub["indicator"].unique():
            ind_df = sub[sub["indicator"] == ind].sort_values("date")
            ticker = ind_df.iloc[0]["ticker"]
            n = len(ind_df)
            latest = ind_df.iloc[-1]
            entry = {
                "indicator": ind,
                "ticker": ticker,
                "category": cat,
                "category_label": CATEGORY_LABELS.get(cat, cat),
                "theme": THEME_MAP.get(cat, "Other"),
                "n_obs": n,
                "first_date": ind_df.iloc[0]["date"].strftime("%Y-%m-%d"),
                "last_date": latest["date"].strftime("%Y-%m-%d"),
                "last_value": float(latest["value"]),
                "units": infer_units(ind),
                "frequency": infer_frequency(ind, n),
                "source": infer_source(cat, ind),
                "description": "",
                "importance": "",
                "signal_high": "",
                "signal_low": "",
                "related": [],
            }
            # Override with headline data if present
            if ind in HEADLINE:
                h = HEADLINE[ind]
                for k, v in h.items():
                    entry[k] = v
            else:
                # Auto-generate description for sub-component indicators by category
                if cat == "03_CapUtil_Detail":
                    entry["units"] = entry["units"] or "%"
                    entry["source"] = entry["source"] or "Federal Reserve (G.17)"
                    entry["description"] = f"Capacity utilization for {ind} — % of productive capacity actually used in this NAICS industry. Long-run avg ~80%."
                elif cat == "04_IP_Detail":
                    entry["units"] = entry["units"] or "Index"
                    entry["source"] = entry["source"] or "Federal Reserve (G.17)"
                    entry["description"] = f"Industrial Production index for {ind} — output level for this NAICS industry, indexed to 2017=100."
                elif cat == "08_Regional_Fed":
                    entry["units"] = entry["units"] or "Index"
                    entry["description"] = f"{ind} — regional Fed manufacturing diffusion index. Positive = expansion, negative = contraction. Helps nowcast ISM."
                elif cat == "09_SLOOS":
                    entry["units"] = entry["units"] or "Net %"
                    entry["source"] = entry["source"] or "Federal Reserve (SLOOS)"
                    entry["description"] = f"Senior Loan Officer Survey — net % of banks reporting {ind.lower()}. Positive = tightening, negative = easing."
                elif cat == "10_Leading":
                    entry["source"] = entry["source"] or "Conference Board"
                    entry["description"] = f"{ind} — component or aggregate of the Conference Board Leading Economic Index."
                elif cat == "12_Cleveland_Nowcasts":
                    entry["units"] = entry["units"] or "% YoY"
                    entry["source"] = entry["source"] or "Cleveland Fed"
                    entry["description"] = f"Cleveland Fed inflation nowcast: {ind}. Daily-updated forecast of upcoming CPI/PCE release."
                elif cat == "16_JOLTS":
                    entry["source"] = entry["source"] or "BLS (JOLTS)"
                    entry["description"] = f"JOLTS — {ind}. Job Openings and Labor Turnover Survey component."
                elif cat == "20_Inflation_Expectations":
                    entry["units"] = entry["units"] or "%"
                    entry["description"] = f"{ind} — measure of expected future inflation, market- or survey-derived."
                elif cat == "23_Housing":
                    entry["description"] = f"{ind} — US housing market indicator."
                elif cat in ("26_Fed_BS_TopLevel","27_Fed_BS_Securities","28_Fed_BS_Repos_Loans","29_Fed_BS_Other_Assets","30_Fed_BS_Liabilities"):
                    entry["units"] = "USD m"
                    entry["source"] = "Federal Reserve (H.4.1)"
                    entry["description"] = f"Federal Reserve H.4.1 balance sheet line item: {ind}. Released weekly, USD millions average of daily figures."
                elif cat == "31_SOMA":
                    entry["units"] = "USD m"
                    entry["source"] = "NY Fed (SOMA)"
                    entry["description"] = f"NY Fed SOMA holdings: {ind}. Daily."
                elif cat == "32_TOMO":
                    entry["source"] = entry["source"] or "NY Fed"
                    entry["description"] = f"NY Fed Temporary Open Market Operations: {ind}. Daily repo operations."
                elif cat == "33_Repo_Overnight":
                    entry["source"] = entry["source"] or "NY Fed"
                    entry["description"] = f"NY Fed Overnight Repo Operations — {ind}."
                elif cat == "36_Treasury_Yields":
                    entry["units"] = entry["units"] or "%"
                    entry["source"] = entry["source"] or "FRB H.15"
                    entry["description"] = f"{ind} constant-maturity yield. Daily."
                elif cat == "44_Commodities":
                    entry["description"] = f"{ind} — commodity price or supply indicator."
                elif cat == "42_Debt_Outstanding":
                    entry["units"] = entry["units"] or "USD bn"
                    entry["source"] = entry["source"] or "US Treasury"
                    entry["description"] = f"{ind} — Treasury debt outstanding by instrument."
                elif cat == "01_GDP":
                    entry["source"] = entry["source"] or "BEA"
                    entry["description"] = entry["description"] or f"{ind} — GDP/national-accounts component (BEA)."
                elif cat == "02_IP_Headline":
                    entry["source"] = entry["source"] or "Federal Reserve (G.17)"
                    entry["description"] = entry["description"] or f"{ind} — Industrial Production headline."
                elif cat == "05_Orders_Inventories":
                    entry["source"] = entry["source"] or "Census Bureau"
                    entry["description"] = entry["description"] or f"{ind} — orders/inventories indicator from Census Bureau M3."
                elif cat == "06_Retail":
                    entry["source"] = entry["source"] or "Census Bureau"
                    entry["description"] = entry["description"] or f"{ind} — retail trade indicator."
                elif cat == "07_PMIs":
                    entry["units"] = entry["units"] or "Index"
                    entry["description"] = entry["description"] or f"{ind} — diffusion index, 50 = neutral."
                elif cat == "13_Employment":
                    entry["source"] = entry["source"] or "BLS"
                    entry["description"] = entry["description"] or f"{ind} — BLS employment indicator."
                elif cat == "14_Payrolls":
                    entry["source"] = entry["source"] or "BLS"
                    entry["description"] = entry["description"] or f"{ind} — payrolls/hours indicator."
                elif cat == "15_Wages":
                    entry["description"] = entry["description"] or f"{ind} — wage/comp/productivity indicator."
                elif cat == "17_Claims_Cuts":
                    entry["source"] = entry["source"] or "DOL"
                    entry["description"] = entry["description"] or f"{ind} — labor market layoff/separation signal."
                elif cat == "18_CPI_PPI_PCE":
                    entry["description"] = entry["description"] or f"{ind} — headline inflation indicator."
                elif cat == "19_Inflation_Breadth":
                    entry["units"] = entry["units"] or "% YoY"
                    entry["description"] = entry["description"] or f"{ind} — robust/trimmed measure of underlying inflation."
                elif cat == "21_Consumer_Income":
                    entry["source"] = entry["source"] or "BEA"
                    entry["description"] = entry["description"] or f"{ind} — consumer income/spending indicator."
                elif cat == "22_Consumer_Sentiment":
                    entry["description"] = entry["description"] or f"{ind} — consumer sentiment survey indicator."
                elif cat == "24_NFIB":
                    entry["source"] = entry["source"] or "NFIB"
                    entry["description"] = entry["description"] or f"{ind} — NFIB small business survey component."
                elif cat == "25_Policy_Rates":
                    entry["units"] = entry["units"] or "%"
                    entry["description"] = entry["description"] or f"{ind} — policy/admin/reference rate."
                elif cat == "35_Money_Aggregates":
                    entry["source"] = entry["source"] or "Federal Reserve (H.6)"
                    entry["description"] = entry["description"] or f"{ind} — monetary aggregate."
                elif cat == "37_Vol":
                    entry["description"] = entry["description"] or f"{ind} — implied volatility index."
                elif cat == "38_FX_REER":
                    entry["description"] = entry["description"] or f"{ind} — USD/FX index."
                elif cat == "39_Credit":
                    entry["description"] = entry["description"] or f"{ind} — corporate credit OAS spread or total return."
                elif cat == "40_FCI":
                    entry["description"] = entry["description"] or f"{ind} — financial conditions composite."
                elif cat == "41_Fiscal":
                    entry["description"] = entry["description"] or f"{ind} — federal fiscal balance."
                elif cat == "43_External":
                    entry["description"] = entry["description"] or f"{ind} — US external sector indicator."
                elif cat == "45_Sentiment":
                    entry["description"] = entry["description"] or f"{ind} — investor sentiment/positioning."
            catalog[ind] = entry

    out = {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": int(len(df)),
        "indicator_count": int(df["indicator"].nunique()),
        "category_count": int(df["category"].nunique()),
        "date_range": [df["date"].min().strftime("%Y-%m-%d"), df["date"].max().strftime("%Y-%m-%d")],
        "categories": cat_meta,
        "indicators": catalog,
    }
    out_path = ROOT / "indicator_catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"Wrote {out_path}: {len(catalog)} indicators across {len(cat_meta)} categories")

if True:  # (was __main__ guard)
    main()


# ============================================================================
# PART 2 of 2 - DASHBOARD BUILDER (from build_dashboard.py)
# ============================================================================

"""
Build the dashboard: assemble compact embedded data + write self-contained HTML.

Output: outputs/macro_dashboard.html (single file, ~3-5 MB)
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# ROOT derives from this script's own location (outputs/build_dashboard.py -> project
# root), so the build runs in any sandbox or on the host with no per-session path edits.
ROOT = Path(__file__).resolve().parent

# 1. Load data — prefer Parquet (47x smaller on disk, ~2x faster build path)
_pq = ROOT / "all_macro_data.parquet"
if _pq.exists():
    df = pd.read_parquet(_pq)
    for _c in ["category", "indicator", "ticker", "field"]:
        if _c in df.columns:
            df[_c] = df[_c].astype(str)   # category dtype -> str for groupby/json
else:
    df = pd.read_csv(ROOT / "all_macro_data_long.csv")
df["date"] = pd.to_datetime(df["date"])
catalog = json.load(open(ROOT / "indicator_catalog.json"))

# 2. Build per-TICKER timeseries [(date_str, value), ...]
# IMPORTANT: 964 indicator names collide across categories (Core PCE > Services
# exists in both cat 48 MoM and cat 50 YoY with different tickers). Grouping by
# name would merge them. Tickers are guaranteed unique (2502 vs 1538 names).
series = {}
for tkr, sub in df.groupby("ticker"):
    sub = sub.sort_values("date")
    series[tkr] = [[d.strftime("%Y-%m-%d"), round(float(v), 6)] for d, v in zip(sub["date"], sub["value"])]
print(f"Built {len(series)} per-ticker series")

# 3. Build slim indicator catalog (omit redundant fields)
slim = {}
for ind, v in catalog["indicators"].items():
    slim[ind] = {
        "t": v["ticker"],
        "c": v["category"],
        "cl": v["category_label"],
        "th": v["theme"],
        "u": v["units"],
        "f": v["frequency"],
        "s": v["source"],
        "d": v["description"],
        "i": v.get("importance", ""),
        "sh": v.get("signal_high", ""),
        "sl": v.get("signal_low", ""),
        "r": v.get("related", []),
        "n": v["n_obs"],
        "ld": v["last_date"],
        "lv": v["last_value"],
    }

# 4. Identify hero indicators (curated front-page tiles)
HERO = [
    "Fed Funds Target Mid", "2Y Treasury", "10Y Treasury", "SOFR",
    "DXY", "MOVE", "VIX", "Bloomberg US HY OAS",
    "CPI YoY", "Core PCE YoY", "Cleveland CPI Nowcast Current", "10Y TIPS Breakeven",
    "Real GDP QoQ SAAR", "Atlanta Fed GDPNow", "ISM Manufacturing PMI", "ISM Services PMI",
    "Unemployment Rate (U-3)", "Nonfarm Payrolls Change", "Initial Jobless Claims", "Avg Hourly Earnings YoY",
    "Fed Total Balance Sheet", "Reserve Balances at Fed Banks",
    "WTI Crude Front", "Gold",
]
HERO_AVAILABLE = [h for h in HERO if h in slim]

# === CURATED AGGREGATE PANELS ===
# Each panel groups thematically-coherent indicators that share a scale (or use dual-axis).
# Selection rule: only include indicators that genuinely tell a story together.
# Avoid: dumping every related ticker. Avoid: mixing scale-incompatible series unless
# we explicitly plan dual-axis.
PANELS = [
    {
        "id": "gdp_pulse",
        "name": "GDP Growth Pulse",
        "theme": "Growth",
        "description": "Quarterly headline GDP alongside real-time growth nowcasts. Look for nowcast/print convergence near release; large nowcast→print gap = data surprise risk.",
        "how_to_read": "All series in % YoY-equivalent terms. GDPNow and WEI run higher-frequency than reported GDP — track their drift between print dates.",
        "indicators": ["Real GDP YoY", "Atlanta Fed GDPNow", "NY Fed Weekly Economic Index", "Chicago Fed National Activity"],
        "axis": "single", "unit_label": "% / Index",
    },
    {
        "id": "inflation_headline",
        "name": "Headline Inflation Stack",
        "theme": "Inflation",
        "description": "Headline and core CPI/PCE — the four numbers Fed reaction function actually weights. Core PCE is the official 2% target.",
        "how_to_read": "All in % YoY. Core PCE is the lowest-volatility — closely watched. Headline-core gap shows energy/food contribution.",
        "indicators": ["CPI YoY", "Core CPI YoY", "PCE Deflator YoY", "Core PCE YoY"],
        "axis": "single", "unit_label": "% YoY",
    },
    {
        "id": "cpi_decomposition",
        "name": "CPI: Headline, Core & Underlying",
        "theme": "Inflation",
        "description": "Headline CPI alongside core (ex food/energy) and two robust measures of underlying CPI trend: 16% Trimmed Mean CPI (outlier-filtered) and Atlanta Sticky CPI (services-anchored, slow-changing items). NOTE 1: BLS-direct subcomponents (Shelter YoY, OER YoY, Core Goods YoY, Core Services YoY, Primary Rent YoY) are listed as Unresolved in the v7 ticker dashboard — they will be added to this panel once Bloomberg tickers are verified on the Terminal. NOTE 2: Cleveland Median CPI YoY (ticker CLEVMCPI) is excluded because that ticker returns the median CPI INDEX LEVEL (~344-369), not the YoY% — needs a separate ticker resolved on Terminal for YoY representation.",
        "how_to_read": "All four lines in % YoY. Headline-Core gap = food + energy contribution. Sticky CPI > Core = services-driven persistence (the post-2022 pattern). Trimmed CPI converging below Core = right tail of price distribution cooling (broad disinflation).",
        "indicators": ["CPI YoY", "Core CPI YoY", "Cleveland 16% Trimmed CPI YoY", "Atlanta Sticky CPI 12mo"],
        "axis": "single", "unit_label": "% YoY",
    },
    {
        "id": "inflation_breadth",
        "name": "Inflation Breadth (Trimmed/Median)",
        "theme": "Inflation",
        "description": "Robust central-tendency measures filter outliers. Often diverge from headline at turning points — useful for identifying whether disinflation is broad or narrow.",
        "how_to_read": "All in % YoY. Watch convergence/divergence vs headline core CPI.",
        "indicators": ["Cleveland Median CPI YoY", "Cleveland 16% Trimmed CPI YoY", "Atlanta Sticky CPI 12mo", "Cleveland Median PCE", "Core CPI YoY"],
        "axis": "single", "unit_label": "% YoY",
    },
    {
        "id": "inflation_nowcast",
        "name": "Cleveland Inflation Nowcasts",
        "theme": "Inflation",
        "description": "Daily-updated forecasts for the next CPI/PCE prints. Track these into release dates for surprise positioning.",
        "how_to_read": "All in % YoY. Current = current-month nowcast; Forward = next-month.",
        "indicators": ["Cleveland CPI Nowcast Current", "Cleveland Core CPI Nowcast Current", "Cleveland PCE Nowcast Current", "Cleveland Core PCE Nowcast Current"],
        "axis": "single", "unit_label": "% YoY",
    },
    {
        "id": "inflation_expectations",
        "name": "Inflation Expectations Term Structure",
        "theme": "Inflation",
        "description": "Market-implied (TIPS breakevens, swaps, 5Y5Y) and survey expectations. Anchored = Fed credibility intact; un-anchoring is the single biggest tail risk.",
        "how_to_read": "All in %. 5Y5Y is the cleanest long-run gauge. Watch divergence between market and household survey measures.",
        "indicators": ["5Y TIPS Breakeven", "10Y TIPS Breakeven", "30Y TIPS Breakeven", "Fed 5Y5Y Forward Inflation Exp", "5Y5Y Forward Inflation Swap"],
        "axis": "single", "unit_label": "%",
    },
    {
        "id": "inflation_survey",
        "name": "Survey Inflation Expectations",
        "theme": "Inflation",
        "description": "Household and consumer expectations. Less anchored than market measures since 2022. Fed cites these but weights cautiously.",
        "how_to_read": "% expected inflation. Michigan tends to be more reactive than NY Fed SCE.",
        "indicators": ["Michigan 1Y Inflation Exp", "Michigan 5-10Y Inflation Exp", "NY Fed SCE 1Y Inflation Exp", "NY Fed SCE 3Y Inflation Exp"],
        "axis": "single", "unit_label": "%",
    },
    {
        "id": "labor_unemployment",
        "name": "Unemployment & Labor Slack",
        "theme": "Labor",
        "description": "Headline U-3 alongside broader U-6 underemployment and emp-pop ratio. Sahm Rule: 0.5pp rise in 3-mo MA U-3 from 12-mo low has historically signaled recession.",
        "how_to_read": "U-3 and U-6 are %; emp-pop ratio is also % but inverse direction. Watch the wedge U-6 minus U-3.",
        "indicators": ["Unemployment Rate (U-3)", "U-6 Underemployment Rate", "Employment-Population Ratio"],
        "axis": "single", "unit_label": "%",
    },
    {
        "id": "labor_payrolls",
        "name": "Payroll Momentum",
        "theme": "Labor",
        "description": "NFP change and ADP private payrolls. ADP isn't a great NFP predictor but converges over 3-mo windows.",
        "how_to_read": "Thousands per month. 200k+ = strong, <100k = cooling, <50k = stalling.",
        "indicators": ["Nonfarm Payrolls Change", "Private Payrolls Change", "ADP Employment Change"],
        "axis": "single", "unit_label": "k jobs / month",
    },
    {
        "id": "labor_claims",
        "name": "Jobless Claims",
        "theme": "Labor",
        "description": "Highest-frequency labor signal. Initial claims = layoff pulse; continuing claims = hiring/re-employment rate.",
        "how_to_read": "Initial claims are noisy weekly — the 4-wk MA is the trend. Continuing claims trend up = labor market loosening.",
        "indicators": ["Initial Jobless Claims", "Initial Claims 4-Wk MA", "Continuing Claims"],
        "axis": "dual", "unit_label": "Thousands (continuing on right)",
    },
    {
        "id": "labor_wages",
        "name": "Wage Growth",
        "theme": "Labor",
        "description": "AHE (timeliest), ECI (Fed's preferred — quarterly), Atlanta WGT (composition-controlled). Convergence to ~3.5% = consistent with 2% inflation + productivity.",
        "how_to_read": "All in % YoY. Atlanta WGT typically runs hottest because median methodology.",
        "indicators": ["Avg Hourly Earnings YoY", "Employment Cost Index YoY", "Atlanta Wage Growth Tracker"],
        "axis": "single", "unit_label": "% YoY",
    },
    {
        "id": "pmi_panel",
        "name": "PMIs (Mfg vs Services)",
        "theme": "Surveys",
        "description": "ISM and S&P/Markit PMIs. 50 = neutral. Mfg-services divergence is common and informative.",
        "how_to_read": "Diffusion index, 50 = neutral. Below 45 historically recessionary.",
        "indicators": ["ISM Manufacturing PMI", "ISM Services PMI", "Markit Manufacturing PMI", "Markit Services PMI"],
        "axis": "single", "unit_label": "Index (50=neutral)",
    },
    {
        "id": "ism_internals",
        "name": "ISM Manufacturing Internals",
        "theme": "Surveys",
        "description": "Headline alongside its most informative components: New Orders (most leading), Prices Paid (inflation pipeline), Employment.",
        "how_to_read": "All diffusion indices, 50=neutral. New Orders typically leads headline.",
        "indicators": ["ISM Manufacturing PMI", "ISM Mfg New Orders", "ISM Mfg Prices Paid", "ISM Mfg Employment"],
        "axis": "single", "unit_label": "Index (50=neutral)",
    },
    {
        "id": "regional_fed",
        "name": "Regional Fed Manufacturing Surveys",
        "theme": "Surveys",
        "description": "Empire/Philly/Richmond/Dallas. Released early in the month — useful for nowcasting ISM Mfg headline.",
        "how_to_read": "Diffusion indices, but each Bank uses different scaling — compare YoY changes more than levels.",
        "indicators": ["Empire State Manufacturing", "Philly Fed Manufacturing", "Richmond Fed Manufacturing", "Dallas Fed Manufacturing"],
        "axis": "single", "unit_label": "Index (varies by Bank)",
    },
    {
        "id": "yield_curve",
        "name": "Treasury Yield Curve",
        "theme": "Rates",
        "description": "Key tenors: 3M, 2Y, 5Y, 10Y, 30Y. Slope (10s-2s) and shape changes drive duration positioning.",
        "how_to_read": "All in %. Bear-steepener = long end up faster (growth/inflation). Bull-flattener = front end down (cuts pricing).",
        "indicators": ["3M T-Bill", "2Y Treasury", "5Y Treasury", "10Y Treasury", "30Y Treasury"],
        "axis": "single", "unit_label": "%",
    },
    {
        "id": "real_vs_nominal",
        "name": "Real vs Nominal Yields",
        "theme": "Rates",
        "description": "10Y nominal decomposes into 10Y real (TIPS) + 10Y breakeven inflation. Decomposition shows whether moves are growth/policy or inflation-driven.",
        "how_to_read": "All %. Nominal = Real + Breakeven (approximately). Watch which leg drives nominal moves.",
        "indicators": ["10Y Treasury", "10Y TIPS Real", "10Y TIPS Breakeven"],
        "axis": "single", "unit_label": "%",
    },
    {
        "id": "policy_rates",
        "name": "Policy & Reference Rates",
        "theme": "Rates",
        "description": "Fed Funds target alongside the actual short rates: EFFR, IORB, SOFR. Spreads to admin rates indicate plumbing stress.",
        "how_to_read": "All %. Watch SOFR-EFFR and IORB-EFFR spreads — they widen when reserves get scarce.",
        "indicators": ["Fed Funds Target Mid", "EFFR", "IORB", "SOFR"],
        "axis": "single", "unit_label": "%",
    },
    {
        "id": "fed_bs_liquidity",
        "name": "Fed BS Liquidity Mechanics",
        "theme": "Fed_BS",
        "description": "The four lines that drive bank-system reserves: total BS, reserves, ON RRP, TGA. Reserves = Total BS − Currency − ON RRP − TGA − other.",
        "how_to_read": "All USD millions, weekly H.4.1. ON RRP near zero = QT pressure starts hitting reserves directly.",
        "indicators": ["Fed Total Balance Sheet", "Reserve Balances at Fed Banks", "Reverse Repurchase Agreements Total", "US Treasury General Account (TGA Weekly)"],
        "axis": "single", "unit_label": "USD m",
    },
    {
        "id": "soma_composition",
        "name": "SOMA Holdings — Composition",
        "theme": "Fed_BS",
        "description": "Daily SOMA holdings detail. Tracks QT pace and sector allocation (bills vs notes/bonds, MBS runoff).",
        "how_to_read": "All USD millions. MBS slope = passive runoff (capped); Treasuries slope = caps + reinvestment.",
        "indicators": ["SOMA Total", "SOMA Treasury Bills", "SOMA Treasury Bonds and Notes", "SOMA MBS", "SOMA TIPS"],
        "axis": "single", "unit_label": "USD m",
    },
    {
        "id": "credit_spreads",
        "name": "Credit Risk Premium",
        "theme": "Credit",
        "description": "IG and HY spreads — most cyclically sensitive credit gauge.",
        "how_to_read": "Both in bps. HY OAS <300 = euphoria, ~500 = normal, 800+ = recession-like. IG <100 = tight.",
        "indicators": ["Bloomberg US IG OAS", "Bloomberg US HY OAS"],
        "axis": "dual", "unit_label": "bps (HY on right)",
    },
    {
        "id": "fci_panel",
        "name": "Financial Conditions",
        "theme": "Credit",
        "description": "Composite FCIs from three sources: Chicago Fed (NFCI/ANFCI), GS, Bloomberg. Different methodologies — agreement strengthens signal.",
        "how_to_read": "Different scales by source. Z-scores around 0 for Chicago Fed; index for GS/Bloomberg. All trend the same direction in stress.",
        "indicators": ["Chicago Fed NFCI", "Chicago Fed ANFCI", "GS US FCI", "Bloomberg US FCI"],
        "axis": "dual", "unit_label": "Multi-axis (see legend)",
    },
    {
        "id": "vol_panel",
        "name": "Implied Volatility (Equity & Rates)",
        "theme": "Markets",
        "description": "VIX (S&P 500) alongside MOVE (Treasuries) and VVIX (vol-of-vol). Cross-asset vol dispersion is informative.",
        "how_to_read": "VIX in vol points (~15 normal); MOVE in bps annualized (different scale, right axis).",
        "indicators": ["VIX", "MOVE", "VVIX"],
        "axis": "dual", "unit_label": "Multi-axis (MOVE on right)",
    },
    {
        "id": "vix_term",
        "name": "VIX Term Structure",
        "theme": "Markets",
        "description": "VIX (30D), VIX9D, VIX3M, VIX6M. Slope = vol risk premium.",
        "how_to_read": "All vol points. Backwardation (front high) = stress; steep contango = complacency.",
        "indicators": ["VIX", "VIX 9-day", "VIX 3-month", "VIX 6-month"],
        "axis": "single", "unit_label": "Vol points",
    },
    {
        "id": "usd_panel",
        "name": "USD Trade-Weighted",
        "theme": "Markets",
        "description": "DXY (EUR-heavy), BBDXY (broader), Real Broad Dollar. Real Broad is the cleanest fundamentals measure.",
        "how_to_read": "Different index bases — compare YoY/% changes rather than levels.",
        "indicators": ["DXY", "BBDXY", "Fed Real Broad Dollar"],
        "axis": "dual", "unit_label": "Multi-axis (see legend)",
    },
    {
        "id": "commodities_panel",
        "name": "Commodities Complex",
        "theme": "Commodities",
        "description": "Broad indices (BCOM, GSCI) and key cyclical commodities. Useful for inflation pipeline + cycle reads.",
        "how_to_read": "Index/price scales differ. WTI on right axis as $/bbl.",
        "indicators": ["Bloomberg Commodity Index", "S&P GSCI", "WTI Crude Front", "Gold"],
        "axis": "dual", "unit_label": "Multi-axis",
    },
    {
        "id": "housing_panel",
        "name": "Housing Activity",
        "theme": "Housing",
        "description": "Starts, permits, existing home sales. Permits leads starts; existing sales captures 85%+ of transactions.",
        "how_to_read": "Starts/permits in thousands SAAR; existing sales in millions SAAR — dual axis.",
        "indicators": ["Housing Starts", "Building Permits", "Existing Home Sales", "NAHB Housing Market Index"],
        "axis": "dual", "unit_label": "Multi-axis",
    },
    {
        "id": "consumer_sentiment",
        "name": "Consumer Sentiment",
        "theme": "Consumer",
        "description": "Conference Board (labor-tilted) vs Michigan (inflation-tilted). Common divergence based on which factor dominates.",
        "how_to_read": "Different index bases (CB 1985=100, Michigan 1966Q1=100). Look at z-scores or YoY changes.",
        "indicators": ["Conf Board Consumer Confidence", "Michigan Consumer Sentiment", "Michigan Current Conditions", "Michigan Expectations"],
        "axis": "dual", "unit_label": "Multi-axis",
    },
    {
        "id": "leading_indicators",
        "name": "Leading Indicators",
        "theme": "Surveys",
        "description": "Conference Board LEI and OECD CLI — composite leading indices designed to anticipate cyclical turning points.",
        "how_to_read": "LEI YoY <-4% has called every US recession since 1959. OECD scaled to 100=trend.",
        "indicators": ["Conf Board LEI YoY", "OECD Leading Indicator", "OECD Leading Indicator 12mo"],
        "axis": "dual", "unit_label": "Multi-axis",
    },
    {
        "id": "surprise_panel",
        "name": "Data Surprise Indices",
        "theme": "Surveys",
        "description": "Citi vs Bloomberg US economic surprise — actual vs consensus, decay-weighted. Mean-reverting.",
        "how_to_read": "Index, 0 = consensus on track. Above 0 = data beating; below = missing.",
        "indicators": ["Citi US Economic Surprise", "Bloomberg US Economic Surprise"],
        "axis": "single", "unit_label": "Index",
    },
    {
        "id": "sloos_business",
        "name": "SLOOS — C&I Lending Standards",
        "theme": "Credit",
        "description": "Senior Loan Officer Survey: net % of banks reporting tighter standards / stronger demand for C&I loans.",
        "how_to_read": "Net %. Positive = tightening (negative for credit); negative = easing.",
        "indicators": ["Tighter C&I Large", "Tighter C&I Small", "Stronger C&I Demand Large", "Stronger C&I Demand Small"],
        "axis": "single", "unit_label": "Net %",
    },
    {
        "id": "sentiment_extremes",
        "name": "Investor Sentiment Extremes",
        "theme": "Markets",
        "description": "AAII bullishness, NAAIM exposure, CBOE put/call. Contrarian indicators at extremes.",
        "how_to_read": "Different units — watch z-scores or extreme readings, not absolute levels.",
        "indicators": ["AAII Bullish %", "AAII Bearish %", "NAAIM Exposure Index", "CBOE Equity Put/Call"],
        "axis": "dual", "unit_label": "Multi-axis",
    },
    {
        "id": "money_aggregates",
        "name": "Money Aggregates",
        "theme": "Fed_BS",
        "description": "Monetary base, M1, M2 growth. Less central post-QE but useful for liquidity narratives and Q4-2021 inflation explainers.",
        "how_to_read": "All % YoY. M2 YoY is most cited.",
        "indicators": ["Monetary Base YoY", "M1 Money Supply YoY", "M2 Money Supply YoY"],
        "axis": "single", "unit_label": "% YoY",
    },
    {
        "id": "external_balance",
        "name": "External Balance",
        "theme": "External",
        "description": "Goods trade balance, services balance, current account. USD strength drives services surplus & capital inflows.",
        "how_to_read": "Negative = deficit; magnitudes differ (services smaller). Use right axis if needed.",
        "indicators": ["Trade Balance Total", "Services Trade Balance", "Current Account"],
        "axis": "dual", "unit_label": "USD bn",
    },
]

# Filter to panels whose indicators all exist in dataset
PANELS_FILTERED = []
for p in PANELS:
    avail = [i for i in p["indicators"] if i in slim]
    if len(avail) >= 2:  # need at least 2 to be a useful panel
        p2 = dict(p)
        p2["indicators"] = avail
        PANELS_FILTERED.append(p2)
print(f"Curated {len(PANELS_FILTERED)} panels (from {len(PANELS)} defined; some indicators may not be in data)")

# 5. Theme order + labels (for navigation)
THEME_ORDER = ["Growth", "Surveys", "Labor", "Inflation", "Consumer", "Housing", "Rates", "Fed_BS", "Credit", "Markets", "Fiscal", "External", "Commodities"]
THEME_LABEL = {
    "Growth": "Growth & Activity", "Surveys": "Surveys", "Labor": "Labor",
    "Inflation": "Inflation", "Consumer": "Consumer", "Housing": "Housing",
    "Rates": "Rates & Policy", "Fed_BS": "Fed Balance Sheet",
    "Markets": "Markets", "Credit": "Credit & FCI",
    "Fiscal": "Fiscal", "External": "External", "Commodities": "Commodities",
}

# Theme → ordered category list (preserve catalog ordering 01_..44_).
# Each entry is (catId, label, desc, tier) where tier ∈ {"", "detail"}.
# "detail" = deep hierarchy / by-industry / by-region breakouts that should sit in a
# collapsed secondary subgroup so the ~headline categories surface first.
# Data-driven: a category is "detail" iff its id is in DETAIL_CATS (explicit ids — the
# hierarchy + by-dimension cats) OR its label contains a by-dimension marker. Both render
# sites read this single flag; no per-site hand lists.
DETAIL_CATS = {
    # Labor: NFP hierarchy + by-industry/region/demographic breakouts
    "54_NFP_Hierarchy_Values", "55_Employment_Ratio_Education",
    "61_Challenger_Job_Layoffs_Industry", "62_JOLTS_Quits_Industry",
    "63_JOLTS_Job_Vacancies_Industry", "64_JOLTS_Hires_Industry",
    "65_Labor_Force_Participation_Age_Gender", "66_Challenger_Job_Layoffs_Region",
    # Inflation: CPI hierarchy values + weights
    "46_CPI_Hierarchy_Values", "47_CPI_Hierarchy_Weights",
}
def _cat_tier(catId, label):
    if catId in DETAIL_CATS:
        return "detail"
    l = label.lower()
    if "hierarchy" in l or "by industry" in l or "by region" in l or " industry" in l:
        return "detail"
    return ""

themes_categories = {}
for th in THEME_ORDER:
    cats = [k for k, v in catalog["categories"].items() if v["theme"] == th]
    cats.sort()
    themes_categories[th] = [
        (c, catalog["categories"][c]["label"], catalog["categories"][c].get("description",""),
         _cat_tier(c, catalog["categories"][c]["label"]))
        for c in cats
    ]

# 6. "Latest prints" feed: indicators ranked by most-recent observation
prints = []
for ind, v in slim.items():
    prints.append({"i": ind, "d": v["ld"], "v": v["lv"], "u": v["u"], "th": v["th"]})
prints.sort(key=lambda x: x["d"], reverse=True)
prints = prints[:60]

# 7. Compose data payload
# === PCE HIERARCHY TREE ===
# Build a unified tree from cats 48 (Core PCE MoM), 49 (Core PCE MoM Weights),
# 50 (Core PCE YoY), 51 (Core PCE YoY Weights), 52 (PCE MoM), 53 (PCE YoY).
# Each node has up to 6 ticker slots: core_mom, core_yoy, full_mom, full_yoy,
# core_mom_w, core_yoy_w. Leaves omit slots they don't have.
_PCE_CAT_MAP = {
    "48_CorePCE_MoM_Values":   ("core", "mom"),
    "50_CorePCE_YoY_Values":   ("core", "yoy"),
    "52_PCE_MoM_Values":       ("full", "mom"),
    "53_PCE_YoY_Values":       ("full", "yoy"),
    "49_CorePCE_MoM_Weights":  ("core", "mom_w"),
    "51_CorePCE_YoY_Weights":  ("core", "yoy_w"),
}

def build_pce_tree(df):
    root = {"n": "PCE", "c": {}, "t": {}, "i": {}}
    pce_cat_df = df[df["category"].isin(_PCE_CAT_MAP.keys())]
    for _, row in pce_cat_df.iterrows():
        variant, kind = _PCE_CAT_MAP[row["category"]]
        slot = f"{variant}_{kind}"
        name = row["indicator"]
        # Strip "(weight)" suffix if it's a weight series
        if kind.endswith("_w") and name.endswith(" (weight)"):
            name = name[:-len(" (weight)")]
        # Split path; drop the variant root token
        parts = name.split(" > ")
        if parts and parts[0] in ("Personal Consumption Expenditures", "Core PCE"):
            parts = parts[1:]
        # Special-case 'Supercore PCE' which is standalone (no path)
        if not parts:
            # name was just "Personal Consumption Expenditures" or "Core PCE" — root
            root["t"][slot] = row["ticker"]
            root["i"][slot] = row["indicator"]
            continue
        # Walk into tree
        node = root
        for p in parts:
            if p not in node["c"]:
                node["c"][p] = {"n": p, "c": {}, "t": {}, "i": {}}
            node = node["c"][p]
        node["t"][slot] = row["ticker"]
        node["i"][slot] = row["indicator"]
    return root

def tree_to_array(node, path=None):
    """Convert dict-of-children to ordered array; assign stable path id."""
    path = path or []
    out = {"n": node["n"], "p": "/".join(path), "t": node["t"], "i": node["i"]}
    if node["c"]:
        # Sort children: alphabetical, but keep certain semantically-important roots first
        priority = {"Services": 0, "Durable Goods": 1, "Nondurable Goods": 2,
                    "Goods": 3, "Nonprofits": 9}
        keys = sorted(node["c"].keys(), key=lambda k: (priority.get(k, 5), k.lower()))
        out["c"] = [tree_to_array(node["c"][k], path + [k]) for k in keys]
    else:
        out["c"] = []
    return out

_pce_root_dict = build_pce_tree(df)

# === Inject headline values into the root node ===
# The cat 48-53 hierarchy doesn't include the aggregate (root) values; those live
# in cat 18 (CPI/PPI/PCE) and cat 21 (Consumer_Income). Map them in.
HEADLINE_MAP = {
    # variant_kind: indicator_name -> ticker (must exist in df)
    "core_mom": ("Core PCE MoM", "PCE CRCH Index"),
    "core_yoy": ("Core PCE YoY", "PCE CYOY Index"),
    # PCE Deflator: only YoY available verified; MoM ticker not yet resolved.
    "full_yoy": ("PCE Deflator YoY", "PCE DEFY Index"),
    # full_mom: leave unset — root will be disabled in Full+MoM mode and a hint surfaces in UI.
}
for slot, (ind_name, ticker) in HEADLINE_MAP.items():
    if ticker in series:  # series now keyed by ticker
        _pce_root_dict["t"][slot] = ticker
        _pce_root_dict["i"][slot] = ind_name

pce_tree = tree_to_array(_pce_root_dict)
# Diagnostic: count nodes
def count_nodes(n):
    return 1 + sum(count_nodes(c) for c in n.get("c", []))
print(f"PCE tree: {count_nodes(pce_tree)} nodes")
print(f"PCE root tickers: {pce_tree['t']}")

# Standalone Supercore PCE (not in tree, surface as headline)
SUPERCORE_PCE = {
    "mom": "Supercore PCE",
    "yoy": "Supercore PCE",
}

# === THEME WORKSPACE REGISTRY ===
# 8 theme dashboards mapped 1:1 to the knowledge-base files in context/07*.md.
# Each theme has: default visible indicators, full available list, description,
# cross-theme links, and macro-narrative references.
THEME_REGISTRY = [
    {
        "id": "real_activity", "name": "Real Activity", "kb": "07a_real_activity.md",
        "summary": "GDP, GDI, IP, capacity util, orders, retail. The cyclical heartbeat — what NBER uses for recession dating. Watch GDP/GDI wedge for turning points.",
        "defaults": ["Real GDP YoY", "Atlanta Fed GDPNow", "Industrial Production YoY", "Retail Sales YoY"],
        "available": ["Real GDP QoQ SAAR", "Real GDP YoY", "GDI QoQ", "Personal Consumption QoQ", "Private Investment QoQ", "Industrial Production YoY", "Industrial Production MoM", "Manufacturing Production MoM", "Capacity Utilization Total", "Manufacturing Capacity Utilization", "Factory Orders MoM", "Durable Goods Orders MoM", "Durable Goods ex Transport MoM", "Retail Sales MoM", "Retail Sales YoY", "Retail Sales ex Autos YoY", "Total Vehicle Sales", "Atlanta Fed GDPNow", "NY Fed Weekly Economic Index"],
        "related": ["surveys", "labor", "inflation"],
        "narratives": ["Recession Pricing", "Reflation Combo", "GDP/GDI Wedge"],
    },
    {
        "id": "surveys", "name": "Surveys & Nowcasts", "kb": "07b_surveys_nowcasts.md",
        "summary": "Diffusion-index business surveys (ISM, Markit, regional Fed, NFIB), composite leading indicators (LEI, OECD), real-time nowcasts (GDPNow, WEI), and surprise indices. Most-watched leading cyclical signals.",
        "defaults": ["ISM Manufacturing PMI", "ISM Services PMI", "Conf Board LEI YoY", "Citi US Economic Surprise"],
        "available": ["ISM Manufacturing PMI", "ISM Mfg New Orders", "ISM Mfg Prices Paid", "ISM Mfg Employment", "ISM Services PMI", "Markit Manufacturing PMI", "Markit Services PMI", "Markit Composite PMI", "Chicago PMI (MNI)", "NFIB Small Business Optimism", "Empire State Manufacturing", "Philly Fed Manufacturing", "Richmond Fed Manufacturing", "Dallas Fed Manufacturing", "Conf Board LEI YoY", "Conf Board LEI MoM", "OECD Leading Indicator", "OECD Leading Indicator 12mo", "Atlanta Fed GDPNow", "NY Fed Weekly Economic Index", "Citi US Economic Surprise", "Bloomberg US Economic Surprise", "Chicago Fed National Activity", "CFNAI 3-mo MA", "SF Fed Labor Market Stress", "SF Fed Proxy Funds Rate"],
        "related": ["real_activity", "labor", "inflation"],
        "narratives": ["LEI Recession Signal", "ISM Mfg-Services Divergence", "Surprise Index Mean-Reversion"],
    },
    {
        "id": "labor", "name": "Labor Market", "kb": "07c_labor.md",
        "summary": "BLS CES/CPS/JOLTS, DOL UI claims, ADP, Atlanta WGT. Triangulation across surveys is mandatory: NFP vs ADP, JOLTS V/U, claims for high-frequency, ECI for clean wages.",
        "defaults": ["Nonfarm Payrolls Change", "Unemployment Rate (U-3)", "Initial Jobless Claims", "Avg Hourly Earnings YoY"],
        "available": ["Nonfarm Payrolls Change", "Private Payrolls Change", "Manufacturing Payrolls Change", "ADP Employment Change", "Unemployment Rate (U-3)", "U-6 Underemployment Rate", "Employment-Population Ratio", "JOLTS Total Job Openings", "JOLTS Job Openings YoY", "JOLTS Hires YoY", "JOLTS Separations YoY", "Initial Jobless Claims", "Initial Claims 4-Wk MA", "Continuing Claims", "Challenger Job Cuts YoY", "Avg Hourly Earnings YoY", "Avg Hourly Earnings MoM", "Employment Cost Index YoY", "Atlanta Wage Growth Tracker", "NF Productivity QoQ", "Unit Labor Costs QoQ", "Aggregate Hours Index", "Avg Weekly Hours NF Private", "NF Payroll Diffusion Index"],
        "related": ["real_activity", "inflation", "surveys"],
        "narratives": ["Wage-Price Spiral", "Recession Sequencing", "Sahm Rule Trip"],
    },
    {
        "id": "inflation", "name": "Inflation", "kb": "07d_inflation.md",
        "summary": "CPI/PCE methodology and the 30-50bp wedge driven by shelter weights and healthcare scope. Core PCE = Fed target. Cleveland nowcasts forecast the next print. 5Y5Y BE is the long-run anchor.",
        "defaults": ["CPI YoY", "Core CPI YoY", "Core PCE YoY", "Cleveland Core CPI Nowcast Current"],
        "available": ["CPI YoY", "CPI MoM", "Core CPI YoY", "Core CPI MoM", "PPI Final Demand YoY", "PPI ex F&E YoY", "PCE Deflator YoY", "Core PCE YoY", "Core PCE MoM", "Cleveland CPI Nowcast Current", "Cleveland Core CPI Nowcast Current", "Cleveland PCE Nowcast Current", "Cleveland Core PCE Nowcast Current", "Cleveland 16% Trimmed CPI YoY", "Atlanta Sticky CPI 12mo", "Dallas Trimmed Mean PCE", "5Y TIPS Breakeven", "10Y TIPS Breakeven", "30Y TIPS Breakeven", "Fed 5Y5Y Forward Inflation Exp", "5Y5Y Forward Inflation Swap", "Michigan 1Y Inflation Exp", "Michigan 5-10Y Inflation Exp", "NY Fed SCE 1Y Inflation Exp", "Import Price Index YoY"],
        "related": ["labor", "markets", "pce_hierarchy", "real_activity"],
        "narratives": ["Wage-Price Spiral", "Disinflation Broadening", "Expectations Un-Anchoring", "Shelter Mean Reversion"],
    },
    {
        "id": "pce_hierarchy", "name": "PCE Hierarchy", "kb": "07e_pce_hierarchy.md",
        "summary": "Headline PCE deflator + Core PCE + Supercore + Cleveland nowcasts. For granular subcomponent decomposition (Health Care, Housing Services, etc.) use the dedicated PCE Dashboard.",
        "defaults": ["Core PCE YoY", "Core PCE MoM", "PCE Deflator YoY", "Cleveland Core PCE Nowcast Current"],
        "available": ["PCE Deflator YoY", "Core PCE YoY", "Core PCE MoM", "Core PCE Deflator QoQ SAAR", "Cleveland PCE Nowcast Current", "Cleveland Core PCE Nowcast Current", "Cleveland PCE Nowcast Forward", "Cleveland Core PCE Nowcast Forward", "Cleveland Median PCE", "Dallas Trimmed Mean PCE", "Personal Spending MoM", "Personal Expenditure YoY", "Personal Income MoM", "Personal Income YoY", "Personal Saving Rate", "Real Personal Income ex Transfers"],
        "related": ["inflation", "labor", "real_activity"],
        "narratives": ["Supercore Watching (Powell Brookings 2022)", "Wage-Price Spiral", "Healthcare Scope vs CPI"],
    },
    {
        "id": "monetary", "name": "Monetary Policy", "kb": "07f_monetary.md",
        "summary": "Policy rates (FFR, IORB, ON RRP), money market (EFFR, SOFR), Fed BS (H.4.1) — total, reserves, RRP, TGA. SOMA composition. Money aggregates. The plumbing of the dollar system.",
        "defaults": ["Fed Funds Target Mid", "EFFR", "Reserve Balances at Fed Banks", "US Treasury General Account (TGA Weekly)"],
        "available": ["Fed Funds Target Upper", "Fed Funds Target Mid", "EFFR", "IORB", "SOFR", "30-day Avg SOFR", "90-day Avg SOFR", "Fed Total Balance Sheet", "Reserve Balances at Fed Banks", "Reverse Repurchase Agreements Total", "US Treasury General Account (TGA Weekly)", "TGA Daily", "Currency in Circulation", "BTFP", "Loans (Discount Window total)", "Primary Credit", "SOMA Total", "SOMA Treasury Bonds and Notes", "SOMA Treasury Bills", "SOMA MBS", "Monetary Base USD bn", "Monetary Base YoY", "M1 Money Supply YoY", "M2 Money Supply YoY"],
        "related": ["markets", "inflation", "real_activity"],
        "narratives": ["QT in Ample-Reserves", "ON RRP → Reserves Transition", "Debt Ceiling Liquidity", "Bank Stress Signals"],
    },
    {
        "id": "markets", "name": "Markets", "kb": "07g_markets.md",
        "summary": "Treasury curve (level/slope/curvature, ACM term premium), TIPS reals, vol (VIX/MOVE/VVIX), USD (DXY/BBDXY/REER), credit (IG/HY OAS), composite FCIs (NFCI/GS/Bloomberg). Where macro views are priced.",
        "defaults": ["10Y Treasury", "2Y Treasury", "VIX", "Bloomberg US HY OAS"],
        "available": ["3M T-Bill", "1Y Treasury", "2Y Treasury", "5Y Treasury", "10Y Treasury", "30Y Treasury", "5Y TIPS Real", "10Y TIPS Real", "30Y TIPS Real", "VIX", "VVIX", "MOVE", "VIX 9-day", "VIX 3-month", "DXY", "BBDXY", "Fed Real Broad Dollar", "Real REER AFE", "Real REER EME", "Bloomberg US IG OAS", "Bloomberg US HY OAS", "Chicago Fed NFCI", "Chicago Fed ANFCI", "NFCI Risk", "NFCI Credit", "NFCI Leverage", "GS US FCI", "Bloomberg US FCI"],
        "related": ["monetary", "inflation", "auxiliary"],
        "narratives": ["Recession Pricing", "Reflation", "Stagflation", "Fed Pivot Pricing", "Calm-Risk Regime"],
    },
    {
        "id": "auxiliary", "name": "Housing/Fiscal/Commodities/Sentiment", "kb": "07h_auxiliary.md",
        "summary": "Housing (most rate-sensitive sector), fiscal/debt, external/TIC, commodities (energy → CPI energy passthrough), investor sentiment (contrarian filter at extremes).",
        "defaults": ["Housing Starts", "WTI Crude Front", "AAII Bullish %", "Bloomberg Commodity Index"],
        "available": ["Housing Starts", "Building Permits", "New Home Sales", "Existing Home Sales", "Pending Home Sales MoM", "NAHB Housing Market Index", "MBA Mortgage Applications WoW", "Personal Income MoM", "Personal Spending MoM", "Personal Saving Rate", "Conf Board Consumer Confidence", "Michigan Consumer Sentiment", "Michigan Expectations", "Trade Balance Total", "Current Account", "Total Public Debt", "Total Marketable Debt", "WTI Crude Front", "Brent Crude Front", "Henry Hub Natural Gas", "Gold", "Silver", "Bloomberg Commodity Index", "S&P GSCI", "AAII Bullish %", "AAII Bearish %", "NAAIM Exposure Index", "CBOE Equity Put/Call", "CBOE Total Put/Call", "CBOE SKEW"],
        "related": ["markets", "real_activity", "inflation"],
        "narratives": ["Housing-Rates Loop", "Commodity-Inflation-Rates", "Sentiment Capitulation"],
    },
]

# Filter availability against actual data + warn on missing
for theme in THEME_REGISTRY:
    available_present = [n for n in theme["available"] if n in catalog["indicators"]]
    defaults_present = [n for n in theme["defaults"] if n in catalog["indicators"]]
    missing = [n for n in theme["available"] if n not in catalog["indicators"]]
    if missing:
        print(f"  Workspace theme '{theme['id']}': {len(missing)} indicators missing from catalog: {missing[:5]}{'...' if len(missing)>5 else ''}")
    theme["available"] = available_present
    theme["defaults"] = [n for n in defaults_present if n in available_present]

print(f"Workspace: {len(THEME_REGISTRY)} themes registered, "
      f"{sum(len(t['available']) for t in THEME_REGISTRY)} total available indicator slots")

# === MATT'S VIEW: synthetic transformations + chart registry ===
#
# Matt's View needs rolling N-month differences (NFP) and N-month annualized
# percent change (Aggregate Hours) that aren't expressible with the Workspace
# MA/lag/magnify primitives. We pre-compute them as synthetic series and inject
# them into the standard indicators + series catalog.

def _series_to_df(tkr):
    """Pull a ticker's series out of the in-memory `series` dict as a pandas Series."""
    if tkr not in series:
        return None
    s = pd.Series(
        [v for _, v in series[tkr]],
        index=pd.to_datetime([d for d, _ in series[tkr]]),
    ).sort_index()
    return s

def _inject_synthetic(name, ticker, dates_values, units, freq, source, description, category_label, theme):
    """Add a synthetic indicator into both `slim` (indicators) and `series`."""
    if not dates_values:
        return
    # Drop NaN/inf entries; this is what xbbg returns for periods with insufficient history
    cleaned = [(d, float(v)) for d, v in dates_values if v is not None and pd.notna(v) and pd.notnull(v) and not (isinstance(v, float) and (v != v))]
    if not cleaned:
        return
    series[ticker] = [[d if isinstance(d, str) else d.strftime("%Y-%m-%d"), round(float(v), 6)] for d, v in cleaned]
    last_d, last_v = cleaned[-1]
    last_date_str = last_d if isinstance(last_d, str) else last_d.strftime("%Y-%m-%d")
    slim[name] = {
        "t": ticker, "c": 14, "cl": category_label, "th": theme,
        "u": units, "f": freq, "s": source,
        "d": description, "i": "", "sh": "", "sl": "",
        "r": [], "n": len(cleaned), "ld": last_date_str, "lv": round(float(last_v), 4),
    }

# Synthetic 1: NFP — trailing N-month AVERAGE monthly change (thousands per month)
# Computed as (level_today − level_{N months ago}) / N. This is the standard
# macro convention: it's identical to an N-month moving average of the m/m
# change, but is exact (no edge effects). Putting all three lines (3m/6m/12m)
# on a "per-month" basis makes them directly comparable on a single axis and
# lands the values in the familiar NFP-print range (e.g., 20-300K/mo).
#
# Earlier this was implemented as raw cumulative diff (level − level_N), but
# that made the 12m line ~4x larger than the 3m line by construction, which
# obscured the trend comparison. The user flagged this as values "looking too
# big". Sanity check at Mar 2026: 12m avg = 260/12 = 21.7K/mo, matches the
# very weak recent trend.
nfp_level = _series_to_df("NFP T Index")
if nfp_level is not None:
    for n_months, label in [(12, "12m"), (6, "6m"), (3, "3m")]:
        avg_monthly = (nfp_level - nfp_level.shift(n_months)) / n_months
        rows = [(d, v) for d, v in avg_monthly.items() if pd.notna(v)]
        _inject_synthetic(
            name=f"NFP {label} Avg Monthly Chg",
            ticker=f"NFP_T_AVG_{n_months}M",  # synthetic
            dates_values=rows,
            units="K jobs/mo",
            freq="Monthly",
            source="BLS (derived)",
            description=(
                f"Trailing {n_months}-month average monthly change in Nonfarm Payrolls. "
                f"Computed as (NFP T Index level − level {n_months} months prior) ÷ {n_months}. "
                f"Equivalent to an N-month moving average of the monthly NFP print."
            ),
            category_label="14_Payrolls (derived)",
            theme="labor",
        )

# Synthetic 2: Aggregate Hours Index — N-month annualized % change (SAAR)
agg_hours = _series_to_df("AGWHTOTL Index")
if agg_hours is not None:
    for n_months, label in [(12, "12m"), (6, "6m"), (3, "3m")]:
        ratio = agg_hours / agg_hours.shift(n_months)
        saar = ((ratio ** (12.0 / n_months)) - 1.0) * 100.0
        rows = [(d, v) for d, v in saar.items() if pd.notna(v)]
        _inject_synthetic(
            name=f"Agg Hours {label} % SAAR",
            ticker=f"AGWHTOTL_SAAR_{n_months}M",  # synthetic
            dates_values=rows,
            units="% SAAR",
            freq="Monthly",
            source="BLS (derived)",
            description=f"Aggregate Hours Index, annualized percent change over the last {n_months} months. Synthetic series — computed from AGWHTOTL Index.",
            category_label="14_Payrolls (derived)",
            theme="labor",
        )

# Synthetic 3: JOLTS rates — derived from levels (the dataset has levels/YoY, not rates).
# BLS definitions:
#   quits rate    = quits     / employment              * 100
#   openings rate = openings  / (employment + openings) * 100
#   hires rate    = hires     / employment              * 100
# Employment base = total nonfarm (NFP T Index, thousands), matching JOLTS units.
# Sanity (Mar 2026): openings 6866/(158736+6866)=4.15%, quits 3171/158736=2.0% — match published.
_nfp_emp = _series_to_df("NFP T Index")                 # total nonfarm employment level (000s)
_jolt_open = _series_to_df("JOLTTOTL Index")            # total job openings level (000s)
_jolt_quits = _series_to_df("JLTSQUIS Index")           # total quits level (000s)
# Hires: dataset carries only sector RATES (HIREPRIR private, HIREGOVR govt), no total level.
# Derive a total hires rate as the employment-weighted blend of the two. Government is a
# stable ~14.9% of nonfarm payrolls over the sample; the blend is insensitive to the exact
# weight (+-2pp in weight -> +-0.05pp in rate) and tracks the published total hires rate (~3.5%).
_hire_priv = _series_to_df("HIREPRIR Index")
_hire_govt = _series_to_df("HIREGOVR Index")
_GOVT_EMP_SHARE = 0.149

if _nfp_emp is not None and _jolt_quits is not None:
    qr = (_jolt_quits / _nfp_emp) * 100.0
    rows = [(d, v) for d, v in qr.items() if pd.notna(v)]
    _inject_synthetic(
        name="JOLTS Quits Rate Total", ticker="JOLTS_QUITS_RATE",
        dates_values=rows, units="%", freq="Monthly", source="BLS JOLTS (derived)",
        description="Total quits rate = total quits (JLTSQUIS) ÷ total nonfarm employment (NFP T) × 100. Derived; dataset carries the quits level, not the rate.",
        category_label="16_JOLTS (derived)", theme="labor",
    )
if _nfp_emp is not None and _jolt_open is not None:
    orr = (_jolt_open / (_nfp_emp + _jolt_open)) * 100.0
    rows = [(d, v) for d, v in orr.items() if pd.notna(v)]
    _inject_synthetic(
        name="JOLTS Job Openings Rate Total", ticker="JOLTS_OPENINGS_RATE",
        dates_values=rows, units="%", freq="Monthly", source="BLS JOLTS (derived)",
        description="Total job openings rate = openings (JOLTTOTL) ÷ (employment + openings) × 100, employment = NFP T. Derived; dataset carries the openings level, not the rate.",
        category_label="16_JOLTS (derived)", theme="labor",
    )
if _hire_priv is not None and _hire_govt is not None:
    hr = _hire_priv * (1 - _GOVT_EMP_SHARE) + _hire_govt * _GOVT_EMP_SHARE
    rows = [(d, v) for d, v in hr.items() if pd.notna(v)]
    _inject_synthetic(
        name="JOLTS Hires Rate Total", ticker="JOLTS_HIRES_RATE",
        dates_values=rows, units="%", freq="Monthly", source="BLS JOLTS (derived)",
        description=(
            "Total hires rate, derived as the employment-weighted blend of the private (HIREPRIR) "
            f"and government (HIREGOVR) hires rates using a ~{_GOVT_EMP_SHARE*100:.0f}% government "
            "employment share (the dataset lacks a total-hires level or a government-employment level). "
            "Tracks the published BLS total hires rate (~3.5%)."
        ),
        category_label="16_JOLTS (derived)", theme="labor",
    )

# Synthetic 4: NFP State & Local Government m/m change = State + Local (cat 54 components).
_nfp_state = _series_to_df("ECANSWQ9 Index")   # Total > Government > State (m/m chg)
_nfp_local = _series_to_df("ECANHL8R Index")   # Total > Government > Local (m/m chg)
if _nfp_state is not None and _nfp_local is not None:
    sl = (_nfp_state.add(_nfp_local, fill_value=float("nan")))
    rows = [(d, v) for d, v in sl.items() if pd.notna(v)]
    _inject_synthetic(
        name="NFP State & Local Govt (m/m)", ticker="NFP_STATE_LOCAL_GOVT",
        dates_values=rows, units="K jobs", freq="Monthly", source="BLS (derived)",
        description="Monthly change in State + Local government payrolls (sum of NFP hierarchy State and Local government nodes).",
        category_label="54_NFP_Hierarchy_Values (derived)", theme="labor",
    )

# === EXTERNAL: BLS Employment-Population ratio by age (official BLS, not in the Bloomberg pull) ===
# Source: U.S. Bureau of Labor Statistics, Current Population Survey, seasonally adjusted.
# Series LNS12300060 = Emp-Pop ratio, 25-54 yrs (prime age) — retrieved from the official BLS
# series (distributed via FRED's data table; the BLS API requires POST which the fetch tool
# can't issue). Dates converted to month-end to align with the dataset's monthly convention.
# NOTE: BLS does not publish single SA emp-pop series for the exact spans 16-24 or 55-64
# (only 16-19, 20-24, 25-54, 55+), so only the exact prime-age cohort is integrated here.
_BLS_EMPPOP_2554 = {  # YYYY-MM : value (%)
    "2020-01":80.6,"2020-02":80.4,"2020-03":79.4,"2020-04":69.6,"2020-05":71.4,"2020-06":73.5,
    "2020-07":73.8,"2020-08":75.2,"2020-09":75.1,"2020-10":76.1,"2020-11":76.1,"2020-12":76.4,
    "2021-01":76.4,"2021-02":76.6,"2021-03":76.8,"2021-04":76.9,"2021-05":77.1,"2021-06":77.1,
    "2021-07":77.8,"2021-08":77.9,"2021-09":78.0,"2021-10":78.4,"2021-11":79.0,"2021-12":79.2,
    "2022-01":79.2,"2022-02":79.5,"2022-03":80.0,"2022-04":79.9,"2022-05":80.0,"2022-06":79.8,
    "2022-07":79.9,"2022-08":80.2,"2022-09":80.2,"2022-10":79.9,"2022-11":79.8,"2022-12":80.2,
    "2023-01":80.3,"2023-02":80.5,"2023-03":80.7,"2023-04":80.7,"2023-05":80.7,"2023-06":80.8,
    "2023-07":80.9,"2023-08":80.8,"2023-09":80.8,"2023-10":80.7,"2023-11":80.8,"2023-12":80.5,
    "2024-01":80.6,"2024-02":80.7,"2024-03":80.7,"2024-04":80.8,"2024-05":80.8,"2024-06":80.7,
    "2024-07":80.9,"2024-08":80.9,"2024-09":80.9,"2024-10":80.6,"2024-11":80.5,"2024-12":80.5,
    "2025-01":80.7,"2025-02":80.5,"2025-03":80.4,"2025-04":80.7,"2025-05":80.5,"2025-06":80.7,
    "2025-07":80.4,"2025-08":80.7,"2025-09":80.7,"2025-11":80.6,"2025-12":80.7,  # 2025-10 missing (shutdown)
    "2026-01":80.8,"2026-02":80.7,"2026-03":80.7,"2026-04":80.7,
}
_emppop_rows = [
    (pd.Timestamp(f"{ym}-01") + pd.offsets.MonthEnd(0), v) for ym, v in sorted(_BLS_EMPPOP_2554.items())
]
_inject_synthetic(
    name="Emp-Pop Ratio 25-54 (BLS)", ticker="LNS12300060",
    dates_values=_emppop_rows, units="%", freq="Monthly", source="BLS (CPS, SA)",
    description="Employment-population ratio, 25-54 years (prime age), seasonally adjusted. Official BLS series LNS12300060 (Current Population Survey). Retrieved from the BLS series distributed via FRED.",
    category_label="13_Employment (BLS)", theme="labor",
)

# === MATT'S VIEW chart registry ===
# Each chart corresponds to one of the requested labor-market panels.
# `series` items are passed to the workspace-style row renderer as default settings.
# `notes` captures any data gaps (reported in the view + summary).
MATTS_VIEW_CHARTS = [
    {
        "id": "nfp_diff",
        "title": "Change in Nonfarm Payrolls",
        "subtitle": "Trailing 12m / 6m / 3m average monthly change (thousands of jobs per month)",
        "series": [
            {"name": "NFP 12m Avg Monthly Chg", "color": "#6ea8ff"},
            {"name": "NFP 6m Avg Monthly Chg",  "color": "#fbbf24"},
            {"name": "NFP 3m Avg Monthly Chg",  "color": "#4ade80"},
        ],
    },
    {
        "id": "nfp_mom",
        "title": "Nonfarm Payrolls (Change m/m)",
        "subtitle": "Total + key sectors, monthly change (thousands)",
        "series": [
            {"name": "Nonfarm Payrolls Change", "color": "#6ea8ff"},
            {"name": "Total > Leisure & Hospitality", "color": "#fbbf24"},
            {"name": "NFP State & Local Govt (m/m)", "color": "#4ade80"},
            {"name": "Total > Education & Health Services", "color": "#f87171"},
        ],
    },
    {
        "id": "part_time_pct",
        "title": "Part-Time Workers as % of Total Employment",
        "subtitle": "",
        "series": [],
        "notes": "Not in dataset (no part-time employment series; would need USEPTOT / USEPTECO from a fresh pull)",
    },
    {
        "id": "cb_labor_diff",
        "title": "Conference Board Labor Market Differential",
        "subtitle": "% jobs plentiful − % jobs hard to get",
        "series": [
            {"name": "Survey Indicators > Appraisal Of Present Situation > Jobs: Plentiful Less Hard to Get", "color": "#6ea8ff"},
        ],
    },
    {
        "id": "agg_hours_saar",
        "title": "Aggregate Hours Worked, Private Industries (% SAAR)",
        "subtitle": "Rolling 12m / 6m / 3m annualized % change",
        "series": [
            {"name": "Agg Hours 12m % SAAR", "color": "#6ea8ff"},
            {"name": "Agg Hours 6m % SAAR",  "color": "#fbbf24"},
            {"name": "Agg Hours 3m % SAAR",  "color": "#4ade80"},
        ],
    },
    {
        "id": "avg_weekly_hours",
        "title": "Average Weekly Hours: Total Private Industries",
        "subtitle": "",
        "series": [
            {"name": "Avg Weekly Hours All Private", "color": "#6ea8ff"},
        ],
    },
    {
        "id": "diffusion_hiring",
        "title": "Diffusion Indexes of Hiring",
        "subtitle": "3-month averages — payroll diffusion + ISM services employment",
        "series": [
            {"name": "NF Payroll Diffusion Index", "color": "#6ea8ff", "maType": "sma", "maPeriod": 3},
            {"name": "PMI Surveys > Survey Indicators > Services > Employment", "color": "#fbbf24", "maType": "sma", "maPeriod": 3},
        ],
    },
    {
        "id": "ism_employment",
        "title": "ISM Employment Sub-Indexes",
        "subtitle": "3-month averages — services + manufacturing employment",
        "series": [
            {"name": "PMI Surveys > Survey Indicators > Services > Employment", "color": "#6ea8ff", "maType": "sma", "maPeriod": 3},
            {"name": "ISM Mfg Employment", "color": "#fbbf24", "maType": "sma", "maPeriod": 3},
        ],
    },
    {
        "id": "nfib_hiring_plans",
        "title": "NFIB: Percent Planning to Increase Employment, Net",
        "subtitle": "Net hiring plans",
        "series": [
            {"name": "Optimism Index > Employment > Hiring Plans", "color": "#6ea8ff"},
        ],
    },
    {
        "id": "jolts_hires_quits",
        "title": "JOLTS Hires / Quits Rates",
        "subtitle": "3-month averages (derived from levels)",
        "series": [
            {"name": "JOLTS Hires Rate Total", "color": "#6ea8ff", "maType": "sma", "maPeriod": 3},
            {"name": "JOLTS Quits Rate Total", "color": "#fbbf24", "maType": "sma", "maPeriod": 3},
        ],
        "notes": "Rates are derived: quits = quits/employment; hires = employment-weighted blend of private+govt rates (~15% govt). See series descriptions.",
    },
    {
        "id": "jolts_openings_rate",
        "title": "JOLTS Job Openings Rate Total",
        "subtitle": "Derived: openings ÷ (employment + openings)",
        "series": [
            {"name": "JOLTS Job Openings Rate Total", "color": "#6ea8ff"},
        ],
    },
    {
        "id": "unemployment",
        "title": "Unemployment Rate",
        "subtitle": "U-3 and U-6",
        "series": [
            {"name": "Unemployment Rate (U-3)", "color": "#6ea8ff"},
            {"name": "U-6 Underemployment Rate", "color": "#fbbf24"},
        ],
    },
    {
        "id": "sahm",
        "title": "Sahm Real-Time Unemployment Rate Recession Indicator",
        "subtitle": "",
        "series": [],
        "notes": "Sahm Indicator not in dataset",
    },
    {
        "id": "emp_pop_age",
        "title": "Employment-Population Ratio",
        "subtitle": "Headline (16+) + prime-age 25-54 (BLS)",
        "series": [
            {"name": "Emp-Pop Ratio 25-54 (BLS)", "color": "#6ea8ff"},
            {"name": "Employment-Population Ratio", "color": "#fbbf24"},
        ],
        "notes": "Prime-age 25-54 is the official BLS SA series (LNS12300060). BLS does not publish single SA series for 16-24 or 55-64 (only 16-19/20-24/25-54/55+) — fetch those proxies on request.",
    },
    {
        "id": "lfpr",
        "title": "Labor Force Participation Rate",
        "subtitle": "25-54 (prime age) + 16+ (headline)",
        "series": [
            {"name": "Age > 25 and Over > 25-54", "color": "#6ea8ff"},
            {"name": "Labor Force Participation Rate", "color": "#fbbf24"},
        ],
    },
    {
        "id": "claims",
        "title": "Jobless Claims",
        "subtitle": "Initial (4-wk MA) + Continuing",
        "series": [
            {"name": "Continuing Claims", "color": "#6ea8ff"},
            {"name": "Initial Claims 4-Wk MA", "color": "#fbbf24"},
        ],
    },
    {
        "id": "challenger",
        "title": "Challenger, Gray & Christmas Announced Job Cuts",
        "subtitle": "Total announced layoffs (level) + YoY",
        "series": [
            {"name": "Job Layoffs", "color": "#6ea8ff"},
            {"name": "Challenger Job Cuts YoY", "color": "#fbbf24", "scale": "right"},
        ],
    },
]

# Drop any chart's series whose name isn't in `slim` (catalog), keep "notes" to surface gaps.
for chart in MATTS_VIEW_CHARTS:
    chart["series"] = [s for s in chart["series"] if s["name"] in slim]

matts_view_missing = [c for c in MATTS_VIEW_CHARTS if not c["series"]]
print(f"Matt's View: {len(MATTS_VIEW_CHARTS)} charts, {len(matts_view_missing)} fully missing data")

# PCE is a route-through theme: surfaced in the rail/home taxonomy but its 963 actual
# indicators (YoY cats 50/51/53; MoM cats 48/49/52 carry no slim entries) are browsed via
# the bespoke PCE tree (renderPceDashboard), NOT the flat themes_categories machinery.
pce_indicator_count = sum(1 for v in slim.values() if v["th"] == "PCE")  # == 963

payload = {
    "generated": catalog["generated"],
    "asof": catalog["date_range"][1],
    "first": catalog["date_range"][0],
    "n_indicators": catalog["indicator_count"],
    "n_categories": catalog["category_count"],
    "themes": [(th, THEME_LABEL[th]) for th in THEME_ORDER],
    "themes_categories": themes_categories,
    "hero": HERO_AVAILABLE,
    "panels": PANELS_FILTERED,
    "workspace_themes": THEME_REGISTRY,
    "pce_tree": pce_tree,
    "pce_theme": {"id": "PCE", "label": "PCE Hierarchy", "count": pce_indicator_count},
    "indicators": slim,
    "series": series,
    "prints_feed": prints,
    "matts_view": MATTS_VIEW_CHARTS,
}

payload_json = json.dumps(payload, separators=(",",":"), ensure_ascii=False)
print(f"Payload size: {len(payload_json)/1024/1024:.2f} MB")

# 8. HTML/CSS/JS template
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>US Macro Dashboard</title>
<style>
:root {
  /* Bloomberg-terminal palette: neutral near-black, signature amber accent.
     Form-follows-function color coding —
       amber  = primary action / active / headers / brand
       blue   = secondary navigation, tickers, identifiers (--info)
       green/red = data direction (--pos/--neg) */
  --bg: #06080c;
  --bg-elev: #0c1016;
  --bg-elev-2: #11161f;
  --bg-hover: #19202b;
  --border: #222b38;
  --border-strong: #3a4759;
  --text: #e8ebf0;
  --text-2: #9aa5b4;
  --text-3: #7d8796;
  --accent: #ffa028;
  --accent-soft: rgba(255,160,40,0.13);
  --accent-dim: #b9742a;
  --info: #4ea1ff;
  --info-soft: rgba(78,161,255,0.12);
  --pos: #2ee08a;
  --neg: #ff5d5d;
  --warn: #ffcb47;
  --accent-2: #c084fc;            /* user/saved panels — distinct from amber=active */
  --accent-2-soft: rgba(192,132,252,0.13);
  --grid: rgba(255,255,255,0.04);
  --shadow: 0 1px 0 rgba(255,255,255,0.02), 0 6px 22px rgba(0,0,0,0.45);
  /* ---- type scale (P1A-08) — rationalizes existing sizes; do NOT enlarge ---- */
  --fs-micro: 10px;  /* eyebrows, tickers, counts, meta (absorbs former 9px) */
  --fs-body:  11px;  /* default label/body — workhorse */
  --fs-label: 12px;  /* nav, chrome labels, search, tile names */
  --fs-value: 13px;  /* numeric values, prose, card/tile titles (absorbs former 14px) */
  --fs-page:  15px;  /* unified page H1 (P1A-07; absorbs former 18px) */
  --fs-hero:  28px;  /* hero latest value */
  /* ---- spacing — 4px step (P1A-11) ---- */
  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 10px;  --sp-4: 12px;  --sp-5: 16px;  --sp-6: 24px;
  /* ---- radius — controls vs containers (P1A-11) ---- */
  --r-ctl: 3px;  /* buttons, selects, chips, inputs, tooltips */
  --r-box: 6px;  /* tiles, cards, value-strip, chart-wrap, panels */
  --mono: ui-monospace, "JetBrains Mono", "SF Mono", "Menlo", monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Inter", "SF Pro Text", system-ui, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 13px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  height: 100%;
  overflow: hidden;
}

.app {
  display: grid;
  grid-template-rows: 48px 1fr;
  height: 100vh;
}

/* HEADER */
header.topbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 14px;
  background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}
.brand {
  display: flex; align-items: center; gap: 8px;
  font-weight: 700; letter-spacing: 0.06em;
}
.brand .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 10px var(--accent);
}
.brand .name { color: var(--text); font-size: 12px; }
.brand .sub { color: var(--accent-dim); font-size: 10px; font-family: var(--mono); margin-left: 2px; }
.navgroup { display: flex; align-items: center; gap: 4px; }
.navgroup .topbar-div { width: 1px; height: 18px; background: var(--border); margin: 0 4px; }
.topbar .stats {
  display: flex; gap: 14px;
  font-family: var(--mono);
  color: var(--text-3);
  font-size: 10px;
  white-space: nowrap;
}
.topbar .stats .k { color: var(--text-3); letter-spacing: 0.06em; }
.topbar .stats .v { color: var(--text-2); }
.topbar .spacer { flex: 1; }
.topbar .search {
  width: 280px;
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px var(--sp-3);
  border-radius: var(--r-ctl);
  font-family: var(--sans);
  font-size: 12px;
}
.topbar .search:focus { outline: none; border-color: var(--accent); }
.topbar button {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 5px var(--sp-4);
  border-radius: var(--r-ctl);
  cursor: pointer;
  font-family: var(--sans);
  font-size: 11px;
  transition: color .1s, border-color .1s, background .1s;
}
.topbar button:hover { color: var(--text); border-color: var(--border-strong); background: var(--bg-hover); }
.topbar button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.topbar button.active {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
  font-weight: 600;
}
.navarrows { display: flex; gap: 2px; }
.topbar button.navarrow {
  padding: 5px var(--sp-2); font-size: var(--fs-value); line-height: 1; font-family: var(--mono);
  min-width: 30px; color: var(--text-2);
}
.topbar button.navarrow:not(.disabled):hover { color: var(--accent); border-color: var(--accent); }
.topbar button.navarrow.disabled { opacity: 0.25; cursor: default; pointer-events: none; }
.topbar .search { width: 240px; }

/* MAIN GRID */
main.grid {
  display: grid;
  grid-template-columns: 240px 1fr 320px;
  height: 100%;
  overflow: hidden;
}

/* LEFT RAIL */
.left-rail {
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 12px 0;
  font-size: 12px;
}
.left-rail .nav-section { padding: 6px 14px; }
.left-rail .nav-h {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-3);
  padding: 12px 14px 6px;
  font-weight: 600;
}
.left-rail a.theme {
  display: flex;
  justify-content: space-between;
  padding: 6px 14px;
  cursor: pointer;
  color: var(--text-2);
  text-decoration: none;
  border-left: 2px solid transparent;
}
.left-rail a.theme:hover { background: var(--bg-hover); color: var(--text); }
.left-rail a.theme.active { background: var(--accent-soft); color: var(--accent); border-left-color: var(--accent); }
.left-rail a.theme .count { font-family: var(--mono); font-size: 10px; color: var(--text-3); }
.left-rail a.theme.active .count { color: var(--accent); }
.left-rail .cat {
  display: flex; justify-content: space-between;
  padding: 4px 14px 4px 32px;
  font-size: 11px;
  color: var(--text-3);
  cursor: pointer;
  text-decoration: none;
}
.left-rail .cat:hover { color: var(--text); background: var(--bg-hover); }
.left-rail .cat.active { color: var(--accent); }
.left-rail .cat .count { font-family: var(--mono); font-size: 10px; }

/* MAIN CONTENT */
.main-content {
  overflow-y: auto;
  padding: 16px 20px;
}
.section-h {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
}
.section-h h1, .detail-h h1 {
  font-size: var(--fs-page); font-weight: 700; letter-spacing: 0.01em; color: var(--text);
  border-left: 3px solid var(--accent);
  padding-left: var(--sp-2);
  line-height: 1.1;
}
.section-h h2 { border-left: 3px solid var(--accent); padding-left: 9px; line-height: 1.1; }
.section-h .breadcrumb { font-size: 11px; font-family: var(--mono); color: var(--text-3); }
.section-h .breadcrumb a { color: var(--accent); cursor: pointer; text-decoration: none; }
.section-h .breadcrumb a:hover { text-decoration: underline; }
.section-h .ticker-row { padding-left: 12px; }
.section-desc { color: var(--text-2); margin-bottom: 18px; font-size: 12px; max-width: 760px; }
.select-hint { font-size: 11px; }
.eyebrow .select-hint { font-weight: 400; text-transform: none; letter-spacing: 0; }
.indicator-grid + .select-hint, p.select-hint { margin: -6px 0 12px 0; }

/* HERO TILES (home view) */
.hero-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 8px;
  margin-bottom: 24px;
}
.hero-tile {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.1s;
  position: relative;
}
.hero-tile:hover { border-color: var(--border-strong); background: var(--bg-elev-2); }
.hero-tile .label { font-size: 10px; color: var(--text-3); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.hero-tile .value { font-family: var(--mono); font-size: 18px; color: var(--text); font-variant-numeric: tabular-nums; font-weight: 500; }
.hero-tile .meta { font-family: var(--mono); font-size: 10px; color: var(--text-3); margin-top: 4px; display: flex; justify-content: space-between; }
.hero-tile .spark { width: 100%; height: 32px; margin-top: 6px; }

/* THEME GRID */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}
.theme-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
  cursor: pointer;
}
.theme-card:hover { border-color: var(--border-strong); background: var(--bg-elev-2); }
.theme-card h3 { font-size: 13px; margin-bottom: 6px; color: var(--text); }
.theme-card .desc { font-size: 11px; color: var(--text-3); line-height: 1.5; margin-bottom: 8px; }
.theme-card .stats { font-family: var(--mono); font-size: 10px; color: var(--accent); }
.cat-detail-h { color: var(--text-2); font-weight: 600; }
.detail-toggle { cursor: pointer; color: var(--text-2); user-select: none; }
.detail-toggle:hover { color: var(--text); }
.theme-card[data-depth="deep"]    { border-left: 3px solid var(--accent); }
.theme-card[data-depth="mid"]     { border-left: 3px solid var(--border-strong); }
.theme-card[data-depth="shallow"] { border-left: 3px solid var(--border); }

/* CATEGORY VIEW (indicator grid) */
.indicator-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px;
}
.indicator-tile {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
}
.indicator-tile:hover { background: var(--bg-elev-2); border-color: var(--border-strong); }
.indicator-tile .name { font-size: 12px; font-weight: 500; color: var(--text); margin-bottom: 4px; }
.indicator-tile .ticker { font-size: 10px; color: var(--text-3); font-family: var(--mono); margin-bottom: 8px; }
.indicator-tile .row { display: flex; justify-content: space-between; align-items: baseline; }
.indicator-tile .v { font-family: var(--mono); font-size: var(--fs-value); color: var(--text); font-variant-numeric: tabular-nums; }
.indicator-tile .d { font-family: var(--mono); font-size: 10px; color: var(--text-3); }
.indicator-tile .spark { width: 100%; height: 28px; margin-top: 6px; }

/* INDICATOR DETAIL */
.detail-h .ticker-row {
  display: flex; gap: 16px; align-items: baseline;
  font-family: var(--mono); font-size: 11px; color: var(--text-3);
  margin-top: 4px;
}
.detail-h .ticker-row .ticker { color: var(--accent); }
.value-strip {
  display: flex; gap: 20px; align-items: baseline;
  margin: 16px 0;
  padding: 12px 16px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
}
.value-strip .latest {
  font-family: var(--mono); font-size: 28px;
  color: var(--text); font-variant-numeric: tabular-nums;
  font-weight: 500;
}
.value-strip .latest .units { font-size: var(--fs-value); color: var(--text-3); margin-left: 6px;}
.value-strip .latest-date { font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.value-strip .deltas { display: flex; gap: 16px; margin-left: auto; }
.value-strip .delta { font-family: var(--mono); font-size: 11px; }
.value-strip .delta .l { color: var(--text-3); }
.value-strip .delta .v { font-variant-numeric: tabular-nums; }
.value-strip .pos { color: var(--pos); }
.value-strip .neg { color: var(--neg); }

.chart-wrap {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}
.chart-canvas { width: 100%; height: 380px; position: relative; }

.detail-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}
.detail-meta .cell {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  padding: 10px 12px;
  border-radius: 6px;
}
.detail-meta .l { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.detail-meta .v { font-family: var(--mono); font-size: 12px; color: var(--text); }

.detail-section {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.detail-section h3 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-3);
  margin-bottom: 8px;
  font-weight: 600;
}
.eyebrow {
  font-size: var(--fs-body);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-3);
  font-weight: 600;
  margin-bottom: var(--sp-3);   /* 10px */
}
.eyebrow.mt { margin-top: var(--sp-6); }  /* 24px — for the 2nd/3rd home eyebrows */
.detail-section p { color: var(--text); font-size: 13px; line-height: 1.6; }
.detail-section .signal-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 8px; }
.detail-section .signal-row .signal { padding: 10px 12px; border-radius: 4px; }
.detail-section .signal.high { background: rgba(248,113,113,0.06); border-left: 3px solid var(--neg); }
.detail-section .signal.low { background: rgba(74,222,128,0.06); border-left: 3px solid var(--pos); }
.detail-section .signal .l { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); margin-bottom: 4px; }
.detail-section .signal.high .l { color: var(--neg); }
.detail-section .signal.low .l { color: var(--pos); }

.related-list {
  display: flex; flex-wrap: wrap; gap: 6px;
}
.related-list a {
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: var(--r-ctl);
  font-size: 11px;
  color: var(--text);
  text-decoration: none;
  cursor: pointer;
  font-family: var(--mono);
}
.related-list a:hover { border-color: var(--accent); color: var(--accent); }

/* RIGHT RAIL */
.right-rail {
  background: var(--bg-elev);
  border-left: 1px solid var(--border);
  overflow-y: auto;
  padding: 14px 16px;
}
.right-rail h3 { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin-bottom: 10px; font-weight: 600; }
.right-rail .feed-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.right-rail .feed-item:hover .feed-name { color: var(--accent); }
.right-rail .feed-item:last-child { border-bottom: none; }
.right-rail .feed-name { font-size: 11px; color: var(--text); margin-bottom: 2px; }
.right-rail .feed-row {
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 10px; color: var(--text-3);
}
.right-rail .feed-row .v { color: var(--text); }
.right-rail .feed-theme { font-size: var(--fs-micro); color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em;}

/* PANELS BOARD — multi-select + custom */
.panels-action-bar {
  display: flex; gap: 10px; align-items: center;
  padding: 10px 14px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-bottom: 14px;
  font-size: 11px;
}
.panels-section-h {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-3);
  margin: 18px 0 8px 0;
  font-weight: 600;
}
.theme-card {
  position: relative;
}
.theme-card.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.theme-card .panel-select {
  position: absolute;
  top: 8px; right: 8px;
  width: 13px; height: 13px;
  accent-color: var(--accent);
  cursor: pointer;
  z-index: 2;
}
/* Indicator-tile multi-select (global, cross-theme) */
.indicator-tile { position: relative; }
.indicator-tile.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.indicator-tile .ind-select,
.hero-tile .ind-select {
  position: absolute;
  top: 6px; right: 6px;
  width: 13px; height: 13px;
  accent-color: var(--accent);
  cursor: pointer;
  z-index: 2;
  opacity: 0.8;
  transition: opacity 0.15s;
}
.indicator-tile:hover .ind-select,
.hero-tile:hover .ind-select,
.indicator-tile .ind-select:checked,
.hero-tile .ind-select:checked {
  opacity: 1;
}
.hero-tile { position: relative; }
.hero-tile.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}
.theme-card.custom-panel {
  border-color: rgba(192, 132, 252, 0.4);
  background: linear-gradient(180deg, var(--accent-2-soft), var(--bg-elev));
}
.theme-card.custom-panel .stats { color: var(--accent-2); }
.theme-card .custom-panel-delete {
  position: absolute;
  top: 8px; right: 32px;
  width: 18px; height: 18px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text-3);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  z-index: 2;
}
.theme-card .custom-panel-delete:hover {
  color: var(--neg);
  border-color: var(--neg);
}

/* COMBO GRID — multiple panels at once */
.combo-controls {
  display: flex; gap: 6px; align-items: center;
  padding: 8px 12px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-bottom: 12px;
}
.combo-controls .label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-3); margin: 0 4px 0 0;
}
.combo-grid {
  display: grid;
  gap: 12px;
}
.combo-cell {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  min-height: 280px;
  transition: border-color 0.1s;
}
.combo-cell:hover { border-color: var(--accent); }
.combo-cell-h {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 6px;
}
.combo-cell-h h3 {
  font-size: 12px; color: var(--text); margin: 0;
}
.combo-cell-meta {
  font-size: 10px; color: var(--text-3); font-family: var(--mono);
}
.combo-cell-chart {
  flex: 1;
  position: relative;
  min-height: 220px;
}
.combo-cell-chart canvas { width: 100%; height: 100%; }

/* SHARED FLOATING SURFACE — fixed transient popovers (selection bar / compare badge / toast) */
.float-surface {
  position: fixed;
  background: var(--bg-elev-2);
  border: 1px solid var(--accent);
  border-radius: 6px;
  box-shadow: var(--shadow);
}

/* FLOATING SELECTION BAR (panels combo) */
.floating-bar {
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%) translateY(16px);
  padding: 9px 14px;
  display: none;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  font-family: var(--mono);
  z-index: 150;
  opacity: 0;
  transition: opacity 0.15s, transform 0.15s;
}
.floating-bar.show {
  display: flex;
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.floating-bar .count {
  color: var(--accent);
  font-weight: 600;
  font-family: var(--mono);
  font-size: 11px;
}
.floating-bar button {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 5px 12px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  font-family: var(--mono);
  transition: color .1s, border-color .1s, background .1s;
}
.floating-bar button:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}
.floating-bar button:disabled { opacity: 0.35; cursor: not-allowed; }

/* TOAST notification (clipboard etc) */
.ws-toast {
  bottom: 24px; right: 24px;
  padding: 10px 16px;
  color: var(--text);
  font-size: 12px;
  font-family: var(--mono);
  z-index: 200;
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 0.18s ease-out, transform 0.18s ease-out;
  pointer-events: none;
  max-width: 420px;
}
.ws-toast.show { opacity: 1; transform: translateY(0); }
.ws-toast.warn { border-color: var(--warn); color: var(--warn); }

/* IN-APP DIALOG (replaces native prompt/confirm — P1C-13) — reuses .float-surface/.pbtn/.ws-mag. */
.ws-overlay {
  position: fixed; inset: 0; z-index: 300;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
}
.ws-dialog {
  position: relative; min-width: 280px; max-width: 360px;
  padding: 16px; font-family: var(--sans);
}
.ws-dialog-msg { font-size: 12px; color: var(--text); margin-bottom: 12px; }
.ws-dialog-input { margin-bottom: 12px; }
.ws-dialog-btns { display: flex; justify-content: flex-end; gap: 8px; }
.ws-dialog-ok { border-color: var(--accent); color: var(--accent); }

/* WORKSPACE — theme-by-theme studio */
.ws-tabs {
  display: flex; gap: 0;
  margin: -4px 0 14px 0;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  flex-wrap: nowrap;
}
.ws-tab {
  background: transparent;
  border: none; border-bottom: 2px solid transparent;
  color: var(--text-3);
  padding: 9px 16px;
  font-size: 12px;
  font-family: var(--sans);
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.1s, border-color 0.1s;
}
.ws-tab:hover { color: var(--text); }
.ws-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 500;
}
.ws-controls-bar {
  display: flex; align-items: center; gap: 6px;
  margin: 0 0 12px 0;
  padding: 10px 14px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  flex-wrap: wrap;
}
/* Matt's View — chart pill bar */
.mv-pill {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 5px 11px;
  font-family: var(--mono);
  font-size: 11px;
  cursor: pointer;
  border-radius: 4px;
  white-space: nowrap;
  transition: background 0.1s, border-color 0.1s, color 0.1s;
}
.mv-pill:hover { background: var(--bg-hover); border-color: var(--border-strong); color: var(--text); }
.mv-pill.active {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent);
}
.mv-pill.missing { opacity: 0.55; }
.mv-pill.missing.active { opacity: 1; border-color: var(--warn); color: var(--warn); background: rgba(251,191,36,0.08); }
.mv-pill .mv-pill-dot { margin-right: 4px; color: var(--warn); }
#btn-matts-view.active { background: var(--accent-soft); color: var(--accent); }
/* Matt's View — thumbnail chart tile grid */
.mv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}
.mv-tile {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px 10px;
  cursor: pointer;
  transition: background 0.1s, border-color 0.1s, transform 0.05s;
  display: flex; flex-direction: column;
}
.mv-tile:hover { background: var(--bg-elev-2); border-color: var(--accent); }
.mv-tile:active { transform: translateY(1px); }
.mv-tile-title { font-size: 13px; font-weight: 500; color: var(--text); margin-bottom: 2px; }
.mv-tile-sub { font-size: 10px; color: var(--text-3); line-height: 1.35; min-height: 26px; }
.mv-tile-cv { width: 100%; height: 60px; margin: 6px 0 4px; display: block; }
.mv-tile-foot { font-family: var(--mono); font-size: 10px; color: var(--text-3); }
.mv-tile-foot .gap { color: var(--warn); }
.mv-tile.missing { opacity: 0.6; }
.mv-tile.missing:hover { opacity: 1; border-color: var(--warn); }
.ws-controls-bar .label {
  font-size: var(--fs-micro);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-3);
  margin: 0 2px 0 0;
  font-weight: 600;
}
/* Vertical divider between control groups (Bauhaus: explicit grouping) */
.ws-controls-bar .ctl-div {
  width: 1px; height: 18px; background: var(--border);
  margin: 0 8px; flex-shrink: 0;
}
.ws-controls-bar .ctl-spacer { flex: 1 1 auto; }

/* ===== UNIFIED BUTTON SYSTEM (form follows function) ===== */
/* Standalone action button — always a complete 1px border on all four sides. */
.pbtn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 4px 10px;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.4;
  cursor: pointer;
  border-radius: 3px;
  transition: color .1s, border-color .1s, background .1s;
}
.pbtn:hover { color: var(--text); border-color: var(--border-strong); background: var(--bg-hover); }
.pbtn:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.pbtn.active {
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid var(--accent);   /* full border — fixes "border not fully highlighted" */
}
.pbtn.dim, .pbtn:disabled { opacity: 0.38; cursor: not-allowed; pointer-events: none; }

/* Segmented control — connected buttons for mutually-exclusive choices (e.g. Period). */
.seg { display: inline-flex; flex-shrink: 0; }
.seg .pbtn { border-radius: 0; border-right: none; }
.seg .pbtn:first-child { border-radius: 3px 0 0 3px; }
.seg .pbtn:last-child  { border-radius: 0 3px 3px 0; border-right: 1px solid var(--border); }
/* Active segment: re-add its own complete border and lift above neighbours so all 4 sides show. */
.seg .pbtn.active {
  border: 1px solid var(--accent);
  position: relative; z-index: 1;
}
.ws-series-list {
  margin-top: 14px;
}
.ws-series-h {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-3);
  margin-bottom: 8px;
  font-weight: 600;
}
.ws-series-h .ws-actions {
  display: flex; gap: 6px;
}
.ws-series-h .ws-actions button {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-3);
  padding: 3px 8px;
  font-size: 10px;
  border-radius: 3px;
  cursor: pointer;
  font-family: var(--sans);
  text-transform: none;
  letter-spacing: 0;
}
.ws-series-h .ws-actions button:hover { color: var(--text); border-color: var(--border-strong); }
.ws-series-row {
  display: grid;
  grid-template-columns: 18px 16px 1fr auto auto auto auto auto;
  gap: 8px;
  align-items: center;
  padding: 6px 10px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 11px;
}
.ws-series-row.row-all-tab {
  grid-template-columns: 18px 16px 1fr auto auto auto auto auto auto;
}
/* Column-header row for the series list (Item 3 / P1C-06) — plain top header (not sticky:
   the scroll parent is .main-content, not the list, so sticky would float over the chart). */
.ws-row-head {
  background: transparent; border: none; margin-bottom: 2px; padding: 0 10px;
  align-items: end;
}
.ws-row-head > span {
  color: var(--text-3); font-size: 9px; text-transform: uppercase;
  letter-spacing: 0.06em; font-family: var(--mono);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* Non-default markers — tint the control border so altered settings read at a glance. */
.ws-series-row select.ws-nondefault,
.ws-series-row .ws-mag.ws-nondefault { border-color: var(--accent); }
.ws-series-row .ws-row-delete {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-3);
  width: 22px; height: 22px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  font-family: var(--sans);
  padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
}
.ws-series-row .ws-row-delete:hover {
  color: var(--neg);
  border-color: var(--neg);
}
.ws-series-row.invisible {
  opacity: 0.45;
}
.ws-series-row.visible {
  border-left-width: 3px;
}
.ws-series-row .ws-color {
  width: 14px; height: 14px;
  border-radius: 3px;
  cursor: pointer;
  flex-shrink: 0;
  border: 1px solid rgba(255,255,255,0.1);
}
.ws-series-row .ws-color:hover {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
/* Color popover (P1C-07) — direct palette pick + reset, reuses .float-surface. */
.ws-color-pop { z-index: 250; padding: 8px; }
.ws-color-grid { display: grid; grid-template-columns: repeat(6, 16px); gap: 6px; margin-bottom: 8px; }
.ws-color-pick { width: 16px; height: 16px; border-radius: 3px; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; padding: 0; }
.ws-color-pick.sel { outline: 2px solid var(--accent); outline-offset: 1px; }
.ws-color-reset { width: 100%; }
.ws-series-row .ws-name {
  color: var(--text);
  font-size: var(--fs-body);
  min-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ws-series-row select {
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 3px 6px;
  border-radius: 3px;
  font-family: var(--mono);
  font-size: 10px;
  cursor: pointer;
  min-width: 64px;
}
.ws-series-row select:focus { border-color: var(--accent); }
.ws-series-row select:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.ws-series-row .ws-scale-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ws-series-row .ws-mag {
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--mono);
  font-size: 10px;
  width: 52px;
  text-align: right;
}
.ws-series-row .ws-mag:focus {
  border-color: var(--accent);
  background: var(--bg-elev);
}
.ws-series-row .ws-mag:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.ws-series-row .ws-mag:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.ws-series-row .ws-mag-reset {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-3);
  width: 22px; height: 22px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  font-family: var(--sans);
  padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
}
.ws-series-row .ws-mag-reset:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--accent);
}
.ws-series-row .ws-mag-reset:disabled,
.ws-series-row .ws-mag-reset.dim {
  opacity: 0.35;
  cursor: not-allowed;
}
.ws-series-row .ws-row-remove {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-3);
  width: 22px; height: 22px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  font-family: var(--sans);
  padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
}
.ws-series-row .ws-row-remove:hover {
  color: var(--neg);
  border-color: var(--neg);
}
.ws-series-row input[type="checkbox"] {
  width: 13px; height: 13px;
  accent-color: var(--accent);
  cursor: pointer;
  margin: 0;
}
.ws-empty-chart {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-3); font-size: 12px;
}
/* Actionable empty states (P1C-12) — turn dead-ends into a next action. */
.ws-empty-state { padding: 24px 0; display: flex; flex-direction: column; gap: 12px; align-items: flex-start; }
.ws-empty-chart .pbtn { margin-left: 6px; }

/* All-tab search picker */
.ws-all-search-wrap { margin: 14px 0; }
.ws-all-search {
  width: 100%;
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 4px;
  font-family: var(--sans);
  font-size: 12px;
  margin-top: 4px;
}
.ws-all-search:focus { outline: none; border-color: var(--accent); }
.ws-all-search-results {
  margin-top: 6px;
  max-height: 320px;
  overflow-y: auto;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 4px;
}
.ws-all-empty, .ws-all-more {
  padding: 12px 14px;
  font-size: 11px;
  color: var(--text-3);
  text-align: center;
}
.ws-all-result {
  display: grid;
  grid-template-columns: 22px minmax(140px, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  padding: 7px 12px;
  font-size: 11px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.ws-all-result:hover { background: var(--bg-hover); }
.ws-all-result:last-child { border-bottom: none; }
.ws-all-result-add {
  color: var(--accent);
  font-size: var(--fs-value);
  font-weight: 700;
  text-align: center;
  line-height: 1;
}
.ws-all-result-name { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-all-result-ticker { color: var(--accent); font-family: var(--mono); font-size: 10px; }
.ws-all-result-cat { color: var(--text-3); font-size: 10px; }
.ws-rail-section {
  font-family: var(--mono);
  font-size: 11px;
  margin-bottom: 12px;
}
.ws-rail-section .summary {
  color: var(--text-2);
  line-height: 1.5;
  font-family: var(--sans);
  font-size: 11px;
}
.ws-rail-ind {
  border-left: 2px solid var(--border);
  padding-left: 8px;
  margin-bottom: 8px;
  font-family: var(--sans);
}
.ws-rail-ind .name {
  color: var(--text);
  font-size: 11px;
  font-weight: 500;
}
.ws-rail-ind .meta {
  color: var(--text-3);
  font-size: 10px;
  font-family: var(--mono);
  margin-top: 2px;
}
.ws-rail-ind .why {
  color: var(--text-2);
  font-size: 10px;
  margin-top: 4px;
  line-height: 1.4;
}
.ws-related-link {
  cursor: pointer;
  padding: 6px 8px;
  margin-bottom: 4px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-elev);
  font-size: 11px;
  transition: border-color 0.1s;
}
.ws-related-link:hover {
  border-color: var(--accent);
  background: var(--bg-elev-2);
}
.ws-related-link .label {
  color: var(--text);
  font-size: 11px;
  font-weight: 500;
}
.ws-related-link .desc {
  color: var(--text-3);
  font-size: 10px;
  margin-top: 2px;
}
.ws-narrative {
  font-size: 11px;
  color: var(--text-2);
  padding: 4px 0;
  border-left: 2px solid var(--accent);
  padding-left: 8px;
  margin-bottom: 4px;
}

/* PCE DASHBOARD */
.pce-chips-bar {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 6px;
  min-height: 38px;
}
.chips-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pce-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 8px 4px 8px;
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 11px;
  color: var(--text);
  cursor: default;
  user-select: none;
}
.pce-chip:hover { border-color: var(--border-strong); }
.pce-chip .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.pce-chip .lbl { font-weight: 500; }
.pce-chip .val { font-family: var(--mono); color: var(--text-3); font-size: 10px; }
.pce-chip .x {
  margin-left: 2px; padding: 0 4px; cursor: pointer;
  color: var(--text-3); font-size: var(--fs-value); line-height: 1;
}
.pce-chip .x:hover { color: var(--neg); }
.pce-chip.disabled { opacity: 0.4; }

.pce-chart-empty {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-3); font-size: 12px;
}

/* PCE right-rail tree & controls */
.pce-rail-controls { padding-bottom: 10px; border-bottom: 1px solid var(--border); margin-bottom: 8px; }
.pce-control-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px;
}
.pce-control-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-3); width: 60px; flex-shrink: 0;
}
.pce-toggle { display: flex; flex: 1; }
.pce-toggle .opt {
  background: transparent; border: 1px solid var(--border); color: var(--text-2);
  padding: 4px 10px; font-size: 11px; cursor: pointer;
  font-family: var(--mono); flex: 1; text-align: center;
}
.pce-toggle .opt:first-child { border-radius: 4px 0 0 4px; }
.pce-toggle .opt:last-child { border-radius: 0 4px 4px 0; border-left: none; }
.pce-toggle .opt.active { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }
.pce-toggle .opt:hover:not(.active) { color: var(--text); }

.pce-search {
  width: 100%;
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 5px 8px;
  border-radius: 4px;
  font-family: var(--sans);
  font-size: 11px;
  margin-top: 4px;
}
.pce-search:focus { outline: none; border-color: var(--accent); }

.pce-rail-actions {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 8px; font-size: 10px;
}
.pce-rail-actions .clear-btn {
  background: transparent; border: 1px solid var(--border); color: var(--text-2);
  padding: 3px 8px; font-size: 10px; border-radius: 3px; cursor: pointer;
  font-family: var(--sans);
}
.pce-rail-actions .clear-btn:hover { color: var(--text); border-color: var(--border-strong); }

.pce-tree-rail {
  font-size: 11px;
  /* Absorbs remaining space — flexible scrollable list */
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  margin-right: -8px; padding-right: 4px;
}
.pce-node {
  display: flex; align-items: center; gap: 2px;
  padding: 2px 0;
  color: var(--text-2);
  cursor: default;
  line-height: 1.3;
}
.pce-node:hover { background: var(--bg-hover); color: var(--text); }
.pce-node.root { font-weight: 600; padding: 4px 0; border-bottom: 1px solid var(--border); margin-bottom: 4px; }
.pce-node .twirl {
  width: 20px; height: 18px;        /* was 12 / 14 — larger drill-down hit target (P1C-16) */
  margin-left: -4px;                 /* keep glyph visually aligned at the indent */
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer; user-select: none;
  color: var(--text-3); font-size: var(--fs-micro);
  transition: transform 0.12s;
  flex-shrink: 0;
}
.pce-node .twirl.expanded { transform: rotate(90deg); }
.pce-node .twirl.leaf { visibility: hidden; }
.pce-node .twirl:hover { color: var(--text); }
.pce-node label {
  flex: 1;
  display: flex; align-items: center; gap: 5px;
  cursor: pointer;
  padding: 0;
  min-width: 0;
}
.pce-node input[type="checkbox"] {
  margin: 0; width: 11px; height: 11px;
  accent-color: var(--accent);
  cursor: pointer;
  flex-shrink: 0;
}
.pce-node .name { flex: 1; line-height: 1.3; word-break: break-word; }
/* Parent-node name doubles as an expand target (sibling of the selection <label>).
   For parent nodes the label holds only the checkbox, so it must not flex-grow —
   the name-expand sibling takes the remaining width instead. */
.pce-node[data-haschildren="1"] > label { flex: 0 0 auto; }
.pce-node .name-expand { flex: 1; cursor: pointer; }
.pce-node.selected .name { color: var(--accent); }
.pce-node.no-data .name { color: var(--text-3); font-style: italic; }
.pce-node.no-data input { opacity: 0.3; cursor: not-allowed; }
.pce-node.no-data:hover { background: transparent; }

/* SEARCH RESULTS POPUP */
.search-results {
  position: absolute;
  top: 42px; right: 18px;
  width: 380px;
  max-height: 500px;
  overflow-y: auto;
  background: var(--bg-elev);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  z-index: 100;
  display: none;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.search-results.open { display: block; }
.search-results .item {
  padding: 8px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.search-results .item:hover { background: var(--bg-hover); }
.search-results .item .name { font-size: 12px; color: var(--text); }
.search-results .item .meta { font-size: 10px; color: var(--text-3); font-family: var(--mono); margin-top: 2px; }
.search-results .sr-group {
  position: sticky; top: 0;
  padding: 4px 14px;
  font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-3); background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
}
.search-results .sr-group .sr-gcount {
  color: var(--text-2); font-family: var(--mono); margin-left: 4px;
}
.search-results .sr-footer {
  padding: 7px 14px; font-size: 10px; text-align: center;
  border-top: 1px solid var(--border);
}

/* SCROLLBAR */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-3); }

/* utility */
.muted { color: var(--text-3); }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.pos { color: var(--pos); } .neg { color: var(--neg); } .warn { color: var(--warn); }

/* Rail drawer (P1C-05): collapse the right rail by choice at any width. */
main.grid.rail-collapsed { grid-template-columns: 240px 1fr 0; }
main.grid.rail-collapsed .right-rail { display: none; }

/* Intermediate tier (~1400px): keep the rail (narrower) but reflow the dense series-row
   controls so the 7 controls wrap beneath the name instead of clipping. Uses flex-wrap
   (the predictable fallback over grid auto-flow). The aligned column header is hidden
   here since rows wrap — the non-default border-tints still convey altered state. */
@media (max-width: 1400px) {
  main.grid { grid-template-columns: 220px 1fr 280px; }
  main.grid.rail-collapsed { grid-template-columns: 220px 1fr 0; }
  .ws-series-row, .ws-series-row.row-all-tab {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  }
  .ws-series-row .ws-name { flex: 1 1 100%; min-width: 0; }
  .ws-series-row select { min-width: 0; }
  .ws-row-head { display: none; }
}

/* Small-screen floor (~1100px): rail auto-hidden; rows already wrap from 1400px down. */
@media (max-width: 1100px) {
  main.grid, main.grid.rail-collapsed { grid-template-columns: 200px 1fr 0; }
  .right-rail { display: none; }
}
</style>
</head>
<body>
<div class="app">
  <header class="topbar">
    <div class="navarrows">
      <button id="btn-back" class="navarrow disabled" title="Back (Alt+←)">←</button>
      <button id="btn-fwd" class="navarrow disabled" title="Forward (Alt+→)">→</button>
    </div>
    <div class="brand">
      <span class="dot"></span>
      <span class="name">US MACRO</span>
      <span class="sub">v1.0</span>
    </div>
    <nav class="navgroup">
      <button id="btn-home">Home</button>
      <button id="btn-workspace">Workspace</button>
      <button id="btn-panels">Panels</button>
      <button id="btn-pce">PCE</button>
      <button id="btn-matts-view" title="Labor Monitor — fixed labor-market board">Labor Monitor</button>
    </nav>
    <button id="btn-rail-toggle" class="navarrow" title="Toggle info rail">⊟</button>
    <div class="spacer"></div>
    <input class="search" id="search" placeholder="Search indicators or tickers…" autocomplete="off">
    <div class="stats">
      <span><span class="k">AS OF</span> <span class="v" id="stat-asof"></span></span>
      <span><span class="k">IND</span> <span class="v" id="stat-n"></span></span>
      <span><span class="k">CAT</span> <span class="v" id="stat-cats"></span></span>
      <span><span class="k">RANGE</span> <span class="v" id="stat-range"></span></span>
    </div>
  </header>

  <main class="grid">
    <aside class="left-rail" id="left-rail"></aside>
    <section class="main-content" id="main"></section>
    <aside class="right-rail" id="right-rail"></aside>
  </main>
</div>

<div class="search-results" id="search-results"></div>
<div class="floating-bar float-surface" id="floating-bar"></div>

<script>
window.MACRO_DATA = __PAYLOAD__;
</script>
<script>
// =========== APP ===========
const D = window.MACRO_DATA;
const $ = (id) => document.getElementById(id);

// Guarded theme-label lookup. PCE (route-through theme, see pce_theme) and any
// theme/category absent from the 13-theme browse maps must not crash detail views.
function themeLabelOf(th) {
  const t = D.themes.find(x => x[0] === th);
  return t ? t[1] : (th || '—');
}
// Category label resolved from the theme maps when present, else from the indicator's
// own cl meta (works for PCE leaves, which live in the tree not themes_categories).
function catLabelOf(th, cat, fallbackCl) {
  const tc = D.themes_categories[th];
  if (tc) { const c = tc.find(x => x[0] === cat); if (c) return c[1]; }
  return fallbackCl || cat || '—';
}
// True when this indicator belongs to a tree-only theme (no themes_categories entry).
function isTreeOnlyTheme(th) { return th === 'PCE'; }

// =========== SEARCH MATCHER (shared by global search + Workspace overlay) ===========
// Defined early (before the Workspace overlay at showResults) so both surfaces see
// initialized const ALIASES/SCORE — avoids any temporal-dead-zone ambiguity.
// Scoring tiers (higher = better). Tunable; gaps leave room to insert tiers later.
const SCORE = { ALIAS:100, EXACT:90, PREFIX:70, WORD:50, SUB:30, CAT:10 };

// Trader/economist shorthand → exact canonical indicator names (all verified in catalog).
// Keys are matched case-insensitively, full-token OR as a leading prefix of the query.
// Targets MUST be exact D.indicators keys.
const ALIASES = {
  // --- Rates / curve ---  (NOTE: no curve-SPREAD series exists; map to the tenor legs)
  '2s10s'        : ['2Y Treasury', '10Y Treasury'],
  '10s2s'        : ['2Y Treasury', '10Y Treasury'],
  'curve'        : ['2Y Treasury', '10Y Treasury', '3M T-Bill', '30Y Treasury'],
  'yield curve'  : ['2Y Treasury', '10Y Treasury', '3M T-Bill', '30Y Treasury'],
  'front end'    : ['2Y Treasury', '3M T-Bill', '5Y Treasury'],
  'long end'     : ['10Y Treasury', '30Y Treasury'],
  'back end'     : ['10Y Treasury', '30Y Treasury'],
  // --- Real yields / breakevens / inflation expectations ---
  'real yield'   : ['10Y TIPS Real', '5Y TIPS Real', '30Y TIPS Real'],
  'real yields'  : ['10Y TIPS Real', '5Y TIPS Real', '30Y TIPS Real'],
  'tips'         : ['10Y TIPS Real', '10Y TIPS Breakeven', '5Y TIPS Real', '5Y TIPS Breakeven'],
  'breakeven'    : ['10Y TIPS Breakeven', '5Y TIPS Breakeven', '30Y TIPS Breakeven'],
  'breakevens'   : ['10Y TIPS Breakeven', '5Y TIPS Breakeven', '30Y TIPS Breakeven'],
  'bei'          : ['10Y TIPS Breakeven', '5Y TIPS Breakeven'],
  '5y5y'         : ['5Y5Y Forward Inflation Swap', 'Fed 5Y5Y Forward Inflation Exp'],
  'inflation expectations' : ['10Y TIPS Breakeven', '5Y5Y Forward Inflation Swap', 'Fed 5Y5Y Forward Inflation Exp'],
  // --- FX ---
  'dxy'          : ['DXY'],
  'dollar'       : ['DXY', 'BBDXY', 'Fed Real Broad Dollar'],
  'dollar index' : ['DXY', 'BBDXY'],
  'broad dollar' : ['Fed Real Broad Dollar', 'BBDXY'],
  // --- Policy / front-end rates ---
  'fed funds'    : ['Fed Funds Target Mid', 'Fed Funds Target Upper', 'Fed Funds Target Lower'],
  'ff'           : ['Fed Funds Target Mid'],
  'fomc'         : ['Fed Funds Target Mid'],
  'policy rate'  : ['Fed Funds Target Mid', 'EFFR', 'IORB'],
  'r-star'       : ['SF Fed Proxy Funds Rate', 'Fed Funds Target Mid'],   // NO true r* series — nearest proxy
  'neutral rate' : ['SF Fed Proxy Funds Rate', 'Fed Funds Target Mid'],   // ditto
  // --- Labor ---
  'nfp'             : ['Nonfarm Payrolls Change', 'Private Payrolls Change'],
  'payrolls'        : ['Nonfarm Payrolls Change', 'Private Payrolls Change'],
  'jobs report'     : ['Nonfarm Payrolls Change', 'Unemployment Rate (U-3)', 'Avg Hourly Earnings YoY'],
  'claims'          : ['Initial Jobless Claims', 'Continuing Claims', 'Initial Claims 4-Wk MA'],
  'jobless'         : ['Initial Jobless Claims', 'Continuing Claims'],
  'prime-age'       : ['Age > 25 and Over > 25-54'],            // LFPR 25-54 (all)
  'prime age'       : ['Age > 25 and Over > 25-54'],
  'emp-pop'         : ['Employment-Population Ratio'],
  'epop'            : ['Employment-Population Ratio'],
  'participation'   : ['Labor Force Participation Rate'],
  'lfpr'            : ['Labor Force Participation Rate'],
  'u6'              : ['U-6 Underemployment Rate'],
  'u-6'             : ['U-6 Underemployment Rate'],
  'eci'             : ['Employment Cost Index YoY'],
  'wages'           : ['Avg Hourly Earnings YoY', 'Employment Cost Index YoY', 'Atlanta Wage Growth Tracker'],
  'wgt'             : ['Atlanta Wage Growth Tracker'],
  'adp'             : ['ADP Employment Change'],
  'quits'           : ['Job Quits (Thousands) > Job Quits'],
  'job openings'    : ['JOLTS Total Job Openings'],
  // --- Inflation ---
  'supercore'       : ['Supercore CPI', 'Supercore PCE'],
  'sticky cpi'      : ['Atlanta Sticky CPI 12mo', 'Atlanta Sticky CPI 3mo annlz'],
  'trimmed mean'    : ['Cleveland 16% Trimmed CPI YoY', 'Dallas Trimmed Mean PCE'],
  'median cpi'      : ['Cleveland Median CPI YoY'],
  'core'            : ['Core CPI YoY', 'Core PCE YoY'],
  'nowcast'         : ['Atlanta Fed GDPNow', 'Cleveland CPI Nowcast Current', 'Cleveland PCE Nowcast Current'],
  'gdpnow'          : ['Atlanta Fed GDPNow'],
  // --- Vol / credit / liquidity ---
  'vol'             : ['VIX', 'MOVE', 'VVIX'],
  'volatility'      : ['VIX', 'MOVE', 'VVIX'],
  'hy'              : ['Bloomberg US HY OAS'],
  'high yield'      : ['Bloomberg US HY OAS'],
  'ig'              : ['Bloomberg US IG OAS'],
  'oas'             : ['Bloomberg US HY OAS', 'Bloomberg US IG OAS'],
  'credit spreads'  : ['Bloomberg US HY OAS', 'Bloomberg US IG OAS'],
  'qt'              : ['Fed Total Balance Sheet', 'Reserve Balances at Fed Banks'],
  'balance sheet'   : ['Fed Total Balance Sheet', 'Reserve Balances at Fed Banks'],
  'reserves'        : ['Reserve Balances at Fed Banks'],
  'tga'             : ['TGA Daily', 'US Treasury General Account (TGA Weekly)'],
  // --- Commodities ---
  'oil'             : ['WTI Crude Front', 'Brent Crude Front'],
  'crude'           : ['WTI Crude Front', 'Brent Crude Front'],
  'wti'             : ['WTI Crude Front'],
  'brent'           : ['Brent Crude Front'],
};

// Regex-escape a user string (query may contain ( ) . etc).
function reEsc(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

// Return Set of canonical names the query maps to via ALIASES.
// Matches a full alias key OR a key that the query starts with (so "real yield curve"
// still hits "real yield"). Cheap: ALIASES is ~40 entries.
function resolveAliases(q) {
  const hits = new Set();
  if (ALIASES[q]) ALIASES[q].forEach(n => hits.add(n));
  else {
    for (const k in ALIASES) {
      if (q === k || q.startsWith(k + ' ') || k.startsWith(q + ' ')) {
        ALIASES[k].forEach(n => hits.add(n));
      }
    }
  }
  // Only keep targets that actually exist (defensive against catalog drift).
  for (const n of [...hits]) if (!(n in D.indicators)) hits.delete(n);
  return hits;
}

// Score one (name,entry) pair against a lowercased query. Returns 0 = no match.
// Also takes the set of alias-target names for this query (may be empty).
function scoreIndicator(name, e, q, aliasHits) {
  const n = name.toLowerCase();
  const t = (e.t || '').toLowerCase();
  let best = 0;
  if (aliasHits && aliasHits.has(name)) best = SCORE.ALIAS;          // forced top
  if (n === q || t === q) best = Math.max(best, SCORE.EXACT);
  else if (n.startsWith(q) || t.startsWith(q)) best = Math.max(best, SCORE.PREFIX);
  else {
    // word-boundary in name: query begins a token delimited by space - / ( > , etc.
    if (new RegExp('(^|[\\s\\-/(>,:])' + reEsc(q)).test(n)) best = Math.max(best, SCORE.WORD);
    else if (n.includes(q) || t.includes(q)) best = Math.max(best, SCORE.SUB);
    else if ((e.cl || '').toLowerCase().includes(q)) best = Math.max(best, SCORE.CAT);
  }
  return best;
}

// Build a ranked, de-duplicated result list for a raw query string. O(n) + sort.
function rankIndicators(rawq, opts) {
  const q = rawq.trim().toLowerCase();
  if (!q) return [];
  const aliasHits = resolveAliases(q);          // Set<canonical name> (may be empty)
  const exclude = (opts && opts.exclude) || null;  // Set<name> for Workspace overlay
  const hero = D.heroSet || (D.heroSet = new Set(D.hero || []));
  const res = [];
  for (const name in D.indicators) {
    if (exclude && exclude.has(name)) continue;
    const e = D.indicators[name];
    const s = scoreIndicator(name, e, q, aliasHits);
    if (s > 0) res.push([name, e, s]);
  }
  res.sort((a, b) => {
    if (b[2] !== a[2]) return b[2] - a[2];                       // 1. score tier
    const ha = hero.has(a[0]) ? 1 : 0, hb = hero.has(b[0]) ? 1 : 0;
    if (hb !== ha) return hb - ha;                              // 2. HERO/curated boolean
    const la = a[1].ld || '', lb = b[1].ld || '';
    if (lb !== la) return lb < la ? -1 : 1;                     // 3. recency (ld desc, ISO sorts lexically)
    return a[0].localeCompare(b[0]);                            // 4. stable alpha
  });
  return res;
}

const SEARCH_MAX_VISIBLE = 40;   // was a hard 30 with no overflow signal

// Topbar stats
$('stat-asof').textContent = D.asof;
$('stat-n').textContent = D.n_indicators;
$('stat-cats').textContent = D.n_categories;
$('stat-range').textContent = D.first + ' → ' + D.asof;

// State
let state = {
  view: 'home',     // home | theme | category | indicator | panels | panel | pce
  theme: null,
  category: null,
  indicator: null,
  panel: null,
  period: '1Y',     // 1M, 3M, 6M, 1Y, 2Y, ALL
  // Global multi-select for indicators (cross-theme; mirrors panelsSelected for panels)
  indicatorsSelected: [],
  // Per-series settings for the indicators combo view, lazy-initialized
  indicatorsComboSeries: null,
  // Matt's View — currently selected chart id (e.g., 'nfp_diff')
  mattsViewChart: null,
  mattsViewSeries: {},  // keyed by chart id -> array of per-series settings
  // PCE dashboard state
  pceVariant: 'core',   // 'core' | 'full'
  pceTransform: 'yoy',  // 'mom' | 'yoy'
  pceSelected: [],      // array of path strings (e.g. "Services/Health Care/Hospitals")
  pceExpanded: ['', 'Services', 'Durable Goods', 'Nondurable Goods'],
  pceSearch: '',
  // Workspace state
  workspace: {
    activeTheme: 'real_activity',
    themes: {}, // populated by initWorkspaceState()
  },
};

// Initialize workspace state from THEME_REGISTRY + add synthetic 'all' theme
const WS_PALETTE = ['#6ea8ff', '#22d3ee', '#c084fc', '#fb923c', '#a3e635', '#f472b6', '#fbbf24', '#4ade80', '#f87171', '#94a3b8'];
// Inject 'all' theme — pseudo-theme that lets user combine indicators from any source
if (!D.workspace_themes.find(t => t.id === 'all')) {
  D.workspace_themes.unshift({
    id: 'all', name: 'All ↗', kb: 'all themes',
    summary: 'Combine indicators from any theme. Search by name, ticker, or category. Each indicator added gets the same per-series controls (color, MA, lag, style, scale) as theme dashboards.',
    defaults: [],
    available: Object.keys(D.indicators), // all indicators in catalog
    related: [], narratives: [],
  });
}
function initWorkspaceState() {
  D.workspace_themes.forEach(theme => {
    // 'all' theme: start with empty indicators; user adds via search
    if (theme.id === 'all') {
      state.workspace.themes['all'] = {
        indicators: [],
        period: '1Y',
        yAxisMode: 'linear',
        showTickers: false,
        searchQuery: '',
      };
      return;
    }
    const indicators = theme.available.map((name, i) => {
      const defIdx = theme.defaults.indexOf(name);
      const isDefault = defIdx >= 0;
      return {
        name,
        visible: isDefault,
        color: isDefault ? WS_PALETTE[defIdx % WS_PALETTE.length] : WS_PALETTE[i % WS_PALETTE.length],
        lineStyle: 'solid',
        lineWidth: 1.6,
        maType: 'none',
        maPeriod: 0,
        lag: 0,
        scale: 'auto',  // 'auto' | 'left' | 'right' | 'own' — auto = smart multi-axis by magnitude
        magnify: 1,     // numeric multiplier (data multiplier on any axis). 1 = no scaling.
        fill: false,
      };
    });
    state.workspace.themes[theme.id] = {
      indicators,
      period: '1Y',
      yAxisMode: 'linear',
      showTickers: false,
    };
  });
}
initWorkspaceState();

// Period presets in days
const PERIOD_DAYS = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365, '2Y': 730, 'ALL': 99999 };

// =========== LEFT RAIL NAV ===========
function renderLeftRail() {
  const r = $('left-rail');
  // Panels section first (if any)
  let html = '<div class="nav-h">Panels</div>';
  const panelsActive = state.view === 'panels' || state.view === 'panel';
  html += `<a class="theme${panelsActive && !state.panel ? ' active' : ''}" data-action="panels-index">
    <span>All Panels</span><span class="count">${D.panels.length}</span>
  </a>`;
  // List panels grouped by theme; only expand if user is on panels view
  if (panelsActive) {
    // group panels by theme
    const byTheme = {};
    D.panels.forEach(p => { (byTheme[p.theme] = byTheme[p.theme] || []).push(p); });
    Object.keys(byTheme).sort().forEach(th => {
      byTheme[th].forEach(p => {
        const a = state.panel === p.id ? ' active' : '';
        html += `<a class="cat${a}" data-panel="${escapeAttr(p.id)}"><span>${escapeHtml(p.name)}</span><span class="count">${p.indicators.length}</span></a>`;
      });
    });
  }
  html += '<div class="nav-h">Themes</div>';
  D.themes.forEach(([th, label]) => {
    const cats = D.themes_categories[th];
    const totalInd = cats.reduce((a,c) => a + Object.values(D.indicators).filter(x => x.c === c[0]).length, 0);
    const active = state.theme === th ? ' active' : '';
    html += `<a class="theme${active}" data-theme="${escapeAttr(th)}">
      <span>${escapeHtml(label)}</span><span class="count">${totalInd}</span>
    </a>`;
    if (state.theme === th) {
      const headline = cats.filter(c => c[3] !== 'detail');
      const detail   = cats.filter(c => c[3] === 'detail');
      const catRow = ([cat, clabel]) => {
        const n = Object.values(D.indicators).filter(x => x.c === cat).length;
        const a = state.category === cat ? ' active' : '';
        return `<a class="cat${a}" data-cat="${escapeAttr(cat)}"><span>${escapeHtml(clabel)}</span><span class="count">${n}</span></a>`;
      };
      headline.forEach(c => { html += catRow(c); });
      if (detail.length) {
        const dn = detail.reduce((a,c) => a + Object.values(D.indicators).filter(x => x.c === c[0]).length, 0);
        const open = state.theme === th && (state.railDetailOpen === th);
        html += `<a class="cat cat-detail-h${open?' open':''}" data-detail-theme="${escapeAttr(th)}">
          <span>${open?'▾':'▸'} Detail / by-industry</span><span class="count">${dn}</span></a>`;
        if (open) detail.forEach(c => { html += catRow(c); });
      }
    }
  });
  // PCE route-through theme (14th entry): a theme-level row that opens the PCE tree
  // dashboard rather than drilling into themes_categories (which has no PCE entry).
  const pceActive = state.view === 'pce' ? ' active' : '';
  html += `<a class="theme${pceActive}" data-action="pce">
    <span>${escapeHtml(D.pce_theme.label)}</span><span class="count">${D.pce_theme.count}</span>
  </a>`;
  r.innerHTML = html;
  r.querySelectorAll('a.theme').forEach(el => {
    el.onclick = () => {
      if (el.dataset.action === 'panels-index') return navPanelsIndex();
      if (el.dataset.action === 'pce') return navPceDashboard();
      navThemeOrCategory(el.dataset.theme);
    };
  });
  r.querySelectorAll('a.cat').forEach(el => {
    el.onclick = () => {
      if (el.dataset.panel) return navPanel(el.dataset.panel);
      if (el.dataset.detailTheme) {
        state.railDetailOpen = (state.railDetailOpen === el.dataset.detailTheme) ? null : el.dataset.detailTheme;
        return renderLeftRail();
      }
      navCategory(el.dataset.cat);
    };
  });
}

// =========== NAVIGATION ===========
// ===== NAVIGATION HISTORY (in-app back / forward) =====
// A snapshot captures only the "location" fields that determine what renders,
// so in-view re-renders (period toggles, series edits) produce an identical
// snapshot and are de-duplicated — they don't create spurious history entries.
let _navHist = [];
let _navPos = -1;
let _navRestoring = false;
function _navSnapshot() {
  return {
    view: state.view, theme: state.theme, category: state.category,
    indicator: state.indicator, panel: state.panel,
    mattsViewChart: state.mattsViewChart,
    wsTheme: state.workspace && state.workspace.activeTheme,
  };
}
function navHistoryRecord() {
  if (_navRestoring) return;
  const snap = _navSnapshot();
  const top = _navHist[_navPos];
  if (top && JSON.stringify(top) === JSON.stringify(snap)) return;  // same location → skip
  _navHist = _navHist.slice(0, _navPos + 1);   // drop the forward branch on new nav
  _navHist.push(snap);
  _navPos = _navHist.length - 1;
  updateNavButtons();
}
function _navApply(snap) {
  _navRestoring = true;
  if (_pceChart) { _pceChart.destroy(); _pceChart = null; }
  if (snap.wsTheme && state.workspace) state.workspace.activeTheme = snap.wsTheme;
  state = {...state, view: snap.view, theme: snap.theme, category: snap.category,
           indicator: snap.indicator, panel: snap.panel, mattsViewChart: snap.mattsViewChart};
  renderLeftRail(); renderMain(); renderRightRail();
  _navRestoring = false;
  updateNavButtons();
}
function navBack() { if (_navPos > 0) { _navPos--; _navApply(_navHist[_navPos]); } }
function navForward() { if (_navPos < _navHist.length - 1) { _navPos++; _navApply(_navHist[_navPos]); } }
function updateNavButtons() {
  const b = $('btn-back'), f = $('btn-fwd');
  if (b) b.classList.toggle('disabled', _navPos <= 0);
  if (f) f.classList.toggle('disabled', _navPos >= _navHist.length - 1);
}
// Highlight the topbar nav button matching the current view (design matches functionality).
function updateNavActive() {
  const map = {
    home: 'btn-home', workspace: 'btn-workspace',
    panels: 'btn-panels', panel: 'btn-panels', panels_combo: 'btn-panels',
    pce: 'btn-pce', matts_view: 'btn-matts-view',
    // Browse drilldowns + indicators-combo originate from the Home/themes flow
    // (breadcrumb "Home · combined indicators"), so keep Home lit as the anchor.
    indicators_combo: 'btn-home',
    theme: 'btn-home', category: 'btn-home', indicator: 'btn-home',
  };
  ['btn-home','btn-workspace','btn-panels','btn-pce','btn-matts-view'].forEach(id => {
    const el = $(id); if (el) el.classList.toggle('active', map[state.view] === id);
  });
}

function navHome() {
  if (_pceChart) { _pceChart.destroy(); _pceChart = null; }
  if (_wsChart) { _wsChart.destroy(); _wsChart = null; }
  state = {...state, view:'home', theme:null, category:null, indicator:null, panel:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navTheme(th) {
  state = {...state, view:'theme', theme:th, category:null, indicator:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
// Singleton themes (exactly 1 category) have no branching value at the theme page —
// route straight to the single category's indicator grid. ≥2-cat themes (incl. Fiscal)
// keep the theme page. PCE is NOT handled here (it routes to the tree, see navPceDashboard).
function navThemeOrCategory(th) {
  const cats = D.themes_categories[th];
  if (cats && cats.length === 1) return navCategory(cats[0][0]);
  return navTheme(th);
}
function navCategory(cat) {
  // Find theme for this cat. PCE categories live in the tree, not themes_categories;
  // route those to the PCE dashboard instead of the (nonexistent) category page.
  const th = Object.keys(D.themes_categories).find(t => D.themes_categories[t].some(c => c[0]===cat));
  if (!th) return navPceDashboard();   // tree-only / unknown category → safe destination
  state = {...state, view:'category', theme:th, category:cat, indicator:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navPanelsIndex() {
  state = {...state, view:'panels', theme:null, category:null, indicator:null, panel:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navPanelsCombo() {
  state = {...state, view:'panels_combo', theme:null, category:null, indicator:null, panel:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navMattsView(chartId) {
  state = {...state, view:'matts_view', theme:null, category:null, indicator:null, panel:null};
  state.mattsViewChart = chartId || null;   // null => thumbnail grid; id => full chart detail
  renderLeftRail(); renderMain(); renderRightRail();
}
function navPceDashboard() {
  state = {...state, view:'pce', theme:null, category:null, indicator:null, panel:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navWorkspace(themeId) {
  if (_pceChart) { _pceChart.destroy(); _pceChart = null; }
  if (themeId) state.workspace.activeTheme = themeId;
  state = {...state, view:'workspace', theme:null, category:null, indicator:null, panel:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navPanel(pid) {
  state = {...state, view:'panel', panel:pid, indicator:null};
  renderLeftRail(); renderMain(); renderRightRail();
}
function navIndicator(ind) {
  const e = D.indicators[ind];
  state = {...state, view:'indicator', theme:e.th, category:e.c, indicator:ind};
  renderLeftRail(); renderMain(); renderRightRail();
}

// =========== MAIN VIEWS ===========
function renderMain() {
  if (!_navRestoring) navHistoryRecord();   // record location for back/forward (dedups same-view)
  updateNavActive();
  const m = $('main');
  if (state.view === 'home') return renderHome(m);
  if (state.view === 'theme') return renderTheme(m);
  if (state.view === 'category') return renderCategory(m);
  if (state.view === 'indicator') return renderIndicator(m);
  if (state.view === 'panels') return renderPanelsIndex(m);
  if (state.view === 'panel') return renderPanelDetail(m);
  if (state.view === 'panels_combo') return renderPanelsCombo(m);
  if (state.view === 'indicators_combo') return renderIndicatorsCombo(m);
  if (state.view === 'matts_view') return renderMattsView(m);
  if (state.view === 'pce') return renderPceDashboard(m);
  if (state.view === 'workspace') return renderWorkspace(m);
}

function fmtNum(v, units) {
  if (v === null || v === undefined) return '—';
  let abs = Math.abs(v);
  let dec = 2;
  if (abs >= 10000) dec = 0;
  else if (abs >= 100) dec = 1;
  else if (abs < 1 && abs > 0) dec = 3;
  return v.toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec});
}

function renderHome(m) {
  let html = `
    <div class="section-h">
      <h1>Dashboard Overview</h1>
      <span class="breadcrumb">Home</span>
    </div>
    <p class="section-desc">Snapshot of headline US macro indicators. Click a tile to drill in. Use the left rail to navigate by theme, or search any of ${D.n_indicators} tickers above.</p>
    <h3 class="eyebrow">Headline Indicators <span class="select-hint muted">· tick tiles to combine indicators on one chart</span></h3>
    <div class="hero-grid">`;
  D.hero.forEach(ind => {
    const e = D.indicators[ind];
    if (!e) return;
    const sel = (state.indicatorsSelected || []).includes(ind);
    html += `<div class="hero-tile ${sel?'selected':''}" data-ind="${escapeAttr(ind)}">
      ${indSelectCheckbox(ind)}
      <div class="label">${escapeHtml(ind)}</div>
      <div class="value">${fmtNum(e.lv, e.u)}<span class="units"> ${e.u || ''}</span></div>
      <canvas class="spark" data-ind="${escapeAttr(ind)}"></canvas>
      <div class="meta"><span>${e.t}</span><span>${e.ld}</span></div>
    </div>`;
  });
  html += `</div>
    <h3 class="eyebrow mt">Aggregate Panels</h3>
    <div class="theme-grid" style="margin-bottom:24px;">`;
  // Show featured panels (first 6 spanning themes)
  const featuredPanelIds = ['yield_curve', 'policy_rates', 'usd_panel', 'vol_panel', 'credit_spreads', 'fed_bs_liquidity'];
  featuredPanelIds.forEach(pid => {
    const p = D.panels.find(x => x.id === pid);
    if (!p) return;
    const themeLabel = D.themes.find(t => t[0]===p.theme)[1];
    html += `<div class="theme-card" data-panel="${escapeAttr(p.id)}">
      <h3>${escapeHtml(p.name)}</h3>
      <div class="desc">${escapeHtml(p.description.slice(0, 130))}…</div>
      <div class="stats">${escapeHtml(themeLabel)} · ${p.indicators.length} indicators</div>
    </div>`;
  });
  html += `</div>
    <div style="margin:-12px 0 24px;"><a id="home-all-panels" style="color:var(--accent);cursor:pointer;font-size:12px;">View all ${D.panels.length} panels →</a></div>
    <h3 class="eyebrow mt">Themes</h3>
    <div class="theme-grid">`;
  D.themes.forEach(([th, label]) => {
    const cats = D.themes_categories[th];
    const totalInd = cats.reduce((a,c) => a + Object.values(D.indicators).filter(x => x.c === c[0]).length, 0);
    const sample = cats.slice(0,3).map(c => c[1]).join(', ') + (cats.length > 3 ? '…' : '');
    const depth = totalInd >= 200 ? 'deep' : (totalInd >= 50 ? 'mid' : 'shallow');
    html += `<div class="theme-card" data-theme="${escapeAttr(th)}" data-depth="${depth}">
      <h3>${escapeHtml(label)}</h3>
      <div class="desc">${escapeHtml(sample)}</div>
      <div class="stats">${cats.length} categories · ${totalInd} indicators</div>
    </div>`;
  });
  // PCE route-through card (14th theme): routes to the PCE tree dashboard.
  html += `<div class="theme-card" data-action="pce" data-depth="deep">
    <h3>${escapeHtml(D.pce_theme.label)}</h3>
    <div class="desc">BEA personal-consumption hierarchy — browse by branch in the PCE tree dashboard.</div>
    <div class="stats">tree view · ${D.pce_theme.count} indicators</div>
  </div>`;
  html += `</div>`;
  m.innerHTML = html;
  m.querySelectorAll('.hero-tile').forEach(el => el.onclick = (e) => {
    if (e.target.classList.contains('ind-select')) return;
    navIndicator(el.dataset.ind);
  });
  wireIndicatorTileSelection(m, '.hero-tile');
  // panel tiles also use .theme-card class — distinguish by data attr
  m.querySelectorAll('.theme-card').forEach(el => {
    if (el.dataset.panel) el.onclick = () => navPanel(el.dataset.panel);
    else if (el.dataset.action === 'pce') el.onclick = navPceDashboard;
    else if (el.dataset.theme) el.onclick = () => navThemeOrCategory(el.dataset.theme);
  });
  const allPanelsLink = m.querySelector('#home-all-panels');
  if (allPanelsLink) allPanelsLink.onclick = navPanelsIndex;
  // Render sparklines — iterate canvases and look up by data-ind (avoids CSS selector escape issues with & % etc)
  m.querySelectorAll('canvas[data-ind]').forEach(cv => {
    const ind = cv.dataset.ind;
    const sd = seriesByName(ind);
    if (sd.length) drawSparkline(cv, sd);
  });
}

function renderTheme(m) {
  const themeLabel = D.themes.find(t => t[0] === state.theme)[1];
  const cats = D.themes_categories[state.theme];
  let html = `
    <div class="section-h">
      <h1>${themeLabel}</h1>
      <span class="breadcrumb"><a id="bc-home">Home</a> / ${themeLabel}</span>
    </div>
    <div class="theme-grid">`;
  const headline = cats.filter(c => c[3] !== 'detail');
  const detail   = cats.filter(c => c[3] === 'detail');
  const catCard = ([cat, label, desc]) => {
    const n = Object.values(D.indicators).filter(x => x.c === cat).length;
    return `<div class="theme-card" data-cat="${escapeAttr(cat)}">
      <h3>${escapeHtml(label)}</h3>
      <div class="desc">${escapeHtml(desc || '')}</div>
      <div class="stats">${n} indicators</div>
    </div>`;
  };
  headline.forEach(c => { html += catCard(c); });
  html += `</div>`;
  if (detail.length) {
    const dn = detail.reduce((a,c) => a + Object.values(D.indicators).filter(x => x.c === c[0]).length, 0);
    const open = !!state.themeDetailOpen;
    html += `<h3 class="eyebrow mt detail-toggle" id="th-detail-toggle">${open?'▾':'▸'} Detail / by-industry · ${detail.length} categories · ${dn} indicators</h3>`;
    html += `<div class="theme-grid" style="${open?'':'display:none;'}" id="th-detail-grid">`;
    detail.forEach(c => { html += catCard(c); });
    html += `</div>`;
  }
  m.innerHTML = html;
  m.querySelector('#bc-home').onclick = navHome;
  const dt = m.querySelector('#th-detail-toggle');
  if (dt) dt.onclick = () => { state.themeDetailOpen = !state.themeDetailOpen; renderTheme(m); };
  m.querySelectorAll('.theme-card').forEach(el => el.onclick = () => navCategory(el.dataset.cat));
}

function renderCategory(m) {
  const themeLabel = D.themes.find(t => t[0] === state.theme)[1];
  const catLabel = D.themes_categories[state.theme].find(c => c[0]===state.category)[1];
  const catDesc = D.themes_categories[state.theme].find(c => c[0]===state.category)[2];
  const inds = Object.entries(D.indicators).filter(([i,e]) => e.c === state.category);
  let html = `
    <div class="section-h">
      <h1>${catLabel}</h1>
      <span class="breadcrumb"><a id="bc-home">Home</a> / <a id="bc-th">${themeLabel}</a> / ${catLabel}</span>
    </div>
    ${catDesc ? `<p class="section-desc">${catDesc}</p>` : ''}
    <p class="select-hint muted">Tick the checkbox on any tile to combine indicators on one chart.</p>
    <div class="indicator-grid">`;
  inds.forEach(([ind, e]) => {
    const sel = (state.indicatorsSelected || []).includes(ind);
    html += `<div class="indicator-tile ${sel?'selected':''}" data-ind="${escapeAttr(ind)}">
      ${indSelectCheckbox(ind)}
      <div class="name">${escapeHtml(ind)}</div>
      <div class="ticker">${escapeHtml(e.t)}</div>
      <canvas class="spark" data-ind="${escapeAttr(ind)}"></canvas>
      <div class="row">
        <span class="v">${fmtNum(e.lv, e.u)} <span style="font-size:10px;color:var(--text-3);">${e.u||''}</span></span>
        <span class="d">${e.ld}</span>
      </div>
    </div>`;
  });
  html += `</div>`;
  m.innerHTML = html;
  m.querySelector('#bc-home').onclick = navHome;
  m.querySelector('#bc-th').onclick = () => navTheme(state.theme);
  m.querySelectorAll('.indicator-tile').forEach(el => el.onclick = (e) => {
    if (e.target.classList.contains('ind-select')) return;
    navIndicator(el.dataset.ind);
  });
  wireIndicatorTileSelection(m, '.indicator-tile');
  // sparklines: iterate the canvas elements directly
  m.querySelectorAll('canvas.spark[data-ind]').forEach(cv => {
    const ind = cv.dataset.ind;
    const sd = seriesByName(ind);
    if (sd.length) drawSparkline(cv, sd);
  });
}

function renderPanelsIndex(m) {
  const customPanels = loadCustomPanels();
  // Selection state for multi-display (panel-multi)
  state.panelsSelected = state.panelsSelected || [];
  const selCount = state.panelsSelected.length;
  let html = `
    <div class="section-h">
      <h1>Aggregate Panels</h1>
      <span class="breadcrumb"><span style="color:var(--text-2);">Panels</span></span>
    </div>
    <p class="section-desc"><strong>Panels</strong> — curated, ready-made multi-series charts. Tick checkboxes on tiles to display several side-by-side; saved presets appear under Custom panels.</p>

    <div class="panels-action-bar">
      <span class="muted">${selCount ? selCount + ' panel' + (selCount>1?'s':'') + ' selected' : 'Tick tiles to select panels'}</span>
      <button class="pbtn" id="panels-clear-selection" ${selCount===0?'disabled':''}>Clear selection</button>
    </div>`;

  // Custom panels first if any
  if (customPanels.length) {
    html += `<h3 class="panels-section-h">Custom panels (${customPanels.length})</h3><div class="theme-grid">`;
    customPanels.forEach(p => {
      const sel = state.panelsSelected.includes(p.id);
      html += `<div class="theme-card custom-panel ${sel?'selected':''}" data-panel="${escapeAttr(p.id)}">
        <input type="checkbox" class="panel-select" data-pid="${escapeAttr(p.id)}" ${sel?'checked':''} title="Select for combined display">
        <button class="custom-panel-delete" data-pid="${escapeAttr(p.id)}" title="Delete this custom panel">×</button>
        <h3>${escapeHtml(p.name)}</h3>
        <div class="desc">${escapeHtml(p.description || '')}</div>
        <div class="stats">★ Custom · ${p.indicators.length} indicator${p.indicators.length>1?'s':''}</div>
      </div>`;
    });
    html += '</div>';
    html += '<h3 class="panels-section-h">Premade panels</h3>';
  } else {
    html += `<h3 class="panels-section-h">Custom panels</h3>
      <p class="section-desc" style="margin-bottom:14px;">None yet — build a chart in Workspace or any panel/Labor Monitor view and use <strong>⤓ Export</strong> to pin it here as a reusable saved panel.</p>`;
  }

  // Group premade by theme
  html += '<div class="theme-grid">';
  const themeOrder = D.themes.map(t => t[0]);
  const byTheme = {};
  D.panels.forEach(p => { (byTheme[p.theme] = byTheme[p.theme] || []).push(p); });
  themeOrder.forEach(th => {
    if (!byTheme[th]) return;
    const themeLabel = D.themes.find(t => t[0]===th)[1];
    byTheme[th].forEach(p => {
      const sel = state.panelsSelected.includes(p.id);
      html += `<div class="theme-card ${sel?'selected':''}" data-panel="${escapeAttr(p.id)}">
        <input type="checkbox" class="panel-select" data-pid="${escapeAttr(p.id)}" ${sel?'checked':''} title="Select for combined display">
        <h3>${escapeHtml(p.name)}</h3>
        <div class="desc">${escapeHtml(p.description)}</div>
        <div class="stats">${escapeHtml(themeLabel)} · ${p.indicators.length} indicators · ${escapeHtml(p.unit_label)}</div>
      </div>`;
    });
  });
  html += `</div>`;
  m.innerHTML = html;

  // Card click → open panel (but only when click is NOT on checkbox or delete button)
  m.querySelectorAll('.theme-card[data-panel]').forEach(el => el.onclick = (e) => {
    if (e.target.classList.contains('panel-select') || e.target.classList.contains('custom-panel-delete')) return;
    const pid = el.dataset.panel;
    const cust = loadCustomPanels().find(p => p.id === pid);
    if (cust) loadCustomPanelToWorkspace(cust);
    else navPanel(pid);
  });
  // Checkbox: toggle multi-selection
  m.querySelectorAll('.panel-select').forEach(cb => cb.onclick = (e) => {
    e.stopPropagation();
    const pid = cb.dataset.pid;
    const i = state.panelsSelected.indexOf(pid);
    if (cb.checked && i < 0) state.panelsSelected.push(pid);
    else if (!cb.checked && i >= 0) state.panelsSelected.splice(i, 1);
    renderPanelsIndex(m);
  });
  // Delete custom
  m.querySelectorAll('.custom-panel-delete').forEach(btn => btn.onclick = async (e) => {
    e.stopPropagation();
    const pid = btn.dataset.pid;
    if (await inAppConfirm('Delete this custom panel? This cannot be undone.', 'Delete')) {
      deleteCustomPanel(pid);
      const i = state.panelsSelected.indexOf(pid);
      if (i >= 0) state.panelsSelected.splice(i, 1);
      renderPanelsIndex(m);
      showToast('Custom panel deleted', 'ok');
    }
  });
  // Action bar
  m.querySelector('#panels-clear-selection').onclick = () => {
    state.panelsSelected = [];
    renderPanelsIndex(m);
  };
}

function loadCustomPanelToWorkspace(panel) {
  state.workspace.themes['all'] = {
    indicators: panel.indicators.map(i => ({
      visible: true,
      lineStyle: 'solid',
      lineWidth: 1.6,
      maType: 'none',
      maPeriod: 0,
      lag: 0,
      scale: 'auto',
      magnify: 1,
      fill: false,
      ...i,
    })),
    period: panel.period || '1Y',
    yAxisMode: 'linear',
    showTickers: !!panel.showTickers,
    searchQuery: '',
  };
  navWorkspace('all');
  showToast(`Loaded "${panel.name}" into Workspace`, 'ok');
}

// =========== Panels Combo View — unified Workspace-style chart ===========
let _panelsComboChart = null;

function ensurePanelsComboSeries() {
  const selIds = (state.panelsSelected || []).slice();
  const customById = {};
  loadCustomPanels().forEach(p => customById[p.id] = p);
  const items = selIds.map(id => D.panels.find(p => p.id === id) || customById[id]).filter(Boolean);

  const seen = new Set();
  const flat = [];
  items.forEach(p => {
    const panelLabel = p.custom ? '★ ' + p.name : p.name;
    p.indicators.forEach(ind => {
      const indName = typeof ind === 'string' ? ind : ind.name;
      if (!indName || seen.has(indName)) return;
      seen.add(indName);
      flat.push({ name: indName, sourcePanel: panelLabel });
    });
  });

  const cacheValid = state.panelsComboSeries
    && state.panelsComboSeries.length === flat.length
    && state.panelsComboSeries.every((s, i) => s.name === flat[i].name);
  if (!cacheValid) {
    const prior = {};
    (state.panelsComboSeries || []).forEach(s => { prior[s.name] = s; });
    state.panelsComboSeries = flat.map((f, i) => normalizeWsSettings(prior[f.name] || {
      name: f.name,
      sourcePanel: f.sourcePanel,
      ticker: D.indicators[f.name]?.t || '',
    }, i));
  } else {
    state.panelsComboSeries.forEach((s, i) => normalizeWsSettings(s, i));
  }
  return state.panelsComboSeries;
}

function drawPanelsComboChart() {
  const cv = $('big-chart');
  if (!cv) return;
  if (_panelsComboChart) _panelsComboChart.destroy();
  const sers = ensurePanelsComboSeries();
  const built = buildAxisDatasets(sers, state.period, s => seriesByName(s.name), s => s.name);
  if (!built) return;
  _panelsComboChart = new MacroChart(cv, {
    datasets: built.datasets, yAxes: built.yAxes,
    showTickers: state.panelsComboShowTickers || false,
    onTickerPanelClick: () => copyTickersFromSers(sers),
    onLegendClick: (srcIdx, { isolate }) => {
      const s = sers[srcIdx]; if (!s) return;
      if (isolate) {
        const onlyMe = sers.every((x, i) => (i === srcIdx) === !!x.visible);
        sers.forEach(x => { x.visible = true; });
        if (!onlyMe) sers.forEach((x, i) => { x.visible = (i === srcIdx); });
      } else { s.visible = !s.visible; }
      renderPanelsComboSeriesRows(); drawPanelsComboChart();
    },
  });
}

function renderPanelsComboSeriesRows() {
  const c = $('pc-series-rows');
  if (!c) return;
  const sers = ensurePanelsComboSeries();
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) =>
    buildWsRowHTML(idx, s, { extraLabel: 'from ' + (s.sourcePanel || '') })
  ).join('');
  wireWsRows(c, sers, renderPanelsComboSeriesRows, drawPanelsComboChart);
}

// =========== MATT'S VIEW (custom labor-market dashboard) ===========
let _mattsViewChart = null;

function getMattsChart(id) {
  return (D.matts_view || []).find(c => c.id === id) || null;
}

function ensureMattsViewSeries(chart) {
  state.mattsViewSeries = state.mattsViewSeries || {};
  if (!state.mattsViewSeries[chart.id]) {
    state.mattsViewSeries[chart.id] = (chart.series || []).map((s, i) =>
      normalizeWsSettings({
        name: s.name,
        ticker: D.indicators[s.name]?.t || '',
        color: s.color || WS_PALETTE[i % WS_PALETTE.length],
        maType: s.maType || 'none',
        maPeriod: s.maPeriod || 0,
        lag: s.lag || 0,
      }, i)
    );
  } else {
    state.mattsViewSeries[chart.id].forEach((s, i) => normalizeWsSettings(s, i));
  }
  return state.mattsViewSeries[chart.id];
}

function drawMattsViewChart() {
  const cv = $('big-chart');
  if (!cv) return;
  if (_mattsViewChart) _mattsViewChart.destroy();
  const chart = getMattsChart(state.mattsViewChart);
  if (!chart) return;
  const sers = ensureMattsViewSeries(chart);
  const built = buildAxisDatasets(sers, state.period, s => seriesByName(s.name), s => s.name);
  if (!built) return;
  _mattsViewChart = new MacroChart(cv, {
    datasets: built.datasets, yAxes: built.yAxes,
    showTickers: !!state.mattsViewShowTickers,
    onTickerPanelClick: () => copyTickersFromSers(sers),
    onLegendClick: (srcIdx, { isolate }) => {
      const s = sers[srcIdx]; if (!s) return;
      if (isolate) {
        const onlyMe = sers.every((x, i) => (i === srcIdx) === !!x.visible);
        sers.forEach(x => { x.visible = true; });
        if (!onlyMe) sers.forEach((x, i) => { x.visible = (i === srcIdx); });
      } else { s.visible = !s.visible; }
      renderMattsViewSeriesRows(); drawMattsViewChart();
    },
  });
}

function renderMattsViewSeriesRows() {
  const c = $('mv-series-rows');
  if (!c) return;
  const chart = getMattsChart(state.mattsViewChart);
  if (!chart) return;
  const sers = ensureMattsViewSeries(chart);
  if (!sers.length) {
    c.innerHTML = `<div class="muted" style="padding:14px;font-size:11px;line-height:1.6;">
      <strong style="color:var(--warn);">No data available.</strong><br>
      ${chart.notes ? escapeHtml(chart.notes) : ''}
    </div>`;
    return;
  }
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) => buildWsRowHTML(idx, s)).join('');
  wireWsRows(c, sers, renderMattsViewSeriesRows, drawMattsViewChart);
}

// Mini multi-line preview for a Labor Monitor tile. Routes through the SAME
// pipeline as the detail (ensureMattsViewSeries -> buildAxisDatasets), so the
// thumbnail shows the same series, the same moving-average / lag / magnify
// settings, the same period, and the same auto multi-axis GROUPING (series that
// share an axis share a scale, preserving their true relative positions) — a
// thumbnail rendition of exactly the chart that opens on click. Earlier this
// forked its own raw-data path (no MA, each series stretched to full height,
// points spaced by index not time), so thumbnails didn't match the detail.
function drawMiniMultiChart(cv, chart, period) {
  if (!cv) return;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.offsetWidth || 240, h = cv.offsetHeight || 60;
  cv.width = Math.max(1, Math.round(w * dpr));
  cv.height = Math.max(1, Math.round(h * dpr));
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const sers = ensureMattsViewSeries(chart);
  const built = buildAxisDatasets(sers, period, s => seriesByName(s.name), s => s.name);
  if (!built || !built.datasets.length) return;
  const pad = 3;
  // Per-axis y-range: datasets sharing a yAxisId share a scale (mirrors the
  // detail's per-axis auto-fit); x is a single shared time range across all.
  const yr = {};
  let xMin = Infinity, xMax = -Infinity;
  built.datasets.forEach(ds => {
    const id = ds.yAxisId || 'y';
    const r = yr[id] || { lo: Infinity, hi: -Infinity };
    ds.data.forEach(p => {
      const v = p[1]; if (v == null || !isFinite(v)) return;
      if (v < r.lo) r.lo = v; if (v > r.hi) r.hi = v;
      if (p[0] < xMin) xMin = p[0]; if (p[0] > xMax) xMax = p[0];
    });
    yr[id] = r;
  });
  const xrng = (xMax - xMin) || 1;
  built.datasets.forEach(ds => {
    if (!ds.data || ds.data.length < 2) return;
    const r = yr[ds.yAxisId || 'y'];
    const yrng = (r.hi - r.lo) || 1;
    ctx.beginPath();
    let started = false;
    ds.data.forEach(p => {
      const v = p[1]; if (v == null || !isFinite(v)) return;
      const x = pad + ((p[0] - xMin) / xrng) * (w - 2 * pad);
      const y = (h - pad) - ((v - r.lo) / yrng) * (h - 2 * pad);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = ds.color || WS_PALETTE[0];
    ctx.lineWidth = 1.3; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.setLineDash(ds.dash && ds.dash.length ? ds.dash : []);
    ctx.stroke();
  });
  ctx.setLineDash([]);
}

function renderMattsView(m) {
  const charts = D.matts_view || [];
  if (!charts.length) {
    m.innerHTML = '<div class="section-h"><h1>Labor Monitor</h1></div><p class="muted">No charts configured.</p>';
    return;
  }

  // ---- GRID MODE: thumbnail tiles (like the dashboard home view) ----
  if (!state.mattsViewChart) {
    const totalMissing = charts.filter(c => !c.series.length).length;
    let html = `
      <div class="section-h">
        <div>
          <h1>Labor Monitor</h1>
          <div class="ticker-row">
            <span>${charts.length} labor-market panels</span>
            ${totalMissing ? `<span style="color:var(--warn);">${totalMissing} with data gaps</span>` : ''}
          </div>
        </div>
        <span class="breadcrumb">Labor Monitor</span>
      </div>
      <p class="section-desc"><strong>Labor Monitor</strong> — a fixed labor-market board. Click any chart to open it full-size with the full Workspace controls (scaling, MA, lag, axes).</p>
      <div class="mv-grid">`;
    charts.forEach(c => {
      const missing = !c.series.length;
      html += `<div class="mv-tile ${missing ? 'missing' : ''}" data-mvid="${escapeAttr(c.id)}" title="${escapeAttr(c.subtitle || c.title)}">
        <div class="mv-tile-title">${escapeHtml(c.title)}</div>
        <div class="mv-tile-sub">${escapeHtml(c.subtitle || '')}</div>
        <canvas class="mv-tile-cv" data-mvid="${escapeAttr(c.id)}"></canvas>
        <div class="mv-tile-foot">${missing ? '<span class="gap">⊘ no data</span>' : (c.series.length + ' series')}</div>
      </div>`;
    });
    html += `</div>`;
    m.innerHTML = html;
    m.querySelectorAll('.mv-tile').forEach(t => t.onclick = () => navMattsView(t.dataset.mvid));
    m.querySelectorAll('canvas.mv-tile-cv').forEach(cv => {
      const c = getMattsChart(cv.dataset.mvid);
      if (c) drawMiniMultiChart(cv, c, state.period);
    });
    return;
  }

  // ---- DETAIL MODE: full chart for the selected tile ----
  const chart = getMattsChart(state.mattsViewChart) || charts[0];
  const notesHtml = chart.notes
    ? `<div class="mv-notes" style="margin:8px 0 12px;padding:8px 12px;background:rgba(251,191,36,0.06);border-left:2px solid var(--warn);font-size:11px;color:var(--text-2);">
        <strong style="color:var(--warn);">Data gap:</strong> ${escapeHtml(chart.notes)}
       </div>`
    : '';

  let html = `
    <div class="section-h">
      <div>
        <h1>${escapeHtml(chart.title)}</h1>
        ${chart.subtitle ? `<div class="ticker-row"><span>${escapeHtml(chart.subtitle)}</span></div>` : ''}
      </div>
      <span class="breadcrumb"><a id="mv-back">Labor Monitor</a> / <span style="color:var(--text-2);">${escapeHtml(chart.title)}</span></span>
    </div>
    ${notesHtml}

    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ensureMattsViewSeries(chart)),
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: !!state.mattsViewShowTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
      extraRight: `<button class="pbtn" data-act="mv-grid" title="Back to all charts">⊞ All charts</button>`,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas"><canvas id="big-chart"></canvas></div>
    </div>

    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Customize series · MA / Lag / Style / Scale / Magnify</span>
        <span class="ws-actions">
          <button id="mv-show-all">Show all</button>
          <button id="mv-hide-all">Hide all</button>
          <button id="mv-reset-series">Reset</button>
        </span>
      </div>
      <div id="mv-series-rows"></div>
    </div>
  `;
  m.innerHTML = html;

  m.querySelector('#mv-back').onclick = () => navMattsView();
  wireWsControlsBar(m, {
    period: (p) => { state.period = p; renderMattsView(m); },
    'mv-grid': () => navMattsView(),
    'auto-scale': () => { applyAutoScaleOnSers(ensureMattsViewSeries(chart)); renderMattsViewSeriesRows(); drawMattsViewChart(); },
    'equalize':   () => { applyEqualizeOnSers(ensureMattsViewSeries(chart)); renderMattsViewSeriesRows(); drawMattsViewChart(); },
    'share-left': () => { applyShareLeftOnSers(ensureMattsViewSeries(chart)); renderMattsViewSeriesRows(); drawMattsViewChart(); },
    'toggle-tickers': () => { state.mattsViewShowTickers = !state.mattsViewShowTickers; renderMattsView(m); },
    'copy-tickers': () => copyTickersFromSers(ensureMattsViewSeries(chart)),
    'export-panel': () => exportSersAsPanel(ensureMattsViewSeries(chart), `Labor Monitor — ${chart.title}`),
    'export-png': () => exportChartPng(m, `Labor Monitor — ${chart.title}`),
  });
  m.querySelector('#mv-show-all').onclick = () => {
    ensureMattsViewSeries(chart).forEach(s => s.visible = true);
    renderMattsViewSeriesRows(); drawMattsViewChart();
  };
  m.querySelector('#mv-hide-all').onclick = () => {
    ensureMattsViewSeries(chart).forEach(s => s.visible = false);
    renderMattsViewSeriesRows(); drawMattsViewChart();
  };
  m.querySelector('#mv-reset-series').onclick = () => {
    delete state.mattsViewSeries[chart.id];
    renderMattsViewSeriesRows(); drawMattsViewChart();
  };

  renderMattsViewSeriesRows();
  drawMattsViewChart();
}

function renderPanelsCombo(m) {
  const selIds = (state.panelsSelected || []).slice();
  const customById = {};
  loadCustomPanels().forEach(p => customById[p.id] = p);
  const items = selIds.map(id => D.panels.find(p => p.id === id) || customById[id]).filter(Boolean);
  if (items.length < 2) {
    m.innerHTML = '<div class="section-h"><h1>Combined Panels</h1><span class="breadcrumb"><a id="bc-panels">Panels</a> / <span style="color:var(--text-2);">combined</span></span></div>' +
      '<div class="ws-empty-state">' +
        '<p class="section-desc">Select 2+ panels in the Panels board first.</p>' +
        '<button class="pbtn" id="pc-empty-go">Go to Panels board →</button>' +
      '</div>';
    const link = m.querySelector('#bc-panels'); if (link) link.onclick = navPanelsIndex;
    const go = m.querySelector('#pc-empty-go'); if (go) go.onclick = navPanelsIndex;
    return;
  }
  const sers = ensurePanelsComboSeries();
  const panelNames = items.map(p => p.custom ? '★ ' + p.name : p.name).join(', ');

  let html = `
    <div class="section-h">
      <div>
        <h1>Combined Panels (${items.length})</h1>
        <div class="ticker-row"><span>${sers.length} unique indicators</span><span>${escapeHtml(panelNames)}</span></div>
      </div>
      <span class="breadcrumb"><a id="bc-panels">Panels</a> / <span style="color:var(--text-2);">combined</span></span>
    </div>
    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ensurePanelsComboSeries()),
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: state.panelsComboShowTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
      extraRight: `<button class="pbtn" data-act="back-to-panels" title="Return to the Panels board">← Back to Panels</button>`,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas"><canvas id="big-chart"></canvas></div>
    </div>

    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Customize series · MA / Lag / Style / Scale / Magnify</span>
        <span class="ws-actions">
          <button id="pc-show-all">Show all</button>
          <button id="pc-hide-all">Hide all</button>
          <button id="pc-reset-series">Reset</button>
        </span>
      </div>
      <div id="pc-series-rows"></div>
    </div>
  `;
  m.innerHTML = html;
  m.querySelector('#bc-panels').onclick = navPanelsIndex;
  wireWsControlsBar(m, {
    period: (p) => { state.period = p; renderPanelsCombo(m); },
    'auto-scale': () => { applyAutoScaleOnSers(ensurePanelsComboSeries()); renderPanelsComboSeriesRows(); drawPanelsComboChart(); },
    'equalize': () => { applyEqualizeOnSers(ensurePanelsComboSeries()); renderPanelsComboSeriesRows(); drawPanelsComboChart(); },
    'share-left': () => { applyShareLeftOnSers(ensurePanelsComboSeries()); renderPanelsComboSeriesRows(); drawPanelsComboChart(); },
    'toggle-tickers': () => { state.panelsComboShowTickers = !state.panelsComboShowTickers; renderPanelsCombo(m); },
    'copy-tickers': () => copyTickersFromSers(ensurePanelsComboSeries()),
    'export-panel': () => exportSersAsPanel(ensurePanelsComboSeries(), `Combined ${items.length} panels`),
    'export-png': () => exportChartPng(m, `Combined ${items.length} panels`),
    'back-to-panels': () => navPanelsIndex(),
  });
  m.querySelector('#pc-show-all').onclick = () => {
    ensurePanelsComboSeries().forEach(s => s.visible = true);
    renderPanelsComboSeriesRows(); drawPanelsComboChart();
  };
  m.querySelector('#pc-hide-all').onclick = () => {
    ensurePanelsComboSeries().forEach(s => s.visible = false);
    renderPanelsComboSeriesRows(); drawPanelsComboChart();
  };
  m.querySelector('#pc-reset-series').onclick = () => {
    state.panelsComboSeries = null;
    renderPanelsComboSeriesRows(); drawPanelsComboChart();
  };

  renderPanelsComboSeriesRows();
  drawPanelsComboChart();
}

// Generic export-as-custom-panel helper — works on any sers array.
// For sers where s.name doesn't resolve in D.indicators (e.g., PCE rows whose
// "name" is just a path segment), fall back to looking up by ticker.
async function exportSersAsPanel(sers, defaultName) {
  if (!sers || !sers.length) { showToast('No series to export', 'warn'); return; }
  // Build ticker -> indicator-name index once for any ticker fallbacks.
  const tickerToName = {};
  Object.entries(D.indicators).forEach(([n, e]) => { if (e.t) tickerToName[e.t] = n; });
  const resolved = sers.map(s => {
    let name = s.name;
    // If name doesn't resolve in catalog but ticker does, swap in the catalog name
    if (!D.indicators[name] && s.ticker && tickerToName[s.ticker]) name = tickerToName[s.ticker];
    return { ...s, name };
  }).filter(s => D.indicators[s.name]);  // drop anything still unresolved
  if (!resolved.length) { showToast('No exportable series (no catalog match)', 'warn'); return; }

  const name = await inAppPrompt('Custom panel name:', defaultName || `Custom panel`);
  if (!name) return;
  const panel = {
    id: 'custom_' + Date.now(),
    name, custom: true,
    description: `Saved from chart view (${resolved.length} indicators)`,
    indicators: resolved.map(s => ({
      name: s.name, visible: s.visible, color: s.color,
      maType: s.maType || 'none', maPeriod: s.maPeriod || 0,
      lag: s.lag || 0, lineStyle: s.lineStyle || 'solid', lineWidth: s.lineWidth || 1.6,
      scale: s.scale, magnify: s.magnify, fill: false,
    })),
    period: state.period, showTickers: false,
  };
  const all = loadCustomPanels();
  all.push(panel);
  if (saveCustomPanels(all)) showToast(`Saved "${name}" to Panels (${resolved.length})`, 'ok');
  else showToast('Save failed', 'err');
}

// ============== GLOBAL INDICATOR MULTI-SELECT ==============
// Cross-theme indicator selection: any tile across the app can be ticked,
// and the floating bar offers a "Display together" action that opens a
// dedicated combo view with full Workspace-style per-series controls.

function toggleIndicatorSelection(ind, checked) {
  state.indicatorsSelected = state.indicatorsSelected || [];
  const i = state.indicatorsSelected.indexOf(ind);
  if (checked && i < 0) state.indicatorsSelected.push(ind);
  else if (!checked && i >= 0) state.indicatorsSelected.splice(i, 1);
  // Drop combo per-series cache so a new state reflects the latest selection
  state.indicatorsComboSeries = null;
  renderFloatingBar();
}

function clearIndicatorSelection() {
  state.indicatorsSelected = [];
  state.indicatorsComboSeries = null;
  renderFloatingBar();
}

// Wire up checkbox handlers on indicator tiles inside any container.
// Call this after rendering tiles. tileSelector is e.g. '.indicator-tile' or '.hero-tile'.
function wireIndicatorTileSelection(container, tileSelector) {
  container.querySelectorAll(tileSelector).forEach(tile => {
    const ind = tile.dataset.ind;
    if (!ind) return;
    const cb = tile.querySelector('.ind-select');
    if (!cb) return;
    cb.onclick = (e) => {
      e.stopPropagation();
      toggleIndicatorSelection(ind, cb.checked);
      tile.classList.toggle('selected', cb.checked);
    };
  });
}

// Build the checkbox HTML to drop into a tile.
function indSelectCheckbox(ind) {
  const sel = (state.indicatorsSelected || []).includes(ind);
  return `<input type="checkbox" class="ind-select" data-ind="${escapeAttr(ind)}" ${sel?'checked':''} title="Select for combined display">`;
}

function navIndicatorsCombo() {
  state = {...state, view:'indicators_combo', theme:null, category:null, indicator:null, panel:null};
  renderLeftRail(); renderMain(); renderRightRail();
}

// Lazily build per-series settings for the combo view, seeded from the global selection.
function ensureIndicatorsComboSeries() {
  state.indicatorsSelected = state.indicatorsSelected || [];
  if (!state.indicatorsComboSeries
      || state.indicatorsComboSeries.length !== state.indicatorsSelected.length
      || state.indicatorsComboSeries.some((s, i) => s.name !== state.indicatorsSelected[i])) {
    const prior = {};
    (state.indicatorsComboSeries || []).forEach(s => { prior[s.name] = s; });
    state.indicatorsComboSeries = state.indicatorsSelected.map((ind, i) =>
      normalizeWsSettings(prior[ind] || { name: ind, ticker: D.indicators[ind]?.t || '' }, i)
    );
  } else {
    state.indicatorsComboSeries.forEach((s, i) => normalizeWsSettings(s, i));
  }
  return state.indicatorsComboSeries;
}

let _indicatorsComboChart = null;
function drawIndicatorsComboChart() {
  const cv = $('big-chart');
  if (!cv) return;
  if (_indicatorsComboChart) _indicatorsComboChart.destroy();
  const sers = ensureIndicatorsComboSeries();
  const built = buildAxisDatasets(sers, state.period, s => seriesByName(s.name), s => s.name);
  if (!built) return;
  _indicatorsComboChart = new MacroChart(cv, {
    datasets: built.datasets, yAxes: built.yAxes,
    showTickers: !!state.indicatorsComboShowTickers,
    onTickerPanelClick: () => copyTickersFromSers(sers),
    onLegendClick: (srcIdx, { isolate }) => {
      const s = sers[srcIdx]; if (!s) return;
      if (isolate) {
        const onlyMe = sers.every((x, i) => (i === srcIdx) === !!x.visible);
        sers.forEach(x => { x.visible = true; });
        if (!onlyMe) sers.forEach((x, i) => { x.visible = (i === srcIdx); });
      } else { s.visible = !s.visible; }
      renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart();
    },
  });
}

function renderIndicatorsComboSeriesRows() {
  const c = $('ic-series-rows');
  if (!c) return;
  const sers = ensureIndicatorsComboSeries();
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) =>
    buildWsRowHTML(idx, s, { removable: true, removeTitle: 'Remove from selection' })
  ).join('');
  wireWsRows(c, sers, renderIndicatorsComboSeriesRows, drawIndicatorsComboChart, (idx) => {
    const removed = sers[idx].name;
    sers.splice(idx, 1);
    const gi = state.indicatorsSelected.indexOf(removed);
    if (gi >= 0) state.indicatorsSelected.splice(gi, 1);
    renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart(); renderFloatingBar();
  });
}

function renderIndicatorsCombo(m) {
  const sel = state.indicatorsSelected || [];
  if (sel.length < 2) {
    m.innerHTML = `
      <div class="section-h"><h1>Combined Indicators</h1>
        <span class="breadcrumb"><a id="bc-home">Home</a> / <span style="color:var(--text-2);">combined indicators</span></span></div>
      <div class="ws-empty-state">
        <p class="section-desc">Select 2+ indicators from any tile across the app, then click "Display together" in the floating bar.</p>
        <button class="pbtn" id="ic-empty-go">Go to Home to pick indicators →</button>
      </div>`;
    const link = m.querySelector('#bc-home'); if (link) link.onclick = navHome;
    const go = m.querySelector('#ic-empty-go'); if (go) go.onclick = navHome;
    return;
  }

  let html = `
    <div class="section-h">
      <div>
        <h1>Combined Indicators (${sel.length})</h1>
        <div class="ticker-row"><span>cross-theme selection</span><span>full Workspace controls</span></div>
      </div>
      <span class="breadcrumb"><a id="bc-home">Home</a> / <span style="color:var(--text-2);">combined indicators</span></span>
    </div>
    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ensureIndicatorsComboSeries()),
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: state.indicatorsComboShowTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
      extraRight: `<button class="pbtn" data-act="clear-all" title="Clear the global indicator selection">Clear all</button>`,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas"><canvas id="big-chart"></canvas></div>
    </div>

    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Customize series · MA / Lag / Style / Scale / Magnify</span>
        <span class="ws-actions">
          <button id="ic-show-all">Show all</button>
          <button id="ic-hide-all">Hide all</button>
          <button id="ic-reset-series">Reset</button>
        </span>
      </div>
      <div id="ic-series-rows"></div>
    </div>
  `;
  m.innerHTML = html;
  m.querySelector('#bc-home').onclick = navHome;
  wireWsControlsBar(m, {
    period: (p) => { state.period = p; renderIndicatorsCombo(m); },
    'auto-scale': () => { applyAutoScaleOnSers(ensureIndicatorsComboSeries()); renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart(); },
    'equalize': () => { applyEqualizeOnSers(ensureIndicatorsComboSeries()); renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart(); },
    'share-left': () => { applyShareLeftOnSers(ensureIndicatorsComboSeries()); renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart(); },
    'toggle-tickers': () => { state.indicatorsComboShowTickers = !state.indicatorsComboShowTickers; renderIndicatorsCombo(m); },
    'copy-tickers': () => copyTickersFromSers(ensureIndicatorsComboSeries()),
    'export-panel': () => exportSersAsPanel(ensureIndicatorsComboSeries(), `Combined ${sel.length} indicators`),
    'export-png': () => exportChartPng(m, `Combined ${sel.length} indicators`),
    'clear-all': async () => {
      if (!(await inAppConfirm('Clear all selected indicators?', 'Clear'))) return;
      clearIndicatorSelection(); renderMain();
    },
  });
  m.querySelector('#ic-show-all').onclick = () => {
    ensureIndicatorsComboSeries().forEach(s => s.visible = true);
    renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart();
  };
  m.querySelector('#ic-hide-all').onclick = () => {
    ensureIndicatorsComboSeries().forEach(s => s.visible = false);
    renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart();
  };
  m.querySelector('#ic-reset-series').onclick = () => {
    state.indicatorsComboSeries = null;
    renderIndicatorsComboSeriesRows(); drawIndicatorsComboChart();
  };

  renderIndicatorsComboSeriesRows();
  drawIndicatorsComboChart();
}

// Per-panel-detail per-series state — keyed by panel id
function ensurePanelDetailSeries(p) {
  state.panelDetailSeries = state.panelDetailSeries || {};
  if (!state.panelDetailSeries[p.id]) {
    state.panelDetailSeries[p.id] = p.indicators.map((ind, i) => normalizeWsSettings({
      name: ind,
      ticker: D.indicators[ind]?.t || '',
      scale: 'auto',   // auto multi-axis decides; was a hardcoded dual heuristic
    }, i));
  } else {
    state.panelDetailSeries[p.id].forEach((s, i) => normalizeWsSettings(s, i));
  }
  return state.panelDetailSeries[p.id];
}

function renderPanelDetail(m) {
  const p = D.panels.find(x => x.id === state.panel);
  if (!p) { m.innerHTML = '<p class="muted">Panel not found.</p>'; return; }
  const themeLabel = D.themes.find(t => t[0] === p.theme)[1];
  state.panelsSelected = state.panelsSelected || [];
  const inCombo = state.panelsSelected.includes(p.id);
  const selN = state.panelsSelected.length;

  let html = `
    <div class="section-h detail-h">
      <div>
        <h1>${escapeHtml(p.name)}</h1>
        <div class="ticker-row">
          <span>${escapeHtml(themeLabel)}</span>
          <span>${p.indicators.length} indicators</span>
          <span>${escapeHtml(p.unit_label)}</span>
          <span>${p.axis === 'dual' ? 'Multi-axis' : 'Single axis'}</span>
        </div>
      </div>
      <span class="breadcrumb"><a id="bc-home">Home</a> / <a id="bc-panels">Panels</a> / ${escapeHtml(p.name)}</span>
    </div>
    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ensurePanelDetailSeries(p)),
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: !!state.panelDetailShowTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
      extraRight: `
        <span class="label">Comparison</span>
        <button class="pbtn ${inCombo?'active':''}" data-act="add-combo" title="${inCombo?'Remove from comparison set':'Add this panel to the comparison set'}">${inCombo ? '✓ In comparison' : '+ Add to comparison'}</button>
        <button class="pbtn ${selN<2?'dim':''}" data-act="display-together" ${selN<2?'disabled':''} title="Display ${selN} selected panel${selN!==1?'s':''} together">Display together (${selN})</button>
      `,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas"><canvas id="big-chart"></canvas></div>
    </div>

    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Customize series · MA / Lag / Style / Scale / Magnify</span>
        <span class="ws-actions">
          <button id="pd-show-all">Show all</button>
          <button id="pd-hide-all">Hide all</button>
          <button id="pd-reset-series">Reset</button>
        </span>
      </div>
      <div id="pd-series-rows"></div>
    </div>

    ${p.description ? `<div class="detail-section"><h3>What this panel shows</h3><p>${escapeHtml(p.description)}</p></div>` : ''}
    ${p.how_to_read ? `<div class="detail-section"><h3>How to read it</h3><p>${escapeHtml(p.how_to_read)}</p></div>` : ''}

    <div class="detail-section"><h3>Indicators in this panel</h3>
      <div class="indicator-grid" style="grid-template-columns:repeat(auto-fill, minmax(220px,1fr));">`;
  p.indicators.forEach(ind => {
    const e = D.indicators[ind];
    if (!e) return;
    const sel = (state.indicatorsSelected || []).includes(ind);
    html += `<div class="indicator-tile ${sel?'selected':''}" data-ind="${escapeAttr(ind)}" style="cursor:pointer;">
      ${indSelectCheckbox(ind)}
      <div class="name">${escapeHtml(ind)}</div>
      <div class="ticker">${escapeHtml(e.t)}</div>
      <div class="row">
        <span class="v">${fmtNum(e.lv,e.u)} <span style="font-size:10px;color:var(--text-3);">${escapeHtml(e.u||'')}</span></span>
        <span class="d">${e.ld}</span>
      </div>
    </div>`;
  });
  html += `</div></div>`;
  m.innerHTML = html;
  m.querySelector('#bc-home').onclick = navHome;
  m.querySelector('#bc-panels').onclick = navPanelsIndex;
  wireWsControlsBar(m, {
    period: (per) => { state.period = per; renderPanelDetail(m); },
    'auto-scale': () => { applyAutoScaleOnSers(ensurePanelDetailSeries(p)); renderPanelSeriesRows(p); drawPanelChart(p); },
    'equalize': () => { applyEqualizeOnSers(ensurePanelDetailSeries(p)); renderPanelSeriesRows(p); drawPanelChart(p); },
    'share-left': () => { applyShareLeftOnSers(ensurePanelDetailSeries(p)); renderPanelSeriesRows(p); drawPanelChart(p); },
    'toggle-tickers': () => { state.panelDetailShowTickers = !state.panelDetailShowTickers; renderPanelDetail(m); },
    'copy-tickers': () => copyTickersFromSers(ensurePanelDetailSeries(p)),
    'export-panel': () => exportSersAsPanel(ensurePanelDetailSeries(p), p.name + ' (custom)'),
    'export-png': () => exportChartPng(m, p.name),
    'add-combo': () => {
      const i = state.panelsSelected.indexOf(p.id);
      if (i >= 0) state.panelsSelected.splice(i, 1);
      else state.panelsSelected.push(p.id);
      renderPanelDetail(m); renderFloatingBar();
    },
    'display-together': () => { if (state.panelsSelected.length >= 2) navPanelsCombo(); },
  });
  m.querySelector('#pd-show-all').onclick = () => {
    ensurePanelDetailSeries(p).forEach(s => s.visible = true);
    renderPanelSeriesRows(p); drawPanelChart(p);
  };
  m.querySelector('#pd-hide-all').onclick = () => {
    ensurePanelDetailSeries(p).forEach(s => s.visible = false);
    renderPanelSeriesRows(p); drawPanelChart(p);
  };
  m.querySelector('#pd-reset-series').onclick = () => {
    delete state.panelDetailSeries[p.id];
    renderPanelDetail(m);
  };
  m.querySelectorAll('.indicator-tile').forEach(el => el.onclick = (e) => {
    if (e.target.classList.contains('ind-select')) return;
    navIndicator(el.dataset.ind);
  });
  wireIndicatorTileSelection(m, '.indicator-tile');
  renderPanelSeriesRows(p);
  drawPanelChart(p);
}

function renderPanelSeriesRows(p) {
  const c = $('pd-series-rows');
  if (!c) return;
  const sers = ensurePanelDetailSeries(p);
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) => buildWsRowHTML(idx, s)).join('');
  wireWsRows(c, sers, () => renderPanelSeriesRows(p), () => drawPanelChart(p));
}

function drawPanelChart(p) {
  const cv = $('big-chart');
  if (!cv) return;
  if (_bigChart) _bigChart.destroy();
  const sers = ensurePanelDetailSeries(p);
  const built = buildAxisDatasets(sers, state.period, s => seriesByName(s.name), s => s.name);
  if (!built) return;
  _bigChart = new MacroChart(cv, {
    datasets: built.datasets, yAxes: built.yAxes,
    showTickers: !!state.panelDetailShowTickers,
    onTickerPanelClick: () => copyTickersFromSers(sers),
    onLegendClick: (srcIdx, { isolate }) => {
      const s = sers[srcIdx]; if (!s) return;
      if (isolate) {
        const onlyMe = sers.every((x, i) => (i === srcIdx) === !!x.visible);
        sers.forEach(x => { x.visible = true; });
        if (!onlyMe) sers.forEach((x, i) => { x.visible = (i === srcIdx); });
      } else { s.visible = !s.visible; }
      renderPanelSeriesRows(p); drawPanelChart(p);
    },
  });
}

// ============== PCE DASHBOARD ==============
let _pceChart = null;

function pceVariantLabel(v) { return v === 'core' ? 'Core PCE' : 'PCE'; }
function pceTransformLabel(t) { return t === 'mom' ? 'MoM %' : 'YoY %'; }

// Resolve a tree node -> the indicator-name string for the active variant/transform,
// returns null if no data available for that combination at this node.
function pceLookupIndicator(node) {
  const slot = state.pceVariant + '_' + state.pceTransform;
  return node.i && node.i[slot] ? node.i[slot] : null;
}
function pceHasData(node) {
  // Recursively check: this node OR any descendant has data for the active variant/transform
  if (pceLookupIndicator(node)) return true;
  return (node.c || []).some(pceHasData);
}

// Color palette for selected items — kept stable so chart colors match chips
const PCE_COLORS = ['#6ea8ff', '#22d3ee', '#c084fc', '#fb923c', '#a3e635', '#f472b6', '#fbbf24', '#4ade80', '#f87171', '#94a3b8'];
function pceColorFor(idx) { return PCE_COLORS[idx % PCE_COLORS.length]; }

function pceRootLabel() {
  return state.pceVariant === 'core' ? 'Core PCE' : 'PCE Deflator';
}

function renderPceDashboard(m) {
  if (state.pceSelected.length === 0 && !state._pceVisited) {
    state.pceSelected = [''];
    state._pceVisited = true;
  }
  // PCE-specific controls (variant + transform) live in the same bar via extraLeft
  const variantTransformHtml = `
    <span class="ctl-div"></span><span class="label">Variant</span>
    <span class="seg">
      <button class="pbtn ${state.pceVariant==='core'?'active':''}" data-act="pce-var-core">Core</button>
      <button class="pbtn ${state.pceVariant==='full'?'active':''}" data-act="pce-var-full">Full</button>
    </span>
    <span class="label">Transform</span>
    <span class="seg">
      <button class="pbtn ${state.pceTransform==='mom'?'active':''}" data-act="pce-tr-mom">MoM</button>
      <button class="pbtn ${state.pceTransform==='yoy'?'active':''}" data-act="pce-tr-yoy">YoY</button>
    </span>
  `;
  let html = `
    <div class="section-h">
      <h1>PCE Dashboard</h1>
      <span class="breadcrumb"><a id="bc-home">Home</a> / PCE Hierarchy · ${pceVariantLabel(state.pceVariant)} · ${pceTransformLabel(state.pceTransform)}</span>
    </div>
    <p class="section-desc">Browse the BEA PCE hierarchy. Use the right-rail tree to toggle indicators on/off — root, branch, or leaf. Full Workspace controls (MA, lag, line style, scale, magnify) apply per series.</p>
    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ensurePceSeriesSettings()),
      extraLeft: variantTransformHtml,
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: !!state.pceShowTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas" id="pce-chart-canvas"><canvas id="pce-chart"></canvas></div>
    </div>

    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Customize series · MA / Lag / Style / Scale / Magnify</span>
        <span class="ws-actions">
          <button id="pce-show-all">Show all</button>
          <button id="pce-hide-all">Hide all</button>
          <button id="pce-clear-sel">Clear all</button>
        </span>
      </div>
      <div id="pce-series-rows"></div>
    </div>
  `;
  m.innerHTML = html;
  const bcH = m.querySelector('#bc-home'); if (bcH) bcH.onclick = navHome;
  wireWsControlsBar(m, {
    period: (p) => { state.period = p; drawPceChart();
      m.querySelectorAll('.ws-controls-bar .pbtn[data-p]').forEach(x =>
        x.classList.toggle('active', x.dataset.p === state.period));
    },
    // Variant/Transform flips change the ticker resolved at each path but keep the same paths,
    // so per-series settings (color, MA, lag, style, scale, magnify) persist.
    'pce-var-core': () => { state.pceVariant = 'core'; renderPceDashboard(m); renderRightRail(); },
    'pce-var-full': () => { state.pceVariant = 'full'; renderPceDashboard(m); renderRightRail(); },
    'pce-tr-mom':   () => { state.pceTransform = 'mom'; renderPceDashboard(m); renderRightRail(); },
    'pce-tr-yoy':   () => { state.pceTransform = 'yoy'; renderPceDashboard(m); renderRightRail(); },
    'auto-scale': () => { applyAutoScaleOnSers(ensurePceSeriesSettings()); renderPceSeriesRows(); drawPceChart(); },
    'equalize': () => { applyEqualizeOnSers(ensurePceSeriesSettings()); renderPceSeriesRows(); drawPceChart(); },
    'share-left': () => { applyShareLeftOnSers(ensurePceSeriesSettings()); renderPceSeriesRows(); drawPceChart(); },
    'toggle-tickers': () => { state.pceShowTickers = !state.pceShowTickers; renderPceDashboard(m); },
    'copy-tickers': () => copyTickersFromSers(ensurePceSeriesSettings()),
    'export-panel': () => exportSersAsPanel(ensurePceSeriesSettings(), `PCE ${pceVariantLabel(state.pceVariant)} ${pceTransformLabel(state.pceTransform)}`),
    'export-png': () => exportChartPng(m, `PCE ${pceVariantLabel(state.pceVariant)} ${pceTransformLabel(state.pceTransform)}`),
  });
  m.querySelector('#pce-show-all').onclick = () => {
    ensurePceSeriesSettings().forEach(s => s.visible = true);
    renderPceSeriesRows(); drawPceChart();
  };
  m.querySelector('#pce-hide-all').onclick = () => {
    ensurePceSeriesSettings().forEach(s => s.visible = false);
    renderPceSeriesRows(); drawPceChart();
  };
  m.querySelector('#pce-clear-sel').onclick = () => {
    state.pceSelected = []; state.pceSeriesSettings = null;
    renderRightRail(); renderPceSeriesRows(); drawPceChart();
  };
  renderPceSeriesRows();
  drawPceChart();
}

// Per-PCE-row settings, keyed by path. Cached on state.pceSeriesSettings.
// Each entry is enriched with name + ticker so it works with shared helpers.
function ensurePceSeriesSettings() {
  const sel = state.pceSelected || [];
  const slot = state.pceVariant + '_' + state.pceTransform;
  const valid = state.pceSeriesSettings
    && state.pceSeriesSettings.length === sel.length
    && state.pceSeriesSettings.every((s, i) => s.path === sel[i]);
  if (!valid) {
    const prior = {};
    (state.pceSeriesSettings || []).forEach(s => { prior[s.path] = s; });
    state.pceSeriesSettings = sel.map((path, i) => {
      const base = prior[path] || { path };
      return normalizeWsSettings(base, i);
    });
  }
  // Refresh derived ticker/name fields whenever variant/transform changes
  state.pceSeriesSettings.forEach(s => {
    const node = pceFindNode(s.path);
    const ticker = node && node.t && node.t[slot];
    s.ticker = ticker || '';
    const labelName = s.path === '' ? pceRootLabel() : s.path.split('/').slice(-1)[0];
    s.name = labelName;
  });
  return state.pceSeriesSettings;
}

function renderPceSeriesRows() {
  const c = $('pce-series-rows');
  if (!c) return;
  const sers = ensurePceSeriesSettings();
  if (!sers.length) {
    c.innerHTML = `<div class="ws-empty-state" style="padding:14px 0;">
      <div class="muted" style="font-size:11px;">No indicators selected. Use the PCE hierarchy tree on the right to toggle series on.</div>
      <button class="pbtn" id="pce-empty-focus">Focus the PCE tree →</button>
    </div>`;
    const go = c.querySelector('#pce-empty-focus');
    if (go) go.onclick = () => {
      const search = $('pce-search');
      if (search) { search.scrollIntoView({ block: 'nearest' }); search.focus(); }
      else { const tree = $('pce-tree'); if (tree) tree.scrollIntoView({ block: 'nearest' }); }
    };
    return;
  }
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) => {
    const fullPath = s.path === '' ? pceRootLabel() : s.path.replace(/\//g, ' › ');
    const enabled = !!s.ticker;
    return buildWsRowHTML(idx, s, {
      removable: true,
      removeTitle: 'Remove from selection',
      extraLabel: enabled ? '' : 'no data for this slot',
      disabled: !enabled,
    });
  }).join('');
  wireWsRows(c, sers, renderPceSeriesRows, drawPceChart, (idx) => {
    const path = sers[idx].path;
    sers.splice(idx, 1);
    const gi = state.pceSelected.indexOf(path);
    if (gi >= 0) state.pceSelected.splice(gi, 1);
    renderRightRail();
    renderPceSeriesRows(); drawPceChart();
  });
}

function renderPceTree() {
  const container = $('pce-tree');
  if (!container) return;
  const tree = D.pce_tree;
  const filter = (state.pceSearch || '').trim().toLowerCase();
  // Build a Set of path-strings whose subtree contains a match (for filter mode).
  let matchSet = null;
  if (filter) {
    matchSet = new Set();
    const walk = (node) => {
      let any = false;
      (node.c || []).forEach(c => { if (walk(c)) any = true; });
      if (node.n.toLowerCase().includes(filter)) any = true;
      if (any) matchSet.add(node.p);
      return any;
    };
    walk(tree);
  }
  let html = '';
  // Render root as a checkable node first (label depends on variant)
  html += renderPceNode(tree, 0, matchSet, /*forceLabel*/ pceRootLabel());
  container.innerHTML = html;
  // Wire handlers
  container.querySelectorAll('.twirl').forEach(el => {
    el.onclick = (e) => { e.stopPropagation(); togglePceExpand(el.dataset.path); };
  });
  container.querySelectorAll('.name-expand').forEach(el => {
    el.onclick = (e) => { e.stopPropagation(); togglePceExpand(el.dataset.path); };
  });
  container.querySelectorAll('.pce-checkbox').forEach(cb => {
    cb.onchange = () => togglePceSelect(cb.dataset.path, cb.checked);
  });
}

function renderPceNode(node, depth, matchSet, forceLabel) {
  const path = node.p;
  // In filter mode, skip nodes outside matchSet
  if (matchSet && !matchSet.has(path)) return '';
  const expanded = state.pceExpanded.includes(path) || (matchSet && matchSet.has(path));
  const hasChildren = node.c && node.c.length > 0;
  const hasIndicator = !!pceLookupIndicator(node);
  const subtreeHasData = pceHasData(node);
  const isSelected = state.pceSelected.includes(path);
  const indent = 6 + depth * 12;  // tighter indentation for narrow rail
  let cls = 'pce-node';
  if (isSelected) cls += ' selected';
  if (!subtreeHasData) cls += ' no-data';
  if (depth === 0) cls += ' root';
  const displayName = forceLabel || node.n;

  // Parent nodes: name is a sibling of <label> and acts as an expand target (P1C-16).
  // Leaf nodes: name stays inside <label> so clicking it toggles selection (unchanged).
  const nameHtml = hasChildren
    ? `<span class="name name-expand" data-path="${escapeAttr(path)}" title="Expand / collapse">${escapeHtml(displayName)}</span>`
    : `<span class="name">${escapeHtml(displayName)}</span>`;
  let html = `<div class="${cls}" data-haschildren="${hasChildren?1:0}" style="padding-left:${indent}px;">
    <span class="twirl ${hasChildren ? (expanded?'expanded':'') : 'leaf'}" data-path="${escapeAttr(path)}">${hasChildren ? '▸' : ''}</span>
    <label>
      <input type="checkbox" class="pce-checkbox" data-path="${escapeAttr(path)}" ${isSelected?'checked':''} ${!hasIndicator?'disabled':''}>
      ${hasChildren ? '' : nameHtml}
    </label>
    ${hasChildren ? nameHtml : ''}
  </div>`;
  if (hasChildren && expanded) {
    html += '<div class="pce-children">';
    node.c.forEach(child => { html += renderPceNode(child, depth + 1, matchSet, null); });
    html += '</div>';
  }
  return html;
}

function togglePceExpand(path) {
  const i = state.pceExpanded.indexOf(path);
  if (i >= 0) state.pceExpanded.splice(i, 1);
  else state.pceExpanded.push(path);
  renderPceTree();
}

function togglePceSelect(path, checked) {
  const i = state.pceSelected.indexOf(path);
  if (checked && i < 0) state.pceSelected.push(path);
  else if (!checked && i >= 0) state.pceSelected.splice(i, 1);
  // Re-render the right-rail tree, the unified series rows, and the chart.
  // (Chips bar removed — series rows now serve that role.)
  renderPceTree();
  renderPceSeriesRows();
  drawPceChart();
}

// Walk tree to find a node by path
function pceFindNode(path) {
  if (!path) return D.pce_tree;
  const parts = path.split('/');
  let node = D.pce_tree;
  for (const p of parts) {
    const child = (node.c || []).find(c => c.n === p);
    if (!child) return null;
    node = child;
  }
  return node;
}

function drawPceChart() {
  const cv = $('pce-chart');
  if (!cv) return;
  if (_pceChart) { _pceChart.destroy(); _pceChart = null; }
  const sers = ensurePceSeriesSettings();
  const built = buildAxisDatasets(
    sers.filter(s => s.ticker), state.period,
    s => seriesByTicker(s.ticker),
    s => (s.path === '' ? pceRootLabel() : s.path.split('/').slice(-1)[0])
  );
  if (!built || !built.datasets.length) {
    const wrap = $('pce-chart-canvas');
    if (wrap) wrap.innerHTML = `<canvas id="pce-chart"></canvas><div class="pce-chart-empty">No data for current selection — try a different Variant or Transform.</div>`;
    return;
  }
  if (!cv.parentElement || cv.parentElement.querySelector('.pce-chart-empty')) {
    const wrap = $('pce-chart-canvas');
    if (wrap) wrap.innerHTML = '<canvas id="pce-chart"></canvas>';
  }
  _pceChart = new MacroChart($('pce-chart'), {
    datasets: built.datasets, yAxes: built.yAxes,
    showTickers: !!state.pceShowTickers,
    onTickerPanelClick: () => copyTickersFromSers(sers),
    onLegendClick: (srcIdx, { isolate }) => {
      // PCE passes sers.filter(s=>s.ticker) into buildAxisDatasets, so srcIdx
      // indexes that FILTERED array — remap back to the live sers array.
      const filtered = sers.filter(s => s.ticker);
      const target = filtered[srcIdx]; if (!target) return;
      if (isolate) {
        const onlyMe = filtered.every(x => (x === target) === !!x.visible);
        filtered.forEach(x => { x.visible = true; });
        if (!onlyMe) filtered.forEach(x => { x.visible = (x === target); });
      } else { target.visible = !target.visible; }
      renderPceSeriesRows(); drawPceChart();
    },
  });
}

// ============== WORKSPACE — theme dashboards ==============
let _wsChart = null;

function renderWorkspace(m) {
  const themeId = state.workspace.activeTheme;
  const theme = D.workspace_themes.find(t => t.id === themeId);
  if (!theme) { m.innerHTML = '<p class="muted">Theme not found.</p>'; return; }
  const ts = state.workspace.themes[themeId];

  let html = `
    <div class="ws-tabs">
      ${D.workspace_themes.map(t => `<button class="ws-tab ${t.id===themeId?'active':''}" data-theme="${escapeAttr(t.id)}">${escapeHtml(t.name)}</button>`).join('')}
    </div>
    <div class="section-h">
      <h1>${escapeHtml(theme.name)}</h1>
      <span class="breadcrumb"><a id="bc-workspace">Workspace</a> / <span style="color:var(--text-2);">${escapeHtml(theme.name)}</span></span>
    </div>
    <p class="section-desc"><strong>Workspace</strong> — build a chart from a theme's full series set. ${escapeHtml(theme.summary)}</p>

    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ts.indicators),
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: ts.showTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
      extraRight: `<span class="label">Visible: ${ts.indicators.filter(i=>i.visible).length}/${ts.indicators.length}</span>`,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas" id="ws-chart-canvas"><canvas id="ws-chart"></canvas></div>
    </div>

    ${themeId === 'all' ? `
    <div class="ws-all-search-wrap">
      <div class="ws-series-h" style="margin-bottom:6px;">
        <span>Add indicators · search across all ${D.workspace_themes.length - 1} themes (${Object.keys(D.indicators).length} total)</span>
        <span class="ws-actions">
          <button id="ws-clear-all-selected">Clear selected</button>
        </span>
      </div>
      <input type="text" class="ws-all-search" id="ws-all-search" placeholder="Search by indicator name, ticker, or category…" value="${escapeAttr(ts.searchQuery || '')}">
      <div id="ws-all-search-results" class="ws-all-search-results"></div>
    </div>
    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Selected indicators (${ts.indicators.length}) · customize each below</span>
      </div>
      <div id="ws-series-rows"></div>
    </div>
    ` : `
    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Indicators in this theme · click to toggle, customize MA/lag/style/axis</span>
        <span class="ws-actions">
          <button id="ws-show-all">Show all</button>
          <button id="ws-hide-all">Hide all</button>
          <button id="ws-reset">Reset defaults</button>
        </span>
      </div>
      <div id="ws-series-rows"></div>
    </div>
    `}
  `;
  m.innerHTML = html;
  const bcWs = m.querySelector('#bc-workspace');
  if (bcWs) bcWs.onclick = () => navWorkspace();
  m.querySelectorAll('.ws-tab').forEach(b => b.onclick = () => {
    state.workspace.activeTheme = b.dataset.theme;
    renderWorkspace(m); renderRightRail();
  });
  wireWsControlsBar(m, {
    period: (p) => { state.period = p; renderWorkspace(m); },
    'auto-scale': () => { applyAutoScaleOnSers(ts.indicators); renderWorkspace(m); },
    'equalize': () => { applyEqualizeOnSers(ts.indicators); renderWorkspace(m); },
    'share-left': () => { applyShareLeftOnSers(ts.indicators); renderWorkspace(m); },
    'toggle-tickers': () => { ts.showTickers = !ts.showTickers; renderWorkspace(m); },
    'copy-tickers': () => copyVisibleTickers(),
    'export-panel': () => exportWorkspaceAsPanel(),
    'export-png': () => exportChartPng(m, `Workspace — ${theme.name}`),
  });
  if (themeId !== 'all') {
    m.querySelector('#ws-show-all').onclick = () => { ts.indicators.forEach(i => i.visible = true); renderWorkspace(m); renderRightRail(); };
    m.querySelector('#ws-hide-all').onclick = () => { ts.indicators.forEach(i => i.visible = false); renderWorkspace(m); renderRightRail(); };
    m.querySelector('#ws-reset').onclick = () => { initWorkspaceState(); renderWorkspace(m); renderRightRail(); };
  } else {
    m.querySelector('#ws-clear-all-selected').onclick = () => { ts.indicators = []; renderWorkspace(m); renderRightRail(); };
    const searchInput = m.querySelector('#ws-all-search');
    searchInput.addEventListener('input', () => {
      ts.searchQuery = searchInput.value;
      renderAllTabSearchResults();
    });
    renderAllTabSearchResults();
  }
  renderWorkspaceSeriesRows(themeId);
  drawWorkspaceChart();
}

function renderWorkspaceSeriesRows(themeId) {
  const c = $('ws-series-rows');
  if (!c) return;
  const ts = state.workspace.themes[themeId];
  const sers = ts.indicators;
  const isAll = themeId === 'all';
  // Unified row renderer (same controls + Auto scale option as every other surface).
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) => buildWsRowHTML(idx, s, {
    removable: isAll, removeTitle: 'Remove from All workspace',
  })).join('');
  const rerender = () => renderWorkspaceSeriesRows(themeId);
  const redraw = () => { drawWorkspaceChart(); renderRightRail(); };
  wireWsRows(c, sers, rerender, redraw, isAll ? (idx) => {
    const removed = sers.splice(idx, 1)[0];
    renderWorkspace($('main')); renderRightRail();
    if (removed) showToast(`Removed "${removed.name}"`, 'ok');
  } : null);
}

// ============== All tab — search-based picker ==============
function renderAllTabSearchResults() {
  const c = $('ws-all-search-results');
  if (!c) return;
  const ts = state.workspace.themes['all'];
  const q = (ts.searchQuery || '').trim().toLowerCase();
  if (q.length < 2) {
    c.innerHTML = '<div class="ws-all-empty">Type at least 2 characters to search across all indicators.</div>';
    return;
  }
  const selectedSet = new Set(ts.indicators.map(i => i.name));
  const matches = [];
  Object.entries(D.indicators).forEach(([name, meta]) => {
    if (selectedSet.has(name)) return;
    const nL = name.toLowerCase();
    const tL = (meta.t || '').toLowerCase();
    const cL = (meta.cl || '').toLowerCase();
    if (nL.includes(q) || tL.includes(q) || cL.includes(q)) {
      matches.push({ name, ticker: meta.t || '', category: meta.cl || '', frequency: meta.f || '' });
    }
  });
  if (!matches.length) {
    c.innerHTML = '<div class="ws-all-empty">No matches for "' + escapeHtml(q) + '".</div>';
    return;
  }
  matches.sort((a, b) => {
    const aN = a.name.toLowerCase().startsWith(q);
    const bN = b.name.toLowerCase().startsWith(q);
    if (aN !== bN) return aN ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const limit = 40;
  const shown = matches.slice(0, limit);
  let html = '';
  shown.forEach(m => {
    html += `<div class="ws-all-result" data-name="${escapeAttr(m.name)}">
      <span class="ws-all-result-add">+</span>
      <span class="ws-all-result-name">${escapeHtml(m.name)}</span>
      <span class="ws-all-result-ticker">${escapeHtml(m.ticker)}</span>
      <span class="ws-all-result-cat">${escapeHtml(m.category)} · ${escapeHtml(m.frequency)}</span>
    </div>`;
  });
  if (matches.length > limit) {
    html += `<div class="ws-all-more">${matches.length - limit} more — refine search to narrow</div>`;
  }
  c.innerHTML = html;
  c.querySelectorAll('.ws-all-result').forEach(el => el.onclick = () => addToAllTab(el.dataset.name));
}

function addToAllTab(name) {
  const ts = state.workspace.themes['all'];
  if (ts.indicators.find(i => i.name === name)) return;
  ts.indicators.push({
    name,
    visible: true,
    color: WS_PALETTE[ts.indicators.length % WS_PALETTE.length],
    lineStyle: 'solid', lineWidth: 1.6,
    maType: 'none', maPeriod: 0,
    lag: 0,
    scale: 'auto', magnify: 1,
    fill: false,
  });
  renderWorkspace($('main')); renderRightRail();
  const inp = $('ws-all-search'); if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
}

// ============== Workspace chart drawer ==============
function computeMA(data, type, period) {
  if (!data || !data.length || type === 'none' || period <= 0) return data || [];
  if (type === 'sma') {
    const out = [];
    for (let i = period - 1; i < data.length; i++) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += data[j][1];
      out.push([data[i][0], sum / period]);
    }
    return out;
  }
  if (type === 'ema') {
    const k = 2 / (period + 1);
    const out = [];
    let ema = data[0][1];
    out.push([data[0][0], ema]);
    for (let i = 1; i < data.length; i++) {
      ema = data[i][1] * k + ema * (1 - k);
      out.push([data[i][0], ema]);
    }
    return out;
  }
  return data;
}
function applyLagMonths(data, months) {
  if (!months) return data;
  return data.map(([ts, v]) => {
    const d = new Date(ts);
    d.setMonth(d.getMonth() + months);
    return [d.getTime(), v];
  });
}
function lineDashFor(style) {
  if (style === 'dashed') return [6, 4];
  if (style === 'dotted') return [2, 3];
  return [];
}

// =========== SHARED WORKSPACE-STYLE ROW HELPERS ===========
// Single source of truth for the per-series row used by Workspace, panel-detail,
// indicator-detail, indicators-combo, panels-combo, and PCE-dashboard. Every
// row gets the SAME controls: visible / color / MA / Lag / Line style / Scale L-R-Own / Magnify.

const PERIOD_DAYS_LOCAL = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365, '2Y': 730, 'ALL': 99999 };

// Apply MA + lag + magnify to a raw [date, value][] series.
// Returns { data, label, dash, mult } where label is decorated with applied transforms.
function applyWsTransforms(rawSeries, settings, period, baseLabel) {
  const days = PERIOD_DAYS_LOCAL[period] || 99999;
  let raw = rawSeries;
  if (!raw || !raw.length) return { data: [], label: baseLabel, dash: lineDashFor(settings.lineStyle), mult: 1 };
  const lag = settings.lag || 0;
  if (days < 99999) {
    const last = new Date(raw[raw.length-1][0]);
    const cutoff = new Date(last);
    cutoff.setDate(cutoff.getDate() - days - Math.abs(lag * 31));
    raw = raw.filter(d => new Date(d[0]) >= cutoff);
  }
  let data = raw.map(d => [new Date(d[0]).getTime(), d[1]]);
  const maType = settings.maType || 'none';
  const maPeriod = settings.maPeriod || 0;
  if (maType !== 'none' && maPeriod > 0) data = computeMA(data, maType, maPeriod);
  if (lag) data = applyLagMonths(data, lag);
  const magNum = parseFloat(settings.magnify);
  const mult = (isFinite(magNum) && magNum > 0) ? magNum : 1;
  if (mult !== 1) data = data.map(([x, y]) => [x, y * mult]);
  let label = baseLabel;
  if (maType !== 'none') label += ` · ${maType.toUpperCase()}${maPeriod}`;
  if (lag) label += ` · ${lag>0?'+':''}${lag}m`;
  if (mult !== 1) label += ` × ${mult}`;
  return { data, label, dash: lineDashFor(settings.lineStyle || 'solid'), mult };
}

// Decide the y-axis assignment for a series and update the running yAxesConfig.
// Returns { yAxisId, ownIncremented }. Mutates: yAxesConfig, axisFlags.
function assignWsAxis(s, axisFlags, yAxesConfig) {
  if (s.scale === 'left') { axisFlags.hasLeft = true; return { yAxisId: 'y' }; }
  if (s.scale === 'right') {
    axisFlags.hasRight = true;
    yAxesConfig.y2 = { position: 'right' };
    return { yAxisId: 'y2' };
  }
  if (s.scale === 'own') {
    axisFlags.ownCounter = (axisFlags.ownCounter || 0) + 1;
    const id = 'own' + axisFlags.ownCounter;
    yAxesConfig[id] = { position: 'left-own', color: s.color };
    return { yAxisId: id };
  }
  axisFlags.hasLeft = true;
  return { yAxisId: 'y' };
}

// ===== AUTOMATIC MULTI-AXIS SCALING =====
// Goal: when series in one chart are magnitudes apart, put them on separate
// auto-fit axes so every series' MOVEMENTS are visible at a comparable visual
// amplitude; when series are of similar scale, keep them on a SHARED axis so
// their true relationship (levels, gaps) is preserved.
//
// Greedy agglomerative clustering on the visible value band [lo,hi]: two
// clusters may merge only if the merged span <= K × the smallest member span
// (i.e. no member would occupy < 1/K of the shared height and "look flat").
// K=10 keeps same-domain series together (e.g. U3 & U6) while separating
// order-of-magnitude differences (e.g. payrolls vs unemployment rate).
function clusterByVisibility(items, K) {
  let clusters = items.map(it => ({ items: [it], lo: it.lo, hi: it.hi, minSpan: it.span }));
  while (clusters.length > 1) {
    let bi = -1, bj = -1, bestSpan = Infinity, bestLo = 0, bestHi = 0, bestMin = 0;
    for (let i = 0; i < clusters.length; i++) {
      for (let j = i + 1; j < clusters.length; j++) {
        const lo = Math.min(clusters[i].lo, clusters[j].lo);
        const hi = Math.max(clusters[i].hi, clusters[j].hi);
        const span = hi - lo;
        const minSpan = Math.min(clusters[i].minSpan, clusters[j].minSpan);
        if (span <= K * minSpan && span < bestSpan) {
          bestSpan = span; bi = i; bj = j; bestLo = lo; bestHi = hi; bestMin = minSpan;
        }
      }
    }
    if (bi < 0) break;
    const merged = { items: clusters[bi].items.concat(clusters[bj].items), lo: bestLo, hi: bestHi, minSpan: bestMin };
    clusters = clusters.filter((_, k) => k !== bi && k !== bj);
    clusters.push(merged);
  }
  return clusters;
}

// Build {datasets, yAxes} for a list of per-series settings, applying transforms
// (MA/lag/magnify via applyWsTransforms) and AUTO multi-axis assignment.
//   getRaw(s)     -> raw [[date,val],...] for the series
//   baseLabel(s)  -> base label string
// Series with scale 'left'/'right'/'own' are honored as manual overrides;
// scale 'auto' (the default) is clustered + assigned to shared/separate axes.
function buildAxisDatasets(sers, period, getRaw, baseLabel) {
  const vis = [];
  // Iterate WITH the original index so each dataset can carry srcIdx (the host
  // sers index). vis is a compacted subsequence (hidden + zero-length skipped),
  // so the positional index would not match the host array — capture i here.
  (sers || []).forEach((s, i) => {
    if (!s.visible) return;
    const tx = applyWsTransforms(getRaw(s), s, period, baseLabel(s));
    if (!tx.data.length) return;
    let lo = Infinity, hi = -Infinity;
    tx.data.forEach(d => { if (d[1] < lo) lo = d[1]; if (d[1] > hi) hi = d[1]; });
    const span = Math.max(hi - lo, Math.abs(hi) * 1e-9, 1e-12);
    vis.push({ s, srcIdx: i, tx, lo, hi, span });
  });
  if (!vis.length) return null;

  const yAxes = {};
  let hasLeft = false, hasRight = false, ownN = 0;
  const claimRight = () => { hasRight = true; yAxes.y2 = { position: 'right' }; return 'y2'; };
  const claimOwn = (color) => { ownN++; const id = 'own' + ownN; yAxes[id] = { position: 'left-own', color }; return id; };

  // Manual overrides first
  vis.forEach(it => {
    const sc = it.s.scale || 'auto';
    if (sc === 'left') { it.axisId = 'y'; hasLeft = true; }
    else if (sc === 'right') { it.axisId = claimRight(); }
    else if (sc === 'own') { it.axisId = claimOwn(it.s.color); }
  });

  // Auto series → cluster by magnitude, assign each cluster a shared axis
  const auto = vis.filter(it => (it.s.scale || 'auto') === 'auto');
  if (auto.length) {
    // K=15: merge series whose smallest member still occupies >= ~1/15 of the
    // shared height. Keeps same-magnitude series together (e.g. U3 & U6, which
    // have a modest level gap) while separating order-of-magnitude differences
    // (e.g. claims ~230 amplitude vs PMI ~8) that would otherwise look flat.
    const clusters = clusterByVisibility(auto, 15);
    clusters.sort((a, b) => (b.items.length - a.items.length) || ((b.hi - b.lo) - (a.hi - a.lo)));
    clusters.forEach(cl => {
      let axisId;
      if (!hasLeft) { axisId = 'y'; hasLeft = true; }
      else if (!hasRight) { axisId = claimRight(); }
      else { axisId = claimOwn(cl.items[0].s.color); }
      cl.items.forEach(it => { it.axisId = axisId; });
    });
  }
  if (hasLeft) yAxes.y = { position: 'left' };
  if (!Object.keys(yAxes).length) yAxes.y = { position: 'left' };

  // How many distinct axes ended up in play (for labeling hints)
  const multiAxis = Object.keys(yAxes).length > 1;
  const datasets = vis.map(it => {
    let label = it.tx.label;
    if (multiAxis) {
      if (it.axisId === 'y2') label += ' · R';
      else if (it.axisId && it.axisId.startsWith('own')) label += ' · ' + it.axisId.replace('own', 'ax');
    }
    return {
      label, data: it.tx.data, color: it.s.color,
      borderWidth: 1.6, pointRadius: pointRadiusFor(it.tx.data.length),
      fill: false, yAxisId: it.axisId || 'y', dash: it.tx.dash,
      unitLabel: (it.s.name && D.indicators[it.s.name]?.u) || '',
      ticker: it.s.ticker || (it.s.name && D.indicators[it.s.name]?.t) || '',
      srcIdx: it.srcIdx,   // host sers index (legend dispatch → onLegendClick)
      mult: it.tx.mult,    // magnify multiplier (tooltip de-fictionalizes via this)
    };
  });
  return { datasets, yAxes };
}

// Build full HTML for ONE workspace-style row.
// opts: { extraLabel?: string, removable?: bool, removeTitle?: string,
//         disabled?: bool, showLineWidth?: bool }
// Non-interactive column-header row, aligned to the same 8-col grid as buildWsRowHTML.
// Rows have 7 children (checkbox·color·name·MA·Lag·Style·scale-group) in an 8-col grid;
// the scale-group (Axis select + × input + trailing button) occupies one cell, so the
// last label is a combined "Axis · ×" over that cell and the trailing cell stays blank.
function buildWsRowHeaderHTML() {
  return `<div class="ws-series-row ws-row-head" aria-hidden="true">
    <span></span><span></span><span></span>
    <span>MA</span><span>Lag</span><span>Style</span><span>Axis · ×</span><span></span>
  </div>`;
}

function buildWsRowHTML(idx, s, opts = {}) {
  const cls = s.visible ? 'visible' : 'invisible';
  // Non-default markers — tint the control border when its value differs from the normalizeWsSettings default.
  const maND    = (s.maType && s.maType !== 'none') ? ' ws-nondefault' : '';
  const lagND   = (s.lag && s.lag !== 0) ? ' ws-nondefault' : '';
  const styleND = (s.lineStyle && s.lineStyle !== 'solid') ? ' ws-nondefault' : '';
  const scaleND = (s.scale && s.scale !== 'auto') ? ' ws-nondefault' : '';
  const magND   = (s.magnify !== undefined && s.magnify !== 1) ? ' ws-nondefault' : '';
  const colorBorder = s.visible ? `border-left-color:${s.color};` : '';
  const tkr = s.ticker || (s.name && D.indicators[s.name]?.t) || '';
  const tickerSpan = tkr ? `<span style="color:var(--text-3);font-size:10px;">${escapeHtml(tkr)}</span>` : '';
  const extraLabel = opts.extraLabel ? `<span style="color:var(--text-3);font-size:10px;">${escapeHtml(opts.extraLabel)}</span>` : '';
  const dis = opts.disabled ? 'disabled' : '';
  // Trailing button: removable rows get a destructive ✕ (ws-row-remove, --neg);
  // non-removable rows get the neutral magnify-reset ↻ (ws-mag-reset).
  const trailingBtn = opts.removable
    ? `<button class="ws-row-remove" data-rm="${idx}" title="${escapeAttr(opts.removeTitle || 'Remove')}">✕</button>`
    : `<button class="ws-mag-reset" data-magreset="${idx}" title="Reset multiplier to auto">↻</button>`;
  const dispName = opts.displayName || s.name;
  return `<div class="ws-series-row ${cls}" style="${colorBorder}">
    <input type="checkbox" data-idx="${idx}" ${s.visible?'checked':''} ${dis} title="Show/hide on chart">
    <span class="ws-color" data-idx="${idx}" style="background:${s.color};" title="Click to cycle · right-click for palette"></span>
    <span class="ws-name" title="${escapeAttr(dispName)}">${escapeHtml(dispName)} ${tickerSpan} ${extraLabel}</span>
    <select class="ws-ma${maND}" data-idx="${idx}" title="Moving average" ${dis}>
      <option value="none:0" ${(!s.maType||s.maType==='none')?'selected':''}>No MA</option>
      <option value="sma:3" ${s.maType==='sma'&&s.maPeriod===3?'selected':''}>SMA 3</option>
      <option value="sma:6" ${s.maType==='sma'&&s.maPeriod===6?'selected':''}>SMA 6</option>
      <option value="sma:12" ${s.maType==='sma'&&s.maPeriod===12?'selected':''}>SMA 12</option>
      <option value="ema:12" ${s.maType==='ema'&&s.maPeriod===12?'selected':''}>EMA 12</option>
      <option value="ema:26" ${s.maType==='ema'&&s.maPeriod===26?'selected':''}>EMA 26</option>
    </select>
    <select class="ws-lag${lagND}" data-idx="${idx}" title="Time-shift (months)" ${dis}>
      <option value="-24" ${s.lag===-24?'selected':''}>−24m</option>
      <option value="-12" ${s.lag===-12?'selected':''}>−12m</option>
      <option value="-6" ${s.lag===-6?'selected':''}>−6m</option>
      <option value="-3" ${s.lag===-3?'selected':''}>−3m</option>
      <option value="0" ${(!s.lag||s.lag===0)?'selected':''}>No lag</option>
      <option value="3" ${s.lag===3?'selected':''}>+3m</option>
      <option value="6" ${s.lag===6?'selected':''}>+6m</option>
      <option value="12" ${s.lag===12?'selected':''}>+12m</option>
      <option value="24" ${s.lag===24?'selected':''}>+24m</option>
    </select>
    <select class="ws-style${styleND}" data-idx="${idx}" title="Line style" ${dis}>
      <option value="solid" ${(!s.lineStyle||s.lineStyle==='solid')?'selected':''}>Solid</option>
      <option value="dashed" ${s.lineStyle==='dashed'?'selected':''}>Dashed</option>
      <option value="dotted" ${s.lineStyle==='dotted'?'selected':''}>Dotted</option>
    </select>
    <span class="ws-scale-group">
      <select class="ws-scale${scaleND}" data-idx="${idx}" title="Y-axis assignment — Auto groups similar-scale series and separates magnitude-apart series onto their own axis" ${dis}>
        <option value="auto" ${(!s.scale||s.scale==='auto')?'selected':''}>Auto</option>
        <option value="left" ${s.scale==='left'?'selected':''}>Y-Left</option>
        <option value="right" ${s.scale==='right'?'selected':''}>Y-Right</option>
        <option value="own" ${s.scale==='own'?'selected':''}>Own</option>
      </select>
      <input type="text" class="ws-mag${magND}" data-idx="${idx}"
        value="${s.magnify === 1 ? 'auto' : s.magnify}"
        placeholder="auto" inputmode="decimal"
        title="Data multiplier — type any positive number or 'auto'" ${dis}>
      ${trailingBtn}
    </span>
  </div>`;
}

// Normalize a per-series settings object — fill in defaults for any missing field.
function normalizeWsSettings(s, idx) {
  if (!s) return s;
  if (s.visible === undefined) s.visible = true;
  if (!s.color) s.color = WS_PALETTE[(idx || 0) % WS_PALETTE.length];
  if (!s.maType) s.maType = 'none';
  if (s.maPeriod === undefined) s.maPeriod = 0;
  if (s.lag === undefined) s.lag = 0;
  if (!s.lineStyle) s.lineStyle = 'solid';
  if (!s.scale) s.scale = 'auto';   // auto = smart multi-axis assignment by magnitude
  if (s.magnify === undefined) s.magnify = 1;
  return s;
}

// Wire ALL the standard row callbacks. Required: container DOM node, sers array,
// rerenderRows fn (rebuilds inner HTML), redrawChart fn.
// Optional: onRemove(idx) when ✕ clicked on rows that have data-rm.
function wireWsRows(container, sers, rerenderRows, redrawChart, onRemove) {
  container.querySelectorAll('input[type="checkbox"][data-idx]').forEach(cb => cb.onchange = () => {
    sers[+cb.dataset.idx].visible = cb.checked;
    rerenderRows(); redrawChart();
  });
  container.querySelectorAll('.ws-color[data-idx]').forEach(el => el.onclick = () => {
    const idx = +el.dataset.idx;
    const i = WS_PALETTE.indexOf(sers[idx].color);
    sers[idx].color = WS_PALETTE[(i + 1) % WS_PALETTE.length];
    rerenderRows(); redrawChart();
  });
  // Secondary gesture (right-click / long-press): open a popover for direct pick + reset.
  container.querySelectorAll('.ws-color[data-idx]').forEach(el => {
    const open = (ev) => {
      ev.preventDefault();
      openColorPopover(el, sers, +el.dataset.idx, rerenderRows, redrawChart);
    };
    el.addEventListener('contextmenu', open);
    let lp;
    el.addEventListener('touchstart', (ev) => { lp = setTimeout(() => open(ev), 450); }, { passive: false });
    el.addEventListener('touchend', () => clearTimeout(lp));
    el.addEventListener('touchmove', () => clearTimeout(lp));
  });
  container.querySelectorAll('.ws-ma[data-idx]').forEach(s => s.onchange = () => {
    const [t, p] = s.value.split(':');
    sers[+s.dataset.idx].maType = t;
    sers[+s.dataset.idx].maPeriod = +p;
    redrawChart();
  });
  container.querySelectorAll('.ws-lag[data-idx]').forEach(s => s.onchange = () => {
    sers[+s.dataset.idx].lag = +s.value;
    redrawChart();
  });
  container.querySelectorAll('.ws-style[data-idx]').forEach(s => s.onchange = () => {
    sers[+s.dataset.idx].lineStyle = s.value;
    redrawChart();
  });
  container.querySelectorAll('.ws-scale[data-idx]').forEach(s => s.onchange = () => {
    sers[+s.dataset.idx].scale = s.value;
    rerenderRows(); redrawChart();
  });
  container.querySelectorAll('.ws-mag[data-idx]').forEach(inp => {
    const commit = () => {
      const idx = +inp.dataset.idx;
      const raw = inp.value.trim().toLowerCase();
      if (raw === '' || raw === 'auto' || raw === 'a') {
        sers[idx].magnify = 1; inp.value = 'auto';
      } else {
        const v = parseFloat(raw);
        if (isFinite(v) && v > 0) {
          sers[idx].magnify = v;
          inp.value = v === 1 ? 'auto' : String(v);
        } else inp.value = sers[idx].magnify === 1 ? 'auto' : sers[idx].magnify;
      }
      redrawChart();
    };
    inp.addEventListener('change', commit);
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); inp.blur(); } });
  });
  container.querySelectorAll('[data-magreset]').forEach(btn => btn.onclick = () => {
    sers[+btn.dataset.magreset].magnify = 1;
    rerenderRows(); redrawChart();
  });
  if (onRemove) {
    container.querySelectorAll('[data-rm]').forEach(btn => btn.onclick = () => {
      onRemove(+btn.dataset.rm);
    });
  }
}

// Color popover (P1C-07): direct palette pick + reset-to-default. Opened by the
// secondary gesture on a swatch; the left-click cycle remains the fast path.
function openColorPopover(anchor, sers, idx, rerenderRows, redrawChart) {
  document.querySelectorAll('.ws-color-pop').forEach(p => p.remove());
  const pop = document.createElement('div');
  pop.className = 'ws-color-pop float-surface';
  const swatches = WS_PALETTE.map((c) =>
    `<button class="ws-color-pick${c===sers[idx].color?' sel':''}" data-c="${escapeAttr(c)}" style="background:${c};" title="${escapeAttr(c)}"></button>`).join('');
  pop.innerHTML = `<div class="ws-color-grid">${swatches}</div>
    <button class="pbtn ws-color-reset" title="Reset to default palette color">↻ Reset</button>`;
  document.body.appendChild(pop);
  const r = anchor.getBoundingClientRect();
  pop.style.left = Math.max(8, Math.min(r.left, window.innerWidth - pop.offsetWidth - 8)) + 'px';
  pop.style.top  = (r.bottom + 4) + 'px';
  const close = () => {
    pop.remove();
    document.removeEventListener('mousedown', onDoc, true);
    document.removeEventListener('keydown', onKey, true);
  };
  pop.querySelectorAll('.ws-color-pick').forEach(b => b.onclick = () => {
    sers[idx].color = b.dataset.c; close(); rerenderRows(); redrawChart();
  });
  pop.querySelector('.ws-color-reset').onclick = () => {
    sers[idx].color = WS_PALETTE[idx % WS_PALETTE.length]; close(); rerenderRows(); redrawChart();
  };
  const onDoc = (e) => { if (!pop.contains(e.target)) close(); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  setTimeout(() => {
    document.addEventListener('mousedown', onDoc, true);
    document.addEventListener('keydown', onKey, true);
  }, 0);
}

// Build the unified Workspace-style controls bar HTML.
// opts: {period, periods?, extraLeft?: html, extraRight?: html,
//        showEqualize?: bool, showShareLeft?: bool, showTickersToggle?: bool,
//        showTickers?: bool, showCopyTickers?: bool, showExport?: bool}
function buildWsControlsBarHTML(opts) {
  const period = opts.period || '1Y';
  const periods = opts.periods || ['1M','3M','6M','1Y','2Y','ALL'];
  // Period = mutually-exclusive choice → segmented control.
  let html = `<div class="ws-controls-bar" style="margin-bottom:12px;">
    <span class="label">Period</span>
    <span class="seg">${periods.map(p => `<button class="pbtn ${period===p?'active':''}" data-p="${p}">${p}</button>`).join('')}</span>`;
  if (opts.extraLeft) html += opts.extraLeft;
  if (opts.showEqualize || opts.showShareLeft) {
    const sm = opts.scaleMode;
    html += `<span class="ctl-div"></span><span class="label">Scaling</span><span class="seg">`;
    html += `<button class="pbtn ${sm==='auto'?'active':''}" data-act="auto-scale" title="Auto multi-axis: group similar-scale series, separate magnitude-apart series onto their own axis (default)">Auto</button>`;
    if (opts.showEqualize) html += `<button class="pbtn ${sm==='equalize'?'active':''}" data-act="equalize" title="Set all visible series to Own auto-fit (movements equalized, one axis each)">Equalize</button>`;
    if (opts.showShareLeft) html += `<button class="pbtn ${sm==='share-left'?'active':''}" data-act="share-left" title="Force all visible series onto one shared Y-Left axis">Share</button>`;
    html += `</span>`;
  }
  if (opts.showTickersToggle || opts.showCopyTickers || opts.showExport || opts.showExportImage) {
    html += `<span class="ctl-div"></span><span class="label">Display</span>`;
    if (opts.showTickersToggle) html += `<button class="pbtn ${opts.showTickers?'active':''}" data-act="toggle-tickers" title="Toggle Bloomberg ticker overlay on the chart">${opts.showTickers ? '✓ ' : ''}Tickers</button>`;
    if (opts.showCopyTickers) html += `<button class="pbtn" data-act="copy-tickers" title="Copy visible series' Bloomberg tickers (one per line)">⧉ Copy</button>`;
    if (opts.showExport) html += `<button class="pbtn" data-act="export-panel" title="Save current series setup as a reusable custom panel">⤓ Panel</button>`;
    if (opts.showExportImage) html += `<button class="pbtn" data-act="export-png" title="Download the chart as a PNG image">⤓ PNG</button>`;
  }
  if (opts.extraRight) { html += `<span class="ctl-spacer"></span>` + opts.extraRight; }
  html += `</div>`;
  return html;
}

// Wire the unified controls-bar buttons. callbacks keyed by data-act value.
// Period buttons fire callbacks.period(p).
function wireWsControlsBar(container, callbacks) {
  container.querySelectorAll('.ws-controls-bar .pbtn[data-p]').forEach(b => b.onclick = () => {
    if (callbacks.period) callbacks.period(b.dataset.p);
  });
  container.querySelectorAll('.ws-controls-bar .pbtn[data-act]').forEach(b => b.onclick = () => {
    const fn = callbacks[b.dataset.act];
    if (fn) fn();
  });
}

// Helper: Auto / Equalize / Share Y-Left over a sers array. Mutates and re-renders.
function applyAutoScaleOnSers(sers) { sers.forEach(s => { if (s.visible) { s.scale = 'auto'; s.magnify = 1; } }); }
function applyEqualizeOnSers(sers) { sers.forEach(s => { if (s.visible) { s.scale = 'own'; s.magnify = 1; } }); }
function applyShareLeftOnSers(sers) { sers.forEach(s => { if (s.visible) { s.scale = 'left'; s.magnify = 1; } }); }

// Derive which Scaling segment (if any) should light up, from the visible rows' state.
// Mixed / manual per-row → null (no segment active — honest).
function deriveScaleMode(sers) {
  const vis = (sers || []).filter(s => s.visible);
  if (!vis.length) return null;
  if (vis.every(s => (s.scale || 'auto') === 'auto')) return 'auto';
  if (vis.every(s => s.scale === 'own'))  return 'equalize';
  if (vis.every(s => s.scale === 'left')) return 'share-left';
  return null;
}

// Shared, DOM-only PNG export: read the live painted canvas, download as a file.
function exportChartPng(container, filename) {
  const cv = (container || document).querySelector('.chart-canvas canvas');
  if (!cv) { showToast('No chart to export', 'warn'); return; }
  const trigger = (blob) => {
    if (!blob) { showToast('Could not export PNG', 'warn'); return; }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = (filename || 'chart') + '.png';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    showToast('Saved PNG', 'ok');
  };
  try {
    if (cv.toBlob) { cv.toBlob(b => trigger(b), 'image/png'); return; }
    // Fallback for environments without toBlob.
    const a = document.createElement('a');
    a.href = cv.toDataURL('image/png');
    a.download = (filename || 'chart') + '.png';
    document.body.appendChild(a); a.click(); a.remove();
    showToast('Saved PNG', 'ok');
  } catch (e) { showToast('Could not export PNG', 'warn'); }
}

// Generic copy-tickers helper for any sers array.
async function copyTickersFromSers(sers) {
  const lines = sers.filter(s => s.visible).map(s => s.ticker || (s.name && D.indicators[s.name]?.t)).filter(Boolean);
  if (!lines.length) { showToast('No visible tickers', 'warn'); return; }
  const ok = await writeClipboard(lines.join('\n'));
  if (ok) showToast(`Copied ${lines.length} ticker${lines.length>1?'s':''}`, 'ok');
  else showToast('Copy failed — check browser permissions', 'warn');
}

// =========== FLOATING SELECTION BAR (cross-view) ===========
function renderFloatingBar() {
  const el = document.getElementById('floating-bar');
  if (!el) return;
  state.panelsSelected = state.panelsSelected || [];
  state.indicatorsSelected = state.indicatorsSelected || [];
  const np = state.panelsSelected.length;
  const ni = state.indicatorsSelected.length;
  if (np === 0 && ni === 0) { el.classList.remove('show'); return; }

  const parts = [];
  if (np > 0) parts.push(`<span class="count">📊 ${np} panel${np>1?'s':''}</span>
    <button id="fb-display-panels"${np<2?' disabled':''} title="${np<2?'Select 2+ panels to combine':'Show selected panels in a grid'}">Display panels →</button>`);
  if (ni > 0) parts.push(`<span class="count">📈 ${ni} indicator${ni>1?'s':''}</span>
    <button id="fb-display-indicators"${ni<2?' disabled':''} title="${ni<2?'Select 2+ indicators to combine':'Show selected indicators on one chart'}">Display indicators →</button>`);
  parts.push(`<button id="fb-clear" title="Clear all selections">Clear</button>`);

  el.innerHTML = parts.join(' ');
  el.classList.add('show');

  const dp = el.querySelector('#fb-display-panels');
  if (dp) dp.onclick = () => { if (np >= 2) navPanelsCombo(); };
  const di = el.querySelector('#fb-display-indicators');
  if (di) di.onclick = () => { if (ni >= 2) navIndicatorsCombo(); };
  el.querySelector('#fb-clear').onclick = () => {
    state.panelsSelected = [];
    state.indicatorsSelected = [];
    state.indicatorsComboSeries = null;
    renderFloatingBar();
    // Re-render anywhere the visual selected-state lives
    if (['panels','panel','indicators_combo','category','home'].includes(state.view)) renderMain();
  };
}

// =========== IN-APP DIALOGS (replace native prompt/confirm — P1C-13) ===========
// In-theme, non-blocking, keyboard-driven (Enter=confirm, Esc=cancel). Returns a Promise:
// prompt → trimmed string or null; confirm → true/false.
function inAppDialog({ message, defaultValue, confirmLabel, cancelLabel, withInput }) {
  return new Promise(resolve => {
    const ov = document.createElement('div');
    ov.className = 'ws-overlay';
    const inputHtml = withInput
      ? `<input type="text" class="ws-dialog-input ws-mag" style="width:100%;text-align:left;" value="${escapeAttr(defaultValue || '')}" placeholder="Name…">`
      : '';
    ov.innerHTML = `<div class="ws-dialog float-surface" role="dialog" aria-modal="true">
      <div class="ws-dialog-msg">${escapeHtml(message)}</div>
      ${inputHtml}
      <div class="ws-dialog-btns">
        <button class="pbtn" data-act="cancel">${escapeHtml(cancelLabel || 'Cancel')}</button>
        <button class="pbtn ws-dialog-ok" data-act="ok">${escapeHtml(confirmLabel || 'OK')}</button>
      </div></div>`;
    document.body.appendChild(ov);
    const inp = ov.querySelector('.ws-dialog-input');
    const done = (val) => { ov.remove(); document.removeEventListener('keydown', onKey, true); resolve(val); };
    const ok = () => done(withInput ? (inp.value.trim() || null) : true);
    ov.querySelector('[data-act="ok"]').onclick = ok;
    ov.querySelector('[data-act="cancel"]').onclick = () => done(withInput ? null : false);
    ov.onclick = (e) => { if (e.target === ov) done(withInput ? null : false); };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); done(withInput ? null : false); }
      else if (e.key === 'Enter') { e.preventDefault(); ok(); }
    };
    document.addEventListener('keydown', onKey, true);
    if (inp) { inp.focus(); inp.select(); } else ov.querySelector('.ws-dialog-ok').focus();
  });
}
function inAppPrompt(message, defaultValue) {
  return inAppDialog({ message, defaultValue, withInput: true, confirmLabel: 'Save' });
}
function inAppConfirm(message, confirmLabel) {
  return inAppDialog({ message, withInput: false, confirmLabel: confirmLabel || 'OK' });
}

// =========== TOAST + CLIPBOARD ===========
function showToast(msg, kind) {
  let el = document.getElementById('ws-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'ws-toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = 'ws-toast float-surface show ' + (kind || 'ok');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = 'ws-toast float-surface ' + (kind || 'ok'); }, 1800);
}

async function writeClipboard(text) {
  // Modern API — works on https / localhost / file:// in most browsers
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* fall through */ }
  }
  // Fallback for older browsers / non-secure contexts
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch (e) { return false; }
}

// =========== CUSTOM PANELS (localStorage-persisted) ===========
const CUSTOM_PANELS_KEY = 'macro_custom_panels_v1';
function loadCustomPanels() {
  try {
    const raw = localStorage.getItem(CUSTOM_PANELS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) { return []; }
}
function saveCustomPanels(panels) {
  try { localStorage.setItem(CUSTOM_PANELS_KEY, JSON.stringify(panels)); return true; }
  catch (e) { return false; }
}
async function exportWorkspaceAsPanel() {
  const themeId = state.workspace.activeTheme;
  const ts = state.workspace.themes[themeId];
  const visible = ts.indicators.filter(i => i.visible);
  if (!visible.length) { showToast('No visible indicators to export', 'warn'); return; }
  const defaultName = `Custom — ${themeId === 'all' ? 'mixed' : (D.workspace_themes.find(t=>t.id===themeId)?.name || themeId)} (${visible.length})`;
  const name = ((await inAppPrompt('Name this panel:', defaultName)) || '').trim();
  if (!name) return;
  const panel = {
    id: 'custom_' + Date.now(),
    name,
    description: 'User-saved panel from Workspace · ' + new Date().toLocaleString(),
    theme: themeId,
    period: state.period,
    showTickers: ts.showTickers,
    indicators: visible.map(i => ({
      name: i.name,
      color: i.color,
      lineStyle: i.lineStyle,
      lineWidth: i.lineWidth,
      maType: i.maType, maPeriod: i.maPeriod,
      lag: i.lag,
      scale: i.scale, magnify: i.magnify,
      fill: i.fill,
    })),
    custom: true,
    createdAt: new Date().toISOString(),
  };
  const panels = loadCustomPanels();
  panels.push(panel);
  if (saveCustomPanels(panels)) {
    showToast(`Saved "${name}" to Panels board · ${visible.length} indicators`, 'ok');
  } else {
    showToast('Save failed — localStorage unavailable', 'warn');
  }
}
function deleteCustomPanel(panelId) {
  const panels = loadCustomPanels().filter(p => p.id !== panelId);
  saveCustomPanels(panels);
}

async function copyVisibleTickers() {
  const themeId = state.workspace.activeTheme;
  const ts = state.workspace.themes[themeId];
  const lines = [];
  ts.indicators.filter(i => i.visible).forEach(i => {
    const meta = D.indicators[i.name];
    if (meta && meta.t) lines.push(meta.t);
  });
  if (!lines.length) { showToast('No visible tickers to copy', 'warn'); return; }
  const text = lines.join('\n');
  const ok = await writeClipboard(text);
  if (ok) showToast(`Copied ${lines.length} ticker${lines.length > 1 ? 's' : ''} · ${text.split('\n')[0]}${lines.length>1?' …':''}`, 'ok');
  else showToast('Copy failed — check browser permissions', 'warn');
}

function renderWorkspaceContext(r) {
  const themeId = state.workspace.activeTheme;
  const theme = D.workspace_themes.find(t => t.id === themeId);
  if (!theme) { r.innerHTML = ''; return; }
  const ts = state.workspace.themes[themeId];
  const visibleInds = ts.indicators.filter(i => i.visible);

  let html = `<h3>Theme overview</h3>
    <div class="ws-rail-section">
      <div class="summary">${escapeHtml(theme.summary)}</div>
    </div>
    <h3>Selected indicators (${visibleInds.length})</h3>
    <div class="ws-rail-section" style="max-height:260px;overflow-y:auto;">`;
  visibleInds.forEach(ind => {
    const m = D.indicators[ind.name];
    if (!m) return;
    const why = m.i || m.d || '';
    html += `<div class="ws-rail-ind" style="border-left-color:${ind.color};">
      <div class="name">${escapeHtml(ind.name)}</div>
      <div class="meta">${escapeHtml(m.t)} · ${escapeHtml(m.f)}${m.s ? ' · ' + escapeHtml(m.s) : ''}</div>
      ${why ? `<div class="why">${escapeHtml(why.slice(0, 160))}${why.length > 160 ? '…' : ''}</div>` : ''}
    </div>`;
  });
  if (!visibleInds.length) html += '<div class="muted" style="font-size:11px;">No indicators selected.</div>';
  html += `</div>
    <h3>Connects to</h3>`;
  theme.related.forEach(rid => {
    const rt = D.workspace_themes.find(t => t.id === rid);
    if (rt) html += `<div class="ws-related-link" data-link="${escapeAttr(rid)}">
      <div class="label">${escapeHtml(rt.name)}</div>
      <div class="desc">${escapeHtml(rt.summary.slice(0, 90))}…</div>
    </div>`;
  });
  if (theme.narratives && theme.narratives.length) {
    html += `<h3 style="margin-top:14px;">Macro narratives</h3>`;
    theme.narratives.forEach(n => {
      html += `<div class="ws-narrative">${escapeHtml(n)}</div>`;
    });
  }
  html += `<div style="margin-top:14px;font-size:10px;color:var(--text-3);font-family:var(--mono);">
    Full research: <span style="color:var(--text-2);">context/${escapeHtml(theme.kb)}</span>
  </div>`;

  r.innerHTML = html;
  r.querySelectorAll('.ws-related-link').forEach(el => el.onclick = () => navWorkspace(el.dataset.link));
}

function drawWorkspaceChart() {
  const cv = $('ws-chart');
  if (!cv) return;
  if (_wsChart) { _wsChart.destroy(); _wsChart = null; }

  const themeId = state.workspace.activeTheme;
  const ts = state.workspace.themes[themeId];
  const built = buildAxisDatasets(ts.indicators, state.period, s => seriesByName(s.name), s => s.name);

  if (!built) {
    const wrap = $('ws-chart-canvas');
    if (wrap) wrap.innerHTML = '<canvas id="ws-chart"></canvas><div class="ws-empty-chart">Tick at least one indicator to plot.</div>';
    return;
  }
  const wrap = $('ws-chart-canvas');
  if (!cv.parentElement || (wrap && wrap.querySelector('.ws-empty-chart'))) {
    if (wrap) wrap.innerHTML = '<canvas id="ws-chart"></canvas>';
  }
  _wsChart = new MacroChart($('ws-chart'), {
    datasets: built.datasets,
    yAxes: built.yAxes,
    showTickers: !!ts.showTickers,
    onTickerPanelClick: () => copyVisibleTickers(),
    onLegendClick: (srcIdx, { isolate }) => {
      const sers = ts.indicators;
      const s = sers[srcIdx]; if (!s) return;
      if (isolate) {
        const onlyMe = sers.every((x, i) => (i === srcIdx) === !!x.visible);
        sers.forEach(x => { x.visible = true; });
        if (!onlyMe) sers.forEach((x, i) => { x.visible = (i === srcIdx); });
      } else { s.visible = !s.visible; }
      renderWorkspaceSeriesRows(themeId);   // resync control-row checkboxes
      drawWorkspaceChart(); renderRightRail();
    },
  });
}

let _bigChart = null;
// Per-indicator-detail series state — lets user add overlays + customize per-series.
// state.indicatorSeries[ind] = [{name, visible, color, scale, magnify, removable}]
// Index 0 is always the main indicator (removable=false). Overlays follow.
function ensureIndicatorSeries(ind) {
  state.indicatorSeries = state.indicatorSeries || {};
  if (!state.indicatorSeries[ind]) {
    state.indicatorSeries[ind] = [normalizeWsSettings({
      name: ind, ticker: D.indicators[ind]?.t || '', removable: false,
    }, 0)];
  } else {
    state.indicatorSeries[ind].forEach((s, i) => normalizeWsSettings(s, i));
  }
  return state.indicatorSeries[ind];
}

function renderIndicator(m) {
  const ind = state.indicator;
  const e = D.indicators[ind];
  const themeLabel = themeLabelOf(e.th);
  const catLabel = catLabelOf(e.th, e.c, e.cl);
  const treeOnly = isTreeOnlyTheme(e.th);

  // Compute deltas from full series
  const series = seriesByName(ind);
  const last = series[series.length-1];
  const findBefore = (days) => {
    if (!last) return null;
    const target = new Date(last[0]); target.setDate(target.getDate() - days);
    for (let i = series.length-1; i >= 0; i--) {
      if (new Date(series[i][0]) <= target) return series[i];
    }
    return series[0];
  };
  const d1m = findBefore(30), d3m = findBefore(90), d12m = findBefore(365);
  const d = (a, b) => (a===null||b===null||!a||!b) ? null : a[1]-b[1];
  const c1m = d(last, d1m), c3m = d(last, d3m), c12m = d(last, d12m);
  const cls = (v) => v===null ? '' : (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
  const sgn = (v) => v===null ? '—' : (v > 0 ? '+' : '') + fmtNum(v);

  let html = `
    <div class="section-h detail-h">
      <div>
        <h1>${escapeHtml(ind)}</h1>
        <div class="ticker-row">
          <span class="ticker">${escapeHtml(e.t)}</span>
          <span>${escapeHtml(e.cl)}</span>
          <span>${escapeHtml(e.f)}</span>
          <span>${escapeHtml(e.s || '')}</span>
        </div>
      </div>
      <span class="breadcrumb"><a id="bc-home">Home</a> / ${treeOnly
        ? `<a id="bc-th">${escapeHtml(themeLabel)}</a>`
        : `<a id="bc-th">${escapeHtml(themeLabel)}</a> / <a id="bc-cat">${escapeHtml(catLabel)}</a>`} / <span style="color:var(--text-2);">${escapeHtml(ind)}</span></span>
    </div>

    <div class="value-strip">
      <div>
        <div class="latest">${fmtNum(e.lv, e.u)}<span class="units">${e.u || ''}</span></div>
        <div class="latest-date">as of ${e.ld}</div>
      </div>
      <div class="deltas">
        <div class="delta"><div class="l">1M Δ</div><div class="v ${cls(c1m)}">${sgn(c1m)}</div></div>
        <div class="delta"><div class="l">3M Δ</div><div class="v ${cls(c3m)}">${sgn(c3m)}</div></div>
        <div class="delta"><div class="l">12M Δ</div><div class="v ${cls(c12m)}">${sgn(c12m)}</div></div>
        <div class="delta"><div class="l">Obs</div><div class="v">${e.n}</div></div>
      </div>
    </div>

    ${buildWsControlsBarHTML({
      period: state.period,
      scaleMode: deriveScaleMode(ensureIndicatorSeries(ind)),
      showEqualize: true, showShareLeft: true,
      showTickersToggle: true, showTickers: !!state.indicatorShowTickers,
      showCopyTickers: true, showExport: true, showExportImage: true,
      extraRight: `<button class="pbtn" data-act="open-workspace" title="Open this indicator in the Workspace view (theme: ${escapeAttr(themeLabel)})">Open in Workspace →</button>`,
    })}

    <div class="chart-wrap">
      <div class="chart-canvas"><canvas id="big-chart"></canvas></div>
    </div>

    <div class="ws-series-list">
      <div class="ws-series-h">
        <span>Customize series · MA / Lag / Style / Scale / Magnify</span>
        <span class="ws-actions">
          <button id="ind-show-all">Show all</button>
          <button id="ind-hide-all">Hide all</button>
          <button id="ind-reset-series">Reset</button>
        </span>
      </div>
      <div id="ind-series-rows"></div>
      <div class="ws-add-overlay" style="margin-top:10px;display:flex;gap:8px;align-items:center;">
        <input type="text" id="ind-overlay-search" placeholder="Add overlay — type indicator name or ticker…" style="flex:1;background:var(--bg-elev-2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:3px;font-family:var(--mono);font-size:11px;" autocomplete="off">
        <div id="ind-overlay-results" style="display:none;position:absolute;background:var(--bg-elev-2);border:1px solid var(--border);max-height:240px;overflow-y:auto;z-index:5;font-family:var(--mono);font-size:11px;"></div>
      </div>
    </div>

    <div class="detail-meta">
      <div class="cell"><div class="l">Ticker</div><div class="v">${e.t}</div></div>
      <div class="cell"><div class="l">Units</div><div class="v">${e.u || '—'}</div></div>
      <div class="cell"><div class="l">Frequency</div><div class="v">${e.f}</div></div>
      <div class="cell"><div class="l">Source</div><div class="v">${e.s || '—'}</div></div>
    </div>

    ${e.d ? `<div class="detail-section"><h3>What it measures</h3><p>${escapeHtml(e.d)}</p></div>` : ''}
    ${e.i ? `<div class="detail-section"><h3>Why it matters</h3><p>${escapeHtml(e.i)}</p></div>` : ''}
    ${(e.sh || e.sl) ? `<div class="detail-section"><h3>Signal interpretation</h3>
      <div class="signal-row">
        <div class="signal high"><div class="l">High → </div>${escapeHtml(e.sh || '—')}</div>
        <div class="signal low"><div class="l">Low → </div>${escapeHtml(e.sl || '—')}</div>
      </div>
    </div>` : ''}
    ${e.r && e.r.length ? `<div class="detail-section"><h3>Related indicators</h3>
      <div class="related-list">${e.r.filter(r => D.indicators[r]).map(r => `<a data-ind="${escapeAttr(r)}">${escapeHtml(r)}</a>`).join('')}</div>
    </div>` : ''}
  `;
  m.innerHTML = html;
  m.querySelector('#bc-home').onclick = navHome;
  if (treeOnly) {
    m.querySelector('#bc-th').onclick = navPceDashboard;
  } else {
    m.querySelector('#bc-th').onclick = () => navTheme(e.th);
    m.querySelector('#bc-cat').onclick = () => navCategory(e.c);
  }
  m.querySelectorAll('.related-list a').forEach(el => el.onclick = () => navIndicator(el.dataset.ind));
  wireWsControlsBar(m, {
    period: (p) => { state.period = p; renderIndicator(m); },
    'auto-scale': () => { applyAutoScaleOnSers(ensureIndicatorSeries(ind)); renderIndicatorSeriesRows(ind); drawIndicatorChart(ind); },
    'equalize': () => { applyEqualizeOnSers(ensureIndicatorSeries(ind)); renderIndicatorSeriesRows(ind); drawIndicatorChart(ind); },
    'share-left': () => { applyShareLeftOnSers(ensureIndicatorSeries(ind)); renderIndicatorSeriesRows(ind); drawIndicatorChart(ind); },
    'toggle-tickers': () => { state.indicatorShowTickers = !state.indicatorShowTickers; renderIndicator(m); },
    'copy-tickers': () => copyTickersFromSers(ensureIndicatorSeries(ind)),
    'export-panel': () => exportSersAsPanel(ensureIndicatorSeries(ind), `${ind} + overlays`),
    'export-png': () => exportChartPng(m, `${ind} + overlays`),
    'open-workspace': () => {
      let targetThemeId = null;
      for (const t of D.workspace_themes) {
        if (t.id === 'all') continue;
        if (t.available.includes(ind)) { targetThemeId = t.id; break; }
      }
      if (!targetThemeId) targetThemeId = 'all';
      const ts = state.workspace.themes[targetThemeId];
      if (ts) {
        if (targetThemeId === 'all') {
          if (!ts.indicators.find(x => x.name === ind)) {
            ts.indicators.push(normalizeWsSettings({ name: ind, ticker: D.indicators[ind]?.t || '' }, ts.indicators.length));
          } else {
            ts.indicators.find(x => x.name === ind).visible = true;
          }
        } else {
          const found = ts.indicators.find(x => x.name === ind);
          if (found) found.visible = true;
        }
      }
      state.workspace.activeTheme = targetThemeId;
      navWorkspace();
    },
  });

  m.querySelector('#ind-show-all').onclick = () => {
    ensureIndicatorSeries(ind).forEach(s => s.visible = true);
    renderIndicatorSeriesRows(ind); drawIndicatorChart(ind);
  };
  m.querySelector('#ind-hide-all').onclick = () => {
    ensureIndicatorSeries(ind).forEach(s => s.visible = false);
    renderIndicatorSeriesRows(ind); drawIndicatorChart(ind);
  };
  m.querySelector('#ind-reset-series').onclick = () => {
    delete state.indicatorSeries[ind];
    renderIndicatorSeriesRows(ind); drawIndicatorChart(ind);
  };

  // Overlay search — filter indicator catalog
  const searchEl = m.querySelector('#ind-overlay-search');
  const resultsEl = m.querySelector('#ind-overlay-results');
  const showResults = (q) => {
    const sers = ensureIndicatorSeries(ind);
    const existingNames = new Set(sers.map(s => s.name));
    const ranked = rankIndicators(q, { exclude: existingNames }).slice(0, 30);
    if (!ranked.length) { resultsEl.style.display = 'none'; return; }
    resultsEl.innerHTML = ranked.map(([n, e]) =>
      `<div class="ovr-item" data-n="${escapeAttr(n)}" style="padding:6px 10px;cursor:pointer;border-bottom:1px solid var(--border);">
        <div>${escapeHtml(n)}</div>
        <div style="color:var(--text-3);font-size:10px;">${escapeHtml(e.t || '')}</div>
      </div>`
    ).join('');
    resultsEl.style.display = 'block';
    // Position — anchor under the input
    const r = searchEl.getBoundingClientRect();
    resultsEl.style.left = r.left + 'px';
    resultsEl.style.top = (r.bottom + window.scrollY) + 'px';
    resultsEl.style.width = r.width + 'px';
    resultsEl.querySelectorAll('.ovr-item').forEach(it => it.onclick = () => {
      const n = it.dataset.n;
      const sers = ensureIndicatorSeries(ind);
      sers.push(normalizeWsSettings({
        name: n, ticker: D.indicators[n]?.t || '', removable: true,
      }, sers.length));
      searchEl.value = '';
      resultsEl.style.display = 'none';
      renderIndicatorSeriesRows(ind);
      drawIndicatorChart(ind);
    });
  };
  searchEl.addEventListener('input', () => {
    const q = searchEl.value.trim();
    if (q.length < 2) { resultsEl.style.display = 'none'; return; }
    showResults(q);
  });
  searchEl.addEventListener('blur', () => setTimeout(() => { resultsEl.style.display = 'none'; }, 150));

  renderIndicatorSeriesRows(ind);
  drawIndicatorChart(ind);
}

function renderIndicatorSeriesRows(ind) {
  const c = $('ind-series-rows');
  if (!c) return;
  const sers = ensureIndicatorSeries(ind);
  c.innerHTML = buildWsRowHeaderHTML() + sers.map((s, idx) => buildWsRowHTML(idx, s, {
    removable: !!s.removable,
    removeTitle: 'Remove overlay',
    extraLabel: idx === 0 ? '(main)' : '',
  })).join('');
  wireWsRows(c, sers, () => renderIndicatorSeriesRows(ind), () => drawIndicatorChart(ind), (idx) => {
    sers.splice(idx, 1);
    renderIndicatorSeriesRows(ind); drawIndicatorChart(ind);
  });
}

function drawIndicatorChart(ind) {
  const cv = $('big-chart');
  if (!cv) return;
  if (_bigChart) _bigChart.destroy();
  const sers = ensureIndicatorSeries(ind);
  const built = buildAxisDatasets(sers, state.period, s => seriesByName(s.name), s => s.name);
  if (!built) return;
  // Fill under the main series when it's alone on a shared left axis (cosmetic)
  if (built.datasets[0] && built.datasets[0].yAxisId === 'y') built.datasets[0].fill = true;
  _bigChart = new MacroChart(cv, {
    datasets: built.datasets, yAxes: built.yAxes,
    showTickers: !!state.indicatorShowTickers,
    onTickerPanelClick: () => copyTickersFromSers(sers),
    onLegendClick: (srcIdx, { isolate }) => {
      const s = sers[srcIdx]; if (!s) return;
      if (isolate) {
        const onlyMe = sers.every((x, i) => (i === srcIdx) === !!x.visible);
        sers.forEach(x => { x.visible = true; });
        if (!onlyMe) sers.forEach((x, i) => { x.visible = (i === srcIdx); });
      } else { s.visible = !s.visible; }
      renderIndicatorSeriesRows(ind); drawIndicatorChart(ind);
    },
  });
}

// =========== SERIES LOOKUP HELPERS ===========
// D.series is keyed by TICKER (not indicator name) because 964 indicator names
// collide across categories (e.g., "Core PCE > Services" exists in both
// cat 48 MoM and cat 50 YoY). Use these helpers everywhere instead of D.series[name].
function seriesByTicker(tkr) {
  return (tkr && D.series[tkr]) || [];
}
function seriesByName(name) {
  if (!name) return [];
  const meta = D.indicators[name];
  if (!meta || !meta.t) return [];
  return D.series[meta.t] || [];
}

// =========== CHARTS ===========
function periodFiltered(series) {
  if (state.period === 'ALL' || !series.length) return series;
  const days = PERIOD_DAYS[state.period];
  const last = new Date(series[series.length-1][0]);
  const cutoff = new Date(last); cutoff.setDate(cutoff.getDate() - days);
  return series.filter(d => new Date(d[0]) >= cutoff);
}

// Adaptive point radius based on series density (so monthly/quarterly indicators show dots)
function pointRadiusFor(n) {
  if (n <= 25) return 3;
  if (n <= 60) return 2;
  if (n <= 200) return 1.4;
  return 0;
}

// ============== MacroChart — vanilla canvas multi-series time chart ==============
class MacroChart {
  constructor(canvas, config) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.config = Object.assign({
      datasets: [],
      yAxes: { y: { position: 'left' } },
      colors: (() => {
        const cs = getComputedStyle(document.documentElement);
        const tok = (n, fb) => (cs.getPropertyValue(n).trim() || fb);
        const elev = tok('--bg-elev', '#0c1016');
        return {
          text:   tok('--text-2', '#9aa5b4'),   // axis labels — AA on bg-elev
          text2:  tok('--text-2', '#9aa5b4'),   // X-axis labels — was #6b7686 (4.14:1, sub-AA)
          text3:  tok('--text-3', '#7d8796'),   // legend/tooltip secondary
          textHi: tok('--text',   '#e8ebf0'),   // tooltip emphasis / tickers
          gridMinor: 'rgba(255,255,255,0.06)',  // minor H/X grid (was 0.03 ≈ 1.06:1)
          gridMajor: 'rgba(255,255,255,0.10)',  // major grid — real minor/major split
          axisBorder:'rgba(255,255,255,0.14)',  // plot frame (was 0.08 ≈ 1.21:1)
          tipBg:  hexA(elev, 0.96),             // tooltip bg from --bg-elev (was #0b1018 literal)
          tipBorder: tok('--border-strong', '#3a4759')
        };
      })(),
    }, config);
    this.dpr = window.devicePixelRatio || 1;
    this.padTop = 18;
    this.padBottom = 56;        // x-axis labels + legend
    // Compute padLeft dynamically based on number of left-side axes (primary + own)
    const ownAxisCount = Object.keys(this.config.yAxes || {}).filter(k => k.startsWith('own')).length;
    this.ownAxisVisibleMax = 3;
    this.ownColWidth = 50;
    const visibleOwn = Math.min(ownAxisCount, this.ownAxisVisibleMax);
    const hasPrimaryLeft = !!(this.config.yAxes && this.config.yAxes.y);
    const leftAxesCount = (hasPrimaryLeft ? 1 : 0) + visibleOwn;
    // Each axis gets a 50px column; the rightmost (closest to plot) needs 56px to clear label edge
    this.padLeft = leftAxesCount === 0 ? 56 : (leftAxesCount - 1) * this.ownColWidth + 56;
    this.padRight = (this.config.yAxes && this.config.yAxes.y2) ? 56 : 18;
    this.hoverX = null;
    // Interaction state (Stream A: zoom + rAF hover + legend hit-test)
    this._zoom = null;            // {xMin,xMax} epoch-ms when drag-zoomed
    this._dragStartX = null;      // px, plot-space drag anchor
    this._dragCurX = null;        // px, plot-space drag cursor
    this._rafId = null;           // coalesce mousemove repaints to ≤1/frame
    this._legendHits = [];        // [{x,y,w,h,srcIdx}] captured in _drawLegend
    this._xCache = null;          // Map<ds, number[]> lazy x arrays for binary search
    this._overLegend = false;     // pointer-feedback: over a legend hit

    this._onMove = (e) => {
      const r = canvas.getBoundingClientRect();
      this.hoverX = e.clientX - r.left;
      // Update cursor: pointer if hovering ticker panel or a legend item
      const py = e.clientY - r.top;
      const inPanel = this._tickerPanelBounds && this.hoverX >= this._tickerPanelBounds.x && this.hoverX <= this._tickerPanelBounds.x + this._tickerPanelBounds.w && py >= this._tickerPanelBounds.y && py <= this._tickerPanelBounds.y + this._tickerPanelBounds.h;
      this._overLegend = this._isOverLegend(this.hoverX, py);
      canvas.style.cursor = (inPanel || this._overLegend) ? 'pointer' : 'default';
      // While dragging, track the band end at the (clamped) cursor x.
      if (this._dragStartX !== null) this._dragCurX = this.hoverX;
      // rAF-coalesce: at most one repaint per frame regardless of move rate.
      if (!this._rafId) this._rafId = requestAnimationFrame(() => { this._rafId = null; this._draw(); });
    };
    this._onLeave = () => { this.hoverX = null; this._overLegend = false; canvas.style.cursor = 'default'; this._draw(); };
    this._onClick = (e) => {
      if (this._suppressClick) { this._suppressClick = false; return; }
      if (!this._tickerPanelBounds) return;
      const r = canvas.getBoundingClientRect();
      const px = e.clientX - r.left, py = e.clientY - r.top;
      const b = this._tickerPanelBounds;
      if (px >= b.x && px <= b.x + b.w && py >= b.y && py <= b.y + b.h) {
        if (typeof this.config.onTickerPanelClick === 'function') this.config.onTickerPanelClick();
      }
    };
    this._onDown = (e) => {
      const r = canvas.getBoundingClientRect();
      const px = e.clientX - r.left, py = e.clientY - r.top;
      // (a) legend hit-test wins → dispatch onLegendClick, suppress the trailing click.
      if (this._legendHitTest(px, py, e)) { this._suppressClick = true; return; }
      // (b) ticker panel copy (before drag, so a panel click copies rather than zero-drags).
      if (this.config.showTickers && this._tickerPanelBounds) {
        const b = this._tickerPanelBounds;
        if (px >= b.x && px <= b.x + b.w && py >= b.y && py <= b.y + b.h) {
          if (typeof this.config.onTickerPanelClick === 'function') this.config.onTickerPanelClick();
          this._suppressClick = true; return;
        }
      }
      // (c) inside plot rect → begin a drag-to-zoom selection.
      if (px >= this._plotX && px <= this._plotX + this._plotW &&
          py >= this._plotY && py <= this._plotY + this._plotH) {
        this._dragStartX = px; this._dragCurX = px;
      }
    };
    this._onUp = (e) => {
      if (this._dragStartX === null) return;
      const a = this._dragStartX, b = this._dragCurX;
      this._dragStartX = null; this._dragCurX = null;
      if (b !== null && Math.abs(b - a) > 4) {
        const x0 = Math.max(this._plotX, Math.min(a, b));
        const x1 = Math.min(this._plotX + this._plotW, Math.max(a, b));
        const t0 = this._domXMin + (x0 - this._plotX) / this._plotW * (this._domXMax - this._domXMin);
        const t1 = this._domXMin + (x1 - this._plotX) / this._plotW * (this._domXMax - this._domXMin);
        this._zoom = { xMin: Math.min(t0, t1), xMax: Math.max(t0, t1) };
        this._suppressClick = true;  // a zoom drag must not also fire ticker-copy
      }
      this._draw();
    };
    this._onDblClick = () => { if (this._zoom) { this._zoom = null; this._draw(); } };
    canvas.addEventListener('mousemove', this._onMove);
    canvas.addEventListener('mouseleave', this._onLeave);
    canvas.addEventListener('click', this._onClick);
    canvas.addEventListener('mousedown', this._onDown);
    canvas.addEventListener('mouseup', this._onUp);
    canvas.addEventListener('dblclick', this._onDblClick);

    if (window.ResizeObserver) {
      this._ro = new ResizeObserver(() => this._draw());
      this._ro.observe(canvas.parentElement || canvas);
    } else {
      this._onResize = () => this._draw();
      window.addEventListener('resize', this._onResize);
    }
    // Initial draw — defer one frame so layout has settled
    requestAnimationFrame(() => this._draw());
    setTimeout(() => this._draw(), 50); // safety re-draw if RO didn't fire
  }

  destroy() {
    this.canvas.removeEventListener('mousemove', this._onMove);
    this.canvas.removeEventListener('mouseleave', this._onLeave);
    this.canvas.removeEventListener('click', this._onClick);
    this.canvas.removeEventListener('mousedown', this._onDown);
    this.canvas.removeEventListener('mouseup', this._onUp);
    this.canvas.removeEventListener('dblclick', this._onDblClick);
    if (this._rafId) cancelAnimationFrame(this._rafId);
    if (this._ro) this._ro.disconnect();
    if (this._onResize) window.removeEventListener('resize', this._onResize);
  }

  _draw() {
    const cv = this.canvas;
    const parent = cv.parentElement;
    const cssW = parent ? parent.clientWidth : cv.clientWidth;
    const cssH = parent ? parent.clientHeight : cv.clientHeight;
    if (!cssW || !cssH) return;

    cv.style.width = cssW + 'px';
    cv.style.height = cssH + 'px';
    cv.width = Math.round(cssW * this.dpr);
    cv.height = Math.round(cssH * this.dpr);
    const ctx = this.ctx;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const c = this.config.colors;
    const datasets = this.config.datasets.filter(ds => ds.data && ds.data.length);
    if (!datasets.length) {
      ctx.fillStyle = c.text2;
      ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('No data in selected period', cssW/2, cssH/2);
      return;
    }

    // Plot rect
    const plotX = this.padLeft;
    const plotY = this.padTop;
    const plotW = Math.max(10, cssW - this.padLeft - this.padRight);
    const plotH = Math.max(10, cssH - this.padTop - this.padBottom);

    // X domain (time)
    let xMin = Infinity, xMax = -Infinity;
    datasets.forEach(ds => ds.data.forEach(d => {
      if (d[0] < xMin) xMin = d[0];
      if (d[0] > xMax) xMax = d[0];
    }));
    if (xMin === xMax) { xMin -= 86400000; xMax += 86400000; }
    // Drag-zoom override: substitute the visible time window. Because mapX,
    // niceTimeTicks, gridlines, lines and tHover all close over xMin/xMax, this
    // single substitution zooms the entire render coherently. Do NOT filter
    // ds.data — clipping points would re-fit Y and break shared-scale comparison.
    if (this._zoom) { xMin = this._zoom.xMin; xMax = this._zoom.xMax; }
    // Stash plot rect + post-override domain for the pointer handlers (which run
    // outside _draw and cannot see these locals). Post-override domain means a
    // drag while already zoomed zooms further (correct).
    this._plotX = plotX; this._plotY = plotY; this._plotW = plotW; this._plotH = plotH;
    this._domXMin = xMin; this._domXMax = xMax;

    // Y domains per axis — auto-fit peak-to-trough with 6% padding, niceTicks for tick values.
    // (Per-series scaling is applied as a data multiplier upstream, so axis just fits the data.)
    const axisIds = Object.keys(this.config.yAxes);
    const yScales = {};
    axisIds.forEach(axId => {
      const dsList = datasets.filter(d => (d.yAxisId || 'y') === axId);
      if (!dsList.length) return;
      let yMin = Infinity, yMax = -Infinity;
      dsList.forEach(ds => ds.data.forEach(d => {
        if (d[1] < yMin) yMin = d[1];
        if (d[1] > yMax) yMax = d[1];
      }));
      if (yMin === yMax) { const pad = Math.abs(yMin)*0.05 || 1; yMin -= pad; yMax += pad; }
      const range = yMax - yMin;
      yMin -= range * 0.06;
      yMax += range * 0.06;
      const ticks = niceTicks(yMin, yMax, 6);
      // Identity tag for the axis: its series ticker (short) or label, with a
      // "+N" annotation when more than one series shares this axis.
      const tag = (dsList[0].ticker || dsList[0].label) + (dsList.length > 1 ? ' +' + (dsList.length - 1) : '');
      yScales[axId] = { min: ticks.min, max: ticks.max, ticks: ticks.values, color: dsList[0].color, tag };
    });

    const mapX = (t) => plotX + (t - xMin) / (xMax - xMin) * plotW;
    const mapY = (v, axId='y') => {
      const s = yScales[axId];
      return plotY + plotH - (v - s.min) / (s.max - s.min) * plotH;
    };

    // Horizontal grid (from primary y-axis)
    if (yScales.y) {
      ctx.strokeStyle = c.gridMajor; ctx.lineWidth = 1;
      yScales.y.ticks.forEach(t => {
        const y = Math.round(mapY(t, 'y')) + 0.5;
        ctx.beginPath(); ctx.moveTo(plotX, y); ctx.lineTo(plotX + plotW, y); ctx.stroke();
      });
    }

    // X-axis ticks
    const xTicks = niceTimeTicks(xMin, xMax, plotW);
    ctx.strokeStyle = c.gridMinor; ctx.lineWidth = 1;
    xTicks.forEach(t => {
      const x = Math.round(mapX(t.value)) + 0.5;
      ctx.beginPath(); ctx.moveTo(x, plotY); ctx.lineTo(x, plotY + plotH); ctx.stroke();
    });

    // Plot border (left + bottom only)
    ctx.strokeStyle = c.axisBorder; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(plotX + 0.5, plotY);
    ctx.lineTo(plotX + 0.5, plotY + plotH + 0.5);
    ctx.lineTo(plotX + plotW, plotY + plotH + 0.5);
    ctx.stroke();

    // Y-axis labels — unified column layout: rightmost column = primary if present, else first own.
    // Each column shifts left by ownColWidth.
    ctx.font = '10px ui-monospace, SF Mono, Menlo, monospace';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    // Draw a right-aligned axis-identity header atop a column, truncated to fit.
    const drawAxisHeader = (tag, xRight, color) => {
      if (!tag) return;
      ctx.save();
      ctx.font = '9px ui-monospace, SF Mono, Menlo, monospace';
      ctx.textAlign = 'right'; ctx.textBaseline = 'bottom';
      ctx.fillStyle = color;
      let s = String(tag);
      const maxTagW = this.ownColWidth - 4;
      if (ctx.measureText(s).width > maxTagW) {
        while (s.length > 1 && ctx.measureText(s + '…').width > maxTagW) s = s.slice(0, -1);
        s += '…';
      }
      ctx.fillText(s, xRight, plotY - 2);
      ctx.restore();
    };
    let leftCol = 0;
    if (yScales.y) {
      ctx.fillStyle = c.text;
      yScales.y.ticks.forEach(t => {
        const y = mapY(t, 'y');
        ctx.fillText(formatNum(t), plotX - 8 - leftCol * this.ownColWidth, y);
      });
      // Header for the primary axis when it hosts a single identifiable series.
      const yList = datasets.filter(d => (d.yAxisId || 'y') === 'y');
      if (yList.length === 1) drawAxisHeader(yScales.y.tag, plotX - 8 - leftCol * this.ownColWidth, c.text);
      leftCol++;
    }
    const ownAxisIds = Object.keys(yScales).filter(id => id.startsWith('own')).slice(0, this.ownAxisVisibleMax);
    ownAxisIds.forEach((axId) => {
      const sc = yScales[axId];
      const xLabel = plotX - 8 - leftCol * this.ownColWidth;
      const xLine = plotX - leftCol * this.ownColWidth;
      ctx.fillStyle = sc.color || c.text;
      sc.ticks.forEach(t => {
        const y = mapY(t, axId);
        ctx.fillText(formatNum(t), xLabel, y);
      });
      // Own-axis column header: its series ticker (+N for shared), in the axis color.
      drawAxisHeader(sc.tag, xLabel, sc.color || c.text);
      // Vertical separator (faint, color-tinted) for own-axis columns 1+
      if (leftCol > 0) {
        ctx.strokeStyle = hexA(sc.color || c.axisBorder, 0.35); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(xLine + 0.5, plotY); ctx.lineTo(xLine + 0.5, plotY + plotH); ctx.stroke();
      }
      leftCol++;
    });
    // Y-axis labels (right) for dual axis
    if (yScales.y2) {
      const y2Color = yScales.y2.color || c.text;
      ctx.textAlign = 'left'; ctx.fillStyle = y2Color;
      yScales.y2.ticks.forEach(t => {
        const y = mapY(t, 'y2');
        ctx.fillText(formatNum(t), plotX + plotW + 8, y);
      });
      // Right-axis identity header (left-aligned over its column), truncated to padRight.
      const y2List = datasets.filter(d => (d.yAxisId || 'y') === 'y2');
      if (y2List.length === 1 && yScales.y2.tag) {
        ctx.save();
        ctx.font = '9px ui-monospace, SF Mono, Menlo, monospace';
        ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
        ctx.fillStyle = y2Color;
        let s = String(yScales.y2.tag);
        const maxTagW = this.padRight - 4;
        if (ctx.measureText(s).width > maxTagW) {
          while (s.length > 1 && ctx.measureText(s + '…').width > maxTagW) s = s.slice(0, -1);
          s += '…';
        }
        ctx.fillText(s, plotX + plotW + 8, plotY - 2);
        ctx.restore();
      }
      // right axis line
      ctx.strokeStyle = c.axisBorder;
      ctx.beginPath(); ctx.moveTo(plotX + plotW + 0.5, plotY); ctx.lineTo(plotX + plotW + 0.5, plotY + plotH); ctx.stroke();
    }

    // X-axis labels
    ctx.fillStyle = c.text2; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    xTicks.forEach(t => {
      const x = mapX(t.value);
      ctx.fillText(t.label, x, plotY + plotH + 8);
    });

    // Draw datasets — clipped to the plot rect so off-window segments (when
    // zoomed) don't bleed into the axis gutter. Crosshair/markers stay outside
    // the clip (hoverX is already gated to [plotX, plotX+plotW]).
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.save();
    ctx.beginPath(); ctx.rect(plotX, plotY, plotW, plotH); ctx.clip();
    datasets.forEach((ds, idx) => {
      const axId = ds.yAxisId || 'y';
      const color = ds.color;

      // Fill under (only if requested)
      if (ds.fill) {
        ctx.fillStyle = hexA(color, 0.10);
        ctx.beginPath();
        ds.data.forEach((d, i) => {
          const x = mapX(d[0]);
          const y = mapY(d[1], axId);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.lineTo(mapX(ds.data[ds.data.length-1][0]), plotY + plotH);
        ctx.lineTo(mapX(ds.data[0][0]), plotY + plotH);
        ctx.closePath();
        ctx.fill();
      }

      // Line
      ctx.strokeStyle = color;
      ctx.lineWidth = ds.borderWidth || 1.6;
      if (ds.dash && ds.dash.length) ctx.setLineDash(ds.dash);
      ctx.beginPath();
      ds.data.forEach((d, i) => {
        const x = mapX(d[0]);
        const y = mapY(d[1], axId);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      // Points
      const pr = ds.pointRadius || 0;
      if (pr > 0) {
        ctx.fillStyle = color;
        ds.data.forEach(d => {
          const x = mapX(d[0]); const y = mapY(d[1], axId);
          ctx.beginPath(); ctx.arc(x, y, pr, 0, Math.PI * 2); ctx.fill();
        });
      }
    });
    ctx.restore();

    // Drag-to-zoom selection band (live during a drag).
    if (this._dragStartX !== null && this._dragCurX !== null) {
      const a = Math.max(plotX, Math.min(this._dragStartX, this._dragCurX));
      const b = Math.min(plotX + plotW, Math.max(this._dragStartX, this._dragCurX));
      if (b - a > 1) {
        ctx.fillStyle = 'rgba(110,168,255,0.12)';
        ctx.fillRect(a, plotY, b - a, plotH);
        ctx.strokeStyle = 'rgba(110,168,255,0.45)'; ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a + 0.5, plotY); ctx.lineTo(a + 0.5, plotY + plotH);
        ctx.moveTo(b - 0.5, plotY); ctx.lineTo(b - 0.5, plotY + plotH);
        ctx.stroke();
      }
    }
    // Zoomed affordance — dim hint top-left of the plot.
    if (this._zoom) {
      ctx.save();
      ctx.font = '9px ui-monospace, SF Mono, Menlo, monospace';
      ctx.fillStyle = c.text3;
      ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      ctx.fillText('zoomed · dbl-click to reset', plotX + 6, plotY + 4);
      ctx.restore();
    }

    // Hover crosshair + tooltip
    if (this.hoverX !== null && this.hoverX >= plotX && this.hoverX <= plotX + plotW) {
      const tHover = xMin + (this.hoverX - plotX) / plotW * (xMax - xMin);
      // Nearest point per dataset via binary search (xs ascending).
      const hits = datasets.map(ds => {
        const xs = this._xsFor(ds);
        return { ds, point: ds.data[this._nearestIndex(xs, tHover)] };
      });
      // Crosshair tracks the true cursor time, not series[0]'s snapped point —
      // honest for mixed-frequency overlays.
      const snapX = Math.round(this.hoverX) + 0.5;
      ctx.save();
      ctx.strokeStyle = 'rgba(255,255,255,0.18)';
      ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(snapX, plotY); ctx.lineTo(snapX, plotY + plotH); ctx.stroke();
      ctx.restore();
      // Highlight markers (each at its own nearest point)
      hits.forEach(h => {
        const axId = h.ds.yAxisId || 'y';
        const x = mapX(h.point[0]); const y = mapY(h.point[1], axId);
        ctx.fillStyle = c.tipBg;
        ctx.beginPath(); ctx.arc(x, y, 4.5, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = h.ds.color;
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2); ctx.fill();
      });
      // Tooltip header = cursor time; each row carries its own nearest date.
      this._drawTooltip(ctx, hits, tHover, cssW, plotY);
    }

    // Legend (bottom)
    this._drawLegend(ctx, datasets, plotX, plotY + plotH + 30, plotW);

    // Bloomberg ticker overlay (toggle via config.showTickers)
    if (this.config.showTickers && datasets.length) {
      this._drawTickerPanel(ctx, datasets, plotX, plotY, plotW, plotH, c);
    } else {
      this._tickerPanelBounds = null;
    }
  }

  _drawTooltip(ctx, hits, ts, cssW, plotY) {
    const c = this.config.colors;
    ctx.font = '11px ui-monospace, SF Mono, Menlo, monospace';
    const date = formatTipDate(ts);
    const cursorDay = Math.floor(ts / 86400000);
    const lines = hits.map(h => {
      const mult = h.ds.mult || 1;
      // Magnify truth: show the TRUE (un-scaled) value; the plotted line stays
      // amplified (that's magnify's purpose) but the readout must not lie. The
      // ×N token tells the analyst the line is amplified.
      const value = formatNum(h.point[1] / mult)
        + (h.ds.unitLabel ? ' ' + h.ds.unitLabel : '')
        + ((mult && mult !== 1) ? '  ×' + mult : '');
      const pt = h.point[0];
      // Per-row own date when this row's nearest point falls on a different day
      // than the cursor (mixed-frequency overlays).
      const dateTok = (Math.floor(pt / 86400000) !== cursorDay) ? formatTipDate(pt) : '';
      return { label: h.ds.label, value, color: h.ds.color, dateTok };
    });
    const padX = 10, padY = 8, lineH = 16;
    let maxW = ctx.measureText(date).width;
    lines.forEach(l => {
      // label + value on the main line; the dim date token sits between them.
      const dateW = l.dateTok ? ctx.measureText(l.dateTok).width + 10 : 0;
      const w = ctx.measureText(l.label + '  ' + l.value).width + 14 + dateW;
      if (w > maxW) maxW = w;
    });
    const tipW = maxW + padX * 2;
    const tipH = padY * 2 + 18 + lines.length * lineH;
    let tx = mapXClamp(this.hoverX) + 14;
    if (tx + tipW > cssW - 6) tx = mapXClamp(this.hoverX) - tipW - 14;
    const ty = Math.max(plotY + 4, 8);
    // Box
    ctx.fillStyle = c.tipBg;
    ctx.strokeStyle = c.tipBorder;
    ctx.lineWidth = 1;
    roundRect(ctx, tx, ty, tipW, tipH, 5);
    ctx.fill(); ctx.stroke();
    // Date
    ctx.fillStyle = c.textHi;
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillText(date, tx + padX, ty + padY);
    // Lines
    lines.forEach((l, i) => {
      const y = ty + padY + 18 + i * lineH;
      ctx.fillStyle = l.color;
      ctx.fillRect(tx + padX, y + 5, 8, 2);
      ctx.fillStyle = c.text;
      const labelStr = l.label;
      ctx.fillText(labelStr, tx + padX + 14, y);
      // Per-row own date (dim), placed just after the label.
      if (l.dateTok) {
        const lw = ctx.measureText(labelStr).width;
        ctx.fillStyle = c.text3;
        ctx.fillText(l.dateTok, tx + padX + 14 + lw + 6, y);
        ctx.fillStyle = c.text;
      }
      ctx.fillStyle = c.textHi;
      ctx.textAlign = 'right';
      ctx.fillText(l.value, tx + tipW - padX, y);
      ctx.textAlign = 'left';
    });
    function mapXClamp(x) { return x; }
  }

  _drawLegend(ctx, datasets, x, y, w) {
    const c = this.config.colors;
    ctx.font = '11px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    let cx = x, cy = y;
    const lineH = 18;
    this._legendHits = [];   // recaptured each paint; clickable rects → host srcIdx
    datasets.forEach(ds => {
      const labelText = ds.label + (this.config.showTickers && ds.ticker ? ' · ' + ds.ticker : '');
      const tw = ctx.measureText(labelText).width;
      const itemW = 18 + tw + 16;
      if (cx + itemW > x + w) { cx = x; cy += lineH; }
      ctx.fillStyle = ds.color;
      ctx.fillRect(cx, cy - 1, 14, 2);
      ctx.fillStyle = c.text;
      ctx.fillText(labelText, cx + 18, cy);
      // srcIdx is the host sers index (legend iterates the VISIBLE/compacted set,
      // so positional index ≠ host index — ds.srcIdx carries the truth).
      this._legendHits.push({ x: cx, y: cy - lineH / 2, w: itemW, h: lineH, srcIdx: ds.srcIdx });
      cx += itemW;
    });
  }

  _drawTickerPanel(ctx, datasets, plotX, plotY, plotW, plotH, c) {
    const padX = 10, padY = 8, lineH = 14;
    const dotW = 10;
    const gap = 14;
    const hintH = 14;  // extra space for "click to copy" hint at bottom

    // Measure widths
    ctx.font = '500 10px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
    let maxNameW = 0;
    datasets.forEach(ds => {
      const w = ctx.measureText(ds.label).width;
      if (w > maxNameW) maxNameW = w;
    });
    ctx.font = '10px ui-monospace, SF Mono, Menlo, monospace';
    let maxTickerW = 0;
    datasets.forEach(ds => {
      const tk = ds.ticker || '—';
      const w = ctx.measureText(tk).width;
      if (w > maxTickerW) maxTickerW = w;
    });
    ctx.font = '600 9px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
    const headerNameW = ctx.measureText('INDICATOR').width;
    const headerTickerW = ctx.measureText('BLOOMBERG TICKER').width;
    maxNameW = Math.max(maxNameW, headerNameW);
    maxTickerW = Math.max(maxTickerW, headerTickerW);
    const hintW = ctx.measureText('Click panel to copy tickers ⧉').width;

    const contentW = dotW + 6 + maxNameW + gap + maxTickerW;
    const panelW = padX * 2 + Math.max(contentW, hintW);
    const panelH = padY * 2 + lineH * (datasets.length + 1) + 4 + hintH;

    let px = plotX + plotW - panelW - 10;
    let py = plotY + 10;
    if (px < plotX + 4) px = plotX + 4;

    // Save bounds for click detection
    this._tickerPanelBounds = { x: px, y: py, w: panelW, h: panelH };

    // Background box
    ctx.fillStyle = 'rgba(11, 16, 24, 0.92)';
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 1;
    roundRect(ctx, px, py, panelW, panelH, 5);
    ctx.fill(); ctx.stroke();

    // Header
    ctx.font = '600 9px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillStyle = c.text3 || '#6b7686';
    ctx.fillText('INDICATOR', px + padX + dotW + 6, py + padY);
    ctx.fillText('BLOOMBERG TICKER', px + padX + dotW + 6 + maxNameW + gap, py + padY);
    ctx.strokeStyle = 'rgba(255,255,255,0.10)';
    ctx.beginPath();
    ctx.moveTo(px + padX, py + padY + lineH - 2);
    ctx.lineTo(px + panelW - padX, py + padY + lineH - 2);
    ctx.stroke();

    // Rows
    datasets.forEach((ds, i) => {
      const rowY = py + padY + lineH + 2 + i * lineH;
      ctx.fillStyle = ds.color;
      ctx.fillRect(px + padX, rowY + 4, dotW, 2);
      ctx.font = '500 10px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
      ctx.fillStyle = c.text || '#e8eaed';
      ctx.fillText(ds.label, px + padX + dotW + 6, rowY);
      ctx.font = '10px ui-monospace, SF Mono, Menlo, monospace';
      ctx.fillStyle = ds.ticker ? (c.textHi || '#e8eaed') : (c.text3 || '#6b7686');
      ctx.fillText(ds.ticker || '—', px + padX + dotW + 6 + maxNameW + gap, rowY);
    });

    // "Click to copy" hint at bottom
    ctx.font = '9px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
    ctx.fillStyle = '#6ea8ff';
    ctx.textAlign = 'center';
    ctx.fillText('Click panel to copy tickers ⧉', px + panelW / 2, py + panelH - hintH + 1);
    ctx.textAlign = 'left';
  }

  // Lazy per-dataset ascending x-array cache (keyed by dataset object). Dropped
  // with the instance on destroy-recreate, so no invalidation is needed.
  _xsFor(ds) {
    if (!this._xCache) this._xCache = new Map();
    let xs = this._xCache.get(ds);
    if (!xs) { xs = ds.data.map(d => d[0]); this._xCache.set(ds, xs); }
    return xs;
  }

  // Index of the nearest x to t (xs sorted ascending — time series are).
  _nearestIndex(xs, t) {
    let lo = 0, hi = xs.length - 1;
    if (t <= xs[0]) return 0;
    if (t >= xs[hi]) return hi;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (xs[mid] < t) lo = mid + 1; else hi = mid; }
    return (lo > 0 && (t - xs[lo - 1]) <= (xs[lo] - t)) ? lo - 1 : lo;
  }

  // Pure predicate: is (px,py) over any legend item? (cursor feedback only).
  _isOverLegend(px, py) {
    for (const it of this._legendHits) {
      if (px >= it.x && px <= it.x + it.w && py >= it.y && py <= it.y + it.h) return true;
    }
    return false;
  }

  // Hit-test + dispatch onLegendClick (toggle, or isolate on Alt/Meta).
  // Called first in _onDown so it wins over drag/ticker. Returns true if handled.
  _legendHitTest(px, py, e) {
    for (const it of this._legendHits) {
      if (px >= it.x && px <= it.x + it.w && py >= it.y && py <= it.y + it.h) {
        if (typeof this.config.onLegendClick === 'function') {
          this.config.onLegendClick(it.srcIdx, { isolate: !!(e && (e.altKey || e.metaKey)) });
        }
        return true;
      }
    }
    return false;
  }
}

// ===== chart helpers =====
function niceTicks(min, max, count) {
  if (!isFinite(min) || !isFinite(max)) return { min: 0, max: 1, values: [0, 1] };
  const range = max - min;
  if (range <= 0) return { min: min - 1, max: max + 1, values: [min - 1, min, min + 1] };
  const rough = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  const niceNorm = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  const step = niceNorm * mag;
  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const values = [];
  for (let v = niceMin; v <= niceMax + step / 1000; v += step) {
    values.push(Math.round(v / step) * step);
  }
  return { min: niceMin, max: niceMax, values };
}

function niceTimeTicks(tMin, tMax, plotW) {
  const dayMs = 86400000;
  const days = (tMax - tMin) / dayMs;
  // Aim for one tick every ~110px of plot width
  const targetCount = Math.max(3, Math.min(8, Math.floor(plotW / 110)));
  let unit, step, format;
  if (days <= 7) {
    unit = 'day'; step = 1;
    format = ts => { const d = new Date(ts); return d.toLocaleString('en-US', {month:'short', day:'numeric'}); };
  } else if (days <= 21) {
    unit = 'day'; step = 2;
    format = ts => { const d = new Date(ts); return d.toLocaleString('en-US', {month:'short', day:'numeric'}); };
  } else if (days <= 60) {
    unit = 'week'; step = 1;
    format = ts => { const d = new Date(ts); return d.toLocaleString('en-US', {month:'short', day:'numeric'}); };
  } else if (days <= 180) {
    unit = 'month'; step = 1;
    format = ts => { const d = new Date(ts); return d.toLocaleString('en-US', {month:'short'}) + " '" + String(d.getFullYear()).slice(2); };
  } else if (days <= 540) {
    unit = 'month'; step = 2;
    format = ts => { const d = new Date(ts); return d.toLocaleString('en-US', {month:'short'}) + " '" + String(d.getFullYear()).slice(2); };
  } else if (days <= 1095) {
    unit = 'month'; step = 3;
    format = ts => { const d = new Date(ts); return d.toLocaleString('en-US', {month:'short'}) + " '" + String(d.getFullYear()).slice(2); };
  } else {
    unit = 'year'; step = 1;
    format = ts => String(new Date(ts).getFullYear());
  }
  const ticks = [];
  let t = startOfUnit(tMin, unit);
  let safety = 0;
  while (t <= tMax && safety++ < 1000) {
    if (t >= tMin) ticks.push({ value: t, label: format(t) });
    t = addStep(t, unit, step);
  }
  // Trim if too many
  while (ticks.length > targetCount + 2) {
    const dropEvery = Math.ceil(ticks.length / (targetCount + 1));
    const newTicks = ticks.filter((_, i) => i % dropEvery === 0);
    if (newTicks.length === ticks.length) break;
    ticks.length = 0; ticks.push(...newTicks);
    if (ticks.length <= targetCount + 1) break;
  }
  return ticks;
}

function startOfUnit(ts, unit) {
  const d = new Date(ts);
  if (unit === 'year') return new Date(d.getFullYear(), 0, 1).getTime();
  if (unit === 'month') return new Date(d.getFullYear(), d.getMonth(), 1).getTime();
  if (unit === 'week') {
    const day = d.getDay(); const diff = (day + 6) % 7;
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() - diff).getTime();
  }
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}
function addStep(ts, unit, step) {
  const d = new Date(ts);
  if (unit === 'year') return new Date(d.getFullYear() + step, 0, 1).getTime();
  if (unit === 'month') return new Date(d.getFullYear(), d.getMonth() + step, 1).getTime();
  if (unit === 'week') return ts + step * 7 * 86400000;
  return ts + step * 86400000;
}

function formatNum(v) {
  if (v === null || v === undefined || !isFinite(v)) return '—';
  const abs = Math.abs(v);
  if (abs === 0) return '0';
  if (abs >= 1e9) return (v / 1e9).toFixed(2).replace(/\.?0+$/, '') + 'B';
  if (abs >= 1e6) return (v / 1e6).toFixed(2).replace(/\.?0+$/, '') + 'M';
  if (abs >= 10000) return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (abs >= 100) return v.toFixed(1);
  if (abs >= 10) return v.toFixed(2);
  if (abs >= 1) return v.toFixed(2);
  return v.toFixed(3);
}
function formatTipDate(ts) {
  const d = new Date(ts);
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function hexA(hex, alpha) {
  // Accepts #rgb / #rrggbb. Returns rgba(r,g,b,a)
  if (!hex || hex[0] !== '#') return hex;
  let r, g, b;
  if (hex.length === 4) { r = parseInt(hex[1]+hex[1],16); g = parseInt(hex[2]+hex[2],16); b = parseInt(hex[3]+hex[3],16); }
  else { r = parseInt(hex.slice(1,3),16); g = parseInt(hex.slice(3,5),16); b = parseInt(hex.slice(5,7),16); }
  return `rgba(${r},${g},${b},${alpha})`;
}

function roundRect(ctx, x, y, w, h, r) {
  if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); return; }
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawSparkline(cv, series) {
  if (!series || !series.length) return;
  const ctx = cv.getContext('2d');
  cv.width = cv.offsetWidth * window.devicePixelRatio;
  cv.height = cv.offsetHeight * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  const w = cv.offsetWidth, h = cv.offsetHeight;
  const vals = series.map(d => d[1]);
  const min = Math.min(...vals), max = Math.max(...vals);
  const rng = max - min || 1;
  const last = vals[vals.length-1], first = vals[0];
  const color = last >= first ? '#4ade80' : '#f87171';
  ctx.clearRect(0, 0, w, h);
  ctx.beginPath();
  series.forEach((d, i) => {
    const x = (i / (series.length-1)) * w;
    const y = h - ((d[1] - min) / rng) * h;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.2;
  ctx.stroke();
  // fill gradient
  ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
  const gr = ctx.createLinearGradient(0, 0, 0, h);
  gr.addColorStop(0, color + '22'); gr.addColorStop(1, color + '00');
  ctx.fillStyle = gr; ctx.fill();
}

// =========== RIGHT RAIL ===========
function renderRightRail() {
  renderFloatingBar();
  const r = $('right-rail');
  if (state.view === 'workspace') return renderWorkspaceContext(r);
  if (state.view === 'pce') {
    // PCE browser: variant/transform toggles + search + tree
    let html = `
      <h3>PCE Browser</h3>
      <div class="pce-rail-controls">
        <div class="pce-control-row">
          <span class="pce-control-label">Variant</span>
          <div class="pce-toggle" id="pce-variant">
            <button class="opt ${state.pceVariant==='core'?'active':''}" data-v="core">Core</button>
            <button class="opt ${state.pceVariant==='full'?'active':''}" data-v="full">Full</button>
          </div>
        </div>
        <div class="pce-control-row">
          <span class="pce-control-label">Transform</span>
          <div class="pce-toggle" id="pce-transform">
            <button class="opt ${state.pceTransform==='mom'?'active':''}" data-t="mom">MoM</button>
            <button class="opt ${state.pceTransform==='yoy'?'active':''}" data-t="yoy">YoY</button>
          </div>
        </div>
        <input class="pce-search" id="pce-search" placeholder="Filter…" autocomplete="off" value="${escapeAttr(state.pceSearch || '')}">
        <div class="pce-rail-actions">
          <span class="muted" id="pce-count-rail">${state.pceSelected.length} selected</span>
          <button class="clear-btn" id="pce-clear">Clear</button>
        </div>
      </div>
      <div class="pce-tree-rail" id="pce-tree"></div>`;
    r.innerHTML = html;
    r.querySelectorAll('#pce-variant .opt').forEach(b => b.onclick = () => {
      state.pceVariant = b.dataset.v;
      // Per-series settings persist; ensurePceSeriesSettings re-derives ticker/name
      renderRightRail(); drawPceChart(); renderPceSeriesRows();
      document.querySelectorAll('.ws-controls-bar .pbtn[data-act^="pce-var"]').forEach(x =>
        x.classList.toggle('active', x.dataset.act === 'pce-var-' + state.pceVariant));
    });
    r.querySelectorAll('#pce-transform .opt').forEach(b => b.onclick = () => {
      state.pceTransform = b.dataset.t;
      renderRightRail(); drawPceChart(); renderPceSeriesRows();
      document.querySelectorAll('.ws-controls-bar .pbtn[data-act^="pce-tr"]').forEach(x =>
        x.classList.toggle('active', x.dataset.act === 'pce-tr-' + state.pceTransform));
    });
    r.querySelector('#pce-clear').onclick = () => {
      state.pceSelected = [];
      state.pceSeriesSettings = null;
      renderRightRail(); drawPceChart(); renderPceSeriesRows();
    };
    const searchEl = r.querySelector('#pce-search');
    searchEl.oninput = () => { state.pceSearch = searchEl.value; renderPceTree(); };
    renderPceTree();
    return;
  }
  if (state.view === 'panel') {
    const p = D.panels.find(x => x.id === state.panel);
    if (!p) { r.innerHTML = ''; return; }
    let html = `<h3>Panel</h3>
      <div style="background:var(--bg-elev-2);padding:10px 12px;border-radius:4px;margin-bottom:14px;font-family:var(--mono);font-size:11px;">
        <div style="margin-bottom:6px;"><span class="muted">Theme</span><br>${escapeHtml(D.themes.find(t=>t[0]===p.theme)[1])}</div>
        <div style="margin-bottom:6px;"><span class="muted">Indicators</span><br>${p.indicators.length}</div>
        <div style="margin-bottom:6px;"><span class="muted">Axis</span><br>${p.axis === 'dual' ? 'Multi-axis' : 'Single'}</div>
        <div><span class="muted">Units</span><br>${escapeHtml(p.unit_label)}</div>
      </div>
      <h3>Other panels</h3>`;
    D.panels.filter(o => o.id !== p.id).slice(0, 12).forEach(o => {
      html += `<div class="feed-item" data-pid="${escapeAttr(o.id)}">
        <div class="feed-theme">${escapeHtml(D.themes.find(t=>t[0]===o.theme)[1])}</div>
        <div class="feed-name">${escapeHtml(o.name)}</div>
        <div class="feed-row"><span>${o.indicators.length} indicators</span><span class="v">${escapeHtml(o.unit_label)}</span></div>
      </div>`;
    });
    r.innerHTML = html;
    r.querySelectorAll('.feed-item[data-pid]').forEach(el => el.onclick = () => navPanel(el.dataset.pid));
    return;
  }
  if (state.view === 'indicator') {
    const e = D.indicators[state.indicator];
    let html = `<h3>Indicator metadata</h3>
      <div style="background:var(--bg-elev-2);padding:10px 12px;border-radius:4px;margin-bottom:14px;font-family:var(--mono);font-size:11px;">
        <div style="margin-bottom:6px;"><span class="muted">Ticker</span><br><span style="color:var(--accent);">${escapeHtml(e.t)}</span></div>
        <div style="margin-bottom:6px;"><span class="muted">Theme</span><br>${escapeHtml(themeLabelOf(e.th))}</div>
        <div style="margin-bottom:6px;"><span class="muted">Category</span><br>${escapeHtml(e.cl)}</div>
        <div style="margin-bottom:6px;"><span class="muted">Units</span><br>${escapeHtml(e.u||'—')}</div>
        <div style="margin-bottom:6px;"><span class="muted">Frequency</span><br>${escapeHtml(e.f)}</div>
        <div style="margin-bottom:6px;"><span class="muted">Source</span><br>${escapeHtml(e.s||'—')}</div>
        <div style="margin-bottom:6px;"><span class="muted">Latest</span><br>${fmtNum(e.lv,e.u)} ${escapeHtml(e.u||'')} (${e.ld})</div>
        <div><span class="muted">Observations</span><br>${e.n}</div>
      </div>
      <h3>In ${escapeHtml(e.cl)}</h3>`;
    const peers = Object.entries(D.indicators).filter(([i,x]) => x.c === e.c && i !== state.indicator).slice(0, 12);
    peers.forEach(([i, x]) => {
      html += `<div class="feed-item" data-ind="${escapeAttr(i)}">
        <div class="feed-name">${escapeHtml(i)}</div>
        <div class="feed-row"><span>${escapeHtml(x.t)}</span><span class="v">${fmtNum(x.lv,x.u)}</span></div>
      </div>`;
    });
    r.innerHTML = html;
    r.querySelectorAll('.feed-item').forEach(el => el.onclick = () => navIndicator(el.dataset.ind));
  } else {
    let html = `<h3>Latest prints</h3>`;
    D.prints_feed.slice(0, 30).forEach(p => {
      const themeLabel = (D.themes.find(t=>t[0]===p.th)||['','—'])[1];
      html += `<div class="feed-item" data-ind="${escapeAttr(p.i)}">
        <div class="feed-theme">${escapeHtml(themeLabel)}</div>
        <div class="feed-name">${escapeHtml(p.i)}</div>
        <div class="feed-row"><span>${p.d}</span><span class="v">${fmtNum(p.v, p.u)} ${escapeHtml(p.u||'')}</span></div>
      </div>`;
    });
    r.innerHTML = html;
    r.querySelectorAll('.feed-item').forEach(el => el.onclick = () => navIndicator(el.dataset.ind));
  }
}

// =========== SEARCH ===========
// Matcher core (SCORE, ALIASES, reEsc, resolveAliases, scoreIndicator, rankIndicators,
// SEARCH_MAX_VISIBLE) is defined once near the top (after const D) so it is shared with
// the Workspace add-indicator overlay. This block owns only the topbar search UI.
const search = $('search');
const sr = $('search-results');

function renderSearchResults(ranked) {
  if (!ranked.length) {
    sr.innerHTML = '<div class="item"><div class="name muted">No matches</div></div>';
    return;
  }
  const total = ranked.length;
  const shown = ranked.slice(0, SEARCH_MAX_VISIBLE);

  // Group shown rows by category-label, preserving each group's best (first) rank.
  const groups = new Map();   // cl -> {label, items:[[name,e,score]]}
  for (const row of shown) {
    const cl = row[1].cl || 'Other';
    if (!groups.has(cl)) groups.set(cl, { label: cl, items: [] });
    groups.get(cl).items.push(row);
  }
  // Group order = order of first appearance in `shown` (already rank-sorted),
  // so the category containing the best hit comes first.
  let html = '';
  for (const g of groups.values()) {
    html += `<div class="sr-group">${escapeHtml(g.label)} <span class="sr-gcount">${g.items.length}</span></div>`;
    html += g.items.map(([name, e]) => `<div class="item" data-ind="${escapeAttr(name)}">
      <div class="name">${escapeHtml(name)}</div>
      <div class="meta">${escapeHtml(e.t)} · ${escapeHtml(e.cl)} · ${escapeHtml(e.f || '')}</div>
    </div>`).join('');
  }
  if (total > SEARCH_MAX_VISIBLE) {
    html += `<div class="sr-footer muted">+${total - SEARCH_MAX_VISIBLE} more — refine your query</div>`;
  }
  sr.innerHTML = html;
  sr.querySelectorAll('.item[data-ind]').forEach(el => {
    el.onclick = () => { sr.classList.remove('open'); search.value = ''; navIndicator(el.dataset.ind); };
  });
}

let _searchTimer = null;
function runGlobalSearch() {
  const q = search.value.trim();
  if (!q) { sr.classList.remove('open'); return; }
  const ranked = rankIndicators(q);
  renderSearchResults(ranked);
  sr.classList.add('open');
}
search.addEventListener('input', () => {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(runGlobalSearch, 120);   // light debounce, headroom
});
// Enter / Escape niceties: Enter opens top hit, Esc closes.
search.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') { sr.classList.remove('open'); }
  else if (ev.key === 'Enter') {
    const first = sr.querySelector('.item[data-ind]');
    if (first) { sr.classList.remove('open'); search.value = ''; navIndicator(first.dataset.ind); }
  }
});
document.addEventListener('click', e => {
  if (!sr.contains(e.target) && e.target !== search) sr.classList.remove('open');
});

// =========== TOPBAR NAV ===========
$('btn-home').onclick = navHome;
$('btn-panels').onclick = navPanelsIndex;
$('btn-pce').onclick = navPceDashboard;
$('btn-workspace').onclick = () => navWorkspace();
$('btn-matts-view').onclick = () => navMattsView();
$('btn-back').onclick = navBack;
$('btn-fwd').onclick = navForward;
// Rail drawer toggle (P1C-05): collapse/restore the right rail by choice; re-render the
// current view so its chart re-fits to the new width via the existing render→draw path.
$('btn-rail-toggle').onclick = () => {
  document.querySelector('main.grid').classList.toggle('rail-collapsed');
  renderMain();
};
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); navBack(); }
  else if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); navForward(); }
});

// =========== UTILS ===========
function escapeHtml(s) {
  return String(s)
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'", '&#39;');
}
function escapeAttr(s) {
  return String(s)
    .replaceAll('&','&amp;')
    .replaceAll('"','&quot;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;');
}
function cssEscapeAttr(s) {
  // Escape only backslash and double-quote — used inside `[data-ind="..."]`
  return String(s).replaceAll('\\','\\\\').replaceAll('"','\\"');
}

// =========== INIT ===========
renderLeftRail();
renderMain();
renderRightRail();
</script>
</body>
</html>
"""

# Inject payload
HTML = HTML.replace("__PAYLOAD__", payload_json)

out_path = ROOT / "macro_dashboard.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)
size_mb = out_path.stat().st_size / 1024 / 1024
print(f"Wrote {out_path} ({size_mb:.2f} MB)")
