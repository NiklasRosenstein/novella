
import logging
import os
import platform
import requests
import shutil
import sys
import tarfile
import tempfile
import typing as t

from nr.util.fs import chmod

logger = logging.getLogger(__name__)


def install_hugo(to: str, version: str = None, extended: bool = True) -> None:
  """ Downloads the latest release of *Hugo* from [Github](https://github.com/gohugoio/hugo/releases)
  and places it at the path specified by *to*. This will install the extended version if it is
  available and *extended* is set to `True`.

  :param to: The file to write the Hugo binary to.
  :param version: The Hugo version to get. If not specified, the latest release will be used.
  :param extended: Whether to download the "Hugo extended" version. Defaults to True.
  """

  # TODO (@NiklasRosenstein): Support BSD platforms.

  if sys.platform.startswith('linux'):
    platform_name = 'Linux'
  elif sys.platform.startswith('win32'):
    platform_name = 'Windows'
  elif sys.platform.startswith('darwin'):
    platform_name = 'macOS'
  else:
    raise EnvironmentError('unsure how to get a Hugo binary for platform {!r}'.format(sys.platform))

  machine = platform.machine().lower()
  if machine in ('x86_64', 'amd64', 'arm64'):
    arch = '64bit'
  elif machine in ('i386',):
    arch = '32bit'
  else:
    raise EnvironmentError('unsure whether to intepret {!r} as 32- or 64-bit.'.format(machine))

  releases = get_github_releases('gohugoio/hugo')
  if version:
    version = version.lstrip('v')
    for release in releases:
      if release['tag_name'].lstrip('v') == version:
        break
    else:
      raise ValueError('no Hugo release for version {!r} found'.format(version))
  else:
    release = next(releases)
    version = release['tag_name'].lstrip('v')

  files = {asset['name']: asset['browser_download_url'] for asset in release['assets']}

  hugo_archive = 'hugo_{}_{}-{}.tar.gz'.format(version, platform_name, arch)
  hugo_extended_archive = 'hugo_extended_{}_{}-{}.tar.gz'.format(version, platform_name, arch)
  if extended and hugo_extended_archive in files:
    filename = hugo_extended_archive
  else:
    filename = hugo_archive

  logger.info('Downloading Hugo v%s from "%s"', version, files[filename])
  os.makedirs(os.path.dirname(to), exist_ok=True)
  with tempfile.TemporaryDirectory() as tempdir:
    path = os.path.join(tempdir, filename)
    with open(path, 'wb') as fp:
      shutil.copyfileobj(requests.get(files[filename], stream=True).raw, fp)
    with tarfile.open(path) as archive:
      with open(to, 'wb') as fp:
        shutil.copyfileobj(
          t.cast(t.IO[bytes], archive.extractfile('hugo')),
          t.cast(t.IO[bytes], fp))

  chmod.update(to, '+x')
  logger.info('Hugo v%s installed to "%s"', version, to)


def get_github_releases(repo: str) -> t.Generator[dict, None, None]:
  """ Returns an iterator for all releases of a Github repository. """

  url: t.Optional[str] = 'https://api.github.com/repos/{}/releases'.format(repo)
  while url:
    response = requests.get(url)
    link = response.headers.get('Link')
    assert link
    links = parse_links_header(link)
    url = links.get('next')
    yield from response.json()


def parse_links_header(link_header: str) -> t.Dict[str, str]:
  """ Parses the `Link` HTTP header and returns a map of the links. Logic from
  [PageLinks.java](https://github.com/eclipse/egit-github/blob/master/org.eclipse.egit.github.core/src/org/eclipse/egit/github/core/client/PageLinks.java#L43-75).
  """

  links = {}

  for link in link_header.split(','):
    segments = link.split(';')
    if len(segments) < 2:
      continue
    link_part = segments[0].strip()
    if not link_part.startswith('<') or not link_part.endswith('>'):
      continue
    link_part = link_part[1:-1]
    for rel in (x.strip().split('=') for x in segments[1:]):
      if len(rel) < 2 or rel[0] != 'rel':
        continue
      rel_value = rel[1]
      if rel_value.startswith('"') and rel_value.endswith('"'):
        rel_value = rel_value[1:-1]
      links[rel_value] = link_part

  return links
