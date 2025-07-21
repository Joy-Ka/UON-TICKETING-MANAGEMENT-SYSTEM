
# PostgreSQL Setup for Replit

This guide explains how to set up PostgreSQL database on Replit for the UON Ticketing Management System.

## Setting Up PostgreSQL on Replit

1. **Open Database Tab**: In your Replit workspace, open a new tab and type "Database"

2. **Create PostgreSQL Database**: Click "create a database" and select PostgreSQL

3. **Environment Variables**: Replit will automatically set the `DATABASE_URL` environment variable for you

4. **Automatic Detection**: The application will automatically detect the PostgreSQL connection and use the appropriate configuration

## Database Features

- **Automatic Connection Pooling**: Enhanced performance with connection pooling
- **Production Ready**: Fully managed PostgreSQL service
- **Environment Detection**: Automatically switches between local MySQL and Replit PostgreSQL
- **Backup & Recovery**: Built-in backup features provided by Replit

## Local vs Replit Configuration

### Local Development (MySQL)
```
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:Jace102020.@localhost:3307/uon_ticketing_db"
```

### Replit Production (PostgreSQL)
```
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')  # Auto-set by Replit
```

## Connection Pooling

The application automatically configures connection pooling for PostgreSQL:
- Pool size: 10 connections
- Max overflow: 20 connections  
- Connection recycling: 300 seconds
- Pre-ping: Enabled for connection health checks

## Migration Notes

When moving from SQLite/MySQL to PostgreSQL, the application will:
1. Automatically create all required tables
2. Initialize default departments and admin user
3. Preserve all existing functionality

## Troubleshooting

- If you see connection errors, ensure the DATABASE_URL environment variable is set
- The application falls back to SQLite if PostgreSQL is not available
- Check the console output for database connection status
