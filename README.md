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
* `shelves` -> list all shelves and their counts
* `browse <shelf_name>` -> list all books on the given shelf
* `addto <shelf_name>` -> add book(s) to shelf (book(s) accepted via stdin)
* `new <shelf_name>` -> create a new shelf
* `extend <shelf_name>` -> add new attributes to a shelf
* `describe` -> show additional attributes on shelf (if any)
* `edit` -> edit additional attributes on book (if any) (accepts stdin)
* `show` -> show additional attributes on book (if any) (accepts stdin)

## easter egg
if you create a shelf called 'read', books on that shelf will have a '>' mark in front of them

## install
```
make
sudo make install
```
