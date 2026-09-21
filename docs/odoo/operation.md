# CÀI ODOO 18 TỪ A → Z TRÊN MACBOOK (Apple Silicon) ĐỂ CODE

> **Máy đích:** MacBook Pro M-series · Anaconda (base = Python 3.13) · VS Code
> **Mục tiêu:** Chạy Odoo từ source, đọc/debug code trong VS Code, có PostgreSQL thật để sau này cắm Debezium CDC.
> **Thời gian:** ~30-45 phút (phần lâu nhất là clone + pip install)

---

## 🗺️ Bản đồ toàn bộ quá trình (6 bước)

```
BƯỚC 1: Cài PostgreSQL          (tầng 4 — kho dữ liệu)
BƯỚC 2: Tạo môi trường Python 3.11 (Conda hoặc venv)
BƯỚC 3: Tạo project + clone source (lấy code về)
BƯỚC 4: Cài thư viện Python        (đồ nghề code cần)
BƯỚC 5: Config + chạy lần đầu      (nối code ↔ data, khởi động)
BƯỚC 6: Setup VS Code              (đọc code + debug F5)
```

Kiểm tra sau MỖI bước trước khi đi tiếp — đừng chạy một mạch.

---

## BƯỚC 1 — Cài PostgreSQL 16

**Vì sao:** Code Odoo chỉ là logic, không chứa dữ liệu. Mọi đơn hàng/khách hàng nằm trong PostgreSQL — một service chạy ngầm riêng, Odoo kết nối vào qua cổng 5432.

```bash
# 1.1. Cài
brew install postgresql@16

# 1.2. Khởi động service (tự chạy lại mỗi lần bật máy)
brew services start postgresql@16

# 1.3. Đưa psql vào PATH (bản @16 không tự link)
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 1.4. Tạo user "odoo" có quyền tạo database
createuser -s odoo
```

**✅ Kiểm tra:**
```bash
psql -U odoo -d postgres -c "SELECT version();"
# Phải in ra: PostgreSQL 16.x ...
```

**Nếu lỗi `command not found: psql`** → bước 1.3 chưa ăn, mở terminal MỚI rồi thử lại.
**Nếu lỗi `role "odoo" already exists`** → không sao, đã tạo rồi, đi tiếp.

---

## BƯỚC 2 — Tạo môi trường Python 3.11

**Vì sao:** Máy bạn đang dùng Python **3.13**, trong khi Odoo 18 phù hợp với Python **3.10 → 3.12**. Vì vậy cần một môi trường riêng chạy Python 3.11 để không ảnh hưởng Python của hệ thống.

Ở bước này có **2 lựa chọn**. Chỉ thực hiện **MỘT** trong hai option dưới đây:

- **Option 1 — Conda:** phù hợp nếu máy đã cài Anaconda/Miniconda; đây là lựa chọn khuyến nghị cho máy hiện tại.
- **Option 2 — venv:** phù hợp nếu muốn dùng môi trường Python tiêu chuẩn, gọn nhẹ và không phụ thuộc Conda.

### 2.1. Option 1 — Tạo môi trường bằng Conda (khuyến nghị)

```bash
# Tạo môi trường tên "odoo18" với Python 3.11
conda create -n odoo18 python=3.11 -y

# Kích hoạt môi trường
conda activate odoo18
```

Mỗi khi mở terminal mới, kích hoạt lại bằng:

```bash
conda activate odoo18
```

### 2.2. Option 2 — Tạo môi trường bằng venv

`venv` không tự cài hoặc đổi phiên bản Python. Vì máy đang dùng Python 3.13, trước tiên phải cài riêng Python 3.11 bằng Homebrew, sau đó dùng đúng bản này để tạo môi trường.

```bash
# Cài Python 3.11 nếu máy chưa có
brew install python@3.11

# Tạo nơi lưu các virtual environment cá nhân
mkdir -p ~/.venvs

# Tạo virtual environment tên "odoo18" bằng Python 3.11
/opt/homebrew/bin/python3.11 -m venv ~/.venvs/odoo18

# Kích hoạt virtual environment
source ~/.venvs/odoo18/bin/activate

# Cập nhật pip trong môi trường mới
python -m pip install --upgrade pip
```

Mỗi khi mở terminal mới, kích hoạt lại bằng:

```bash
source ~/.venvs/odoo18/bin/activate
```

> Không chạy cả hai option. Conda env và venv là hai môi trường độc lập; thư viện cài trong môi trường này không xuất hiện trong môi trường kia.

**✅ Kiểm tra (áp dụng cho cả hai option):**

```bash
# Đầu dòng terminal phải có (odoo18)
python --version
# Phải in ra: Python 3.11.x (KHÔNG phải 3.13)

which python
# Option 1 phải trỏ tới: .../anaconda3/envs/odoo18/bin/python
# Option 2 phải trỏ tới: /Users/<username>/.venvs/odoo18/bin/python
```

**⚠️ Quy tắc từ giờ về sau:** chỉ chạy các lệnh `pip` khi đầu dòng terminal có `(odoo18)`. Nếu chưa có, hãy kích hoạt lại bằng lệnh của option bạn đã chọn.

---

## BƯỚC 3 — Tạo project folder + clone source

**Vì sao cấu trúc này:** Project folder (`odoo-dev`) ≠ source folder (`odoo/`). Source của cộng đồng nằm gọn một góc CHỈ ĐỂ ĐỌC; đồ của bạn (custom-addons, config) nằm bên ngoài. Nhờ vậy nâng cấp Odoo không mất công sức của bạn, và đóng gói Docker sau này chỉ cần mang đồ của bạn đi.

```bash
# 3.1. Tạo project folder (tầng ngoài — nơi mở VS Code)
mkdir ~/odoo-dev && cd ~/odoo-dev

# 3.2. Clone Odoo 18 — chỉ lấy bản mới nhất, bỏ lịch sử (nhẹ hơn ~6GB)
git clone https://github.com/odoo/odoo.git --depth 1 --branch 18.0

# 3.3. Tạo đất riêng cho module của bạn sau này
mkdir custom-addons
```

**✅ Kiểm tra:**
```bash
ls ~/odoo-dev
# Phải thấy: odoo  custom-addons

ls ~/odoo-dev/odoo | head
# Phải thấy: odoo-bin, addons/, odoo/, requirements.txt ...
```

Cấu trúc đích:
```
~/odoo-dev/                ← PROJECT (mở VS Code tại đây)
   ├── odoo/               ← source clone (CHỈ ĐỌC, không sửa)
   │     ├── odoo-bin      ← file khởi động
   │     ├── odoo/         ← lõi framework: ORM, server
   │     └── addons/       ← ~400 module: sale/, purchase/, stock/...
   ├── custom-addons/      ← code CỦA BẠN (sau này)
   ├── odoo.conf           ← tạo ở Bước 5
   └── .vscode/            ← tạo ở Bước 6
```

---

## BƯỚC 4 — Cài thư viện Python

**Vì sao:** Code Odoo import ~70 thư viện ngoài (psycopg2 nói chuyện Postgres, lxml xử lý XML, reportlab in PDF...). Vài thư viện viết bằng C — pip phải BIÊN DỊCH trên máy, cần sẵn "nguyên liệu C" từ brew (đặc thù Apple Silicon hay thiếu).

```bash
# Chắc chắn môi trường (odoo18) của Conda hoặc venv đang được kích hoạt!

# 4.1. Nguyên liệu C cho quá trình biên dịch
brew install libpq openssl libxml2 libxslt

# 4.2. psycopg2: dùng bản binary đóng sẵn, né lỗi biên dịch M-series
pip install psycopg2-binary

# 4.3. Cài toàn bộ requirements
cd ~/odoo-dev/odoo
pip install -r requirements.txt
```

**✅ Kiểm tra:**
```bash
python -c "import psycopg2, lxml, PIL, reportlab; print('OK — đủ đồ nghề')"
```

**Nếu requirements.txt lỗi giữa chừng** (thường ở `gevent` hoặc `python-ldap`):
```bash
# Hai package này không bắt buộc cho dev cơ bản. Cài từng dòng, bỏ qua dòng lỗi:
pip install -r requirements.txt 2>&1 | tail -5   # xem package nào lỗi
# rồi xóa/comment dòng đó trong requirements.txt và chạy lại,
# hoặc thử: pip install <tên-package> --no-build-isolation
```

---

## BƯỚC 5 — Tạo config + chạy lần đầu

**Vì sao cần odoo.conf:** Code (Bước 3) và database (Bước 1) là hai thứ tách rời chưa biết nhau. File config là "tờ giấy giới thiệu": database ở đâu, tìm module ở thư mục nào, mở web cổng mấy.

```bash
# 5.1. Lấy username máy bạn (cần cho đường dẫn tuyệt đối trong config)
whoami
# ví dụ in ra: macos
```

Tạo file `~/odoo-dev/odoo.conf` (thay `macos` bằng kết quả `whoami` của bạn):

```ini
[options]
db_host = localhost
db_port = 5432
db_user = odoo
db_password = False
addons_path = /Users/macos/odoo-dev/odoo/addons,/Users/macos/odoo-dev/custom-addons
http_port = 8069
```

```bash
# 5.2. CHẠY LẦN ĐẦU — tạo database + cài 6 module đã học
cd ~/odoo-dev/odoo
python odoo-bin -c ../odoo.conf -d trading_erp -i base,sale_management,purchase,stock,account,hr
```

Giải nghĩa lệnh: `-c` trỏ config · `-d trading_erp` tạo database tên đó · `-i` cài sẵn Sales, Purchase, Inventory, Accounting, HR. Lần đầu chạy mất 2-5 phút (Odoo tạo ~500 bảng + dữ liệu khởi tạo).

**✅ Kiểm tra:**
- Terminal hiện dòng `HTTP service (werkzeug) running on ...:8069`
- Mở browser: **http://localhost:8069** → trang login
- Đăng nhập: `admin` / `admin`
- Thấy menu Sales, Purchase, Inventory, Accounting → THÀNH CÔNG 🎉

**Kiểm tra tầng 4 (việc của dân data):**
```bash
# Mở terminal MỚI (để Odoo chạy tiếp ở terminal cũ)
psql -U odoo -d trading_erp

\dt                          -- liệt kê ~500 bảng
\d sale_order                -- soi cấu trúc, đối chiếu sổ tay 27 models
SELECT id, name, state FROM res_partner LIMIT 5;
\q
```

**Các lần chạy SAU (không cần -i nữa):**
```bash
# Kích hoạt lại môi trường theo option đã chọn:
conda activate odoo18
# HOẶC: source ~/.venvs/odoo18/bin/activate

cd ~/odoo-dev/odoo
python odoo-bin -c ../odoo.conf -d trading_erp
# Dừng server: Ctrl+C
```

---

## BƯỚC 6 — Setup VS Code để đọc code + debug

```bash
cd ~/odoo-dev
mkdir -p .vscode
code .        # mở VS Code tại project (hoặc mở tay: File > Open Folder > odoo-dev)
```

**6.1. Chọn interpreter:** `Cmd+Shift+P` → gõ "Python: Select Interpreter" → chọn **odoo18** đúng với option đã tạo:

- Conda: đường dẫn có `anaconda3/envs/odoo18/bin/python`.
- venv: đường dẫn có `.venvs/odoo18/bin/python`.

**6.2. Tạo file `.vscode/launch.json`:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Odoo 18",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/odoo/odoo-bin",
      "args": ["-c", "${workspaceFolder}/odoo.conf", "-d", "trading_erp"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

Từ giờ bấm **F5** = khởi động Odoo kèm debugger.

**✅ Kiểm tra tổng thể — bài debug đầu tiên:**
1. Mở `odoo/addons/sale/models/sale_order.py`
2. Tìm method `action_confirm` (Cmd+F) → click đặt breakpoint (chấm đỏ) ở dòng đầu method
3. Bấm F5 chạy Odoo → vào web tạo 1 báo giá → bấm nút **Confirm**
4. VS Code dừng đúng breakpoint → bấm Step Over (F10) từng dòng, nhìn Odoo sinh phiếu kho + chuyển state

> Nhìn thấy dòng chảy "1 cú Confirm kích hoạt dây chuyền" chạy qua từng dòng code = khoảnh khắc mọi lý thuyết đã học thành thật.

---

## 🧯 Bảng xử lý lỗi thường gặp (Apple Silicon)

| Lỗi | Nguyên nhân | Xử lý |
|---|---|---|
| `command not found: psql` | PATH chưa có postgresql@16 | Mở terminal mới; kiểm tra `~/.zshrc` có dòng export ở bước 1.3 |
| `connection refused ... 5432` | Postgres chưa chạy | `brew services restart postgresql@16` |
| `pg_config executable not found` | Thiếu libpq khi build psycopg2 | Đã né bằng `psycopg2-binary` — kiểm tra đã cài chưa |
| `error: legacy-install-failure` khi pip | Package C không build được trên M-series | `brew install` nguyên liệu (4.1) rồi thử lại; package không thiết yếu thì bỏ qua |
| Chạy odoo-bin báo `ModuleNotFoundError` | Package được cài sai môi trường | Kích hoạt `(odoo18)` theo option đã chọn rồi cài lại package đó |
| Web trắng / port bận | 8069 bị chiếm | Đổi `http_port = 8070` trong odoo.conf |
| `FATAL: role "odoo" does not exist` | Chưa tạo user Postgres | Chạy lại `createuser -s odoo` |

---

## 📋 Checklist hoàn thành

- [ ] `psql -U odoo` vào được Postgres
- [ ] `(odoo18)` + `python --version` = 3.11.x
- [ ] `~/odoo-dev` có đủ: odoo/, custom-addons/, odoo.conf
- [ ] `import psycopg2, lxml` không lỗi
- [ ] http://localhost:8069 login được admin/admin
- [ ] `\dt` trong psql thấy ~500 bảng
- [ ] F5 trong VS Code chạy được Odoo
- [ ] Breakpoint trong `action_confirm` dừng được khi bấm Confirm trên web

## 🎯 Sau khi cài xong — tuần đầu tiên

Tự tay đi trọn **dòng chảy 8 bước** đã học, sau MỖI bước mở psql xem bảng nào đổi:

```
Tạo NCC → Tạo PO → Confirm PO → Nhận hàng (kho tăng)
→ Tạo KH → Tạo SO → Confirm SO (kho giảm + picking sinh ra)
→ Tạo hóa đơn → Ghi nhận thanh toán (amount_residual về 0)
```

Đây là cách kiểm chứng toàn bộ sổ tay 27 models bằng thực nghiệm — và chính là dữ liệu CDC đầu tiên cho Debezium sau này.
