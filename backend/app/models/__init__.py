"""SQLAlchemy models. Importing this package registers every table in Base.metadata."""

from app.models.account import Account
from app.models.base import Base
from app.models.category import Category
from app.models.credit_config import CreditConfig
from app.models.movement import Movement
from app.models.user import User

__all__ = ["Account", "Base", "Category", "CreditConfig", "Movement", "User"]
