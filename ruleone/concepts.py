"""XBRL concept aliases. Earlier tags take priority; later tags fill gaps
(e.g. the 2018 ASC 606 switch from `Revenues` to `RevenueFromContract...`)."""

USD, USD_SH, SH = "USD", "USD-per-shares", "shares"

# field -> (unit, [us-gaap tags])   duration (annual) facts
FLOW = {
    "revenue": (USD, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                      "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                      "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense"]),
    "gross_profit": (USD, ["GrossProfit"]),
    "op_income": (USD, ["OperatingIncomeLoss"]),
    "pretax": (USD, ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                     "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]),
    "tax": (USD, ["IncomeTaxExpenseBenefit"]),
    "interest": (USD, ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]),
    "net_income": (USD, ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"]),
    "eps": (USD_SH, ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"]),
    "shares": (SH, ["WeightedAverageNumberOfDilutedSharesOutstanding",
                    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
                    "WeightedAverageNumberOfSharesOutstandingBasic"]),
    "ocf": (USD, ["NetCashProvidedByUsedInOperatingActivities",
                  "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
    "capex": (USD, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]),
    "da": (USD, ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                 "DepreciationAmortizationAndAccretionNet", "Depreciation"]),
    "dividends_paid": (USD, ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"]),
    "dps": (USD_SH, ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]),
    "buybacks": (USD, ["PaymentsForRepurchaseOfCommonStock"]),
}

# field -> (unit, [tags])   instant (balance-sheet) facts
INSTANT = {
    "equity": (USD, ["StockholdersEquity",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]),
    "lt_debt": (USD, ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"]),
    "debt_current": (USD, ["LongTermDebtCurrent", "DebtCurrent"]),
    "cash": (USD, ["CashAndCashEquivalentsAtCarryingValue",
                   "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]),
    "assets": (USD, ["Assets"]),
}

# Fields fetched universe-wide in stage 1 (keeps the request count ~600).
STAGE1_FLOW = ["revenue", "op_income", "pretax", "tax", "net_income", "eps", "shares", "ocf", "capex"]
STAGE1_INSTANT = ["equity", "lt_debt"]
