
import dataclasses
import logging
import pkg_resources
import subprocess
import typing as t

import yaml
from databind.core.annotations import alias
from . import Action, Context

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MkdocsAction(Action):
  """ An action to run Mkdocs in the temporary build directory. """

  directory: str
  adjust_paths: t.Annotated[bool, alias('adjust-paths')] = True
  use_profile: t.Annotated[str | None, alias('use-profile')] = None

  def execute(self, context: Context) -> None:
    self.update_mkdocs_config(context)
    command = ['mkdocs', 'serve']
    subprocess.check_call(command, cwd=context.build_directory / self.directory)

  def update_mkdocs_config(self, context: Context) -> None:
    """ Performs changes to the MkDocs configuration in in the build directory. """

    mkdocs_yml = context.build_directory / self.directory / 'mkdocs.yml'
    data = yaml.safe_load(mkdocs_yml.read_text())

    if self.adjust_paths:
      if 'site_dir' in data:
        data['site_dir'] = str(context.project_directory / data['site_dir'])
      if 'theme' in data and 'custom_dir' in data['theme']:
        data['theme']['custom_dir'] = str(context.project_directory / data['theme']['custom_dir'])

    if self.use_profile is not None:
      self.apply_profile(self.use_profile, data)

    mkdocs_yml.write_text(yaml.dump(data))

  def apply_profile(self, profile_name: str, data: t.MutableMapping[str, t.Any]) -> None:
    """ Apply an existing MkDocs configuration shipped with Novella. """

    logger.info('Apply MkDocs profile %s', profile_name)

    config = pkg_resources.resource_string(__name__, f'data/mkdocs/profiles/{profile_name}/mkdocs.yml').decode('utf-8')
    config_data = yaml.safe_load(config)

    for key in config_data:
      if key not in data:
        data[key] = config_data[key]
