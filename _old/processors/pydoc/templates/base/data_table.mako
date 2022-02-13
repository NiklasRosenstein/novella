## members, obj, options
<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

<table>
  <thead>
    <th>Attribute</th>
    <th>Type</th>
    <th>Description</th>
  </thead>
  <tbody>
      % for member in members:
    <tr>
      <td><code>${member.name}</code></td>
      <td><code>${member.datatype or ''}</code></td>
      <td>

${member.docstring or ''}

</td>
    </tr>
      % endfor
  </tbody>
</table>
