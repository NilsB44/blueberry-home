"""The owner's economy: accounts and loans, subscriptions, and a wishlist checked against
purchase rules.

Like the home-screen layout, the web app owns the meaning (net worth, totals, which rules pass);
the API only checks the shape and size and stores it.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.auth.deps import DbSession, OwnerUser
from app.auth.models import utcnow
from app.modules.economy.models import EconomyData

router = APIRouter(prefix="/api/economy", tags=["economy"])

Name = Annotated[str, Field(min_length=1, max_length=60)]
# SEK. Generous, but keeps a typo from becoming a number JSON can't round-trip.
Amount = Annotated[float, Field(ge=-1e12, le=1e12)]
Positive = Annotated[float, Field(ge=0, le=1e12)]


class Account(BaseModel):
    name: Name
    # A loan's balance is what is owed, as a positive number; it counts against net worth.
    kind: Literal["cash", "investment", "pension", "property", "loan", "other"]
    balance: Amount


class Subscription(BaseModel):
    name: Name
    price: Positive
    period: Literal["month", "year"]


class Rules(BaseModel):
    wait_days: int = Field(default=7, ge=0, le=365)
    # At or above this price the longer wait applies.
    big_price: Positive = 5000
    big_wait_days: int = Field(default=30, ge=0, le=365)
    max_net_worth_pct: float = Field(default=1, ge=0, le=100)
    # 0: not set, so the emergency-fund rule is skipped.
    monthly_expenses: Positive = 0
    emergency_months: float = Field(default=3, ge=0, le=60)
    # After tax. 0: not set, so the hours-of-work rule is skipped.
    hourly_pay: Positive = 0
    max_work_hours: float = Field(default=20, ge=0, le=10_000)
    max_cost_per_use: Positive = 50


class WishItem(BaseModel):
    name: Name
    price: Positive
    added: date
    # How many times you expect to use it, for cost per use. 0: not estimated.
    uses: int = Field(default=0, ge=0, le=1_000_000)
    # The yes/no questions answered so far, by the web app's question id.
    checks: dict[Annotated[str, Field(max_length=32)], bool] = Field(
        default_factory=dict, max_length=50
    )


class Economy(BaseModel):
    accounts: list[Account] = Field(default_factory=list, max_length=100)
    subscriptions: list[Subscription] = Field(default_factory=list, max_length=200)
    rules: Rules = Field(default_factory=Rules)
    wishlist: list[WishItem] = Field(default_factory=list, max_length=100)


@router.get("")
def get_economy(user: OwnerUser, db: DbSession) -> Economy:
    row = db.get(EconomyData, user.id)
    return Economy.model_validate_json(row.data) if row else Economy()


@router.put("")
def put_economy(economy: Economy, user: OwnerUser, db: DbSession) -> Economy:
    row = db.get(EconomyData, user.id) or EconomyData(user_id=user.id, data="")
    row.data = economy.model_dump_json()
    row.updated_at = utcnow()
    db.add(row)
    db.commit()
    return economy
