import itertools
import random

import pytest

from app.modules.poker.settle import Transfer, settle


def apply(balances, transfers):
    left = dict(balances)
    for t in transfers:
        assert t.amount > 0
        left[t.payer] += t.amount
        left[t.payee] -= t.amount
    return left


def test_simple():
    assert settle({"A": 300, "B": -300}) == [Transfer("B", "A", 300)]


def test_everyone_square():
    assert settle({"A": 0, "B": 0}) == []


def test_rejects_unbalanced():
    with pytest.raises(ValueError):
        settle({"A": 100, "B": -50})


def test_typical_home_game():
    balances = {"Nils": 1250, "Sam": -500, "Alex": -500, "Kim": 250, "Jo": -500}
    transfers = settle(balances)
    assert all(v == 0 for v in apply(balances, transfers).values())
    assert len(transfers) <= len(balances) - 1


@pytest.mark.parametrize("seed", range(50))
def test_random_games_settle_in_at_most_n_minus_one(seed):
    rng = random.Random(seed)
    names = [f"p{i}" for i in range(rng.randint(2, 9))]
    nets = [rng.randint(-50, 50) * 100 for _ in names[:-1]]
    balances = dict(zip(names, [*nets, -sum(nets)], strict=True))
    transfers = settle(balances)
    assert all(v == 0 for v in apply(balances, transfers).values())
    assert len(transfers) <= len([b for b in balances.values() if b]) - 1 or not transfers
    # Nobody both pays and receives.
    payers = {t.payer for t in transfers}
    assert not payers & {t.payee for t in transfers}
    assert all(a != b for a, b in itertools.pairwise(transfers))
