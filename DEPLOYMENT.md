# 診所排班系統 - 部署指南

本指南將協助您將診所排班系統部署到 Streamlit Community Cloud 或其他雲端平台。

## 📋 目錄

- [Streamlit Community Cloud 部署(推薦)](#streamlit-community-cloud-部署推薦)
- [替代部署方案](#替代部署方案)
- [常見問題排解](#常見問題排解)

---

## Streamlit Community Cloud 部署(推薦)

### 為什麼選擇 Streamlit Community Cloud?

✅ **完全免費** - 無需信用卡
✅ **自動部署** - 從 GitHub 推送即自動更新  
✅ **HTTPS 加密** - 自動提供安全連線  
✅ **簡單設定** - 5 分鐘內完成部署  
✅ **Secrets 管理** - 安全儲存敏感憑證

---

### 步驟 1: 準備 GitHub 儲存庫

#### 1.1 初始化 Git (如果尚未初始化)

```bash
cd c:\Users\User\Desktop\program\clinic
git init
```

#### 1.2 檢查 .gitignore

確認以下敏感檔案 **不會** 被提交到 Git:

```
credentials.json          # ✅ 已在 .gitignore 中
config.py                 # ✅ 已在 .gitignore 中
.streamlit/secrets.toml   # ✅ 已在 .gitignore 中
```

驗證方法:
```bash
git status
```

如果看到 `credentials.json` 或 `config.py` 在待提交列表中,請先執行:
```bash
git rm --cached credentials.json config.py
```

#### 1.3 提交程式碼

```bash
git add .
git commit -m "準備 Streamlit Cloud 部署"
```

#### 1.4 推送到 GitHub

**選項 A: 建立新的儲存庫**

1. 前往 [GitHub](https://github.com) 並登入
2. 點擊右上角 `+` → `New repository`
3. 命名儲存庫(例如: `clinic-scheduler`)
4. 選擇 **Private**(私有,推薦) 或 Public(公開)
5. 點擊 `Create repository`
6. 按照 GitHub 提供的指令推送:

```bash
git remote add origin https://github.com/你的帳號/clinic-scheduler.git
git branch -M main
git push -u origin main
```

**選項 B: 使用現有儲存庫**

```bash
git remote add origin https://github.com/你的帳號/你的儲存庫.git
git push -u origin main
```

---

### 步驟 2: 設定 Streamlit Cloud

#### 2.1 註冊 Streamlit Community Cloud

1. 前往 [share.streamlit.io](https://share.streamlit.io)
2. 使用 GitHub 帳號登入
3. 授權 Streamlit 存取您的 GitHub 儲存庫

#### 2.2 部署應用程式

1. 點擊 `New app` 按鈕
2. 填寫部署設定:
   - **Repository**: 選擇您的 `clinic-scheduler` 儲存庫
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: 選擇您的應用程式網址(例如: `clinic-scheduler`)

3. **先不要點 Deploy!** 我們需要先設定 Secrets

---

### 步驟 3: 設定 Secrets(重要!)

#### 3.1 準備 Secrets 內容

開啟您本地的 `credentials.json` 文件,然後參考 `.streamlit/secrets.toml.example` 格式,將內容轉換為 TOML 格式。

**範例轉換**:

**credentials.json**:
```json
{
  "type": "service_account",
  "project_id": "my-project-123",
  "private_key": "-----BEGIN PRIVATE KEY-----\nABC...XYZ\n-----END PRIVATE KEY-----\n",
  "client_email": "my-service@my-project.iam.gserviceaccount.com",
  ...
}
```

**轉換為 TOML** (貼到 Streamlit Secrets):
```toml
[google_credentials]
type = "service_account"
project_id = "my-project-123"
private_key = "-----BEGIN PRIVATE KEY-----\nABC...XYZ\n-----END PRIVATE KEY-----\n"
client_email = "my-service@my-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."

spreadsheet_id = "你的試算表ID"
```

> [!IMPORTANT]
> **private_key 注意事項**: 請確保 `private_key` 的換行符號 `\n` 被保留。這是最常見的錯誤來源!

#### 3.2 在 Streamlit Cloud 添加 Secrets

1. 在部署設定頁面,點擊 `Advanced settings`
2. 找到 `Secrets` 區塊
3. 將上面準備的 TOML 內容完整貼入
4. 確認格式正確無誤

#### 3.3 部署

點擊 `Deploy!` 按鈕,等待 2-3 分鐘完成部署。

---

### 步驟 4: 驗證部署

部署完成後:

1. ✅ 檢查應用程式能否正常載入
2. ✅ 測試 Google Sheets 連線
3. ✅ 嘗試管理員登入
4. ✅ 測試生成排班功能

如果遇到問題,請查看 [常見問題排解](#常見問題排解)。

---

### 步驟 5: 更新部署

當您修改程式碼後,只需推送到 GitHub:

```bash
git add .
git commit -m "更新功能"
git push
```

Streamlit Cloud 會自動偵測更新並重新部署(約 1-2 分鐘)。

---

## 替代部署方案

### 方案 2: Render.com

**優點**: 免費層級、支援自訂網域、容易擴展

**步驟**:
1. 前往 [render.com](https://render.com) 並註冊
2. 連結 GitHub 儲存庫
3. 建立新的 Web Service
4. 設定:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
5. 在 Environment Variables 添加:
   - 將 `credentials.json` 轉為 JSON 字串設定為 `GOOGLE_CREDENTIALS`
   - 設定 `SPREADSHEET_ID`

### 方案 3: Railway.app

**優點**: 每月 $5 免費額度、極簡設定

**步驟**:
1. 前往 [railway.app](https://railway.app)
2. 使用 GitHub 登入
3. 新增專案並選擇您的儲存庫
4. Railway 會自動偵測並部署
5. 在 Variables 設定 Secrets

### 方案 4: 自架伺服器(VPS)

適合有伺服器管理經驗的使用者。

**推薦供應商**: DigitalOcean、Linode、AWS EC2

**基本步驟**:
1. 租用 VPS(最小 1GB RAM)
2. 安裝 Python 3.8+
3. 安裝相依套件: `pip install -r requirements.txt`
4. 使用 systemd 或 supervisor 管理 Streamlit 程序
5. 使用 Nginx 作為反向代理
6. 使用 Let's Encrypt 設定 SSL

---

## 常見問題排解

### ❌ 錯誤: "找不到憑證"

**原因**: Secrets 未正確設定

**解決方法**:
1. 檢查 Streamlit Cloud 的 Secrets 設定
2. 確認格式為 TOML,不是 JSON
3. 確認 `[google_credentials]` 區塊存在

### ❌ 錯誤: "連線失敗"

**可能原因**:
1. **private_key 格式錯誤**: 最常見! 確保 `\n` 被保留
2. **試算表未共用**: 確認已與服務帳戶共用試算表
3. **API 未啟用**: 確認 Google Sheets API 和 Drive API 已啟用

**解決方法**:
1. 重新複製 `private_key`,確保包含完整的 `-----BEGIN PRIVATE KEY-----` 和 `-----END PRIVATE KEY-----`
2. 開啟 Google Sheets,點擊「共用」,加入服務帳戶 email(在 `credentials.json` 的 `client_email`)
3. 前往 [Google Cloud Console](https://console.cloud.google.com) 檢查 API 狀態

### ❌ 錯誤: "工作表名稱錯誤"

**原因**: Google Sheets 工作表名稱不符

**解決方法**:
確認您的試算表包含以下工作表(全形中文):
- 設定檔
- 員工名單
- 管理員
- 請假
- 已排班

### ❌ 部署後應用程式一直重啟

**原因**: 程式碼錯誤或記憶體不足

**解決方法**:
1. 查看 Streamlit Cloud 的 Logs
2. 檢查是否有 Python 語法錯誤
3. 升級到更高的資源方案(如果使用付費平台)

### 🔍 查看應用程式日誌

在 Streamlit Cloud:
1. 開啟您的應用程式
2. 點擊右下角的 `Manage app`
3. 查看 `Logs` 標籤

---

## 安全性最佳實踐

✅ **絕不提交** `credentials.json` 或 `config.py` 到 GitHub  
✅ **使用私有儲存庫**(如果包含商業邏輯)  
✅ **定期輪換** Google Service Account 金鑰  
✅ **限制 API 權限** 只授予必要的 Google Sheets 存取權限  
✅ **監控存取日誌** 定期檢查 Google Cloud Console 的 API 使用記錄

---

## 需要協助?

如果遇到本指南未涵蓋的問題:

1. 檢查 Streamlit Cloud [官方文件](https://docs.streamlit.io/streamlit-community-cloud)
2. 查看應用程式日誌找出錯誤訊息
3. 確認所有步驟都已正確完成

---

**恭喜!** 🎉 您的診所排班系統現已成功部署到雲端!
