PYTHON := $(CURDIR)/.venv/bin/python
ODOO_BIN := $(CURDIR)/odoo/odoo-bin
CONFIG := $(CURDIR)/odoo.conf
DATABASE ?= superstore_erp

.PHONY: check run version

check:
	test -x "$(PYTHON)"
	test -f "$(ODOO_BIN)"
	test -f "$(CONFIG)"
	test -d "$(CURDIR)/odoo/addons"
	test -d "$(CURDIR)/custom-addons"

version:
	"$(PYTHON)" "$(ODOO_BIN)" --version

run: check
	"$(PYTHON)" "$(ODOO_BIN)" \
		-c "$(CONFIG)" \
		-d "$(DATABASE)"