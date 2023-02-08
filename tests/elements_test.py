from pyridy.file import RDYFile


def test_get_integrity_report():
    rdy_file = RDYFile(path="../docs/source/files/sqlite/sample3.sqlite")
    report = rdy_file.get_integrity_report()
    assert True
