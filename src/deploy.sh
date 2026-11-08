#!/usr/bin/env bash
#
# deploy.sh - wgrywa skin.netflixlike na TV (LG webOS) i restartuje Kodi.
#
# Zasady:
#  - przed jakimkolwiek zapisem na TV tworzony jest świeży backup,
#  - na TV nic nie jest usuwane: pliki są tylko dopisywane/nadpisywane,
#  - stare backupy nie są kasowane automatycznie.
#
# Użycie:
#   ./deploy.sh                 # backup + skin + zależności + restart
#   ./deploy.sh --activate      # dodatkowo ustawia skin jako aktywny
#   ./deploy.sh --no-deps       # tylko skin (zależności już zainstalowane)
#   ./deploy.sh --no-restart    # tylko kopiowanie, bez restartu Kodi
#   ./deploy.sh --dry-run       # pokaż plan, nic nie zapisuj na TV
#
# Zmienne środowiskowe:
#   TV=tv                       # alias SSH (domyślnie: tv)
#   TV_IP=192.168.18.68         # adres do JSON-RPC (domyślnie z ssh -G)
#   KODI_HOME=...               # katalog .kodi na TV
#   BACKUP_ROOT=...             # katalog backupów na TV
#   NO_DEPS=1 / NO_RESTART=1 / ACTIVATE=1 / FORCE_DEPS=1
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SKIN_ID="skin.netflixlike"
SKIN_VERSION="1.0.0"
SKIN_SRC="$SCRIPT_DIR/$SKIN_ID"
DEPS_FILE="$SCRIPT_DIR/deploy/deps.tsv"
CACHE_DIR="$SCRIPT_DIR/deploy/.cache"
STAGE_DIR="$CACHE_DIR/staged"

TV="${TV:-tv}"
APP_DIR="/media/developer/apps/usr/palm/applications/org.xbmc.kodi"
KODI_HOME="${KODI_HOME:-$APP_DIR/.kodi}"
ADDONS_DIR="$KODI_HOME/addons"
BACKUP_ROOT="${BACKUP_ROOT:-/media/developer/backups/kodi}"
REMOTE_BIN_RSYNC="/media/developer/apps/usr/palm/services/org.webosbrew.hbchannel.service/bin/rsync"

NO_DEPS="${NO_DEPS:-0}"
NO_RESTART="${NO_RESTART:-0}"
ACTIVATE="${ACTIVATE:-0}"
FORCE_DEPS="${FORCE_DEPS:-0}"
DRY_RUN=0

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR)
SSH_OPTS_N=(-o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR -n)
JSONRPC_URL=""

# ---------------------------------------------------------------------------
# pomocnicze
# ---------------------------------------------------------------------------
log()  { printf '%s\n' "$*"; }
warn() { printf 'UWAGA: %s\n' "$*" >&2; }
die()  { printf 'BŁĄD: %s\n' "$*" >&2; exit 1; }

run_tv() {
    ssh "${SSH_OPTS[@]}" "$TV" "$@"
}

run_tv_n() {
    ssh "${SSH_OPTS_N[@]}" "$TV" "$@"
}

ssh_tty() {
    ssh "${SSH_OPTS[@]}" -tt "$TV" "$@"
}

usage() {
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --activate)   ACTIVATE=1 ;;
            --no-deps)    NO_DEPS=1 ;;
            --no-restart) NO_RESTART=1 ;;
            --force-deps) FORCE_DEPS=1 ;;
            --dry-run)    DRY_RUN=1 ;;
            -h|--help)    usage; exit 0 ;;
            *) die "nieznana opcja: $1 (użyj --help)" ;;
        esac
        shift
    done

    if [[ "$ACTIVATE" == "1" && "$NO_RESTART" == "1" ]]; then
        die "--activate wymaga restartu Kodi; usuń --no-restart"
    fi
}

remote_has_dir() {
    run_tv "test -d '$1'"
}

remote_has_file() {
    run_tv "test -f '$1'"
}

# Wypisuje wersję add-onu z <addons>/<id>/addon.xml (pusty string, gdy brak).
# Używa sed z zakresem lini (od <addon do >) bo atrybuty mogą być na wielu liniach.
remote_version() {
    local id="$1"
    run_tv_n "sed -n '/<addon /,/>/p' '$ADDONS_DIR/$id/addon.xml' | sed -n 's/.*version=\"\\([^\"]*\\)\".*/\\1/p' | head -1" 2>/dev/null \
        | head -n1 || true
}

# Wypisuje id add-onu z pliku addon.xml (lokalnie).
# Use Python for robust XML parsing (handles multi-line attributes)
local_addon_id() {
    python3 -c "import xml.etree.ElementTree as ET, sys; print(ET.parse(sys.argv[1]).getroot().get('id'))" "$1" 2>/dev/null || true
}

local_addon_version() {
    python3 -c "import xml.etree.ElementTree as ET, sys; print(ET.parse(sys.argv[1]).getroot().get('version'))" "$1" 2>/dev/null || true
}

preflight() {
    [[ -d "$SKIN_SRC" ]] || die "brak katalogu skina: $SKIN_SRC"
    [[ -f "$SKIN_SRC/addon.xml" ]] || die "brak $SKIN_SRC/addon.xml"
    [[ "$(local_addon_id "$SKIN_SRC/addon.xml")" == "$SKIN_ID" ]] \
        || die "addon.xml nie ma id=$SKIN_ID"
    [[ "$(local_addon_version "$SKIN_SRC/addon.xml")" == "$SKIN_VERSION" ]] \
        || die "addon.xml nie ma wersji $SKIN_VERSION"

    if [[ "$NO_DEPS" != "1" ]]; then
        [[ -f "$DEPS_FILE" ]] || die "brak listy zależności: $DEPS_FILE"
        command -v curl     >/dev/null || die "brak curl"
        command -v unzip    >/dev/null || die "brak unzip"
        command -v sha256sum>/dev/null || die "brak sha256sum"
        command -v tar      >/dev/null || die "brak tar"
    fi

    run_tv "true" || die "brak połączenia SSH z '$TV'"
    remote_has_dir "$KODI_HOME" || die "brak $KODI_HOME na TV"
    remote_has_dir "$ADDONS_DIR" || die "brak $ADDONS_DIR na TV"

    TV_IP="${TV_IP:-$(ssh -G "$TV" 2>/dev/null | awk '$1=="hostname"{print $2; exit}')}"
    [[ -n "$TV_IP" ]] || die "nie potrafię ustalić IP TV; ustaw TV_IP=..."
    JSONRPC_URL="http://$TV_IP:8089/jsonrpc"
}

# ---------------------------------------------------------------------------
# plan zależności
# ---------------------------------------------------------------------------
plan_id=()
plan_ver=()
plan_url=()
plan_sha=()

build_plan() {
    if [[ "$NO_DEPS" == "1" ]]; then
        log "Zależności: pomijam (--no-deps)."
        return
    fi

    log "Sprawdzam zależności na TV:"
    local id ver url sha rv
    while IFS=$'\t' read -r id ver url sha; do
        [[ -z "${id:-}" || "$id" == \#* ]] && continue
        [[ -n "${url:-}" && -n "${sha:-}" ]] || die "błędny wiersz w $DEPS_FILE: $id"

        rv="$(remote_version "$id" | tr -d '\r')"
        if [[ "$rv" == "$ver" && "$FORCE_DEPS" != "1" ]]; then
            log "  = $id $ver (już jest)"
        else
            if [[ -n "$rv" ]]; then
                log "  > $id $rv -> $ver"
            else
                log "  + $id $ver (brak)"
            fi
            plan_id+=("$id")
            plan_ver+=("$ver")
            plan_url+=("$url")
            plan_sha+=("$sha")
        fi
    done < "$DEPS_FILE"

    if [[ ${#plan_id[@]} -eq 0 ]]; then
        log "Zależności: wszystkie aktualne."
    else
        log "Do instalacji: ${#plan_id[@]}."
    fi
}

# ---------------------------------------------------------------------------
# pobieranie / rozpakowywanie zależności (lokalnie)
# ---------------------------------------------------------------------------
download_zip() {
    local url="$1" sha="$2" zip="$3"
    local actual
    if [[ -f "$zip" ]]; then
        actual=$(sha256sum "$zip" | awk '{print $1}')
        if [[ "$actual" == "$sha" ]]; then
            log "  cache: $(basename "$zip")"
            return
        fi
        warn "zły checksum cache, pobieram ponownie: $(basename "$zip")"
    fi
    log "  pobieram: $(basename "$zip")"
    curl -fL --retry 3 --connect-timeout 15 --max-time 1800 \
        -o "$zip.part" "$url"
    actual=$(sha256sum "$zip.part" | awk '{print $1}')
    [[ "$actual" == "$sha" ]] || die "checksum nie zgadza się: $zip"
    mv -- "$zip.part" "$zip"
}

stage_addon() {
    local id="$1" ver="$2" zip="$3"
    local dest="$STAGE_DIR/$id-$ver"
    if [[ -f "$dest/addon.xml" ]] \
        && [[ "$(local_addon_id "$dest/addon.xml")" == "$id" ]] \
        && [[ "$(local_addon_version "$dest/addon.xml")" == "$ver" ]]; then
        printf '%s\n' "$dest"
        return
    fi

    local tmp="$STAGE_DIR/.tmp-$id-$ver"
    rm -rf -- "$tmp" "$dest"
    mkdir -p -- "$tmp"
    unzip -q -o "$zip" -d "$tmp"
    local ax
    ax=$(find "$tmp" -maxdepth 2 -type f -name addon.xml -print -quit)
    [[ -n "$ax" ]] || die "brak addon.xml w $zip"
    local root
    root=$(dirname "$ax")
    local sid sver
    sid=$(local_addon_id "$root/addon.xml")
    sver=$(local_addon_version "$root/addon.xml")
    [[ "$sid" == "$id" ]]  || die "zip $zip ma id=$sid, oczekiwano $id"
    [[ "$sver" == "$ver" ]] || die "zip $zip ma wersję $sver, oczekiwano $ver"
    mv -- "$root" "$dest"
    rm -rf -- "$tmp"
    printf '%s\n' "$dest"
}

prepare_deps() {
    [[ ${#plan_id[@]} -gt 0 ]] || return 0
    log "Przygotowuję zależności (lokalnie):"
    mkdir -p -- "$CACHE_DIR" "$STAGE_DIR"
    local i zip stage
    for ((i=0; i<${#plan_id[@]}; i++)); do
        zip="$CACHE_DIR/$(basename "${plan_url[$i]}")"
        download_zip "${plan_url[$i]}" "${plan_sha[$i]}" "$zip"
        stage=$(stage_addon "${plan_id[$i]}" "${plan_ver[$i]}" "$zip")
        log "  gotowe: ${plan_id[$i]} ${plan_ver[$i]}"
    done
}

# ---------------------------------------------------------------------------
# miejsce na dysku TV
# ---------------------------------------------------------------------------
staged_kb() {
    local id="$1" ver="$2"
    du -sk "$STAGE_DIR/$id-$ver" | awk '{print $1}'
}

check_space() {
    local skin_kb deps_kb free_kb need_kb i
    skin_kb=$(du -sk "$SKIN_SRC" | awk '{print $1}')
    deps_kb=0
    for ((i=0; i<${#plan_id[@]}; i++)); do
        deps_kb=$((deps_kb + $(staged_kb "${plan_id[$i]}" "${plan_ver[$i]}")))
    done
    free_kb=$(run_tv "df -k '$KODI_HOME'" | awk 'NR==2{print $4}')
    # 150 MiB marginesu na backup (kompresja) i inne pliki Kodi
    need_kb=$((skin_kb + deps_kb + 150000))
    log "Miejsce na TV: wolne $((free_kb/1024)) MiB, potrzeba ok. $((need_kb/1024)) MiB."
    [[ "$free_kb" -ge "$need_kb" ]] \
        || die "za mało miejsca na TV (wolne $((free_kb/1024)) MiB, potrzeba $((need_kb/1024)) MiB)"
}

# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------
do_backup() {
    local ts="$1" bdir="$BACKUP_ROOT/$ts" i id
    log "Backup na TV: $bdir"
    run_tv "mkdir -p '$bdir'"

    if remote_has_dir "$ADDONS_DIR/$SKIN_ID"; then
        run_tv "tar -czf '$bdir/$SKIN_ID.tar.gz' -C '$ADDONS_DIR' '$SKIN_ID'"
        log "  $SKIN_ID.tar.gz"
    fi

    if remote_has_dir "$KODI_HOME/userdata/addon_data/$SKIN_ID"; then
        run_tv "tar -czf '$bdir/addon_data-$SKIN_ID.tar.gz' -C '$KODI_HOME/userdata/addon_data' '$SKIN_ID'"
        log "  addon_data-$SKIN_ID.tar.gz"
    fi

    if remote_has_file "$KODI_HOME/userdata/guisettings.xml"; then
        run_tv "cp -p '$KODI_HOME/userdata/guisettings.xml' '$bdir/guisettings.xml'"
        log "  guisettings.xml"
    fi

    # baza add-onów Kodi (mała, przydatna przy odtwarzaniu)
    run_tv "cp -p '$KODI_HOME'/userdata/Database/Addons*.db '$bdir/' 2>/dev/null || true"

    # katalogi danych add-onów, które będą nadpisane
    for ((i=0; i<${#plan_id[@]}; i++)); do
        id="${plan_id[$i]}"
        if remote_has_dir "$ADDONS_DIR/$id"; then
            run_tv "tar -czf '$bdir/$id.tar.gz' -C '$ADDONS_DIR' '$id'"
            log "  $id.tar.gz"
        fi
        if remote_has_dir "$KODI_HOME/userdata/addon_data/$id"; then
            run_tv "tar -czf '$bdir/addon_data-$id.tar.gz' -C '$KODI_HOME/userdata/addon_data' '$id'"
            log "  addon_data-$id.tar.gz"
        fi
    done

    local manifest
    manifest="timestamp=$ts
skin=$SKIN_ID
skin_version=$SKIN_VERSION
kodi_home=$KODI_HOME
"
    for ((i=0; i<${#plan_id[@]}; i++)); do
        manifest+="dep=${plan_id[$i]} ${plan_ver[$i]}"$'\n'
    done
    printf '%s' "$manifest" | run_tv "cat > '$bdir/manifest.txt'"
    log "  manifest.txt"
    BACKUP_DIR="$bdir"
}

# ---------------------------------------------------------------------------
# kopiowanie na TV (tar | ssh, bez kasowania plików po drugiej stronie)
# ---------------------------------------------------------------------------
# copy_tree src dst [writable]
# writable: "yes" -> chown to Kodi user + chmod 777 (for skin that needs write access)
#           "no"  -> chmod a+rX only (read-only for addons that don't write)
copy_tree() {
    local src="$1" dst="$2" writable="${3:-no}"
    tar -C "$src" -czf - . \
        | run_tv "mkdir -p '$dst' && tar -C '$dst' -xzf -"
    if [[ "$writable" == "yes" ]]; then
        # Get Kodi UID:GID from $KODI_HOME
        local uid_gid
        uid_gid=$(run_tv "stat -c '%u:%g' '$KODI_HOME'")
        run_tv "chown -R '$uid_gid' '$dst' && chmod -R a+rwX '$dst'"
    else
        run_tv "chmod -R a+rX '$dst'"
    fi
}

copy_skin() {
    log "Kopiuję $SKIN_ID na TV..."
    
    copy_tree "$SKIN_SRC" "$ADDONS_DIR/$SKIN_ID" "yes"
    
    # Ustaw skinvariables.skinuser na "default" w settings.xml skina (w userdata/addon_data)
    local skin_settings="$KODI_HOME/userdata/addon_data/$SKIN_ID/settings.xml"
    run_tv "sed -i 's|<setting id=\"skinvariables.skinuser\" type=\"string\"></setting>|<setting id=\"skinvariables.skinuser\" type=\"string\">default</setting>|' "$skin_settings""
    # Ustaw skinvariables.skinuser na "default" w settings.xml skina (w userdata/addon_data)
    local skin_settings="$KODI_HOME/userdata/addon_data/$SKIN_ID/settings.xml"
    run_tv "sed -i 's|<setting id=\"skinvariables.skinuser\" type=\"string\"></setting>|<setting id=\"skinvariables.skinuser\" type=\"string\">default</setting>|' "$skin_settings""
    
    local rid rver
    rid=$(run_tv "cat '$ADDONS_DIR/$SKIN_ID/addon.xml'" 2>/dev/null \
        | sed -n 's/.*<addon[^>]*id=\"\([^\"]*\)\".*/\1/p' | head -n1 || true)
    rver=$(remote_version "$SKIN_ID" | tr -d '\r')
    [[ "$rid" == "$SKIN_ID" ]] || die "na TV addon.xml ma id=$rid"
    [[ "$rver" == "$SKIN_VERSION" ]] || die "na TV addon.xml ma wersję $rver"
    log "  na TV: $SKIN_ID $rver"
}

install_deps() {
    [[ ${#plan_id[@]} -gt 0 ]] || return 0
    local i id ver stage
    log "Instaluję zależności na TV:"
    for ((i=0; i<${#plan_id[@]}; i++)); do
        id="${plan_id[$i]}"
        ver="${plan_ver[$i]}"
        stage="$STAGE_DIR/$id-$ver"
        copy_tree "$stage" "$ADDONS_DIR/$id" "no"
        local rv
        rv=$(remote_version "$id" | tr -d '\r')
        [[ "$rv" == "$ver" ]] || die "na TV $id ma wersję '$rv', oczekiwano $ver"
        log "  + $id $ver"
    done
}

# ---------------------------------------------------------------------------
# JSON-RPC / restart Kodi
# ---------------------------------------------------------------------------
rpc() {
    local method="$1" params="$2"
    curl -sS --max-time 15 -H 'Content-Type: application/json' \
        --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$method\",\"params\":$params}" \
        "$JSONRPC_URL"
}

kodi_pids() {
    run_tv "pgrep -f '[k]odi-webos' || true"
}

kodi_running() {
    [[ -n "$(kodi_pids | tr -d '[:space:]')" ]]
}

wait_rpc() {
    local i out
    log "Czekam na JSON-RPC Kodi ($JSONRPC_URL)..."
    for i in $(seq 1 180); do
        out=$(rpc JSONRPC.Ping '{}' 2>/dev/null || true)
        if [[ "$out" == *'"pong"'* ]]; then
            log "  JSON-RPC gotowe."
            return 0
        fi
        if [[ $((i % 15)) -eq 0 ]]; then
            log "  ... nadal czekam ($i s)"
        fi
        sleep 1
    done
    return 1
}

restart_kodi() {
    local i
    if kodi_running; then
        log "Zatrzymuję Kodi..."
        rpc Application.Quit '{}' >/dev/null 2>&1 || true
        for i in $(seq 1 30); do
            if ! kodi_running; then break; fi
            sleep 0.5
        done
        if kodi_running; then
            warn "Kodi nie wyszło przez JSON-RPC; wysyłam SIGTERM."
            run_tv "pkill -TERM -f '[k]odi-webos' || true"
            for i in $(seq 1 30); do
                if ! kodi_running; then break; fi
                sleep 0.5
            done
        fi
        if kodi_running; then
            warn "Kodi nadal działa; wysyłam SIGKILL."
            run_tv "pkill -KILL -f '[k]odi-webos' || true"
            sleep 2
            if kodi_running; then
                die "nie udało się zatrzymać Kodi"
            fi
        fi
    fi

    log "Uruchamiam Kodi..."
    ssh_tty "luna-send -n 1 -f luna://com.webos.applicationManager/launch '{\"id\":\"org.xbmc.kodi\"}'" \
        </dev/null >/dev/null 2>&1 || true

    for i in $(seq 1 60); do
        if kodi_running; then break; fi
        sleep 0.5
    done
    if ! kodi_running; then
        die "Kodi się nie uruchomiło (luna-send). Otwórz Kodi ręcznie i użyj --no-restart."
    fi
    wait_rpc || die "Kodi nie wystawiło JSON-RPC na porcie 8089"
}

wait_addon() {
    local id="$1" i out
    for i in $(seq 1 60); do
        out=$(rpc Addons.GetAddonDetails \
            "{\"addonid\":\"$id\",\"properties\":[\"version\",\"enabled\",\"installed\"]}" \
            2>/dev/null || true)
        [[ "$out" == *"\"addonid\":\"$id\""* ]] && return 0
        sleep 1
    done
    return 1
}

enable_addons() {
    local ids=() id out
    if [[ "$NO_DEPS" != "1" && -f "$DEPS_FILE" ]]; then
        while IFS=$'\t' read -r id _rest; do
            [[ -z "${id:-}" || "$id" == \#* ]] && continue
            ids+=("$id")
        done < "$DEPS_FILE"
    fi
    ids+=("$SKIN_ID")

    log "Sprawdzam rejestrację add-onów w Kodi..."
    for id in "${ids[@]}"; do
        if ! wait_addon "$id"; then
            warn "Kodi nie widzi add-onu $id"
            continue
        fi
        out=$(rpc Addons.SetAddonEnabled \
            "{\"addonid\":\"$id\",\"enabled\":true}" 2>/dev/null || true)
        if [[ "$out" != *'"result"'* ]]; then
            warn "nie udało się włączyć $id: $out"
        fi
    done
}

run_skinvariables_generator() {
    local i out
    log "Uruchamiam generator script.skinvariables (może potrwać ok. 10 s)..."
    out=$(rpc Addons.ExecuteAddon \
        "{\"addonid\":\"script.skinvariables\",\"params\":[\"run_executebuiltin=special://skin/shortcuts/skinvariables-build-templates.json\",\"use_rules\"]}" \
        2>/dev/null || true)
    if [[ "$out" != *'\"result\"'* ]]; then
        warn "Generator nie zwrócił wyniku: $out"
    fi
    # Wait for generator to finish (it updates XML files)
    for i in $(seq 1 15); do
        sleep 1
    done
    log "Generator zakończony."
}

log "Konfiguracja TMDb Helper zakończona."

copy_fanfilm_prebuilt() {
    log "Kopiuję prebuilt fanfilm-tmdb do skina..."
    
    # Ręcznie skopiuj pliki prebuilta do skina (shortcuts folder)
    local prebuilt_src="$ADDONS_DIR/$SKIN_ID/shortcuts/prebuilt/fanfilm-tmdb"
    local shortcuts_dst="$ADDONS_DIR/$SKIN_ID/shortcuts"
    
    log "Kopiuję pliki prebuilta fanfilm-tmdb do shortcuts..."
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-homemenu.json\" \"$shortcuts_dst/skinvariables-shortcut-homemenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-sidemenu.json\" \"$shortcuts_dst/skinvariables-shortcut-sidemenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-powermainmenu.json\" \"$shortcuts_dst/skinvariables-shortcut-powermainmenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-searchmenu.json\" \"$shortcuts_dst/skinvariables-shortcut-searchmenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-context.json\" \"$shortcuts_dst/skinvariables-shortcut-context.json\""
    run_tv "chmod 644 \"$shortcuts_dst\"/skinvariables-shortcut-*.json"
    log "  Prebuilt fanfilm-tmdb skopiowany do shortcuts"
    
    # Ręcznie skopiuj pliki prebuilta do skinvariables data folder (dla generatora)
    local skinvars_dst="/media/developer/apps/usr/palm/applications/org.xbmc.kodi/.kodi/userdata/addon_data/script.skinvariables/nodes/$SKIN_ID"
    
    log "Kopiuję pliki prebuilta fanfilm-tmdb do skinvariables data..."
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-homemenu.json\" \"$skinvars_dst/skinvariables-shortcut-homemenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-sidemenu.json\" \"$skinvars_dst/skinvariables-shortcut-sidemenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-powermainmenu.json\" \"$skinvars_dst/skinvariables-shortcut-powermainmenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-searchmenu.json\" \"$skinvars_dst/skinvariables-shortcut-searchmenu.json\""
    run_tv "cp -f \"$prebuilt_src/skinvariables-shortcut-context.json\" \"$skinvars_dst/skinvariables-shortcut-context.json\""
    run_tv "chmod 644 \"$skinvars_dst\"/skinvariables-shortcut-*.json"
    log "  Prebuilt fanfilm-tmdb skopiowany do skinvariables data"
    
    # Uruchom generator ponownie po skopiowaniu plików
    log "Uruchamiam generator script.skinvariables..."
    local out
    out=$(rpc Addons.ExecuteAddon \
        "{\"addonid\":\"script.skinvariables\",\"params\":[\"run_executebuiltin=special://skin/shortcuts/skinvariables-build-templates.json\",\"use_rules\",\"force=true\"]}" \
        2>/dev/null || true)
    if [[ "$out" != *'\"result\"'* ]]; then
        warn "Generator nie zwrócił wyniku: $out"
    fi
    # Odczekaj chwilę na skopiowanie
    sleep 3
    log "  Prebuilt fanfilm-tmdb skopiowany i generator uruchomiony"
}
configure_tmdbhelper_fanfilm() {
    local out
    log "Konfiguruję TMDb Helper do używania FanFilm jako odtwarzacza..."
    
    # 1. Skopiuj plik player JSON do TMDb Helper
    local player_src="$ADDONS_DIR/$SKIN_ID/extras/players/fanfilm.json"
    local player_dst="$ADDONS_DIR/plugin.video.themoviedb.helper/resources/players/fanfilm.json"
    
    log "Kopiuję fanfilm.json do TMDb Helper..."
    run_tv "mkdir -p '$(dirname \"$player_dst\")' && cp -f \"$player_src\" \"$player_dst\""
    run_tv "chmod 644 \"$player_dst\""
    log "  fanfilm.json skopiowany"
    
    # 2. Ustaw FanFilm jako domyślny player dla filmów
    log "Ustawiam FanFilm jako domyślny player dla filmów..."
    out=$(rpc Addons.ExecuteAddon \
        "{\"addonid\":\"plugin.video.themoviedb.helper\",\"params\":[\"set_defaultplayer=movie\"]}" \
        2>/dev/null || true)
    if [[ "$out" != *'"result"'* ]]; then
        warn "Nie udało się ustawić domyślnego playera dla filmów: $out"
    else
        log "  Domyślny player filmów ustawiony"
    fi
    
    # 3. Ustaw FanFilm jako domyślny player dla seriali
    log "Ustawiam FanFilm jako domyślny player dla seriali..."
    out=$(rpc Addons.ExecuteAddon \
        "{\"addonid\":\"plugin.video.themoviedb.helper\",\"params\":[\"set_defaultplayer=tv\"]}" \
        2>/dev/null || true)
    if [[ "$out" != *'"result"'* ]]; then
        warn "Nie udało się ustawić domyślnego playera dla seriali: $out"
    else
        log "  Domyślny player seriali ustawiony"
    fi
    
    # 4. Wymuś używanie providera zamiast Kodi player (pomijane - ustawiane ręcznie)
    # log "Włączam używanie zewnętrznego providera..."
    # out=$(rpc Settings.SetSettingValue \
    #     "{\"setting\":\"plugin.video.themoviedb.helper.default_player_provider\",\"value\":true}" \
    #     2>/dev/null || true)
    # if [[ "$out" != *'"result":true'* ]]; then
    #     warn "Nie udało się włączyć providera: $out"
    # else
    #     log "  Provider włączony"
    # fi
    
    log "Konfiguracja TMDb Helper zakończona."
}

activate_skin() {
    local out cur i
    log "Ustawiam aktywny skin: $SKIN_ID..."
    out=$(rpc Settings.SetSettingValue \
        "{\"setting\":\"lookandfeel.skin\",\"value\":\"$SKIN_ID\"}" 2>/dev/null || true)
    if [[ "$out" != *'"result":true'* ]]; then
        warn "Kodi odrzuciło zmianę skina: $out"
        warn "Wybierz ręcznie: Ustawienia -> Interfejs -> Skórka -> NetflixLike."
        return 1
    fi
    # Wait for skin to be reported as active
    for i in $(seq 1 30); do
        cur=$(rpc Settings.GetSettingValue '{"setting":"lookandfeel.skin"}' 2>/dev/null || true)
        if [[ "$cur" == *"$SKIN_ID"* ]]; then
            log "  Aktywny skin: $SKIN_ID"
            break
        fi
        sleep 1
    done
    
    # Run generator while skin is active to generate required includes
    run_skinvariables_generator
    
    # Reload skin to pick up generated includes
    log "Przeładowuję skin po generacji..."
    rpc Application.ReloadSkin '{}' >/dev/null 2>&1 || true
    sleep 3
    
    # Verify skin is still active after reload
    for i in $(seq 1 30); do
        cur=$(rpc Settings.GetSettingValue '{"setting":"lookandfeel.skin"}' 2>/dev/null || true)
        if [[ "$cur" == *"$SKIN_ID"* ]]; then
            log "  Aktywny skin (po przeładowaniu): $SKIN_ID"
            return 0
        fi
        sleep 1
    done
    warn "Skin nie został aktywowany automatycznie po przeładowaniu."
    warn "Wybierz ręcznie: Ustawienia -> Interfejs -> Skórka -> NetflixLike."
    return 1
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    log "== deploy $SKIN_ID $SKIN_VERSION na '$TV' =="
    preflight
    build_plan

    if [[ "$DRY_RUN" == "1" ]]; then
        log ""
        log "DRY-RUN: nic nie zapisano na TV."
        log "  backup:     $BACKUP_ROOT/<timestamp>/"
        log "  skin:       $ADDONS_DIR/$SKIN_ID"
        log "  zależności: ${#plan_id[@]}"
        log "  restart:    $([[ "$NO_RESTART" == "1" ]] && echo nie || echo tak)"
        log "  aktywacja:  $([[ "$ACTIVATE" == "1" ]] && echo tak || echo nie)"
        exit 0
    fi

    prepare_deps
    check_space

    local ts; ts=$(date -u +%Y%m%dT%H%M%SZ)
    BACKUP_DIR=""
    do_backup "$ts"

    copy_skin
    install_deps

    if [[ "$NO_RESTART" == "1" ]]; then
        log "Restart Kodi: pominięty (--no-restart)."
    else
        restart_kodi
        enable_addons
        if [[ "$ACTIVATE" == "1" ]]; then
            activate_skin || true
            configure_tmdbhelper_fanfilm
            copy_fanfilm_prebuilt
        fi
    fi

    log ""
    log "Gotowe."
    log "  Backup:      ${BACKUP_DIR:-brak}"
    log "  Skin:        $ADDONS_DIR/$SKIN_ID ($SKIN_VERSION)"
    log "  Zależności:  ${#plan_id[@]} zainstalowanych"
    if [[ "$NO_RESTART" != "1" ]]; then
        log "  Kodi:        zrestartowane"
    fi
    if [[ "$NO_RESTART" != "1" && "$ACTIVATE" != "1" ]]; then
        log "  Aktywacja:   nie zmieniano (użyj --activate albo wybierz skina w Kodi)"
    fi
}

main "$@"
