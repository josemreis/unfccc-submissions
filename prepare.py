from platform import platform
import requests
import os
import sys
import tarfile

# paths
PATH_TO_GECKODRIVER = "resources"
URL_GECKODRIVER_LINUX = "https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-linux64.tar.gz"
URL_GECKODRIVER_MAC = "https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-macos-aarch64.tar.gz"
URL_GECKODRIVER_WIN = "https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-win64.zip"

if not os.path.isdir(PATH_TO_GECKODRIVER):
    os.mkdir(PATH_TO_GECKODRIVER)

def download_geckodriver() -> None:
    """download geckodriver to the resources folder"""
    if sys.platform.startswith("linux"):
        url = URL_GECKODRIVER_LINUX
    elif sys.platform.startswith("darwin"):
        url = URL_GECKODRIVER_MAC
    elif sys.platform.contains("win"):
        url = URL_GECKODRIVER_WIN
    else:
        raise TypeError("Can only download geckodriver for linux, macos, or windows")
    resp = requests.get(url)
    with open(os.path.join(PATH_TO_GECKODRIVER, "geckodriver.tar.gz"), "wb") as gf:
        gf.write(resp.content)


def main() -> None:
    geckodriver_path = os.path.join(PATH_TO_GECKODRIVER, "geckodriver.tar.gz")
    needs_geckodriver = False
    resources = [_.name for _ in os.scandir("resources")]
    if not resources:
        needs_geckodriver = True
    else:
        for _ in resources:
            if "geckodriver" not in _:
                needs_geckodriver = True
    if needs_geckodriver:
        download_geckodriver()
        with tarfile.open(geckodriver_path) as my_tarfile:
            my_tarfile.extractall("resources")
            my_tarfile.close
            os.remove(geckodriver_path)


if __name__ == "__main__":
    main()
