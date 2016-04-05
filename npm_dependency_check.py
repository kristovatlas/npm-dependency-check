"""Generate and compare digests of npm packages."""

import argparse
import os
import json
import warnings
import tempfile
from shutil import rmtree
import zipfile
from urllib2 import HTTPError

import hasher # hasher.py
import npm    # npm.py
import http   # http.py

# pylint: disable=C0103
glob_num_warnings = 0

ENABLE_DEBUG_PRINT = False

def warn(string):
    """Write warning to stdout."""
    global glob_num_warnings
    glob_num_warnings += 1
    warnings.warn(string)

def main():
    """Process arguments and do stuff."""
    args = get_args()

    exts_to_hash = []
    if args.file_hash:
        exts_to_hash = args.extensions[0].split(',')

    package_data_json = get_package_data(args.target_dir, exts_to_hash, args)
    if package_data_json is None:
        warn("No data discovered about specified npm package.")
        return

    dprint(json.dumps(package_data_json))

    if args.output:
        args.output[0].write(json.dumps(package_data_json))
        if args.verbose:
            print "Wrote results to output file."

    if args.input is None:
        if args.verbose:
            print "No input JSON file specified. Completed work."
        return

    prev_data_json = None
    try:
        # TODO: may want to validate input JSON file against schema
        prev_data_json = json.load(args.input[0])
    except ValueError:
        warn("Could not parse input file. Will not compare to current output "
             "for discrepancies.")
        return

    compare_jsons(args.target_dir, prev_data_json, package_data_json, args)

    if glob_num_warnings > 0:
        print("ATTENTION: Execution produced %d warning%s." %
              (glob_num_warnings, 's' if glob_num_warnings != 1 else ''))
    elif glob_num_warnings == 0:
        print "No changes detected between npm installations."
    return

def compare_jsons(package_location, prev_data_json, new_data_json, args):
    """Iterates through the JSON files and emits warnings about changes.

    Comparisons:
    * Check commonality of package names
    * Check commaonlity of package versions
    * Check commonality of filenames and file hashes
    * Check commonality of github project links

    Args:
        package_location (str): The current package location relative to the
            top-level directory specified to this script. For example, if this
            script was run on 'my_npm_package' and this function is operating
            on the first-level npm dependency 'my_dependency',
            `package_location` would be 'my_npm_paclage/my_dependency'.
        prev_data_json (dict): The JSON generated by a previous invocation of
            this script against the target directory.
        new_data_json (dict): The JSON generated by the current invocation of
            this script against the target directory.
        args (`argparse.Namespace`): The command-line arguments produced by the
            `argparse` Python module.

    Returns:
        int: The number of warnings emitted by this invocation of
            `compare_jsons`.
    """
    dprint("Entered compare_jsons()")

    assert 'package_name' in prev_data_json
    assert 'package_name' in new_data_json

    assert 'package_location' in prev_data_json
    assert 'package_location' in new_data_json

    num_warnings = 0

    if prev_data_json['package_name'] != new_data_json['package_name']:
        warn(("Package names have changed since baseline npm installation. "
              "Was: '%s' Now: '%s'") %
             (prev_data_json['package_name'], new_data_json['package_name']))
        num_warnings += 1

    if args.ver_mismatch:
        assert 'package_version' in prev_data_json
        assert 'package_version' in new_data_json
        if (prev_data_json['package_version'] !=
                new_data_json['package_version']):
            warn(("Package versions have changed since baseline npm "
                  "installation. Was '%s' Now: '%s'") %
                 (prev_data_json['package_version'],
                  new_data_json['package_version']))
            num_warnings += 1

    if ('files' in prev_data_json and len(prev_data_json['files']) > 0 and
            'files' not in new_data_json):
        if args.file_missing:
            warn("These files in '%s' are now missing: %s" %
                 (package_location, str(prev_data_json['files'])))
            num_warnings += 1
    elif ('files' in new_data_json and len(new_data_json['files']) > 0 and
          'files' not in prev_data_json):
        if args.file_missing:
            warn("These files in '%s' were not previously present: %s" %
                 (package_location, str(new_data_json['files'])))
            num_warnings += 1
    else:
        if args.hash_mismatch or args.file_missing:
            for old_file in prev_data_json['files']:
                found_old_file = False
                for new_file in new_data_json['files']:
                    if old_file['file_location'] == new_file['file_location']:
                        found_old_file = True
                        if old_file['file_hash'] != new_file['file_hash']:
                            if args.hash_mismatch:
                                warn(("Hash mismatch for '%s' in '%s'. Was: "
                                      "'%s' Now: '%s'") %
                                     (old_file['file_location'],
                                      os.path.basename(package_location),
                                      old_file['file_hash'],
                                      new_file['file_hash']))
                                num_warnings += 1
                if args.file_missing and not found_old_file:
                    warn("File '%s' no longer present in '%s'" %
                         (old_file['file_location'],
                          os.path.basename(package_location)))
                    num_warnings += 1

    if args.github_changed:
        if ('github_location' in prev_data_json and
                'github_location' not in new_data_json):
            warn("GitHub link for '%s' has been deleted. Was: '%s'" %
                 (os.path.basename(package_location),
                  prev_data_json['github_location']))
            num_warnings += 1
        elif ('github_location' not in prev_data_json and
              'github_location' in new_data_json):
            warn("Previously absent GitHub link appeared for '%s' as: '%s'" %
                 (package_location, new_data_json['github_location']))
            num_warnings += 1

        elif ('github_location' in prev_data_json and
              'github_location' in new_data_json and
              prev_data_json['github_location'] !=
              new_data_json['github_location']):
            warn("GitHub link for '%s' has been modified. Was: '%s' Now: '%s'" %
                 (os.path.basename(package_location),
                  prev_data_json['github_location'],
                  new_data_json['github_location']))
            num_warnings += 1

    if 'submodules' in prev_data_json and 'submodules' not in new_data_json:
        warn("The following submodules have gone missing from '%s': %s" %
             (package_location, str(get_names_of_submodules(prev_data_json))))
        num_warnings += 1
    elif 'submodules' not in prev_data_json and 'submodules' in new_data_json:
        warn("The following new submodules of '%s' have appeared: %s" %
             (package_location, str(get_names_of_submodules(new_data_json))))
        num_warnings += 1
    elif 'submodules' in prev_data_json and 'submodules' in new_data_json:
        for prev_submodule in prev_data_json['submodules']:
            found_old_submodule = False
            for new_submodule in new_data_json['submodules']:
                if is_matching_submodule(prev_submodule, new_submodule):
                    found_old_submodule = True
                    compare_jsons(prev_submodule['package_location'],
                                  prev_submodule, new_submodule, args)
                    break
            if not found_old_submodule:
                warn("Missing sub-dependency '%s' from '%s'" %
                     (prev_submodule['package_location'], package_location))
                num_warnings += 1

        # look for new submodules
        for new_submodule in new_data_json['submodules']:
            found_new_submodule = False
            for prev_submodule in prev_data_json['submodules']:
                if is_matching_submodule(prev_submodule, new_submodule):
                    found_new_submodule = True
                    break
            if not found_new_submodule:
                warn("New sub-dependency '%s' has appeared in '%s'" %
                     (get_package_name_or_location(new_submodule),
                      package_location))
                num_warnings += 1

    return num_warnings

def get_package_name_or_location(package_json):
    """Get the name of package from package.json, or file location if missing."""
    if 'package_name' in package_json:
        return package_json['package_name']
    else:
        assert 'package_location' in package_json
        return package_json['package_location']

def is_matching_submodule(prev_submodule, new_submodule):
    """Match two npm submodules based on package name or location."""

    if 'package_name' in prev_submodule and 'package_name' in new_submodule:
        return prev_submodule['package_name'] == new_submodule['package_name']

    assert 'package_location' in prev_submodule
    assert 'package_location' in new_submodule

    return (prev_submodule['package_location'] ==
            new_submodule['package_location'])

def get_names_of_submodules(package_json):
    """Extract list of names of submodules from a JSON created by this script."""
    names = []
    for submodule in package_json['submodules']:
        if 'package_name' in submodule:
            names.append(submodule['package_name'])
    return names

def get_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description='Generate and compare digests of npm packages.')
    parser.add_argument('target_dir', metavar='target-dir', type=str,
                        help=('the location of the npm package you want to '
                              'check. this should usually be a relative '
                              'location; use an absolute directory location if '
                              'you expect that to remain constant on all '
                              'machines that you will verify this imprint '
                              'against in the future.'))
    parser.add_argument('--input', type=argparse.FileType('r'), nargs=1,
                        metavar='input-json',
                        help=('read in JSON file previously generated by this '
                              'script using the --output argument. When this '
                              'argument is specified, the current state of the '
                              'target npm package will be compared to the '
                              'prior results, and warnings will be emitted '
                              'when there is a change.'))
    parser.add_argument('--output', type=argparse.FileType('w'), nargs=1,
                        metavar='output-json',
                        help=('output information about the target package in '
                              'JSON format. This can be compared against '
                              'future checks using the --input argument.'))

    parser.add_argument('--include-file-hash', dest='file_hash',
                        action='store_true',
                        help=('include a SHA-256 hash of all code files within '
                              'npm packages in the output JSON file. '
                              '(Default)'))
    parser.add_argument('--exclude-file-hash', dest='file_hash',
                        action='store_false',
                        help=('do not include a hash check a hash of code '
                              'files within npm  packages. only other checks '
                              'will be performed.'))

    parser.add_argument('--hashed-extensions', metavar='comma-separated-list',
                        dest='extensions', type=str, nargs=1,
                        help=('specify the filename suffixes that will be '
                              'hashed. Default: .js,.json'))
    parser.add_argument('--report-version-mismatch', dest='ver_mismatch',
                        action='store_true',
                        help=('when comparing to a previously generated JSON '
                              'file, report when npm package versions have '
                              'changed according to included package.json '
                              'files. (Default)'))
    parser.add_argument('--no-report-version-mismatch', dest='ver_mismatch',
                        action='store_false',
                        help=('when comparing to a previously generated JSON '
                              'file, do not report changed npm package '
                              'versions.'))
    parser.add_argument('--report-hash-mismatch', dest='hash_mismatch',
                        action='store_true',
                        help=('when comparing to a previously generated JSON '
                              'file, report when a file hash has changed. '
                              '(Default) NOTE: not compatible with the '
                              '--exclude-file-hash option.'))
    parser.add_argument('--no-report-hash-mismatch', dest='hash_mismatch',
                        action='store_false',
                        help=('when comparing to a previously generated JSON '
                              'file, do not report when a file hash has '
                              'changed.'))
    parser.add_argument('--report-missing-file', dest='file_missing',
                        action='store_true',
                        help=('when comparing to a previously generated JSON '
                              'file, report when a file is no longer present. '
                              '(Default)'))
    parser.add_argument('--no-report-missing-file', dest='file_missing',
                        action='store_false',
                        help=('when comparing to a previously generated JSON '
                              'file, do not report when a file is no longer '
                              'present.'))

    parser.add_argument('--report-github-changed', dest='github_changed',
                        action='store_true',
                        help=('when comparing to a previously generated JSON '
                              'file, report when the apparent github project '
                              'location has changed. (Default)'))
    parser.add_argument('--no-report-github-changed', dest='github_changed',
                        action='store_false',
                        help=('when comparing to a previously generated JSON '
                              'file, do not report when the apparent github '
                              'project location has changed.'))

    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help=('enable verbose output about status of execution '
                              '(Disabled by default)'))

    # TODO:
    # --guess-github-project=[1|0]    If no github project location is specified in a package's package.json file, the top search result from GitHub will be used. A warning will be emited. Security notice: This can be gamed by an attacker who raises a copy of her malicious npm package to the top of the GitHub search results. Default: Enabled (1)

    parser.set_defaults(file_hash=True, extensions=['.js,.json'],
                        ver_mismatch=True, hash_mismatch=True,
                        file_missing=True, github_changed=True, verbose=False)

    args = parser.parse_args()

    if args.verbose:
        print(("input: %s\n"
               "output: %s\n"
               "file_hash: %s\n"
               "extensions: %s\n"
               "ver_mismatch: %s\n"
               "hash_mismatch: %s\n"
               "file_missing: %s\n"
               "github_changed: %s\n"
               "verbose: %s") %
              tuple(str(x) for x in (args.input, args.output, args.file_hash,
                                     args.extensions[0], args.ver_mismatch,
                                     args.hash_mismatch, args.file_missing,
                                     args.github_changed, args.verbose)))

    check_args(args)

    return args

def check_args(args):
    """Verify that user's command-line args are proeprly formatted."""
    assert os.path.isdir(args.target_dir), ("'%s' is not a directory." %
                                            str(args.target_dir))
    assert os.access(args.target_dir, os.R_OK), ("'%s' cannot be read from." %
                                                 str(args.target_dir))

    assert len(args.extensions[0].split(',')) > 0, \
        "'%s' is not a comma-separated list." % args.extensions[0]
    for ext in args.extensions[0].split(','):
        assert ext != '', ("'%s contains an empty file extension" %
                           str(args.extensions[0]))

def get_package_data(package_location, extensions_hashed, args,
                     github_comparison=True):
    """Process this package along with sub-dirs. Recurse on node_modules.

    Args:
        package_location (str): A directory containing an npm package, as
            indicated by the presense of a `package.json` file. If a
            `package.json` file cannot be found, a warning will be emitted.
            If the directory contains a `node_modules` directory, this will
            recurse on any subdirectories of that `node_modules` directory
            with the expectation that they are npm packages. The full
            `package_location` should be relative to the current working
            directory, with the right-most directory being the package
            being targeted by this invocation of the function, e.g.:
                * /my-npm-package/
                * /my-npm-package/node_modules/dependency-a/
        extensions_hashed (List[str]): A list of filename suffixes that should
            be SHA-256 hashed. If this list is empty, no files will be hashed.
        args (List): List of arguments acquired by `parse_args`.
        github_comparison (bool): Flag determines whether this function will
            attempt to download a copy of the current package from GitHub
            for verification. The caller should set this to `False` in order
            to avoid cycles.

    Returns:
        dict: Data about this package, including:
            * package_location (str) -- the `package_location` argument. Used
                for navigating directory structures when parsed in the future.
            * package_name (str)
            * package_version (str)
            * github_location (str)
            * files (List[dict]) including subdirs other than `node_modules`
                * file_location (str): file path and filename
                * file_hash (str): hash of file contents, unless disabled by
                    command line argument
            * submodules (List[dict]): a list of the `dict`s returned by
                recurisve calls to this function for npm (sub-)dependencies.

            OR `None`, if there is no information available for the package.
    """
    dprint("Entered get_package_data()")

    if not is_readable_dir(package_location):
        warn("Could not read directory '%s'. Skipping." % package_location)
        return None

    files = os.listdir(package_location)
    if 'package.json' not in files:
        warn(("Could not find expected package.json in directory '%s'. "
              "Skipping." % package_location))
        return None

    package_json_obj = None
    with open(os.path.join(package_location, 'package.json'), 'r') as p_json_f:
        package_json_obj = json.load(p_json_f)

    package_name = npm.get_package_name(package_json_obj)
    if package_name is None:
        warn(("Malformed package.json file for '%s': Could not parse name "
              "field.") % package_location)
        return None

    package_version = npm.get_package_version(package_json_obj)
    if package_version is None:
        warn(("Malformed package.json file for '%s': Could not parse version "
              "field.") % package_location)
        return None

    github_location = npm.get_github_location(package_json_obj)
    if github_location is None:
        # TODO: implement guessing with HTTP calls to github search
        github_location = ''


    files_json = get_file_data(package_location, "", files, extensions_hashed,
                               args)

    node_modules = []
    if 'node_modules' in files:
        if args.verbose:
            print "Found 'node_modules' directory in %s." % package_location
        node_modules_files = os.listdir(
            os.path.join(package_location, 'node_modules'))
        for node_module in node_modules_files:
            module_location = os.path.join(package_location, 'node_modules',
                                           node_module)

            # TODO: It may be possible to hide malicious code in a dot-directory
            # TODO: Investigate whether hidden files/directories are shown
            if is_readable_non_dot_dir(module_location):
                if args.verbose:
                    print("Found possible sub-dependency '%s' in '%s'" %
                          (node_module, package_location))

                dependency = get_package_data(
                    module_location, extensions_hashed, args)
                if dependency is not None:
                    node_modules.append(dependency)

    json_obj = {'package_location': package_location,
                'package_name': package_name,
                'package_version': package_version,
                'github_location': github_location}
    json_obj['files'] = files_json
    if len(node_modules) > 0:
        json_obj['submodules'] = node_modules

    # every time we fetch data about a given module, we will compare it to the
    # version on GitHub if it's available and warnings emitted if it doesn't
    # match.

    if (github_location is not None and github_location != '' and
            github_comparison):
        compare_package_to_github(json_obj, github_location, package_version,
                                  extensions_hashed, args)

    return json_obj

def get_file_data(location_cwd, location_in_package, files, extensions_hashed,
                  args):
    """Gets data about files and sub-directories, except for /node_modules.

    Args:
        location_cwd (str): The location of the files relative to the current
            working directory.
        location_in_package (str): The location of the files relative to the
            current package. If this is the top-level directory of the package,
            `location_in_package` is empty (""). If the files are in a
            sub-directory after a recursive call to this function, they will be
            relative to the package root dir.
        files (List[str]): A list of files the directory being iterated; either
            in the top-level directory of a package, or one of its
            sub-directories.
        extensions_hashed (List[str]): A list of filename suffixes that should
            be SHA-256 hashed. If this list is empty, no files will be hashed.
        args (List): List of arguments acquired by `parse_args`.
    Returns:
        List[dict]: A list of hashed files, each expressed as a `dict`. Each
            `dict` contains two attributes:
            * 'file_location' (str): Location of the file relative to the
                package it belongs to.
            * 'file_hash' (str): hash of the file

            If there are no files that are hashed, an empty list is returned.
    """

    dprint("Entered get_file_data()")

    files_json = []
    for filename in files:
        path_cwd = os.path.join(location_cwd, filename)
        if os.path.isdir(path_cwd):
            if is_readable_dir(path_cwd):
                if (is_readable_non_dot_dir(path_cwd) and
                        filename != 'node_modules'):
                    subdir_in_package = os.path.join(location_in_package,
                                                     filename)
                    if args.verbose:
                        print("Found package sub-directory '%s'" %
                              subdir_in_package)
                    subdir_files = os.listdir(path_cwd)

                    #this will produce a depth-first list of files
                    files_json = files_json + get_file_data(
                        path_cwd, subdir_in_package, subdir_files,
                        extensions_hashed, args)
            else:
                warn("Could not read directory '%s' Skipping it for checks." %
                     path_cwd)
        else:
            for ext in extensions_hashed:
                if filename.endswith(ext):
                    file_in_package = os.path.join(
                        os.path.basename(location_in_package), filename)
                    file_cwd = os.path.join(location_cwd, filename)
                    file_hash = hasher.hash_file(file_cwd)
                    file_json = {'file_location': file_in_package,
                                 'file_hash': file_hash}
                    files_json.append(file_json)
                    if args.verbose:
                        print "hash(%s) = %s" % (filename, file_hash)

    return files_json

def is_readable_non_dot_dir(dir_location):
    """Returns whether arg is a readable dir that doesn't begin with '.'"""
    return (not os.path.basename(dir_location).startswith('.') and
            is_readable_dir(dir_location))

def is_readable_dir(dir_location):
    """Returns whether string argument is a readable directory."""
    return os.path.isdir(dir_location) and os.access(dir_location, os.R_OK)

def compare_package_to_github(local_data_json, github_location, package_version,
                              extensions_hashed, args):
    """Downloads the npm package from GitHub and warns about discrepancies.

    Args:
        local_data_json (dict): The JSON generated by the current invocation of
            this script for the target directory. This should be at the
            JSON level of the npm package being targeted by this function call.
            The JSON contains previous hashes to compare the GitHub download to.
        github_location (str): The URL for the project on GitHub, as returned
            by `npm.get_github_location`.
        package_version (str): The version of the package being targeted.
        extensions_hashed (List[str]): A list of filename suffixes that should
            be SHA-256 hashed. If this list is empty, no files will be hashed.
        args (List): List of arguments acquired by `parse_args`.
    """
    dprint("Entered compare_package_to_github()")

    assert isinstance(github_location, str)
    assert isinstance(package_version, str)

    urls = http.get_possible_zip_urls(github_location, package_version)
    zip_filename = None
    for url in urls:
        if args.verbose:
            print "Trying to download zip file from '%s'..." % url

        try:
            zip_filename = http.fetch_url(url, fetch_tmp_file=True)
            if args.verbose:
                print "Successfully downloaded data from '%s'." % url
            break #found a good url
        except HTTPError, err:
            if hasattr(err, 'code') and err.code == 404:
                continue #try next url
            else:
                raise

    if zip_filename is None:
        warn(("Could not resolve GitHub link for '%s'; maybe this project does "
              "not have a tagged release for version '%s'? Skipping comparison "
              "to GitHub project.") %
              (get_package_name_or_location(local_data_json), package_version))
        return

    tmp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_filename, 'r') as downloaded_zip:
        downloaded_zip.extractall(tmp_dir)

    # if the extraction worked correctly, there should be a single
    # sub-directory in the temp directory
    extracted_files = os.listdir(tmp_dir)
    if len(extracted_files) != 1:
        warn(("Failed to extract zip file for '%s'; expected 1 sub-directory "
              "but found these: '%s'") %
             (get_package_name_or_location(local_data_json),
              str(extracted_files)))
        cleanup(zip_filename, tmp_dir)
        return

    package_location = os.path.join(tmp_dir, extracted_files[0])
    github_package_json = get_package_data(
        package_location, extensions_hashed, args, github_comparison=False)
    num_warnings = compare_jsons(package_location, local_data_json,
                                 github_package_json, args)


    if num_warnings == 0:
        if args.verbose:
            print("No discrepancies found compared to GitHub copy of %s." %
                  get_package_name_or_location(local_data_json))
    else:
        print(("Encountered %d discrepancies comparing %s to copy downloaded "
               "from GitHub.") %
              (num_warnings, get_package_name_or_location(local_data_json)))

    cleanup(zip_filename, tmp_dir)

def cleanup(zip_filename, tmp_dir):
    """Remove temporay files."""
    try:
        os.remove(zip_filename)
    except OSError:
        pass
    try:
        rmtree(tmp_dir)
    except OSError:
        pass

def dprint(msg):
    """Debug print statements."""
    if ENABLE_DEBUG_PRINT:
        print "DEBUG: %s" % msg

if __name__ == '__main__':
    main()
