from fastapi import APIRouter

router = APIRouter()


@router.get("/list")
async def list_tests():
    return [
        {"name": "Glucose", "ref_min": 3.9, "ref_max": 5.5, "units": "mmol/L"},
        {"name": "Cholesterol", "ref_min": 0, "ref_max": 200, "units": "mg/dL"},
    ]

