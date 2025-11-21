# BEWARE ! Makefiles require the use of hard tabs
OUT_HTML    := index.html
TMPLT_HTML  := template-index.html
CSS_SRC_FILE:= character-sheet.css
JS_SRC_FILE := character-sheet.js
PY_INDEX_GEN:= index_generator.py
PY_WSGI     := jsonp_db.py
DB_FILE     := jsonp_db.db
CSS_DIR     := layout/
CSS_LAYOUTS := $(wildcard $(CSS_DIR)*.css)
PORT        := 8080

.PHONY: all install check $(CSS_LAYOUTS) test run-server help clean

all: $(OUT_HTML)
	@:

install: dev-requirements.txt
	pip install --upgrade -r $<
	npm install -g csslint htmlhint htmllint-cli jscs jshint
	pre-commit install

$(OUT_HTML): $(PY_INDEX_GEN) $(DB_FILE) $(TMPLT_HTML) $(JS_SRC_FILE) $(CSS_SRC_FILE)
	./$< $(TMPLT_HTML) --db-filepath $(DB_FILE) >$(OUT_HTML)

check: $(CSS_LAYOUTS) $(CSS_SRC_FILE) $(JS_SRC_FILE) $(PY_INDEX_GEN) $(PY_WSGI) $(TMPLT_HTML)
	csslint --ignore=order-alphabetical $(CSS_SRC_FILE)
	jscs $(JS_SRC_FILE)
	jshint $(JS_SRC_FILE)
	pycodestyle $(PY_INDEX_GEN)
	pycodestyle $(PY_WSGI)
	## Parsing the template so that we do not have to generate $(OUT_HTML) which required a valid .db
	htmlhint $(TMPLT_HTML)
	## Parsing the template for the same reason + because of this bug: https://github.com/htmllint/htmllint/issues/216
	htmllint $(TMPLT_HTML)
	pre-commit run --all-files

$(CSS_LAYOUTS): $(CSS_DIR)%.css:
	@# Check disabled due to: https://github.com/CSSLint/parser-lib/pull/256
	@if [ "$@" != "layout/BladesInTheDark.css" ]; then csslint --ignore=font-sizes,ids,order-alphabetical,overqualified-elements $@; fi
	@grep -q 'input#name' $@ || { echo "No input#name in $@" && false; }

run-server: $(PY_WSGI) $(DB_FILE)
	## Launching a local server to serve HTML files & WSGI apps
	python -m webbrowser http://localhost:$(PORT)/$(OUT_HTML)
	./$(PY_WSGI) $(PORT)

test: $(PY_WSGI)
	./jsonp_db-tests.sh

help:
	# make -n target           # --dry-run : get targets description
	# make -B target           # --always-make : force execution of targets commands, even if dependencies are satisfied
	# make --debug[=abijmv]    # enable variants of make verbose output

clean:
	@$(RM) $(OUT_HTML)
