# npm-dependency-check

NOTE: This script is still being developed and is not necessarily production-ready as it requires, at a minimum, unit testing. If you like the idea, please let me know on Twitter, GitHub issue, etc.

This script can be used to detect tampering with npm package source code. It does this in two ways:

1. The script creates a baseline image of the npm package using SHA256 hashes of source code files, and compare future installations of the npm package against the baseline.
2. The script looks for GitHub project links and verifies that the source code files maintained on GitHub.com match the local copies.

## Usage

### Creating a baseline

Start by doing a clean install of your target npm package in the way that you would normally perform it. It is recommended that you do not use an existing copy of any `npm_modules` directory, as this can cause unnecessary discrepancies due to [npm's non-deterministic install process](https://docs.npmjs.com/how-npm-works/npm3-nondet) (particularly in `npm3`).

For example:

```bash
mkdir ~/my-npm-package
npm install --prefix ~/my-npm-package my-npm-package
```

Next, run this script to output a baseline impression to a JSON file.

```bash
python npm-dependency-check.py --output baseline.json ~/my-npm-package/
```

### Checking an installation against the baseline

When you want to verify that a new installation of your target npm package has not been maliciously modified, specify the baseline JSON as a command-line argument to this script:

```bash
python npm-dependency-check.py --input baseline.json ~/my-npm-package/
```

## Sample output

Running against a clean npm package:
```bash
$ python npm_dependency_check.py --input baseline.json my-npm-package
No changes detected between npm installations.
```

Running against an npm package that has been tampered with:
```bash
$ python npm_dependency_check.py --input baseline.json my-npm-package
npm_dependency_check.py:25: UserWarning: Hash mismatch for 'lib/bigint.js' in 'bigi-0.0.1'. Was: '4f2d93cea49b7f214ed5c17340d8b7e9a6701ab6cfc8b5c6668707c7febaff43' Now: '0abe22154f2f62d243a6dc2edfbaadb86c6e109e7b275ef1dbbba34e0ecf1c3d'
  warnings.warn(string)
Encountered 1 discrepancies comparing cryptocoin-bigint to copy downloaded from GitHub.
npm_dependency_check.py:25: UserWarning: Hash mismatch for 'lib/bigint.js' in 'bigi-0.0.1'. Was: '0abe22154f2f62d243a6dc2edfbaadb86c6e109e7b275ef1dbbba34e0ecf1c3d' Now: '4f2d93cea49b7f214ed5c17340d8b7e9a6701ab6cfc8b5c6668707c7febaff43'
  warnings.warn(string)
ATTENTION: Execution produced 2 warnings.
```
