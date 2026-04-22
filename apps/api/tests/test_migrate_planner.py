"""Pure-logic tests for the load-order planner.

The planner has no DB dependencies, so the tests are dense and fast —
each one constructs a tiny FK graph by hand and asserts on the plan.
"""

from __future__ import annotations

import pytest

from src.migrate.planner import (
    ForeignKey,
    LoadGroup,
    LoadPlan,
    TableRef,
    collect_self_referential_fks,
    plan_load_order,
)


def t(name: str, schema: str = "public") -> TableRef:
    return TableRef(schema=schema, name=name)


def fk(name: str, child: TableRef, parent: TableRef, deferrable: bool = False) -> ForeignKey:
    return ForeignKey(name=name, from_table=child, to_table=parent, deferrable=deferrable)


def _flat(plan: LoadPlan) -> list[str]:
    return [tbl.name for tbl in plan.flat_tables()]


# ─── Acyclic ordering ────────────────────────────────────────────────────────


class TestAcyclic:
    def test_single_table(self):
        plan = plan_load_order([t("emp")], [])
        assert _flat(plan) == ["emp"]
        assert plan.groups[0].is_cycle is False

    def test_simple_parent_child(self):
        # orders.customer_id -> customers.id; customers must load first.
        customers, orders = t("customers"), t("orders")
        plan = plan_load_order(
            [customers, orders],
            [fk("orders_cust_fk", orders, customers)],
        )
        assert _flat(plan) == ["customers", "orders"]

    def test_diamond(self):
        # users
        #   ├─> orders
        #   └─> reviews
        # both depend on users; users loads first, then orders/reviews
        # in deterministic alphabetic order.
        users, orders, reviews = t("users"), t("orders"), t("reviews")
        plan = plan_load_order(
            [users, orders, reviews],
            [
                fk("orders_user_fk", orders, users),
                fk("reviews_user_fk", reviews, users),
            ],
        )
        order = _flat(plan)
        assert order[0] == "users"
        assert set(order[1:]) == {"orders", "reviews"}

    def test_chain_three_levels(self):
        a, b, c = t("a"), t("b"), t("c")
        # c -> b -> a
        plan = plan_load_order([a, b, c], [fk("c_b", c, b), fk("b_a", b, a)])
        assert _flat(plan) == ["a", "b", "c"]

    def test_unrelated_islands(self):
        a, b, x, y = t("a"), t("b"), t("x"), t("y")
        plan = plan_load_order([a, b, x, y], [fk("b_a", b, a), fk("y_x", y, x)])
        order = _flat(plan)
        # a precedes b, x precedes y; relative order between islands is
        # deterministic but uninteresting.
        assert order.index("a") < order.index("b")
        assert order.index("x") < order.index("y")


# ─── Self-referential FKs ────────────────────────────────────────────────────


class TestSelfReferential:
    def test_self_fk_does_not_block(self):
        # employees.manager_id -> employees.id
        emp = t("employees")
        plan = plan_load_order([emp], [fk("emp_mgr_fk", emp, emp)])
        assert _flat(plan) == ["employees"]
        # Single-table group, so not flagged as a multi-table cycle.
        assert plan.groups[0].is_cycle is False

    def test_self_fk_extracted_for_runner(self):
        emp, dept = t("employees"), t("departments")
        fks = [
            fk("emp_dept_fk", emp, dept),
            fk("emp_mgr_fk", emp, emp),
        ]
        plan = plan_load_order([emp, dept], fks)
        # Departments still loads before employees.
        assert _flat(plan) == ["departments", "employees"]
        # The runner asks for self-FKs separately.
        self_fks = collect_self_referential_fks(fks)
        assert [f.name for f in self_fks] == ["emp_mgr_fk"]


# ─── Multi-table cycles ──────────────────────────────────────────────────────


class TestCycles:
    def test_two_table_cycle(self):
        # a -> b and b -> a
        a, b = t("a"), t("b")
        fks = [fk("a_to_b", a, b), fk("b_to_a", b, a)]
        plan = plan_load_order([a, b], fks)

        assert len(plan.groups) == 1
        group = plan.groups[0]
        assert {tbl.name for tbl in group.tables} == {"a", "b"}
        assert group.is_cycle
        # Both edges deferred.
        assert {fk.name for fk in group.deferred_constraints} == {"a_to_b", "b_to_a"}

    def test_three_table_cycle_with_acyclic_neighbor(self):
        # cycle: a -> b -> c -> a
        # plus an acyclic neighbor d -> a (loads after the cycle)
        a, b, c, d = t("a"), t("b"), t("c"), t("d")
        fks = [
            fk("a_b", a, b),
            fk("b_c", b, c),
            fk("c_a", c, a),
            fk("d_a", d, a),
        ]
        plan = plan_load_order([a, b, c, d], fks)
        # Two groups expected: the cycle (size 3), then d alone.
        groups = plan.groups
        cycle_group = next(g for g in groups if len(g.tables) == 3)
        d_group = next(g for g in groups if len(g.tables) == 1 and g.tables[0].name == "d")
        assert {t.name for t in cycle_group.tables} == {"a", "b", "c"}
        # d depends on a, which is in the cycle, so d must come after.
        assert groups.index(cycle_group) < groups.index(d_group)
        # The cycle group defers all three intra-cycle edges.
        assert {fk.name for fk in cycle_group.deferred_constraints} == {"a_b", "b_c", "c_a"}


# ─── Filtering & edge cases ──────────────────────────────────────────────────


class TestFiltering:
    def test_external_fk_endpoints_ignored(self):
        # FK targets a table the planner wasn't asked to load.
        a = t("a")
        external = t("not_in_set")
        plan = plan_load_order([a], [fk("a_ext", a, external)])
        # The external FK is dropped; a loads alone.
        assert _flat(plan) == ["a"]
        assert plan.groups[0].deferred_constraints == []

    def test_empty_input(self):
        plan = plan_load_order([], [])
        assert plan.groups == []

    def test_deterministic_ordering(self):
        # No FKs: alphabetic order is guaranteed.
        names = ["zeta", "alpha", "mu", "beta"]
        tables = [t(n) for n in names]
        plan = plan_load_order(tables, [])
        assert _flat(plan) == sorted(names)


# ─── Schema-qualified names ──────────────────────────────────────────────────


class TestSchemaQualified:
    def test_same_name_different_schema_treated_as_distinct(self):
        # Two `audit_log` tables in different schemas — they should not
        # collapse and the FK targets the explicit one.
        sales_audit = TableRef(schema="sales", name="audit_log")
        ops_audit = TableRef(schema="ops", name="audit_log")
        sales_orders = TableRef(schema="sales", name="orders")
        plan = plan_load_order(
            [sales_audit, ops_audit, sales_orders],
            [fk("orders_audit_fk", sales_orders, sales_audit)],
        )
        # sales.audit_log loads before sales.orders; ops.audit_log is
        # independent and lands wherever the topo decides.
        order = [t.qualified() for t in plan.flat_tables()]
        assert order.index("sales.audit_log") < order.index("sales.orders")
        assert "ops.audit_log" in order

    def test_parse_qualified(self):
        assert TableRef.parse("hr.employees") == TableRef(schema="hr", name="employees")
        assert TableRef.parse("plain") == TableRef(schema="", name="plain")


# ─── Sanity on the LoadGroup/LoadPlan dataclasses ────────────────────────────


class TestPlanShape:
    def test_load_group_is_cycle_signal(self):
        single = LoadGroup(tables=[t("a")])
        multi = LoadGroup(tables=[t("a"), t("b")])
        deferred = LoadGroup(tables=[t("a")], deferred_constraints=[fk("x", t("a"), t("a"))])
        assert single.is_cycle is False
        assert multi.is_cycle is True
        assert deferred.is_cycle is True
