# Python interpreter trong virtual environment của Odoo
PYTHON := $(CURDIR)/.venv/bin/python

# File thực thi chính của Odoo
ODOO_BIN := $(CURDIR)/odoo/odoo-bin

# File cấu hình Odoo
CONFIG := $(CURDIR)/odoo.conf

# Database mặc định; có thể override khi chạy make
DATABASE ?= superstore_erp

# Khai báo các target này không phải tên file
.PHONY: check run version repair-mart-data


# Kiểm tra môi trường cần thiết trước khi chạy Odoo
check:
	# Kiểm tra Python trong .venv tồn tại và có quyền execute
	test -x "$(PYTHON)"

	# Kiểm tra odoo-bin tồn tại
	test -f "$(ODOO_BIN)"

	# Kiểm tra file cấu hình odoo.conf tồn tại
	test -f "$(CONFIG)"

	# Kiểm tra thư mục addon mặc định của Odoo
	test -d "$(CURDIR)/odoo/addons"

	# Kiểm tra thư mục custom addon của project
	test -d "$(CURDIR)/custom-addons"


# Hiển thị phiên bản Odoo
version:
	"$(PYTHON)" "$(ODOO_BIN)" --version


# Chạy Odoo sau khi check môi trường
run: check
	"$(PYTHON)" "$(ODOO_BIN)" \
		-c "$(CONFIG)" \
		-d "$(DATABASE)"


# Bổ sung UTM/channel/carrier cho dữ liệu mô phỏng qua Odoo ORM nội bộ.
# Không cần mật khẩu XML-RPC và có thể chạy lại an toàn.
repair-mart-data: check
	set -a; . "$(CURDIR)/.env"; set +a; \
	PYTHONPATH="$(CURDIR)/source" "$(PYTHON)" "$(ODOO_BIN)" shell \
		-c "$(CONFIG)" \
		-d "$(DATABASE)" \
		< "$(CURDIR)/source/repair_mart_source_data.py"
