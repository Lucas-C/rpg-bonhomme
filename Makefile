# BEWARE ! Makefiles require the use of hard tabs
OUT_HTML    := index.html
LOCAL_HTML  := local-character-sheet.html
TMPLT_HTML  := template-index.html
CSS_SRC_FILE:= character-sheet.css
JS_SRC_FILE := character-sheet.js
INDEX_MAKER := index_generator.py
PY_WSGI     := jsonp_db
DB_FILE     := jsonp_db.db
HTML_CHECKER:= vnu.jar
CSS_DIR     := layout/
PORT        := 8082
CSS_LAYOUTS := $(wildcard $(CSS_DIR)*.css)

.PHONY: all clean test help
.PHONY: check check-style check-layouts-css $(CSS_LAYOUTS)
.PHONY: view-local open-index
.PHONY: start-local-server restart-local-server kill-local-server list-local-server-processes

all: $(OUT_HTML)
	@:

$(OUT_HTML): $(INDEX_MAKER) $(TMPLT_HTML) $(JS_SRC_FILE) $(CSS_SRC_FILE) $(DB_FILE)
	./$< --db-filepath $(DB_FILE) --html-template $(TMPLT_HTML) > $(OUT_HTML)

check: check-style pre-commit-hooks
	@:

check-style: $(TMPLT_HTML) $(JS_SRC_FILE) check-layouts-css
	## Running code style check
	jscs $(JS_SRC_FILE)
	jshint $(JS_SRC_FILE)
	pep8 $(PY_WSGI).py
    ## Parsing the template so that we do not have to generate $(OUT_HTML) which required a valid .db
	htmlhint $(TMPLT_HTML)
    ## Parsing the template for the same reason + because of this bug: https://github.com/htmllint/htmllint/issues/216
	htmllint $(TMPLT_HTML)

check-layouts-css: $(CSS_LAYOUTS) $(CSS_SRC_FILE)
	## DONE checking the CSS layouts

$(CSS_SRC_FILE):
	@csslint --ignore=order-alphabetical $@

$(CSS_LAYOUTS): $(CSS_DIR)%.css:
	@csslint --ignore=ids,order-alphabetical,overqualified-elements $@
	@grep -q 'input#name' $@ || { echo "No input#name in $@" && false; }

pre-commit-hooks: .git/hooks/pre-commit
	pre-commit run

.git/hooks/pre-commit:
	pre-commit install

view-local: open-index start-local-server
	@:

open-index: $(LOCAL_HTML)
	## Opening the website in a browser
	python -m webbrowser http://localhost:$(PORT)/$(LOCAL_HTML)

$(LOCAL_HTML): $(OUT_HTML)
	### Generating a local HTML file pointing to the WSGI DB running on localhost
	sed "s/SERVER_STORAGE_CGI = '.*'/SERVER_STORAGE_CGI = 'http:\/\/localhost:$(PORT)\/$(PY_WSGI)\/'/" $(OUT_HTML) > $(LOCAL_HTML)

start-local-server:
	## Launching a local server to serve HTML files & WSGI apps
	uwsgi --buffer-size 8000 --http :$(PORT) --static-map /=. --touch-reload $(OUT_HTML) \
		--manage-script-name --mount /$(PY_WSGI)=$(PY_WSGI).py --py-autoreload 2 --daemonize uwsgi.log &

restart-local-server:
	@pgrep -f '^[^ ]*uwsgi' | ifne xargs kill

list-local-server-processes:
	@pgrep -f '^[^ ]*uwsgi' | ifne xargs ps -fp

kill-local-server:
	@pgrep -f '^[^ ]*uwsgi' | ifne xargs kill -2

test:
	./jsonp_db-tests.sh

help:
	# make -n target           # --dry-run : get targets description
	# make -B target           # --always-make : force execution of targets commands, even if dependencies are satisfied
	# make --debug[=abijmv]    # enable variants of make verbose output

clean:
	@$(RM) $(LOCAL_HTML) $(OUT_HTML)
