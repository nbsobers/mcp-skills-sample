---
name: refunds
description: Calculate a mock refund amount with a flat restocking fee. Use when the user asks to compute a refund, restocking fee, or return amount for a test order.
metadata:
  version: "1.0"
---

# Refunds

A **nested-path** skill (`skill://acme/billing/refunds/...`) used to test SEP-2640
nested skill-path support: the skill-path is `acme/billing/refunds`, the prefix
`acme/billing` is purely organizational, and the final segment matches the
frontmatter `name` (`refunds`).

## Instructions

1. Run the helper script with the order amount:

   ```
   python scripts/refund.py <amount>
   ```

2. Return the refund breakdown exactly as printed (original amount, 10% restocking
   fee, refund total).

## Files

- `scripts/refund.py` - prints the refund breakdown for a given amount.
