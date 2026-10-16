"""Who pays whom after a cash game, in as few transfers as possible."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Transfer:
    payer: str
    payee: str
    amount: int  # minor units (öre, cents)


def settle(balances: dict[str, int]) -> list[Transfer]:
    """Greedy: the biggest loser pays the biggest winner until everyone is square.

    Produces at most n-1 transfers. (The true minimum is NP-hard in general; greedy is
    optimal or within one transfer for home-game sized tables.)
    """
    if sum(balances.values()) != 0:
        raise ValueError("balances must sum to zero")
    debtors = sorted(((-b, p) for p, b in balances.items() if b < 0), reverse=True)
    creditors = sorted(((b, p) for p, b in balances.items() if b > 0), reverse=True)
    transfers = []
    while debtors and creditors:
        owe, payer = debtors[0]
        due, payee = creditors[0]
        amount = min(owe, due)
        transfers.append(Transfer(payer, payee, amount))
        debtors[0] = (owe - amount, payer)
        creditors[0] = (due - amount, payee)
        debtors = sorted((d for d in debtors if d[0] > 0), reverse=True)
        creditors = sorted((c for c in creditors if c[0] > 0), reverse=True)
    return transfers
