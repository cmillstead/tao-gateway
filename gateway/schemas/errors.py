from pydantic import BaseModel


class ErrorDetail(BaseModel):
    type: str
    message: str
    code: int


class ErrorResponse(BaseModel):
    error: ErrorDetail
