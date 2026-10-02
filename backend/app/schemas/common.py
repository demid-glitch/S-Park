from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.core.normalize import normalize_phone, normalize_plate

Phone = Annotated[str, AfterValidator(normalize_phone)]
Plate = Annotated[str, AfterValidator(normalize_plate)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
