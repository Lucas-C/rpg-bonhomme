#!/bin/bash
RANDOM_101CHAR_KEY=$(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 101 | tr -d '\n')
set -o pipefail -o errexit -o nounset -o xtrace

curl -s http://localhost:8080/jsonp-db/the_answer?42 | grep '^42$'
curl -s http://localhost:8080/jsonp-db/the_answer | grep '^42$'
curl -sX POST -d '{name:"John Doe"}' http://localhost:8080/jsonp-db/json_doe | grep '{name:"John Doe"}'
curl -s http://localhost:8080/jsonp-db/json_doe | grep '{name:"John Doe"}'
curl -s http://localhost:8080/jsonp-db/urlencoded_dict?%7Bname%3A%22John%20Doe%22%7D | grep '{name:"John Doe"}'
curl -s http://localhost:8080/jsonp-db/urlencoded_dict?callback=foo | grep 'foo({name:"John Doe"}, '
curl -s http://localhost:8080/jsonp-db/nested?%7Ba%3A%7Bb%3Atrue%7D%7D | grep '{a:{b:true}}'
echo '@<>#%"{}|\^[]`' > tmp.json
curl -sX POST --data-urlencode @tmp.json http://localhost:8080/jsonp-db/urlencoded_str | grep '@<>#%"{}|\^\[\]`'
rm tmp.json

# Error handling:
curl -s http://localhost:8080/jsonp-db | grep 'Error400: Incorrect request syntax'
curl -s http://localhost:8080/jsonp-db/a/ | grep 'Error400: Incorrect request syntax'
curl -s http://localhost:8080/jsonp-db/unset_key | grep 'undefined'
curl -sX PUT -d 0=1 http://localhost:8080/jsonp-db/$RANDOM_101CHAR_KEY | grep 'Key length exceeded maximum'

#curl -s http://localhost:8080/jsonp-db/nonascii?aéè | grep 'àéè'
# TODO FIXME

# Modification-key
# TODO FIXME
