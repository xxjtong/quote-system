#!/bin/bash
# Quote system SQLite backup — daily cron (using Python since sqlite3 CLI not available)
DB="/opt/quote-system/quote.db"
BACKUP_DIR="/opt/quote-system/backups"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/quote_${TIMESTAMP}.db"

python3 -c "
import sqlite3, shutil
src = '$DB'
dst = '${BACKUP_FILE}'
conn = sqlite3.connect(src)
bak = sqlite3.connect(dst)
conn.backup(bak)
bak.close()
conn.close()
" 2>/dev/null

if [ $? -eq 0 ]; then
    gzip "${BACKUP_FILE}"
    find "$BACKUP_DIR" -name "quote_*.db.gz" -mtime +$KEEP_DAYS -delete
    echo "$(date -Iseconds) Backup OK: ${BACKUP_FILE}.gz"
else
    echo "$(date -Iseconds) Backup FAILED" >&2
    rm -f "${BACKUP_FILE}"
fi
