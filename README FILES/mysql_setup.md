# MySQL 8.0 Setup for UON Ticketing Management System

This guide provides instructions to set up MySQL 8.0 as the database for the UON Ticketing Management System on your local machine.

## 1. Install MySQL 8.0

- Download and install MySQL Community Server 8.0 from the official website: https://dev.mysql.com/downloads/mysql/
- Follow the installation instructions for your operating system.
- During installation, set a root password and remember it.

## 2. Create Database and User

1. Open MySQL command line or MySQL Workbench.
2. Log in as root or an admin user.
3. Create a new database for the system:

```sql
CREATE DATABASE uon_ticketing_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

4. Create a new user and grant privileges:

```sql
CREATE USER 'uon_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON uon_ticketing_db.* TO 'uon_user'@'localhost';
FLUSH PRIVILEGES;
```

Replace `'your_password'` with a strong password.

## 3. Set Environment Variable

Set the `DATABASE_URL` environment variable to connect to your MySQL database. The format is:

```
mysql+mysqldb://uon_user:your_password@localhost/uon_ticketing_db
```

For example, on Linux/macOS:

```bash
export DATABASE_URL="mysql+mysqldb://uon_user:your_password@localhost/uon_ticketing_db"
```

On Windows (Command Prompt):

```cmd
set DATABASE_URL=mysql+mysqldb://uon_user:your_password@localhost/uon_ticketing_db
```

## 4. Install Dependencies

Make sure you have installed the MySQL driver dependency:

```bash
pip install mysqlclient
```

If you are using the default PyMySQL driver, install it explicitly:

```bash
pip install PyMySQL
```

Or if you use the pyproject.toml, run:

```bash
pip install -r requirements.txt
# or
pip install .
```

## 5. Run the Application

Start the application as usual. The system will connect to the MySQL database using the provided `DATABASE_URL`.

## Notes

- If you encounter issues with `mysqlclient` installation, ensure you have the necessary build tools and MySQL development headers installed.
- Alternatively, you can use `PyMySQL` as a pure Python MySQL driver by installing it and changing the connection string prefix to `mysql+pymysql://`.
- This project now supports both `mysqlclient` and `PyMySQL` drivers. The default connection string in `app.py` uses `PyMySQL` for easier installation.

This setup replaces the default PostgreSQL configuration with MySQL 8.0 for local development.
