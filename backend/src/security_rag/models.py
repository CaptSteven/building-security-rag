from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, model_validator

Category = Literal["视频监控", "门禁", "对讲", "入侵报警"]


class Device(BaseModel):
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=150)
    category: Category
    protocols: list[str] = Field(default_factory=list, max_length=100)
    specs: dict[str, str | int | float | bool] = Field(default_factory=dict)
    # 参数仅表示此份来源的声明，不合并不同版本来源的事实。


class IngestRequest(BaseModel):
    source_key: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=300)
    source_url: HttpUrl | None = None
    version: str = Field(default="未标注", max_length=100)
    published_on: date | None = None
    device: Device
    text: str = Field(min_length=10, max_length=500_000)
    page: int | None = Field(default=None, ge=1)
    review_status: Literal["pending", "verified", "demo"] = "pending"
    # verified 是维护者的人工确认；原型不提供自动事实审核。

    @model_validator(mode="after")
    def meaningful_text(self):
        if len(self.text.strip()) < 10:
            raise ValueError("正文有效文本至少需要 10 个字符")
        return self


class Filters(BaseModel):
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    category: Category | None = None
    protocol: str | None = Field(default=None, max_length=100)
    spec_equals: dict[str, str | int | float | bool] = Field(default_factory=dict)
    include_unverified: bool = False


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    filters: Filters = Field(default_factory=Filters)
    mode: Literal["hybrid", "relational", "vector"] = "hybrid"
    top_k: int = Field(default=6, ge=1, le=20)
    generate: bool = True

    @model_validator(mode="after")
    def question_not_blank(self):
        if not self.question.strip():
            raise ValueError("问题不能为空")
        return self


class Compatibility(BaseModel):
    source_device_id: int = Field(ge=1)
    target_device_id: int = Field(ge=1)
    document_id: int = Field(ge=1)
    verdict: Literal["compatible", "incompatible", "conditional"]
    conditions: str = Field(min_length=1, max_length=2000)
    evidence_quote: str = Field(min_length=10, max_length=5000)


    @model_validator(mode="after")
    def different_devices(self):
        if self.source_device_id == self.target_device_id:
            raise ValueError("兼容关系需要两个不同设备")
        return self
