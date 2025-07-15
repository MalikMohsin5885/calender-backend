import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Automatically creates PostgreSQL database, user, and assigns privileges"

    def handle(self, *args, **kwargs):
        try:
            conn = psycopg2.connect(
                dbname="postgres",  # Connect to default database first
                user="postgres",    # Default PostgreSQL user
                password="Mohsin",  # Change this if needed
                host="localhost",
                port="5432"
            )
            conn.autocommit = True
            cur = conn.cursor()

            # Get database credentials from settings
            db_name = settings.DATABASES['default']['NAME']
            db_user = settings.DATABASES['default']['USER']
            db_password = settings.DATABASES['default']['PASSWORD']

            # Create database if it doesn't exist
            cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {db_name}")
                self.stdout.write(self.style.SUCCESS(f"Database '{db_name}' created successfully"))

            # Create user if it doesn't exist
            cur.execute(f"SELECT 1 FROM pg_roles WHERE rolname = '{db_user}'")
            if not cur.fetchone():
                cur.execute(f"CREATE USER {db_user} WITH PASSWORD '{db_password}'")
                self.stdout.write(self.style.SUCCESS(f"User '{db_user}' created successfully"))

            # Assign ownership and privileges
            cur.execute(f"ALTER DATABASE {db_name} OWNER TO {db_user}")
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user}")

            # Connect to the new database to set schema permissions
            conn.close()
            conn = psycopg2.connect(
                dbname=db_name,
                user="postgres",  # Use superuser to make schema changes
                password="Mohsin",
                host="localhost",
                port="5432"
            )
            conn.autocommit = True
            cur = conn.cursor()

            # Grant permissions on schema public
            cur.execute(f"ALTER SCHEMA public OWNER TO {db_user}")
            cur.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {db_user}")
            cur.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user}")
            cur.execute(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user}")

            self.stdout.write(self.style.SUCCESS("PostgreSQL setup completed successfully"))

            cur.close()
            conn.close()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error setting up PostgreSQL: {e}"))
