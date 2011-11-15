from sqlalchemy import text
from sqlalchemy.sql.expression import _BindParamClause
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import schema
from alembic.ddl import base

class ImplMeta(type):
    def __init__(cls, classname, bases, dict_):
        newtype = type.__init__(cls, classname, bases, dict_)
        if '__dialect__' in dict_:
            _impls[dict_['__dialect__']] = cls
        return newtype

_impls = {}

class DefaultImpl(object):
    """Provide the entrypoint for major migration operations,
    including database-specific behavioral variances.
    
    While individual SQL/DDL constructs already provide
    for database-specific implementations, variances here
    allow for entirely different sequences of operations
    to take place for a particular migration, such as
    SQL Server's special 'IDENTITY INSERT' step for 
    bulk inserts.

    """
    __metaclass__ = ImplMeta
    __dialect__ = 'default'

    transactional_ddl = False

    def __init__(self, dialect, connection, as_sql, transactional_ddl, output_buffer):
        self.dialect = dialect
        self.connection = connection
        self.as_sql = as_sql
        self.output_buffer = output_buffer
        if transactional_ddl is not None:
            self.transactional_ddl = transactional_ddl

    @classmethod
    def get_by_dialect(cls, dialect):
        return _impls[dialect.name]

    def static_output(self, text):
        self.output_buffer.write(text + "\n\n")

    def _exec(self, construct, *args, **kw):
        if isinstance(construct, basestring):
            construct = text(construct)
        if self.as_sql:
            if args or kw:
                # TODO: coverage
                raise Exception("Execution arguments not allowed with as_sql")
            self.static_output(unicode(
                    construct.compile(dialect=self.dialect)
                    ).replace("\t", "    ").strip() + ";")
        else:
            self.connection.execute(construct, *args, **kw)

    def execute(self, sql):
        self._exec(sql)

    def alter_column(self, table_name, column_name, 
                        nullable=None,
                        server_default=False,
                        name=None,
                        type_=None,
                        schema=None,
    ):

        if nullable is not None:
            self._exec(base.ColumnNullable(table_name, column_name, 
                                nullable, schema=schema))
        if server_default is not False:
            self._exec(base.ColumnDefault(
                                table_name, column_name, server_default,
                                schema=schema
                            ))
        if type_ is not None:
            self._exec(base.ColumnType(
                                table_name, column_name, type_, schema=schema
                            ))

    def add_column(self, table_name, column):
        self._exec(base.AddColumn(table_name, column))

    def drop_column(self, table_name, column):
        self._exec(base.DropColumn(table_name, column))

    def add_constraint(self, const):
        self._exec(schema.AddConstraint(const))

    def create_table(self, table):
        self._exec(schema.CreateTable(table))
        for index in table.indexes:
            self._exec(schema.CreateIndex(index))

    def drop_table(self, table):
        self._exec(schema.DropTable(table))

    def bulk_insert(self, table, rows):
        if self.as_sql:
            for row in rows:
                self._exec(table.insert().values(**dict(
                    (k, _literal_bindparam(k, v, type_=table.c[k].type))
                    for k, v in row.items()
                )))
        else:
            self._exec(table.insert(), *rows)


class _literal_bindparam(_BindParamClause):
    pass

@compiles(_literal_bindparam)
def _render_literal_bindparam(element, compiler, **kw):
    return compiler.render_literal_bindparam(element, **kw)
