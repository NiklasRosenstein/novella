
from __future__ import annotations

import abc
import typing as t

T_Node = t.TypeVar('T_Node', bound='Node')


class Node(t.Generic[T_Node], abc.ABC):
  """ Base class for nodes. """

  #: The name of the node. This must be unique within a graph.
  name: str

  #: A list of dependencies of the node. If set to `None`, it means the node has no explicit dependencies but a
  #: default set of dependencies may be used instead to enforce a default order.
  dependencies: list[T_Node] | None = None

  #: A list of nodes that must occur *after* the current node in the execution order.
  predecessors: list[T_Node] | None = None

  #: The graph that this node is assigned to.
  graph: Graph[T_Node] | None = None

  def depends_on(self, *nodes: T_Node | str) -> None:
    """ Add dependencies to this node, either by supplying the nodes directly or by passing the node name which
    will be resolved in node's graph. Note that the node must be associated with a graph and all referenced nodes
    must be members of the same graph. """

    if self.graph is None:
      raise RuntimeError('Node.graph is not set')

    if self.dependencies is None:
      self.dependencies = []

    for node in nodes:
      if isinstance(node, str):
        node = self.graph.nodes[node]
      assert isinstance(node, Node), node
      if node.graph is not self.graph:
        raise RuntimeError('Nodes added as dependencies must be part of the same graph')
      self.dependencies.append(node)

  def precedes(self, *nodes: T_Node | str) -> None:
    """ Like #depends_on(), but instead fillse in #predecessors. """

    if self.graph is None:
      raise RuntimeError('Node.graph is not set')

    if self.predecessors is None:
      self.predecessors = []

    for node in nodes:
      if isinstance(node, str):
        node = self.graph.nodes[node]
      assert isinstance(node, Node), node
      if node.graph is not self.graph:
        raise RuntimeError('Nodes added as predecessors must be part of the same graph')
      self.predecessors.append(node)


class Graph(t.Generic[T_Node]):
  """ Wrapper for storing #Node#s and evaluating them as a graph. """

  def __init__(self) -> None:
    from nr.util.digraph import DiGraph
    self._digraph = DiGraph[str, T_Node, None]()
    self._last_node_added: T_Node | None = None
    self._fallback_dependencies: dict[str, t.Sequence[T_Node]] = {}
    self._edges_built = False

  def __repr__(self) -> str:
    return f'Graph(num_nodes={len(self._digraph.nodes)})'

  @property
  def nodes(self) -> t.Mapping[str, T_Node]:
    return self._digraph.nodes

  @property
  def last_node_added(self) -> T_Node | None:
    return self._last_node_added

  def add_node(self, node: T_Node, fallback_dependencies: t.Sequence[T_Node] | T_Node | None) -> None:
    """ Adds a node to the graph, and registers the fallback dependencies to use if #Node.dependencies is `None`
    when #build_edges() is called. """

    if node.name in self._digraph.nodes:
      raise ValueError(f'node name {node.name!r} is already in use')

    if fallback_dependencies is not None and not isinstance(fallback_dependencies, t.Sequence):
      fallback_dependencies = [fallback_dependencies]

    node.graph = self
    self._digraph.add_node(node.name, node)
    self._fallback_dependencies[node.name] = fallback_dependencies or []
    self._last_node_added = node

  def build_edges(self) -> None:
    """ Builds the edges of the graph by inspecting the #Node.dependencies. """

    for node in self._digraph.nodes.values():
      if node.dependencies is None and node.predecessors is None:
        dependencies = self._fallback_dependencies[node.name]
      else:
        dependencies = node.dependencies or []
      for dependency in dependencies:
        self._digraph.add_edge(dependency.name, node.name, None)
      for successor in (node.predecessors or []):
        self._digraph.add_edge(node.name, successor.name, None)
    self._edges_built = True

  def execution_order(self) -> t.Iterator[T_Node]:
    """ Returns the nodes in the graph in execution order. Will call #build_edges() if it hasn't been called yet. """

    from nr.util.digraph.algorithm.topological_sort import topological_sort

    if not self._edges_built:
      self.build_edges()

    return (self._digraph.nodes[k] for k in topological_sort(self._digraph))
