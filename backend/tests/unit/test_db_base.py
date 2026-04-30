from app.db.base import Base


def test_base_uses_consistent_naming_convention():
    convention = Base.metadata.naming_convention
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["ix"] == "ix_%(table_name)s_%(column_0_name)s"
