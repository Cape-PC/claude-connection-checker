"""回線チェッカー（非公式）

このパソコンのネットのつながり方が、Anthropic から見て BAN されやすい状態かを判定する。
IP アドレス・地域・プロバイダ名は画面にも履歴にも出さない。
Anthropic 社とは関係のない非公式ツール。
"""

import concurrent.futures
import csv
import ctypes
import datetime
import html
import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
import winreg
from tkinter import ttk

APP_NAME_JA = "回線チェッカー"
APP_NAME_EN = "Connection Checker"
VERSION = "1.1.1"

# 設定ファイルを置いた URL（GitHub の raw URL など）。空なら組み込みのドメイン一覧だけを使う。
# 形式: {"domains": ["claude.ai", ...]}
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/Cape-PC/claude-connection-checker/main/config/domains.json"

DEFAULT_DOMAINS = [
    "claude.ai",
    "api.anthropic.com",
    "console.anthropic.com",
    "claude.com",
    "platform.claude.com",
    "support.claude.com",
]
BASELINE_DOMAIN = "www.cloudflare.com"  # 比較用の普通のサイト
COUNTRIES_URL = "https://www.anthropic.com/supported-countries"
BUILTIN_COUNTRIES_DATE = "2026-10-10"

TIMEOUT = 10
USER_AGENT = f"KaisenChecker/{VERSION}"

# 公式ページの国名 → ISO 3166-1 alpha-2。ページの読み取りと、組み込み一覧の両方に使う。
COUNTRY_CODES = {
    "Albania": "AL", "Algeria": "DZ", "Andorra": "AD", "Angola": "AO", "Antigua and Barbuda": "AG",
    "Argentina": "AR", "Armenia": "AM", "Australia": "AU", "Austria": "AT", "Azerbaijan": "AZ",
    "Bahamas": "BS", "Bahrain": "BH", "Bangladesh": "BD", "Barbados": "BB", "Belgium": "BE",
    "Belize": "BZ", "Benin": "BJ", "Bhutan": "BT", "Bolivia": "BO", "Bosnia and Herzegovina": "BA",
    "Botswana": "BW", "Brazil": "BR", "Brunei": "BN", "Bulgaria": "BG", "Burkina Faso": "BF",
    "Burundi": "BI", "Cabo Verde": "CV", "Cambodia": "KH", "Cameroon": "CM", "Canada": "CA",
    "Central African Republic": "CF", "Chad": "TD", "Chile": "CL", "Colombia": "CO", "Comoros": "KM",
    "Congo (Brazzaville)": "CG", "Congo, Democratic Republic of (DRC)": "CD", "Costa Rica": "CR",
    "Côte d'Ivoire": "CI", "Croatia": "HR", "Cyprus": "CY", "Czechia (Czech Republic)": "CZ",
    "Denmark": "DK", "Djibouti": "DJ", "Dominica": "DM", "Dominican Republic": "DO", "Ecuador": "EC",
    "Egypt": "EG", "El Salvador": "SV", "Equatorial Guinea": "GQ", "Eritrea": "ER", "Estonia": "EE",
    "Eswatini": "SZ", "Ethiopia": "ET", "Fiji": "FJ", "Finland": "FI", "France": "FR", "Gabon": "GA",
    "Gambia": "GM", "Georgia": "GE", "Germany": "DE", "Ghana": "GH", "Greece": "GR", "Grenada": "GD",
    "Guatemala": "GT", "Guinea": "GN", "Guinea-Bissau": "GW", "Guyana": "GY", "Haiti": "HT",
    "Honduras": "HN", "Hungary": "HU", "Iceland": "IS", "India": "IN", "Indonesia": "ID", "Iraq": "IQ",
    "Ireland": "IE", "Israel": "IL", "Italy": "IT", "Jamaica": "JM", "Japan": "JP", "Jordan": "JO",
    "Kazakhstan": "KZ", "Kenya": "KE", "Kiribati": "KI", "Kuwait": "KW", "Kyrgyzstan": "KG",
    "Laos": "LA", "Latvia": "LV", "Lebanon": "LB", "Lesotho": "LS", "Liberia": "LR", "Libya": "LY",
    "Liechtenstein": "LI", "Lithuania": "LT", "Luxembourg": "LU", "Madagascar": "MG", "Malawi": "MW",
    "Malaysia": "MY", "Maldives": "MV", "Mali": "ML", "Malta": "MT", "Marshall Islands": "MH",
    "Mauritania": "MR", "Mauritius": "MU", "Mexico": "MX", "Micronesia": "FM", "Moldova": "MD",
    "Monaco": "MC", "Mongolia": "MN", "Montenegro": "ME", "Morocco": "MA", "Mozambique": "MZ",
    "Namibia": "NA", "Nauru": "NR", "Nepal": "NP", "Netherlands": "NL", "New Zealand": "NZ",
    "Nicaragua": "NI", "Niger": "NE", "Nigeria": "NG", "North Macedonia": "MK", "Norway": "NO",
    "Oman": "OM", "Pakistan": "PK", "Palau": "PW", "Palestine": "PS", "Panama": "PA",
    "Papua New Guinea": "PG", "Paraguay": "PY", "Peru": "PE", "Philippines": "PH", "Poland": "PL",
    "Portugal": "PT", "Qatar": "QA", "Romania": "RO", "Rwanda": "RW", "Saint Kitts and Nevis": "KN",
    "Saint Lucia": "LC", "Saint Vincent and the Grenadines": "VC", "Samoa": "WS", "San Marino": "SM",
    "São Tomé and Príncipe": "ST", "Saudi Arabia": "SA", "Senegal": "SN", "Serbia": "RS",
    "Seychelles": "SC", "Sierra Leone": "SL", "Singapore": "SG", "Slovakia": "SK", "Slovenia": "SI",
    "Somalia": "SO", "Solomon Islands": "SB", "South Africa": "ZA", "South Korea": "KR",
    "South Sudan": "SS", "Spain": "ES", "Sri Lanka": "LK", "Sudan": "SD", "Suriname": "SR",
    "Sweden": "SE", "Switzerland": "CH", "Taiwan": "TW", "Tajikistan": "TJ", "Tanzania": "TZ",
    "Thailand": "TH", "Timor-Leste": "TL", "Togo": "TG", "Tonga": "TO", "Trinidad and Tobago": "TT",
    "Tunisia": "TN", "Türkiye (Turkey)": "TR", "Turkmenistan": "TM", "Tuvalu": "TV", "Uganda": "UG",
    "Ukraine": "UA", "United Arab Emirates": "AE", "United Kingdom": "GB",
    "United States of America": "US", "Uruguay": "UY", "Uzbekistan": "UZ", "Vanuatu": "VU",
    "Vatican City": "VA", "Vietnam": "VN", "Zambia": "ZM", "Zimbabwe": "ZW",
}
# 一覧に載っている国の属領・海外領土（公式ページの「Territories and dependencies」に当たるもの）
TERRITORIES = set("""
PR GU VI AS MP UM GF GP MQ RE YT PM BL MF NC PF WF TF GI IM JE GG BM KY VG TC MS AI FK SH PN
IO GS AW CW SX BQ GL FO AX SJ BV CX CC NF HM CK NU TK
""".split())

COUNTRY_NAMES = {
    "ja": {"JP": "日本", "US": "アメリカ", "GB": "イギリス", "KR": "韓国", "TW": "台湾",
           "SG": "シンガポール", "HK": "香港", "CN": "中国", "MO": "マカオ", "RU": "ロシア",
           "DE": "ドイツ", "FR": "フランス", "NL": "オランダ", "CA": "カナダ", "AU": "オーストラリア",
           "IN": "インド", "TH": "タイ", "VN": "ベトナム", "PH": "フィリピン", "MY": "マレーシア",
           "ID": "インドネシア", "IR": "イラン", "KP": "北朝鮮", "BY": "ベラルーシ", "CU": "キューバ",
           "SY": "シリア", "VE": "ベネズエラ", "AF": "アフガニスタン", "MM": "ミャンマー"},
    "en": {"JP": "Japan", "US": "United States", "GB": "United Kingdom", "KR": "South Korea",
           "TW": "Taiwan", "SG": "Singapore", "HK": "Hong Kong", "CN": "China", "MO": "Macao",
           "RU": "Russia", "DE": "Germany", "FR": "France", "NL": "Netherlands", "CA": "Canada",
           "AU": "Australia", "IN": "India"},
}

# プロセス名に含まれる文字列 → (表示名, 除外方式 "domain"/"app"/"admin")
VPN_SOFTWARE = {
    "adguardvpn": ("AdGuard VPN", "domain"),
    "surfshark": ("Surfshark", "domain"),
    "windscribe": ("Windscribe", "domain"),
    "warp-svc": ("Cloudflare WARP", "domain"),
    "nordvpn": ("NordVPN", "app"),
    "expressvpn": ("ExpressVPN", "app"),
    "protonvpn": ("Proton VPN", "app"),
    "pia-client": ("Private Internet Access", "app"),
    "mullvad": ("Mullvad VPN", "app"),
    "hotspotshield": ("Hotspot Shield", "app"),
    "cyberghost": ("CyberGhost", "app"),
    "tunnelbear": ("TunnelBear", "app"),
    "openvpn": ("OpenVPN", "app"),
    "wireguard": ("WireGuard", "app"),
    "softether": ("SoftEther VPN", "app"),
    "tailscale": ("Tailscale", "app"),
    "forticlient": ("FortiClient", "admin"),
    "vpnui": ("Cisco Secure Client", "admin"),
    "pangpa": ("GlobalProtect", "admin"),
    "zsatunnel": ("Zscaler", "admin"),
}

# VPN ソフトごとの除外設定の場所。メニュー名はバージョンで変わることがある。
VPN_GUIDE = {
    "ja": {
        "AdGuard VPN": "AdGuard VPN：「除外」→「手動で追加する」で、ドメインを1つずつ追加します。",
        "Surfshark": "Surfshark：「VPN設定」→「Bypasser」→「ウェブサイトとIPをバイパス」に、ドメインを追加します。",
        "Windscribe": "Windscribe：「設定」→「スプリットトンネリング」で「除外」を選び、ホスト名にドメインを追加します。",
        "Cloudflare WARP": "Cloudflare WARP：「設定」→「詳細設定」→「スプリットトンネル」で、ドメインを除外に追加します。",
        "NordVPN": "NordVPN：「設定」→「スプリットトンネリング」で、Claude、ブラウザ、回線チェッカー.exe をVPNから外します。",
        "ExpressVPN": "ExpressVPN：「オプション」→「スプリットトンネリング」で、Claude、ブラウザ、回線チェッカー.exe をVPNから外します。",
        "Proton VPN": "Proton VPN：「設定」→「スプリットトンネリング」で、Claude、ブラウザ、回線チェッカー.exe を除外します。",
        "_app": "{name}：「スプリットトンネリング」や「除外」の設定で、Claude、ブラウザ、回線チェッカー.exe をVPNから外します。",
        "_admin": "{name}は会社や学校が管理するVPNです。設定を変えずに、管理者に相談してください。",
    },
    "en": {
        "AdGuard VPN": "AdGuard VPN: Exclusions → Add manually, then add each domain.",
        "Surfshark": "Surfshark: VPN settings → Bypasser → Bypass websites and IPs, then add the domains.",
        "Windscribe": "Windscribe: Preferences → Split Tunneling → Exclusive, then add the domains as hostnames.",
        "Cloudflare WARP": "Cloudflare WARP: Preferences → Advanced → Split Tunnels, then exclude the domains.",
        "NordVPN": "NordVPN: Settings → Split tunneling, then exclude Claude, your browser and this checker app.",
        "ExpressVPN": "ExpressVPN: Options → Split tunneling, then exclude Claude, your browser and this checker app.",
        "Proton VPN": "Proton VPN: Settings → Split Tunneling, then exclude Claude, your browser and this checker app.",
        "_app": "{name}: in split tunneling or exclusion settings, exclude Claude, your browser and this checker app.",
        "_admin": "{name} is managed by your company or school. Ask your administrator instead of changing it.",
    },
}

OK, VPN, OUTSIDE, UNKNOWN = "ok", "vpn", "outside", "unknown"
SAFE, CAUTION, DANGER = "safe", "caution", "danger"

TEXT = {
    "ja": {
        "app": APP_NAME_JA,
        "title": "回線チェッカー（非公式）",
        "subtitle": "IPアドレス・地域・プロバイダ名は表示しません",
        "col_domain": "接続先", "col_country": "国", "col_status": "回線",
        OK: "家庭向け回線（問題なし）", VPN: "VPN・プロキシ経由", OUTSIDE: "利用対象外の国", UNKNOWN: "確認不可",
        "csv_" + OK: "OK", "csv_" + VPN: "VPN経由", "csv_" + OUTSIDE: "対象外の国", "csv_" + UNKNOWN: "確認不可",
        SAFE: "安全", CAUTION: "要注意", DANGER: "危険",
        "head_" + SAFE: "安全　BANされやすい接続ではありません",
        "head_" + CAUTION: "要注意　一部の通信に気になる点があります",
        "head_" + DANGER: "危険　BANされやすい接続です",
        "head_failed": "要注意　接続を確認できませんでした",
        "checking": "チェック中…",
        "baseline": "（比較）ほかのサイト",
        "reasons": "理由", "actions": "やること",
        "r_failed": "Claudeのどのドメインにも接続を確認できませんでした。",
        "r_country": "Claudeへの接続元の国は{c}です。",
        "r_outside": "Claudeを使える国の外からつながっているドメインがあります。利用対象外の国からの利用は規約違反になります。",
        "r_vpn": "{n}個のドメインが、VPN・プロキシ経由でつながっています。データセンターの回線は、不正利用の判定で疑われやすい種類です。",
        "r_allok": "{n}個のドメインすべてが、VPNを通らず、普通の回線でつながっています。",
        "r_unknown": "{n}個のドメインは確認できませんでした。",
        "r_blocked": "確認できなかった原因は、広告ブロッカー（AdGuardなど）が通信を止めていることかもしれません。",
        "r_split_ok": "{names}は動いていますが、ほかのサイトだけがVPNを通っています。除外設定が効いています。",
        "r_vpnsoft": "VPNソフト（{names}）が動いています。",
        "r_app_split": "{names}はアプリ単位で除外する方式です。回線チェッカー.exe も同じように除外しておかないと、結果がClaudeの実際の通信と合わないことがあります。",
        "r_proxy": "Windowsのプロキシ設定がオンになっています。",
        "a_outside": "VPNの接続先を日本など利用対象の国に変えるか、VPNをオフにしてください。",
        "a_copy": "「除外ドメインをコピー」を押し、VPNソフトの除外設定に貼り付けてください。",
        "a_generic": "VPNソフトの「スプリットトンネリング」や「除外」の設定で、Claudeの通信をVPNから外してください。",
        "a_off": "すぐに直せないときは、Claudeを使う間だけVPNをオフにしてください。",
        "a_retry": "少し待ってから「再チェック」を押してください。続く場合は、広告ブロッカーを一時的にオフにして試してください。",
        "a_safe": "今の設定のままで大丈夫です。VPNソフトを入れ直したときは、もう一度チェックしてください。",
        "a_verify": "画面に突然「本人確認」が出たら、放置せずにすぐ対応してください。",
        "btn_check": "再チェック", "btn_copy": "除外ドメインをコピー", "btn_folder": "履歴フォルダ",
        "btn_manual": "説明書", "btn_lang": "English", "btn_close": "閉じる",
        "copied": "{n}個のドメインをコピーしました：{d}",
        "saved": "{t} に判定し、履歴に記録しました。",
        "save_failed": "履歴を保存できませんでした（{e}）。Excelで開いている場合は閉じてください。",
        "error": "エラー：{e}。ネットの接続を確かめて、再チェックしてください。",
        "check_failed": "チェックできませんでした",
        "no_manual": "説明書が見つかりません。exeと同じフォルダに 説明書.html と Manual_en.html を置いてください。",
        "src_live": "国の一覧：公式ページから取得（{d}）",
        "src_cache": "国の一覧：前回取得した一覧（{d}）",
        "src_builtin": "国の一覧：組み込み（{d}時点）",
        "notice": "非公式ツールです。Anthropic社とは関係ありません。判定は目安で、BANされないことを保証しません。\n"
                  "アプリ単位で除外するVPNと、ブラウザ拡張のVPNは正しく判定できません。",
        "csv_header": ["日時", "結論"],
        "csv_vpnsoft": "VPNソフト", "csv_proxy": "Windowsプロキシ", "on": "オン", "off": "オフ", "none": "なし",
        "sep": "、",
    },
    "en": {
        "app": APP_NAME_EN,
        "title": "Connection Checker (unofficial)",
        "subtitle": "IP addresses, locations and ISP names are never shown",
        "col_domain": "Domain", "col_country": "Country", "col_status": "Connection",
        OK: "Regular connection (OK)", VPN: "Via VPN / proxy", OUTSIDE: "Unsupported country", UNKNOWN: "Could not check",
        "csv_" + OK: "OK", "csv_" + VPN: "VPN", "csv_" + OUTSIDE: "Unsupported", "csv_" + UNKNOWN: "Unknown",
        SAFE: "Safe", CAUTION: "Caution", DANGER: "Danger",
        "head_" + SAFE: "Safe — this connection is unlikely to get you banned",
        "head_" + CAUTION: "Caution — some connections need attention",
        "head_" + DANGER: "Danger — this connection is likely to get you banned",
        "head_failed": "Caution — could not check the connection",
        "checking": "Checking…",
        "baseline": "(Reference) other sites",
        "reasons": "Why", "actions": "What to do",
        "r_failed": "Could not reach any Claude domain.",
        "r_country": "You connect to Claude from: {c}.",
        "r_outside": "Some domains are reached from a country where Claude is not available. Using Claude from an unsupported country violates the terms.",
        "r_vpn": "{n} domain(s) go through a VPN or proxy. Data center connections are often flagged by fraud detection.",
        "r_allok": "All {n} domains connect over a regular connection without a VPN.",
        "r_unknown": "{n} domain(s) could not be checked.",
        "r_blocked": "An ad blocker (such as AdGuard) may be blocking the check.",
        "r_split_ok": "{names} is running, but only other sites go through the VPN. Your exclusions are working.",
        "r_vpnsoft": "VPN software is running: {names}.",
        "r_app_split": "{names} excludes by app. Exclude this checker app as well, or the result may not match Claude's real traffic.",
        "r_proxy": "The Windows proxy setting is on.",
        "a_outside": "Switch your VPN server to a supported country, or turn the VPN off.",
        "a_copy": "Click \"Copy domains to exclude\" and paste them into your VPN's exclusion settings.",
        "a_generic": "Use your VPN's split tunneling or exclusion settings to keep Claude's traffic out of the VPN.",
        "a_off": "If you can't fix it now, turn the VPN off while you use Claude.",
        "a_retry": "Wait a moment and click \"Check again\". If it keeps failing, pause your ad blocker and try again.",
        "a_safe": "No changes needed. Check again after reinstalling or resetting your VPN.",
        "a_verify": "If Claude suddenly asks you to verify your identity, respond right away.",
        "btn_check": "Check again", "btn_copy": "Copy domains to exclude", "btn_folder": "History folder",
        "btn_manual": "Manual", "btn_lang": "日本語", "btn_close": "Close",
        "copied": "Copied {n} domain(s): {d}",
        "saved": "Checked at {t} and saved to history.",
        "save_failed": "Could not save history ({e}). Close the file if it is open in Excel.",
        "error": "Error: {e}. Check your internet connection and try again.",
        "check_failed": "Could not complete the check",
        "no_manual": "Manual not found. Put Manual_en.html and 説明書.html in the same folder as the app.",
        "src_live": "Country list: fetched from the official page ({d})",
        "src_cache": "Country list: last fetched copy ({d})",
        "src_builtin": "Country list: built-in (as of {d})",
        "notice": "Unofficial tool, not affiliated with Anthropic. Results are a guide only and do not guarantee you won't be banned.\n"
                  "Per-app VPN exclusions and browser-extension VPNs cannot be checked accurately.",
        "csv_header": ["Time", "Result"],
        "csv_vpnsoft": "VPN software", "csv_proxy": "Windows proxy", "on": "On", "off": "Off", "none": "None",
        "sep": ", ",
    },
}


# ---------------------------------------------------------------- 保存場所・設定

def data_dir():
    path = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "KaisenChecker")
    os.makedirs(path, exist_ok=True)
    return path


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_json(name, default):
    try:
        with open(os.path.join(data_dir(), name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    try:
        with open(os.path.join(data_dir(), name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------- 通信

def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read().decode("utf-8", errors="replace")


def fetch_trace_ip(host):
    """Cloudflare の /cdn-cgi/trace から、そのサイトに見えている接続元 IP を取る。"""
    text = http_get(f"https://{host}/cdn-cgi/trace")
    for line in text.splitlines():
        if line.startswith("ip="):
            return line[3:].strip()
    raise ValueError("no ip in trace")


def lookup_ip(ip):
    """IP の国とプロキシ判定を返す。freeipapi.com を優先し、だめなら IP2Location.io。"""
    errors = []
    try:
        data = json.loads(http_get(f"https://freeipapi.com/api/json/{ip}"))
        if data.get("countryCode"):
            return {"country": data["countryCode"].upper(), "proxy": bool(data.get("isProxy"))}
        errors.append("freeipapi: empty")
    except Exception as e:  # noqa: BLE001
        errors.append(f"freeipapi: {type(e).__name__}")
    try:
        data = json.loads(http_get(f"https://api.ip2location.io/?ip={ip}"))
        if data.get("country_code") and data["country_code"] != "-":
            return {"country": data["country_code"].upper(), "proxy": bool(data.get("is_proxy"))}
        errors.append("ip2location: empty")
    except Exception as e:  # noqa: BLE001
        errors.append(f"ip2location: {type(e).__name__}")
    raise RuntimeError(" / ".join(errors))


def parse_supported_countries(page):
    """公式ページの国一覧を国コードの集合にする。読めない国名があれば None。"""
    start = page.find("currently offer access")
    if start < 0:
        return None
    ul = re.search(r"<ul[^>]*>(.*?)</ul>", page[start:], re.S)
    if not ul:
        return None
    codes = set()
    for item in re.findall(r"<li[^>]*>(.*?)</li>", ul.group(1), re.S):
        name = html.unescape(re.sub(r"<[^>]+>", "", item)).strip()
        name = re.sub(r"\s*\(except .*\)$", "", name)  # Ukraine (except ...) など
        code = COUNTRY_CODES.get(name)
        if not code:
            return None  # 知らない国名がある＝ページの形が変わった。組み込みに任せる
        codes.add(code)
    return codes if len(codes) >= 100 else None


def get_supported_countries():
    """(国コードの集合, 取得元, 日付)。公式ページ → 前回の取得 → 組み込みの順に使う。"""
    today = datetime.date.today().isoformat()
    try:
        codes = parse_supported_countries(http_get(COUNTRIES_URL))
        if codes:
            save_json("countries.json", {"date": today, "codes": sorted(codes)})
            return codes | TERRITORIES, "live", today
    except Exception:  # noqa: BLE001
        pass
    cache = load_json("countries.json", None)
    if cache and cache.get("codes"):
        return set(cache["codes"]) | TERRITORIES, "cache", cache.get("date", "?")
    return set(COUNTRY_CODES.values()) | TERRITORIES, "builtin", BUILTIN_COUNTRIES_DATE


DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,63}$")


def get_domains():
    """設定ファイルの URL があればそこからドメイン一覧を読む。失敗したら前回分か組み込み。"""
    if REMOTE_CONFIG_URL.startswith("https://"):
        try:
            data = json.loads(http_get(REMOTE_CONFIG_URL))
            domains = [d.strip().lower() for d in data.get("domains", []) if isinstance(d, str)]
            domains = [d for d in domains if DOMAIN_RE.match(d)]
            if domains:
                save_json("domains.json", {"domains": domains})
                return domains
        except Exception:  # noqa: BLE001
            pass
        cache = load_json("domains.json", None)
        if cache and cache.get("domains"):
            return cache["domains"]
    return list(DEFAULT_DOMAINS)


# ---------------------------------------------------------------- パソコンの状態

def detect_vpn_software():
    try:
        out = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, encoding="mbcs", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15,
        ).stdout.lower()
    except Exception:  # noqa: BLE001
        return []
    found = []
    for key, (name, kind) in VPN_SOFTWARE.items():
        if key in out and all(name != f[0] for f in found):
            found.append((name, kind))
    return found


def windows_proxy_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as k:
            return winreg.QueryValueEx(k, "ProxyEnable")[0] == 1
    except OSError:
        return False


def windows_dark_mode():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def looks_blocked(err):
    """広告ブロッカー等で止められたらしいエラーかどうか。"""
    text = str(err).lower()
    if isinstance(err, urllib.error.HTTPError) and err.code in (403, 451):
        return True
    return any(w in text for w in ("blocked", "10054", "connection reset", "forcibly closed", "refused"))


# ---------------------------------------------------------------- 判定

def classify(info, supported):
    if info is None:
        return UNKNOWN
    if info["country"] not in supported:
        return OUTSIDE
    if info["proxy"]:
        return VPN
    return OK


def run_check():
    """判定をすべて行い、IP を含まない結果だけを返す。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_domains = ex.submit(get_domains)
        f_countries = ex.submit(get_supported_countries)
        f_vpn = ex.submit(detect_vpn_software)
        domains = f_domains.result()

        hosts = domains + [BASELINE_DOMAIN]
        ips, errors = {}, {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts)) as tx:
            futures = {tx.submit(fetch_trace_ip, h): h for h in hosts}
            for f in concurrent.futures.as_completed(futures):
                h = futures[f]
                try:
                    ips[h] = f.result()
                except Exception as e:  # noqa: BLE001
                    errors[h] = e
        supported, country_src, country_date = f_countries.result()
        vpn_software = f_vpn.result()

    # 同じ IP は 1 回だけ問い合わせる
    lookups = {}
    for ip in set(ips.values()):
        try:
            lookups[ip] = lookup_ip(ip)
        except Exception as e:  # noqa: BLE001
            lookups[ip] = None
            for h, hip in ips.items():
                if hip == ip:
                    errors[h] = e

    rows = []
    for h in hosts:
        info = lookups.get(ips.get(h))
        rows.append({"domain": h, "status": classify(info, supported),
                     "country": info["country"] if info else None})
    del ips, lookups  # IP はここで捨てる

    claude_rows = rows[:-1]
    statuses = [r["status"] for r in claude_rows]
    checked = [s for s in statuses if s != UNKNOWN]

    if OUTSIDE in statuses or (checked and all(s == VPN for s in checked)):
        level = DANGER
    elif VPN in statuses or UNKNOWN in statuses:
        level = CAUTION
    else:
        level = SAFE

    return {
        "time": datetime.datetime.now(),
        "level": level,
        "rows": claude_rows,
        "baseline": rows[-1],
        "vpn_software": vpn_software,
        "proxy_setting": windows_proxy_enabled(),
        "blocked_hint": any(looks_blocked(e) for e in errors.values()),
        "all_failed": not checked,
        "country_src": country_src,
        "country_date": country_date,
    }


def country_label(code, lang):
    if not code:
        return "—"
    return COUNTRY_NAMES[lang].get(code, code)


def build_explanation(result, lang):
    """結論の見出し・理由・やることを作る。"""
    t = TEXT[lang]
    level, rows = result["level"], result["rows"]
    vpn_rows = [r for r in rows if r["status"] == VPN]
    outside_rows = [r for r in rows if r["status"] == OUTSIDE]
    unknown_rows = [r for r in rows if r["status"] == UNKNOWN]
    countries = sorted({r["country"] for r in rows if r["country"]})
    software = result["vpn_software"]
    names = t["sep"].join(n for n, _ in software)

    headline = t["head_failed"] if result["all_failed"] else t["head_" + level]

    reasons = []
    if result["all_failed"]:
        reasons.append(t["r_failed"])
    else:
        reasons.append(t["r_country"].format(c=t["sep"].join(country_label(c, lang) for c in countries)))
    if outside_rows:
        reasons.append(t["r_outside"])
    if vpn_rows:
        reasons.append(t["r_vpn"].format(n=len(vpn_rows)))
    if not vpn_rows and not outside_rows and not unknown_rows:
        reasons.append(t["r_allok"].format(n=len(rows)))
    if unknown_rows and not result["all_failed"]:
        reasons.append(t["r_unknown"].format(n=len(unknown_rows)))
    if result["blocked_hint"]:
        reasons.append(t["r_blocked"])
    if software:
        if result["baseline"]["status"] == VPN and not vpn_rows and not outside_rows:
            reasons.append(t["r_split_ok"].format(names=names))
        else:
            reasons.append(t["r_vpnsoft"].format(names=names))
        app_split = [n for n, kind in software if kind == "app"]
        if app_split:
            reasons.append(t["r_app_split"].format(names=t["sep"].join(app_split)))
    if result["proxy_setting"]:
        reasons.append(t["r_proxy"])

    actions = []
    if outside_rows:
        actions.append(t["a_outside"])
    if vpn_rows:
        actions.append(t["a_copy"])
        guides = VPN_GUIDE[lang]
        if software:
            for name, kind in software:
                if name in guides:
                    actions.append(guides[name])
                else:
                    actions.append(guides["_" + kind].format(name=name))
        else:
            actions.append(t["a_generic"])
        actions.append(t["a_off"])
    if unknown_rows:
        actions.append(t["a_retry"])
    if level == SAFE:
        actions.append(t["a_safe"])
    actions.append(t["a_verify"])

    return headline, reasons, actions


def save_history(result, lang):
    t = TEXT[lang]
    path = os.path.join(data_dir(), "history.csv")
    domains = [r["domain"] for r in result["rows"]]
    header = t["csv_header"] + domains + [t["csv_vpnsoft"], t["csv_proxy"]]
    row = [
        result["time"].strftime("%Y-%m-%d %H:%M:%S"),
        t[result["level"]],
        *[t["csv_" + r["status"]] for r in result["rows"]],
        t["sep"].join(n for n, _ in result["vpn_software"]) or t["none"],
        t["on"] if result["proxy_setting"] else t["off"],
    ]
    new_file = not os.path.exists(path)
    try:
        with open(path, "a", newline="", encoding="utf-8-sig" if new_file else "utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(header)
            w.writerow(row)
        return None
    except OSError as e:
        return t["save_failed"].format(e=e.strerror)


# ---------------------------------------------------------------- 画面

PALETTES = {
    "light": {
        "bg": "#f5f6f8", "fg": "#1d2330", "muted": "#5b6475", "line": "#d9dde5", "panel": "#ffffff",
        "head_bg": "#eceef2",
        SAFE: ("#1f7a4a", "#e8f5ee"), CAUTION: ("#a35f00", "#fff4e0"), DANGER: ("#b42318", "#fdecea"),
        "checking": ("#2f5bd3", "#e9eefc"), UNKNOWN: "#5b6475",
        "primary": ("#2f5bd3", "#2449ad", "#1b3888", "#ffffff"),
        "secondary": ("#4b5567", "#3a4252", "#2b313d", "#ffffff"),
        "plain": ("#e3e6ec", "#d3d8e0", "#c1c7d2", "#1d2330"),
        "disabled": "#9aa3b5",
    },
    "dark": {
        "bg": "#12151c", "fg": "#e6e9ef", "muted": "#9aa3b5", "line": "#2a303c", "panel": "#1a1f29",
        "head_bg": "#222836",
        SAFE: ("#6fd39c", "#15301f"), CAUTION: ("#ffb35c", "#3a2614"), DANGER: ("#ff8a80", "#3b1714"),
        "checking": ("#9db5ff", "#1c2540"), UNKNOWN: "#9aa3b5",
        "primary": ("#4a74e8", "#5f86f0", "#3a5fc4", "#ffffff"),
        "secondary": ("#3a4252", "#4b5567", "#2b313d", "#e6e9ef"),
        "plain": ("#2a303c", "#363d4b", "#1f242e", "#e6e9ef"),
        "disabled": "#5b6475",
    },
}
FONT = "Yu Gothic UI"


class HoverButton(tk.Button):
    """ホバーで色が変わり、押すと沈むボタン。"""

    def __init__(self, master, colors, disabled_fg, **kw):
        bg, hover, active, fg = colors
        super().__init__(master, bg=bg, fg=fg, activebackground=active, activeforeground=fg,
                         relief="flat", bd=0, cursor="hand2", padx=14, pady=7,
                         font=(FONT, 10, "bold"), disabledforeground=disabled_fg, **kw)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self["state"] != "disabled" and self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<ButtonPress-1>", lambda e: self["state"] != "disabled" and self.config(relief="sunken"))
        self.bind("<ButtonRelease-1>", lambda e: self.config(relief="flat"))


class App:
    def __init__(self, root):
        self.root = root
        self.result = None
        self.settings = load_json("settings.json", {})
        self.lang = self.settings.get("lang", "ja")
        if self.lang not in TEXT:
            self.lang = "ja"
        self.mode = "dark" if windows_dark_mode() else "light"
        self.c = PALETTES[self.mode]
        c = self.c

        root.configure(bg=c["bg"])
        root.geometry("760x820")
        root.minsize(620, 640)
        self._dark_title_bar()

        outer = tk.Frame(root, bg=c["bg"], padx=20, pady=16)
        outer.pack(fill="both", expand=True)

        top = tk.Frame(outer, bg=c["bg"])
        top.pack(fill="x")
        self.title = tk.Label(top, font=(FONT, 16, "bold"), bg=c["bg"], fg=c["fg"])
        self.title.pack(side="left")
        self.btn_lang = HoverButton(top, c["plain"], c["disabled"], command=self.toggle_lang)
        self.btn_lang.pack(side="right")
        self.subtitle = tk.Label(outer, font=(FONT, 9), bg=c["bg"], fg=c["muted"])
        self.subtitle.pack(anchor="w", pady=(0, 10))

        self.banner = tk.Frame(outer, padx=14, pady=10, highlightthickness=1)
        self.banner.pack(fill="x")
        self.headline = tk.Label(self.banner, font=(FONT, 14, "bold"), anchor="w", justify="left")
        self.headline.pack(fill="x")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("K.Treeview", font=(FONT, 10), rowheight=26, background=c["panel"],
                        fieldbackground=c["panel"], foreground=c["fg"], bordercolor=c["line"],
                        lightcolor=c["line"], darkcolor=c["line"])
        style.configure("K.Treeview.Heading", font=(FONT, 10, "bold"), background=c["head_bg"],
                        foreground=c["fg"], bordercolor=c["line"], lightcolor=c["head_bg"],
                        darkcolor=c["head_bg"], relief="flat")
        style.map("K.Treeview.Heading", background=[("active", c["head_bg"])])
        self.tree = ttk.Treeview(outer, columns=("domain", "country", "status"), show="headings",
                                 height=len(DEFAULT_DOMAINS) + 1, style="K.Treeview", selectmode="none")
        for col, width in (("domain", 200), ("country", 110), ("status", 220)):
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure(OK, foreground=c[SAFE][0])
        self.tree.tag_configure(VPN, foreground=c[CAUTION][0])
        self.tree.tag_configure(OUTSIDE, foreground=c[DANGER][0])
        self.tree.tag_configure(UNKNOWN, foreground=c[UNKNOWN])
        self.tree.tag_configure("base", foreground=c["muted"])
        self.tree.pack(fill="x", pady=(14, 4))
        self.source = tk.Label(outer, font=(FONT, 9), bg=c["bg"], fg=c["muted"], anchor="w")
        self.source.pack(fill="x", pady=(0, 8))

        self.text = tk.Text(outer, font=(FONT, 10), wrap="char", bg=c["panel"], fg=c["fg"],
                            relief="flat", padx=12, pady=10, highlightthickness=1,
                            highlightbackground=c["line"], height=10, insertbackground=c["fg"])
        self.text.tag_configure("h", font=(FONT, 11, "bold"), spacing1=4, spacing3=4)
        self.text.tag_configure("p", lmargin1=8, lmargin2=22, spacing3=3)
        self.text.pack(fill="both", expand=True)

        self.notice = tk.Label(outer, font=(FONT, 9), bg=c["bg"], fg=c["muted"], justify="left", anchor="w")
        self.notice.pack(fill="x", pady=(8, 0))
        outer.bind("<Configure>", lambda e: self.notice.config(wraplength=max(300, e.width - 40)))

        bar = tk.Frame(outer, bg=c["bg"])
        bar.pack(fill="x", pady=(10, 0))
        self.btn_check = HoverButton(bar, c["primary"], c["disabled"], command=self.start_check)
        self.btn_check.pack(side="left")
        self.btn_copy = HoverButton(bar, c["secondary"], c["disabled"], command=self.copy_domains)
        self.btn_copy.pack(side="left", padx=6)
        self.btn_folder = HoverButton(bar, c["plain"], c["disabled"], command=self.open_folder)
        self.btn_folder.pack(side="left")
        self.btn_manual = HoverButton(bar, c["plain"], c["disabled"], command=self.open_manual)
        self.btn_manual.pack(side="left", padx=6)
        self.btn_close = HoverButton(bar, c["plain"], c["disabled"], command=root.destroy)
        self.btn_close.pack(side="right")
        self.status = tk.Label(outer, font=(FONT, 9), bg=c["bg"], fg=c["muted"], anchor="w")
        self.status.pack(fill="x", pady=(6, 0))

        self.apply_texts()
        self.start_check()

    def _dark_title_bar(self):
        if self.mode != "dark":
            return
        try:
            self.root.update()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:  # noqa: BLE001
            pass

    def t(self, key):
        return TEXT[self.lang][key]

    def apply_texts(self):
        self.root.title(f"{self.t('app')} {VERSION}")
        self.title.config(text=self.t("title"))
        self.subtitle.config(text=self.t("subtitle"))
        self.notice.config(text=self.t("notice"))
        for col in ("domain", "country", "status"):
            self.tree.heading(col, text=self.t("col_" + col), anchor="w")
        for btn, key in ((self.btn_check, "btn_check"), (self.btn_copy, "btn_copy"),
                         (self.btn_folder, "btn_folder"), (self.btn_manual, "btn_manual"),
                         (self.btn_lang, "btn_lang"), (self.btn_close, "btn_close")):
            btn.config(text=self.t(key))

    def toggle_lang(self):
        self.lang = "en" if self.lang == "ja" else "ja"
        self.settings["lang"] = self.lang
        save_json("settings.json", self.settings)
        self.apply_texts()
        if self.result:
            self.render(self.result)
        elif self.btn_check["state"] == "disabled":
            self.set_banner("checking", self.t("checking"))

    def set_banner(self, key, text):
        fg, bg = self.c[key]
        self.banner.config(bg=bg, highlightbackground=fg, highlightcolor=fg)
        self.headline.config(text=text, bg=bg, fg=fg)

    def start_check(self):
        self.result = None
        self.btn_check.config(state="disabled")
        self.btn_copy.config(state="disabled")
        self.set_banner("checking", self.t("checking"))
        self.status.config(text="")
        self.source.config(text="")
        self.tree.delete(*self.tree.get_children())
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            result, err = run_check(), None
        except Exception as e:  # noqa: BLE001
            result, err = None, e
        self.root.after(0, self.show_result, result, err)

    def show_result(self, result, err):
        self.btn_check.config(state="normal")
        if err is not None:
            self.set_banner(CAUTION, self.t("check_failed"))
            self.status.config(text=self.t("error").format(e=type(err).__name__))
            return
        self.result = result
        self.render(result)
        note = save_history(result, self.lang)
        self.status.config(text=note or self.t("saved").format(t=f"{result['time']:%Y-%m-%d %H:%M}"))

    def render(self, result):
        headline, reasons, actions = build_explanation(result, self.lang)
        self.set_banner(CAUTION if result["all_failed"] else result["level"], headline)

        self.tree.delete(*self.tree.get_children())
        self.tree.configure(height=len(result["rows"]) + 1)
        for r in result["rows"]:
            self.tree.insert("", "end", values=(r["domain"], country_label(r["country"], self.lang),
                                                self.t(r["status"])), tags=(r["status"],))
        b = result["baseline"]
        self.tree.insert("", "end", values=(self.t("baseline"), country_label(b["country"], self.lang),
                                            self.t(b["status"])), tags=("base",))
        self.source.config(text=self.t("src_" + result["country_src"]).format(d=result["country_date"]))

        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", self.t("reasons") + "\n", "h")
        for s in reasons:
            self.text.insert("end", f"・{s}\n" if self.lang == "ja" else f"• {s}\n", "p")
        self.text.insert("end", self.t("actions") + "\n", "h")
        for i, s in enumerate(actions, 1):
            self.text.insert("end", f"{i}. {s}\n", "p")
        self.text.config(state="disabled")

        has_vpn = any(r["status"] == VPN for r in result["rows"])
        self.btn_copy.config(state="normal" if has_vpn else "disabled")

    def copy_domains(self):
        if not self.result:
            return
        domains = [r["domain"] for r in self.result["rows"] if r["status"] == VPN]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(domains))
        self.status.config(text=self.t("copied").format(n=len(domains), d=self.t("sep").join(domains)))

    def open_folder(self):
        os.startfile(data_dir())

    def open_manual(self):
        names = ["Manual_en.html", "説明書.html"] if self.lang == "en" else ["説明書.html", "Manual_en.html"]
        for name in names:
            path = os.path.join(app_dir(), name)
            if os.path.exists(path):
                os.startfile(path)
                return
        self.status.config(text=self.t("no_manual"))


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
