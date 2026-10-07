#!/bin/sh
# Example hook: runs as root inside the image (copy it to <project>/hooks/).
set -e
# Enable a service in the installed system:
# systemctl enable ssh
# Add a default bookmark for every new user:
mkdir -p /etc/skel/Desktop
cat > /etc/skel/Desktop/edukasaun.desktop <<'DESKTOP'
[Desktop Entry]
Type=Link
Name=Edukasaun OS
URL=https://edukasaun.org
Icon=applications-education
DESKTOP
