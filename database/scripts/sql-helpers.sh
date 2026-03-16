#!/usr/bin/env bash

# Database connection helper script
# Usage: bash sql-helpers.sh [command]

DB_USER=${DB_USER:-myuser}
DB_PASSWORD=${DB_PASSWORD:-mypassword}
DB_NAME=${DB_NAME:-mydb}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}

USER_CONN="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

case "${1:-help}" in
  "tables")
    echo "📋 All tables in database:"
    psql "$USER_CONN" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;" | cat
    ;;
  "users")
    echo "👥 Users in database:"
    psql "$USER_CONN" -c "SELECT id, name, email FROM users LIMIT 10;" | cat
    ;;
  "profiles")
    echo "👤 User profiles:"
    psql "$USER_CONN" -c "SELECT id, first_name, last_name, alias, role FROM profiles LIMIT 10;" | cat
    ;;
  "scenarios")
    echo "🎭 Available scenarios:"
    psql "$USER_CONN" -c "SELECT id, name, description FROM scenarios LIMIT 5;" | cat
    ;;
  "simulations")
    echo "🎮 Simulations:"
    psql "$USER_CONN" -c "SELECT id, title, active FROM simulations LIMIT 5;" | cat
    ;;
  "counts")
    echo "📊 Table row counts:"
    psql "$USER_CONN" -c "
      SELECT 
        'users' as table_name, COUNT(*) as row_count FROM users
      UNION ALL SELECT 'profiles', COUNT(*) FROM profiles
      UNION ALL SELECT 'scenarios', COUNT(*) FROM scenarios
      UNION ALL SELECT 'simulations', COUNT(*) FROM simulations
      UNION ALL SELECT 'agents', COUNT(*) FROM agents
      ORDER BY table_name;
    " | cat
    ;;
  "schema")
    echo "🏗️  Database schema for table: ${2:-users}"
    psql "$USER_CONN" -c "\\d ${2:-users}" | cat
    ;;
  "connect")
    echo "🔌 Opening interactive connection..."
    echo "💡 Remember: End each SQL command with semicolon (;)"
    psql "$USER_CONN"
    ;;
  "help"|*)
    echo "🛠️  Database Helper Commands:"
    echo ""
    echo "  bash sql-helpers.sh tables     - List all tables"
    echo "  bash sql-helpers.sh users      - Show users"
    echo "  bash sql-helpers.sh profiles   - Show user profiles"
    echo "  bash sql-helpers.sh scenarios  - Show scenarios"
    echo "  bash sql-helpers.sh simulations- Show simulations"
    echo "  bash sql-helpers.sh counts     - Show row counts for all tables"
    echo "  bash sql-helpers.sh schema [table] - Show table structure"
    echo "  bash sql-helpers.sh connect    - Open interactive connection"
    echo ""
    echo "Examples:"
    echo "  bash sql-helpers.sh schema users"
    echo "  bash sql-helpers.sh schema scenarios"
    ;;
esac 