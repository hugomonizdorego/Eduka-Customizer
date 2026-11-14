# D!sco (Distro Custom) - build your own Debian-based distribution (ISO and SD-card images)
VERSION   = 0.11
PYTHON   ?= python3
DESTDIR  ?=
PREFIX   ?= /usr
LIBDIR    = $(PREFIX)/lib/disco
DATADIR   = $(PREFIX)/share/disco
INSTALL   = install
GIT       = git

all: check

check:
	$(PYTHON) -m compileall -q disco
	@$(PYTHON) -m pyflakes disco/core disco/gui disco/cli.py tests 2>/dev/null || echo "pyflakes not installed, skipped"

test:
	$(PYTHON) -m pytest -q tests

install:
	$(INSTALL) -d $(DESTDIR)$(LIBDIR) $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(DATADIR) \
		$(DESTDIR)/etc/disco $(DESTDIR)$(PREFIX)/share/applications \
		$(DESTDIR)$(PREFIX)/share/polkit-1/actions \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps \
		$(DESTDIR)$(PREFIX)/share/metainfo $(DESTDIR)$(PREFIX)/share/man/man1 \
		$(DESTDIR)$(PREFIX)/share/doc/disco/examples
	cp -r disco $(DESTDIR)$(LIBDIR)/
	find $(DESTDIR)$(LIBDIR) -name '__pycache__' -prune -exec rm -rf {} +
	find $(DESTDIR)$(LIBDIR) -type f -exec chmod 644 {} +
	sed -e 's|@LIBDIR@|$(LIBDIR)|g' -e 's|@DATADIR@|$(DATADIR)|g' data/disco.in \
		> $(DESTDIR)$(PREFIX)/bin/disco
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/disco-pkexec.in \
		> $(DESTDIR)$(PREFIX)/bin/disco-pkexec
	chmod 755 $(DESTDIR)$(PREFIX)/bin/disco $(DESTDIR)$(PREFIX)/bin/disco-pkexec
	# The old command names (DistroForge, Eduka-Customizer) keep working.
	for old in distroforge eduka-customizer; do \
		ln -sf disco $(DESTDIR)$(PREFIX)/bin/$$old; \
		ln -sf disco-pkexec $(DESTDIR)$(PREFIX)/bin/$$old-pkexec; done
	$(INSTALL) -m644 data/exclude.list data/desktops.json data/languages.json data/profiles.json data/apps.json data/themes.json data/catalog.json $(DESTDIR)$(DATADIR)/
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/presets $(DESTDIR)$(DATADIR)/board
	$(INSTALL) -m644 data/presets/*.json $(DESTDIR)$(DATADIR)/presets/
	$(INSTALL) -m755 data/board/disco-firstboot $(DESTDIR)$(DATADIR)/board/
	$(INSTALL) -m644 data/disco.conf $(DESTDIR)/etc/disco/disco.conf
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/io.github.hugomonizdorego.Disco.desktop.in \
		> $(DESTDIR)$(PREFIX)/share/applications/io.github.hugomonizdorego.Disco.desktop
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/io.github.hugomonizdorego.Disco.policy.in \
		> $(DESTDIR)$(PREFIX)/share/polkit-1/actions/io.github.hugomonizdorego.Disco.policy
	$(INSTALL) -m644 data/io.github.hugomonizdorego.Disco.metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/
	$(INSTALL) -m644 icons/disco.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/
	for s in 16 22 24 32 48 64 128 256; do \
		$(INSTALL) -D -m644 icons/hicolor/$${s}x$${s}/apps/disco.png \
			$(DESTDIR)$(PREFIX)/share/icons/hicolor/$${s}x$${s}/apps/disco.png; done
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/icons/menu
	$(INSTALL) -m644 data/icons/menu/*.svg data/icons/menu/README.md $(DESTDIR)$(DATADIR)/icons/menu/
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/welcome
	$(INSTALL) -m755 data/welcome/eduka-welcome $(DESTDIR)$(DATADIR)/welcome/
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/bootloader
	$(INSTALL) -m755 data/bootloader/distroforge-bootloader $(DESTDIR)$(DATADIR)/bootloader/
	$(INSTALL) -m644 icons/disco.svg $(DESTDIR)$(DATADIR)/icons/
	$(INSTALL) -m644 docs/disco.1 $(DESTDIR)$(PREFIX)/share/man/man1/
	$(INSTALL) -m644 examples/* $(DESTDIR)$(PREFIX)/share/doc/disco/examples/
	# The user guides live with the data: minimal systems drop /usr/share/doc.
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/guide
	$(INSTALL) -m644 docs/Disco-Guide.pdf $(DESTDIR)$(DATADIR)/guide/
	ln -sf $(DATADIR)/guide/Disco-Guide.pdf $(DESTDIR)$(PREFIX)/share/doc/disco/Disco-Guide.pdf

uninstall:
	rm -rf $(DESTDIR)$(LIBDIR) $(DESTDIR)$(DATADIR)
	rm -f $(DESTDIR)$(PREFIX)/bin/disco $(DESTDIR)$(PREFIX)/bin/disco-pkexec \
		$(DESTDIR)$(PREFIX)/bin/eduka-customizer $(DESTDIR)$(PREFIX)/bin/eduka-customizer-pkexec \
		$(DESTDIR)$(PREFIX)/bin/distroforge $(DESTDIR)$(PREFIX)/bin/distroforge-pkexec \
		$(DESTDIR)$(PREFIX)/share/applications/io.github.hugomonizdorego.Disco.desktop \
		$(DESTDIR)$(PREFIX)/share/polkit-1/actions/io.github.hugomonizdorego.Disco.policy \
		$(DESTDIR)$(PREFIX)/share/metainfo/io.github.hugomonizdorego.Disco.metainfo.xml \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/disco.svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/*/apps/disco.png \
		$(DESTDIR)$(PREFIX)/share/man/man1/disco.1

run:
	DISCO_DATA=$(CURDIR)/data $(PYTHON) -m disco gui

deb:
	dpkg-buildpackage -us -uc -b

dist:
	$(GIT) archive HEAD --prefix="disco-$(VERSION)/" | xz > "disco-$(VERSION).tar.xz"

clean:
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache debian/disco debian/.debhelper debian/files \
		debian/*.substvars debian/*.log debian/debhelper-build-stamp *.tar.xz

.PHONY: all check test install uninstall run deb dist clean
