#!/bin/sh
# Example hook: runs as root inside the image (copy it to <project>/hooks/).
set -e
# Enable a service in the installed system:
# systemctl enable ssh
# Add a default bookmark for every new user:
mkdir -p /etc/skel/Desktop
cat > /etc/skel/Desktop/website.desktop <<'DESKTOP'
[Desktop Entry]
Type=Link
Name=My Linux website
URL=https://example.org
Icon=applications-education
DESKTOP
