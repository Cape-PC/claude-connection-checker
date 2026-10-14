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
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
import winreg
import tkinter.font as tkfont
from tkinter import ttk

APP_NAME_JA = "回線チェッカー"
APP_NAME_EN = "Connection Checker"
VERSION = "1.2.0"

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


# ---------------------------------------------------------------- v1.2 で足した文言

TEXT["ja"].update({
    "note_mixed": "IPv4とIPv6で経路が違います",
    "note_estimated": "参考値（別の方法で確認）",
    "note_conflict": "判定サービスの答えが食い違い",
    "col_country_hint": "国",
    "r_mixed": "{n}個のドメインで、IPv4とIPv6の通る道が違います。片方だけがVPNを通っています。",
    "r_estimated": "{n}個のドメインは、通常の方法で確認できなかったので、別の方法で調べた参考値です。",
    "r_conflict": "{n}個のドメインで、2つの判定サービスの答えが食い違いました。念のため、少し時間をおいて再チェックしてください。",
    "r_changed": "前回（{t}）は「{prev}」でした。今回は「{now}」に変わりました。",
    "r_changed_domains": "前回から変わったドメイン：{d}",
    "a_mixed": "IPv6だけが別の経路になっています。VPNソフトの「IPv6」の設定（IPv6の漏れを防ぐ設定）を確かめるか、ドメインの除外を見直してください。",
    "a_conflict": "少し時間をおいて、もう一度「再チェック」を押してください。",
    "shortcuts": "F5：再チェック　Esc：閉じる　Ctrl＋プラス／マイナス：文字の大きさ　Ctrl＋0：元の大きさ　Ctrl＋L：言語",
    "opt_autostart": "Windowsの起動時に自動で調べる（安全なときは何も表示しません）",
    "opt_update": "新しい版を確認する（GitHubに接続します）",
    "update_available": "新しい版 {v} があります。",
    "btn_update": "ダウンロードページを開く",
    "autostart_failed": "起動時の自動チェックの設定を変更できませんでした。",
    "autostart_unavailable": "起動時の自動チェックは、exeで使えます。",
    "checking_row": "確認中…",
})
TEXT["en"].update({
    "note_mixed": "IPv4 and IPv6 take different routes",
    "note_estimated": "Estimate (checked another way)",
    "note_conflict": "Lookup services disagree",
    "col_country_hint": "Country",
    "r_mixed": "{n} domain(s) take different routes over IPv4 and IPv6. Only one of them goes through the VPN.",
    "r_estimated": "{n} domain(s) could not be checked the usual way, so the result is an estimate from another method.",
    "r_conflict": "The two lookup services disagreed for {n} domain(s). Wait a moment and check again.",
    "r_changed": "Last time ({t}) the result was \"{prev}\". Now it is \"{now}\".",
    "r_changed_domains": "Domains that changed since last time: {d}",
    "a_mixed": "Only IPv6 takes a different route. Check your VPN's IPv6 setting (the one that prevents IPv6 leaks) or review the domain exclusions.",
    "a_conflict": "Wait a moment and click \"Check again\".",
    "shortcuts": "F5: check again   Esc: close   Ctrl + plus/minus: text size   Ctrl+0: reset size   Ctrl+L: language",
    "opt_autostart": "Check automatically when Windows starts (shows nothing when safe)",
    "opt_update": "Check for a new version (connects to GitHub)",
    "update_available": "A new version {v} is available.",
    "btn_update": "Open download page",
    "autostart_failed": "Could not change the startup check setting.",
    "autostart_unavailable": "The startup check works with the exe.",
    "checking_row": "Checking…",
})

# 取得先として許す系列。設定ファイルが書き換えられても、これ以外のサイトには接続しない。
ALLOWED_DOMAIN_SUFFIXES = ("claude.ai", "anthropic.com", "claude.com")
MAX_DOMAINS = 20
RELEASES_API = "https://api.github.com/repos/Cape-PC/claude-connection-checker/releases/latest"
RELEASES_PAGE = "https://github.com/Cape-PC/claude-connection-checker/releases/latest"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "KaisenChecker"
V6_TIMEOUT = 4
V6_DEADLINE = 4  # IPv6 の確認を待つ最大の秒数
ECHO_HOSTS = {"v4": "api.ipify.org", "v6": "api6.ipify.org"}  # 通常の確認方法が使えないときだけ使う


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

class HttpStatusError(OSError):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read().decode("utf-8", errors="replace")


class _FamilyHTTPSConnection(http.client.HTTPSConnection):
    """IPv4 だけ、または IPv6 だけを使って接続する HTTPS 接続。"""

    def __init__(self, host, family, timeout):
        super().__init__(host, timeout=timeout)
        self._family = family

    def connect(self):
        infos = socket.getaddrinfo(self.host, self.port, self._family, socket.SOCK_STREAM)
        last, sock = None, None
        for fam, typ, proto, _, addr in infos:
            s = socket.socket(fam, typ, proto)
            s.settimeout(self.timeout)
            try:
                s.connect(addr)
                sock = s
                break
            except OSError as e:
                last = e
                s.close()
        if sock is None:
            raise last or OSError("no address")
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def http_get_family(host, path, family):
    timeout = TIMEOUT if family == socket.AF_INET else V6_TIMEOUT
    conn = _FamilyHTTPSConnection(host, family, timeout)
    try:
        conn.request("GET", path, headers={"User-Agent": USER_AGENT})
        res = conn.getresponse()
        body = res.read().decode("utf-8", errors="replace")
        if res.status != 200:
            raise HttpStatusError(res.status)
        return body
    finally:
        conn.close()


def fetch_trace_ip(host, family=socket.AF_INET):
    """Cloudflare の /cdn-cgi/trace から、そのサイトに見えている接続元 IP を取る。"""
    for line in http_get_family(host, "/cdn-cgi/trace", family).splitlines():
        if line.startswith("ip="):
            return line[3:].strip()
    raise ValueError("no ip in trace")


def fetch_echo_ip(family):
    """trace が使えないときの代わり。ドメインごとの違いは分からないので、参考値として扱う。"""
    key = "v4" if family == socket.AF_INET else "v6"
    return http_get_family(ECHO_HOSTS[key], "/?format=text", family).strip()


def _query_freeipapi(ip):
    data = json.loads(http_get(f"https://freeipapi.com/api/json/{ip}"))
    if not data.get("countryCode"):
        raise ValueError("empty")
    return {"country": data["countryCode"].upper(), "proxy": bool(data.get("isProxy"))}


def _query_ip2location(ip):
    data = json.loads(http_get(f"https://api.ip2location.io/?ip={ip}"))
    code = data.get("country_code")
    if not code or code == "-":
        raise ValueError("empty")
    return {"country": code.upper(), "proxy": bool(data.get("is_proxy"))}


def lookup_ip(ip):
    """2つの判定サービスに同時に聞いて、答えを比べる。片方だけでも答えが取れれば使う。"""
    results, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_query_freeipapi, ip), ex.submit(_query_ip2location, ip)]
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:  # noqa: BLE001
                errors.append(type(e).__name__)
    if not results:
        raise RuntimeError("lookup failed: " + ", ".join(errors))
    countries = {r["country"] for r in results}
    proxies = {r["proxy"] for r in results}
    return {
        "country": next(iter(countries)) if len(countries) == 1 else None,
        "proxy": all(r["proxy"] for r in results),
        "country_conflict": len(countries) > 1,
        "proxy_conflict": len(proxies) > 1,
    }


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


def domain_allowed(domain):
    return bool(DOMAIN_RE.match(domain)) and any(
        domain == s or domain.endswith("." + s) for s in ALLOWED_DOMAIN_SUFFIXES)


def clean_domains(items):
    out = []
    for d in items:
        if isinstance(d, str):
            d = d.strip().lower()
            if domain_allowed(d) and d not in out:
                out.append(d)
    return out[:MAX_DOMAINS]


def get_domains():
    """設定ファイルの URL があればそこからドメイン一覧を読む。許可した系列だけを使う。"""
    if REMOTE_CONFIG_URL.startswith("https://"):
        try:
            domains = clean_domains(json.loads(http_get(REMOTE_CONFIG_URL)).get("domains", []))
            if domains:
                save_json("domains.json", {"domains": domains})
                return domains
        except Exception:  # noqa: BLE001
            pass
        cached = clean_domains((load_json("domains.json", {}) or {}).get("domains", []))
        if cached:
            return cached
    return list(DEFAULT_DOMAINS)


def _version_tuple(text):
    return tuple(int(x) for x in re.findall(r"\d+", text)[:3])


def check_update():
    """新しい版があれば (版, ページの URL)。なければ None。"""
    data = json.loads(http_get(RELEASES_API))
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    if _version_tuple(tag) > _version_tuple(VERSION):
        return tag, RELEASES_PAGE
    return None


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
    if getattr(err, "code", None) in (403, 451):
        return True
    text = str(err).lower()
    return any(w in text for w in ("blocked", "10054", "connection reset", "forcibly closed", "refused"))


def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return f'"{pyw if os.path.exists(pyw) else exe}" "{os.path.abspath(__file__)}" --background'


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return "--background" in str(winreg.QueryValueEx(k, RUN_NAME)[0])
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- 判定

def classify(info, supported):
    if info is None or info.get("country") is None:
        return UNKNOWN
    if info["country"] not in supported:
        return OUTSIDE
    if info["proxy"]:
        return VPN
    return OK


def _call_with_deadline(fn, seconds):
    """fn を別スレッドで動かし、seconds 秒で答えが出なければ None にする（IPv6 が止まる環境で待たされないため）。"""
    box = {}

    def target():
        try:
            box["value"] = fn()
        except Exception as e:  # noqa: BLE001
            box["error"] = e

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(seconds)
    return box.get("value")


def check_host(host, supported_future, lookup, errors):
    """1つのドメインを、IPv4 と IPv6 の両方で調べる。IP はこの中だけで使って捨てる。"""
    infos = {}  # 経路 -> {"ip": ..., "estimated": bool}
    v6_box = {}
    v6_thread = threading.Thread(
        target=lambda: v6_box.update(ip=_call_with_deadline(lambda: fetch_trace_ip(host, socket.AF_INET6), V6_DEADLINE)),
        daemon=True)
    v6_thread.start()  # IPv6 は IPv4 と同時に調べ、遅ければ「なし」として扱う
    try:
        infos["v4"] = {"ip": fetch_trace_ip(host, socket.AF_INET), "estimated": False}
    except Exception as e:  # noqa: BLE001
        errors[host] = e
        try:  # 通常の方法が使えないときだけ、別の方法で調べる
            infos["v4"] = {"ip": fetch_echo_ip(socket.AF_INET), "estimated": True}
        except Exception:  # noqa: BLE001
            pass
    v6_thread.join(V6_DEADLINE + 1)
    if v6_box.get("ip"):
        infos["v6"] = {"ip": v6_box["ip"], "estimated": False}
    supported = supported_future.result()[0]
    per_family, countries, estimated, conflict = {}, set(), False, False
    for key, item in infos.items():
        try:
            info = lookup(item["ip"])
        except Exception as e:  # noqa: BLE001
            errors.setdefault(host, e)
            info = None
        status = classify(info, supported)
        per_family[key] = status
        if info:
            if info.get("country"):
                countries.add(info["country"])
            conflict = conflict or info["country_conflict"] or info["proxy_conflict"]
        estimated = estimated or item["estimated"]
    statuses = list(per_family.values())
    if not statuses:
        status = UNKNOWN
    elif OUTSIDE in statuses:
        status = OUTSIDE
    elif VPN in statuses:
        status = VPN
    elif UNKNOWN in statuses:
        status = UNKNOWN
    else:
        status = OK
    mixed = VPN in statuses and OK in statuses
    note = "mixed" if mixed else "estimated" if estimated else "conflict" if conflict else None
    return {"domain": host, "status": status, "countries": sorted(countries), "note": note,
            "families": per_family}


def run_check(progress=None, on_domains=None):
    """判定をすべて行い、IP を含まない結果だけを返す。progress(row) は、ドメインごとの結果が出るたびに呼ぶ。"""
    domains = get_domains()
    if on_domains:
        on_domains(domains)
    hosts = domains + [BASELINE_DOMAIN]
    errors = {}
    cache, lock = {}, threading.Lock()
    lookup_pool = concurrent.futures.ThreadPoolExecutor(max_workers=6)

    def lookup(ip):  # 同じ IP は 1 回だけ問い合わせる
        with lock:
            fut = cache.get(ip)
            if fut is None:
                fut = cache[ip] = lookup_pool.submit(lookup_ip, ip)
        return fut.result()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts) + 2) as ex:
        f_countries = ex.submit(get_supported_countries)
        f_vpn = ex.submit(detect_vpn_software)
        futures = {ex.submit(check_host, h, f_countries, lookup, errors): h for h in hosts}
        rows = {}
        for f in concurrent.futures.as_completed(futures):
            h = futures[f]
            try:
                row = f.result()
            except Exception as e:  # noqa: BLE001
                errors[h] = e
                row = {"domain": h, "status": UNKNOWN, "countries": [], "note": None, "families": {}}
            rows[h] = row
            if progress:
                progress(row)
        _, country_src, country_date = f_countries.result()
        vpn_software = f_vpn.result()
    lookup_pool.shutdown(wait=False)
    cache.clear()  # IP はここで捨てる

    claude_rows = [rows[h] for h in domains]
    statuses = [r["status"] for r in claude_rows]
    checked = [s for s in statuses if s != UNKNOWN]
    notes = [r["note"] for r in claude_rows]

    if OUTSIDE in statuses or (checked and all(s == VPN for s in checked)):
        level = DANGER
    elif VPN in statuses or UNKNOWN in statuses or any(notes):
        level = CAUTION
    else:
        level = SAFE

    return {
        "time": datetime.datetime.now(),
        "level": level,
        "rows": claude_rows,
        "baseline": rows[BASELINE_DOMAIN],
        "vpn_software": vpn_software,
        "proxy_setting": windows_proxy_enabled(),
        "blocked_hint": any(looks_blocked(e) for e in errors.values()),
        "all_failed": not checked,
        "country_src": country_src,
        "country_date": country_date,
        "prev": None,
    }


def country_label(code, lang):
    if not code:
        return "—"
    return COUNTRY_NAMES[lang].get(code, code)


def row_values(row, lang):
    t = TEXT[lang]
    country = " / ".join(country_label(c, lang) for c in row["countries"]) or "—"
    status = t[row["status"]]
    if row.get("note"):
        status += f"（{t['note_' + row['note']]}）" if lang == "ja" else f" ({t['note_' + row['note']]})"
    return country, status


def load_last():
    return load_json("last.json", None)


def save_last(result):
    save_json("last.json", {
        "time": result["time"].strftime("%Y-%m-%d %H:%M"),
        "level": result["level"],
        "rows": {r["domain"]: r["status"] for r in result["rows"]},
    })


def build_explanation(result, lang):
    """結論の見出し・理由・やることを作る。"""
    t = TEXT[lang]
    level, rows = result["level"], result["rows"]
    vpn_rows = [r for r in rows if r["status"] == VPN]
    outside_rows = [r for r in rows if r["status"] == OUTSIDE]
    unknown_rows = [r for r in rows if r["status"] == UNKNOWN]
    mixed = [r for r in rows if r.get("note") == "mixed"]
    estimated = [r for r in rows if r.get("note") == "estimated"]
    conflict = [r for r in rows if r.get("note") == "conflict"]
    countries = sorted({c for r in rows for c in r["countries"]})
    software = result["vpn_software"]
    names = t["sep"].join(n for n, _ in software)

    headline = t["head_failed"] if result["all_failed"] else t["head_" + level]

    reasons = []
    prev = result.get("prev")
    if prev and prev.get("level") in (SAFE, CAUTION, DANGER) and prev["level"] != level:
        reasons.append(t["r_changed"].format(t=prev.get("time", "?"), prev=t[prev["level"]], now=t[level]))
        changed = [r["domain"] for r in rows if prev.get("rows", {}).get(r["domain"]) not in (None, r["status"])]
        if changed:
            reasons.append(t["r_changed_domains"].format(d=t["sep"].join(changed)))
    if result["all_failed"]:
        reasons.append(t["r_failed"])
    else:
        reasons.append(t["r_country"].format(c=t["sep"].join(country_label(c, lang) for c in countries)))
    if outside_rows:
        reasons.append(t["r_outside"])
    if vpn_rows:
        reasons.append(t["r_vpn"].format(n=len(vpn_rows)))
    if mixed:
        reasons.append(t["r_mixed"].format(n=len(mixed)))
    if not vpn_rows and not outside_rows and not unknown_rows and not (estimated or conflict):
        reasons.append(t["r_allok"].format(n=len(rows)))
    if unknown_rows and not result["all_failed"]:
        reasons.append(t["r_unknown"].format(n=len(unknown_rows)))
    if estimated:
        reasons.append(t["r_estimated"].format(n=len(estimated)))
    if conflict:
        reasons.append(t["r_conflict"].format(n=len(conflict)))
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
                actions.append(guides[name] if name in guides else guides["_" + kind].format(name=name))
        else:
            actions.append(t["a_generic"])
        actions.append(t["a_off"])
    if mixed:
        actions.append(t["a_mixed"])
    if unknown_rows:
        actions.append(t["a_retry"])
    if conflict or estimated:
        actions.append(t["a_conflict"])
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
        "checking": ("#2f5bd3", "#e9eefc"), UNKNOWN: "#5b6475", "link": "#2f5bd3",
        "primary": ("#2f5bd3", "#2449ad", "#1b3888", "#ffffff"),
        "secondary": ("#4b5567", "#3a4252", "#2b313d", "#ffffff"),
        "plain": ("#e3e6ec", "#d3d8e0", "#c1c7d2", "#1d2330"),
        "disabled": "#9aa3b5",
    },
    "dark": {
        "bg": "#12151c", "fg": "#e6e9ef", "muted": "#9aa3b5", "line": "#2a303c", "panel": "#1a1f29",
        "head_bg": "#222836",
        SAFE: ("#6fd39c", "#15301f"), CAUTION: ("#ffb35c", "#3a2614"), DANGER: ("#ff8a80", "#3b1714"),
        "checking": ("#9db5ff", "#1c2540"), UNKNOWN: "#9aa3b5", "link": "#9db5ff",
        "primary": ("#4a74e8", "#5f86f0", "#3a5fc4", "#ffffff"),
        "secondary": ("#3a4252", "#4b5567", "#2b313d", "#e6e9ef"),
        "plain": ("#2a303c", "#363d4b", "#1f242e", "#e6e9ef"),
        "disabled": "#5b6475",
    },
}
FONT = "Yu Gothic UI"
FONT_SPECS = {"title": (16, "bold"), "body": (10, "normal"), "bold": (10, "bold"),
              "small": (9, "normal"), "banner": (14, "bold"), "heading": (11, "bold")}
SCALE_MIN, SCALE_MAX, SCALE_STEP = 0.8, 1.6, 0.1


class HoverButton(tk.Button):
    """ホバーで色が変わり、押すと沈むボタン。"""

    def __init__(self, master, colors, disabled_fg, font, **kw):
        bg, hover, active, fg = colors
        super().__init__(master, bg=bg, fg=fg, activebackground=active, activeforeground=fg,
                         relief="flat", bd=0, cursor="hand2", padx=14, pady=7,
                         font=font, disabledforeground=disabled_fg, **kw)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self["state"] != "disabled" and self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<ButtonPress-1>", lambda e: self["state"] != "disabled" and self.config(relief="sunken"))
        self.bind("<ButtonRelease-1>", lambda e: self.config(relief="flat"))


class App:
    def __init__(self, root, background=False):
        self.root = root
        self.background = background
        self.result = None
        self.checking = False
        self.attempts = 0
        self.update_info = None
        self.settings = load_json("settings.json", {})
        self.lang = self.settings.get("lang", "ja")
        if self.lang not in TEXT:
            self.lang = "ja"
        try:
            self.scale = min(SCALE_MAX, max(SCALE_MIN, float(self.settings.get("font_scale", 1.0))))
        except (TypeError, ValueError):
            self.scale = 1.0
        self.mode = "dark" if windows_dark_mode() else "light"
        self.c = PALETTES[self.mode]
        c = self.c
        self.fonts = {n: tkfont.Font(family=FONT, size=s, weight=w) for n, (s, w) in FONT_SPECS.items()}

        root.configure(bg=c["bg"])
        root.geometry("800x900")
        root.minsize(640, 700)
        if background:
            root.withdraw()
        self._dark_title_bar()

        outer = tk.Frame(root, bg=c["bg"], padx=20, pady=16)
        outer.pack(fill="both", expand=True)

        top = tk.Frame(outer, bg=c["bg"])
        top.pack(fill="x")
        self.title = tk.Label(top, font=self.fonts["title"], bg=c["bg"], fg=c["fg"])
        self.title.pack(side="left")
        self.btn_lang = HoverButton(top, c["plain"], c["disabled"], self.fonts["bold"], command=self.toggle_lang)
        self.btn_lang.pack(side="right")
        self.subtitle = tk.Label(outer, font=self.fonts["small"], bg=c["bg"], fg=c["muted"])
        self.subtitle.pack(anchor="w", pady=(0, 8))

        self.update_bar = tk.Frame(outer, bg=c["bg"])
        self.update_label = tk.Label(self.update_bar, font=self.fonts["bold"], bg=c["bg"], fg=c[CAUTION][0])
        self.update_label.pack(side="left")
        self.btn_update = HoverButton(self.update_bar, c["plain"], c["disabled"], self.fonts["bold"],
                                      command=self.open_update)
        self.btn_update.pack(side="left", padx=10)

        self.banner = tk.Frame(outer, padx=14, pady=10, highlightthickness=1)
        self.banner.pack(fill="x")
        self.headline = tk.Label(self.banner, font=self.fonts["banner"], anchor="w", justify="left")
        self.headline.pack(fill="x")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.tree = ttk.Treeview(outer, columns=("domain", "country", "status"), show="headings",
                                 height=len(DEFAULT_DOMAINS) + 1, style="K.Treeview", selectmode="none")
        for col, width in (("domain", 210), ("country", 130), ("status", 330)):
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure(OK, foreground=c[SAFE][0])
        self.tree.tag_configure(VPN, foreground=c[CAUTION][0])
        self.tree.tag_configure(OUTSIDE, foreground=c[DANGER][0])
        self.tree.tag_configure(UNKNOWN, foreground=c[UNKNOWN])
        self.tree.tag_configure("base", foreground=c["muted"])
        self.tree.tag_configure("pending", foreground=c["muted"])
        self.tree.pack(fill="x", pady=(14, 4))
        self.source = tk.Label(outer, font=self.fonts["small"], bg=c["bg"], fg=c["muted"], anchor="w")
        self.source.pack(fill="x", pady=(0, 8))

        self.text = tk.Text(outer, font=self.fonts["body"], wrap="char", bg=c["panel"], fg=c["fg"],
                            relief="flat", padx=12, pady=10, highlightthickness=1,
                            highlightbackground=c["line"], height=10, insertbackground=c["fg"])
        self.text.tag_configure("h", font=self.fonts["heading"], spacing1=4, spacing3=4)
        self.text.tag_configure("p", lmargin1=8, lmargin2=22, spacing3=3)
        self.text.pack(fill="both", expand=True)

        self.notice = tk.Label(outer, font=self.fonts["small"], bg=c["bg"], fg=c["muted"],
                               justify="left", anchor="w")
        self.notice.pack(fill="x", pady=(8, 0))
        self.shortcuts = tk.Label(outer, font=self.fonts["small"], bg=c["bg"], fg=c["muted"],
                                  justify="left", anchor="w")
        self.shortcuts.pack(fill="x", pady=(2, 0))
        outer.bind("<Configure>", lambda e: (self.notice.config(wraplength=max(300, e.width - 40)),
                                             self.shortcuts.config(wraplength=max(300, e.width - 40))))

        self.var_auto = tk.BooleanVar(value=autostart_enabled())
        self.var_update = tk.BooleanVar(value=bool(self.settings.get("update_check", False)))
        opts = tk.Frame(outer, bg=c["bg"])
        opts.pack(fill="x", pady=(8, 0))
        cb_kw = dict(bg=c["bg"], fg=c["fg"], activebackground=c["bg"], activeforeground=c["fg"],
                     selectcolor=c["panel"], font=self.fonts["small"], anchor="w", cursor="hand2",
                     highlightthickness=0, bd=0)
        self.cb_auto = tk.Checkbutton(opts, variable=self.var_auto, command=self.on_autostart, **cb_kw)
        self.cb_auto.pack(fill="x")
        self.cb_update = tk.Checkbutton(opts, variable=self.var_update, command=self.on_update_check, **cb_kw)
        self.cb_update.pack(fill="x")

        bar = tk.Frame(outer, bg=c["bg"])
        bar.pack(fill="x", pady=(10, 0))
        self.btn_check = HoverButton(bar, c["primary"], c["disabled"], self.fonts["bold"], command=self.start_check)
        self.btn_check.pack(side="left")
        self.btn_copy = HoverButton(bar, c["secondary"], c["disabled"], self.fonts["bold"], command=self.copy_domains)
        self.btn_copy.pack(side="left", padx=6)
        self.btn_folder = HoverButton(bar, c["plain"], c["disabled"], self.fonts["bold"], command=self.open_folder)
        self.btn_folder.pack(side="left")
        self.btn_manual = HoverButton(bar, c["plain"], c["disabled"], self.fonts["bold"], command=self.open_manual)
        self.btn_manual.pack(side="left", padx=6)
        self.btn_close = HoverButton(bar, c["plain"], c["disabled"], self.fonts["bold"], command=root.destroy)
        self.btn_close.pack(side="right")
        self.status = tk.Label(outer, font=self.fonts["small"], bg=c["bg"], fg=c["muted"], anchor="w")
        self.status.pack(fill="x", pady=(6, 0))

        root.bind("<F5>", lambda e: self.start_check())
        root.bind("<Escape>", lambda e: root.destroy())
        root.bind("<Control-l>", lambda e: self.toggle_lang())
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            root.bind(seq, lambda e: self.change_scale(SCALE_STEP))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            root.bind(seq, lambda e: self.change_scale(-SCALE_STEP))
        root.bind("<Control-0>", lambda e: self.change_scale(None))

        self.apply_scale()
        self.apply_texts()
        self.start_check()
        if self.var_update.get() and not background:
            threading.Thread(target=self._update_worker, daemon=True).start()

    # --- 見た目 ---
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

    def apply_scale(self):
        for name, (size, _) in FONT_SPECS.items():
            self.fonts[name].configure(size=max(7, round(size * self.scale)))
        c = self.c
        self.style.configure("K.Treeview", font=self.fonts["body"], rowheight=max(20, round(26 * self.scale)),
                             background=c["panel"], fieldbackground=c["panel"], foreground=c["fg"],
                             bordercolor=c["line"], lightcolor=c["line"], darkcolor=c["line"])
        self.style.configure("K.Treeview.Heading", font=self.fonts["bold"], background=c["head_bg"],
                             foreground=c["fg"], bordercolor=c["line"], lightcolor=c["head_bg"],
                             darkcolor=c["head_bg"], relief="flat")
        self.style.map("K.Treeview.Heading", background=[("active", c["head_bg"])])

    def change_scale(self, step):
        self.scale = 1.0 if step is None else min(SCALE_MAX, max(SCALE_MIN, round(self.scale + step, 2)))
        self.settings["font_scale"] = self.scale
        save_json("settings.json", self.settings)
        self.apply_scale()

    def t(self, key):
        return TEXT[self.lang][key]

    def apply_texts(self):
        self.root.title(f"{self.t('app')} {VERSION}")
        self.title.config(text=self.t("title"))
        self.subtitle.config(text=self.t("subtitle"))
        self.notice.config(text=self.t("notice"))
        self.shortcuts.config(text=self.t("shortcuts"))
        self.text.config(wrap="char" if self.lang == "ja" else "word")  # 英語は単語の途中で折り返さない
        self.cb_auto.config(text=self.t("opt_autostart"))
        self.cb_update.config(text=self.t("opt_update"))
        for col in ("domain", "country", "status"):
            self.tree.heading(col, text=self.t("col_" + col), anchor="w")
        for btn, key in ((self.btn_check, "btn_check"), (self.btn_copy, "btn_copy"),
                         (self.btn_folder, "btn_folder"), (self.btn_manual, "btn_manual"),
                         (self.btn_lang, "btn_lang"), (self.btn_close, "btn_close"),
                         (self.btn_update, "btn_update")):
            btn.config(text=self.t(key))
        if self.update_info:
            self.update_label.config(text=self.t("update_available").format(v=self.update_info[0]))

    def toggle_lang(self):
        self.lang = "en" if self.lang == "ja" else "ja"
        self.settings["lang"] = self.lang
        save_json("settings.json", self.settings)
        self.apply_texts()
        if self.result:
            self.render(self.result)
        elif self.checking:
            self.set_banner("checking", self.t("checking"))

    def set_banner(self, key, text):
        fg, bg = self.c[key]
        self.banner.config(bg=bg, highlightbackground=fg, highlightcolor=fg)
        self.headline.config(text=text, bg=bg, fg=fg)

    # --- 設定（起動時の自動チェック・新しい版の確認）---
    def on_autostart(self):
        want = self.var_auto.get()
        try:
            set_autostart(want)
        except OSError:
            self.var_auto.set(not want)
            self.status.config(text=self.t("autostart_failed"))
            return
        if want and not getattr(sys, "frozen", False):
            self.status.config(text=self.t("autostart_unavailable"))

    def on_update_check(self):
        self.settings["update_check"] = bool(self.var_update.get())
        save_json("settings.json", self.settings)
        if self.var_update.get():
            threading.Thread(target=self._update_worker, daemon=True).start()
        else:
            self.update_info = None
            self.update_bar.pack_forget()

    def _update_worker(self):
        try:
            info = check_update()
        except Exception:  # noqa: BLE001
            info = None
        self.root.after(0, self._show_update, info)

    def _show_update(self, info):
        if not info or not self.var_update.get():
            return
        self.update_info = info
        self.update_label.config(text=self.t("update_available").format(v=info[0]))
        self.update_bar.pack(fill="x", pady=(0, 8), before=self.banner)

    def open_update(self):
        if self.update_info:
            webbrowser.open(self.update_info[1])

    # --- 判定 ---
    def start_check(self):
        if self.checking:
            return
        self.checking = True
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
            result = run_check(
                progress=lambda row: self.root.after(0, self._progress_row, row),
                on_domains=lambda ds: self.root.after(0, self._placeholder_rows, ds),
            )
            err = None
        except Exception as e:  # noqa: BLE001
            result, err = None, e
        self.root.after(0, self.show_result, result, err)

    def _placeholder_rows(self, domains):
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(height=len(domains) + 1)
        for d in domains + [BASELINE_DOMAIN]:
            name = self.t("baseline") if d == BASELINE_DOMAIN else d
            self.tree.insert("", "end", iid=d, values=(name, "—", self.t("checking_row")),
                             tags=("base" if d == BASELINE_DOMAIN else "pending",))

    def _progress_row(self, row):
        iid = row["domain"]
        if not self.tree.exists(iid):
            return
        country, status = row_values(row, self.lang)
        name = self.t("baseline") if iid == BASELINE_DOMAIN else iid
        self.tree.item(iid, values=(name, country, status),
                       tags=("base" if iid == BASELINE_DOMAIN else row["status"],))

    def show_result(self, result, err):
        self.checking = False
        self.btn_check.config(state="normal")
        if err is not None:
            self.set_banner(CAUTION, self.t("check_failed"))
            self.status.config(text=self.t("error").format(e=type(err).__name__))
            self._after_background(None)
            return
        result["prev"] = load_last()
        self.result = result
        self.render(result)
        note = save_history(result, self.lang)
        save_last(result)
        self.status.config(text=note or self.t("saved").format(t=f"{result['time']:%Y-%m-%d %H:%M}"))
        self._after_background(result)

    def _after_background(self, result):
        """起動時の自動チェックのとき：安全なら何も見せずに終わる。通信できていないときは少し待って調べ直す。"""
        if not self.background:
            return
        failed = result is None or result["all_failed"]
        if failed and self.attempts < 3:
            self.attempts += 1
            self.root.after(20000, self.start_check)
            return
        if result is not None and result["level"] == SAFE:
            self.root.destroy()
            return
        self.root.deiconify()
        self.root.lift()
        self.background = False

    def render(self, result):
        headline, reasons, actions = build_explanation(result, self.lang)
        self.set_banner(CAUTION if result["all_failed"] else result["level"], headline)

        self.tree.delete(*self.tree.get_children())
        self.tree.configure(height=len(result["rows"]) + 1)
        for r in result["rows"]:
            country, status = row_values(r, self.lang)
            self.tree.insert("", "end", iid=r["domain"], values=(r["domain"], country, status), tags=(r["status"],))
        b = result["baseline"]
        country, status = row_values(b, self.lang)
        self.tree.insert("", "end", iid=BASELINE_DOMAIN, values=(self.t("baseline"), country, status), tags=("base",))
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
        if not domains:
            return
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
    App(root, background="--background" in sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()
