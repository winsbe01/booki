#!/usr/bin/env python3
import csv
import sys
import os
import time
import subprocess
import tempfile
import hashlib
import urllib.request
import json
from datetime import datetime
from pathlib import Path

EDITOR = os.environ.get('EDITOR', 'nano')
BOOK_SHORT_ID_LENGTH = 6

base_url = 'https://openlibrary.org/'
isbn_url = 'isbn/'
json_ext = '.json'


class Shelf:

	shelves_dir = '~/.local/share/booki/shelves'
	default_header = ['id', 'book_id']

	def __init__(self, shelf_name, shelf_path=None):
		self.shelf_name = shelf_name
		if not shelf_path:
			shelf_path = Shelf.shelves_dir
		self.shelf_file = Path(shelf_path).expanduser() / self.shelf_name
		self.data = None
		self.book_ids = []
		self.is_changed = False
		if self.exists():
			self.shelf_header = self._get_header_from_shelf()
		else:
			self.shelf_header = Shelf.default_header

	def get_books(self):
		if not self.data:
			self._load_data_and_header()
		return self.data

	def get_book_count(self):
		if not self.data:
			self._load_data_and_header()
		return len(self.data)

	'''
	def get_book_short_ids(self):
		if not self.data:
			self._load_data_and_header()
		return list(self.data.keys())
	'''

	def get_book(self, book_short_id):
		if self.has_book(book_short_id):
			return self.data[book_short_id]
		else:
			return None

	def update_book(self, book_short_id, book):
		if self.has_book(book_short_id):
			self.data[book_short_id] = book
			self.is_changed = True

	def add_book(self, book):
		if not self.data:
			self._load_data_and_header()
		short_id = self._get_short_id(book)
		if short_id not in self.data.keys():
			self.data[short_id] = book
			self.is_changed = True

	def remove_book(self, book_short_id):
		if self.has_book(book_short_id):
			self.data.pop(book_short_id)
			self.is_changed = True

	'''
	def _gen_id(self):
		return hashlib.sha256(str(datetime.now()).encode()).hexdigest()
	'''

	def has_book(self, book_id):
		if not self.data:
			self._load_data_and_header()
		return book_id in self.data.keys()

	def get_universe_books(self):
		if not self.data:
			self._load_data_and_header()
		return self.book_ids

	def exists(self):
		return self.shelf_file.exists()

	def create(self):
		if not self.exists():
			with open(str(self.shelf_file), 'w') as fil:
				header_to_write = '|'.join(self.get_header())
				fil.write(header_to_write + '\n')

	def add_attribute(self, attribute_name):
		if attribute_name in self.shelf_header:
			print("can't add '{}'; already exists".format(attribute_name))
			return False
		if not self.data:
			self._load_data_and_header()
		self.shelf_header.append(attribute_name)
		if self.data:
			for book in self.data.values():
				book[attribute_name] = ""
		self.is_changed = True
		return True

	def get_header(self):
		return self.shelf_header

	def get_header_without_ids(self):
		new_header = self.shelf_header[:]
		new_header.remove('id')
		if 'book_id' in new_header:
			new_header.remove('book_id')
		return new_header

	def save(self):
		if self.exists() and self.is_changed:
			with open(str(self.shelf_file), 'w') as fil:
				writer = csv.DictWriter(fil, lineterminator='\n', delimiter='|', escapechar='\\', quoting=csv.QUOTE_NONE, quotechar='', fieldnames=self.get_header())
				writer.writeheader()
				for book in self.data.values():
					writer.writerow(book)

	def _get_short_id(self, book):
		return book['id'][0:BOOK_SHORT_ID_LENGTH]

	def _get_header_from_shelf(self):
		with open(str(self.shelf_file), 'r') as fil:
			first_line = fil.readline().strip()
		return first_line.split('|')

	def _load_data_and_header(self):
		if self.exists():
			self.data = {}
			with open(str(self.shelf_file), 'r') as fil:
				reader = csv.DictReader(fil, delimiter='|', quoting=csv.QUOTE_NONE)
				self.shelf_header = reader.fieldnames
				book_list = list(reader)
				for book in book_list:
					short_id = self._get_short_id(book)
					self.data[short_id] = book
					if 'book_id' in book:
						self.book_ids.append(book['book_id'])
					else:
						self.book_ids.append(book['id'])


class Universe(Shelf):

	def __init__(self):
		super().__init__('theuniverse', '~/.local/share/booki')
		self.shelf_header = ['id', 'isbn', 'title', 'author', 'page_count']


universe_o = Universe()
if not universe_o.exists():
	universe_o.create()

def _get_shelves():
	shelvesdir = Path('~/.local/share/booki/shelves').expanduser()
	if not shelvesdir.exists():
		shelvesdir.mkdir()

	shelves = {fil.name: Shelf(fil.name) for fil in shelvesdir.iterdir()}
	return {name: shelves[name] for name in sorted(shelves)}

shelves_map = _get_shelves()

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


def print_books(books):
	if len(books) > 0:
		print("\n".join(map(format_book_for_print, books)))

def format_book_for_print(book):

	if 'short_id' not in book:
		book['short_id'] = book['id'][0:BOOK_SHORT_ID_LENGTH]

	if 'book_id' in book:
		book_id = book['book_id']
	else:
		book_id = book['id']

	on_shelves = [name for name, shelf in shelves_map.items() if book_id in shelf.get_universe_books()]

	read_marker = "> " if 'read' in on_shelves else ""
	return "{}  {}{} by {}".format(book['short_id'], read_marker, book['title'], book['author'])


def book_list_sort(book_list):
	by_title = sorted(book_list, key=lambda book: book['title'])
	by_author_first_name = sorted(by_title, key=lambda book: book['author'].split(' ')[0])
	by_author_last_name = sorted(by_author_first_name, key=lambda book: book['author'].split(' ')[-1])
	return by_author_last_name


def _get_shelf_book_tuple(line_in):
	line_in_list = line_in.split(' ')

	# check for bad input
	if len(line_in_list) == 1 and len(line_in_list[0]) == '':
		return None

	shelf_and_id_list = line_in_list[0].split('.')

	if len(shelf_and_id_list) == 1:
		first_item = shelf_and_id_list[0]
		if len(first_item) == 0:
			return None
		# if the first item is not empty, it's a universe book
		else:
			return (universe_o, universe_o.get_book(first_item))

	elif len(shelf_and_id_list) == 2:
		shelf_name = shelf_and_id_list[0]
		book_id = shelf_and_id_list[1]
		if shelf_name not in shelves_map:
			print("shelf doesn't exist: " + shelf_name)
			return None

		shelf = shelves_map[shelf_name]
		return (shelf, shelf.get_book(book_id))

	else:
		return None


def discover(args):

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

	universe_header = universe_o.get_header_without_ids()
	out_map = {x: '' for x in universe_header}
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
	add_book_to_universe(user_input)


def add_book_to_universe(book):
	book_id = hashlib.sha256(str(book).encode()).hexdigest()
	if not universe_o.has_book(book_id[0:BOOK_SHORT_ID_LENGTH]):
		book['id'] = book_id
		universe_o.add_book(book)
		universe_o.save()
		print("added book to universe!")
		print_books([book])
		shelves_in = input("add book to shelves: ")
		shelves_list = [x.strip() for x in shelves_in.split(',')]
		if len(shelves_list) == 1 and shelves_list[0] == "":
			return
		for shelf in shelves_list:
			if shelf in shelves_map:
				add_book_to_shelf(book, shelves_map[shelf])
				print("added to " + shelf)
				shelves_map[shelf].save()
			else:
				print("no shelf named '{}'".format(shelf.shelf_name))
				
	else:
		print("that book already exists!")


def add(args):
	universe_header = universe_o.get_header_without_ids()
	u_map = {x: '' for x in universe_header}
	comment = "adding a book from scratch"
	user_input = user_entry_from_file(u_map, comment)
	add_book_to_universe(user_input)


def _get_books_from_shelf_with_short_ids(shelf):
	book_list = []
	shelf_books = shelf.get_books()
	for shelf_book_id in shelf_books.keys():
		shelf_book = shelf_books[shelf_book_id]
		book = universe_o.get_book(shelf_book['book_id'][0:BOOK_SHORT_ID_LENGTH]).copy()
		book['short_id'] = "{}.{}".format(shelf.shelf_name, shelf_book_id)
		book_list.append(book)
	return book_list


def browse(args):

	if len(args) < 1:
		print("usage: browse <shelf_name> <<search info>>")
		return

	if args[0] not in shelves_map:
		print("no shelf named '" + args[0] + "'")
		return

	shelf = shelves_map[args[0]]
	book_list = _get_books_from_shelf_with_short_ids(shelf)
	if len(args) == 1:
		print_books(book_list)
	else:
		search(args[1:], book_list)


def search(args, list_to_search=None):
	if list_to_search is None:
		list_to_search = universe_o.get_books().values()
	if len(args) == 0:
		sorted_list = book_list_sort(list_to_search)
		print_books(sorted_list)
		return
	if len(args) % 2 != 0:
		print("need an even number of arguments")
		return
	search_types = ['title', 'author']
	if args[0] not in search_types:
		print("search type must be in: " + str(search_types))
		return

	search_term = args[1].lower()
	search_type = "in"
	if search_term[0] == '^' and search_term[-1] == '$':
		search_type = "full_string"
		search_term = search_term[1:-1]
	if search_term[0] == '^':
		search_type = "start"
		search_term = search_term[1:]
	elif search_term[-1] == '$':
		search_type = "end"
		search_term = search_term[0:-1]
	
	ret = []
	for book in list_to_search:
		candidate = book[args[0]].lower()
		if search_type == "in" and search_term in candidate:
			ret.append(book)
		elif search_type == "full_string" and candidate.startswith(search_term) and candidate.endswith(search_term):
			ret.append(book)
		elif search_type == "start" and candidate.startswith(search_term):
			ret.append(book)
		elif search_type == "end" and candidate.endswith(search_term):
			ret.append(book)

	search(args[2:], ret)

def add_book_to_shelf(book, shelf):
	new_id = hashlib.sha256(str(datetime.now()).encode()).hexdigest()

	headers = shelf.get_header_without_ids()
	header_map = {}
	if len(headers) != 0:
		comment = "adding to {}: {}".format(shelf.shelf_name, format_book_for_print(book))
		header_map = {x: "" for x in headers}
		out = user_entry_from_file(header_map, comment)
	
	header_map['id'] = new_id
	header_map['book_id'] = book['id']
	shelf.add_book(header_map)


def addto(args):

	if len(args) != 1:
		print("usage: addto <shelf_name> (accepts stdin)")
		return

	if args[0] not in shelves_map:
		print("no shelf named '" + args[0] + "'")
		return

	shelf = shelves_map[args[0]]

	stdin = list(sys.stdin)

	for line in stdin:

		book = _get_shelf_book_tuple(line)[1]
		add_book_to_shelf(book, shelf)

	shelf.save()
	print("shelved " + str(len(stdin)) + " books")


def pull(args):

	if len(args) != 0:
		print("usage: pull (accepts stdin)")
		return

	stdin = list(sys.stdin)

	for line in stdin:
		shelf, book = _get_shelf_book_tuple(line)

		if shelf.shelf_name == universe_o.shelf_name: # can't pull a book from the universe
			break

		shelf.remove_book(book['id'][0:BOOK_SHORT_ID_LENGTH])
		shelf.save()
		print_books([universe_o.get_book(book["book_id"][0:BOOK_SHORT_ID_LENGTH])])


def shelves(args):
	if len(args) != 0:
		print("usage: 'shelves'")
		return

	for shelf_name, shelf in shelves_map.items():
		print("{}: {} books".format(shelf_name, str(shelf.get_book_count())))


def new(args):
	if len(args) != 1:
		print("usage: 'add <shelf_name'")
		return

	if args[0] in shelves_map:
		print("already have a shelf named '{}'!".format(args[0]))
		return

	shelf = Shelf(args[0])
	new_attributes = input("attributes (sep. by comma): ")
	attr_list = [x.strip() for x in new_attributes.split(',')]
	out_count = _add_attributes_to_shelf(attr_list, shelf)
	shelf.create()
	print("created shelf: " + shelf.shelf_name)


def _add_attributes_to_shelf(attribute_list, shelf):
	cnt = 0
	for att in attribute_list:
		if att != "":
			ret = shelf.add_attribute(att)
			if ret:
				cnt += 1
	return cnt


def show(args):
	if len(args) != 0:
		print("usage: 'edit' (with stdin)")
		return

	stdin = list(sys.stdin)

	for line in stdin:
		
		shelf, book = _get_shelf_book_tuple(line)
		if not shelf or not book:
			print("error: " + str(shelf) + " " + str(book))
			break

		print(line.strip('\n'))
		headers = shelf.get_header_without_ids()
		for attr in headers:
			print(" - {}: {}".format(attr, book[attr]))


def describe(args):
	if len(args) != 1:
		print("usage: 'describe <shelf_name>'")
		return

	if args[0] not in shelves_map:
		print("no shelf named '" + args[0] + "'")
		return

	shelf = shelves_map[args[0]]

	attribute_list = shelf.get_header_without_ids()
	if len(attribute_list) == 0:
		print("no current attributes for " + shelf.shelf_name)
	else:
		print("current attributes of {}: {}".format(shelf.shelf_name, ", ".join(attribute_list)))


def extend(args):
	if len(args) != 1:
		print("usage: 'extend <shelf_name>'")
		return

	if args[0] not in shelves_map:
		print("no shelf named '" + args[0] + "'")
		return

	shelf = shelves_map[args[0]]

	describe(args)

	new_attributes = input("new attributes (sep. by comma): ")
	attr_list = [x.strip() for x in new_attributes.split(',')]
	out_count = _add_attributes_to_shelf(attr_list, shelf)
	shelf.save()
	print("added {} new attribute{} to {}".format(str(out_count), '' if out_count == 1 else 's', shelf.shelf_name))


def edit(args):
	if len(args) != 0:
		print("usage: 'edit' (with stdin)")
		return

	stdin = list(sys.stdin)

	if len(stdin) != 1:
		print("you can only edit one entry at a time!")
		return

	target_shelf, book = _get_shelf_book_tuple(stdin[0])

	if not target_shelf or not book:
		print("error!")
		return

	if book:

		# get the universe book
		if 'book_id' in book:
			universe_book = universe_o.get_book(book['book_id'][0:BOOK_SHORT_ID_LENGTH])
		else:
			universe_book = book

		# get the headers without IDs
		header_list = target_shelf.get_header_without_ids()
		
		if len(header_list) == 0:
			print("no additional data to edit")
			return

		# add data from book
		book_map = { x: book[x] for x in header_list }
		# user edit
		comment = "editing on {}: {}".format(target_shelf.shelf_name, format_book_for_print(universe_book))
		user_input = user_entry_from_file(book_map, comment)
		# update the book on the shelf
		for key, val in user_input.items():
			book[key] = val

		# TODO: this should be cleaner, probably part of a book itself
		if 'short_id' in book:
			book.pop('short_id')
		target_shelf.update_book(book['id'][0:BOOK_SHORT_ID_LENGTH], book)
		target_shelf.save()

		print("updated!")

	else:
		print("can't find book on shelf...")
		return


def main():
	args = sys.argv[1:]

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
		print(" - edit (accepts stdin)")
		print(" - describe <shelf_name>")
		print(" - show (accepts stdin)")
		return

	option_dict = { 'search': search,
					'shelves': shelves,
					'addto': addto,
					'add': add,
					'discover': discover,
					'new': new,
					'browse': browse,
					'extend': extend,
					'edit': edit, 
					'describe': describe, 
					'show': show,
					'pull': pull, }

	if args[0] in option_dict.keys():
		option_dict[args[0]](args[1:])
	else:
		print("bad command")

if __name__ == "__main__":
	main()

