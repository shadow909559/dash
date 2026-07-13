from dash_memory.types import MemoryRecord


def test_memory_record() -> None:
    record = MemoryRecord(id="1", content="hello")
    assert record.content == "hello"
