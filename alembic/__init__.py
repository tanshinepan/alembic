from os import path

__version__ = '0.4.0'

package_dir = path.abspath(path.dirname(__file__))


from alembic import op
from alembic import context

