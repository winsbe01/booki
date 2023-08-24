# booki
organize your books on the command line

## the toml version!
it's less of a pain than multiple CSVs, and it's easier to manually manipulate
than a sqlite db file. it should be simple to make changes to your library,
with or without booki.

## current usage
* `search` -> search for books in your booki file, filtering by:
  * `--title`
  * `--author`
  * `--on` (which shelves it's on)
* `shelves` -> list all shelves and their counts
* `--show` -> show all details of the matching books (used with `--search`)

## TODO (?)
* add
* discover
* addto
* pull
* new
* extend
* describe
* edit

## install
```
make
sudo make install
```
