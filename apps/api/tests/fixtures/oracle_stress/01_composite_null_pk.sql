-- Stress fixture: composite "primary key" with a nullable second column.
--
-- Targets the keyset NULL guard at apps/api/src/migrate/keyset.py. A
-- naive keyset walk over (a, b) where b is nullable would silently
-- halt mid-table when it hits a NULL. The runtime guard now refuses
-- to resume from a NULL last_pk, and `IntrospectedSchema.nullable_pk_columns()`
-- surfaces the offender pre-flight so an operator hears about it
-- during planning rather than after rows go missing.
--
-- Real Oracle PRIMARY KEY constraints implicitly enforce NOT NULL,
-- so this case typically arises when an "effective" PK was declared
-- via a UNIQUE INDEX over partially-nullable columns. We construct
-- exactly that shape here: UNIQUE on (a, b) with b nullable.

CREATE TABLE system.HAFEN_STRESS_NULL_PK (
    a NUMBER(6) NOT NULL,
    b NUMBER(6),  -- deliberately nullable
    label VARCHAR2(50)
);

CREATE UNIQUE INDEX system.HAFEN_STRESS_NULL_PK_UQ
    ON system.HAFEN_STRESS_NULL_PK (a, b);

INSERT INTO system.HAFEN_STRESS_NULL_PK VALUES (1, 100, 'first');
INSERT INTO system.HAFEN_STRESS_NULL_PK VALUES (2, 200, 'second');
INSERT INTO system.HAFEN_STRESS_NULL_PK VALUES (3, NULL, 'has-null-in-pk-col');
INSERT INTO system.HAFEN_STRESS_NULL_PK VALUES (4, 400, 'fourth');

COMMIT;
