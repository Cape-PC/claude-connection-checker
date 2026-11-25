"""回線チェッカーの自動テスト。標準ライブラリの unittest だけで動く（Windows が必要）。

    python -m unittest discover -s tests -v

ネットワークには出ない。通信の部分は、すべて疑似データに差し替えてある。
"""

import gc
import os
import socket
import sys
import traceback
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import kaisen_checker as k  # noqa: E402

SUPPORTED = {"JP", "US", "GB"}
HOME = {"country": "JP", "proxy": False, "country_conflict": False, "proxy_conflict": False}
VPN_INFO = {"country": "JP", "proxy": True, "country_conflict": False, "proxy_conflict": False}
HK = {"country": "HK", "proxy": True, "country_conflict": False, "proxy_conflict": False}
NONE_GROUP = {"status": "none", "vpn": 0, "direct": 0, "local": 0}
DIRECT_GROUP = {"status": "direct", "vpn": 0, "direct": 3, "local": 0}
VPN_GROUP = {"status": "vpn", "vpn": 2, "direct": 0, "local": 0}


class TextTableTests(unittest.TestCase):
    def test_ja_and_en_have_same_keys(self):
        ja, en = set(k.TEXT["ja"]), set(k.TEXT["en"])
        self.assertEqual(ja - en, set(), "英語にない文言")
        self.assertEqual(en - ja, set(), "日本語にない文言")

    def test_glossary_has_both_languages(self):
        self.assertEqual(len(k.FR_GLOSSARY["ja"]), len(k.FR_GLOSSARY["en"]))

    def test_country_codes_are_two_letters(self):
        for name, code in k.COUNTRY_CODES.items():
            self.assertRegex(code, r"^[A-Z]{2}$", name)


class DomainTests(unittest.TestCase):
    def test_allowed(self):
        for d in ("claude.ai", "api.anthropic.com", "a.b.claude.com", "claude.com"):
            self.assertTrue(k.domain_allowed(d), d)

    def test_not_allowed(self):
        for d in ("evil.com", "claude.ai.evil.com", "notclaude.ai", "http://x.claude.ai", "claude.ai/path", "", "claude.ai."):
            self.assertFalse(k.domain_allowed(d), d)

    def test_clean_domains_filters_and_dedupes(self):
        got = k.clean_domains(["Claude.ai ", "evil.com", "claude.ai", "api.anthropic.com", 5, None])
        self.assertEqual(got, ["claude.ai", "api.anthropic.com"])

    def test_clean_domains_limit(self):
        many = [f"s{i}.claude.ai" for i in range(50)]
        self.assertEqual(len(k.clean_domains(many)), k.MAX_DOMAINS)

    def test_get_domains_ignores_foreign_names_from_remote(self):
        body = '{"domains": ["evil.com", "claude.ai", "x.anthropic.com"]}'
        with mock.patch.object(k, "http_get", return_value=body), mock.patch.object(k, "save_json"):
            self.assertEqual(k.get_domains(), ["claude.ai", "x.anthropic.com"])

    def test_get_domains_falls_back_to_builtin(self):
        with mock.patch.object(k, "http_get", side_effect=OSError("offline")), \
                mock.patch.object(k, "load_json", return_value={}):
            self.assertEqual(k.get_domains(), k.DEFAULT_DOMAINS)


class ClassifyTests(unittest.TestCase):
    def test_ok_vpn_outside_unknown(self):
        self.assertEqual(k.classify(HOME, SUPPORTED), k.OK)
        self.assertEqual(k.classify(VPN_INFO, SUPPORTED), k.VPN)
        self.assertEqual(k.classify(HK, SUPPORTED), k.OUTSIDE)
        self.assertEqual(k.classify(None, SUPPORTED), k.UNKNOWN)
        self.assertEqual(k.classify({"country": None, "proxy": False}, SUPPORTED), k.UNKNOWN)


class CountryPageTests(unittest.TestCase):
    @staticmethod
    def _page(names):
        items = "".join(f"<li>{n}</li>" for n in names)
        return f"<p>Countries and regions where we currently offer access to our products and services:</p><ul>{items}</ul>"

    def test_parses_known_names(self):
        names = list(k.COUNTRY_CODES)[:150]
        codes = k.parse_supported_countries(self._page(names))
        self.assertEqual(len(codes), 150)

    def test_ukraine_exception_is_stripped(self):
        names = list(k.COUNTRY_CODES)[:150] + ["Ukraine (except Crimea, Donetsk)"]
        self.assertIn("UA", k.parse_supported_countries(self._page(names)))

    def test_unknown_name_returns_none(self):
        names = list(k.COUNTRY_CODES)[:150] + ["Atlantis"]
        self.assertIsNone(k.parse_supported_countries(self._page(names)))

    def test_too_few_returns_none(self):
        self.assertIsNone(k.parse_supported_countries(self._page(["Japan", "Canada"])))

    def test_no_marker_returns_none(self):
        self.assertIsNone(k.parse_supported_countries("<ul><li>Japan</li></ul>"))


class LookupMergeTests(unittest.TestCase):
    def test_both_agree(self):
        with mock.patch.object(k, "_query_freeipapi", return_value={"country": "JP", "proxy": True}), \
                mock.patch.object(k, "_query_ip2location", return_value={"country": "JP", "proxy": True}):
            r = k.lookup_ip("x")
        self.assertEqual((r["country"], r["proxy"], r["country_conflict"], r["proxy_conflict"]), ("JP", True, False, False))

    def test_proxy_disagreement_is_not_proxy_but_flagged(self):
        with mock.patch.object(k, "_query_freeipapi", return_value={"country": "JP", "proxy": True}), \
                mock.patch.object(k, "_query_ip2location", return_value={"country": "JP", "proxy": False}):
            r = k.lookup_ip("x")
        self.assertFalse(r["proxy"])
        self.assertTrue(r["proxy_conflict"])

    def test_country_disagreement_has_no_country(self):
        with mock.patch.object(k, "_query_freeipapi", return_value={"country": "JP", "proxy": False}), \
                mock.patch.object(k, "_query_ip2location", return_value={"country": "US", "proxy": False}):
            r = k.lookup_ip("x")
        self.assertIsNone(r["country"])
        self.assertTrue(r["country_conflict"])

    def test_one_service_down_uses_the_other(self):
        with mock.patch.object(k, "_query_freeipapi", side_effect=OSError("down")), \
                mock.patch.object(k, "_query_ip2location", return_value={"country": "JP", "proxy": False}):
            self.assertEqual(k.lookup_ip("x")["country"], "JP")

    def test_both_down_raises(self):
        with mock.patch.object(k, "_query_freeipapi", side_effect=OSError), \
                mock.patch.object(k, "_query_ip2location", side_effect=OSError):
            with self.assertRaises(RuntimeError):
                k.lookup_ip("x")


class AdapterTests(unittest.TestCase):
    def test_vpn_adapters(self):
        for name, desc in (("AdGuard VPN", "Wintun Userspace Tunnel"), ("Nord", "NordLynx Tunnel"),
                           ("Proton", "WireGuard Tunnel"), ("OpenVPN", "TAP-Windows Adapter V9")):
            self.assertTrue(k.adapter_is_vpn({"name": name, "desc": desc, "hw": False}), name)

    def test_not_vpn_adapters(self):
        for name, desc, hw in (("イーサネット", "Realtek Gaming 2.5GbE", True), ("Wi-Fi", "Intel Wi-Fi 6", True),
                               ("vEthernet (WSL)", "Hyper-V Virtual Ethernet Adapter", False),
                               ("x", "Microsoft IP-HTTPS Platform Interface", False),
                               ("x", "WAN Miniport (L2TP)", False), ("x", "Teredo Tunneling Pseudo-Interface", False)):
            self.assertFalse(k.adapter_is_vpn({"name": name, "desc": desc, "hw": hw}), desc)

    def test_unknown_adapter(self):
        self.assertIsNone(k.adapter_is_vpn(None))


class AppTrafficTests(unittest.TestCase):
    ADS = [{"idx": 1, "name": "Ethernet", "desc": "Realtek", "hw": True},
           {"idx": 2, "name": "AdGuard VPN", "desc": "Wintun Userspace Tunnel", "hw": False},
           {"idx": 3, "name": "vEthernet (WSL)", "desc": "Hyper-V Virtual Ethernet Adapter", "hw": False}]
    IPS = [{"ip": "192.168.1.5", "idx": 1}, {"ip": "10.66.0.2", "idx": 2}, {"ip": "172.20.0.1", "idx": 3},
           {"ip": "fe80::1%4", "idx": 1}]
    PROCS = [{"pid": 10, "name": "claude.exe", "cmd": None}, {"pid": 11, "name": "node.exe", "cmd": "node /x/claude-code/cli.js"},
             {"pid": 12, "name": "node.exe", "cmd": "node server.js"}, {"pid": 13, "name": "chrome.exe", "cmd": None},
             {"pid": 14, "name": "notepad.exe", "cmd": None}]
    G = "160.79.104.10"

    def run_case(self, conns):
        data = {"ads": self.ADS, "ips": self.IPS, "procs": self.PROCS, "conns": conns}
        return k.analyze_app_traffic(data, {self.G})

    def test_direct(self):
        r = self.run_case([{"la": "192.168.1.5", "ra": self.G, "pid": 10}, {"la": "192.168.1.5", "ra": "1.1.1.1", "pid": 11}])
        self.assertEqual((r["app"]["status"], r["app"]["direct"]), ("direct", 2))

    def test_vpn(self):
        self.assertEqual(self.run_case([{"la": "10.66.0.2", "ra": self.G, "pid": 10}])["app"]["status"], "vpn")

    def test_mixed(self):
        r = self.run_case([{"la": "10.66.0.2", "ra": self.G, "pid": 10}, {"la": "192.168.1.5", "ra": self.G, "pid": 11}])
        self.assertEqual(r["app"]["status"], "mixed")

    def test_unrelated_processes_ignored(self):
        r = self.run_case([{"la": "10.66.0.2", "ra": self.G, "pid": 12}, {"la": "10.66.0.2", "ra": self.G, "pid": 14}])
        self.assertEqual(r["app"]["status"], "none")

    def test_browser_counts_only_claude_addresses(self):
        r = self.run_case([{"la": "10.66.0.2", "ra": self.G, "pid": 13}, {"la": "10.66.0.2", "ra": "8.8.8.8", "pid": 13}])
        self.assertEqual((r["browser"]["status"], r["browser"]["vpn"]), ("vpn", 1))

    def test_lan_is_ignored(self):
        r = self.run_case([{"la": "192.168.1.5", "ra": "192.168.1.1", "pid": 10}])
        self.assertEqual(r["app"]["status"], "none")

    def test_loopback_only_means_proxied(self):
        r = self.run_case([{"la": "127.0.0.1", "ra": "127.0.0.1", "pid": 10}])
        self.assertEqual(r["app"]["status"], "proxied")

    def test_wsl_adapter_is_not_vpn(self):
        self.assertEqual(self.run_case([{"la": "172.20.0.1", "ra": self.G, "pid": 10}])["app"]["status"], "direct")

    def test_unknown_local_address_not_counted(self):
        self.assertEqual(self.run_case([{"la": "203.0.113.9", "ra": self.G, "pid": 10}])["app"]["status"], "none")

    def test_diagnose_counts_have_no_addresses(self):
        data = {"ads": self.ADS, "ips": self.IPS, "procs": self.PROCS,
                "conns": [{"la": "10.66.0.2", "ra": self.G, "pid": 10}, {"la": "127.0.0.1", "ra": "127.0.0.1", "pid": 10}]}
        text = str(k.connection_stage_counts(data, {self.G}))
        self.assertNotIn(self.G, text)
        self.assertNotIn("10.66", text)


def fake_run_check(trace_map, apps, *, vpn_software=(), countries=SUPPORTED, domains=("claude.ai", "api.anthropic.com", "claude.com")):
    """通信を疑似データにして run_check を動かす。trace_map: ドメイン → ("home"|"vpn"|"hk" など)"""
    info = {"home": HOME, "vpn": VPN_INFO, "hk": HK}

    def trace(host, fam=socket.AF_INET):
        if fam == socket.AF_INET6:
            raise OSError("no ipv6")
        return trace_map.get(host, trace_map.get("*", "home"))

    patches = [
        mock.patch.object(k, "get_domains", return_value=list(domains)),
        mock.patch.object(k, "fetch_trace_ip", side_effect=trace),
        mock.patch.object(k, "lookup_ip", side_effect=lambda ip: info[ip]),
        mock.patch.object(k, "get_supported_countries", return_value=(countries, "builtin", "2026-01-01")),
        mock.patch.object(k, "detect_vpn_software", return_value=list(vpn_software)),
        mock.patch.object(k, "check_app_traffic", return_value=apps),
        mock.patch.object(k, "windows_proxy_enabled", return_value=False),
    ]
    for p in patches:
        p.start()
    try:
        return k.run_check()
    finally:
        mock.patch.stopall()


class RunCheckTests(unittest.TestCase):
    def test_safe(self):
        r = fake_run_check({"*": "home"}, {"app": DIRECT_GROUP, "browser": NONE_GROUP})
        self.assertEqual(r["level"], k.SAFE)

    def test_some_vpn_is_caution(self):
        r = fake_run_check({"claude.com": "vpn"}, {"app": NONE_GROUP, "browser": NONE_GROUP})
        self.assertEqual(r["level"], k.CAUTION)

    def test_all_vpn_is_danger(self):
        r = fake_run_check({"*": "vpn"}, {"app": NONE_GROUP, "browser": NONE_GROUP})
        self.assertEqual(r["level"], k.DANGER)

    def test_outside_country_is_danger(self):
        r = fake_run_check({"*": "hk"}, {"app": NONE_GROUP, "browser": NONE_GROUP})
        self.assertEqual(r["level"], k.DANGER)

    def test_checker_on_vpn_but_app_direct_is_downgraded_to_caution(self):
        r = fake_run_check({"*": "vpn"}, {"app": DIRECT_GROUP, "browser": NONE_GROUP})
        self.assertEqual((r["level"], r["app_adjust"]), (k.CAUTION, "downgraded"))

    def test_outside_is_never_downgraded(self):
        r = fake_run_check({"*": "hk"}, {"app": DIRECT_GROUP, "browser": NONE_GROUP})
        self.assertEqual(r["level"], k.DANGER)

    def test_app_on_vpn_makes_safe_into_caution(self):
        r = fake_run_check({"*": "home"}, {"app": VPN_GROUP, "browser": NONE_GROUP})
        self.assertEqual(r["level"], k.CAUTION)

    def test_app_check_failure_does_not_change_level(self):
        r = fake_run_check({"*": "home"}, None)
        self.assertEqual(r["level"], k.SAFE)

    def test_no_ip_in_result(self):
        r = fake_run_check({"claude.com": "vpn"}, {"app": NONE_GROUP, "browser": NONE_GROUP})
        self.assertNotIn("160.", repr(r))

    def test_all_failed(self):
        with mock.patch.object(k, "get_domains", return_value=["claude.ai"]), \
                mock.patch.object(k, "fetch_trace_ip", side_effect=OSError("blocked")), \
                mock.patch.object(k, "fetch_echo_ip", side_effect=OSError("blocked")), \
                mock.patch.object(k, "get_supported_countries", return_value=(SUPPORTED, "builtin", "x")), \
                mock.patch.object(k, "detect_vpn_software", return_value=[]), \
                mock.patch.object(k, "check_app_traffic", return_value=None), \
                mock.patch.object(k, "windows_proxy_enabled", return_value=False):
            r = k.run_check()
        self.assertTrue(r["all_failed"])
        self.assertEqual(r["level"], k.CAUTION)

    def test_echo_fallback_marks_estimate(self):
        def trace(host, fam=socket.AF_INET):
            raise OSError("trace blocked")
        with mock.patch.object(k, "get_domains", return_value=["claude.ai"]), \
                mock.patch.object(k, "fetch_trace_ip", side_effect=trace), \
                mock.patch.object(k, "fetch_echo_ip", return_value="home"), \
                mock.patch.object(k, "lookup_ip", side_effect=lambda ip: HOME), \
                mock.patch.object(k, "get_supported_countries", return_value=(SUPPORTED, "builtin", "x")), \
                mock.patch.object(k, "detect_vpn_software", return_value=[]), \
                mock.patch.object(k, "check_app_traffic", return_value=None), \
                mock.patch.object(k, "windows_proxy_enabled", return_value=False):
            r = k.run_check()
        self.assertEqual(r["rows"][0]["note"], "estimated")
        self.assertEqual(r["level"], k.CAUTION)


class ExplanationTests(unittest.TestCase):
    def test_every_scenario_explains_in_both_languages(self):
        scenarios = [({"*": "home"}, {"app": DIRECT_GROUP, "browser": NONE_GROUP}),
                     ({"claude.com": "vpn"}, {"app": VPN_GROUP, "browser": NONE_GROUP}),
                     ({"*": "vpn"}, {"app": DIRECT_GROUP, "browser": NONE_GROUP}),
                     ({"*": "hk"}, {"app": NONE_GROUP, "browser": NONE_GROUP}),
                     ({"*": "home"}, {"app": {"status": "proxied", "vpn": 0, "direct": 0, "local": 5}, "browser": NONE_GROUP})]
        for trace_map, apps in scenarios:
            result = fake_run_check(trace_map, apps, vpn_software=[("NordVPN", "app")])
            for lang in ("ja", "en"):
                head, reasons, actions = k.build_explanation(result, lang)
                self.assertTrue(head and reasons and actions, (trace_map, lang))
                self.assertNotIn("{", " ".join(reasons + actions), "埋め忘れの {} が残っている")

    def test_change_from_previous_is_reported(self):
        result = fake_run_check({"*": "hk"}, {"app": NONE_GROUP, "browser": NONE_GROUP})
        result["prev"] = {"level": "safe", "time": "2026-01-01 00:00", "rows": {"claude.ai": "ok"}}
        _, reasons, _ = k.build_explanation(result, "ja")
        self.assertIn("前回", reasons[0])

    def test_app_split_vpn_gets_a_guide(self):
        result = fake_run_check({"claude.com": "vpn"}, {"app": NONE_GROUP, "browser": NONE_GROUP}, vpn_software=[("NordVPN", "app")])
        _, _, actions = k.build_explanation(result, "en")
        self.assertTrue(any("NordVPN" in a for a in actions))


class MiscTests(unittest.TestCase):
    def test_version_files_match(self):
        """版を上げたとき、exe のプロパティに出る版の直し忘れを防ぐ。"""
        numbers = ", ".join((k.VERSION.split(".") + ["0"] * 4)[:4])
        for path in ("version_info.txt", os.path.join("取説", "version_info.txt")):
            with open(os.path.join(ROOT, path), encoding="utf-8-sig") as f:
                text = f.read()
            for expected in (f"filevers=({numbers})", f"prodvers=({numbers})",
                             f"'FileVersion', '{k.VERSION}'", f"'ProductVersion', '{k.VERSION}'"):
                self.assertIn(expected, text, path)

    def test_version_compare(self):
        self.assertGreater(k._version_tuple("v1.10.0"), k._version_tuple("1.2.0"))
        self.assertEqual(k._version_tuple("v1.2.0"), k._version_tuple("1.2.0"))

    def test_check_update(self):
        newer = '{"tag_name": "v99.0.0", "draft": false, "prerelease": false}'
        with mock.patch.object(k, "http_get", return_value=newer):
            self.assertEqual(k.check_update()[0], "v99.0.0")
        same = '{"tag_name": "v%s", "draft": false}' % k.VERSION
        with mock.patch.object(k, "http_get", return_value=same):
            self.assertIsNone(k.check_update())
        draft = '{"tag_name": "v99.0.0", "draft": true}'
        with mock.patch.object(k, "http_get", return_value=draft):
            self.assertIsNone(k.check_update())

    def test_looks_blocked(self):
        self.assertTrue(k.looks_blocked(OSError("ERR_BLOCKED_BY_CLIENT")))
        self.assertTrue(k.looks_blocked(k.HttpStatusError(403)))
        self.assertFalse(k.looks_blocked(ValueError("x")))

    def test_row_values_has_no_unfilled_text(self):
        row = {"domain": "claude.ai", "status": k.VPN, "countries": ["JP"], "note": "mixed", "families": {}}
        for lang in ("ja", "en"):
            country, status = k.row_values(row, lang)
            self.assertTrue(country and status)


def _can_use_tk():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_can_use_tk(), "画面が使えない環境")
class GuiSmokeTests(unittest.TestCase):
    """画面を実際に作って、3つの表示・言語・文字の大きさを切り替えても、エラーが出ないことを確かめる。"""

    def test_views_languages_and_scale(self):
        import tkinter as tk
        info = {"home": HOME, "vpn": VPN_INFO}
        patches = [
            mock.patch.object(k, "REMOTE_CONFIG_URL", ""),
            mock.patch.object(k, "load_json", side_effect=lambda name, default: {"lang": "ja"} if name == "settings.json" else default),
            mock.patch.object(k, "save_json"), mock.patch.object(k, "save_history", return_value=None),
            mock.patch.object(k, "save_last"), mock.patch.object(k, "load_last", return_value=None),
            mock.patch.object(k, "windows_dark_mode", return_value=False),
            mock.patch.object(k, "autostart_enabled", return_value=False),
            mock.patch.object(k, "windows_proxy_enabled", return_value=False),
            mock.patch.object(k, "detect_vpn_software", return_value=[("AdGuard VPN", "domain")]),
            mock.patch.object(k, "get_supported_countries", return_value=(SUPPORTED, "builtin", "2026-01-01")),
            mock.patch.object(k, "fetch_trace_ip", side_effect=lambda h, fam=socket.AF_INET: ("vpn" if h == "claude.com" else "home") if fam == socket.AF_INET else (_ for _ in ()).throw(OSError())),
            mock.patch.object(k, "lookup_ip", side_effect=lambda ip: info[ip]),
            mock.patch.object(k, "check_app_traffic", return_value={"app": VPN_GROUP, "browser": NONE_GROUP}),
        ]
        for p in patches:
            p.start()
        errors, done = [], []
        root = tk.Tk()
        root.report_callback_exception = lambda *a: errors.append("".join(traceback.format_exception(*a)))
        try:
            app = k.App(root)

            # 別のスレッドから画面を更新するので、本物の mainloop の中で、順番に操作する
            def steps():
                yield from wait_for_result()
                self.assertEqual(app.view, "hud")
                for expected in ("friendly", "plain", "hud", "friendly"):
                    app.toggle_view()
                    self.assertEqual(app.view, expected)
                    yield 300
                app.toggle_lang()
                yield 300
                app.change_scale(0.1)
                app.change_scale(None)
                yield 300
                app.start_check()  # チェック中に切り替える
                for _ in range(3):
                    app.toggle_view()
                yield from wait_for_result()
                done.append(True)

            def wait_for_result():
                for _ in range(200):
                    if app.result is not None:
                        return
                    yield 100
                self.fail("チェックが終わらなかった")

            sequence = steps()

            def advance():
                try:
                    root.after(next(sequence), advance)
                except StopIteration:
                    root.quit()
                except Exception:  # noqa: BLE001
                    errors.append(traceback.format_exc())
                    root.quit()

            root.after(300, advance)
            root.after(60000, root.quit)  # 止まったときの保険
            root.mainloop()
        finally:
            try:
                root.destroy()
            except Exception:  # noqa: BLE001
                pass
            mock.patch.stopall()
            app = sequence = None
            gc.collect()  # 画面の部品を、このスレッドで片づける
        self.assertEqual(errors, [], "画面の処理でエラーが出た")
        self.assertTrue(done, "操作の手順が最後まで進まなかった")


if __name__ == "__main__":
    unittest.main()
