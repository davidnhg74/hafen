-- Stress fixture: VARCHAR2 with multi-byte UTF-8 content.
--
-- Targets apps/api/src/migrate/quality.py:scan_varchar_lengths.
-- An Oracle VARCHAR2(20 BYTE) column holding 18 ASCII chars fits a
-- PG VARCHAR(20) target with room to spare. The same column holding
-- 18 multi-byte UTF-8 chars uses 36+ bytes — overflowing a PG
-- VARCHAR(20) on COPY unless the operator widens the target column.
-- The pre-copy quality scan should flag this BEFORE the migration runs.
--
-- We declare the column generously sized in source so we can stuff
-- multi-byte chars into it; the test harness then introspects it as
-- if its target counterpart were narrower (the common operator
-- mistake we're guarding against).

CREATE TABLE system.HAFEN_STRESS_BYTE_VS_CHAR (
    id NUMBER(6) NOT NULL PRIMARY KEY,
    name_short VARCHAR2(60),  -- room for multi-byte content
    label VARCHAR2(50)
);

-- 18 multi-byte chars (3 bytes each in UTF-8) = 54 bytes.
-- A target column declared VARCHAR(20) (in chars) fits; declared
-- VARCHAR2(20 BYTE) does NOT — and that's the bug the quality
-- scanner catches.
INSERT INTO system.HAFEN_STRESS_BYTE_VS_CHAR VALUES
    (1, 'Hello',                        'ascii — fits anywhere');
INSERT INTO system.HAFEN_STRESS_BYTE_VS_CHAR VALUES
    (2, 'こんにちは世界、テスト中です',     'jp 14 chars / 42 bytes');
INSERT INTO system.HAFEN_STRESS_BYTE_VS_CHAR VALUES
    (3, '여러 한국어 글자가 들어 있습니다',  'kr 18 chars / 54 bytes');
INSERT INTO system.HAFEN_STRESS_BYTE_VS_CHAR VALUES
    (4, '中文测试字符串内容长度超过',        'cn 13 chars / 39 bytes');

COMMIT;
