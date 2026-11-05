#!/usr/bin/env bash
# Start a local MariaDB for Prody and make sure the prody_dev database + app user exist.
# Usage: scripts/start_mysql.sh   then:  source scripts/mysql_env.sh && python app.py
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ENVF="$HERE/scripts/mysql_env.sh"
if [ ! -f "$ENVF" ]; then
  PW="$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)"
  printf 'export PRODY_DB=mysql\nexport PRODY_DB_HOST=127.0.0.1\nexport PRODY_DB_USER=prody\nexport PRODY_DB_PASSWORD=%s\nexport PRODY_DB_NAME=prody_dev\n' "$PW" > "$ENVF"
  chmod 600 "$ENVF"
fi
source "$ENVF"
if [ ! -x /usr/sbin/mariadbd ] || ! id mysql >/dev/null 2>&1; then
  echo "MariaDB not installed (no /usr/sbin/mariadbd or mysql user); installing..."
  sudo apt-get update -q && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q mariadb-server mariadb-client
fi
sudo mkdir -p /run/mysqld && sudo chown mysql:mysql /run/mysqld
if ! sudo mariadb -e 'SELECT 1' >/dev/null 2>&1; then
  sudo -u mysql nohup /usr/sbin/mariadbd --user=mysql >/tmp/mariadbd.log 2>&1 &
  for i in $(seq 1 30); do sudo mariadb -e 'SELECT 1' >/dev/null 2>&1 && break; sleep 1; done
fi
sudo mariadb <<SQL
CREATE DATABASE IF NOT EXISTS prody_dev CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'prody'@'localhost' IDENTIFIED BY '$PRODY_DB_PASSWORD';
CREATE USER IF NOT EXISTS 'prody'@'127.0.0.1' IDENTIFIED BY '$PRODY_DB_PASSWORD';
GRANT ALL ON prody_dev.* TO 'prody'@'localhost';
GRANT ALL ON prody_dev.* TO 'prody'@'127.0.0.1';
CREATE DATABASE IF NOT EXISTS prody_migtest CHARACTER SET utf8mb4;
GRANT ALL ON prody_migtest.* TO 'prody'@'localhost';
GRANT ALL ON prody_migtest.* TO 'prody'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
echo "MariaDB up; prody_dev ready. Load env with: source $ENVF"
