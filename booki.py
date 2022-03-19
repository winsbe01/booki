#!/usr/bin/env python3
import sqlite3
import sys
import os
from collections import namedtuple
import subprocess
import tempfile
import hashlib
import urllib.request
import json
import random
from datetime import datetime
from pathlib import Path

Book = namedtuple("Book", ("shelf_name", "hash", "isbn", "title", "author", "page_count"))

EDITOR = os.environ.get('EDITOR', 'nano')

base_url = 'https://openlibrary.org/'
isbn_url = 'isbn/'
json_ext = '.json'

BOOKI_DB = Path("~/.local/share/booki/booki.db").expanduser()


def _bootstrap(conn, cur):
    cur.execute("create table if not exists books (hash text, isbn text, title text, author text, page_count integer)");
    cur.execute("create table if not exists shelves (name text)");
    cur.execute("create table if not exists shelf_books (hash text, book_id integer, shelf_id integer, foreign key(book_id) references books(rowid), foreign key(shelf_id) references shelves(rowid))");
    cur.execute("create table if not exists shelf_attributes (shelf_id integer, name text, foreign key(shelf_id) references shelves(rowid))");
    cur.execute("create table if not exists shelf_book_attribute (shelf_book_id integer, shelf_attribute_id integer, value text, foreign key(shelf_book_id) references shelf_books(rowid), foreign key(shelf_attribute_id) references shelf_attributes(rowid))");

def get_all_books(cur):
    return [Book(*record) for record in cur.execute("select null, * from books")]

def get_all_shelf_books(cur, shelf):
    return [Book(*record) for record in 
        cur.execute("""
            select s.name, sb.hash, b.isbn, b.title, 
            b.author, b.page_count from shelves s 
            inner join shelf_books sb 
            on s.rowid = sb.shelf_id inner join books b 
            on sb.book_id = b.rowid where s.name = ?""", 
            (shelf,))]

def get_book_by_hash(cur, book_hash):
    cur.execute("""
        select rowid from books where hash like ? || '%'
        """,(book_hash,))
    book_id = cur.fetchone()
    return book_id if book_id is None else book_id[0]

def get_book_info_by_hash(cur, book_hash):
    cur.execute("""
        select null, * from books where hash like ? || '%'
        """,(book_hash,))
    book_info = Book(*cur.fetchone())
    return book_info

def get_book_attributes_by_hash(cur, shelf_book_hash):
    shelf_name, hsh = shelf_book_hash.split(".")
    cur.execute("""
        select sa.name, ba.rowid, ba.value, sa.rowid, sb.rowid from shelves s inner join shelf_books sb
        on s.rowid = sb.shelf_id inner join shelf_attributes 
        sa on s.rowid = sa.shelf_id left outer join shelf_book_attribute ba
        on sb.rowid = ba.shelf_book_id and sa.rowid = ba.shelf_attribute_id 
        where s.name = ? and sb.hash like ? || '%'
        """, (shelf_name, hsh))
    attr_map = {name: (rowid, value, sarowid, sbrowid) for name, rowid, value, sarowid, sbrowid in cur.fetchall()}
    return attr_map

def get_shelf_book_by_hash(cur, shelf_book_hash):
    shelf_name, hsh = shelf_book_hash.split(".")
    cur.execute("""
        select sb.rowid, sb.book_id from shelves s 
        inner join shelf_books sb on s.rowid = sb.shelf_id 
        where s.name = ? and sb.hash like ? || '%'
        """,(shelf_name, hsh))
    shelf_book_info = cur.fetchone()
    return shelf_book_info

def gen_hash(in_val=datetime.now()):
    salt = random.getrandbits(16)
    new_str = str(in_val) + str(salt)
    return hashlib.sha256(str(new_str).encode()).hexdigest()

def user_entry_from_file(in_map, comment=None):

    before_contents = ""

    if comment is not None:
        before_contents = "# {}\n".format(comment)
    before_contents += '\n'.join(["{}: {}".format(x, in_map[x]) for x in in_map.keys()])
    
    with tempfile.NamedTemporaryFile(delete=False) as tmpfil:
        tmpfil.write(before_contents.encode('utf-8'))
        tmpfil.flush()
        subprocess.run([EDITOR, tmpfil.name], stdin=sys.stdout)
        with open(tmpfil.name, 'r') as newfil:
            after_contents = newfil.read()

        os.unlink(tmpfil.name)

    after_contents_list = after_contents.strip().split('\n')
    for line in after_contents_list:
        if line[0] == "#":
            continue
        line_list = line.split(':')
        key = line_list[0].strip()
        if key in in_map:
            in_map[key] = ":".join(line_list[1:]).strip()

    return in_map

def print_books(book_list):
    for book in book_list:
        print_book(book)

def print_book(book):
    print(format_book_for_print(book))

def format_book_for_print(book):
    if book.shelf_name is None:
        short_id = book.hash[0:6]
    else:
        short_id = f"{book.shelf_name}.{book.hash[0:6]}"
    return f"{short_id}  {book.title} by {book.author}"

def add_book(conn, cur, info):
    hsh = gen_hash(info)
    vals = [hsh] + list(info.values())

    cur.execute("""
        insert into books (hash, isbn, title, author, page_count) 
        values (?, ?, ?, ?, ?)
    """, tuple(vals))

    book_info = get_book_info_by_hash(cur, hsh)
    print("added a book!")
    print_book(book_info)
    book_id = get_book_by_hash(cur, hsh)
    shelves_in = input("add book to shelves: ")
    shelves_list = [x.strip() for x in shelves_in.split(',')]
    if len(shelves_list) == 1 and shelves_list[0] == "":
        return
    for shelf in shelves_list:

        shelf_id = cur.execute("""
                        select rowid from shelves where name = ?
                    """, (shelf,)).fetchone()

        if shelf_id is None:
            print(f"no shelf named '{shelf}'")
            continue
        
        shelf_id = shelf_id[0]
        hsh = gen_hash()
        cur.execute("""
            insert into shelf_books (hash, book_id, shelf_id)
            values (?, ?, ?)
        """, (hsh, book_id, shelf_id))
        print(f"added to {shelf}")

    conn.commit()

# functions
def add(conn, cur, args):
    fields = ["isbn", "title", "author", "page_count"]
    out_map = {x: '' for x in fields}
    comment = "adding a book from scratch"
    user_input = user_entry_from_file(out_map, comment)
    add_book(conn, cur, user_input)

def addto(conn, cur, args):
    if len(args) != 1:
        print("usage: addto <shelf_name> (accepts stdin)")
        return

    shelf_id = cur.execute("""
        select rowid from shelves where name = ?
        """, (args[0],)).fetchone()

    if shelf_id is None:
        print(f"no shelf named '{args[0]}'")
        return

    shelf_id = shelf_id[0]
    cur.execute("""
        select rowid, name from shelf_attributes where shelf_id = ?
    """, (shelf_id,))
    attributes = {x[1]: x[0] for x in cur.fetchall()}

    stdin = list(sys.stdin)
    for line in stdin:
        book_id = get_book_by_hash(cur, line.split(" ")[0])
        hsh = gen_hash()
        cur.execute("""
            insert into shelf_books (hash, book_id, shelf_id) values (?, ?, ?)
        """, (hsh, book_id, shelf_id))
        if len(attributes) != 0:
            stripped_line = line.strip("\n")
            out_map = {val: "" for val in attributes.keys()}
            comment = f"adding to {args[0]}: {stripped_line}"
            user_input = user_entry_from_file(out_map, comment)

            cur.execute("""
                select rowid from shelf_books where hash = ?
            """, (hsh,))
            shelf_book_id = cur.fetchone()[0]
            for key, val in user_input.items():
                if len(val) > 1:
                    cur.execute("""
                        insert into shelf_book_attribute (shelf_book_id, shelf_attribute_id, value)
                            values (?, ?, ?)
                    """, (shelf_book_id, attributes[key], val))

    conn.commit()

def browse(conn, cur, args):
    if len(args) < 1:
        print("usage: browse <shelf name> <<search info>>")
        return
    shelf_name = args[0]
    cur.execute("select * from shelves where name = ?", (shelf_name,))
    if cur.fetchone() is None:
        print(f"no shelf named '{shelf_name}'")
        return

    search(conn, cur, args[1:], shelf=args[0])
    return

def describe(conn, cur, args):
    if len(args) != 1:
        print("usage: 'describe <shelf_name>'")
        return
    shelf_name = args[0]
    cur.execute("select rowid from shelves where name = ?", (shelf_name,))
    shelf = cur.fetchone()
    if shelf is None:
        print(f"no shelf named '{shelf_name}'")
        return

    attrs = [val[0] for val in cur.execute("select name from shelf_attributes where shelf_id = ?", shelf)]
    if len(attrs) == 0:
        print(f"no current attributes for {shelf_name}")
    else:
        print(f"current attributes of {shelf_name}: {', '.join(attrs)}")
    return

def discover(conn, cur, args):

    if len(args) != 1:
        print("need an ISBN")
        return

    full_url = base_url + isbn_url + args[0] + json_ext
    with urllib.request.urlopen(full_url) as fil:
        json_text = fil.read().decode('utf-8')

    try:
        json_array = json.loads(json_text)
    except json.decoder.JSONDecodeError:
        print("ERROR with: " + isbn)
        return

    fields = ["isbn", "title", "author", "page_count"]
    out_map = {x: '' for x in fields}
    out_map['isbn'] = args[0]

    author_url = ''

    if 'title' in json_array:
        out_map['title'] = json_array['title']
    if 'authors' in json_array:
        author_url = json_array['authors'][0]['key']
    if 'number_of_pages' in json_array:
        out_map['page_count'] = json_array['number_of_pages']
    if 'by_statement' in json_array:
        out_map['author'] = json_array['by_statement']

    full_author_url = base_url + author_url + json_ext
    with urllib.request.urlopen(full_author_url) as fil:
        author_json_text = fil.read().decode('utf-8')
    author_json_array = None
    try:
        author_json_array = json.loads(author_json_text)
    except json.decoder.JSONDecodeError:
        pass

    if author_json_array and 'name' in author_json_array:
        out_map['author'] = author_json_array['name']
    
    comment = "discovering a book from ISBN" + args[0]
    user_input = user_entry_from_file(out_map, comment)
    add_book(conn, cur, user_input)

def edit(conn, cur, args):
    if len(args) != 0:
        print("usage: 'edit' (with stdin)")
        return

    stdin = list(sys.stdin)
    if len(stdin) != 1:
        print("you can only edit one entry at a time!")
        return

    shelf_book_hash = stdin[0].split(" ")[0]
    attr_map = get_book_attributes_by_hash(cur, shelf_book_hash)

    if len(attr_map) == 0:
        print("no additional data to edit")
        return

    book_map = {}
    for key, vals in attr_map.items():
        val = vals[1] if vals[1] is not None else ""
        book_map[key] = val

    comment = f"editing on {shelf_book_hash[0]}: {stdin[0].strip()}"
    user_input = user_entry_from_file(book_map, comment)
    for key, val in user_input.items():
        shelf_book_attribute_id, attribute_value, shelf_attribute_id, shelf_book_id = attr_map[key]
        if val == "" and shelf_book_attribute_id is not None:
            cur.execute("""
                delete from shelf_book_attribute where rowid = ?
            """, (shelf_book_attribute_id,))
        elif len(val) > 1:
            if val != attribute_value and shelf_book_attribute_id is not None:
                cur.execute("""
                    update shelf_book_attribute set value = ? where rowid = ?
                """, (val, shelf_book_attribute_id))
            elif val != attribute_value and shelf_book_attribute_id is None:
                cur.execute("""
                    insert into shelf_book_attribute (shelf_book_id, shelf_attribute_id, value)
                    values (?, ?, ?)
                """, (shelf_book_id, shelf_attribute_id, val))

        conn.commit()

def extend(conn, cur, args):
    if len(args) != 1:
        print("usage: 'extend <shelf_name>'")
        return

    shelf_name = args[0]
    shelf_query = "select rowid from shelves where name = ?"
    cur.execute(shelf_query, (shelf_name,))
    shelf_id = cur.fetchone()
    if shelf_id is None:
        print(f"no shelf named '{shelf_name}'")
        return

    describe(conn, cur, args)
    new_attributes = input("new attributes (sep. by comma): ")
    attr_list = [x.strip() for x in new_attributes.split(",") if x.strip() != ""]
    if len(attr_list) != 0:
        cur.execute(shelf_query, (shelf_name,))
        shelf_id = cur.fetchone()[0]
        to_tuple_list = [(shelf_id, attribute) for attribute in attr_list]
        cur.executemany("""
            insert into shelf_attributes (shelf_id, name) values (?, ?)
        """, to_tuple_list)

    conn.commit()
    print(f"added {len(attr_list)} new attribute{'' if len(attr_list) == 1 else 's'} to {shelf_name}")


def new(conn, cur, args):
    if len(args) != 1:
        print("usage: 'new <shelf_name>'")
        return

    shelf_name = args[0]
    shelf_query = "select rowid from shelves where name = ?"
    cur.execute(shelf_query, (shelf_name,))
    shelf_id = cur.fetchone()
    if shelf_id is not None:
        print(f"already have a shelf named '{shelf_name}'!")
        return

    cur.execute("""
        insert into shelves (name) values (?)
    """, (shelf_name,))

    new_attributes = input("attributes (sep. by comma): ")
    attribute_list = [x.strip() for x in new_attributes.split(",") if x.strip() != ""]
    if len(attribute_list) != 0:
        cur.execute(shelf_query, (shelf_name,))
        shelf_id = cur.fetchone()[0]
        to_tuple_list = [(shelf_id, attribute) for attribute in attribute_list]
        print(to_tuple_list)
        cur.executemany("""
            insert into shelf_attributes (shelf_id, name) values (?, ?)
        """, to_tuple_list)
    print(f"created shelf '{shelf_name}' with {len(attribute_list)} attribute{'' if len(attribute_list) == 1 else 's'}")
    conn.commit()
 

def pull(conn, cur, args):
    if len(args) != 0:
        print("usage: pull (accepts stdin)")
        return

    stdin = list(sys.stdin)

    for line in stdin:
        shelf_book = line.split(" ")[0]
        if "." not in shelf_book:
            print("can't remove from the top at this time!")
            return
        shelf_book_id, book_id = get_shelf_book_by_hash(cur, line.split(" ")[0])
        cur.execute("""
            delete from shelf_book_attribute where shelf_book_id = ?
        """, (shelf_book_id,))
        cur.execute("""
            delete from shelf_books where rowid = ?
        """, (shelf_book_id,))
        print_books([Book(*record) for record in cur.execute(f"select null, * from books where rowid = ?",(book_id,))])

    conn.commit()


def search(conn, cur, args, list_to_search=None, shelf=None):

    if list_to_search is None:
        if shelf is None:
            list_to_search = get_all_books(cur)
        else:
            list_to_search = get_all_shelf_books(cur, shelf)

    if len(args) == 0:
        print_books(list_to_search)
        return

    search_types = ["title", "author"]
    in_types = [typ for idx, typ in enumerate(args) if idx % 2 == 0]  # get even indexed args
    if not set(in_types) <= set(search_types):
        print(f"search type must be in: {search_types}")
        return

    if len(args) % 2 != 0:
        print("must be an even number of arguments")
        return

    start_perc = end_perc = "%"
    where_list = []
    search_args = args
    while len(search_args) != 0:
        typ, term = search_args[0:2]

        if term[0] == "^":
            start_perc = ""
            term = term[1:]
        if term[-1] == "$":
            end_perc = ""
            term = term[:-1]

        where_list.append((typ, term))
        search_args = search_args[2:]

    if len(where_list) != 0:
        where_record = " and ".join([f"lower({item[0]}) like '{start_perc}' || ? || '{end_perc}'" for item in where_list])
        q_list = [item[1] for item in where_list]
        if shelf is None:
            out = [Book(*record) for record in cur.execute(f"select null, * from books where {where_record}", tuple(q_list))]
        else:
            q_list.insert(0, shelf)
            out = [Book(*record) for record in 
                cur.execute(f"""
                    select s.name, sb.hash, b.isbn, b.title, 
                    b.author, b.page_count from shelves s 
                    inner join shelf_books sb 
                    on s.rowid = sb.shelf_id inner join books b
                    on sb.book_id = b.rowid where s.name = ? 
                    and {where_record}""", tuple(q_list))]
        print_books(out)


def shelves(conn, cur, args):
    if len(args) != 0:
        print("usage: 'shelves'")
        return

    cur.execute(
        '''
        select s.name, ifnull(sb.book_count, 0) as book_count 
        from shelves s 
        left outer join 
        (select shelf_id, count(*) as book_count 
        from shelf_books group by shelf_id) sb 
        on s.rowid = sb.shelf_id
        order by s.name
        ''')

    for shelf_name, book_count in cur.fetchall():
        s = "" if book_count == 1 else "s"
        print(f"{shelf_name}: {book_count} book{s}")


def show(conn, cur, args):
    if len(args) != 0:
        print("usage: 'edit' (with stdin)")
        return

    stdin = list(sys.stdin)
    for line in stdin:
        print(line.strip("\n"))
        shelf_book = line.split(" ")[0]
        if "." in shelf_book:
            shelf_book_id, book_id = get_shelf_book_by_hash(cur, shelf_book)
            attrs = {name: value for name, value in cur.execute("""
                select sa.name, sba.value from shelf_attributes sa
                inner join shelf_book_attribute sba on sa.rowid = sba.shelf_attribute_id
                where sba.shelf_book_id = ?
            """,(shelf_book_id,))}
        else:
            book_id = get_book_by_hash(cur, shelf_book)
            
            cur.execute(f"select null, * from books where rowid = ?",(book_id,))
            book = Book(*cur.fetchone())
            attrs = {name: getattr(book, name) for name in book._fields if name not in ("hash", "shelf_name") and getattr(book, name) != ""}

        for key, val in attrs.items():
            print(f" - {key}: {val}")


def main():
    args = sys.argv[1:]

    conn = sqlite3.connect(BOOKI_DB)
    cur = conn.cursor()
    _bootstrap(conn, cur)

    if len(args) == 0:
        print("booki!")
        print("find new books:")
        print(" - add")
        print(" - discover <isbn>")
        print("search for books")
        print(" - search <author|title> <query>")
        print("manage shelves")
        print(" - shelves")
        print(" - browse <shelf_name> <<search terms>>")
        print(" - addto <shelf_name> (accepts stdin)")
        print(" - pull (accepts stdin)")
        print(" - new <shelf_name>")
        print(" - extend <shelf_name>")
        print(" - describe <shelf_name>")
        print(" - show (accepts stdin)")
        return

    option_dict = { 'add': add,
                    'addto': addto,
                    'browse': browse, 
                    'describe': describe,
                    'discover': discover,
                    'edit': edit,
                    'extend': extend,
                    'new': new,
                    'pull': pull,
                    'search': search,
                    'shelves': shelves, 
                    'show': show }

    if args[0] in option_dict.keys():
        option_dict[args[0]](conn, cur, args[1:])
    else:
        print("bad command")

    conn.close()


if __name__ == "__main__":
    main()

