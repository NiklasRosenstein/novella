# Using Novella on GitHub

This guide is intended to give you a quick introduction on how to build your project documentation using Novella on
GitHub using Actions and publish them to Pages. It should also serve as a reference point to quickly get boilerplate
configuration for this type of workflow.

## Project structure

Here we are going that you are building documentation for a Python project and that your structure looks
similar to the below:

    .github/
      workflows/
        python.yml
    docs/
      content/
        index.md
        changelog.md
        etc.md
      build.novella
      requirements.txt
    # ...

## Requirements

It is convenient to have the requirements for building the documentation in a `docs/requirements.txt` file as that
means your job does not need to rely on another external tool other than Pip to install your tools.

```title="docs/requirements.txt"
mkdocs
mkdocs-material
novella==1.1.1
```

## GitHub Action

### Test and build in one job

In some cases it is convenient to build the documentation in the same job as where tests are run. But if your
Python project needs to be tested with versions of the Python that Novella or other tooling is not compatible
with, you need to make sure you install the tooling into an appropriate Python version instead. You can actually
run the `actions/setup-python@v2` action multiple times in the same job.

```yaml
jobs:
  test:
    steps:

    - uses: actions/checkout@v2

    - name: Set up Python 3.10
      uses: actions/setup-python@v2
      with: { python-version: "3.10" }

    - name: Install tooling
      run: python -m venv .tooling && .tooling/bin/pip install -r docs/requirements.txt

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v2
      with: { python-version: "${{ matrix.python-version }}" }

    - name: Install project
      run: pip install .

    # ...

    - name: Build documentation
      run: cd docs && ../.tooling/bin/novella

    # ...
```

### Build in a separate job

Building the documentation completely isolated from other CI jobs is often preferred.

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    steps:

    - uses: actions/checkout@v2

    - name: Set up Python 3.10
      uses: actions/setup-python@v2
      with: { python-version: "3.10" }

    - name: Install dependencies
      run: pip install -r docs/requirements.txt

    - name: Build documentation
      run: cd docs && novella

    # ...
```

### Publish the documentation

Having a separate job for publishing the docs is nice because it allows you to build the documentation in parallel
to other CI jobs such as tests and static type checks, while only publishing it if the tests succeed. For this, upload
the documentation output as an artifact in your `docs` job:

```yaml
jobs:
  docs:
    # ... (see above)

    - uses: actions/upload-artifact@v2
      with:
        name: docs
        path: docs/_site
```

Then in a new job, publish the documentation:

```yaml
jobs:
  docs-publish:
    needs: [ "test", "docs" ]
    runs-on: ubuntu-latest
    steps:

    - uses: actions/checkout@v2

    - uses: actions/download-artifact@v2
      with:
        name: docs
        path: docs/_site

    - name: Publish docs
      uses: JamesIves/github-pages-deploy-action@4.1.4
      with:
        branch: gh-pages
        folder: docs/_site
        ssh-key: ${{ secrets.DEPLOY_KEY }}
```
