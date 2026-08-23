.PHONY: check hygiene

check: hygiene

hygiene:
	python3 scripts/check_repo_hygiene.py
