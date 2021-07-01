configure:
	if [ ! -d ~/.config/booki ]; \
	then mkdir ~/.config/booki; \
	fi
	if [ ! -d ~/.local/share/booki/shelves ]; \
	then mkdir -p ~/.local/share/booki/shelves; \
	fi

install:
	cp booki.py /usr/local/bin/booki
