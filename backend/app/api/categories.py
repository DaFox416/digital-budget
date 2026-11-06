from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.repositories import categories as categories_repo
from app.schemas.categories import CategoryRead

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(session: SessionDep, user_id: CurrentUserId) -> list[CategoryRead]:
    return [
        CategoryRead.model_validate(category)
        for category in categories_repo.list_all(session, user_id)
    ]
