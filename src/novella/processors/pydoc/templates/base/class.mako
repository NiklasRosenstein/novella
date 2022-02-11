<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

% if options.render_title:
<%helpers:markdown_header prefix='Class' header_level="${options.header_level['class']}"/>
% endif

% if not parent and options.render_module_name_after_title:
__Module__: `${helpers.attr.get_fqn(obj)}`
% endif

% if options.render_class_def:
<%helpers:definition_codeblock obj="${obj}"/>
% endif

${obj.docstring or ""}

<%
  attrs = [a for a in helpers.attr.get_attributes(obj) if not helpers.attr.ignored(a, obj, options)]
  methods = [m for m in helpers.attr.get_functions(obj) if not helpers.attr.ignored(m, obj, options)]
%>

% if options.render_class_attrs_summary and attrs:
${render(options.templates.class_attrs_table, obj=obj, members=attrs)}
% endif

% if options.render_class_method_table and methods:
${render(options.templates.class_method_table, obj=obj, members=methods)}
% endif

% if options.render_class_attrs:
% for member in attrs:
  ${render(options.templates.entrypoint, obj=member, parent=obj)}
% endfor
% endif

% if options.render_class_methods:
% for member in methods:
  ${render(options.templates.entrypoint, obj=member, parent=obj)}
% endfor
% endif

% if options.render_class_hr:
---
% endif
