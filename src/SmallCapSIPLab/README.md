# SmallCapSIPLab

## Small-Cap Mutual Fund SIP Research

SmallCapSIPLab is a research and production decision framework for selecting a current Rank #1 small-cap mutual fund for a monthly SIP using systematic, historically tested strategies.

The project separates:

1. Historical research/backtesting
2. Saved research artifacts
3. Production SIP decision/reporting

This separation is intentional.

---

# 1. Project Purpose

The purpose of SmallCapSIPLab is to answer:

> "Based on the latest completed-month data and the strategy selected from historical research, which small-cap mutual fund is currently Rank #1 for the next new monthly SIP?"

The production SIP model is:

- Monthly SIP: ₹10,000
- New SIP allocation: 100% to Rank #1
- Informational ranks: #2 to #5
- Existing holdings: remain invested
- Automatic selling: No
- Automatic rebalancing: No
- Ranking frequency: Monthly

A change in Rank #1 does not trigger a sale of previous holdings.

If Rank #1 changes next month, the next new ₹10,000 SIP is directed to the new Rank #1.

Therefore, over time, the portfolio can contain multiple funds.

---

# 2. Project Architecture

The project has two distinct execution layers.

## Research Layer

```text
backtest.py