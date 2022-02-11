<%namespace name="helpers" file="helpers.mako"/>

<% type = helpers.attr.get_type(obj) %>
% if type == 'Function':
  <%include file="function.mako"/>
% elif type == 'Class':
  <%include file="class.mako"/>
% elif type == 'Data':
  <%include file="data.mako"/>
% else:
  Unsure how to handle ${type}
% endif
