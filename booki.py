#!/usr/bin/env python3
import tomllib
import os
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from tempfile import NamedTemporaryFile

BOOKI_FILE = Path("~/.local/share/booki/books.toml").expanduser()
EDITOR = os.environ.get("EDITOR", "nano")
OPERATIONAL = ["subcommand", "show"]


def load_books():
    with open(BOOKI_FILE, "rb") as fil:
        data = tomllib.load(fil)
    write_books(data["books"])
    return data["books"]

def format_datum(datum):
    if isinstance(datum, str):
        q = "'" if '"' in datum else '"'
        return f"{q}{datum}{q}"
    elif isinstance(datum, list):
        inner = ", ".join([format_datum(item) for item in datum])
        return f"[ {inner} ]"
    else:
        return datum

def write_books(books):
    with open("out.toml", "w") as fil:
        for book in books:
            fil.write("[[books]]\n")
            for key, val in book.items():
                fil.write(f"{key} = {format_datum(val)}\n")
            fil.write("\n")

def format_authors(authors):
    if isinstance(authors, str):
        return authors
    elif len(authors) == 1:
        return authors[0]
    elif len(authors) == 2:
        return " and ".join(authors)
    else:
        return ", ".join(authors[0:-2]) + " and " + authors[-1]


def show_books(books):
    for book in books:
        print_books([book])
        for key, val in book.items():
            if key in ["id", "title", "author"]:
                continue
            print(f" - {key}: {val}")


def print_books(books):
    for book in books:
        author_str = format_authors(book["author"])
        print(f"\033[4m{book['title']}\033[0m by {author_str}")

def sort_books(books, sort_by):
    return sorted(books, lambda x: x[sort_by])


def filter_single(item, query):
    return query.lower() in item.lower()


def filter_list(items, query):
    for item in items:
        if filter_single(item, query):
            return True
    return False

def filter_items(items, query):
    if isinstance(items, list):
        return filter_list(items, query)
    else:
        return filter_single(items, query)


def user_entry_from_file(book):
    with NamedTemporaryFile(delete=False) as tmpfil:
        for key, val in book.items():
            tmpfil.write(f"{key} = {format_datum(val)}\n".encode("utf-8"))
        tmpfil.flush()
        subprocess.run([EDITOR, tmpfil.name], stdin=sys.stdout)
        with open(tmpfil.name, "rb") as newfil:
            contents = tomllib.load(newfil)
        os.unlink(tmpfil.name)
    return contents

def edit(book):
    target_id = book["id"]
    fixed = user_entry_from_file(book)
    books = load_books()
    for idx, item in enumerate(books):
        if item["id"] == fixed["id"]:
            books[idx] = fixed
            break
    write_books(books)
    return fixed

def search(fltr):
    books = load_books()
    typs = ["title", "author", "on"]
    
    for key, val in vars(fltr).items():
        if key in OPERATIONAL:
            continue
        if val is None:
            continue
        for subval in val:
            books = [x for x in books if key in x and filter_items(x[key], subval)]
        #books = [x for x in books if filter_items(x[key], val)]
    #print_books(books)
    return books

def shelves(_):
    books = load_books()
    all_shelves = {}
    for book in books:
        on = book.get("on", None)
        if on:
            for sh in on:
                if sh in all_shelves:
                    all_shelves[sh] += 1
                else:
                    all_shelves[sh] = 1
    for key in sorted(all_shelves):
        print(f"{key}: {all_shelves[key]} books")
    return []


def parse_args(args):
    parser = ArgumentParser()
    parser.add_argument("--show", action="store_true")
    subs = parser.add_subparsers(required=True, dest="subcommand")
    add_parser = subs.add_parser("add")
    discover_parser = subs.add_parser("discover")
    discover_parser.add_argument("isbn")
    search_parser = subs.add_parser("search")
    search_parser.add_argument("-t", "--title", type=str, nargs="+")
    search_parser.add_argument("-a", "--author", type=str, nargs="+")
    search_parser.add_argument("-o", "--on", type=str, nargs="+")
    shelves_parser = subs.add_parser("shelves")
    return parser.parse_known_args(args)
    #return parser.parse_known_intermixed_args(args)

def sort_books(books):
    by_title = sorted(books, key=lambda x: x["title"])
    def sort_by_author(book):
        author = book["author"]
        if isinstance(author, list):
            author = author[0]
        return author.split(" ")[-1]

    return sorted(by_title, key=sort_by_author)


def main():
    args, extras = parse_args(sys.argv[1:])

    commands = {
        #"add": add,
        #"discover": discover,
        "search": search,
        "shelves": shelves,
    }

    subcommand = args.subcommand
    if subcommand not in commands:
        print(f"no command for '{subcommand}'")
        sys.exit(1)

    books = commands[subcommand](args)

    if "--edit" in extras:
        if len(books) != 1:
            print(f"you can only edit one entry at a time! (got {len(books)})")
            return
        books = [edit(books[0])]

    books_sorted = sort_books(books)
    if "--show" in extras:
        show_books(books_sorted)
    else:
        print_books(books_sorted)


if __name__ == "__main__":
    main()
