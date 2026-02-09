from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False


class Table(BaseModel):
    name: str
    columns: List[Column] = Field(default_factory=list)

    def column_map(self) -> Dict[str, Column]:
        return {c.name: c for c in self.columns}

    def primary_keys(self) -> List[str]:
        return [c.name for c in self.columns if c.primary_key]


class SchemaSnapshot(BaseModel):
    version: int = 1
    tables: List[Table] = Field(default_factory=list)

    def table_map(self) -> Dict[str, Table]:
        return {t.name: t for t in self.tables}

    def get_table(self, name: str) -> Optional[Table]:
        return self.table_map().get(name)
