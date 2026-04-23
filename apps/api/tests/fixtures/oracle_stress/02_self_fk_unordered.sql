-- Stress fixture: self-referential FK with non-hierarchical ordering.
--
-- Targets the runner's NULL-then-UPDATE pass for self-FKs
-- (apps/api/src/migrate/runner.py:null_then_update_columns).
-- HR.EMPLOYEES happens to be hierarchically ordered (smaller IDs are
-- managers of larger IDs) which lets a naive in-PK-order COPY succeed
-- by accident. This fixture deliberately INVERTS that ordering:
-- children's IDs are SMALLER than their parents'. With the self-FK
-- installed on the target, a naive COPY would FK-fail on the first
-- child row. The runner's two-pass handler must NULL the manager_id
-- column during COPY, then UPDATE it from the source after.

CREATE TABLE system.HAFEN_STRESS_SELF_FK (
    id NUMBER(6) NOT NULL PRIMARY KEY,
    name VARCHAR2(50) NOT NULL,
    manager_id NUMBER(6)
);

-- Five rows where every non-root row points UP to a LARGER id.
-- Insert order is deliberately scrambled to make the point that
-- the migration must work regardless of source insert order.
INSERT INTO system.HAFEN_STRESS_SELF_FK VALUES (1, 'Junior', 4);   -- → Mid
INSERT INTO system.HAFEN_STRESS_SELF_FK VALUES (2, 'Mid', 4);      -- → Mid (peer)
INSERT INTO system.HAFEN_STRESS_SELF_FK VALUES (3, 'Senior', 5);   -- → Director
INSERT INTO system.HAFEN_STRESS_SELF_FK VALUES (4, 'Director', 5); -- → Director (peer)
INSERT INTO system.HAFEN_STRESS_SELF_FK VALUES (5, 'Root', NULL);  -- root, loaded last in id order

-- Self-FK on the SOURCE so the data is realistic. The target gets
-- the same constraint installed by the test harness so the
-- NULL-then-UPDATE pass actually has something to satisfy.
ALTER TABLE system.HAFEN_STRESS_SELF_FK
    ADD CONSTRAINT HAFEN_STRESS_SELF_FK_MGR
    FOREIGN KEY (manager_id) REFERENCES system.HAFEN_STRESS_SELF_FK(id);

COMMIT;
