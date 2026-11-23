# Shared setup for the scripts in this folder (sourced, not run):
#   - loads scripts/.env.backup (git-ignored) so connection strings never
#     have to be typed or exported;
#   - puts the Postgres client tools (pg_dump, pg_restore, psql) on PATH from
#     wherever they're installed — a private conda folder, or Homebrew's libpq —
#     so nobody has to edit their shell profile.
if [ -f scripts/.env.backup ]; then
  set -a; . scripts/.env.backup; set +a
fi
for _d in "$HOME/.local/share/pgclient/bin" /opt/homebrew/opt/libpq/bin /usr/local/opt/libpq/bin; do
  [ -d "$_d" ] && PATH="$_d:$PATH"
done
export PATH
