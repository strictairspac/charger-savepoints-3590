from pydantic import BaseModel, Field, field_validator


class RevocationInput(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    meter: str = Field(min_length=1, max_length=24)
    invalid_from: int | str
    invalid_to: int | str
    note: str = Field(default="", max_length=500)

    @field_validator("code")
    @classmethod
    def check_code(cls, code):
        if code is None:
            return None
        text = code.strip().upper()
        if not text or len(text) > 32 or not all(ch.isalnum() or ch == "-" for ch in text):
            raise ValueError("撤销单编号须为 1–32 位大写字母、数字或连字符")
        return text


class RevocationEntry(BaseModel):
    id: int
    code: str
    meter: str
    invalid_from: int
    invalid_to: int
    note: str
    actor: str
    created_at: int
