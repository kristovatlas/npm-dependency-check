"""Functions related to analyzing npm packages."""

import http # http.py
import util # util.py

def get_package_name(package_json_obj):
    """Get the name of the package.

    Args:
        package_json_obj (dict): The object returned by calling json.load() on
            the packages `package.json` file.

    Returns:
        name as `str` or `None`
    """
    if 'name' in package_json_obj:
        return util.standardize_str(package_json_obj['name'])
    else:
        return None

def get_package_version(package_json_obj):
    """Get the version of the package.

    Args:
        package_json_obj (dict): The object returned by calling json.load() on
            the packages `package.json` file.

    Returns:
        version as `str`, or `None`
    """
    if ('version' in package_json_obj and
            http.looks_like_version(package_json_obj['version'])):
        return util.standardize_str(package_json_obj['version'])
    else:
        return None

def get_github_location(package_json_obj):
    """Get the GitHub project location for this npm package.

    Sample strings:
    https://github.com/blockchain/my-wallet-v3.git
    https://github.com/cryptocoinjs/bigi
    git://github.com/nickmerwin/node-coveralls.git
    git+https://github.com/rvagg/learnyounode.git

    Args:
        package_json_obj (dict): The object returned by calling json.load() on
            the packages `package.json` file.

    Returns:
        str: The GitHub.com url for the package in question

    If it cannot be determined from the `package.json` file, `None` is returned.
    """
    if 'repository' in package_json_obj:
        if 'url' in package_json_obj['repository']:
            url = util.standardize_str(package_json_obj['repository']['url'])
            if url.endswith('.git'):
                url = url.replace('.git', '/')

            if url.startswith('https://github.com/'):
                return url
            elif url.startswith('git://github.com/'):
                return url.replace('git://github.com/', 'https://github.com/')
            elif url.startswith('git+https://github.com/'):
                return url.replace('git+https://github.com/',
                                   'https://github.com/')
    return None
