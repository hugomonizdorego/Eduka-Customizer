# Eduka-Customizer - ISO builder for Debian-based distributions
VERSION   = 0.15.0~alpha
PYTHON   ?= python3
DESTDIR  ?=
PREFIX   ?= /usr
LIBDIR    = $(PREFIX)/lib/eduka-customizer
DATADIR   = $(PREFIX)/share/eduka-customizer
INSTALL   = install
GIT       = git

all: check

check:
	$(PYTHON) -m compileall -q eduka_customizer
	@$(PYTHON) -m pyflakes eduka_customizer/core eduka_customizer/gui eduka_customizer/cli.py tests 2>/dev/null || echo "pyflakes not installed, skipped"

test:
	$(PYTHON) -m pytest -q tests

install:
	$(INSTALL) -d $(DESTDIR)$(LIBDIR) $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(DATADIR) \
		$(DESTDIR)/etc/eduka-customizer $(DESTDIR)$(PREFIX)/share/applications \
		$(DESTDIR)$(PREFIX)/share/polkit-1/actions \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps \
		$(DESTDIR)$(PREFIX)/share/metainfo $(DESTDIR)$(PREFIX)/share/man/man1 \
		$(DESTDIR)$(PREFIX)/share/doc/eduka-customizer/examples
	cp -r eduka_customizer $(DESTDIR)$(LIBDIR)/
	find $(DESTDIR)$(LIBDIR) -name '__pycache__' -prune -exec rm -rf {} +
	find $(DESTDIR)$(LIBDIR) -type f -exec chmod 644 {} +
	sed -e 's|@LIBDIR@|$(LIBDIR)|g' -e 's|@DATADIR@|$(DATADIR)|g' data/eduka-customizer.in \
		> $(DESTDIR)$(PREFIX)/bin/eduka-customizer
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/eduka-customizer-pkexec.in \
		> $(DESTDIR)$(PREFIX)/bin/eduka-customizer-pkexec
	chmod 755 $(DESTDIR)$(PREFIX)/bin/eduka-customizer $(DESTDIR)$(PREFIX)/bin/eduka-customizer-pkexec
	$(INSTALL) -m644 data/exclude.list data/desktops.json data/languages.json data/profiles.json data/apps.json data/themes.json $(DESTDIR)$(DATADIR)/
	$(INSTALL) -m644 data/eduka-customizer.conf $(DESTDIR)/etc/eduka-customizer/eduka-customizer.conf
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/org.edukasaun.customizer.desktop.in \
		> $(DESTDIR)$(PREFIX)/share/applications/org.edukasaun.customizer.desktop
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/org.edukasaun.customizer.policy.in \
		> $(DESTDIR)$(PREFIX)/share/polkit-1/actions/org.edukasaun.customizer.policy
	$(INSTALL) -m644 data/org.edukasaun.customizer.metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/
	$(INSTALL) -m644 icons/eduka-customizer.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/
	for s in 16 22 24 32 48 64 128 256; do \
		$(INSTALL) -D -m644 icons/hicolor/$${s}x$${s}/apps/eduka-customizer.png \
			$(DESTDIR)$(PREFIX)/share/icons/hicolor/$${s}x$${s}/apps/eduka-customizer.png; done
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/icons/menu
	$(INSTALL) -m644 data/icons/menu/*.svg data/icons/menu/README.md $(DESTDIR)$(DATADIR)/icons/menu/
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/welcome
	$(INSTALL) -m755 data/welcome/eduka-welcome $(DESTDIR)$(DATADIR)/welcome/
	$(INSTALL) -m644 icons/eduka-customizer.svg $(DESTDIR)$(DATADIR)/icons/
	$(INSTALL) -m644 docs/eduka-customizer.1 $(DESTDIR)$(PREFIX)/share/man/man1/
	$(INSTALL) -m644 examples/* $(DESTDIR)$(PREFIX)/share/doc/eduka-customizer/examples/

uninstall:
	rm -rf $(DESTDIR)$(LIBDIR) $(DESTDIR)$(DATADIR)
	rm -f $(DESTDIR)$(PREFIX)/bin/eduka-customizer $(DESTDIR)$(PREFIX)/bin/eduka-customizer-pkexec \
		$(DESTDIR)$(PREFIX)/share/applications/org.edukasaun.customizer.desktop \
		$(DESTDIR)$(PREFIX)/share/polkit-1/actions/org.edukasaun.customizer.policy \
		$(DESTDIR)$(PREFIX)/share/metainfo/org.edukasaun.customizer.metainfo.xml \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/eduka-customizer.svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/*/apps/eduka-customizer.png \
		$(DESTDIR)$(PREFIX)/share/man/man1/eduka-customizer.1

run:
	EDUKA_CUSTOMIZER_DATA=$(CURDIR)/data $(PYTHON) -m eduka_customizer gui

deb:
	dpkg-buildpackage -us -uc -b

dist:
	$(GIT) archive HEAD --prefix="eduka-customizer-$(VERSION)/" | xz > "eduka-customizer-$(VERSION).tar.xz"

clean:
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache debian/eduka-customizer debian/.debhelper debian/files \
		debian/*.substvars debian/*.log debian/debhelper-build-stamp *.tar.xz

.PHONY: all check test install uninstall run deb dist clean
