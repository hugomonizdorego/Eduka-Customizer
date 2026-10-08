# DistroForge - live ISO builder for Debian-based distributions
VERSION   = 0.17.0~alpha
PYTHON   ?= python3
DESTDIR  ?=
PREFIX   ?= /usr
LIBDIR    = $(PREFIX)/lib/distroforge
DATADIR   = $(PREFIX)/share/distroforge
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
		$(DESTDIR)/etc/distroforge $(DESTDIR)$(PREFIX)/share/applications \
		$(DESTDIR)$(PREFIX)/share/polkit-1/actions \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps \
		$(DESTDIR)$(PREFIX)/share/metainfo $(DESTDIR)$(PREFIX)/share/man/man1 \
		$(DESTDIR)$(PREFIX)/share/doc/distroforge/examples
	cp -r eduka_customizer $(DESTDIR)$(LIBDIR)/
	find $(DESTDIR)$(LIBDIR) -name '__pycache__' -prune -exec rm -rf {} +
	find $(DESTDIR)$(LIBDIR) -type f -exec chmod 644 {} +
	sed -e 's|@LIBDIR@|$(LIBDIR)|g' -e 's|@DATADIR@|$(DATADIR)|g' data/distroforge.in \
		> $(DESTDIR)$(PREFIX)/bin/distroforge
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/distroforge-pkexec.in \
		> $(DESTDIR)$(PREFIX)/bin/distroforge-pkexec
	chmod 755 $(DESTDIR)$(PREFIX)/bin/distroforge $(DESTDIR)$(PREFIX)/bin/distroforge-pkexec
	# The old command names keep working.
	ln -sf distroforge $(DESTDIR)$(PREFIX)/bin/eduka-customizer
	ln -sf distroforge-pkexec $(DESTDIR)$(PREFIX)/bin/eduka-customizer-pkexec
	$(INSTALL) -m644 data/exclude.list data/desktops.json data/languages.json data/profiles.json data/apps.json data/themes.json $(DESTDIR)$(DATADIR)/
	$(INSTALL) -m644 data/distroforge.conf $(DESTDIR)/etc/distroforge/distroforge.conf
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/io.github.hugomonizdorego.DistroForge.desktop.in \
		> $(DESTDIR)$(PREFIX)/share/applications/io.github.hugomonizdorego.DistroForge.desktop
	sed -e 's|@PREFIX@|$(PREFIX)|g' data/io.github.hugomonizdorego.DistroForge.policy.in \
		> $(DESTDIR)$(PREFIX)/share/polkit-1/actions/io.github.hugomonizdorego.DistroForge.policy
	$(INSTALL) -m644 data/io.github.hugomonizdorego.DistroForge.metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/
	$(INSTALL) -m644 icons/distroforge.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/
	for s in 16 22 24 32 48 64 128 256; do \
		$(INSTALL) -D -m644 icons/hicolor/$${s}x$${s}/apps/distroforge.png \
			$(DESTDIR)$(PREFIX)/share/icons/hicolor/$${s}x$${s}/apps/distroforge.png; done
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/icons/menu
	$(INSTALL) -m644 data/icons/menu/*.svg data/icons/menu/README.md $(DESTDIR)$(DATADIR)/icons/menu/
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/welcome
	$(INSTALL) -m755 data/welcome/eduka-welcome $(DESTDIR)$(DATADIR)/welcome/
	$(INSTALL) -m644 icons/distroforge.svg $(DESTDIR)$(DATADIR)/icons/
	$(INSTALL) -m644 docs/distroforge.1 $(DESTDIR)$(PREFIX)/share/man/man1/
	$(INSTALL) -m644 examples/* $(DESTDIR)$(PREFIX)/share/doc/distroforge/examples/
	# The user guides live with the data: minimal systems drop /usr/share/doc.
	$(INSTALL) -d $(DESTDIR)$(DATADIR)/guide
	$(INSTALL) -m644 docs/DistroForge-Panduan.pdf docs/DistroForge-Guide.pdf $(DESTDIR)$(DATADIR)/guide/
	ln -sf $(DATADIR)/guide/DistroForge-Panduan.pdf $(DESTDIR)$(PREFIX)/share/doc/distroforge/DistroForge-Panduan.pdf
	ln -sf $(DATADIR)/guide/DistroForge-Guide.pdf $(DESTDIR)$(PREFIX)/share/doc/distroforge/DistroForge-Guide.pdf

uninstall:
	rm -rf $(DESTDIR)$(LIBDIR) $(DESTDIR)$(DATADIR)
	rm -f $(DESTDIR)$(PREFIX)/bin/distroforge $(DESTDIR)$(PREFIX)/bin/distroforge-pkexec \
		$(DESTDIR)$(PREFIX)/bin/eduka-customizer $(DESTDIR)$(PREFIX)/bin/eduka-customizer-pkexec \
		$(DESTDIR)$(PREFIX)/share/applications/io.github.hugomonizdorego.DistroForge.desktop \
		$(DESTDIR)$(PREFIX)/share/polkit-1/actions/io.github.hugomonizdorego.DistroForge.policy \
		$(DESTDIR)$(PREFIX)/share/metainfo/io.github.hugomonizdorego.DistroForge.metainfo.xml \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/distroforge.svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/*/apps/distroforge.png \
		$(DESTDIR)$(PREFIX)/share/man/man1/distroforge.1

run:
	DISTROFORGE_DATA=$(CURDIR)/data $(PYTHON) -m eduka_customizer gui

deb:
	dpkg-buildpackage -us -uc -b

dist:
	$(GIT) archive HEAD --prefix="distroforge-$(VERSION)/" | xz > "distroforge-$(VERSION).tar.xz"

clean:
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache debian/distroforge debian/.debhelper debian/files \
		debian/*.substvars debian/*.log debian/debhelper-build-stamp *.tar.xz

.PHONY: all check test install uninstall run deb dist clean
