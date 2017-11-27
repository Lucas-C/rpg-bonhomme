# BEWARE ! Makefiles require the use of hard tabs
OUT_HTML    := index.html
TMPLT_HTML  := template-index.html
CSS_SRC_FILE:= character-sheet.css
JS_SRC_FILE := character-sheet.js
PY_WSGI     := jsonp_db.py
DB_FILE     := jsonp_db.db
CSS_DIR     := layout/
CSS_LAYOUTS := $(wildcard $(CSS_DIR)*.css)

.PHONY: all install check $(CSS_LAYOUTS) test run-server help clean

all: $(OUT_HTML)
	@:

install: dev-requirements.txt
	pip install -r $<
	npm install -g csslint htmlhint htmllint-cli jscs jshint
	pre-commit install

$(OUT_HTML): index_generator.py $(DB_FILE) $(TMPLT_HTML) $(JS_SRC_FILE) $(CSS_SRC_FILE)
	./$< --db-filepath $(DB_FILE) --html-template $(TMPLT_HTML) >$(OUT_HTML)

check: $(CSS_LAYOUTS) $(CSS_SRC_FILE) $(JS_SRC_FILE) $(PY_WSGI) $(TMPLT_HTML)
	csslint --ignore=order-alphabetical $(CSS_SRC_FILE)
	jscs $(JS_SRC_FILE)
	jshint $(JS_SRC_FILE)
	pep8 $(PY_WSGI)
	## Parsing the template so that we do not have to generate $(OUT_HTML) which required a valid .db
	htmlhint $(TMPLT_HTML)
	## Parsing the template for the same reason + because of this bug: https://github.com/htmllint/htmllint/issues/216
	htmllint $(TMPLT_HTML)
	pre-commit run --all-files

$(CSS_LAYOUTS): $(CSS_DIR)%.css:
	csslint --ignore=ids,order-alphabetical,overqualified-elements $@
	grep -q 'input#name' $@ || { echo "No input#name in $@" && false; }

run-server: $(PY_WSGI) $(DB_FILE)
	## Launching a local server to serve HTML files & WSGI apps
	python -m webbrowser http://localhost/$(OUT_HTML)
	./$(PY_WSGI)

test: $(PY_WSGI)
	./jsonp_db-tests.sh

help:
	# make -n target           # --dry-run : get targets description
	# make -B target           # --always-make : force execution of targets commands, even if dependencies are satisfied
	# make --debug[=abijmv]    # enable variants of make verbose output

clean:
	@$(RM) $(OUT_HTML)
