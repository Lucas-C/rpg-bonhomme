# BEWARE ! Makefiles require the use of hard tabs
OUT_HTML    := character-sheet.html
LOCAL_HTML  := local-character-sheet.html
TMPLT_HTML  := template-character-sheet.html
JS_SRC_FILE := character-sheet.js
PY_WSGI     := jsonp_db
DB_FILE     := jsonp_db.db
HTML_CHECKER:= vnu.jar
CSS_DIR     := css/
CSS_LAYOUTS := $(wildcard $(CSS_DIR)*.css)

.PHONY: check check-static check-style check-html check-layouts-css $(CSS_LAYOUTS)
.PHONY: view-local open-index
.PHONY: start-local-server restart-local-server kill-local-server list-local-server-processes
.PHONY: test help

all: $(OUT_HTML)
	@:

$(OUT_HTML): $(JS_SRC_FILE) $(TMPLT_HTML)
	# Inserting the JS code into the HTML template
	sed "/<script type='text\/javascript'>/r $(JS_SRC_FILE)" $(TMPLT_HTML) > $(OUT_HTML)

check: check-static check-style check-html check-layouts-css
	@:

check-static: $(JS_SRC_FILE)
	## Running static analysis check
	jshint $(JS_SRC_FILE)
	pylint --rcfile=.pylintrc --reports=no -f colorized $(PY_WSGI).py

check-style: $(JS_SRC_FILE)
	## Running code style check
	jscs $(JS_SRC_FILE)
	pep8 $(PY_WSGI).py

check-html: $(OUT_HTML) $(HTML_CHECKER)
	## Running HTML validation check
	grep -vF "http-equiv='X-UA-Compatible'" $(OUT_HTML) | java -jar $(HTML_CHECKER) -

$(HTML_CHECKER):
	### Retrieving vnu.jar from github
	wget https://github.com/validator/validator/releases/download/20141006/vnu-20141013.jar.zip
	unzip vnu*.jar.zip
	mv vnu/$(HTML_CHECKER) .
	rm -r vnu/ vnu*.jar.zip

check-layouts-css: $(CSS_LAYOUTS)
	## DONE checking the CSS layouts

$(CSS_LAYOUTS): $(CSS_DIR)%.css:
	@csslint --ignore=ids,overqualified-elements $@
	@grep -q 'input#name' $@ || { echo "No input#name in $@" && false; }

view-local: open-index start-local-server
	@:

open-index: $(LOCAL_HTML)
	## Opening the website in a browser
	python -m webbrowser http://localhost:8080/$(LOCAL_HTML)

$(LOCAL_HTML): $(OUT_HTML)
	### Generating a local HTML file pointing to the WSGI DB running on localhost
	sed "s/SERVER_STORAGE_CGI = '.*'/SERVER_STORAGE_CGI = 'http:\/\/localhost:8080\/$(PY_WSGI)\/'/" $(OUT_HTML) > $(LOCAL_HTML)

start-local-server:
	## Launching a local server to serve HTML files & WSGI apps
	uwsgi --buffer-size 8000 --http :8080 --static-map /=. --touch-reload $(OUT_HTML) \
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

