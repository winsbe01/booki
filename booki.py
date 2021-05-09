#!/usr/bin/env python3
import csv
import sys
import os
import time
import subprocess
import tempfile
import pty
import hashlib
import urllib.request
import json
from datetime import datetime
from pathlib import Path

EDITOR = os.environ.get('EDITOR', 'nano')

base_url = 'https://openlibrary.org/'
isbn_url = 'isbn/'
json_ext = '.json'


class Shelf:

	shelves_dir = '~/.config/booki/shelves'
	default_header = ['id', 'book_id']

	def __init__(self, shelf_name, shelf_path=None):
		self.shelf_name = shelf_name
		if not shelf_path:
			shelf_path = Shelf.shelves_dir
		self.shelf_file = Path(shelf_path).expanduser() / self.shelf_name
		self.data = None
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

	def get_book_short_ids(self):
		if not self.data:
			self._load_data_and_header()
		return list(self.data.keys())

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

	def _gen_id(self):
		return hashlib.sha256(str(datetime.now()).encode()).hexdigest()

	def has_book(self, book_id):
		if not self.data:
			self._load_data_and_header()
		return book_id in self.data.keys()

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
			return
		if not self.data:
			self._load_data_and_header()
		self.shelf_header.append(attribute_name)
		for book in self.data.values():
			book[attribute_name] = ""
		self.is_changed = True

	def get_header(self):
		return self.shelf_header

	def get_header_without_ids(self):
		new_header = self.shelf_header[:]
		new_header.remove('id')
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
		return book['id'][0:10]

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


class Universe(Shelf):

	def __init__(self):
		super().__init__('theuniverse', '~/.config/booki')
		self.shelf_header = ['id', 'isbn', 'title', 'author', 'page_count']


universe_o = Universe()
if not universe_o.exists():
	universe_o.create()

def _get_shelves():
	shelvesdir = Path('~/.config/booki/shelves').expanduser()
	if not shelvesdir.exists():
		shelvesdir.mkdir()
	out = {}
	for shelf in shelvesdir.iterdir():
		out[shelf.name] = Shelf(shelf)
	return out

shelves_map = _get_shelves()


def user_entry_from_file(in_map):
	before_contents = '\n'.join(["{}: {}".format(x, in_map[x]) for x in in_map.keys()])
	
	with tempfile.NamedTemporaryFile(delete=False) as tmpfil:
		tmpfil.write(before_contents.encode('utf-8'))
		tmpfil.flush()
		subprocess.run([EDITOR, tmpfil.name], stdin=sys.stdout)
		with open(tmpfil.name, 'r') as newfil:
			after_contents = newfil.read()

		os.unlink(tmpfil.name)

	after_contents_list = after_contents.strip().split('\n')
	for line in after_contents_list:
		line_list = line.split(':')
		key = line_list[0].strip()
		if key in in_map:
			in_map[key] = ":".join(line_list[1:]).strip()

	return in_map


def print_books(books):
	for book in books:
		print_book(book)


def print_book(book):

	if 'short_id' not in book:
		book['short_id'] = book['id'][0:10]

	if 'book_id' in book:
		book_id = book['book_id']
	else:
		book_id = book['id']

	read_marker = ""
	if 'read' in shelves_map.keys():
		for shelf_book_id, shelf_book in shelves_map['read'].get_books().items():
			if shelf_book['book_id'] == book_id:
				read_marker = "> "
	page_count = book['page_count'] if len(book['page_count']) > 0 else '??'
	print("{}  {}{} by {} ({} pages)".format(book['short_id'], read_marker, book['title'], book['author'], page_count))


def book_list_sort(book_list):
	by_title = sorted(book_list, key=lambda book: book['title'])
	by_author_first_name = sorted(by_title, key=lambda book: book['author'].split(' ')[0])
	by_author_last_name = sorted(by_author_first_name, key=lambda book: book['author'].split(' ')[-1])
	return by_author_last_name


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

	universe_header = universe_o.get_header_without_id()
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
	
	user_input = user_entry_from_file(out_map)
	add_book_to_universe(user_input)


def add_book_to_universe(book):
	book_id = hashlib.sha256(str(book).encode()).hexdigest()
	if not universe_o.has_book(book_id[0:10]):
		book['id'] = book_id
		universe_o.add_book(book)
		universe_o.save()
		print("added book to universe!")
		print_books([book])
	else:
		print("that book already exists!")


def add(args):
	universe_header = universe_o.get_header_without_id()
	u_map = {x: '' for x in universe_header}
	user_input = user_entry_from_file(u_map)
	add_book_to_universe(user_input)


def browse(args):

	if len(args) != 1:
		print("usage: browse <shelf_name>")
		return

	shelf = Shelf(args[0])

	if not shelf.exists():
		print("no shelf named '" + shelf.shelf_name + "'")
		return

	shelf_books = shelf.get_books()
	for shelf_book_id in shelf_books.keys():
		shelf_book = shelf_books[shelf_book_id]
		book = universe_o.get_book(shelf_book['book_id'][0:10])
		book['short_id'] = "{}.{}".format(shelf.shelf_name, shelf_book_id)
		print_book(book)


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

def addto(args):

	if len(args) != 1:
		print("usage: addto <shelf_name> (accepts stdin)")
		return

	shelf = Shelf(args[0])

	if not shelf.exists():
		print("no shelf named '" + shelf.shelf_name + "'")
		return

	stdin = list(sys.stdin)

	for line in stdin:

		new_id = hashlib.sha256(str(datetime.now()).encode()).hexdigest()

		book_short_id = line.split(' ')[0]
		book = universe_o.get_book(book_short_id)

		headers = shelf.get_header_without_ids()
		header_map = {}
		if len(headers) != 0:
			header_map = {x: "" for x in headers}
			out = user_entry_from_file(header_map)
		
		header_map['id'] = new_id
		header_map['book_id'] = book['id']
		shelf.add_book(header_map)

	shelf.save()
	print("shelved " + str(len(stdin)) + " books")


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

	shelf = Shelf(args[0])
	if shelf.exists():
		print("already have a shelf named '{}'!".format(shelf.shelf_name))
		return

	shelf.create()
	print("added shelf: " + shelf.shelf_name)


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
		print(" - browse <shelf_name>")
		print(" - shelve <shelf_name> (accepts stdin)")
		print(" - new <shelf_name>")
		return

	option_dict = { 'search': search,
					'shelves': shelves,
					'addto': addto,
					'add': add,
					'discover': discover,
					'new': new,
					'browse': browse, }

	if args[0] in option_dict.keys():
		option_dict[args[0]](args[1:])
	else:
		print("bad command")

if __name__ == "__main__":
	main()

