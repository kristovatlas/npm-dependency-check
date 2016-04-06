"""Takes care of fetching data via HTTP."""
import urllib2
import ssl
from socket import error as SocketError
import time
import re
from tempfile import mkstemp
import os

ENABLE_DEBUG_PRINT = False

MAX_RETRY_TIME_IN_SEC = 5
NUM_SEC_TIMEOUT = 30
NUM_SEC_SLEEP = 0

def looks_like_version(version):
    """Returns whether the string looks like a legitimate version number

    Example version strings:
        * 1.0.0-rc4
        * 1.0.0
    """
    pattern = re.compile(r'^([\w\-]+\.)?([\w\-]+\.)?([\w\-]+)$')
    return bool(pattern.match(version))

def get_possible_zip_urls(github_project_url, version):
    """Get likely download links to the .zip file for the specified version.

    Examples:
    https://github.com/blockchain/My-Wallet-V3/archive/v3.13.0.zip
    https://github.com/cryptocoinjs/bigi/archive/1.4.1.zip

    Args:
        github_project_url (str): URL of project on GitHub.com
        version (str):

    Returs:
        List[str]: A list of urls as strings
    """
    assert isinstance(github_project_url, str)
    assert looks_like_version(version)
    assert github_project_url.startswith('https://github.com/')

    github_project_url = github_project_url.rstrip('/')

    urls = []

    urls.append("%s/archive/v%s.zip" % (github_project_url, version))
    urls.append("%s/archive/%s.zip" % (github_project_url, version))

    return urls

def fetch_url(url, fetch_tmp_file=False):
    """Fetch contents of remote page as string for specified url.

    Handles a variety of errors and retries with linearly increasing backoff.

    Args:
        url (str): The URL of the HTTP resource to be fetched.
        fetch_tmp_file (bool): Disabled by default. If set to true, instead
            of returning the contents of the HTTP response body as a string,
            a file handle to a temporary file where the contents have been
            output will be returned.

    Returns:
        str or filename, depending on setting of `fetch_tmp_file` arg.
    """

    if NUM_SEC_SLEEP > 0:
        time.sleep(NUM_SEC_SLEEP)

    current_retry_time_in_sec = 0

    dprint("Fetching url: %s" % url)

    response = ''
    while current_retry_time_in_sec <= MAX_RETRY_TIME_IN_SEC:
        if current_retry_time_in_sec:
            time.sleep(current_retry_time_in_sec)
        try:
            req = urllib2.urlopen(url=url, timeout=NUM_SEC_TIMEOUT)
            if fetch_tmp_file:
                return download_to_tmp(url, req)
            else:
                response = req.read()
                if response is None:
                    raise Exception
                return response

        except (urllib2.HTTPError, ssl.SSLError, urllib2.URLError,
                SocketError) as err:
            dprint(str(err))
            if hasattr(err, 'code') and err.code == 404:
                raise #don't retry for HTTP 404
            elif current_retry_time_in_sec == MAX_RETRY_TIME_IN_SEC:
                print str(err)
                raise
            else:
                current_retry_time_in_sec += 1

def download_to_tmp(url, req):
    """Download the data indicated in the request to a temp file.

    This does not currently use a back-off in the event of an error, as I'm too
    lazy to deal with the edge cases currently.

    Args:
        url (str): The URL that data is being fetched from.
        req (`urllib.addinfourl`): The object returned from `urllib2.urlopen`.

    Returns:
        str: The filename of the temporary file written to.

    Raises:
        ValueError: Fails if the downloaded file appears incomplete.
    """
    tmp_fd, tmp_filename = mkstemp()
    downloaded = 0
    content_len_str = req.info().getheader('Content-Length')
    total_size = None
    if content_len_str is not None:
        total_size = int(content_len_str.strip())
    if total_size == 0:
        raise ValueError(("Size of file returned by request to '%s' is 0 bytes "
                          "according to HTTP response header.") % url)
    CHUNK = 256 * 10240

    with open(tmp_filename, 'w') as tmp_file:
        while True:
            data_chunk = req.read(CHUNK)
            downloaded += len(data_chunk)
            if not data_chunk:
                break
            tmp_file.write(data_chunk)

    #https://www.logilab.org/blogentry/17873
    os.close(tmp_fd)

    if total_size is not None and downloaded != total_size:
        os.remove(tmp_filename)
        raise ValueError(('Incomplete download for %s. Expected %d bytes, '
                          'received %d.') % (url, total_size, downloaded))

    return tmp_filename

def dprint(msg):
    """Debug print statements."""
    if ENABLE_DEBUG_PRINT:
        print "DEBUG: %s" % msg
