import csv
import sys
import os
import time
import subprocess
import tempfile
import pty
from pathlib import Path

EDITOR = os.environ.get('EDITOR', 'nano')

universe = []
universefile = Path("~/.config/booki/theuniverse").expanduser()

shelvesdir = Path('~/.config/booki/shelves').expanduser()

if not shelvesdir.exists():
	shelvesdir.mkdir()

with open(str(universefile), 'r') as bookfil:
	bookreader = csv.DictReader(bookfil, delimiter='|')
	universe = list(bookreader)
	universe_map = {}
	for book in universe:
		universe_map[book['id'][0:10]] = book


def print_books(books):
	for book in books:
		short_id = book['id'][0:10]
		page_count = book['page_count'] if len(book['page_count']) > 0 else '??'
		print("{}  {} by {} ({} pages)".format(short_id, book['title'], book['author'], page_count))


def search(args, list_to_search=universe):
	if len(args) == 0:
		print_books(list_to_search)
		return
	if len(args) % 2 != 0:
		print("need an even number of arguments")
		return
	search_types = ['title', 'author']
	if args[0] not in search_types:
		print("search type must be in: " + str(search_types))
		return
	
	ret = []
	for book in list_to_search:
		if args[1].lower() in book[args[0]].lower():
			ret.append(book)

	search(args[2:], ret)


def shelve(args):

	if len(args) != 1:
		print("need a shelf to shelve to")
		return

	shelf_file = shelvesdir / args[0]

	if not shelf_file.exists():
		print("no shelf named '" + args[0] + "'")
		return

	stdin = list(sys.stdin)

	total = 0
	with open(str(shelf_file), 'a') as fil:
		for line in stdin:
			book_id = line.split(' ')[0]
			fil.write("{}\n".format(book_id))
			total += 1
	print("shelved " + str(total) + " books")

def shelf(args):
	if len(args) != 1:
		print("usage: 'shelf <shelf_name>'")
		return
	shelf_file = shelvesdir / args[0]
	if not shelf_file.exists():
		print("no shelf named '" + args[0] + "'")
		return
	
	book_list = []
	with open(str(shelf_file), 'r') as fil:
		for line in fil:
			book_list.append(universe_map[line.strip('\n')])

	print_books(book_list)
	

def shelves(args):
	if len(args) == 0:
		for shelf in shelvesdir.iterdir():
			with open(str(shelf), 'r') as fil:
				linecount = len(fil.readlines())
				print("{}: {} books".format(shelf.name, str(linecount)))
	elif len(args) == 2 and args[0] == 'add':
		shelf_name = args[1]
		shelf_path = shelvesdir / shelf_name
		shelf_path.touch()
		print("added shelf: " + shelf_name)

	else:
		print("wrong args; use 'add <shelf_name>' or nothing")

def main():
	args = sys.argv[1:]

	if len(args) == 0:
		print("commands: 'search <author|title> <query>', 'shelves', 'shelve', 'shelf <shelf_name>'")
		return

	option_dict = { 'search': search,
					'shelves': shelves,
					'shelve': shelve,
					'shelf': shelf }

	if args[0] in option_dict.keys():
		option_dict[args[0]](args[1:])
	else:
		print("bad command")

if __name__ == "__main__":
	main()

