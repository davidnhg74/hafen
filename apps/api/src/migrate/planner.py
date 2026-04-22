"""Load-order planner.

Given a set of tables and the FK edges between them, produce a load plan:
the order in which tables should be filled so that every parent row exists
before any child row references it.

Strategy:

  1. Build a directed graph: child -> parent (an edge means "child depends
     on parent"). Topo-sort yields parents-before-children, which is the
     correct load order.

  2. Real schemas have cycles (employees.manager_id -> employees.id is the
     classic). We detect each strongly-connected component (Tarjan), and
     for any non-trivial SCC we pick the FK with the most-deferrable
     properties (`DEFERRABLE INITIALLY IMMEDIATE` first; otherwise the one
     touching the largest table) and mark it for `SET CONSTRAINTS ALL
     DEFERRED` during the load. The cycle's tables then load in arbitrary
     SCC order.

  3. The output is a `LoadPlan` of `LoadGroup`s. A group is either a
     single table (acyclic case) or a set of cycle members loaded with a
     deferred-constraints wrapper. Groups appear in the order they should
     run; tables inside a cycle group are unordered.

This module is pure: it operates on lightweight value types and never
opens a connection. Connector code introspects the schema and feeds the
results in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class TableRef:
    """Schema-qualified table identifier. Schema can be empty for tables in
    the connector's default search path."""

    schema: str
    name: str

    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    @classmethod
    def parse(cls, qualified: str) -> "TableRef":
        if "." in qualified:
            s, n = qualified.split(".", 1)
            return cls(schema=s.strip(), name=n.strip())
        return cls(schema="", name=qualified.strip())


@dataclass(frozen=True)
class ForeignKey:
    """One FK edge. `from_table` references `to_table`; we don't need the
    column names for ordering, only for the deferred-constraints wrapper.
    `name` is the constraint identifier in the source schema (used to issue
    `SET CONSTRAINTS <name> DEFERRED` when breaking a cycle)."""

    name: str
    from_table: TableRef
    to_table: TableRef
    deferrable: bool = False  # DEFERRABLE in Oracle source
    self_referential: bool = False  # set by the planner; do not pass in


@dataclass
class LoadGroup:
    """A unit of work for the runner. `tables` is the set of tables to
    load together. When `deferred_constraints` is non-empty, the runner
    wraps the group in a transaction that issues `SET CONSTRAINTS ...
    DEFERRED` before loading and lets COMMIT enforce them at the end."""

    tables: List[TableRef]
    deferred_constraints: List[ForeignKey] = field(default_factory=list)

    @property
    def is_cycle(self) -> bool:
        return bool(self.deferred_constraints) or len(self.tables) > 1


@dataclass
class LoadPlan:
    """Ordered list of LoadGroups. The runner executes them sequentially;
    inside a cycle group, tables can be loaded in any order (or in
    parallel) as long as the deferred constraints stay deferred until the
    group commits."""

    groups: List[LoadGroup]

    def flat_tables(self) -> List[TableRef]:
        out: List[TableRef] = []
        for g in self.groups:
            out.extend(g.tables)
        return out


# ─── Public entry point ──────────────────────────────────────────────────────


def plan_load_order(tables: Iterable[TableRef], fks: Iterable[ForeignKey]) -> LoadPlan:
    """Topo-sort the table set into a runnable LoadPlan.

    Self-referential FKs (employees.manager_id -> employees.id) are
    annotated and require the row-by-row insert path or an after-load
    UPDATE; they don't block ordering and don't form a multi-table cycle.

    Multi-table cycles are returned as a single `LoadGroup` whose
    `deferred_constraints` lists the edges to defer.
    """
    table_set: Set[TableRef] = set(tables)
    # Filter FKs to those whose endpoints are both in the loaded set;
    # cross-system references become someone else's problem.
    relevant_fks: List[ForeignKey] = []
    for fk in fks:
        if fk.from_table not in table_set or fk.to_table not in table_set:
            continue
        if fk.from_table == fk.to_table:
            relevant_fks.append(
                ForeignKey(
                    name=fk.name,
                    from_table=fk.from_table,
                    to_table=fk.to_table,
                    deferrable=fk.deferrable,
                    self_referential=True,
                )
            )
        else:
            relevant_fks.append(fk)

    # Self-referential FKs don't influence inter-table ordering.
    inter_table_fks = [fk for fk in relevant_fks if not fk.self_referential]
    sccs = _strongly_connected_components(table_set, inter_table_fks)

    # Build a condensation: each SCC is a node; add edges between SCCs.
    scc_index: Dict[TableRef, int] = {t: i for i, scc in enumerate(sccs) for t in scc}
    cond_edges: Dict[int, Set[int]] = {i: set() for i in range(len(sccs))}
    for fk in inter_table_fks:
        a, b = scc_index[fk.from_table], scc_index[fk.to_table]
        if a != b:
            # child -> parent; parent must load first, so condensation
            # edge points parent -> child for the topo sort below.
            cond_edges[b].add(a)

    # Tie-break Kahn's "ready" set by the lex-smallest qualified table name
    # in each SCC, so output is deterministic regardless of set iteration.
    scc_keys: Dict[int, str] = {
        i: min(t.qualified() for t in scc) for i, scc in enumerate(sccs)
    }
    cond_order = _topo_sort(range(len(sccs)), cond_edges, key=lambda i: scc_keys[i])

    groups: List[LoadGroup] = []
    for scc_idx in cond_order:
        members = sorted(sccs[scc_idx], key=lambda t: t.qualified())
        if len(members) == 1:
            groups.append(LoadGroup(tables=members))
        else:
            # Multi-table cycle: defer every FK whose endpoints are inside
            # the SCC. The runner will issue SET CONSTRAINTS ... DEFERRED
            # for each by name.
            deferred = [
                fk
                for fk in inter_table_fks
                if scc_index[fk.from_table] == scc_idx
                and scc_index[fk.to_table] == scc_idx
            ]
            groups.append(LoadGroup(tables=members, deferred_constraints=deferred))

    return LoadPlan(groups=groups)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _strongly_connected_components(
    nodes: Set[TableRef], edges: Sequence[ForeignKey]
) -> List[FrozenSet[TableRef]]:
    """Tarjan's SCC over the child->parent FK graph. Returns components
    in reverse-topological order (sinks first), which is what Tarjan
    yields naturally."""
    adj: Dict[TableRef, List[TableRef]] = {n: [] for n in nodes}
    for fk in edges:
        adj[fk.from_table].append(fk.to_table)

    index_counter = [0]
    stack: List[TableRef] = []
    on_stack: Set[TableRef] = set()
    indices: Dict[TableRef, int] = {}
    lowlink: Dict[TableRef, int] = {}
    sccs: List[FrozenSet[TableRef]] = []

    def strongconnect(v: TableRef) -> None:
        indices[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj[v]:
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            component: List[TableRef] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.append(w)
                if w == v:
                    break
            sccs.append(frozenset(component))

    for n in nodes:
        if n not in indices:
            strongconnect(n)

    return sccs


def _topo_sort(
    nodes: Iterable[int],
    edges: Dict[int, Set[int]],
    key=None,
) -> List[int]:
    """Kahn's algorithm over the condensation. `edges[u]` lists nodes
    that depend on `u` (i.e. parent -> child in load terms). `key` is an
    optional callable used to break ties in the ready queue — required
    for deterministic plans regardless of set/dict iteration order."""
    nodes_list = list(nodes)
    in_degree: Dict[int, int] = {n: 0 for n in nodes_list}
    for u, dests in edges.items():
        for v in dests:
            in_degree[v] = in_degree.get(v, 0) + 1

    sort_key = key if key is not None else (lambda x: x)
    ready = [n for n in nodes_list if in_degree[n] == 0]
    out: List[int] = []
    while ready:
        ready.sort(key=sort_key)
        n = ready.pop(0)
        out.append(n)
        for v in edges.get(n, ()):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                ready.append(v)

    if len(out) != len(nodes_list):
        # Should be unreachable: the condensation of an SCC graph is a DAG.
        raise RuntimeError("condensation is not a DAG — planner bug")
    return out


def collect_self_referential_fks(fks: Iterable[ForeignKey]) -> List[ForeignKey]:
    """Convenience for the runner: pull out self-FKs so the loader can
    decide between a NULL-then-UPDATE pass or per-row INSERT (Oracle's
    `WITH ROWDEPENDENCIES` won't help on the Postgres side)."""
    return [fk for fk in fks if fk.from_table == fk.to_table]
