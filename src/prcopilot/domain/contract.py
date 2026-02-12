from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CheckSpec(BaseModel):
    type: str
    value: Optional[float] = None
    pattern: Optional[str] = None
    allowed: Optional[List[str]] = None


class ColumnRule(BaseModel):
    column: str
    checks: List[CheckSpec] = Field(default_factory=list)
class ContractSpec(BaseModel):
    table: str
    rules: List[ColumnRule] = Field(default_factory=list)
class CheckResult(BaseModel):
    column: str
    check_type: str
    passed: bool
    details: Dict[str, Any] = Field(default_factory=dict)
class ContractReport(BaseModel):
    table: str
    total_checks: int
    failed_checks: int
    results: List[CheckResult] = Field(default_factory=list)
