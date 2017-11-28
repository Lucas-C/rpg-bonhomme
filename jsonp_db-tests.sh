#!/bin/bash
RANDOM_101CHAR_KEY=$(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 101 | tr -d '\n')
set -o pipefail -o errexit -o nounset -o xtrace

DB_FILE=jsonp_db.db
test -e $DB_FILE && mv $DB_FILE $DB_FILE.bak
sqlite3 $DB_FILE 'CREATE TABLE KVStore(Key TEXT PRIMARY KEY, Value TEXT);'

./jsonp_db.py 8082 &  # TravisCI does not allow to use port 80
WSGI_PID=$!
WSGI_URL=http://localhost:8082
sleep 2

curl -s $WSGI_URL/the_answer?42 | grep '^\[42,'
curl -s $WSGI_URL/the_answer | grep '^42$'
curl -sX POST -d '{name:"John Doe"}' $WSGI_URL/json_doe | grep '{name:"John Doe"}'
curl -s $WSGI_URL/json_doe | grep '{name:"John Doe"}'
curl -s $WSGI_URL/urlencoded_dict?%7Bname%3A%22John%20Doe%22%7D | grep '{name:"John Doe"}'
curl -s $WSGI_URL/urlencoded_dict?callback=foo | grep 'foo({name:"John Doe"})'
curl -s $WSGI_URL/nested?%7Ba%3A%7Bb%3Atrue%7D%7D | grep '{a:{b:true}}'
echo '@<>#%"{}|\^[]`' > tmp.json
curl -sX POST --data-urlencode @tmp.json $WSGI_URL/urlencoded_str | grep '@<>#%"{}|\\^\[\]`'
rm tmp.json

# Error handling:
curl -s $WSGI_URL/a/ | grep '400 Bad Request : Incorrect request syntax'
curl -s $WSGI_URL/unset_key | grep 'undefined'
curl -sX PUT -d 0=1 $WSGI_URL/$RANDOM_101CHAR_KEY | grep 'Key length exceeded maximum'

# Modification-key
modifkey=$(curl -s "$WSGI_URL/K?callback=_&V1" | sed 's/_(V1, "\(.*\)")/\1/')
curl -s "$WSGI_URL/K?V2&modification-key=$modifkey"
curl -s $WSGI_URL/K | grep V2
curl -s "$WSGI_URL/K?V2&modification-key=DUMMY" | grep '401 Unauthorized : Invalid modification-key'
curl -s $WSGI_URL/K?V2 | grep '401 Unauthorized : No modification-key provided'

# List
curl -s $WSGI_URL/a_1?1
curl -s $WSGI_URL/a_2?2
curl -s $WSGI_URL/a_3?3
curl -s $WSGI_URL/list_by_prefix/a_ | grep "^\['1', '2', '3'\]\$"

kill $WSGI_PID
test -e $DB_FILE.bak && mv $DB_FILE.bak $DB_FILE || true
