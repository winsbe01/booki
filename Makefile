configure:
	if [ ! -d ~/.config/booki ]; \
	then mkdir ~/.config/booki; \
	fi
	if [ ! -d ~/.local/share/booki ]; \
	then mkdir -p ~/.local/share/booki; \
	fi

install:
	cp booki.py /usr/local/bin/booki
