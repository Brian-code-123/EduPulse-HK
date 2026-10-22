import re
from pathlib import Path

SCHEMA = (Path(__file__).resolve().parent.parent / "sql" / "supabase_schema.sql").read_text()


def test_every_table_in_the_schema_enables_row_level_security():
    tables = re.findall(r"create table if not exists (\w+)", SCHEMA)
    assert tables, "no tables found in sql/supabase_schema.sql"
    unprotected = [t for t in tables if not re.search(rf"alter table {t} enable row level security", SCHEMA)]
    assert not unprotected, f"RLS missing for: {unprotected}"


def test_vector_extension_is_not_installed_in_the_public_schema():
    assert re.search(r"create extension if not exists vector with schema extensions", SCHEMA)


def test_match_function_pins_its_search_path():
    function = re.search(r"create or replace function match_document_chunks.*?\$\$;", SCHEMA, re.S).group(0)
    assert "set search_path" in function
