import os
# Prefer PyMySQL (pure-Python) where available, then try mysqlclient (MySQLdb)
MySQLdb = None
try:
    import pymysql
    pymysql.install_as_MySQLdb()
    import MySQLdb
    MySQLdb = MySQLdb
except Exception:
    try:
        import MySQLdb
        MySQLdb = MySQLdb
    except Exception:
        MySQLdb = None
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Create MySQL database and user. Uses admin credentials from environment."

    def add_arguments(self, parser):
        parser.add_argument('--db-name', help='Database name to create (overrides settings)', required=False)
        parser.add_argument('--db-user', help='Database user to create (overrides settings)', required=False)
        parser.add_argument('--db-password', help='Password for the new DB user (overrides settings)', required=False)

    def handle(self, *args, **options):
        # Read admin (root) credentials from environment
        root_user = os.getenv('MYSQL_ROOT_USER', 'root')
        root_password = "Mohsin"
        host = os.getenv('MYSQL_HOST', 'localhost')
        port = int(os.getenv('MYSQL_PORT', '3306'))

        if not root_password:
            self.stdout.write(self.style.ERROR('MYSQL_ROOT_PASSWORD env var must be set for create_db to run.'))
            return

        if MySQLdb is None:
            self.stdout.write(self.style.ERROR('No MySQL driver available. Install mysqlclient or PyMySQL (pip install mysqlclient or pip install PyMySQL).'))
            return

        db_name = options.get('db_name') or settings.DATABASES['default'].get('NAME')
        db_user = options.get('db_user') or settings.DATABASES['default'].get('USER')
        db_password = options.get('db_password') or settings.DATABASES['default'].get('PASSWORD')

        if not all([db_name, db_user, db_password]):
            self.stdout.write(self.style.ERROR('Target DB name/user/password must be provided either via --db-name/--db-user/--db-password or in settings.DATABASES["default"].'))
            return

        try:
            conn = MySQLdb.connect(host=host, user=root_user, passwd=root_password, port=port)
            conn.autocommit(True)
            cur = conn.cursor()

            # Create database if not exists
            cur.execute("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" % db_name)
            self.stdout.write(self.style.SUCCESS(f"Database '{db_name}' ensured."))

            # Create user if not exists and grant privileges
            # MySQL 5.7+ supports CREATE USER IF NOT EXISTS
            try:
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s" % (
                    MySQLdb.escape_string(db_user).decode(),
                    "'%'",
                    MySQLdb.escape_string(db_password).decode()
                ))
            except Exception:
                # Fallback for older MySQL versions: attempt to create and ignore errors
                try:
                    cur.execute("CREATE USER %s@'%%' IDENTIFIED BY '%s'" % (db_user, db_password))
                except Exception:
                    pass

            cur.execute("GRANT ALL PRIVILEGES ON `%s`.* TO %s@'%%'" % (db_name, db_user))
            cur.execute("FLUSH PRIVILEGES")
            self.stdout.write(self.style.SUCCESS(f"User '{db_user}' granted privileges on '{db_name}'."))

            cur.close()
            conn.close()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error setting up MySQL: {e}"))
