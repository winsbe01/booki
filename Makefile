configure:
	if [ ! -d ~/.config/booki ]; \
	then mkdir ~/.config/booki; \
	fi

install:
	cp booki.py /usr/local/bin/booki
