<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

% if options.render_title:
<%helpers:markdown_header prefix='Class' header_level="${header_level}"/>
% endif

% if not parent and options.render_module_name_after_title:
__Module__: `${helpers.attr.get_fqn(obj)}`
% endif

% if options.render_class_def:
<%helpers:definition_codeblock obj="${obj}"/>
% endif

${obj.docstring or ""}

% if options.render_class_attrs:
% for member in obj.members:
  % if helpers.attr.get_type(member) == 'Data':
    ${render(options.templates.entrypoint, obj=member, parent=obj, header_level=(header_level or options.header_level) + 1)}
  % endif
% endfor
% endif

% if options.render_class_methods:
% for member in obj.members:
  % if helpers.attr.get_type(member) == 'Function':
    ${render(options.templates.entrypoint, obj=member, parent=obj, header_level=(header_level or options.header_level) + 1)}
  % endif
% endfor
% endif

% if options.render_class_hr:
---
% endif
