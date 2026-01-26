from fastapi import APIRouter, Depends

from ..models import User
from .deps import get_current_user

router = APIRouter()


@router.post("/request")
async def request_consultation(current_user: User = Depends(get_current_user)):
    return {
        "status": "requested",
        "details": "consultation scheduled (MVP stub)",
        "user_id": current_user.id,
    }

