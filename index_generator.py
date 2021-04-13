#!/usr/bin/env python3

import argparse, json, os, sys, sqlite3
from contextlib import closing
from itertools import groupby
from jinja2 import Environment, FileSystemLoader


THIS_SCRIPT_PARENT_DIR = os.path.dirname(os.path.realpath(__file__))


def generate_html_index(argv=None):
    args = parse_args(argv)
    if args.db_filepath:
        characters = sorted(get_characters(args.db_filepath), key=lambda c: c['layout'])
        characters_per_layout = {l: list(c) for l, c in groupby(characters, lambda c: c['layout'])}
    else:
        characters_per_layout = {layout: [] for layout in get_layouts()}
    env = Environment(loader=FileSystemLoader(THIS_SCRIPT_PARENT_DIR),
                      autoescape=True, trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(args.html_template)
    print(template.render(characters_per_layout=characters_per_layout))

def parse_args(argv):
    parser = argparse.ArgumentParser(description='Generates an HTML index with a galery of all rpg-bonhomme characters')
    parser.add_argument('html_template')
    parser.add_argument('--db-filepath')
    return parser.parse_args(argv)

def get_characters(db_filepath):
    layouts = get_layouts()
    for key, value in db_list_all(db_filepath):
        matching_layouts = [l for l in layouts if key.startswith(l + '_')]
        assert len(matching_layouts) == 1, key
        layout = matching_layouts[0]
        character = json.loads(value)
        character['layout'] = layout
        character['character_name'] = key[len(layout) + 1:]
        print(layout, character['character_name'], file=sys.stderr)
        yield character

def get_layouts():
    return [os.path.splitext(f)[0] for f in os.listdir(os.path.join(THIS_SCRIPT_PARENT_DIR, 'layout'))]

def db_list_all(db_filepath):
    chars_db = sqlite3.connect(db_filepath, check_same_thread=False)
    # pylint: disable=no-member
    with closing(chars_db.cursor()) as db_cursor:
        db_cursor.execute('SELECT Key, Value FROM KVStore')
        return db_cursor.fetchall()


if __name__ == '__main__':
    generate_html_index()
