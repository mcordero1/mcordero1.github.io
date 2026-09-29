from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

Text = Annotated[str, Field(min_length=1, max_length=3000)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Experience(Record):
    company: Text
    role: Text
    period: Text
    description: Text
    highlights: list[Text] = Field(max_length=20)


class Education(Record):
    title: Text
    institution: Text


class SkillGroup(Record):
    name: Text
    items: list[Text] = Field(min_length=1, max_length=30)


class Profile(Record):
    name: Text
    role: Text
    specialty: Text
    location: Text
    email: Text
    linkedin: HttpUrl
    introduction: Text
    about: list[Text] = Field(min_length=1, max_length=10)
    experience: list[Experience] = Field(min_length=1, max_length=40)
    education: list[Education] = Field(max_length=30)
    courses: list[Education] = Field(max_length=30)
    skills: list[SkillGroup] = Field(max_length=15)
    languages: list[Text] = Field(max_length=15)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value):
            raise ValueError("Ingresá un correo válido, sin parámetros ni saltos de línea.")
        return value

    @field_validator("linkedin")
    @classmethod
    def valid_linkedin(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https" or value.host not in {"linkedin.com", "www.linkedin.com"}:
            raise ValueError("Usá una URL HTTPS de LinkedIn.")
        return value
