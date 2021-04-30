# booki
organize your books on the command line

## usage
make booki aware of books
* `add` -> add a book by typing in the book's information
* `discover <isbn>` -> try to pull in book's information from [OpenLibrary](https://openlibrary.org)

search for booki books
* `search <type> <query>` -> search for a book
  * type - either `title` or `author`
  * query - a string to match (can use ^ and/or $ for beginning/end of string)

manage shelves
* `shelves <add <shelf_name>>` -> without arguments, lists all shelves and their counts. With `add`, lets you create a new shelf.
* `shelf <shelf_name>` -> list all books on the given shelf
* `shelve <shelf_name>` -> add book(s) to shelf (book(s) accepted via stdin)

## easter egg
if you create a shelf called 'read', books on that shelf will have a '>' mark in front of them

## install
```
make
sudo make install
```
