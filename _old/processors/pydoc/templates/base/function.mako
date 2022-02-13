<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

<% is_method = helpers.attr.get_type(obj.parent) == 'Class' %>

% if options.render_title:
<%helpers:markdown_header
  prefix="${'Method' if is_method else 'Function'}"
  header_level="${options.header_level.class_member if is_method else options.header_level.module_member}"
  absolute_fqn="${parent}"/>
% endif

% if options.render_func_def:
<%helpers:definition_codeblock obj="${obj}"/>
% endif

% if not parent and options.render_module_name_after_title:
__Module__: `${helpers.attr.get_fqn(obj)}`
% endif

${obj.docstring or ""}
