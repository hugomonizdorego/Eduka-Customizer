"""Is there an internet connection? (Packages, Flatpaks, kernels and updates need one.)"""

import urllib.error
import urllib.request

# Answered by Debian's and Flathub's own servers; the first that answers is enough.
CHECK_URLS = ["http://deb.debian.org/debian/", "https://www.debian.org/", "https://flathub.org/"]


def online(timeout=4, urls=CHECK_URLS):
    """True when one of the servers answers (through the system's proxy settings)."""
    for url in urls:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "D!sco connectivity check"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status < 400:
                    return True
        except urllib.error.HTTPError as e:
            # The server answered: only a proxy that refuses (403, 407) means "no internet".
            if e.code < 500 and e.code not in (403, 407):
                return True
        except (OSError, ValueError):
            continue
    return False


NO_INTERNET = ("No internet connection. Extracting the ISO and editing files work offline, but installing "
               "packages, Flatpak applications, kernels and updates needs internet. Connecting is recommended.")
