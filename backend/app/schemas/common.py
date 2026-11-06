from decimal import Decimal
from typing import Annotated

from pydantic import Field

# Money travels as a JSON string ("387.56") in responses; requests accept strings or numbers.
# max_digits/decimal_places mirror NUMERIC(12, 2), so "12.345" gets a 422 before reaching the DB.
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
