This project provides the following features:
- locally load & save your character from JSON files.
- only require a web browser (and an Internet connection to use the remote storage feature).
- optionnaly you can save your character on a remote server,
which enables you to share it with others simply by providing a unique URL.
- add character sheets from any game.

# Examples

- [Lythes](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=Dedale&name=lythes), an android from the French RPG [Dédale](http://lab00.free.fr/sommaire/home.htm).
- [Kathelyn Terblanche](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=Absence&name=kathelyn_terblanche) & [Raphaelle Lepercq](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=Absence&name=raphaelle_lepercq), two characters from a 'one-shot' RPG called 'Absence'.
- [Atharès](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=InCognito1&name=athares), a character from the second campaign of my RPG game 'In Cognito'.
- [Ted Sand](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=Allegoria&name=ted_sand) & [Jacob Valens](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=Allegoria&name=jacob_valens) from my RPG campaign 'Allegoria'.

# Usage & asumptions

- a ?layout= URL parameter must always be provided to _character-sheet.html_.
- this _layout_ must match the name of a .css file in **css/**, and a .png character sheet image in **img/**.
- input (or textarea) fields are defined once and only once by rules starting with 'input#<name>' in the layout.css,
and they must be the only selectors starting that way in the file.
Non-textual fields must be specified as 'input[type=.+]#<name>'
- the _layout.css_ MUST define a text input with id 'name'.
- (up)loading a new character currently only replace inputs defined in the provided file,
non-redefined caracteristics will keep their old value.

# jsonp-db

First, a word of warning: **trusting a 3rd party JSONP API is a big confidence commitment / security risk**.
More details [here](http://security.stackexchange.com/a/23439).

That being said, this WSGI app won't do anything nasty.
It's a simple key-value store using a SQLite DB (yes, Redis may have been a better fit), developped to allow simple GET/PUT through JSONP.

The **key** MUST be a string, and the **value** MUST be a JSON dictionary.
There are some length limitations currently hardcoded at the top of the Python file.
In case of a lookup error, the return value will be '{}', else it will returns {key: value} or throw an error
(calling 'alert' if using JSONP, else displaying an HTML error page).
- [Atharès](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=InCognito1&name=athares), a character from the second campaign of my RPG game 'In Cognito'.
- [Atharès](https://chezsoi.org/lucas/rpg-bonhomme/character-sheet.html?layout=InCognito1&name=athares), a character from the second campaign of my RPG game 'In Cognito'.

## Setup

    sqlite3 jsonp-db.db 'CREATE TABLE KVStore(Key TEXT PRIMARY KEY, Value TEXT);'
    chmod ugo+rw jsonp-db.db
    sudo ln -s jsonp-db-backup.sh /etc/cron.daily/jsonp-db-backup.sh

## Testing

    curl -X POST -d name="John Doe" https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/john_doe
    curl https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/john_doe
    curl 'https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/john_doe?_do=put&name=John%20Doe'
    curl https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/john_doe&callback=foo

Error handling:

    curl https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db # raises a 404
    curl https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/a/ # raises a 404
    curl https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/unset_key # returns {}
    key=$(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 101 | tr -d '\n')
    curl -X PUT -d 0=1 https://chezsoi.org/lucas/rpg-bonhomme/jsonp-db/$key # raises a ValueError 404

# Resources

Zero dependencies, all coded in vanilla Javascript.
All icons are from Google Material Design icons set (CC BY 4.0) : https://github.com/google/material-design-icons

# Notes

- why the name ? It's a reference to the video "Tom et ses chums! Farador D&D" : http://youtu.be/T9FMURHhgzc?t=4m40s
- in case the character sheet you want to use is in PDF format, you can use `pdftoppm` then ImageMagick `convert` to get PNG image file.

