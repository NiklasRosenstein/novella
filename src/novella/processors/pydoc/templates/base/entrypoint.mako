<%namespace name="helpers" file="${context['options'].templates.helpers}"/>
<%
  if options.exclude_undocumented and not obj.docstring and parent:
    return
  include_file = options.templates[helpers.attr.get_type(obj).lower()]
%>
<%include file="${include_file}"/>
