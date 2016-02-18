#!/bin/bash
RANDOM_101CHAR_KEY=$(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 101 | tr -d '\n')
DB_FILE=jsonp_db.db
set -o pipefail -o errexit -o nounset -o xtrace

make kill-local-server
test -e $DB_FILE && mv $DB_FILE $DB_FILE.bak
sqlite3 $DB_FILE 'CREATE TABLE KVStore(Key TEXT PRIMARY KEY, Value TEXT);'
make start-local-server

curl -s http://localhost:8080/jsonp_db/the_answer?42 | grep '^42$'
curl -s http://localhost:8080/jsonp_db/the_answer | grep '^42$'
curl -sX POST -d '{name:"John Doe"}' http://localhost:8080/jsonp_db/json_doe | grep '{name:"John Doe"}'
curl -s http://localhost:8080/jsonp_db/json_doe | grep '{name:"John Doe"}'
curl -s http://localhost:8080/jsonp_db/urlencoded_dict?%7Bname%3A%22John%20Doe%22%7D | grep '{name:"John Doe"}'
curl -s http://localhost:8080/jsonp_db/urlencoded_dict?callback=foo | grep 'foo({name:"John Doe"}, null)'
curl -s http://localhost:8080/jsonp_db/nested?%7Ba%3A%7Bb%3Atrue%7D%7D | grep '{a:{b:true}}'
echo '@<>#%"{}|\^[]`' > tmp.json
curl -sX POST --data-urlencode @tmp.json http://localhost:8080/jsonp_db/urlencoded_str | grep '@<>#%"{}|\\^\[\]`'
rm tmp.json

# Error handling:
curl -s http://localhost:8080/jsonp_db | grep 'Error400: Incorrect request syntax'
curl -s http://localhost:8080/jsonp_db/a/ | grep 'Error400: Incorrect request syntax'
curl -s http://localhost:8080/jsonp_db/unset_key | grep 'undefined'
curl -sX PUT -d 0=1 http://localhost:8080/jsonp_db/$RANDOM_101CHAR_KEY | grep 'Key length exceeded maximum'

#curl -s http://localhost:8080/jsonp_db/nonascii?aéè | grep 'àéè'
# TODO FIXME

# Modification-key
modifkey=$(curl -s 'http://localhost:8080/jsonp_db/K?callback=_&V1' | sed 's/_(V1, "\(.*\)")/\1/')
curl -s "http://localhost:8080/jsonp_db/K?V2&modification-key=$modifkey"
curl -s http://localhost:8080/jsonp_db/K | grep V2
curl -s 'http://localhost:8080/jsonp_db/K?V2&modification-key=DUMMY' | grep 'Error400: Invalid modification-key'
curl -s http://localhost:8080/jsonp_db/K?V2 | grep 'Error400: No modification-key provided'

make kill-local-server
test -e $DB_FILE.bak && mv $DB_FILE.bak $DB_FILE

