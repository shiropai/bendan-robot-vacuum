# repo 改成公開了：之後寫進 repo 的東西任何人都看得到

- 回覆：—
- 分支／PR：—（只改了 GitHub 的 repo 設定；這份筆記直接推上 `main`）
- 寫的人：shiro 的 Claude

## 做了什麼

- 2026-11-22，shiro 決定把 `shiropai/bendan-robot-vacuum` 從私人改成**公開**，我已經改好了，沒登入也看得到。
- 公開前掃過全部 commit 的每一個版本：沒有 API Key、token、私鑰，也沒有學號。

## 要對方注意的

- **之後的筆記、commit、PR、issue 全部是公開的。** 不要寫：API Key、組帳號密碼、學號、任何人的 email 或全名、
  伺服器位址，也不要貼 log 裡的原始請求。要提到組員，用 GitHub 帳號或「組員」就好。
- commit 的作者 email 也會公開。如果你那邊用的是個人信箱，可以改用 GitHub 的 noreply 信箱
  （GitHub → Settings → Emails → 勾「Keep my email addresses private」，再把 `git config user.email` 設成那個 noreply 信箱）。
- [PR #8](https://github.com/shiropai/bendan-robot-vacuum/pull/8)（v9.1，修好分給 shiro 的 6 個問題）在等你看：
  裡面改到你那邊的 `bendan/gameplay/mood.py`，只新增東西，原本的數值沒動。

## ❓ 待回答

無（第一份筆記的 3 個問題，和 PR #8 的 review 還在等你）。
