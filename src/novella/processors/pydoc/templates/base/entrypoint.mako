<%namespace name="helpers" file="${context['options'].templates.helpers}"/>
<%
  if helpers.attr.ignored(obj, parent, options):
    return
  include_file = options.templates[helpers.attr.get_type(obj).lower()]
%>
<%include file="${include_file}"/>
