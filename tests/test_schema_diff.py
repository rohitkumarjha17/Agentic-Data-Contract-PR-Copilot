from prcopilot.domain.schema import SchemaSnapshot
from prcopilot.domain.diff import diff_schemas, ChangeType, Severity


def test_detects_breaking_column_removed():
    base = SchemaSnapshot.model_validate({
        "version": 1,
        "tables": [{"name": "t", "columns": [{"name": "a", "type": "int", "nullable": False}]}],
    })
    head = SchemaSnapshot.model_validate({
        "version": 2,
        "tables": [{"name": "t", "columns": []}],
    })
    cs = diff_schemas(base, head)
    assert any(c.change_type == ChangeType.column_removed and c.severity == Severity.breaking for c in cs.changes)


def test_detects_column_rename_instead_of_remove_add():
    base = SchemaSnapshot.model_validate({
        "version": 1,
        "tables": [{"name": "orders", "columns": [
            {"name": "order_total", "type": "float", "nullable": False},
        ]}],
    })
    head = SchemaSnapshot.model_validate({
        "version": 2,
        "tables": [{"name": "orders", "columns": [
            {"name": "total_amount", "type": "float", "nullable": False},
        ]}],
    })

    cs = diff_schemas(base, head)

    assert any(c.change_type == ChangeType.column_renamed and c.table == "orders" and c.column == "total_amount"
               and c.details.get("base_column") == "order_total" for c in cs.changes)

    assert not any(c.change_type == ChangeType.column_removed and c.column == "order_total" for c in cs.changes)
    assert not any(c.change_type == ChangeType.column_added and c.column == "total_amount" for c in cs.changes)
