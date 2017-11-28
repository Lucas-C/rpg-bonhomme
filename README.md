[![Build Status](https://travis-ci.org/Lucas-C/rpg-bonhomme.svg?branch=master)](https://travis-ci.org/Lucas-C/rpg-bonhomme)

Features:
- purely web-based : only require a web browser for end users
- easily deployable WSGI Python app, also usable locally without Internet connexion
- locally load & save your character from JSON files, or save your character on a remote server,
which will let you share it with others simply by providing its unique URL
- can support character sheets from any game, simply by adding a new background image and matching CSS stylesheet

# Online website & examples

[Homepage](https://chezsoi.org/lucas/rpg-bonhomme)

- [Lythes](https://chezsoi.org/lucas/rpg-bonhomme?layout=Dedale&name=lythes), an android from the French RPG [Dédale](http://lab00.free.fr/sommaire/home.htm).
- [Kathelyn Terblanche](https://chezsoi.org/lucas/rpg-bonhomme?layout=Absence&name=kathelyn_terblanche) & [Raphaelle Lepercq](https://chezsoi.org/lucas/rpg-bonhomme?layout=Absence&name=raphaelle_lepercq_se_fait_appeler_lila_), two characters from a 'one-shot' RPG called 'Absence'.
- [Atharès](https://chezsoi.org/lucas/rpg-bonhomme?layout=InCognito1&name=athares), a character from the second campaign of my RPG game 'In Cognito'.
- [Ted Sand](https://chezsoi.org/lucas/rpg-bonhomme?layout=Allegoria&name=ted_sand) & [Jacob Valens](https://chezsoi.org/lucas/rpg-bonhomme?layout=Allegoria&name=jacob_valens) from my RPG campaign 'Allegoria'.
- [Sylvia](https://chezsoi.org/lucas/rpg-bonhomme?layout=PsiRun&name=Sylvia), a psi from the French version of the game [PsyRun](http://nightskygames.com/welcome/game/PsiRun).
- [Yuri Pashlov](https://chezsoi.org/lucas/jdr/rpg-bonhomme/?layout=Scavengers&name=yuri_pashlov), a character for Greg Pogorzelski game [Scavengers](http://awarestudios.blogspot.fr/2014/01/scavengers.html) 

# Usage

All the interactions are made using the 4 top right buttons and the 'name' input field.

To remote load an existing character, simply go to https://chezsoi.org/lucas/rpg-bonhomme?layout= and type a layout name at the end of URL, then enter your character name and press 'Load from remote server'. Alternatively you can directly enter an URL formatted like this: '?layout=<layout-name>&name=<character-id>'.

To edit and remote save a new character, simply go to https://chezsoi.org/lucas/rpg-bonhomme?layout= and type a layout name at the end of the URL, then enter your character name and press the 'Save to remote server' button.

The currently available layouts matches the list of file in the **layout/** & **background/** directories of this repository.

# Internals & asumptions

- a ?layout= URL parameter must always be provided to _index.html_.
- this _layout_ must match the name of a .css file in **layout/**, and a .png character sheet image in **background/**.
- input (or textarea) fields are defined once and only once by rules starting with 'input#<name>' in the layout.css,
and they must be the only selectors starting that way in the file.
Non-textual fields must be specified as 'input[type=.+]#<name>'
- the _layout.css_ MUST define a text input with id 'name'.
- (up)loading a new character currently only replace inputs defined in the provided file,
non-redefined caracteristics will keep their old value.

# jsonp_db

This is a simple key-value store, written in Python and using a SQLite DB, developped to allow simple GET/PUT through JSONP.

In case of a lookup error, the return value will be 'undefined', else it will returns 'value' or an error (a JS `Error` object if using JSONP, else an HTML error page).

There are some key/value length limitations currently hardcoded at the top of the Python file.
There is also a client & server limitation on the request URI (between 2KB & 8KB usually), that can trigger a 414 error.

Finally, a word of warning: **trusting a 3rd party JSONP API is a big confidence commitment / security risk**.
More details [here](http://security.stackexchange.com/a/23439).

That being said, this WSGI app won't do anything nasty.

## Environment setup

Installing a Python virtualenv and the needed dependencies with [pew](https://github.com/berdario/pew) :

    pew new rpg-bonhomme -p python3
    make install

## Deployment

Initial configuration & file permissions:

    echo modification_key_salt = $(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 30 | tr -d '\n') >> jsonp_db.ini
    sqlite3 jsonp_db.db 'CREATE TABLE KVStore(Key TEXT PRIMARY KEY, Value TEXT);'
    chmod ugo+rw jsonp_db.db

Installing the backup cron task:

    sudo sed -e "s~\$USER~$USER~" -e "s~\$PWD~$PWD~g" jsonp_db-crons > /etc/cron.d/jsonp_db-crons
    chmod u+x /etc/cron.d/jsonp_db-crons

### For Apache

With [`mod_wsgi`](https://modwsgi.readthedocs.org), simply:

    sudo -u www-data bash -c "source /var/www/apache-python-venv/bin/activate && pip install configobj requests"

And the Apache httpd.conf:

    WSGIScriptAlias /path/to/jsonp_db /path/to/jsonp_db.py

### For Nginx

    cat << EOF | sudo tee /etc/init/rpg-bonhomme.conf
    start on startup
    script
        set -o errexit -o nounset -o xtrace
        cd $PWD
        exec >> upstart-stdout.log
        exec 2>> upstart-stderr.log
        date
        pew-in rpg-bonhomme uwsgi --buffer-size 64000 --http :8088 --static-map /=. --manage-script-name --mount /jsonp_db=jsonp_db.py
    end script
    EOF
    service rpg-bonhomme start

And the Nginx configuration:

    location /jsonp_db {
        include uwsgi_params;
        rewrite ^/jsonp_db(.*)$ $1 break;
        proxy_pass http://127.0.0.1:8088;
    }
    location /jsonp_db-tests.ini {
        deny all;
    }


## Validating

    make check
    make test

## Developping

Require a `jsonp_db.db`:

    make
    make run-server

## Ops

### Retrieving a modification key

    function get_mod_key () {
        local layout="${1?}"
        local char_name="${2?}"
        python -c "from jsonp_db import get_modification_key;print('&modification-key='+get_modification_key('${layout}_'+'${char_name}'.lower()))"
    }

### Changing an avatar

    function avatar_chg () {
        local key="${1?}"
        local img="${2?}"
        python -c "import json;from jsonp_db import db_get,db_put;k='$key';v=json.loads(db_get(k));v['avatar']='$img';db_put(k, json.dumps(v))"
    }

# License
Adaptive Public License 1.0 (APL-1.0)

Tl;dr plain English version: https://tldrlegal.com/license/adaptive-public-license-1.0-%28apl-1.0%29

# Resources

Zero JavascriptS dependencies, only 3 Python requirements..
The banner is from [FreebieVectors](http://www.freebievectors.com/fr/apercu-vecteur/150/rubans-banniere-vecteur-libre-symbole/).
All icons are from Google Material Design icons set (CC BY 4.0) : https://github.com/google/material-design-icons
The default avatar image was made by [NoHoDamon](https://www.flickr.com/photos/nohodamon/6485519491/in/photolist-7HSNkN-rzqCWQ-7HSNxA-5JtRYh-apeuDG-6MdYX2-aT6YZz-dRq1jf-dbRcxi-6igHjz-PHJD6-dN5YT-79V2QG-5ShoNL-FAQmN-4mU9vu-9rBg5B-9rBg8M-5ShoaN-5Z7D5b-EMUuT-78gz6Q-Gn5u9-GRGtNs) (CC BY-NC-ND)

# Notes

- why this project name ? It's a reference to the line "T'as tué mon bonhomme !" from the video "Tom et ses chums! Farador D&D" : http://youtu.be/T9FMURHhgzc?t=4m40s
- in case you want to add a character sheet in PDF format, you can use `pdftoppm` then ImageMagick `convert` to get a PNG image file.

