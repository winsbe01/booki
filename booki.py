#!/usr/bin/env python
import csv
import sys
import os
import time
import subprocess
import tempfile
import pty
import hashlib
import requests
import json
from pathlib import Path

EDITOR = os.environ.get('EDITOR', 'nano')

universe = []
universefile = Path("~/.config/booki/theuniverse").expanduser()

shelvesdir = Path('~/.config/booki/shelves').expanduser()
readfile = Path('~/.config/booki/shelves/read').expanduser()

if not shelvesdir.exists():
	shelvesdir.mkdir()

base_url = 'https://openlibrary.org/'
isbn_url = 'isbn/'
json_ext = '.json'

with open(str(universefile), 'r') as bookfil:
	bookreader = csv.DictReader(bookfil, delimiter='|')
	universe = list(bookreader)
	universe_map = {}
	for book in universe:
		universe_map[book['id'][0:10]] = book

with open(str(readfile), 'r') as readfil:
	readreader = csv.reader(readfil, delimiter='|')
	read_list = []
	for book in list(readreader):
		read_list.append(book[0])

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
		short_id = book['id'][0:10]
		read_marker = ""
		if short_id in read_list:
			read_marker = "> "
		page_count = book['page_count'] if len(book['page_count']) > 0 else '??'
		print("{}  {}{} by {} ({} pages)".format(short_id, read_marker, book['title'], book['author'], page_count))


def book_list_sort(book_list):
	by_title = sorted(book_list, key=lambda book: book['title'])
	by_author_first_name = sorted(by_title, key=lambda book: book['author'].split(' ')[0])
	by_author_last_name = sorted(by_author_first_name, key=lambda book: book['author'].split(' ')[-1])
	return by_author_last_name


def discover(args):

	if len(args) != 1:
		print("need an ISBN")
		return
	
	response = requests.get(base_url + isbn_url + args[0] + json_ext)
	json_text = response.text
	try:
		json_array = json.loads(json_text)
	except json.decoder.JSONDecodeError:
		print("ERROR with: " + isbn)
		return

	universe_header = list(universe[0].keys())
	universe_header.remove('id')
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

	author_response = requests.get(base_url + author_url + json_ext)
	author_json_text = author_response.text
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
	if book_id[0:10] not in universe_map:
		out_string = "{}|{}".format(book_id, "|".join(book.values()))
		with open(str(universefile), 'a') as fil:
			fil.write(out_string + '\n')
		print("added book to universe!")
		book['id'] = book_id
		print_books([book])
	else:
		print("that book already exists!")


def add(args):
	universe_header = list(universe[0].keys())
	universe_header.remove('id')
	u_map = {x: '' for x in universe_header}
	user_input = user_entry_from_file(u_map)
	add_book_to_universe(user_input)


def search(args, list_to_search=universe):
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
					'shelf': shelf,
					'add': add,
					'discover': discover }

	if args[0] in option_dict.keys():
		option_dict[args[0]](args[1:])
	else:
		print("bad command")

if __name__ == "__main__":
	main()

