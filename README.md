# 回線チェッカー（非公式） / Connection Checker (unofficial)

Claude を使うときのネットのつながり方が、VPN やデータセンターの回線を通っていないか、利用対象の国からつながっているかを判定する Windows 11 用のアプリです。

> **非公式ツールです。** Anthropic 社とは関係ありません。判定は目安で、BAN されないことを保証するものではありません。

A Windows 11 app that checks whether your connection to Claude goes through a VPN or data center network, and whether you connect from a supported country.

> **Unofficial tool, not affiliated with Anthropic.** Results are a guide only and do not guarantee that your account won't be banned.

## 使い方 / Usage

1. zip を展開し、`回線チェッカー.exe` をダブルクリックします。 / Extract the zip and run `回線チェッカー.exe`.
2. 数秒で結果が出ます。 / The result appears in a few seconds.

くわしくは `説明書.html` を見てください（日本語）。右上のボタンで画面を英語に切り替えられます。
See `説明書.html` for details (Japanese). Use the button in the top-right corner to switch the app to English.

## 送信する情報 / Data sent

- Claude の各ドメイン、www.cloudflare.com、Anthropic の国一覧ページに接続します。
- 接続元の IP アドレスを、IP 判定サービス（freeipapi.com、IP2Location.io）に HTTPS で送ります。
- IP アドレス・地域・プロバイダ名は、画面にも履歴にも残しません。利用状況を作者に送ることはありません。

- Connects to Claude's domains, www.cloudflare.com and Anthropic's supported-countries page.
- Sends your public IP address to IP lookup services (freeipapi.com, IP2Location.io) over HTTPS.
- IP addresses, locations and ISP names are never shown or saved. No usage data is sent to the author.

## 正しく判定できない場合 / Known limitations

- アプリ単位で除外する VPN（NordVPN など）では、`回線チェッカー.exe` も除外しないと結果が合いません。
- ブラウザ拡張の VPN は判定できません。

- With per-app split tunneling (e.g. NordVPN), exclude this app as well or the result may not match.
- Browser-extension VPNs cannot be detected.

## ファイルの確認 / Verify the download

```powershell
Get-FileHash .\回線チェッカー_v1.1.0.zip -Algorithm SHA256
```

結果を、配布ページの `SHA256SUMS.txt` と比べてください。 / Compare the result with `SHA256SUMS.txt` on the release page.

## ソースからビルド / Build from source

```powershell
pip install pyinstaller
python -m PyInstaller --onedir --noconsole --name "回線チェッカー" --version-file version_info.txt kaisen_checker.py
```

Python 3.13 と標準ライブラリだけで動きます。 / Requires Python 3.13 and the standard library only.

## ライセンス / License

MIT License — Copyright (c) 2026 Cape-PC。くわしくは `LICENSE` を見てください。 / See `LICENSE`.

## 商標 / Trademarks

「Claude」「Anthropic」は Anthropic 社の商標です。 / "Claude" and "Anthropic" are trademarks of Anthropic.

## 変更履歴 / Changelog

- 1.1.0：英語表示、ダークモード、国一覧の自動取得、VPN ソフト別の案内、免責表示を追加。履歴の保存先を `%LOCALAPPDATA%\KaisenChecker` に変更。
- 1.0.0：最初の版。
