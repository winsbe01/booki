import sqlite3
import sys
from pathlib import Path


BOOKI_DB = Path("~/.local/share/booki/booki.db").expanduser()


def _bootstrap(cur):
    cur.execute("create table if not exists books (hash text, isbn text, title text, author text, page_count text)");
    cur.execute("create table if not exists shelves (name text)");
    cur.execute("create table if not exists shelf_books (hash text, book_id integer, shelf_id integer, foreign key(book_id) references books(rowid), foreign key(shelf_id) references shelves(rowid))");
    cur.execute("create table if not exists shelf_attributes (shelf_id integer, name text, foreign key(shelf_id) references shelves(rowid))");
    cur.execute("create table if not exists shelf_book_attribute (shelf_book_id integer, shelf_attribute_id integer, value text, foreign key(shelf_book_id) references shelf_books(rowid), foreign key(shelf_attribute_id) references shelf_attributes(rowid))");

def load_books(conn):
    theuniverse = Path("~/.local/share/booki/theuniverse").expanduser()
    with open(str(theuniverse), "r") as fil:
        lines = []
        first = True
        for line in fil.readlines():
            if first:
                first = False
                continue
            lines.append(tuple(line.strip().split('|')))

    conn.executemany("insert into books (hash, isbn, title, author, page_count) values (?, ?, ?, ?, ?)", lines)
    conn.commit()
    print(f"added {len(lines)} books...")

def create_shelves(conn, cur):
    shelves_dir = Path("~/.local/share/booki/shelves").expanduser()
    for shelf in shelves_dir.iterdir():
        cur.execute("insert into shelves (name) values (?)", (shelf.name,))
        print(f"creating shelf: {shelf.name}...")
        cur.execute("select rowid from shelves where name = ?", (shelf.name,))
        shelf_id = cur.fetchone()[0]
        with open(str(shelf), "r") as fil:
            lines = []
            first = True
            other_attributes = None
            val_dict = {}
            for line in fil.readlines():
                if first:
                    first = False
                    other_attributes = line.strip().split("|")[2:]
                    continue
                vals = line.strip().split("|")
                hsh, book_hash = vals[0:2]
                if len(vals) > 2:
                    v = vals[2:]
                    max_len = max([len(x) for x in v])
                    if max_len > 0:
                        val_dict[hsh] = vals[2:]
                cur.execute("select rowid from books where hash = ?", (book_hash,))
                book_id = cur.fetchone()[0]
                lines.append((hsh, book_id, shelf_id,))

        conn.executemany("insert into shelf_books (hash, book_id, shelf_id) values (?, ?, ?)", lines)
        print(f" > added {len(lines)} books...")

        attrs = [(shelf_id, x) for x in other_attributes]

        conn.executemany("insert into shelf_attributes (shelf_id, name) values (?, ?)", attrs)
        print(f" > created {len(attrs)} attributes...")

        attr_ids = [v[0] for v in cur.execute("select rowid from shelf_attributes where shelf_id = ?", (shelf_id,))]

        for key, val in val_dict.items():
            cur.execute("select rowid from shelf_books where hash = ?", (key,))
            shelf_book_id = cur.fetchone()[0]
            for idx, v in enumerate(val):
                if v != "":
                    cur.execute("insert into shelf_book_attribute (shelf_book_id, shelf_attribute_id, value) values (?, ?, ?)", (shelf_book_id, attr_ids[idx], v))

        print(f" > added attributes for {len(val_dict)} books...")

    conn.commit()


def main():
    args = sys.argv[1:]
    if len(args) > 1:
        print(f"usage: {sys.argv[0]} [<name_of_database_to_initialize>]")
        sys.exit(1)

    dbfile = BOOKI_DB if len(args) == 0 else Path(args[0])
    if dbfile.exists():
        while True:
            yn = input(f"overwrite {dbfile}! [y/n] ").lower()
            if yn == 'y':
                dbfile.unlink()
                break
            elif yn == 'n':
                print("exiting to prevent an overwrite")
                sys.exit()

    conn = sqlite3.connect(str(dbfile))
    cur = conn.cursor()
    _bootstrap(cur)
    load_books(conn)
    create_shelves(conn, cur)
    conn.close()
    print("...done!")
    print()
    print("the following can be removed from ~/.local/shares/booki:")
    print(" > theuniverse")
    print(" > shelves/ (and all files within)")
    print("thank you for using booki!")


if __name__ == "__main__":
    main()
