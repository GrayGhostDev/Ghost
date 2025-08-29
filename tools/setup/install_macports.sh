#!/usr/bin/env bash
set -euo pipefail

# Source the env helpers for safe_curl function
if [ -f "$(dirname "$0")/env_helpers.sh" ]; then
  source "$(dirname "$0")/env_helpers.sh"
fi

need_xcode() {
  if ! xcode-select -p >/dev/null 2>&1; then
    echo "[install_macports] Xcode Command Line Tools not found. Triggering installer..."
    xcode-select --install || true
    echo "[install_macports] Please complete the Xcode CLT GUI installer, then re-run this script."
    exit 1
  fi
}

macports_installed() {
  [[ -x /opt/local/bin/port ]]
}

detect_os_codename() {
  # Map macOS major to codename used by MacPorts pkg
  local major
  major="$(sw_vers -productVersion | awk -F. '{print $1}')"
  case "$major" in
    11) echo "11-BigSur" ;;
    12) echo "12-Monterey" ;;
    13) echo "13-Ventura" ;;
    14) echo "14-Sonoma" ;;
    15) echo "15-Sequoia" ;; # Future-proof; update if needed
    *) echo "${major}" ;;
  esac
}

latest_macports_pkg_url() {
  local codename tag ver
  codename="$(detect_os_codename)"
  
  # Use safe_curl if available, otherwise use regular curl with SSL handling
  if command -v safe_curl >/dev/null 2>&1; then
    tag="$(safe_curl -fsSL https://api.github.com/repos/macports/macports-base/releases/latest | awk -F'\"' '/"tag_name":/ {print $4; exit}' 2>/dev/null)" || tag=""
  else
    # Fallback: temporarily clear Proxyman SSL env vars
    local old_cafile="${CURL_CA_BUNDLE:-}"
    local old_capath="${SSL_CERT_DIR:-}"
    local old_cafile_path="${SSL_CERT_PATH:-}"
    unset CURL_CA_BUNDLE SSL_CERT_DIR SSL_CERT_FILE SSL_CERT_PATH HTTPS_CA_BUNDLE REQUESTS_CA_BUNDLE
    
    tag="$(curl -fsSL https://api.github.com/repos/macports/macports-base/releases/latest 2>/dev/null | awk -F'\"' '/"tag_name":/ {print $4; exit}')" || tag=""
    
    # Restore env vars
    [ -n "$old_cafile" ] && export CURL_CA_BUNDLE="$old_cafile"
    [ -n "$old_capath" ] && export SSL_CERT_DIR="$old_capath"
    [ -n "$old_cafile_path" ] && export SSL_CERT_PATH="$old_cafile_path"
  fi
  
  # Use fallback version if API call failed
  if [ -z "$tag" ] || [ "$tag" = "null" ]; then
    echo "[install_macports] Failed to get latest release, using fallback version v2.11.5" >&2
    tag="v2.11.5"
  fi
  
  ver="${tag#v}"
  echo "https://github.com/macports/macports-base/releases/download/${tag}/MacPorts-${ver}-${codename}.pkg"
}

install_macports() {
  need_xcode
  local url pkg
  url="$(latest_macports_pkg_url)"
  pkg="/tmp/$(basename "$url")"
  echo "[install_macports] Downloading $url ..."
  
  # Try multiple curl strategies to handle Proxyman SSL interference
  local download_success=false
  
  # Strategy 1: Use safe_curl if available
  if command -v safe_curl >/dev/null 2>&1; then
    if safe_curl -fL "$url" -o "$pkg"; then
      download_success=true
    fi
  fi
  
  # Strategy 2: Use curl with explicit system certs
  if [ "$download_success" = false ]; then
    echo "[install_macports] Trying with system certificates..."
    local old_cafile="${CURL_CA_BUNDLE:-}"
    unset CURL_CA_BUNDLE SSL_CERT_DIR SSL_CERT_FILE SSL_CERT_PATH HTTPS_CA_BUNDLE REQUESTS_CA_BUNDLE
    
    # Try with explicit system cert bundle on macOS
    if curl -fL --cacert /etc/ssl/cert.pem "$url" -o "$pkg" 2>/dev/null; then
      download_success=true
    elif curl -fL --cacert /usr/local/etc/ca-certificates.crt "$url" -o "$pkg" 2>/dev/null; then
      download_success=true
    elif curl -fL --cacert /opt/homebrew/etc/ca-certificates.crt "$url" -o "$pkg" 2>/dev/null; then
      download_success=true
    fi
    
    # Restore CA bundle if it was set
    [ -n "$old_cafile" ] && export CURL_CA_BUNDLE="$old_cafile"
  fi
  
  # Strategy 3: Use curl with --insecure (last resort)
  if [ "$download_success" = false ]; then
    echo "[install_macports] Trying with --insecure (bypassing SSL verification)..."
    unset CURL_CA_BUNDLE SSL_CERT_DIR SSL_CERT_FILE SSL_CERT_PATH HTTPS_CA_BUNDLE REQUESTS_CA_BUNDLE
    
    if curl -fLk "$url" -o "$pkg"; then
      download_success=true
      echo "[install_macports] WARNING: Downloaded with SSL verification disabled"
    fi
  fi
  
  # Strategy 4: Use wget as alternative
  if [ "$download_success" = false ] && command -v wget >/dev/null 2>&1; then
    echo "[install_macports] Trying with wget..."
    if wget --no-check-certificate -O "$pkg" "$url"; then
      download_success=true
      echo "[install_macports] Downloaded using wget"
    fi
  fi
  
  if [ "$download_success" = false ]; then
    echo "[install_macports] ERROR: Failed to download MacPorts installer"
    echo "[install_macports] You may need to download it manually from:"
    echo "[install_macports] $url"
    exit 1
  fi
  
  echo "[install_macports] Installing $pkg ..."
  sudo installer -pkg "$pkg" -target /
}

selfupdate() {
  echo "[install_macports] Running 'sudo port -v selfupdate' ..."
  sudo /opt/local/bin/port -v selfupdate || {
    echo "Selfupdate failed. Try manually: sudo /opt/local/bin/port -v selfupdate"
    exit 1
  }
}

main() {
  if macports_installed; then
    echo "[install_macports] MacPorts already installed."
    selfupdate
  else
    install_macports
    selfupdate
  fi
}

main "$@"

