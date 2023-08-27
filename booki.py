#!/usr/bin/env python3
import tomllib
import json
import os
import subprocess
import sys
import urllib.request
from argparse import ArgumentParser
from pathlib import Path
from shutil import copy2
from tempfile import NamedTemporaryFile

BOOKI_FILE = Path("~/.local/share/booki/books.toml").expanduser()
EDITOR = os.environ.get("EDITOR", "nano")
OPERATIONAL = ["subcommand", "show"]


def load_books():
    with open(BOOKI_FILE, "rb") as fil:
        data = tomllib.load(fil)
    write_books(data["books"])
    return data["books"]


def get_attrs(books=None):
    if not books:
        books = load_books()
    attrs = []
    for book in books:
        for key in book:
            if key not in attrs:
                attrs.append(key)
    return attrs


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
    copy2(f"{BOOKI_FILE}", f"{BOOKI_FILE}.bak")
    with open(f"{BOOKI_FILE}", "w") as fil:
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
    if isinstance(item, str):
        return query.lower() in item.lower()
    try:
        int_item = int(item)
        int_query = int(query)
        return int_query == int_item
    except ValueError:
        print(f"{item} is not an int?")
        return False


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


def user_entry_from_file(book, err=None):
    with NamedTemporaryFile(delete=False) as tmpfil:
        for key, val in book.items():
            tmpfil.write(f"{key} = {format_datum(val)}\n".encode("utf-8"))
        tmpfil.flush()

        while True:
            subprocess.run([EDITOR, tmpfil.name], stdin=sys.stdout)
            with open(tmpfil.name, "rb") as newfil:
                try:
                    contents = tomllib.load(newfil)
                    break
                except tomllib.TOMLDecodeError as err:
                    print(f"parse error: {err}")
                    resp = input("edit again? (y/n) ")
                    if resp.lower() == "y":
                        continue

                    # we aren't re-editing, so we'll keep the original
                    print("aborting edit")
                    contents = book
                    break
        os.unlink(tmpfil.name)
    return contents

def add(_):
    books = load_books()
    attrs = get_attrs(books)
    empty_book = {attr: "" for attr in attrs if attr != "id"}
    filled_book = user_entry_from_file(empty_book)
    books.append(filled_book)
    write_books(books)
    show_books([filled_book])
    return []

def discover(args):
    base_url = "https://openlibrary.org"
    isbn_url = "isbn"

    full_isbn_url = f"{base_url}/{isbn_url}/{args.isbn}.json"
    with urllib.request.urlopen(full_isbn_url) as url:
        json_text = url.read().decode("utf-8")

    try:
        json_obj = json.loads(json_text)
    except json.decoder.JSONDecodeError as err:
        print(f"error with {args.isbn}: {err}")
        return []

    # fields i'm interested in
    books = load_books()
    attrs = get_attrs(books)
    book_dict = {attr: None for attr in attrs if attr != "id"}
    book_dict["isbn"] = args.isbn
    book_dict["title"] = json_obj.get("title", None)
    book_dict["author"] = json_obj.get("by_statement", None)
    book_dict["pages"] = json_obj.get("number_of_pages", None)

    # get author things
    authors = json_obj.get("authors", None)
    if authors:
        names = []
        for author in authors:
            full_author_url = f"{base_url}/{author['key']}.json"
            with urllib.request.urlopen(full_author_url) as url:
                author_json_text = url.read().decode("utf-8")

            try:
                author_json_obj = json.loads(author_json_text)
            except json.decoder.JSONDecodeError:
                author_json_obj = None

            if author_json_obj:
                if name := author_json_obj.get("name", None):
                    names.append(name)
        if len(names) == 1:
            book_dict["author"] = names[0]
        else:
            book_dict["author"] = names

    filled_book = user_entry_from_file(book_dict)
    books.append(filled_book)
    write_books(books)
    return [filled_book]

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


def parse_args(args, book_attrs):
    parser = ArgumentParser()
    parser.add_argument("--show", action="store_true")
    subs = parser.add_subparsers(required=True, dest="subcommand")
    add_parser = subs.add_parser("add")
    discover_parser = subs.add_parser("discover")
    discover_parser.add_argument("isbn")
    search_parser = subs.add_parser("search")
    for attr in book_attrs:
        search_parser.add_argument(f"--{attr}", type=str, nargs="+")
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
    attrs = get_attrs()
    args, extras = parse_args(sys.argv[1:], attrs)

    commands = {
        "add": add,
        "discover": discover,
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
