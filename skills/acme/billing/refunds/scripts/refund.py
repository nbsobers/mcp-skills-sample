"""Print a mock refund breakdown: amount minus a flat 10% restocking fee."""

import sys


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python refund.py <amount>", file=sys.stderr)
        raise SystemExit(1)

    amount = float(sys.argv[1])
    fee = round(amount * 0.10, 2)
    refund = round(amount - fee, 2)

    print(f"original:        {amount:.2f}")
    print(f"restocking fee:  {fee:.2f}")
    print(f"refund total:    {refund:.2f}")


if __name__ == "__main__":
    main()
